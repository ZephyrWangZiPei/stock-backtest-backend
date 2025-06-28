import pandas as pd
import json
from datetime import datetime
import logging

from app import db
from app.models import Stock, DailyData, Strategy, BacktestResult, BacktestTrade
from app.strategies import STRATEGY_MAP
from .performance_analyzer import calculate_performance_metrics, calculate_trade_statistics

logger = logging.getLogger(__name__)

class BacktestEngine:
    """
    回测引擎，负责执行策略、模拟交易并记录结果。
    """
    def __init__(self, strategy_id: int, start_date: str, end_date: str, initial_capital: float, stock_codes: list, custom_parameters: dict = None):
        """
        初始化回测引擎。
        :param strategy_id: 策略ID
        :param start_date: 回测开始日期 'YYYY-MM-DD'
        :param end_date: 回测结束日期 'YYYY-MM-DD'
        :param initial_capital: 初始资金
        :param stock_codes: 股票代码列表，例如 ['sh.600036', 'sz.000001']
        :param custom_parameters: 用户自定义的策略参数
        """
        self.strategy_model = Strategy.query.get_or_404(strategy_id)
        self.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        self.end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        self.initial_capital = float(initial_capital)
        self.stock_codes = stock_codes
        
        # 优先使用传入的自定义参数，否则使用数据库中存储的默认参数
        if custom_parameters is not None:
            self.strategy_params = custom_parameters
            self.parameters_to_save = json.dumps(custom_parameters)
        else:
            self.strategy_params = json.loads(self.strategy_model.parameters)
            self.parameters_to_save = self.strategy_model.parameters
        
        # 从STRATEGY_MAP中获取策略实现类
        strategy_class = STRATEGY_MAP.get(self.strategy_model.identifier)
        if not strategy_class:
            raise ValueError(f"策略 '{self.strategy_model.identifier}' 未在 STRATEGY_MAP 中找到。")
        self.strategy = strategy_class(self.strategy_params)
        logger.info(f"回测引擎初始化完成，使用策略: {self.strategy_model.name}")

    def run(self):
        """
        执行回测。
        """
        logger.info("开始执行回测...")
        
        # 1. 为所有选定股票一次性获取全部历史数据
        all_stocks_data = self._fetch_data()
        if all_stocks_data.empty:
            logger.warning("在指定日期范围内未找到任何股票数据。")
            return None

        # 2. 为每支股票生成交易信号
        all_signals = self._generate_all_signals(all_stocks_data)

        # 3. 模拟交易过程
        portfolio_history_df, trades = self._simulate_trading(all_stocks_data, all_signals)

        # 4. 计算最终结果
        final_value = portfolio_history_df['total'].iloc[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital

        # 计算详细性能指标
        performance_metrics = calculate_performance_metrics(portfolio_history_df.copy())
        
        # 计算交易统计数据
        trade_statistics = calculate_trade_statistics(trades, self.stock_codes)

        # 合并所有指标
        all_metrics = {**performance_metrics, **trade_statistics}

        logger.info(f"回测完成。最终资产: {final_value:.2f}, 总回报率: {total_return:.2%}, 年化回报率: {all_metrics['annualized_return']:.2%}, 夏普比率: {all_metrics['sharpe_ratio']:.2f}, 最大回撤: {all_metrics['max_drawdown']:.2%}, 胜率: {all_metrics['win_rate']:.2%}")

        # 5. 将结果存入数据库
        result_id = self._save_results(portfolio_history_df, trades, final_value, total_return, all_metrics)
        logger.info(f"回测结果已保存，ID: {result_id}")
        
        return result_id

    def _fetch_data(self) -> pd.DataFrame:
        """为所有选定股票在指定日期范围内获取历史数据。"""
        logger.info(f"正在为 {len(self.stock_codes)} 支股票获取从 {self.start_date} 到 {self.end_date} 的数据...")
        
        stock_map = {s.code: s.id for s in Stock.query.filter(Stock.code.in_(self.stock_codes)).all()}
        stock_ids = list(stock_map.values())

        if not stock_ids:
            return pd.DataFrame()

        query = DailyData.query.filter(
            DailyData.stock_id.in_(stock_ids),
            DailyData.trade_date >= self.start_date,
            DailyData.trade_date <= self.end_date
        ).order_by(DailyData.stock_id, DailyData.trade_date)
        
        df = pd.read_sql(query.statement, db.engine)
        
        # 将stock_id映射回stock_code以便于处理
        reverse_stock_map = {id: code for code, id in stock_map.items()}
        df['stock_code'] = df['stock_id'].map(reverse_stock_map)

        logger.info(f"数据获取完成，共 {len(df)} 条记录。")
        return df

    def _generate_all_signals(self, all_stocks_data: pd.DataFrame) -> dict:
        """为回测范围内的每支股票生成一次信号。"""
        logger.info("正在生成交易信号...")
        signals = {}
        for stock_code, group in all_stocks_data.groupby('stock_code'):
            logger.debug(f"为 {stock_code} 生成信号...")
            signals[stock_code] = self.strategy.generate_signals(group)
        logger.info("所有交易信号生成完毕。")
        return signals

    def _simulate_trading(self, all_stocks_data: pd.DataFrame, all_signals: dict) -> (pd.DataFrame, list):
        """核心交易模拟逻辑。"""
        logger.info("开始模拟交易...")
        
        cash = self.initial_capital
        positions = {code: 0 for code in self.stock_codes} # 持股数量 {stock_code: quantity}
        portfolio_history = []
        trades = []

        # 按照交易日历进行每日迭代
        for trade_date in sorted(all_stocks_data['trade_date'].unique()):
            
            # 在每日开始时，先处理卖出信号
            for stock_code in self.stock_codes:
                if positions[stock_code] > 0: # 只有持仓的才需要考虑卖
                    stock_signals = all_signals.get(stock_code)
                    if stock_signals is None: continue
                    
                    day_signal_row = stock_signals[stock_signals['trade_date'] == trade_date]
                    if day_signal_row.empty: continue

                    signal = day_signal_row.iloc[0]['signal']
                    if signal == 'sell':
                        current_price = day_signal_row.iloc[0]['close_price']
                        
                        quantity_to_sell = positions[stock_code]
                        trade_amount = current_price * quantity_to_sell
                        cash += trade_amount
                        positions[stock_code] = 0
                        
                        trades.append({
                            'stock_code': stock_code, 'date': trade_date, 'trade_type': 'sell',
                            'price': current_price, 'quantity': quantity_to_sell, 'amount': trade_amount, 'cash_after': cash
                        })
                        logger.debug(f"[{trade_date}] 卖出 {stock_code}: {quantity_to_sell} 股 @ {current_price}, 现金: {cash:.2f}")

            # 处理完卖出后，用剩余现金处理买入信号
            # 简单平均分配资金给每个买入机会
            buy_signals_today = []
            for stock_code in self.stock_codes:
                 if positions[stock_code] == 0: # 只有空仓的才考虑买
                    stock_signals = all_signals.get(stock_code)
                    if stock_signals is None: continue
                    
                    day_signal_row = stock_signals[stock_signals['trade_date'] == trade_date]
                    if day_signal_row.empty: continue

                    signal = day_signal_row.iloc[0]['signal']
                    if signal == 'buy':
                        buy_signals_today.append({'code': stock_code, 'row': day_signal_row.iloc[0]})
            
            if buy_signals_today and cash > 1: # 留1块钱防止全买完
                capital_per_buy = cash / len(buy_signals_today)
                for buy_op in buy_signals_today:
                    stock_code = buy_op['code']
                    current_price = buy_op['row']['close_price']
                    
                    quantity = int(capital_per_buy // current_price)
                    if quantity > 0:
                        positions[stock_code] = quantity
                        trade_amount = current_price * quantity
                        cash -= trade_amount
                        trades.append({
                            'stock_code': stock_code, 'date': trade_date, 'trade_type': 'buy',
                            'price': current_price, 'quantity': quantity, 'amount': trade_amount, 'cash_after': cash
                        })
                        logger.debug(f"[{trade_date}] 买入 {stock_code}: {quantity} 股 @ {current_price}, 现金: {cash:.2f}")

            # 计算当日结束时的总资产
            current_portfolio_value = cash
            for stock_code in self.stock_codes:
                if positions[stock_code] > 0:
                    # 获取当日股价
                    today_price = all_stocks_data[
                        (all_stocks_data['trade_date'] == trade_date) & 
                        (all_stocks_data['stock_code'] == stock_code)
                    ]['close_price'].iloc[0]
                    current_portfolio_value += positions[stock_code] * today_price
            
            portfolio_history.append({'date': trade_date, 'total': current_portfolio_value})

        logger.info("交易模拟结束。")
        return pd.DataFrame(portfolio_history), trades

    def _save_results(self, portfolio_history: pd.DataFrame, trades: list, final_value, total_return, metrics: dict) -> int:
        """将回测结果保存到数据库。"""
        
        # 主结果记录
        result = BacktestResult(
            strategy_id=self.strategy_model.id,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            final_capital=final_value,
            total_return=total_return,
            annual_return=metrics.get('annualized_return'),
            sharpe_ratio=metrics.get('sharpe_ratio'),
            max_drawdown=metrics.get('max_drawdown'),
            total_trades=metrics.get('total_trades'),
            winning_trades=metrics.get('winning_trades'),
            losing_trades=metrics.get('losing_trades'),
            win_rate=metrics.get('win_rate'),
            # profit_factor 暂时不存，因为可能是无穷大
            parameters_used=self.parameters_to_save,
            portfolio_history=portfolio_history.to_json(orient='records', date_format='iso'),
            status='completed',
            completed_at=datetime.utcnow()
        )
        db.session.add(result)
        db.session.flush()

        # 详细交易记录
        for trade_data in trades:
            trade = BacktestTrade(
                backtest_result_id=result.id,
                stock_code=trade_data['stock_code'],
                trade_date=trade_data['date'],
                trade_type=trade_data['trade_type'],
                price=trade_data['price'],
                quantity=trade_data['quantity'],
                amount=trade_data['amount'],
                cash_after=trade_data['cash_after']
            )
            db.session.add(trade)
            
        db.session.commit()
        return result.id 