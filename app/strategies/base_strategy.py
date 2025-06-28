from abc import ABC, abstractmethod
import pandas as pd
import re
import inspect

class BaseStrategy(ABC):
    """
    策略基类，所有具体策略都应继承此类。
    """
    def __init__(self, parameters: dict):
        """
        初始化策略。
        :param parameters: 一个包含策略所需参数的字典。
        """
        self.parameters = parameters

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        根据输入的历史数据生成交易信号。

        :param data: 一个Pandas DataFrame，包含日线数据，
                     必须包含 'trade_date', 'close_price', 和相关的技术指标列。
        :return: 一个带有'signal'列的Pandas DataFrame。
                 'signal'可以是 'buy', 'sell', 'hold'。
        """
        pass

    @classmethod
    @abstractmethod
    def get_parameter_definitions(cls):
        """
        返回策略参数的定义，用于在前端动态生成表单。
        
        :return: 一个列表，每个元素是一个描述参数的字典。
                 例如: [{'name': 'short_window', 'label': '短期均线', 'type': 'number', 'default': 5}]
        """
        pass

    @classmethod
    def get_name(cls) -> str:
        # 将类名从 "CamelCase" 转换为 "Spaced Name"
        name = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', cls.__name__)
        return name.replace(" Strategy", "")

    @classmethod
    def get_description(cls) -> str:
        """获取策略的描述"""
        doc = cls.__doc__
        if doc:
            # 清理文档字符串的缩进
            return inspect.cleandoc(doc)
        return "暂无描述"

    @classmethod
    def get_identifier(cls) -> str:
        # 将类名转换为 "snake_case"
        return re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower().replace('_strategy', '') 