from app import db
from datetime import datetime

class DailyData(db.Model):
    """股票日线数据表"""
    __tablename__ = 'daily_data'
    
    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False, index=True)
    trade_date = db.Column(db.Date, nullable=False, index=True, comment='交易日期')
    
    # OHLCV数据
    open_price = db.Column(db.DECIMAL(20, 4), comment='开盘价')
    high_price = db.Column(db.DECIMAL(20, 4), comment='最高价')
    low_price = db.Column(db.DECIMAL(20, 4), comment='最低价')
    close_price = db.Column(db.DECIMAL(20, 4), comment='收盘价')
    volume = db.Column(db.BigInteger, comment='成交量')
    amount = db.Column(db.DECIMAL(30, 4), comment='成交额')
    
    # 复权价格
    adj_close = db.Column(db.DECIMAL(20, 4), comment='后复权收盘价')
    
    # 技术指标
    ma5 = db.Column(db.Numeric(10, 3), comment='5日均线')
    ma10 = db.Column(db.Numeric(10, 3), comment='10日均线')
    ma20 = db.Column(db.Numeric(10, 3), comment='20日均线')
    ma60 = db.Column(db.Numeric(10, 3), comment='60日均线')
    
    # MACD指标
    macd_dif = db.Column(db.Numeric(10, 6), comment='MACD DIF')
    macd_dea = db.Column(db.Numeric(10, 6), comment='MACD DEA')
    macd_macd = db.Column(db.Numeric(10, 6), comment='MACD MACD')
    
    # RSI指标
    rsi_6 = db.Column(db.Numeric(5, 2), comment='6日RSI')
    rsi_12 = db.Column(db.Numeric(5, 2), comment='12日RSI')
    rsi_24 = db.Column(db.Numeric(5, 2), comment='24日RSI')
    
    # 其他指标
    turnover_rate = db.Column(db.DECIMAL(20, 8), comment='换手率')
    pe_ratio = db.Column(db.Numeric(8, 2), comment='市盈率')
    pb_ratio = db.Column(db.Numeric(8, 2), comment='市净率')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 联合唯一索引
    __table_args__ = (
        db.UniqueConstraint('stock_id', 'trade_date', name='uq_stock_date'),
        db.Index('idx_trade_date', 'trade_date'),
    )
    
    def __repr__(self):
        return f'<DailyData {self.stock.code if self.stock else "Unknown"} {self.trade_date}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'stock_id': self.stock_id,
            'trade_date': self.trade_date.isoformat(),
            'open_price': float(self.open_price) if self.open_price else None,
            'high_price': float(self.high_price) if self.high_price else None,
            'low_price': float(self.low_price) if self.low_price else None,
            'close_price': float(self.close_price) if self.close_price else None,
            'volume': self.volume,
            'amount': float(self.amount) if self.amount else None,
            'adj_close': float(self.adj_close) if self.adj_close else None,
            'ma5': float(self.ma5) if self.ma5 else None,
            'ma10': float(self.ma10) if self.ma10 else None,
            'ma20': float(self.ma20) if self.ma20 else None,
            'ma60': float(self.ma60) if self.ma60 else None,
            'macd_dif': float(self.macd_dif) if self.macd_dif else None,
            'macd_dea': float(self.macd_dea) if self.macd_dea else None,
            'macd_macd': float(self.macd_macd) if self.macd_macd else None,
            'rsi_6': float(self.rsi_6) if self.rsi_6 else None,
            'rsi_12': float(self.rsi_12) if self.rsi_12 else None,
            'rsi_24': float(self.rsi_24) if self.rsi_24 else None,
            'turnover_rate': float(self.turnover_rate) if self.turnover_rate else None,
            'pe_ratio': float(self.pe_ratio) if self.pe_ratio else None,
            'pb_ratio': float(self.pb_ratio) if self.pb_ratio else None,
            'created_at': self.created_at.isoformat()
        } 