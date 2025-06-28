from app import db
from datetime import datetime

class RealtimeData(db.Model):
    """实时数据表"""
    __tablename__ = 'realtime_data'
    
    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(10), nullable=False, index=True, comment='股票代码')
    
    # 实时价格数据
    current_price = db.Column(db.Numeric(10, 3), comment='当前价格')
    open_price = db.Column(db.Numeric(10, 3), comment='开盘价')
    high_price = db.Column(db.Numeric(10, 3), comment='最高价')
    low_price = db.Column(db.Numeric(10, 3), comment='最低价')
    pre_close = db.Column(db.Numeric(10, 3), comment='昨收价')
    
    # 涨跌信息
    change_amount = db.Column(db.Numeric(10, 3), comment='涨跌额')
    change_rate = db.Column(db.Numeric(5, 2), comment='涨跌幅(%)')
    
    # 成交信息
    volume = db.Column(db.BigInteger, comment='成交量')
    amount = db.Column(db.Numeric(15, 2), comment='成交额')
    turnover_rate = db.Column(db.Numeric(5, 2), comment='换手率')
    
    # 买卖盘信息
    bid1_price = db.Column(db.Numeric(10, 3), comment='买一价')
    bid1_volume = db.Column(db.Integer, comment='买一量')
    ask1_price = db.Column(db.Numeric(10, 3), comment='卖一价')
    ask1_volume = db.Column(db.Integer, comment='卖一量')
    
    # 市值信息
    market_cap = db.Column(db.Numeric(15, 2), comment='总市值')
    circulating_cap = db.Column(db.Numeric(15, 2), comment='流通市值')
    
    # 估值指标
    pe_ratio = db.Column(db.Numeric(8, 2), comment='市盈率')
    pb_ratio = db.Column(db.Numeric(8, 2), comment='市净率')
    
    # 时间戳
    quote_time = db.Column(db.DateTime, comment='行情时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<RealtimeData {self.stock_code}: {self.current_price}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'current_price': float(self.current_price) if self.current_price else None,
            'open_price': float(self.open_price) if self.open_price else None,
            'high_price': float(self.high_price) if self.high_price else None,
            'low_price': float(self.low_price) if self.low_price else None,
            'pre_close': float(self.pre_close) if self.pre_close else None,
            'change_amount': float(self.change_amount) if self.change_amount else None,
            'change_rate': float(self.change_rate) if self.change_rate else None,
            'volume': self.volume,
            'amount': float(self.amount) if self.amount else None,
            'turnover_rate': float(self.turnover_rate) if self.turnover_rate else None,
            'bid1_price': float(self.bid1_price) if self.bid1_price else None,
            'bid1_volume': self.bid1_volume,
            'ask1_price': float(self.ask1_price) if self.ask1_price else None,
            'ask1_volume': self.ask1_volume,
            'market_cap': float(self.market_cap) if self.market_cap else None,
            'circulating_cap': float(self.circulating_cap) if self.circulating_cap else None,
            'pe_ratio': float(self.pe_ratio) if self.pe_ratio else None,
            'pb_ratio': float(self.pb_ratio) if self.pb_ratio else None,
            'quote_time': self.quote_time.isoformat() if self.quote_time else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        } 