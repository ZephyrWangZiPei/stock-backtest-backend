from app import db
from datetime import datetime

class Stock(db.Model):
    """股票基础信息表"""
    __tablename__ = 'stocks'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False, index=True, comment='股票代码')
    name = db.Column(db.String(50), nullable=False, comment='股票名称')
    market = db.Column(db.String(10), nullable=False, comment='市场(SH/SZ)')
    industry = db.Column(db.String(50), comment='所属行业')
    sector = db.Column(db.String(50), comment='所属板块')
    list_date = db.Column(db.Date, comment='上市日期')
    is_active = db.Column(db.Boolean, default=True, comment='是否活跃')
    stock_type = db.Column(db.String(10), default='stock', comment='类型: stock/etf')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    daily_data = db.relationship('DailyData', backref='stock', lazy='dynamic')
    watchlists = db.relationship('UserWatchlist', backref='stock', lazy='dynamic')
    
    def __repr__(self):
        return f'<Stock {self.code}: {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'market': self.market,
            'industry': self.industry,
            'sector': self.sector,
            'list_date': self.list_date.isoformat() if self.list_date else None,
            'is_active': self.is_active,
            'stock_type': self.stock_type,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        } 