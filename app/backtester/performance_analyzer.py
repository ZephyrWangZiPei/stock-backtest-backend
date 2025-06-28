import pandas as pd
import numpy as np

def calculate_performance_metrics(portfolio_history: pd.DataFrame, risk_free_rate: float = 0.0):
    """
    计算投资组合的关键性能指标。

    :param portfolio_history: 一个DataFrame，包含 'date' 和 'total' (每日总资产) 列。
    :param risk_free_rate: 无风险利率，用于计算夏普比率。
    :return: 一个包含所有性能指标的字典。
    """
    if portfolio_history.empty or len(portfolio_history) < 2:
        return {
            'annualized_return': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0
        }

    # 确保 'date' 是 datetime 类型
    portfolio_history['date'] = pd.to_datetime(portfolio_history['date'])
    
    # 计算年化回报率
    annualized_return = calculate_annualized_return(portfolio_history)
    
    # 计算夏普比率
    sharpe_ratio = calculate_sharpe_ratio(portfolio_history, risk_free_rate)
    
    # 计算最大回撤
    max_drawdown = calculate_max_drawdown(portfolio_history)

    return {
        'annualized_return': annualized_return,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown
    }

def calculate_annualized_return(portfolio_history: pd.DataFrame) -> float:
    """计算年化回报率"""
    total_days = (portfolio_history['date'].iloc[-1] - portfolio_history['date'].iloc[0]).days
    if total_days == 0:
        return 0.0
    
    total_return = portfolio_history['total'].iloc[-1] / portfolio_history['total'].iloc[0] - 1
    annualized_return = (1 + total_return) ** (365.0 / total_days) - 1
    return annualized_return

def calculate_sharpe_ratio(portfolio_history: pd.DataFrame, risk_free_rate: float) -> float:
    """计算夏普比率"""
    daily_returns = portfolio_history['total'].pct_change().dropna()
    
    if daily_returns.empty or daily_returns.std() == 0:
        return 0.0
        
    excess_returns = daily_returns - (risk_free_rate / 365) # 假设无风险利率是年化的
    # 年化夏普比率
    sharpe_ratio = (excess_returns.mean() / excess_returns.std()) * np.sqrt(252) # 假设一年252个交易日
    return sharpe_ratio

def calculate_max_drawdown(portfolio_history: pd.DataFrame) -> float:
    """计算最大回撤"""
    portfolio_history['cumulative_max'] = portfolio_history['total'].cummax()
    portfolio_history['drawdown'] = portfolio_history['total'] / portfolio_history['cumulative_max'] - 1
    max_drawdown = portfolio_history['drawdown'].min()
    return abs(max_drawdown)

def calculate_trade_statistics(trades: list, stock_codes: list) -> dict:
    """
    计算交易相关的统计数据。

    :param trades: 一个包含所有交易记录的列表字典。
    :param stock_codes: 本次回测涉及的所有股票代码列表。
    :return: 一个包含交易统计指标的字典。
    """
    if not trades:
        return {
            'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
            'win_rate': 0.0, 'profit_factor': 0.0,
        }

    winning_trades = 0
    losing_trades = 0
    total_profit = 0.0
    total_loss = 0.0
    
    # 为每只股票维护一个买入队列
    buy_queues = {code: [] for code in stock_codes}

    for trade in trades:
        stock_code = trade['stock_code']
        if trade['trade_type'] == 'buy':
            buy_queues[stock_code].append(trade)
        elif trade['trade_type'] == 'sell':
            if buy_queues[stock_code]:
                buy_trade = buy_queues[stock_code].pop(0) # FIFO
                # 假设整笔买入被整笔卖出
                profit = (trade['price'] - buy_trade['price']) * buy_trade['quantity']
                if profit > 0:
                    winning_trades += 1
                    total_profit += profit
                else:
                    losing_trades += 1
                    total_loss += abs(profit)
            
    total_closed_trades = winning_trades + losing_trades
    win_rate = winning_trades / total_closed_trades if total_closed_trades > 0 else 0.0
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

    return {
        'total_trades': len(trades),
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
    } 