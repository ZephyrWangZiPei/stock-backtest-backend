import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
from sqlalchemy.exc import IntegrityError
import time
import random

from app import db
from app.models import Stock, DailyData
from .indicators import TechnicalIndicators
from .baostock_client import BaostockClient

logger = logging.getLogger(__name__)

class DataCollector:
    """数据采集器 (完全基于BaoStock)"""
    
    def __init__(self):
        self.indicators = TechnicalIndicators()

    def collect_all_stocks(self, progress_callback=None) -> Dict[str, int]:
        """使用BaoStock采集所有股票基础信息"""
        success_count = 0
        error_count = 0
        
        try:
            with BaostockClient() as client:
                all_stocks_df = client.get_all_stocks()
                total_stocks = len(all_stocks_df)
                
                # 发送初始进度
                if progress_callback:
                    progress_callback({
                        'task': 'update_stock_list',
                        'progress': 0,
                        'message': f'开始更新，共 {total_stocks} 只股票',
                        'current': 0,
                        'total': total_stocks
                    })
                
                for i, row in all_stocks_df.iterrows():
                    try:
                        stock_code = row['code']
                        stock_name = row['code_name']

                        existing_stock = Stock.query.filter_by(code=stock_code).first()
                        
                        if existing_stock:
                            # 更新名称，以防变更
                            if existing_stock.name != stock_name:
                                existing_stock.name = stock_name
                                existing_stock.updated_at = datetime.utcnow()
                        else:
                            # 创建新记录
                            market = stock_code.split('.')[0].upper()
                            stock = Stock(
                                code=stock_code,
                                name=stock_name,
                                market=market,
                                stock_type='stock'
                            )
                            
                            # 获取并填充详细信息
                            detail_df = client.get_stock_basic_info(stock_code)
                            if detail_df is not None and not detail_df.empty:
                                detail = detail_df.iloc[0]
                                stock.industry = detail.get('industry')
                                ipo_date = detail.get('ipoDate')
                                if ipo_date:
                                    stock.list_date = datetime.strptime(ipo_date, '%Y-%m-%d').date()

                            db.session.add(stock)
                        
                        success_count += 1
                        
                        # 每处理10只股票更新一次进度
                        if progress_callback and (i + 1) % 10 == 0:
                            progress = int((i + 1) / total_stocks * 100)
                            progress_callback({
                                'task': 'update_stock_list',
                                'progress': progress,
                                'message': f'已处理 {i + 1}/{total_stocks} 只股票',
                                'current': i + 1,
                                'total': total_stocks
                            })
                            
                    except Exception as e:
                        error_count += 1
                        logger.error(f"处理股票 {stock_code} 时出错: {str(e)}")
                        continue
                
                # 提交所有更改
                db.session.commit()
                
                # 发送最终进度
                if progress_callback:
                    progress_callback({
                        'task': 'update_stock_list',
                        'progress': 100,
                        'message': f'更新完成，成功 {success_count} 只，失败 {error_count} 只',
                        'current': total_stocks,
                        'total': total_stocks
                    })
                
        except Exception as e:
            logger.error(f"采集股票列表时发生错误: {str(e)}")
            db.session.rollback()
            error_count = total_stocks if 'total_stocks' in locals() else 0
            success_count = 0
            
            # 发送错误进度
            if progress_callback and 'total_stocks' in locals():
                progress_callback({
                    'task': 'update_stock_list',
                    'progress': 0,
                    'message': f'更新失败: {str(e)}',
                    'current': 0,
                    'total': total_stocks
                })
        
        return {'success': success_count, 'error': error_count}

    def update_daily_data(self, date: str = None, progress_callback=None) -> Dict[str, int]:
        """使用BaoStock更新日线数据"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"开始使用BaoStock更新 {date} 的日线数据...")
        
        # 首先检查BaoStock是否有当天的数据
        try:
            with BaostockClient() as client:
                test_stocks_df = client.get_all_stocks(date)
                if test_stocks_df is None or len(test_stocks_df) == 0:
                    message = f"BaoStock暂无 {date} 的股票数据，可能是非交易日或数据尚未更新"
                    logger.warning(message)
                    if progress_callback:
                        progress_callback({
                            'task': 'update_daily_data',
                            'progress': 100,
                            'message': message
                        })
                    return {'success': 0, 'error': 0, 'total': 0, 'message': message}
        except Exception as e:
            logger.error(f"检查BaoStock数据可用性失败: {e}")
            return {'success': 0, 'error': 1, 'total': 0, 'message': f"数据源连接失败: {str(e)}"}
        
        stocks = Stock.query.filter(Stock.is_active == True).all()
        total_stocks = len(stocks)
        success_count = 0
        error_count = 0
        
        logger.info(f"即将处理 {total_stocks} 只股票...")

        try:
            with BaostockClient() as client:
                for i, stock in enumerate(stocks):
                    try:
                        logger.info(f"[{i + 1}/{total_stocks}] 正在处理股票: {stock.code}")

                        # 检查数据是否已存在
                        existing_data = DailyData.query.filter_by(
                            stock_id=stock.id,
                            trade_date=datetime.strptime(date, '%Y-%m-%d').date()
                        ).first()
                        if existing_data:
                            continue

                        # 获取日线数据
                        df = client.get_stock_history(stock.code, date, date)
                        if df is None or df.empty:
                            continue
                        
                        # 确保数值列为float类型
                        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn']
                        for col in numeric_columns:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors='coerce')
                        
                        # BaoStock返回的数据列名需要转换
                        df.rename(columns={
                            'date': 'trade_date',
                            'open': 'open_price',
                            'high': 'high_price',
                            'low': 'low_price',
                            'close': 'close_price',
                            'turn': 'turnover_rate'
                        }, inplace=True)
                        df['trade_date'] = pd.to_datetime(df['trade_date'])

                        # 计算指标
                        historical_df = self._get_historical_data_for_indicators(stock.id, date)
                        if historical_df is not None:
                            # 确保历史数据的数值列也是float类型
                            numeric_columns = ['open_price', 'high_price', 'low_price', 'close_price', 'volume']
                            for col in numeric_columns:
                                if col in historical_df.columns:
                                    historical_df[col] = pd.to_numeric(historical_df[col], errors='coerce')
                            
                            # 统一列名
                            historical_df.rename(columns={
                                'open_price': 'open',
                                'high_price': 'high',
                                'low_price': 'low',
                                'close_price': 'close'
                            }, inplace=True)
                            
                            combined_df = pd.concat([historical_df, df]).sort_values('trade_date')
                            combined_df = self.indicators.add_all_indicators(combined_df)
                            df = combined_df.tail(1)

                        # 保存数据
                        row = df.iloc[0]
                        
                        # 处理 nan 值的辅助函数
                        def safe_float(value, default=0.0):
                            try:
                                if pd.isna(value):
                                    return default
                                return float(value)
                            except (ValueError, TypeError):
                                return default
                        
                        daily_data = DailyData(
                            stock_id=stock.id,
                            trade_date=row['trade_date'].date(),
                            open_price=safe_float(row.get('open_price')),
                            high_price=safe_float(row.get('high_price')),
                            low_price=safe_float(row.get('low_price')),
                            close_price=safe_float(row.get('close_price')),
                            adj_close=safe_float(row.get('close_price')),
                            volume=safe_float(row.get('volume')),
                            amount=safe_float(row.get('amount')),
                            turnover_rate=safe_float(row.get('turnover_rate')),
                            ma5=safe_float(row.get('ma5')),
                            ma10=safe_float(row.get('ma10')),
                            ma20=safe_float(row.get('ma20')),
                            ma60=safe_float(row.get('ma60')),
                            macd_dif=safe_float(row.get('macd_dif')),
                            macd_dea=safe_float(row.get('macd_dea')),
                            macd_macd=safe_float(row.get('macd_macd')),
                            rsi_6=safe_float(row.get('rsi_6')),
                            rsi_12=safe_float(row.get('rsi_12')),
                            rsi_24=safe_float(row.get('rsi_24'))
                        )
                        db.session.add(daily_data)
                        
                        # 核心修改：将批处理提交改为逐条提交，确保健壮性
                        db.session.commit()
                        success_count += 1
                        
                        # 智能休眠
                        sleep_time = random.uniform(0.3, 1.2)
                        time.sleep(sleep_time)

                        # 进度回调 (改为每次都调用)
                        if progress_callback:
                            progress_callback({
                                'task': 'update_daily_data',
                                'progress': round(((i + 1) / total_stocks) * 100, 2),
                                'message': f"处理完毕: {stock.code} ({i + 1}/{total_stocks})"
                            })

                        # 每100条进行一次长时间休眠
                        if (i + 1) % 100 == 0:
                            # 长时间休眠
                            long_sleep_time = random.uniform(5, 10)
                            logger.info(f"批处理节点，休眠 {long_sleep_time:.2f} 秒...")
                            time.sleep(long_sleep_time)

                    except Exception as e:
                        db.session.rollback() # 仅回滚当前失败的单个事务
                        error_count += 1
                        logger.error(f"更新股票 {stock.code} 数据失败: {e}", exc_info=True)
                        
                        # 在错误时也更新进度
                        if progress_callback:
                            progress_callback({
                                'task': 'update_daily_data',
                                'progress': round(((i + 1) / total_stocks) * 100, 2),
                                'message': f"处理进度: 成功 {success_count} 只，失败 {error_count} 只 ({i + 1}/{total_stocks})"
                            })
                        continue
                        
        except Exception as e:
            logger.error(f"BaoStock客户端初始化或主循环外发生错误: {e}")
            error_count = total_stocks
            
            # 在全局错误时也发送进度信息
            if progress_callback:
                progress_callback({
                    'task': 'update_daily_data',
                    'progress': 100,
                    'message': f"更新失败: {str(e)}，成功 {success_count} 只，失败 {error_count} 只"
                })

        # 由于已改为逐条提交，最后的commit不再需要
        logger.info(f"BaoStock日线数据更新完成: 成功 {success_count}, 失败 {error_count}")
        
        # 发送最终进度
        if progress_callback:
            progress_callback({
                'task': 'update_daily_data',
                'progress': 100,
                'message': f"更新完成: 成功 {success_count} 只，失败 {error_count} 只"
            })
        
        return {'success': success_count, 'error': error_count, 'total': total_stocks}

    def _get_historical_data_for_indicators(self, stock_id: int, current_date: str, days: int = 100) -> Optional[pd.DataFrame]:
        """获取用于计算技术指标的历史数据"""
        try:
            end_date = datetime.strptime(current_date, '%Y-%m-%d') - timedelta(days=1)
            start_date = end_date - timedelta(days=days)
            
            historical_data = DailyData.query.filter(
                DailyData.stock_id == stock_id,
                DailyData.trade_date >= start_date.date(),
                DailyData.trade_date <= end_date.date()
            ).order_by(DailyData.trade_date).all()
            
            if not historical_data:
                return None
            
            # 转换为DataFrame
            data = [d.to_dict() for d in historical_data]
            df = pd.DataFrame(data)
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            # 返回BaoStock兼容的列名
            return df[['trade_date', 'open_price', 'high_price', 'low_price', 'close_price', 'volume']]
            
        except Exception as e:
            logger.error(f"获取指标所需历史数据失败: {e}")
            return None 