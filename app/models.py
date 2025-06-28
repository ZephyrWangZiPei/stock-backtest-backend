class BacktestResult(db.Model):
    # ... existing code ...
    strategy_id = db.Column(db.Integer, db.ForeignKey('strategy.id'), nullable=False)
    strategy = db.relationship('Strategy', backref=db.backref('backtest_results', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'initial_capital': self.initial_capital,
            'final_value': self.final_value,
            'profit_loss': self.profit_loss,
            'profit_rate': self.profit_rate,
            'created_at': self.created_at.isoformat()
        }

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