import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from datetime import datetime, timedelta
import pytz
from flask_socketio import emit
from app.backtester import BacktestEngine
from app import create_app
import json
from .jobs import (
    emit_scheduler_status_job, 
    daily_data_update_job, 
    stock_list_update_job, 
    data_cleanup_job,
    realtime_data_push_job
)

# Import of emit_scheduler_status_job is removed from here

logger = logging.getLogger(__name__)

class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, app=None):
        self.app = app
        self.scheduler = None
        self.socketio = None
        self._initialized = False
        
    def init_app(self, app):
        """初始化调度器"""
        self.app = app
        
        # 配置调度器
        jobstores = {
            'default': SQLAlchemyJobStore(url=app.config.get('SQLALCHEMY_DATABASE_URI'))
        }
        
        executors = {
            'default': ThreadPoolExecutor(20)
        }
        
        job_defaults = {
            'coalesce': False,
            'max_instances': 3
        }
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=pytz.timezone('Asia/Shanghai')
        )
        
        self.socketio = None
        self._initialized = True
        logger.info("调度器初始化完成")
        
    def init_socketio(self, socketio):
        """绑定SocketIO实例并注册事件处理器"""
        self.socketio = socketio
        
        @socketio.on('request_status_update', namespace='/scheduler')
        def handle_request_status_update():
            logger.info("收到来自客户端的状态更新请求。")
            self._emit_scheduler_status()

        @socketio.on('setup_jobs', namespace='/scheduler')
        def handle_setup_jobs():
            logger.info("收到来自客户端的重置任务请求。")
            self.setup_jobs()
            self._emit_scheduler_status()

        @socketio.on('run_job_manually', namespace='/scheduler')
        def handle_run_job_manually(data):
            job_id = data.get('job_id')
            if not job_id:
                logger.warning("手动运行任务请求缺少 'job_id'。")
                return

            logger.info(f"收到手动运行任务 '{job_id}' 的请求。")
            job = self.scheduler.get_job(job_id)
            if job:
                self.scheduler.modify_job(job_id, next_run_time=datetime.now(pytz.timezone('Asia/Shanghai')))
                logger.info(f"任务 '{job_id}' 已被调度立即执行。")
                self._emit_scheduler_status()
            else:
                # 如果任务不存在，尝试根据ID执行预定义的函数
                if job_id == 'candidate_pool':
                     from app.jobs.candidate_pool_job import update_candidate_pool
                     self.scheduler.add_job(
                         func=update_candidate_pool, 
                         id='candidate_pool_manual', 
                         name='手动执行潜力股海选', 
                         replace_existing=True, 
                         misfire_grace_time=3600
                     )
                     logger.info("已添加并立即执行手动海选任务。")
                else:
                    logger.error(f"无法找到或执行未知的任务ID: {job_id}")

        logger.info("SocketIO实例已绑定到调度器，并已注册事件处理器。")
        
    def start(self):
        """启动调度器"""
        if not self._initialized:
            raise RuntimeError("调度器未初始化")
            
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("调度器已启动")
            
            # 不再在启动时清理所有任务，保留数据库中持久化的任务。
            # 如果确实需要重置，可通过 /setup_jobs WebSocket 事件或命令行调用实现。
            
            # 确保核心任务存在（如果数据库里没有，就补充一次）
            self._ensure_core_jobs()
            
            # 启动后，立即添加状态推送任务（方法内部已检查是否重复）
            self.add_status_emitter_job()
            
    def shutdown(self):
        """关闭调度器"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("调度器已关闭")
            
    def add_job(self, func, trigger, id=None, **kwargs):
        """添加任务"""
        if not self.scheduler:
            raise RuntimeError("调度器未初始化")
            
        return self.scheduler.add_job(func, trigger, id=id, **kwargs)
        
    def remove_job(self, job_id):
        """移除任务"""
        if not self.scheduler:
            raise RuntimeError("调度器未初始化")
            
        self.scheduler.remove_job(job_id)
        self._emit_scheduler_status() # 立即推送状态
        
    def get_jobs(self):
        """获取所有任务"""
        if not self.scheduler:
            return []
            
        return self.scheduler.get_jobs()
        
    def _emit_scheduler_status(self):
        """收集调度器状态并通过WebSocket发送"""
        if not self.socketio or not self.scheduler:
            return
            
        try:
            with self.app.app_context():
                is_running = self.scheduler.running
                
                jobs_data = []
                jobs_in_store = self.get_jobs()
                
                for job in jobs_in_store:
                    live_job = self.scheduler.get_job(job.id)
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
                
                self.socketio.emit('scheduler_status', status_data, namespace='/scheduler')
        except Exception as e:
            logger.error(f"发送调度器状态失败: {e}", exc_info=True)
        
    def add_daily_data_update_job(self):
        """添加每日数据更新任务"""
        # 工作日18:00更新数据（股市收盘后）
        trigger = CronTrigger(
            day_of_week='mon-fri',  # 周一到周五
            hour=18,
            minute=0,
            timezone=pytz.timezone('Asia/Shanghai')
        )
        
        job = self.add_job(
            func=daily_data_update_job,
            trigger=trigger,
            id='daily_data_update',
            name='每日数据更新',
            replace_existing=True
        )
        
        logger.info("每日数据更新任务已添加")
        self._emit_scheduler_status() # 立即推送状态
        return job
        
    def add_weekend_data_cleanup_job(self):
        """添加周末数据清理任务"""
        # 每周日凌晨2点执行数据清理
        trigger = CronTrigger(
            day_of_week='sun',
            hour=2,
            minute=0,
            timezone=pytz.timezone('Asia/Shanghai')
        )
        
        job = self.add_job(
            func=data_cleanup_job,
            trigger=trigger,
            id='weekend_data_cleanup',
            name='周末数据清理',
            replace_existing=True
        )
        
        logger.info("周末数据清理任务已添加")
        self._emit_scheduler_status() # 立即推送状态
        return job
        
    def add_stock_list_update_job(self):
        """添加股票列表更新任务"""
        # 每月第一个工作日早上9点更新股票列表
        trigger = CronTrigger(
            day='1-7',
            day_of_week='mon-fri',
            hour=9,
            minute=0,
            timezone=pytz.timezone('Asia/Shanghai')
        )
        
        job = self.add_job(
            func=stock_list_update_job,
            trigger=trigger,
            id='monthly_stock_list_update',
            name='月度股票列表更新',
            replace_existing=True
        )
        
        logger.info("月度股票列表更新任务已添加")
        self._emit_scheduler_status() # 立即推送状态
        return job
        
    def add_status_emitter_job(self):
        """添加一个定时任务，用于定期通过WebSocket发送调度器状态。"""
        if self.scheduler.get_job('status_emitter'):
            logger.info("状态推送任务已存在。")
            return

        # 直接使用函数，不使用lambda
        job = self.add_job(
            func=emit_scheduler_status_job,  # 直接使用函数，支持无参数调用
            trigger='interval',
            seconds=3600,  # 每小时推送一次（3600秒）
            id='status_emitter',
            name='调度器状态实时推送',
            replace_existing=True
        )
        logger.info("调度器状态实时推送任务已添加，每小时执行一次。")
        return job

    def reschedule_job(self, job_id, trigger_args):
        """修改任务的调度规则"""
        if not self.scheduler:
            raise RuntimeError("调度器未初始化")
        
        # CronTrigger只接受字符串类型的参数
        trigger_args_str = {k: str(v) for k, v in trigger_args.items()}
        
        result = self.scheduler.reschedule_job(job_id, trigger=CronTrigger(**trigger_args_str, timezone=pytz.timezone('Asia/Shanghai')))
        self._emit_scheduler_status() # 立即推送状态
        return result 

    def _ensure_core_jobs(self):
        """检查并补充系统核心任务，防止首次启动时任务为空。"""
        core_jobs = [
            ("daily_data_update", self.add_daily_data_update_job),
            ("weekend_data_cleanup", self.add_weekend_data_cleanup_job),
            ("monthly_stock_list_update", self.add_stock_list_update_job),
            ("realtime_data_push", self.add_realtime_data_push_job),
        ]
        for job_id, add_func in core_jobs:
            if not self.scheduler.get_job(job_id):
                try:
                    add_func()
                    logger.info(f"核心任务 {job_id} 缺失，已自动补充")
                except Exception as e:
                    logger.error(f"自动补充核心任务 {job_id} 失败: {e}")
    
    def add_realtime_data_push_job(self):
        """添加实时行情推送任务"""
        # 交易时间内每5秒执行一次
        trigger = CronTrigger(
            second='*/5',  # 每5秒
            hour='9-15',   # 交易时间 9:00-15:00
            day_of_week='mon-fri',  # 工作日
            timezone=pytz.timezone('Asia/Shanghai')
        )
        
        job = self.add_job(
            func=realtime_data_push_job,
            trigger=trigger,
            id='realtime_data_push',
            name='实时行情推送',
            replace_existing=True,
            max_instances=1
        )
        
        logger.info("实时行情推送任务已添加")
        self._emit_scheduler_status() # 立即推送状态
        return job

    def setup_jobs(self):
        """设置所有定时任务"""
        
        # ... existing jobs ...
        
        # 实时行情推送任务 - 每5秒执行一次（交易时间内）
        self.scheduler.add_job(
            func=realtime_data_push_job,
            trigger='cron',
            second='*/5',  # 每5秒
            hour='9-15',   # 交易时间 9:00-15:00
            day_of_week='mon-fri',  # 工作日
            id='realtime_data_push',
            name='实时行情推送',
            replace_existing=True,
            max_instances=1
        )
        
        # ... existing code ...

def run_backtest_task(backtest_id: int):
    """
    在后台执行回测的函数。
    :param backtest_id: 回测结果的数据库ID。
    """
    logger.info(f"开始执行后台回测任务，ID: {backtest_id}")
    app = create_app()
    with app.app_context():
        from app.models import BacktestResult
        from app import db

        result = db.session.get(BacktestResult, backtest_id)
        if not result:
            logger.error(f"无法找到ID为 {backtest_id} 的回测任务记录。")
            return
        
        # 标记任务为正在运行
        result.status = 'running'
        db.session.commit()

        try:
            # 从 result 中获取参数来初始化引擎
            engine = BacktestEngine(
                strategy_id=result.strategy_id,
                start_date=result.start_date.strftime('%Y-%m-%d'),
                end_date=result.end_date.strftime('%Y-%m-%d'),
                initial_capital=float(result.initial_capital),
                stock_codes=result.get_selected_stocks(),
                custom_parameters=json.loads(result.parameters_used) if result.parameters_used else None,
                backtest_result_id=backtest_id # 传入ID
            )
            # engine.run() 现在将负责更新结果，而不是返回ID
            engine.run()
            logger.info(f"回测任务 {backtest_id} 成功完成。")

        except Exception as e:
            logger.error(f"回测任务 {backtest_id} 执行失败: {e}", exc_info=True)
            # 更新数据库中的状态为 'failed'
            result.status = 'failed'
            result.error_message = str(e)
            db.session.commit()