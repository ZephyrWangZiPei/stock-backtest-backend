import pandas as pd
import numpy as np
from .base_strategy import BaseStrategy

class DualMovingAverageStrategy(BaseStrategy):
    """
    双均线交叉策略。
    - 金叉 (买入信号): 短期均线从下方向上穿过长期均线。
    - 死叉 (卖出信号): 短期均线从上方向下穿过长期均线。
    """

    def __init__(self, parameters: dict):
        super().__init__(parameters)
        self.short_window = self.parameters.get('short_window', 5)
        self.long_window = self.parameters.get('long_window', 20)
        self.short_ma_col = f'ma{self.short_window}'
        self.long_ma_col = f'ma{self.long_window}'

    @classmethod
    def get_parameter_definitions(cls):
        return [
            {'name': 'short_window', 'label': '短期均线', 'type': 'number', 'default': 5, 'description': '短期移动平均线的计算窗口，用于捕捉近期趋势。'},
            {'name': 'long_window', 'label': '长期均线', 'type': 'number', 'default': 20, 'description': '长期移动平均线的计算窗口，用于判断长期趋势。'},
        ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        为给定的数据生成买入/卖出信号。

        :param data: DataFrame，需包含 'close_price' 列。
        :return: 带有 'signal' 列的 DataFrame。
        """
        signals_df = data.copy()
        
        # 1. 计算移动平均线
        signals_df[self.short_ma_col] = signals_df['close_price'].rolling(window=self.short_window, min_periods=1).mean()
        signals_df[self.long_ma_col] = signals_df['close_price'].rolling(window=self.long_window, min_periods=1).mean()

        # 2. 信号初始化为 'hold'
        signals_df['signal'] = 'hold'

        # 3. 计算短期均线和长期均线的位置关系
        # 当短期 > 长期时，为1；否则为-1
        signals_df['position'] = np.where(signals_df[self.short_ma_col] > signals_df[self.long_ma_col], 1, -1)
        
        # 4. 寻找交叉点
        # 当position从-1变为1时，是金叉（买入）
        # 当position从1变为-1时，是死叉（卖出）
        # .diff() 会计算当前行与前一行的差异
        signals_df['crossover'] = signals_df['position'].diff()

        # 5. 生成信号
        signals_df.loc[signals_df['crossover'] == 2, 'signal'] = 'buy'  # 从-1到1，差值为2
        signals_df.loc[signals_df['crossover'] == -2, 'signal'] = 'sell' # 从1到-1，差值为-2

        return signals_df[['trade_date', 'close_price', 'signal']] 