from app import db
from datetime import datetime

class UserWatchlist(db.Model):
    """用户自选股表"""
    __tablename__ = 'user_watchlist'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False, comment='用户ID')  # 暂时用字符串，后续可扩展用户系统
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    
    # 自选股配置
    alert_price_high = db.Column(db.Numeric(10, 3), comment='价格上限提醒')
    alert_price_low = db.Column(db.Numeric(10, 3), comment='价格下限提醒')
    alert_change_rate = db.Column(db.Numeric(5, 2), comment='涨跌幅提醒')
    
    # 备注信息
    notes = db.Column(db.Text, comment='备注')
    tags = db.Column(db.String(200), comment='标签，逗号分隔')
    
    # 排序权重
    sort_order = db.Column(db.Integer, default=0, comment='排序权重')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 联合唯一索引
    __table_args__ = (
        db.UniqueConstraint('user_id', 'stock_id', name='uq_user_stock'),
        db.Index('idx_user_id', 'user_id'),
    )
    
    def __repr__(self):
        return f'<UserWatchlist {self.user_id}: {self.stock.code if self.stock else "Unknown"}>'
    
    def get_tags_list(self):
        """获取标签列表"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []
    
    def set_tags_list(self, tags_list):
        """设置标签列表"""
        self.tags = ','.join(tags_list) if tags_list else None
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'stock_id': self.stock_id,
            'stock': self.stock.to_dict() if self.stock else None,
            'alert_price_high': float(self.alert_price_high) if self.alert_price_high else None,
            'alert_price_low': float(self.alert_price_low) if self.alert_price_low else None,
            'alert_change_rate': float(self.alert_change_rate) if self.alert_change_rate else None,
            'notes': self.notes,
            'tags': self.get_tags_list(),
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        } 