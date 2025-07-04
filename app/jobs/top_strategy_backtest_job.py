import logging
from datetime import datetime, timedelta
import math

from app import db, _current_app_instance, socketio
from app.models import Strategy, BacktestResult, CandidateStock, TopStrategyStock, Stock
from app.backtester.engine import BacktestEngine
from app.data_collector import DataCollector
from app.strategies import STRATEGY_MAP
from app.api.deepseek_api import _analyze_top_stocks_with_deepseek

logger = logging.getLogger(__name__)

def update_top_strategy_stocks(strategies: list[str] = None, top_n: int = 5, period_days: int = 1095, initial_capital: float = 100000, min_trade_count: int = 3):
    """
    执行多策略回测任务，计算各策略胜率最高的前N只股票并保存到数据库。
    此函数会自动创建并运行在它自己的Flask应用上下文中。
    """
    if not _current_app_instance:
        logger.error("无法获取Flask应用实例，Top策略回测任务无法执行。")
        return

    app = _current_app_instance
    with app.app_context():
        logger.info("--- 开始执行Top策略回测任务 ---")
        socketio.emit('job_status', {
            'job_name': 'top_strategy_backtest',
            'status': 'started',
            'message': '开始执行Top策略回测任务...'
        }, namespace='/scheduler')
        
        try:
            # 默认策略列表
            if strategies is None:
                strategies = list(STRATEGY_MAP.keys())
            
            # 1. 获取潜力股列表
            potential_codes = [c.code for c in CandidateStock.query.all()]
            if not potential_codes:
                dc = DataCollector()
                potential_codes = dc.screen_potential_stocks()
            
            if not potential_codes:
                logger.warning("未找到潜力股，回测任务结束。")
                socketio.emit('job_status', {
                    'job_name': 'top_strategy_backtest', 'status': 'completed', 
                    'message': '未找到潜力股，任务结束。'
                }, namespace='/scheduler')
                return
            
            logger.info(f"将对 {len(potential_codes)} 只潜力股进行 {len(strategies)} 种策略回测")
            
            # 计算总任务数用于进度显示
            total_tasks = len(strategies) * len(potential_codes)
            completed_tasks = 0
            
            socketio.emit('job_progress', {
                'job_name': 'top_strategy_backtest', 'progress': 0, 'total': total_tasks,
                'message': f'准备对 {len(potential_codes)} 只潜力股进行 {len(strategies)} 种策略回测...'
            }, namespace='/scheduler')

            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=period_days)

            for strategy_identifier in strategies:
                logger.info(f"\n=== 开始策略 {strategy_identifier} 回测 ===")
                
                strat_model = Strategy.query.filter_by(identifier=strategy_identifier).first()
                if not strat_model:
                    logger.error(f"策略 {strategy_identifier} 未在数据库找到，跳过。")
                    completed_tasks += len(potential_codes)  # 跳过的任务也要计入进度
                    continue

                # 清除该策略的旧Top记录
                TopStrategyStock.query.filter_by(strategy_id=strat_model.id).delete()
                db.session.commit()

                top_list: list[dict] = []  # 保存 {code, win_rate, result_obj}

                for code in potential_codes:
                    completed_tasks += 1
                    
                    # 每10个任务发送一次进度更新
                    if completed_tasks % 10 == 0:
                        socketio.emit('job_progress', {
                            'job_name': 'top_strategy_backtest',
                            'progress': completed_tasks,
                            'total': total_tasks,
                            'message': f'正在回测: {strategy_identifier} - {code} ({completed_tasks}/{total_tasks})'
                        }, namespace='/scheduler')

                    try:
                        engine = BacktestEngine(
                            strategy_id=strat_model.id,
                            start_date=start_date.strftime('%Y-%m-%d'),
                            end_date=end_date.strftime('%Y-%m-%d'),
                            initial_capital=initial_capital,
                            stock_codes=[code],
                            custom_parameters=None
                        )
                        result_id = engine.run()
                        if not result_id:
                            continue
                        
                        result: BacktestResult = BacktestResult.query.get(result_id)
                        if not result or result.win_rate is None:
                            continue
                        
                        win_rate = float(result.win_rate)
                        trade_count = result.total_trades or 0
                        if trade_count < min_trade_count:
                            # 交易次数不足，忽略该股票
                            continue
                        
                        # Wilson score lower bound at 95% confidence
                        def wilson_lb(p: float, n: int, z: float = 1.96):
                            if n == 0:
                                return 0.0
                            return (p + z*z/(2*n) - z * math.sqrt((p*(1-p) + z*z/(4*n))/n)) / (1 + z*z/n)
                        win_rate_lb = wilson_lb(win_rate, trade_count)
                        expectancy = 0.0
                        if trade_count > 0 and result.total_return is not None:
                            expectancy = float(result.total_return) / trade_count
                        
                        # 维护前 top_n 列表，根据 win_rate_lb 排序
                        score = win_rate_lb  # 用置信下界做比较
                        if len(top_list) < top_n:
                            top_list.append({'code': code, 'score': score, 'result': result,
                                             'trade_count': trade_count, 'win_rate_lb': win_rate_lb,
                                             'expectancy': expectancy,
                                             'profit_factor': float(result.profit_factor) if result.profit_factor else None})
                        else:
                            min_entry = min(top_list, key=lambda x: x['score'])
                            if score > min_entry['score']:
                                top_list.remove(min_entry)
                                top_list.append({'code': code, 'score': score, 'result': result,
                                                 'trade_count': trade_count, 'win_rate_lb': win_rate_lb,
                                                 'expectancy': expectancy,
                                                 'profit_factor': float(result.profit_factor) if result.profit_factor else None})
                                
                    except Exception as e:
                        logger.error(f"回测 {code} 时出错: {e}")
                        db.session.rollback()
                        continue

                # 排序并保存到数据库
                top_list.sort(key=lambda x: x['score'], reverse=True)
                
                for rank, entry in enumerate(top_list, 1):
                    code = entry['code']
                    result = entry['result']
                    
                    # 获取股票名称
                    stock = Stock.query.filter_by(code=code).first()
                    stock_name = stock.name if stock else None
                    
                    top_stock = TopStrategyStock(
                        strategy_id=strat_model.id,
                        stock_code=code,
                        stock_name=stock_name,
                        win_rate=result.win_rate,
                        total_return=result.total_return,
                        annual_return=result.annual_return,
                        max_drawdown=result.max_drawdown,
                        sharpe_ratio=result.sharpe_ratio,
                        backtest_result_id=result.id,
                        rank=rank,
                        backtest_period_days=period_days,
                        initial_capital=initial_capital,
                        trade_count=entry['trade_count'],
                        win_rate_lb=entry['win_rate_lb'],
                        expectancy=entry['expectancy'],
                        profit_factor=entry.get('profit_factor')
                    )
                    db.session.add(top_stock)
                
                db.session.commit()

                # 调用 DeepSeek 进行 AI 分析，并更新 TopStrategyStock 记录
                if top_list:
                    try:
                        # 获取刚刚保存的 TopStrategyStock 对象列表，用于AI分析
                        # 需要重新查询，因为top_stock对象可能在db.session.add后没有刷新其ID
                        # 或者直接使用 top_stock 对象的列表，但在 _analyze_top_stocks_with_deepseek 中进行查询
                        # 为了简化，我们直接传入 top_list 中的 stock_code，然后在 AI 函数内部查询最新的 TopStrategyStock
                        # 但更好的方式是，将 db.session.add 后的 top_stock 对象存起来，然后批量传入
                        
                        # 考虑到TopStrategyStock是刚刚创建并提交的，我们可以直接根据 strategy_id 和 rank 查询回来
                        # 或者更简单的，我们让 _analyze_top_stocks_with_deepseek 直接使用传入的 candidate_top_stocks
                        # 但这里是针对单个策略的top_list，所以我们先保存，再对这个top_list进行AI分析

                        # 重新查询这些股票，确保它们是持久化且可追踪的Session对象
                        # 获取刚刚保存的 TopStrategyStock 记录的 ID 列表
                        saved_top_stock_codes = [entry['code'] for entry in top_list]
                        ai_candidate_top_stocks = TopStrategyStock.query.filter(
                            TopStrategyStock.strategy_id == strat_model.id,
                            TopStrategyStock.stock_code.in_(saved_top_stock_codes)
                        ).all()

                        if ai_candidate_top_stocks:
                            logger.info(f"正在为策略 {strategy_identifier} 的 {len(ai_candidate_top_stocks)} 只Top股票调用DeepSeek AI分析...")
                            ai_analysis_results = _analyze_top_stocks_with_deepseek(app, ai_candidate_top_stocks)
                            
                            # 更新 TopStrategyStock 记录
                            for ai_result in ai_analysis_results:
                                stock_code = ai_result.get('stock_code')
                                # Find the corresponding TopStrategyStock object to update
                                top_stock_to_update = next((ts for ts in ai_candidate_top_stocks if ts.stock_code == stock_code), None)
                                if top_stock_to_update:
                                    top_stock_to_update.potential_rating = ai_result.get('potential_rating')
                                    top_stock_to_update.confidence_score = ai_result.get('confidence_score')
                                    top_stock_to_update.recommendation_reason = ai_result.get('recommendation_reason')
                                    top_stock_to_update.buy_point = ai_result.get('buy_point')
                                    top_stock_to_update.sell_point = ai_result.get('sell_point')
                                    top_stock_to_update.risks = ai_result.get('risks')
                                    db.session.add(top_stock_to_update) # Mark for update
                            db.session.commit() # Commit the AI analysis updates
                            logger.info(f"策略 {strategy_identifier} 的Top股票AI分析结果已保存。")

                    except Exception as ai_e:
                        logger.error(f"DeepSeek AI分析 {strategy_identifier} 的Top股票时出错: {ai_e}", exc_info=True)
                        db.session.rollback() # Rollback only AI analysis part if it fails
                        # Continue with the next strategy, don't block the whole job
                
                logger.info(f"策略 {strategy_identifier} 胜率 Top {top_n} 已保存: {[(d['code'], round(d['score'],3)) for d in top_list]}")

            message = f"Top策略回测任务完成！共处理 {len(strategies)} 种策略，每种策略保存前 {top_n} 只股票。"
            logger.info(message)
            socketio.emit('job_status', {
                'job_name': 'top_strategy_backtest', 'status': 'completed', 'message': message
            }, namespace='/scheduler')

        except Exception as e:
            db.session.rollback()
            error_message = f"Top策略回测任务发生严重错误: {e}"
            logger.error(error_message, exc_info=True)
            socketio.emit('job_status', {
                'job_name': 'top_strategy_backtest', 'status': 'failed', 'message': str(e)
            }, namespace='/scheduler')

def backtest_potential_stocks(strategies: list[str] = None, top_n: int = 5, period_days: int = 1095, initial_capital: float = 100000):
    """
    按给定策略对潜力股做回测，返回各策略胜率最高的前 N 只股票。
    此函数保留用于API直接调用，但建议使用定时任务 update_top_strategy_stocks。
    """
    if strategies is None:
        strategies = list(STRATEGY_MAP.keys())

    if not _current_app_instance:
        logger.error("无法获取 Flask 应用实例，无法执行回测任务。")
        return {}

    app = _current_app_instance
    with app.app_context():
        # 1. 获取潜力股列表：优先使用数据库已有的 CandidateStock
        potential_codes = [c.code for c in CandidateStock.query.all()]
        if not potential_codes:
            # 若数据库为空，则动态筛选
            dc = DataCollector()
            potential_codes = dc.screen_potential_stocks()
        if not potential_codes:
            logger.warning("未找到潜力股，回测任务结束。")
            return {}
        logger.info(f"将对 {len(potential_codes)} 只潜力股回测：{potential_codes[:10]} …")

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=period_days)

        summary = {}

        for strategy_identifier in strategies:
            logger.info(f"\n=== 开始策略 {strategy_identifier} 回测 ===")
            strat_model = Strategy.query.filter_by(identifier=strategy_identifier).first()
            if not strat_model:
                logger.error(f"策略 {strategy_identifier} 未在数据库找到，跳过。")
                continue

            top_list: list[dict] = []  # 保存 {code, win_rate, result_id}

            for code in potential_codes:
                try:
                    engine = BacktestEngine(
                        strategy_id=strat_model.id,
                        start_date=start_date.strftime('%Y-%m-%d'),
                        end_date=end_date.strftime('%Y-%m-%d'),
                        initial_capital=initial_capital,
                        stock_codes=[code],
                        custom_parameters=None
                    )
                    result_id = engine.run()
                    if not result_id:
                        continue
                    result: BacktestResult = BacktestResult.query.get(result_id)
                    if not result or result.win_rate is None:
                        continue
                    win_rate = float(result.win_rate)
                    # 维护前 top_n
                    if len(top_list) < top_n:
                        top_list.append({'code': code, 'win_rate': win_rate, 'result_id': result_id})
                    else:
                        min_entry = min(top_list, key=lambda x: x['win_rate'])
                        if win_rate > min_entry['win_rate']:
                            top_list.remove(min_entry)
                            top_list.append({'code': code, 'win_rate': win_rate, 'result_id': result_id})
                except Exception as e:
                    logger.error(f"回测 {code} 时出错: {e}")
                    db.session.rollback()
                    continue

            # 排序输出
            top_list.sort(key=lambda x: x['win_rate'], reverse=True)
            summary[strategy_identifier] = top_list
            logger.info(f"策略 {strategy_identifier} 胜率 Top {top_n}: {[(d['code'], d['win_rate']) for d in top_list]}")

        return summary

if __name__ == '__main__':
    # 允许命令行直接运行调试
    from app import create_app
    app = create_app()
    with app.app_context():
        update_top_strategy_stocks(strategies=['macd', 'dual_moving_average', 'rsi']) 