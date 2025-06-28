import baostock as bs
import pandas as pd
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class BaostockClient:
    """
    一个用于与BaoStock API交互的客户端，包含登录和登出管理。
    """
    def __init__(self):
        self._is_logged_in = False
        self.bs = bs

    def __enter__(self):
        """上下文管理器进入方法，执行登录。"""
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出方法，执行登出。"""
        self.logout()

    def login(self):
        """登录BaoStock系统"""
        if not self._is_logged_in:
            lg = bs.login()
            if lg.error_code == '0':
                logger.info("BaoStock login successful.")
                self._is_logged_in = True
            else:
                logger.error(f"BaoStock login failed: {lg.error_msg}")
                raise ConnectionError(f"BaoStock login failed: {lg.error_msg}")

    def logout(self):
        """登出BaoStock系统"""
        if self._is_logged_in:
            bs.logout()
            logger.info("BaoStock logout successful.")
            self._is_logged_in = False

    def get_all_stocks(self, trade_date: str = None) -> pd.DataFrame:
        """
        获取指定交易日的所有股票列表
        :param trade_date: 交易日期，格式 YYYY-MM-DD，如果为None则获取最新交易日
        :return: 包含股票代码和名称的DataFrame
        """
        if not self._is_logged_in:
            raise ConnectionError("BaoStock is not logged in.")
            
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y-%m-%d')
            
        rs = self.bs.query_all_stock(day=trade_date)
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        # 筛选出股票（tradeStatus为1表示正常交易）
        df = df[(df['tradeStatus'] == '1') & (~df['code_name'].str.contains('ST'))]
        return df[['code', 'code_name']]

    def get_stock_basic_info(self, code: str) -> Optional[pd.DataFrame]:
        """
        获取单只股票的基本信息，如行业、上市日期
        """
        if not self._is_logged_in:
            raise ConnectionError("BaoStock is not logged in.")
            
        rs = self.bs.query_stock_basic(code=code)
        if rs.error_code != '0':
            logger.error(f'获取 {code} 基本信息失败: {rs.error_msg}')
            return None
            
        return rs.get_data()

    def get_stock_history(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取单只股票的日K线数据
        """
        if not self._is_logged_in:
            raise ConnectionError("BaoStock is not logged in.")
            
        fields = "date,code,open,high,low,close,volume,amount,turn"
        rs = self.bs.query_history_k_data_plus(code, fields, start_date=start_date, end_date=end_date, frequency="d", adjustflag="2") # 2是前复权
        
        if rs.error_code != '0':
            logger.error(f'获取 {code} 历史数据失败: {rs.error_msg}')
            return pd.DataFrame()
        
        return rs.get_data() 