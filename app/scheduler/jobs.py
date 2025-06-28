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
        # Get the current Flask app and its bound scheduler instance
        app = current_app._get_current_object()
        if not hasattr(app, 'scheduler'):
            logger.error("Flask app does not have scheduler attribute in 'emit_scheduler_status_job'.")
            return
            
        scheduler = app.scheduler
        
        # Dynamically import socketio to avoid circular dependencies
        from app import socketio
        
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