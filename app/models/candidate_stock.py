from app import db
from datetime import datetime

class CandidateStock(db.Model):
    """
    存储通过后台任务筛选出的候选股票池
    """
    __tablename__ = 'candidate_stock'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, unique=True, comment='股票代码')
    name = db.Column(db.String(50), nullable=False, comment='股票名称')
    reason = db.Column(db.String(255), nullable=True, comment='入选原因')
    added_at = db.Column(db.DateTime, default=datetime.utcnow, comment='添加时间')

    def __repr__(self):
        return f'<CandidateStock {self.code} ({self.name})>'

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'reason': self.reason,
            'added_at': self.added_at.isoformat() if self.added_at else None
        } 