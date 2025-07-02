from app import db
from datetime import datetime

class TopStrategyStock(db.Model):
    """策略Top股票表 - 存储每个策略胜率最高的前N只股票"""
    __tablename__ = 'top_strategy_stocks'
    
    id = db.Column(db.Integer, primary_key=True)
    strategy_id = db.Column(db.Integer, db.ForeignKey('strategies.id'), nullable=False, index=True)
    stock_code = db.Column(db.String(10), nullable=False, comment='股票代码')
    stock_name = db.Column(db.String(100), comment='股票名称')
    
    # 回测结果指标
    win_rate = db.Column(db.Numeric(5, 2), nullable=False, comment='胜率')
    total_return = db.Column(db.Numeric(10, 4), comment='总收益率')
    annual_return = db.Column(db.Numeric(10, 4), comment='年化收益率')
    max_drawdown = db.Column(db.Numeric(10, 4), comment='最大回撤')
    sharpe_ratio = db.Column(db.Numeric(10, 4), comment='夏普比率')
    trade_count = db.Column(db.Integer, comment='交易次数')
    win_rate_lb = db.Column(db.Numeric(10, 4), comment='胜率置信下界(95%)')
    expectancy = db.Column(db.Numeric(10, 4), comment='每笔期望收益率')
    profit_factor = db.Column(db.Numeric(10, 4), comment='盈亏比')
    
    # 关联的BacktestResult ID
    backtest_result_id = db.Column(db.Integer, db.ForeignKey('backtest_results.id'), nullable=False)
    
    # 排名信息
    rank = db.Column(db.Integer, nullable=False, comment='在该策略中的排名')
    
    # 回测参数
    backtest_period_days = db.Column(db.Integer, comment='回测周期天数')
    initial_capital = db.Column(db.Numeric(15, 2), comment='初始资金')
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    
    # 关联关系
    strategy = db.relationship('Strategy', backref=db.backref('top_stocks', lazy='dynamic'))
    backtest_result = db.relationship('BacktestResult', backref=db.backref('top_strategy_stocks', lazy='dynamic'))
    
    # 复合索引：确保每个策略的排名唯一
    __table_args__ = (
        db.UniqueConstraint('strategy_id', 'rank', name='uk_strategy_rank'),
        db.Index('idx_strategy_rank', 'strategy_id', 'rank'),
    )
    
    def __repr__(self):
        return f'<TopStrategyStock {self.stock_code} Rank#{self.rank} WinRate:{self.win_rate}%>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy.name if self.strategy else None,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'win_rate': float(self.win_rate) if self.win_rate else None,
            'total_return': float(self.total_return) if self.total_return else None,
            'annual_return': float(self.annual_return) if self.annual_return else None,
            'max_drawdown': float(self.max_drawdown) if self.max_drawdown else None,
            'sharpe_ratio': float(self.sharpe_ratio) if self.sharpe_ratio else None,
            'trade_count': self.trade_count,
            'win_rate_lb': float(self.win_rate_lb) if self.win_rate_lb else None,
            'expectancy': float(self.expectancy) if self.expectancy else None,
            'profit_factor': float(self.profit_factor) if self.profit_factor else None,
            'rank': self.rank,
            'backtest_result_id': self.backtest_result_id,
            'backtest_period_days': self.backtest_period_days,
            'initial_capital': float(self.initial_capital) if self.initial_capital else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        } 