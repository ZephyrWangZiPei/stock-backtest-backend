from app import db
from datetime import datetime

class UpdateLog(db.Model):
    """更新日志表，记录各种更新任务的最后执行时间"""
    __tablename__ = 'update_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(50), unique=True, nullable=False, comment='任务名称')
    last_update = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, comment='最后更新时间')
    status = db.Column(db.String(20), nullable=False, default='success', comment='最后更新状态')
    message = db.Column(db.String(500), comment='最后更新消息')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def update_task_status(task_name: str, status: str = 'success', message: str = None):
        """更新任务状态"""
        log = UpdateLog.query.filter_by(task_name=task_name).first()
        if not log:
            log = UpdateLog(task_name=task_name)
            db.session.add(log)
        
        log.last_update = datetime.utcnow()
        log.status = status
        log.message = message
        db.session.commit()

    def to_dict(self):
        return {
            'task_name': self.task_name,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'status': self.status,
            'message': self.message
        } 