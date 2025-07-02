import baostock as bs
import pandas as pd
import logging
from datetime import datetime, timedelta
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
        :param trade_date: 交易日期，格式 YYYY-MM-DD，如果为None则使用一个确定的历史交易日
        :return: 包含股票代码和名称的DataFrame
        """
        if not self._is_logged_in:
            raise ConnectionError("BaoStock is not logged in.")
            
        if trade_date is None:
            # 使用一个确定的历史交易日，避免非交易日问题
            trade_date = "2024-12-31"
            
        rs = self.bs.query_all_stock(day=trade_date)
        if rs.error_code != '0':
            logger.error(f"查询股票列表失败: {rs.error_msg}")
            return pd.DataFrame()
            
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            logger.warning(f"在交易日 {trade_date} 未获取到任何股票数据")
            return pd.DataFrame()
            
        df = pd.DataFrame(data_list, columns=rs.fields)

        # 若查询字段缺失 tradeStatus，则填充默认 '1'
        if 'tradeStatus' not in df.columns:
            df['tradeStatus'] = '1'

        # 移除内部过滤逻辑，让外部的filter_stocks_baostock方法来处理
        # 这里只返回原始数据
        
        # 确保列存在再返回
        base_cols = ['code', 'code_name', 'tradeStatus']
        if 'ipoDate' in df.columns:
            base_cols.append('ipoDate')
        return df[base_cols]

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

    def get_stock_history(self, stock_code, start_date=None, end_date=None, days_ago=None):
        if days_ago:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        
        if not all([stock_code, start_date, end_date]):
            raise ValueError("Must provide stock_code, start_date, and end_date, or days_ago.")

        fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST"
        rs = self.bs.query_history_k_data_plus(stock_code, fields, start_date=start_date, end_date=end_date, frequency="d", adjustflag="2") # 2是前复权
        
        if rs.error_code != '0':
            logger.error(f'获取 {stock_code} 历史数据失败: {rs.error_msg}')
            return pd.DataFrame()
        
        return rs.get_data() 