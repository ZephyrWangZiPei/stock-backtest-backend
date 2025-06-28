from flask import request
from flask_restx import Namespace, Resource
import logging
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import desc

from app.data_collector.baostock_client import BaostockClient
from app.models import Strategy, Stock, CandidateStock, DailyData
from app.strategies import get_strategy_by_identifier
from app import db

logger = logging.getLogger(__name__)

ns = Namespace('signals', description='策略信号接口')

def _get_history_from_db(stock_code: str, days_ago: int = 200) -> pd.DataFrame:
    """从数据库获取指定股票的历史日线数据"""
    end_date = datetime.now()
    # 多获取一些数据以防交易日不连续
    start_date = end_date - timedelta(days=days_ago * 1.5) 

    records = db.session.query(DailyData).join(Stock).filter(
        Stock.code == stock_code,
        DailyData.trade_date >= start_date
    ).order_by(desc(DailyData.trade_date)).limit(days_ago).all()

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame([r.to_dict() for r in records])
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values(by='trade_date', ascending=True)
    
    # 策略内部期望的列名是 'close_price' 和 'trade_date'
    if 'close' in df.columns:
        df.rename(columns={'close': 'close_price'}, inplace=True)
    if 'date' in df.columns:
        df.rename(columns={'date': 'trade_date'}, inplace=True)
        
    return df

def _generate_signals_for_stock(stock_code: str, use_db: bool = True, baostock_client: BaostockClient = None) -> dict:
    """为单只股票生成所有策略的最新信号, 可选择数据源或传入一个已激活的客户端"""
    signals = {'buy': 0, 'sell': 0, 'hold': 0}
    df = pd.DataFrame()

    try:
        if use_db:
            df = _get_history_from_db(stock_code, days_ago=200)
        else:
            # 如果传入了client，则使用它；否则，创建一个新的
            if baostock_client:
                df = baostock_client.get_stock_history(stock_code, days_ago=200)
            else:
                with BaostockClient() as client:
                    df = client.get_stock_history(stock_code, days_ago=200)
        
        if df.empty or len(df) < 50:  # 数据不足
            return {}
        
        # --- 列名标准化 ---
        # 数据库来源: close_price, trade_date
        # BaoStock来源: close, date
        if 'close' in df.columns:
            df.rename(columns={'close': 'close_price'}, inplace=True)
        if 'date' in df.columns:
            df.rename(columns={'date': 'trade_date'}, inplace=True)

        if 'close_price' not in df.columns:
            logger.warning(f"数据中缺少 'close_price'/'close' 列: {stock_code}")
            return {}
        if 'trade_date' not in df.columns:
            logger.warning(f"数据中缺少 'trade_date'/'date' 列: {stock_code}")
            return {}

        df['trade_date'] = pd.to_datetime(df['trade_date'])

        strategies = Strategy.query.all()
        for strategy_model in strategies:
            StrategyClass = get_strategy_by_identifier(strategy_model.identifier)
            if not StrategyClass:
                continue
            
            strategy_instance = StrategyClass()
            signals_df = strategy_instance.generate_signals(df.copy()) # 使用copy避免后续策略影响
            if not signals_df.empty:
                last_signal = signals_df['signal'].iloc[-1]
                if last_signal == 1:
                    signals['buy'] += 1
                elif last_signal == -1:
                    signals['sell'] += 1
                else:
                    signals['hold'] += 1
        
        return signals

    except Exception as e:
        logger.error(f"为股票 {stock_code} 生成信号时出错: {e}", exc_info=True)
        return {}

@ns.route('/recommendations')
class Recommendations(Resource):
    @ns.doc('获取策略推荐的股票')
    def get(self):
        """直接从数据库获取海选出的推荐列表"""
        logger.info("开始从数据库获取策略推荐...")
        try:
            # 直接查询 CandidateStock 表
            candidate_stocks = CandidateStock.query.all()
            logger.info(f"从候选池中发现 {len(candidate_stocks)} 只股票。")

            if not candidate_stocks:
                return {'success': True, 'message': '当前候选池为空，暂无推荐', 'data': []}

            recommendations = [{
                'code': candidate.code,
                'name': candidate.name,
                'reason': candidate.reason,  # 海选时记录的原因
                'signals': {'buy': 1, 'sell': 0, 'hold': 0} # 构造一个虚拟信号，表示这是买入推荐
            } for candidate in candidate_stocks]
            
            logger.info(f"推荐获取完成，共返回 {len(recommendations)} 个推荐。")
            return {
                'success': True,
                'message': f'发现 {len(recommendations)} 个推荐',
                'data': recommendations
            }
        except Exception as e:
            logger.error(f"获取推荐列表时发生严重错误: {e}", exc_info=True)
            return {'success': False, 'message': f'服务器错误: {str(e)}'}, 500

@ns.route('/batch')
class BatchSignals(Resource):
    @ns.doc('批量获取股票的策略信号')
    @ns.param('codes', '股票代码列表，逗号分隔', type=str, required=True)
    def get(self):
        """批量获取多只股票的策略信号汇总"""
        codes_param = request.args.get('codes', '')
        if not codes_param:
            return {'success': False, 'message': '请提供股票代码'}, 400

        codes = [code.strip() for code in codes_param.split(',') if code.strip()]
        
        results = {}
        errors = []

        try:
            # 在循环外创建并管理一个BaostockClient实例
            with BaostockClient() as client:
                for code in codes:
                    # 实时数据，明确指定 use_db=False，并传入共享的client
                    signal_summary = _generate_signals_for_stock(code, use_db=False, baostock_client=client)
                    if signal_summary:
                        results[code] = signal_summary
                    else:
                        errors.append(code)

            return {
                'success': True,
                'message': f'成功为 {len(results)} 只股票生成信号',
                'data': results,
                'errors': errors
            }

        except Exception as e:
            logger.error(f"批量生成信号接口错误: {e}")
            return {'success': False, 'message': f'服务器错误: {str(e)}'}, 500 