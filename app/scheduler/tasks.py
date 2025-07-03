import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy import func
from app import db
from app.models import Stock, DailyData
from app.models.update_log import UpdateLog
from app.data_collector import DataCollector
import pandas as pd

logger = logging.getLogger(__name__)

class DataUpdateTask:
    """数据更新任务"""
    
    def __init__(self, app, socketio=None):
        self.app = app
        self.collector = DataCollector()
        self.socketio = socketio
    
    def _emit_progress(self, event, data, sid=None):
        """通过WebSocket发送进度 (广播)"""
        if self.socketio:
            logger.info(f"🔔 发送WebSocket事件: {event}, 数据: {data}, SID: {sid}")
            namespace = '/scheduler'
            try:
                # 直接广播给命名空间下的所有客户端，保证刷新后重新连接的客户端能继续收到进度
                self.socketio.emit(event, data, namespace=namespace)
                # 如果需要，也可以定向发送给原 SID（可选，避免重复可省略）
                # if sid:
                #     self.socketio.emit(event, data, namespace=namespace, to=sid)
                self.socketio.sleep(0.05)  # 确保消息发出
            except Exception as e:
                logger.error(f"❌ 发送WebSocket事件失败: {e}")
        else:
            logger.warning("⚠️ SocketIO实例为空，无法发送事件")
    
    def update_daily_data(self, date_str: str = None, sid: str = None) -> Dict[str, Any]:
        """
        更新每日数据。
        如果未指定日期 (date_str为None)，则自动检测数据库中缺失的交易日数据并进行更新。
        Args:
            date_str: 指定日期，格式为 YYYY-MM-DD，如果为None则自动检测缺失日期
            sid: WebSocket session ID，用于发送进度
        Returns:
            包含更新结果的字典
        """
        with self.app.app_context():
            updated_count = 0
            error_count = 0
            # 获取总股票数，用于判断数据是否完整
            total_stocks = db.session.query(Stock).count()
            if total_stocks == 0:
                message = "数据库中没有股票信息，请先更新股票列表。"
                logger.warning(message)
                self._emit_progress('update_error', {'task': 'update_daily_data', 'message': message}, sid=sid)
                return {'success': False, 'message': message, 'data': None}

            try:
                dates_to_update = []
                if date_str:
                    # 如果指定了日期，则只更新该日期
                    dates_to_update.append(date_str)
                else:
                    # 自动检测缺失日期
                    latest_date_in_db = db.session.query(func.max(DailyData.trade_date)).scalar()
                    logger.info(f"DEBUG: latest_date_in_db: {latest_date_in_db}")

                    today = datetime.now().date()
                    logger.info(f"DEBUG: today: {today}")

                    start_date_to_process = None

                    if latest_date_in_db:
                        # Check if the latest_date_in_db's data is complete
                        daily_data_count_latest = db.session.query(DailyData).filter_by(trade_date=latest_date_in_db).count()
                        logger.info(f"DEBUG: For latest_date_in_db ({latest_date_in_db}), count: {daily_data_count_latest}, total_stocks: {total_stocks}")
                        
                        if daily_data_count_latest < total_stocks:
                            # If latest date in DB is incomplete, start processing from that date
                            start_date_to_process = latest_date_in_db
                            logger.info(f"DEBUG: Latest date {latest_date_in_db} is incomplete. Starting processing from it.")
                        else:
                            # If latest date in DB is complete, start processing from the next day
                            start_date_to_process = latest_date_in_db + timedelta(days=1)
                            logger.info(f"DEBUG: Latest date {latest_date_in_db} is complete. Starting processing from next day.")
                    else:
                        # If no data in DB, start from a reasonable past date, e.g., 30 days ago
                        start_date_to_process = today - timedelta(days=30)
                        logger.info(f"DEBUG: No data in DB. Starting processing from {start_date_to_process} (30 days ago).")
                    
                    logger.info(f"DEBUG: Calculated start_date_to_process: {start_date_to_process}")

                    current_check_date = start_date_to_process
                    while current_check_date <= today:
                        date_str_to_check = current_check_date.strftime('%Y-%m-%d')
                        is_trading_day = self._is_trading_day(date_str_to_check)
                        logger.info(f"DEBUG: Checking date {date_str_to_check}. Is trading day: {is_trading_day}")
                        
                        if is_trading_day:
                            # 检查该日期的数据是否完整（已入库的股票数量是否等于总股票数量）
                            daily_data_count = db.session.query(DailyData).filter_by(trade_date=current_check_date).count()
                            logger.info(f"DEBUG: For {date_str_to_check}, daily_data_count: {daily_data_count}, total_stocks: {total_stocks}")
                            
                            if daily_data_count < total_stocks:
                                dates_to_update.append(date_str_to_check)
                                logger.info(f"DEBUG: Added {date_str_to_check} to dates_to_update. Current list: {dates_to_update}")
                            else:
                                logger.info(f"DEBUG: {date_str_to_check} data is complete ({daily_data_count}/{total_stocks}). Skipping.")
                        else:
                            logger.info(f"DEBUG: {date_str_to_check} is not a trading day. Skipping.")
                        current_check_date += timedelta(days=1)
                
                logger.info(f"DEBUG: Final dates_to_update list before check: {dates_to_update}")
                if not dates_to_update:
                    message = "数据已经是最新，无需更新。"
                    logger.info(message)
                    self._emit_progress('update_complete', {
                        'task': 'update_daily_data',
                        'progress': 100,
                        'message': message,
                        'success': True,
                        'data': {'updated_count': 0}
                    }, sid=sid)
                    return {'success': True, 'message': message, 'data': {'updated_count': 0}}
                
                # Update log to running
                try:
                    UpdateLog.update_task_status('update_daily_data', 'running', f'正在更新 {len(dates_to_update)} 个交易日的数据...')
                except Exception as _:
                    logger.warning("无法写入 UpdateLog (daily running)")
                
                # Iterate through dates to update
                total_dates_to_process = len(dates_to_update)
                for idx, target_date_str in enumerate(dates_to_update):
                    logger.info(f"开始更新 {target_date_str} 的数据 ({idx + 1}/{total_dates_to_process})")

                    # Define progress callback for each date
                    def date_progress_callback(progress_data):
                        # Augment progress data with overall task progress
                        overall_progress = int(((idx + progress_data.get('progress', 0) / 100) / total_dates_to_process) * 100)
                        self._emit_progress('update_progress', {
                        'task': 'update_daily_data',
                            'date': target_date_str,
                            'progress': overall_progress,
                            'message': f"正在更新 {target_date_str}: {progress_data.get('message', '')}",
                            'current_date_progress': progress_data.get('progress', 0)
                    }, sid=sid)
                    
                    result = self.collector.update_daily_data(target_date_str, progress_callback=date_progress_callback)
                    
                    if result.get('success'):
                        updated_count += result.get('updated_count', 0)
                        logger.info(f"{target_date_str} 数据更新成功: {result}")
                        self._log_update_result('daily_data', target_date_str, result, status='success')
                    else:
                        error_count += 1
                        logger.error(f"{target_date_str} 数据更新失败: {result.get('message', '未知错误')}")
                        self._log_update_result('daily_data', target_date_str, result, status='error', message=result.get('message', ''))

                message = f"每日数据更新完成: 成功 {updated_count} 条，失败 {error_count} 条。"
                logger.info(message)
                self._emit_progress('update_complete', {
                    'task': 'update_daily_data',
                    'progress': 100,
                    'message': message,
                    'success': True,
                    'data': {'updated_count': updated_count, 'error_count': error_count}
                }, sid=sid)
                UpdateLog.update_task_status('update_daily_data', 'success', message)
                return {'success': True, 'message': message, 'data': {'updated_count': updated_count, 'error_count': error_count}}
                
            except Exception as e:
                message = f"每日数据更新任务失败: {str(e)}"
                logger.error(message, exc_info=True)
                self._emit_progress('update_error', {
                    'task': 'update_daily_data',
                    'message': message
                }, sid=sid)
                UpdateLog.update_task_status('update_daily_data', 'error', message)
                return {'success': False, 'message': message, 'data': None}
    
    def update_stock_list(self, sid: str = None) -> Dict[str, Any]:
        """
        更新股票列表
        
        Args:
            sid: WebSocket会话ID，用于定向发送进度消息
            
        Returns:
            包含更新结果的字典
        """
        with self.app.app_context():
            try:
                logger.info("开始更新股票列表")
                
                # 更新日志为运行中
                try:
                    UpdateLog.update_task_status('update_stock_list', 'running', '任务进行中...')
                except Exception:
                    logger.warning("无法写入 UpdateLog (stock running)")
                
                def progress_callback(progress_data):
                    self._emit_progress('update_progress', progress_data, sid=sid)

                result = self.collector.collect_all_stocks(progress_callback=progress_callback)
                
                logger.info(f"股票列表更新完成: {result}")
                
                # 记录更新日志
                success = result.get('success', 0) > 0 and result.get('error', 0) == 0
                message = "股票列表更新成功" if success else f"股票列表更新部分失败 (成功: {result.get('success', 0)}, 失败: {result.get('error', 0)})"
                self._log_update_result('stock_list', datetime.now().strftime('%Y-%m-%d'), result)
                
                # 发送完成状态
                self._emit_progress('update_complete', {
                    'task': 'update_stock_list',
                    'progress': 100,
                    'message': message,
                    'success': success,
                    'data': result
                }, sid=sid)
                
                # 更新 UpdateLog 状态
                try:
                    UpdateLog.update_task_status('update_stock_list', 'success' if success else 'error', message)
                except Exception:
                    logger.warning("无法写入 UpdateLog (stock finish)")
                
                return {
                    'success': success,
                    'message': message,
                    'data': result
                }
                
            except Exception as e:
                error_msg = f"更新股票列表失败: {str(e)}"
                logger.error(error_msg)
                
                # 发送错误状态
                self._emit_progress('update_error', {
                    'task': 'update_stock_list',
                    'message': error_msg
                }, sid=sid)
                
                try:
                    UpdateLog.update_task_status('update_stock_list', 'error', error_msg)
                except Exception:
                    logger.warning("无法写入 UpdateLog (stock error)")
                
                return {
                    'success': False,
                    'message': error_msg,
                    'data': None
                }
    
    def cleanup_old_data(self, days_to_keep: int = 3650) -> Dict[str, Any]:
        """
        清理旧数据
        
        Args:
            days_to_keep: 保留的天数，默认10年
            
        Returns:
            包含清理结果的字典
        """
        with self.app.app_context():
            try:
                logger.info(f"开始清理 {days_to_keep} 天前的数据")
                
                cutoff_date = datetime.now() - timedelta(days=days_to_keep)
                
                # 删除旧的日线数据
                deleted_count = db.session.query(DailyData).filter(
                    DailyData.trade_date < cutoff_date.date()
                ).delete()
                
                db.session.commit()
                
                logger.info(f"数据清理完成，删除了 {deleted_count} 条记录")
                
                result = {'deleted_count': deleted_count}
                self._log_update_result('data_cleanup', datetime.now().strftime('%Y-%m-%d'), result)
                
                # 发送完成状态
                self._emit_progress('update_complete', {
                    'task': 'data_cleanup',
                    'progress': 100,
                    'message': f"成功清理了 {deleted_count} 条旧数据",
                    'success': True,
                    'data': result
                }, sid=None)  # 全局广播
                
                return {
                    'success': True,
                    'message': f"成功清理了 {deleted_count} 条旧数据",
                    'data': result
                }
                
            except Exception as e:
                logger.error(f"清理旧数据失败: {str(e)}", exc_info=True)
                db.session.rollback()
                # 发送完成状态（失败）
                self._emit_progress('update_complete', {
                    'task': 'data_cleanup',
                    'progress': 100,
                    'message': f"清理失败: {str(e)}",
                    'success': False,
                    'data': None
                }, sid=None)
                return {
                    'success': False,
                    'message': f"清理失败: {str(e)}",
                    'data': None
                }
    
    def batch_update_historical_data(self, start_date: str, end_date: str = None, 
                                   stock_codes: list = None) -> Dict[str, Any]:
        """
        批量更新历史数据
        
        Args:
            start_date: 开始日期，格式为 YYYY-MM-DD
            end_date: 结束日期，格式为 YYYY-MM-DD，如果为None则使用当前日期
            stock_codes: 指定股票代码列表，如果为None则更新所有股票
            
        Returns:
            包含更新结果的字典
        """
        with self.app.app_context():
            try:
                if not end_date:
                    end_date = datetime.now().strftime('%Y-%m-%d')
                
                logger.info(f"开始批量更新 {start_date} 到 {end_date} 的历史数据")
                
                # 获取需要更新的日期列表
                date_list = self._get_trading_days_between(start_date, end_date)
                
                total_success = 0
                total_error = 0
                
                for date_str in date_list:
                    if stock_codes:
                        # 更新指定股票
                        result = self._update_specific_stocks_data(date_str, stock_codes)
                    else:
                        # 更新所有股票
                        result = self.collector.update_daily_data(date_str)
                    
                    total_success += result.get('success', 0)
                    total_error += result.get('error', 0)
                    
                    logger.info(f"已完成 {date_str} 的数据更新")
                
                result = {
                    'success': total_success,
                    'error': total_error,
                    'dates_processed': len(date_list)
                }
                
                logger.info(f"批量历史数据更新完成: {result}")
                
                return {
                    'success': True,
                    'message': f"批量更新完成，处理了 {len(date_list)} 个交易日",
                    'data': result
                }
                
            except Exception as e:
                logger.error(f"批量更新历史数据失败: {str(e)}", exc_info=True)
                return {
                    'success': False,
                    'message': f"批量更新失败: {str(e)}",
                    'data': None
                }
    
    def _is_trading_day(self, date_str: str) -> bool:
        """
        检查是否为交易日
        
        Args:
            date_str: 日期字符串，格式为 YYYY-MM-DD
            
        Returns:
            是否为交易日
        """
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            
            # 简单的交易日判断：周一到周五，排除一些明显的节假日
            if date_obj.weekday() >= 5:  # 周六日
                return False
            
            # 可以在这里添加更复杂的节假日判断逻辑
            # 例如：春节、国庆节等
            
            return True
            
        except Exception:
            return False
    
    def _get_trading_days_between(self, start_date: str, end_date: str) -> list:
        """
        获取两个日期之间的交易日列表
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            交易日期列表
        """
        trading_days = []
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current_date <= end_date_obj:
            if self._is_trading_day(current_date.strftime('%Y-%m-%d')):
                trading_days.append(current_date.strftime('%Y-%m-%d'))
            current_date += timedelta(days=1)
        
        return trading_days
    
    def _update_specific_stocks_data(self, date_str: str, stock_codes: list) -> Dict[str, int]:
        """
        更新指定股票的数据
        
        Args:
            date_str: 日期字符串
            stock_codes: 股票代码列表
            
        Returns:
            更新结果统计
        """
        success_count = 0
        error_count = 0
        
        updated_stocks = 0
        
        for code in stock_codes:
            try:
                stock = Stock.query.filter_by(code=code).first()
                if not stock:
                    logger.warning(f"股票 {code} 不存在")
                    error_count += 1
                    continue
                
                # 检查是否已有数据
                existing_data = DailyData.query.filter_by(
                    stock_id=stock.id,
                    trade_date=datetime.strptime(date_str, '%Y-%m-%d').date()
                ).first()
                
                if existing_data:
                    continue
                
                # 获取数据
                df = self.collector.akshare_client.get_stock_history(code, date_str, date_str)
                
                if df is None or df.empty:
                    error_count += 1
                    continue
                    
                # 计算技术指标
                historical_df = self.collector._get_historical_data_for_indicators(stock.id, date_str)
                if historical_df is not None and not historical_df.empty:
                    combined_df = pd.concat([historical_df, df]).sort_values('trade_date')
                    combined_df = self.collector.indicators.add_all_indicators(combined_df)
                    df = combined_df.tail(1)

                # 保存数据
                row = df.iloc[0]
                daily_data = DailyData(
                    stock_id=stock.id,
                    trade_date=row['trade_date'].date(),
                    open_price=row['open_price'],
                    high_price=row['high_price'],
                    low_price=row['low_price'],
                    close_price=row['close_price'],
                    volume=row['volume'],
                    amount=row['amount'],
                    adj_close=row['adj_close'],
                    ma5=row.get('ma5'),
                    ma10=row.get('ma10'),
                    ma20=row.get('ma20'),
                    ma60=row.get('ma60'),
                    macd_dif=row.get('macd_dif'),
                    macd_dea=row.get('macd_dea'),
                    macd_macd=row.get('macd_macd'),
                    rsi_6=row.get('rsi_6'),
                    rsi_12=row.get('rsi_12'),
                    rsi_24=row.get('rsi_24'),
                    turnover_rate=row.get('turnover_rate')
                )
                db.session.add(daily_data)
                success_count += 1
                updated_stocks += 1
                    
            except Exception as e:
                logger.error(f"更新股票 {code} 数据失败: {str(e)}")
                error_count += 1
                db.session.rollback()
        
        try:
            db.session.commit()
            if updated_stocks > 0:
                logger.info(f"为 {updated_stocks} 只指定股票更新了 {date_str} 的数据。")
        except Exception as e:
            db.session.rollback()
            logger.error(f"为指定股票提交 {date_str} 数据失败: {str(e)}")
            return {'success': 0, 'error': len(stock_codes)}
            
        return {'success': success_count, 'error': error_count}
    
    def _log_update_result(self, task_type: str, date: str, result: dict, status: str = 'success', message: str = ''):
        """
        记录更新结果日志
        
        Args:
            task_type: 任务类型
            date: 日期
            result: 结果
            status: 状态
            message: 消息
        """
        logger.info(f"Task: {task_type}, Date: {date}, Result: {result}, Status: {status}, Message: {message}")
        
        # 写入 UpdateLog
        try:
            UpdateLog.update_task_status(f"update_{task_type}", status, str(result))
        except Exception:
            logger.warning("无法写入 UpdateLog (generic)") 