from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import logging
from flask_socketio import emit

from app.scheduler import TaskScheduler, DataUpdateTask
from app.models.update_log import UpdateLog

logger = logging.getLogger(__name__)

# HTTP蓝图仍然保留，用于处理非实时任务，如任务的增删改
scheduler_bp = Blueprint('scheduler', __name__, url_prefix='/api/scheduler')

def init_scheduler_api(app, scheduler: TaskScheduler):
    """
    初始化调度器API和WebSocket事件处理器。
    HTTP接口用于一次性操作（增删改），WebSocket用于状态同步和触发任务。
    """
    socketio = scheduler.socketio

    # --- WebSocket 事件处理器 ---
    
    @socketio.on('connect', namespace='/scheduler')
    def handle_connect():
        """处理WebSocket连接"""
        sid = request.sid
        logger.info(f"客户端 {sid} 已连接")
        
        # 发送调度器状态
        scheduler._emit_scheduler_status()
        
        # 发送更新日志
        try:
            with app.app_context():
                logs = UpdateLog.query.all()
                # 使用emit而不是socketio.emit，因为我们想发送给当前连接的客户端
                emit('update_logs', {
                    'logs': [log.to_dict() for log in logs]
                })
                logger.info(f"已向客户端 {sid} 发送更新日志")
        except Exception as e:
            logger.error(f"发送更新日志失败: {str(e)}", exc_info=True)

    @socketio.on('request_status_update', namespace='/scheduler')
    def handle_request_status_update():
        """响应前端的主动状态更新请求"""
        scheduler._emit_scheduler_status()
        # 同时发送更新日志
        emit_update_logs()

    def emit_update_logs():
        """发送更新日志给客户端"""
        try:
            with app.app_context():
                logs = UpdateLog.query.all()
                socketio.emit('update_logs', {
                    'logs': [log.to_dict() for log in logs]
                }, namespace='/scheduler')
        except Exception as e:
            logger.error(f"发送更新日志失败: {str(e)}", exc_info=True)

    @socketio.on('manual_update_daily_data', namespace='/scheduler')
    def ws_manual_update_daily_data(data):
        """(WS) 手动触发每日数据更新"""
        sid = request.sid
        try:
            date = data.get('date') if data else None
            flask_app = current_app._get_current_object()
            task = DataUpdateTask(flask_app, socketio)
            socketio.start_background_task(task.update_daily_data, date=date, sid=sid)
            logger.info(f"已通过WebSocket为客户端 {sid} 启动数据更新任务 (日期: {date or '今天'})")
        except Exception as e:
            logger.error(f"WebSocket - 手动更新每日数据失败: {e}", exc_info=True)
            socketio.emit('update_error', {'task': 'update_daily_data', 'message': str(e)}, room=sid)
            UpdateLog.update_task_status('update_daily_data', 'error', str(e))

    @socketio.on('manual_update_stock_list', namespace='/scheduler')
    def ws_manual_update_stock_list(data):
        """(WS) 手动触发股票列表更新"""
        sid = request.sid
        try:
            flask_app = current_app._get_current_object()
            task = DataUpdateTask(flask_app, socketio)
            socketio.start_background_task(task.update_stock_list, sid=sid)
            logger.info(f"已通过WebSocket为客户端 {sid} 启动股票列表更新任务")
        except Exception as e:
            logger.error(f"WebSocket - 手动更新股票列表失败: {e}", exc_info=True)
            socketio.emit('update_error', {'task': 'update_stock_list', 'message': str(e)}, room=sid)
            UpdateLog.update_task_status('update_stock_list', 'error', str(e))
            emit_update_logs()

    @socketio.on('setup_jobs', namespace='/scheduler')
    def ws_setup_scheduled_jobs(data):
        """(WS) 重置所有定时任务"""
        sid = request.sid
        try:
            # 清除所有现有任务
            scheduler.scheduler.remove_all_jobs()
            logger.info("所有旧的定时任务已通过 remove_all_jobs() 成功清除。")

            # 添加所有预定义的任务
            scheduler.add_daily_data_update_job()
            scheduler.add_weekend_data_cleanup_job()
            scheduler.add_stock_list_update_job()
            scheduler.add_status_emitter_job()
            
            logger.info("已重新设置所有预定义的定时任务。")
            
            # 发送更新后的调度器状态
            scheduler._emit_scheduler_status()
            
            # 发送完成事件给客户端
            socketio.emit('update_complete', {
                'task': 'setup_jobs',
                'progress': 100,
                'message': '定时任务已成功重置',
                'success': True,
                'data': {'success': True, 'message': '定时任务已成功重置'}
            }, room=sid, namespace='/scheduler')
            
            logger.info(f"已向客户端 {sid} 发送任务完成事件")

        except Exception as e:
            error_msg = f"设置定时任务失败: {str(e)}"
            logger.error(f"WebSocket - {error_msg}", exc_info=True)
            
            # 发送错误事件给客户端
            socketio.emit('update_error', {
                'task': 'setup_jobs', 
                'message': error_msg
            }, room=sid, namespace='/scheduler')
            
            # 同时发送完成事件（失败状态）
            socketio.emit('update_complete', {
                'task': 'setup_jobs',
                'progress': 100,
                'message': error_msg,
                'success': False,
                'data': None
            }, room=sid, namespace='/scheduler')

    # --- HTTP API 接口 (保留用于管理任务定义) ---

    @scheduler_bp.route('/jobs/<job_id>', methods=['DELETE'])
    def remove_job(job_id):
        """删除指定任务"""
        try:
            scheduler.remove_job(job_id)
            return jsonify({
                'success': True,
                'message': f'任务 {job_id} 已删除'
            })
            
        except Exception as e:
            logger.error(f"删除任务失败: {str(e)}")
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500
    
    @scheduler_bp.route('/jobs/<job_id>', methods=['PUT'])
    def reschedule_job(job_id):
        """修改定时任务的执行时间"""
        try:
            data = request.get_json()
            if not data or 'trigger' not in data:
                return jsonify({'success': False, 'message': '缺少 trigger 参数'}), 400
            
            trigger_args = data['trigger']
            if not isinstance(trigger_args, dict):
                return jsonify({'success': False, 'message': 'trigger 参数必须是JSON对象'}), 400
            
            scheduler.reschedule_job(job_id, trigger_args)
            
            # 状态会通过WebSocket自动更新，这里只需返回成功信息
            return jsonify({
                'success': True,
                'message': f'任务 {job_id} 已成功更新'
            })
            
        except Exception as e:
            logger.error(f"更新任务失败: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500
    
    # 不再需要/jobs和/status接口，因为状态通过WebSocket推送
    # @scheduler_bp.route('/jobs', methods=['GET'])
    # @scheduler_bp.route('/status', methods=['GET'])

    # 注册蓝图
    app.register_blueprint(scheduler_bp)
    
    return scheduler_bp 