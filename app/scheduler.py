from flask_apscheduler import APScheduler
from app import socketio
import logging
from app.jobs.candidate_pool_job import update_candidate_pool

logger = logging.getLogger(__name__)

scheduler = APScheduler()

def push_status_update():
    """推送系统状态更新到前端"""
    # ... existing code ...
    with scheduler.app.app_context():
        # ... existing code ...
        logger.debug("Pushing status update via WebSocket")
        socketio.emit('status_update', data)

def init_scheduler(app):
    """初始化调度器并添加任务"""
    scheduler.init_app(app)
    scheduler.start()
    logger.info("调度器已启动")

    # --- 实时数据推送任务 ---
    if scheduler.get_job('push_status') is None:
        scheduler.add_job(
            id='push_status',
            func=push_status_update,
            trigger='interval',
            seconds=5,
            name='实时状态推送'
        )
        logger.info("实时状态推送任务已添加。")
    else:
        logger.info("状态推送任务已存在。")

    # --- 每日候选池更新任务 ---
    if scheduler.get_job('update_candidate_pool') is None:
        scheduler.add_job(
            id='update_candidate_pool',
            func=update_candidate_pool,
            trigger='cron',
            hour=2, # 凌晨2点执行
            minute=0,
            name='每日更新候选股票池'
        )
        logger.info("每日候选股票池更新任务已添加。")
    else:
        logger.info("每日候选股票池更新任务已存在。") 