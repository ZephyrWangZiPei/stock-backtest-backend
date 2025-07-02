import logging
from datetime import datetime
from flask import current_app

logger = logging.getLogger(__name__)

def emit_scheduler_status_job():
    """
    A standalone, pickle-friendly job function to emit scheduler status via WebSocket.
    It dynamically imports app components to avoid circular dependencies at startup.
    """
    try:
        # 动态导入避免循环依赖
        from app import create_app, socketio
        
        # 创建应用上下文
        app = create_app()
        
        with app.app_context():
            if not hasattr(app, 'scheduler'):
                logger.error("Flask app does not have scheduler attribute in 'emit_scheduler_status_job'.")
                return
                
            scheduler = app.scheduler
            
            # Now that we are in a context, we can safely use socketio and scheduler
            if not socketio or not scheduler.scheduler:
                logger.warning("Scheduler or SocketIO not available in 'emit_scheduler_status_job'.")
                return
            
            is_running = scheduler.scheduler.running
            
            jobs_data = []
            jobs_in_store = scheduler.get_jobs()
            
            for job in jobs_in_store:
                live_job = scheduler.scheduler.get_job(job.id)
                next_run_time = None
                if live_job and hasattr(live_job, 'next_run_time') and live_job.next_run_time:
                    next_run_time = live_job.next_run_time
                elif hasattr(job, 'trigger'):
                    now = datetime.now(job.trigger.timezone)
                    next_run_time = job.trigger.get_next_fire_time(None, now)

                jobs_data.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': next_run_time.strftime('%Y-%m-%d %H:%M:%S') if next_run_time else None,
                    'trigger': str(job.trigger)
                })
                
            status_data = {
                'is_running': is_running,
                'jobs_count': len(jobs_in_store),
                'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'jobs': jobs_data
            }
            
            # Use the global socketio instance to emit
            socketio.emit('scheduler_update', {'data': status_data})
    except Exception as e:
        logger.error(f"Error in scheduled job 'emit_scheduler_status_job': {e}", exc_info=True)

def daily_data_update_job():
    """每日数据更新任务"""
    try:
        app = current_app._get_current_object()
        from app import socketio
        from app.scheduler.tasks import DataUpdateTask
        
        task = DataUpdateTask(app, socketio)
        result = task.update_daily_data()
        
        logger.info(f"每日数据更新任务执行结果: {result}")
        
    except Exception as e:
        logger.error(f"每日数据更新任务执行失败: {e}", exc_info=True)

def stock_list_update_job():
    """股票列表更新任务"""
    try:
        app = current_app._get_current_object()
        from app import socketio
        from app.scheduler.tasks import DataUpdateTask
        
        task = DataUpdateTask(app, socketio)
        result = task.update_stock_list()
        
        logger.info(f"股票列表更新任务执行结果: {result}")
        
    except Exception as e:
        logger.error(f"股票列表更新任务执行失败: {e}", exc_info=True)

def data_cleanup_job():
    """数据清理任务"""
    try:
        app = current_app._get_current_object()
        from app import socketio
        from app.scheduler.tasks import DataUpdateTask
        
        task = DataUpdateTask(app, socketio)
        result = task.cleanup_old_data()
        
        logger.info(f"数据清理任务执行结果: {result}")
        
    except Exception as e:
        logger.error(f"数据清理任务执行失败: {e}", exc_info=True)

def realtime_data_push_job():
    """
    实时行情推送任务
    定期获取热门股票的实时数据并通过WebSocket推送
    """
    logger = logging.getLogger(__name__)
    
    try:
        # 动态导入避免循环依赖
        from app import socketio
        from app.websocket.events import broadcast_realtime_data
        from app.models.stock import Stock
        
        if not socketio:
            logger.warning("SocketIO not available in 'realtime_data_push_job'.")
            return
        
        # 获取活跃的股票列表（这里可以根据业务需求调整）
        # 例如：获取成交量最大的前20只股票，或者用户自选股等
        popular_stocks = Stock.query.filter(
            Stock.is_active == True,
            Stock.code.like('sz.%')  # 先只推送深市股票作为示例
        ).limit(10).all()
        
        stock_codes = [stock.code for stock in popular_stocks]
        
        if stock_codes:
            logger.info(f"开始推送 {len(stock_codes)} 只股票的实时数据")
            broadcast_realtime_data(socketio, stock_codes)
        else:
            logger.info("没有找到需要推送的股票")
            
    except Exception as e:
        logger.error(f"实时行情推送任务失败: {e}")

def top_strategy_backtest_job():
    """
    Top策略回测任务
    对潜力股进行多策略回测，计算各策略胜率最高的前N只股票并保存到数据库
    """
    try:
        app = current_app._get_current_object()
        
        # 动态导入避免循环依赖
        from app.jobs.top_strategy_backtest_job import update_top_strategy_stocks
        
        logger.info("开始执行Top策略回测任务")
        
        # 执行回测任务，使用默认参数
        update_top_strategy_stocks()
        
        logger.info("Top策略回测任务执行完成")
        
    except Exception as e:
        logger.error(f"Top策略回测任务执行失败: {e}", exc_info=True) 