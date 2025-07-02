import logging
from threading import Thread
from flask import current_app
from flask_restx import Namespace, Resource
from app.jobs.candidate_pool_job import update_candidate_pool
from app.jobs.top_strategy_backtest_job import update_top_strategy_stocks

logger = logging.getLogger(__name__)
ns = Namespace('jobs', description='手动任务触发接口')

# 支持的手动任务列表
SUPPORTED_JOBS = {
    'candidate_pool': update_candidate_pool,
    'top_strategy_backtest': update_top_strategy_stocks
}

def run_job_in_background(job_func):
    """在一个单独的线程中运行任务，以避免阻塞API请求"""
    app = current_app._get_current_object()
    def wrapper():
        with app.app_context():
            job_func()
    
    thread = Thread(target=wrapper)
    thread.daemon = True
    thread.start()


@ns.route('/run/<string:job_name>')
class RunJob(Resource):
    @ns.doc('手动触发一个后台任务')
    @ns.response(202, '任务已成功启动')
    @ns.response(404, '不支持的任务')
    @ns.response(500, '任务启动失败')
    def post(self, job_name):
        """
        根据名称手动触发一个后台任务。
        目前支持的任务: 'candidate_pool', 'top_strategy_backtest'
        """
        if job_name not in SUPPORTED_JOBS:
            return {'success': False, 'message': f'不支持的任务: {job_name}'}, 404
        
        try:
            logger.info(f"手动触发任务: {job_name}")
            job_func = SUPPORTED_JOBS[job_name]
            
            # 在后台线程中运行，立即返回响应
            run_job_in_background(job_func)
            
            return {'success': True, 'message': f'任务 {job_name} 已在后台启动'}, 202
        except Exception as e:
            logger.error(f"启动任务 {job_name} 时出错: {e}", exc_info=True)
            return {'success': False, 'message': f'启动任务失败: {str(e)}'}, 500 