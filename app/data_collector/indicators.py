import pandas as pd
import numpy as np
from typing import Dict, Any

class TechnicalIndicators:
    """技术指标计算"""
    
    @staticmethod
    def calculate_ma(data: pd.Series, window: int) -> pd.Series:
        """计算移动平均线"""
        return data.rolling(window=window).mean()
    
    @staticmethod
    def calculate_macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """计算MACD指标"""
        ema_fast = data.ewm(span=fast).mean()
        ema_slow = data.ewm(span=slow).mean()
        
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal).mean()
        macd = (dif - dea) * 2
        
        return {
            'dif': dif,
            'dea': dea,
            'macd': macd
        }
    
    @staticmethod
    def calculate_rsi(data: pd.Series, window: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def calculate_bollinger_bands(data: pd.Series, window: int = 20, num_std: float = 2) -> Dict[str, pd.Series]:
        """计算布林带"""
        sma = data.rolling(window=window).mean()
        std = data.rolling(window=window).std()
        
        upper = sma + (std * num_std)
        lower = sma - (std * num_std)
        
        return {
            'upper': upper,
            'middle': sma,
            'lower': lower
        }
    
    @staticmethod
    def calculate_kdj(high: pd.Series, low: pd.Series, close: pd.Series, 
                     n: int = 9, m1: int = 3, m2: int = 3) -> Dict[str, pd.Series]:
        """计算KDJ指标"""
        lowest_low = low.rolling(window=n).min()
        highest_high = high.rolling(window=n).max()
        
        rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
        
        k = rsv.ewm(com=m1-1).mean()
        d = k.ewm(com=m2-1).mean()
        j = 3 * k - 2 * d
        
        return {
            'k': k,
            'd': d,
            'j': j
        }
    
    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """为数据框添加所有技术指标"""
        if df.empty:
            return df
        
        df = df.copy()
        close = df['close_price']
        high = df['high_price']
        low = df['low_price']
        
        # 移动平均线
        df['ma5'] = TechnicalIndicators.calculate_ma(close, 5)
        df['ma10'] = TechnicalIndicators.calculate_ma(close, 10)
        df['ma20'] = TechnicalIndicators.calculate_ma(close, 20)
        df['ma60'] = TechnicalIndicators.calculate_ma(close, 60)
        
        # MACD
        macd_data = TechnicalIndicators.calculate_macd(close)
        df['macd_dif'] = macd_data['dif']
        df['macd_dea'] = macd_data['dea']
        df['macd_macd'] = macd_data['macd']
        
        # RSI
        df['rsi_6'] = TechnicalIndicators.calculate_rsi(close, 6)
        df['rsi_12'] = TechnicalIndicators.calculate_rsi(close, 12)
        df['rsi_24'] = TechnicalIndicators.calculate_rsi(close, 24)
        
        # 布林带
        bb_data = TechnicalIndicators.calculate_bollinger_bands(close)
        df['bb_upper'] = bb_data['upper']
        df['bb_middle'] = bb_data['middle']
        df['bb_lower'] = bb_data['lower']
        
        # KDJ
        kdj_data = TechnicalIndicators.calculate_kdj(high, low, close)
        df['kdj_k'] = kdj_data['k']
        df['kdj_d'] = kdj_data['d']
        df['kdj_j'] = kdj_data['j']
        
        return df 