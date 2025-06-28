from .base_strategy import BaseStrategy
from .dual_moving_average import DualMovingAverageStrategy
from .macd_strategy import MacdStrategy
from .rsi_strategy import RsiStrategy

# 策略映射表，键为策略的唯一标识符，值为策略类
STRATEGY_MAP = {
    strategy.get_identifier(): strategy
    for strategy in [
        DualMovingAverageStrategy,
        MacdStrategy,
        RsiStrategy
        # 新策略在这里添加
    ]
}

def get_strategy_by_identifier(identifier: str):
    """
    根据策略的唯一标识符获取策略类。

    :param identifier: 策略的标识符 (e.g., 'dual_moving_average')
    :return: 对应的策略类，如果找不到则返回 None
    """
    return STRATEGY_MAP.get(identifier)

__all__ = [
    'BaseStrategy',
    'STRATEGY_MAP',
    'get_strategy_by_identifier',
    'DualMovingAverageStrategy',
    'MacdStrategy',
    'RsiStrategy'
] 