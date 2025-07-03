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
        
        # 批量提交相关配置
        batch_size = 500  # 每批提交条数，可按需要调整
        batch_objects = []
        
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
                        # 批量收集，按 batch_size 批量提交
                        batch_objects.append(daily_data)
                        success_count += 1

                        if len(batch_objects) >= batch_size:
                            try:
                                db.session.bulk_save_objects(batch_objects)
                                db.session.commit()
                                batch_objects.clear()
                            except IntegrityError as ie:
                                db.session.rollback()
                                error_count += len(batch_objects)
                                logger.warning(f"批量提交出现完整性错误，部分记录可能已存在: {ie}")
                                batch_objects.clear()
                            except Exception as e_commit:
                                db.session.rollback()
                                error_count += len(batch_objects)
                                logger.error(f"批量提交失败: {e_commit}", exc_info=True)
                                batch_objects.clear()

                        # 进度回调 (改为每次都调用)
                        if progress_callback:
                            progress_callback({
                                'task': 'update_daily_data',
                                'progress': round(((i + 1) / total_stocks) * 100, 2),
                                'message': f"处理完毕: {stock.code} ({i + 1}/{total_stocks})"
                            })

                        # 每 500 条后可选择短暂休息以避免限速
                        if (i + 1) % batch_size == 0:
                            time.sleep(random.uniform(1, 2))

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

        # 提交剩余未提交的批次
        if batch_objects:
            try:
                db.session.bulk_save_objects(batch_objects)
                db.session.commit()
            except IntegrityError as ie:
                db.session.rollback()
                error_count += len(batch_objects)
                logger.warning(f"最终批量提交出现完整性错误，部分记录可能已存在: {ie}")
            except Exception as e_commit:
                db.session.rollback()
                error_count += len(batch_objects)
                logger.error(f"最终批量提交失败: {e_commit}", exc_info=True)
            finally:
                batch_objects.clear()

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

    def filter_stocks_baostock(self, n: int = 60) -> List[str]:
        """
        过滤股票列表：1) 次新股; 2) ST, *ST, 退市股; 3) 科创、创业板股票; 4) 指数和ETF。
        不包含涨停、跌停、停牌的实时判断，因为这需要实时行情数据且可能效率较低。
        :param n: 过滤掉n个交易日之前上市的股票 (这里简化为n个日历日)。
        :return: 过滤后的股票代码列表。
        """
        logger.info(f"开始过滤股票，排除过去 {n} 日内上市的次新股、ST/退市股、科创板/创业板股票、指数和ETF...")
        filtered_stock_codes = []
        try:
            with BaostockClient() as client:
                all_stocks_df = client.get_all_stocks()
                if all_stocks_df is None or all_stocks_df.empty:
                    logger.warning("未能获取所有股票列表，过滤操作取消。")
                    return []

                # 计算 n 日前的日期，用于过滤次新股
                # 简化为日历日，如果需要精确交易日，则需要额外查询 Baostock 交易日历
                n_days_ago = (datetime.now() - timedelta(days=n)).date()

                for _, row in all_stocks_df.iterrows():
                    stock_code = row.get('code')
                    stock_name = row.get('code_name', '')
                    ipo_date_str = row.get('ipoDate')  # 有些数据版本可能没有该字段
                    trade_status = row.get('tradeStatus', '1')  # 默认视为正常交易

                    # 0. 首先过滤指数和ETF - 这是最重要的过滤
                    # sh.000开头的都是指数
                    if stock_code.startswith('sh.000'):
                        continue
                    
                    # sz.399开头的都是深圳指数
                    if stock_code.startswith('sz.399'):
                        continue
                    
                    # 过滤ETF和基金代码段
                    fund_prefixes = (
                        'sh.51', 'sh.50', 'sh.52', 'sh.56', 'sh.58',
                        'sz.15', 'sz.16', 'sz.17', 'sz.18', 'sz.159'
                    )
                    if stock_code.startswith(fund_prefixes):
                        continue

                    # 过滤名称中包含指数、ETF、基金等关键词的证券
                    non_stock_keywords = ['指数', 'ETF', '基金', 'LOF', '债券', 'REITs']
                    if any(keyword in stock_name for keyword in non_stock_keywords):
                        continue

                    # 1. 过滤次新股 (上市日期在 n 天之内)，若没有 ipoDate 字段则跳过此过滤
                    if ipo_date_str:
                        try:
                            ipo_date = datetime.strptime(ipo_date_str, '%Y-%m-%d').date()
                            if ipo_date > n_days_ago:
                                continue
                        except ValueError:
                            # 无法解析上市日期，则不以此为依据过滤
                            pass

                    # 2. 过滤 ST, *ST, 退市股
                    if trade_status == '3': # '3' 表示退市
                        continue
                    if any(keyword in stock_name for keyword in ['ST', '*', '退']):
                        continue

                    # 3. 过滤科创板 (688) 和 创业板 (300)
                    if stock_code.startswith(('sh.688', 'sz.300')):
                        continue

                    # 4. 过滤停牌股 (tradeStatus == '2' 表示停牌)，若缺失该字段则默认正常交易
                    if trade_status == '2':
                        continue

                    # 5. 只保留主板A股股票
                    # 上海主板：sh.600, sh.601, sh.603
                    # 深圳主板：sz.000, sz.001
                    # 深圳中小板：sz.002
                    valid_prefixes = ('sh.600', 'sh.601', 'sh.603', 'sz.000', 'sz.001', 'sz.002')
                    if not stock_code.startswith(valid_prefixes):
                        continue

                    filtered_stock_codes.append(stock_code)
        except Exception as e:
            logger.error(f"过滤股票列表时发生错误: {str(e)}")
            return []

        logger.info(f"股票过滤完成，共保留 {len(filtered_stock_codes)} 只股票。")
        return filtered_stock_codes

    def screen_potential_stocks(self, n_recent_ipo_days: int = 60, bb_window: int = 20, bb_std: float = 2, gradient_lookback_days: int = 30) -> List[str]:
        """
        筛选潜力股票：
        1. 过滤掉次新股、ST/退市股、科创板/创业板、停牌股。
        2. 筛选出当前收盘价高于布林带上轨的股票。
        3. 筛选出在指定时间段内股价斜率为正的股票（上升趋势）。
        
        :param n_recent_ipo_days: 过滤次新股的上市天数。
        :param bb_window: 布林带计算的周期 (N)。
        :param bb_std: 布林带的倍数 (P)。
        :param gradient_lookback_days: 计算股价斜率所用的历史天数。
        :return: 符合筛选条件的股票代码列表。
        """
        logger.info("开始筛选潜力股票...")
        
        # 第一步：初步过滤股票
        initial_filtered_codes = self.filter_stocks_baostock(n=n_recent_ipo_days)
        if not initial_filtered_codes:
            logger.warning("初步过滤后没有股票，停止潜力股票筛选。")
            return []
            
        logger.info(f"初步过滤后共有 {len(initial_filtered_codes)} 只股票进入第二阶段筛选。")
        
        selected_stocks = []
        total_stocks_to_screen = len(initial_filtered_codes)
        
        try:
            with BaostockClient() as client:
                for i, code in enumerate(initial_filtered_codes):
                    logger.info(f"[{i + 1}/{total_stocks_to_screen}] 正在对股票 {code} 进行布林带和斜率筛选...")
                    
                    # 获取足够历史数据用于布林带和斜率计算
                    # 需要确保获取的数据量足以覆盖 bb_window 和 gradient_lookback_days 中更大的一个
                    required_days = max(bb_window, gradient_lookback_days) * 2 + 10 # 额外加一些天数以防非交易日
                    end_date = datetime.now().strftime('%Y-%m-%d')
                    start_date_obj = datetime.now() - timedelta(days=required_days)
                    start_date = start_date_obj.strftime('%Y-%m-%d')

                    df = client.get_stock_history(code, start_date, end_date)
                    
                    if df is None or df.empty:
                        logger.warning(f"未能获取 {code} 的历史数据，跳过筛选。")
                        continue
                    
                    # 确保数据为数值类型并按日期排序
                    df['close'] = pd.to_numeric(df['close'], errors='coerce')
                    df = df.dropna(subset=['close']).sort_values(by='date')
                    
                    # 确保有足够数据进行计算
                    if len(df) < required_days:
                        logger.warning(f"股票 {code} 数据不足 {required_days} 天，无法进行精确筛选，跳过。")
                        continue

                    # --- 布林带筛选 ---
                    # 取最近的 bb_window 数据进行布林带计算
                    bb_df = df.tail(bb_window)
                    if len(bb_df) < bb_window: # 再次检查是否有足够数据
                         logger.warning(f"股票 {code} 计算布林带数据不足 {bb_window} 天，跳过。")
                         continue

                    bb_ma = bb_df['close'].rolling(window=bb_window).mean()
                    bb_std_dev = bb_df['close'].rolling(window=bb_window).std()
                    upper_band = bb_ma + bb_std * bb_std_dev
                    
                    # 检查最新价格是否高于布林带上轨
                    current_close = df.iloc[-1]['close']
                    current_upper_band = upper_band.iloc[-1]
                    
                    if not (current_close > current_upper_band):
                        # logger.info(f"股票 {code} 不符合布林带上轨条件。")
                        continue # 不符合布林带条件则跳过

                    # --- 斜率筛选 ---
                    # 取最近的 gradient_lookback_days 数据进行斜率计算
                    gradient_prices = df['close'].tail(gradient_lookback_days)
                    if len(gradient_prices) < gradient_lookback_days:
                        logger.warning(f"股票 {code} 计算斜率数据不足 {gradient_lookback_days} 天，跳过。")
                        continue

                    gradient_value = TechnicalIndicators.calculate_gradient(gradient_prices)
                    
                    if gradient_value > 0: # 仅当斜率为正时才加入
                        selected_stocks.append(code)
                        logger.info(f"股票 {code} 同时符合布林带上轨和正斜率条件！")

                    # 智能休眠，避免请求过快
                    sleep_time = random.uniform(0.1, 0.5) # 适当缩短休眠时间，因为这里请求量可能较大
                    time.sleep(sleep_time)

        except Exception as e:
            logger.error(f"筛选潜力股票时发生错误: {str(e)}", exc_info=True)
            return []
            
        logger.info(f"潜力股票筛选完成，共找到 {len(selected_stocks)} 只符合条件的股票。")
        return selected_stocks 