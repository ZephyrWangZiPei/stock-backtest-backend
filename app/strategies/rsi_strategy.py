import pandas as pd
import pandas_ta as ta
from .base_strategy import BaseStrategy

class RsiStrategy(BaseStrategy):
    """
    RSI (Relative Strength Index) 策略。
    - 超卖 (买入信号): RSI 从下向上穿过超卖线 (e.g., 30)。
    - 超买 (卖出信号): RSI 从上向下穿过超买线 (e.g., 70)。
    """

    def __init__(self, parameters: dict):
        super().__init__(parameters)
        self.rsi_length = self.parameters.get('rsi_length', 14)
        self.oversold_threshold = self.parameters.get('oversold_threshold', 30)
        self.overbought_threshold = self.parameters.get('overbought_threshold', 70)
        self.rsi_col = f'RSI_{self.rsi_length}'

    @classmethod
    def get_parameter_definitions(cls):
        return [
            {'name': 'rsi_period', 'label': 'RSI周期', 'type': 'number', 'default': 14, 'description': '相对强弱指数(RSI)的计算周期，常用值为14。'},
            {'name': 'overbought_threshold', 'label': '超买阈值', 'type': 'number', 'default': 70, 'description': 'RSI高于此值被视为超买区域，可能预示价格回调。'},
            {'name': 'oversold_threshold', 'label': '超卖阈值', 'type': 'number', 'default': 30, 'description': 'RSI低于此值被视为超卖区域，可能预示价格反弹。'},
        ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        为给定的数据生成买入/卖出信号。

        :param data: DataFrame，需包含 'close_price' 列。
        :return: 带有 'signal' 列的 DataFrame。
        """
        signals_df = data.copy()
        
        # 1. 计算 RSI
        signals_df[self.rsi_col] = ta.rsi(signals_df['close_price'], length=self.rsi_length)
        signals_df.dropna(subset=[self.rsi_col], inplace=True)

        # 2. 信号初始化为 'hold'
        signals_df['signal'] = 'hold'

        # 3. 确定前一天的位置
        signals_df['prev_rsi'] = signals_df[self.rsi_col].shift(1)

        # 4. 生成信号
        # 买入信号：RSI 从下方上穿超卖线
        buy_conditions = (signals_df[self.rsi_col] > self.oversold_threshold) & (signals_df['prev_rsi'] <= self.oversold_threshold)
        
        # 卖出信号：RSI 从上方下穿超买线
        sell_conditions = (signals_df[self.rsi_col] < self.overbought_threshold) & (signals_df['prev_rsi'] >= self.overbought_threshold)

        signals_df.loc[buy_conditions, 'signal'] = 'buy'
        signals_df.loc[sell_conditions, 'signal'] = 'sell'

        return signals_df[['trade_date', 'close_price', 'signal']] 