import pandas as pd
import pandas_ta as ta
from .base_strategy import BaseStrategy

class MacdStrategy(BaseStrategy):
    """
    MACD (Moving Average Convergence Divergence) 策略。
    - 金叉 (买入信号): MACD线 (快线) 从下方向上穿过信号线 (慢线)。
    - 死叉 (卖出信号): MACD线 (快线) 从上方向下穿过信号线 (慢线)。
    """

    def __init__(self, custom_parameters: dict = None):
        super().__init__(custom_parameters)
        self.fast = self.parameters.get('fast', 12)
        self.slow = self.parameters.get('slow', 26)
        self.signal_period = self.parameters.get('signal', 9)
        self.macd_col = f'MACD_{self.fast}_{self.slow}_{self.signal_period}'
        self.signal_col = f'MACDs_{self.fast}_{self.slow}_{self.signal_period}'

    @classmethod
    def get_parameter_definitions(cls):
        return [
            {'name': 'fast', 'label': '快线周期', 'type': 'number', 'default': 12, 'description': '快线(DIF)的短期指数移动平均周期，常用值为12。'},
            {'name': 'slow', 'label': '慢线周期', 'type': 'number', 'default': 26, 'description': '快线(DIF)的长期指数移动平均周期，常用值为26。'},
            {'name': 'signal_period', 'label': '信号线周期', 'type': 'number', 'default': 9, 'description': '慢线(DEA)的指数移动平均周期，基于DIF计算，常用值为9。'}
        ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        为给定的数据生成买入/卖出信号。

        :param data: DataFrame，需包含 'close_price' 列。
        :return: 带有 'signal' 列的 DataFrame。
        """
        signals_df = data.copy()
        
        # 1. 计算 MACD
        macd = ta.macd(signals_df['close_price'], fast=self.fast, slow=self.slow, signal=self.signal_period)
        signals_df = pd.concat([signals_df, macd], axis=1)
        signals_df.dropna(subset=[self.macd_col, self.signal_col], inplace=True)

        # 2. 信号初始化为 'hold'
        signals_df['signal'] = 'hold'

        # 3. 确定前一天的位置
        signals_df['prev_macd'] = signals_df[self.macd_col].shift(1)
        signals_df['prev_signal_line'] = signals_df[self.signal_col].shift(1)
        signals_df.dropna(subset=['prev_macd', 'prev_signal_line'], inplace=True)

        # 4. 生成信号
        # 金叉买入信号：MACD线从下方上穿信号线
        buy_conditions = (signals_df[self.macd_col] > signals_df[self.signal_col]) & \
                         (signals_df['prev_macd'] <= signals_df['prev_signal_line'])
        
        # 死叉卖出信号：MACD线从上方下穿信号线
        sell_conditions = (signals_df[self.macd_col] < signals_df[self.signal_col]) & \
                          (signals_df['prev_macd'] >= signals_df['prev_signal_line'])

        signals_df.loc[buy_conditions, 'signal'] = 'buy'
        signals_df.loc[sell_conditions, 'signal'] = 'sell'

        return signals_df[['trade_date', 'close_price', 'signal']] 