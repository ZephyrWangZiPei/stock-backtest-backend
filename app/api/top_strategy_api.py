from flask_restx import Namespace, Resource, fields
from flask import request
from app.api.responses import api_success, api_error, get_api_response_model, get_api_list_response_model
from app.models import TopStrategyStock, Strategy
from app import db
import logging

logger = logging.getLogger(__name__)

ns = Namespace('top-strategy', description='Top策略股票接口')

# 定义返回数据结构
top_stock_model = ns.model('TopStrategyStock', {
    'id': fields.Integer(description='ID'),
    'strategy_id': fields.Integer(description='策略ID'),
    'strategy_name': fields.String(description='策略名称'),
    'stock_code': fields.String(description='股票代码'),
    'stock_name': fields.String(description='股票名称'),
    'win_rate': fields.Float(description='胜率'),
    'total_return': fields.Float(description='总收益率'),
    'annual_return': fields.Float(description='年化收益率'),
    'max_drawdown': fields.Float(description='最大回撤'),
    'sharpe_ratio': fields.Float(description='夏普比率'),
    'trade_count': fields.Integer(description='交易次数'),
    'win_rate_lb': fields.Float(description='胜率置信下界'),
    'expectancy': fields.Float(description='期望收益率'),
    'profit_factor': fields.Float(description='盈亏比'),
    'rank': fields.Integer(description='排名'),
    'backtest_period_days': fields.Integer(description='回测周期天数'),
    'initial_capital': fields.Float(description='初始资金'),
    'created_at': fields.String(description='创建时间'),
    'updated_at': fields.String(description='更新时间'),
    'potential_rating': fields.String(description='AI潜力评级 (高/中/低)'),
    'confidence_score': fields.Float(description='AI置信率 (0-100)'),
    'recommendation_reason': fields.String(description='AI推荐理由'),
    'buy_point': fields.String(description='AI建议买入点位'),
    'sell_point': fields.String(description='AI建议卖出点位'),
    'risks': fields.String(description='AI风险提示'),
})

strategy_summary_model = ns.model('StrategyTopStocks', {
    'strategy_id': fields.Integer(description='策略ID'),
    'strategy_name': fields.String(description='策略名称'),
    'top_stocks': fields.List(fields.Nested(top_stock_model), description='Top股票列表')
})

# 创建列表响应模型
response_model = get_api_list_response_model(ns, strategy_summary_model)
single_response_model = get_api_list_response_model(ns, top_stock_model)

@ns.route('/')
class TopStrategyStockList(Resource):
    @ns.doc('get_all_top_strategy_stocks')
    @ns.marshal_with(response_model, code=200)
    def get(self):
        """获取所有策略的Top股票，按策略分组"""
        try:
            # 获取所有有Top股票记录的策略
            strategies_with_tops = db.session.query(Strategy).join(TopStrategyStock).distinct().all()
            
            result = []
            for strategy in strategies_with_tops:
                top_stocks = TopStrategyStock.query.filter_by(
                    strategy_id=strategy.id
                ).order_by(TopStrategyStock.rank).all()
                
                result.append({
                    'strategy_id': strategy.id,
                    'strategy_name': strategy.name,
                    'top_stocks': [stock.to_dict() for stock in top_stocks]
                })
            
            return api_success(data=result, message=f'获取到 {len(result)} 个策略的Top股票')
            
        except Exception as e:
            logger.error(f'获取Top策略股票失败: {e}', exc_info=True)
            return api_error('获取Top策略股票失败', 500)

@ns.route('/strategy/<int:strategy_id>')
class StrategyTopStocks(Resource):
    @ns.doc('get_strategy_top_stocks')
    @ns.marshal_with(single_response_model, code=200)
    def get(self, strategy_id):
        """获取指定策略的Top股票"""
        try:
            strategy = Strategy.query.get(strategy_id)
            if not strategy:
                return api_error('策略不存在', 404)
            
            top_stocks = TopStrategyStock.query.filter_by(
                strategy_id=strategy_id
            ).order_by(TopStrategyStock.rank).all()
            
            if not top_stocks:
                return api_success(data=[], message=f'策略 {strategy.name} 暂无Top股票数据')
            
            result = [stock.to_dict() for stock in top_stocks]
            return api_success(data=result, message=f'获取到策略 {strategy.name} 的 {len(result)} 只Top股票')
            
        except Exception as e:
            logger.error(f'获取策略Top股票失败: {e}', exc_info=True)
            return api_error('获取策略Top股票失败', 500)

@ns.route('/latest')
class LatestTopStocks(Resource):
    @ns.doc('get_latest_top_stocks')
    @ns.marshal_with(response_model, code=200)
    def get(self):
        """获取最新的Top策略股票（基于更新时间）"""
        try:
            # 获取每个策略最新更新的Top股票
            latest_updates = db.session.query(
                TopStrategyStock.strategy_id,
                db.func.max(TopStrategyStock.updated_at).label('latest_update')
            ).group_by(TopStrategyStock.strategy_id).subquery()
            
            strategies_with_latest = db.session.query(Strategy).join(
                latest_updates, Strategy.id == latest_updates.c.strategy_id
            ).all()
            
            result = []
            for strategy in strategies_with_latest:
                # 获取该策略最新的Top股票
                top_stocks = TopStrategyStock.query.filter_by(
                    strategy_id=strategy.id
                ).order_by(TopStrategyStock.rank).all()
                
                if top_stocks:
                    result.append({
                        'strategy_id': strategy.id,
                        'strategy_name': strategy.name,
                        'top_stocks': [stock.to_dict() for stock in top_stocks]
                    })
            
            return api_success(data=result, message=f'获取到 {len(result)} 个策略的最新Top股票')
            
        except Exception as e:
            logger.error(f'获取最新Top策略股票失败: {e}', exc_info=True)
            return api_error('获取最新Top策略股票失败', 500)

@ns.route('/stats')
class TopStocksStats(Resource):
    @ns.doc('get_top_stocks_stats')
    def get(self):
        """获取Top策略股票的统计信息"""
        try:
            # 统计各策略的Top股票数量
            strategy_stats = db.session.query(
                Strategy.name,
                db.func.count(TopStrategyStock.id).label('stock_count'),
                db.func.avg(TopStrategyStock.win_rate).label('avg_win_rate'),
                db.func.max(TopStrategyStock.updated_at).label('last_update')
            ).join(TopStrategyStock).group_by(Strategy.id, Strategy.name).all()
            
            result = []
            for stat in strategy_stats:
                # 安全转换日期
                if stat.last_update:
                    try:
                        last_update_str = stat.last_update.isoformat()
                    except AttributeError:
                        last_update_str = str(stat.last_update)
                else:
                    last_update_str = None

                result.append({
                    'strategy_name': stat.name,
                    'stock_count': stat.stock_count,
                    'avg_win_rate': float(stat.avg_win_rate) if stat.avg_win_rate else 0,
                    'last_update': last_update_str
                })
            
            total_stocks = db.session.query(TopStrategyStock).count()
            total_strategies = len(result)
            
            return api_success(data={
                'total_strategies': total_strategies,
                'total_top_stocks': total_stocks,
                'strategy_details': result
            }, message='获取统计信息成功')
            
        except Exception as e:
            logger.error(f'获取Top策略股票统计失败: {e}', exc_info=True)
            return api_error('获取统计信息失败', 500) 