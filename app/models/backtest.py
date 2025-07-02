from app import db
from datetime import datetime
import json

class BacktestResult(db.Model):
    """回测结果表"""
    __tablename__ = 'backtest_results'
    
    id = db.Column(db.Integer, primary_key=True)
    strategy_id = db.Column(db.Integer, db.ForeignKey('strategies.id'), nullable=False)
    
    # 回测参数
    start_date = db.Column(db.Date, nullable=False, comment='回测开始日期')
    end_date = db.Column(db.Date, nullable=False, comment='回测结束日期')
    initial_capital = db.Column(db.Numeric(15, 2), nullable=False, comment='初始资金')
    
    # 回测结果
    final_capital = db.Column(db.Numeric(15, 2), comment='最终资金')
    total_return = db.Column(db.Numeric(10, 4), comment='总收益率')
    annual_return = db.Column(db.Numeric(10, 4), comment='年化收益率')
    max_drawdown = db.Column(db.Numeric(10, 4), comment='最大回撤')
    sharpe_ratio = db.Column(db.Numeric(10, 4), comment='夏普比率')
    profit_factor = db.Column(db.Numeric(10, 4), comment='盈亏比')
    expectancy = db.Column(db.Numeric(10, 4), comment='每笔期望收益率')
    
    # 交易统计
    total_trades = db.Column(db.Integer, comment='总交易次数')
    winning_trades = db.Column(db.Integer, comment='盈利交易次数')
    losing_trades = db.Column(db.Integer, comment='亏损交易次数')
    win_rate = db.Column(db.Numeric(5, 2), comment='胜率')
    
    # 其他指标
    volatility = db.Column(db.Numeric(10, 4), comment='波动率')
    beta = db.Column(db.Numeric(10, 4), comment='贝塔系数')
    
    # 回测状态
    status = db.Column(db.String(20), default='running', comment='回测状态: running/completed/failed')
    error_message = db.Column(db.Text, comment='错误信息')
    
    # 回测配置
    selected_stocks = db.Column(db.Text, comment='选中的股票列表JSON')
    parameters_used = db.Column(db.Text, comment='策略参数JSON')
    portfolio_history = db.Column(db.Text, comment='每日资产组合历史JSON')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, comment='完成时间')
    
    # 关联关系
    trades = db.relationship('BacktestTrade', backref='backtest_result', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<BacktestResult {self.id}: {self.strategy.name if self.strategy else "Unknown"}>'
    
    def get_selected_stocks(self):
        """获取选中的股票列表"""
        if self.selected_stocks:
            return json.loads(self.selected_stocks)
        return []
    
    def set_selected_stocks(self, stocks):
        """设置选中的股票列表"""
        self.selected_stocks = json.dumps(stocks, ensure_ascii=False)
    
    def to_dict(self, include_trades=False):
        data = {
            'id': self.id,
            'strategy_id': self.strategy_id,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'initial_capital': float(self.initial_capital),
            'final_capital': float(self.final_capital) if self.final_capital else None,
            'total_return': float(self.total_return) if self.total_return else None,
            'annual_return': float(self.annual_return) if self.annual_return else None,
            'max_drawdown': float(self.max_drawdown) if self.max_drawdown else None,
            'sharpe_ratio': float(self.sharpe_ratio) if self.sharpe_ratio else None,
            'profit_factor': float(self.profit_factor) if self.profit_factor else None,
            'expectancy': float(self.expectancy) if self.expectancy else None,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': float(self.win_rate) if self.win_rate else None,
            'volatility': float(self.volatility) if self.volatility else None,
            'beta': float(self.beta) if self.beta else None,
            'status': self.status,
            'error_message': self.error_message,
            'selected_stocks': self.get_selected_stocks(),
            'parameters_used': json.loads(self.parameters_used) if self.parameters_used else {},
            'portfolio_history': json.loads(self.portfolio_history) if self.portfolio_history else [],
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
        if include_trades:
            data['trades'] = [trade.to_dict() for trade in self.trades]
        return data

class BacktestTrade(db.Model):
    """回测交易记录表"""
    __tablename__ = 'backtest_trades'
    
    id = db.Column(db.Integer, primary_key=True)
    backtest_result_id = db.Column(db.Integer, db.ForeignKey('backtest_results.id'), nullable=False)
    stock_code = db.Column(db.String(10), nullable=False, comment='股票代码')
    
    # 交易信息
    trade_type = db.Column(db.String(10), nullable=False, comment='交易类型: buy/sell')
    trade_date = db.Column(db.Date, nullable=False, comment='交易日期')
    price = db.Column(db.Numeric(10, 3), nullable=False, comment='交易价格')
    quantity = db.Column(db.Integer, nullable=False, comment='交易数量')
    amount = db.Column(db.Numeric(15, 2), nullable=False, comment='交易金额')
    
    # 手续费
    commission = db.Column(db.Numeric(10, 2), default=0, comment='手续费')
    
    # 交易原因/信号
    signal = db.Column(db.String(100), comment='交易信号')
    reason = db.Column(db.Text, comment='交易原因')
    
    # 持仓信息
    position_before = db.Column(db.Integer, comment='交易前持仓')
    position_after = db.Column(db.Integer, comment='交易后持仓')
    cash_before = db.Column(db.Numeric(15, 2), comment='交易前现金')
    cash_after = db.Column(db.Numeric(15, 2), comment='交易后现金')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<BacktestTrade {self.stock_code} {self.trade_type} {self.trade_date}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'backtest_result_id': self.backtest_result_id,
            'stock_code': self.stock_code,
            'trade_type': self.trade_type,
            'trade_date': self.trade_date.isoformat(),
            'price': float(self.price),
            'quantity': self.quantity,
            'amount': float(self.amount),
            'commission': float(self.commission),
            'signal': self.signal,
            'reason': self.reason,
            'position_before': self.position_before,
            'position_after': self.position_after,
            'cash_before': float(self.cash_before) if self.cash_before else None,
            'cash_after': float(self.cash_after) if self.cash_after else None,
            'created_at': self.created_at.isoformat()
        } 