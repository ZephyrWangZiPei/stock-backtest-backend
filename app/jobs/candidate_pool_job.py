import logging
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import desc

from app import db, create_app, socketio, _current_app_instance
from app.models import Stock, CandidateStock, DailyData

logger = logging.getLogger(__name__)

def _get_history_from_db(stock_code: str, days_ago: int = 100) -> pd.DataFrame:
    """从数据库获取指定股票的历史日线数据"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_ago * 1.5) # 多获取一些数据以防交易日不连续

    records = db.session.query(DailyData).join(Stock).filter(
        Stock.code == stock_code,
        DailyData.trade_date >= start_date
    ).order_by(desc(DailyData.trade_date)).limit(days_ago).all()

    if not records:
        return pd.DataFrame()
    
    # 将查询结果转换为DataFrame
    df = pd.DataFrame([r.to_dict() for r in records])
    df = df.sort_values(by='trade_date', ascending=True)
    # 接口需要 'close' 列，而数据库是 'close_price'
    df.rename(columns={'close_price': 'close', 'trade_date': 'date'}, inplace=True)
    df = df[['date', 'close']]
    return df

def _calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算所需的技术指标"""
    if df.empty:
        return df
    
    # 确保 'close' 列存在且为数值类型
    if 'close' in df.columns:
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df.dropna(subset=['close'], inplace=True)
    else:
        return pd.DataFrame() # 如果没有收盘价数据，则无法计算

    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()
    return df

def _check_golden_cross_candidate(df: pd.DataFrame) -> (bool, str):
    """
    检查股票是否是即将发生金叉的候选者
    条件：
    1. 长期趋势向上 (收盘价 > MA60)
    2. MA5 < MA20
    3. MA5 非常接近 MA20 (差距在2%以内)
    """
    if len(df) < 60:
        return False, None # 数据不足

    last_row = df.iloc[-1]
    price = last_row.get('close')
    ma5 = last_row.get('ma5')
    ma20 = last_row.get('ma20')
    ma60 = last_row.get('ma60')

    if not all([price, ma5, ma20, ma60]):
        return False, None # 指标数据不全

    is_long_trend_up = price > ma60
    is_before_cross = ma5 < ma20
    is_approaching = (ma20 - ma5) / ma20 < 0.02 # 差距小于2%

    if is_long_trend_up and is_before_cross and is_approaching:
        reason = f"即将金叉 (MA5:{ma5:.2f}, MA20:{ma20:.2f}) 且处于上升趋势 (Price:{price:.2f} > MA60:{ma60:.2f})"
        return True, reason
        
    return False, None


def update_candidate_pool():
    """
    执行"海选"，扫描所有股票，找出有潜力的候选者并存入数据库。
    此函数会自动创建并运行在它自己的Flask应用上下文中。
    """
    if not _current_app_instance:
        logger.error("无法获取Flask应用实例，候选股票池任务无法执行。")
        return

    app = _current_app_instance
    with app.app_context():
        logger.info("--- 开始执行候选股票池更新任务 ---")
        socketio.emit('job_status', {
            'job_name': 'candidate_pool',
            'status': 'started',
            'message': '开始执行候选股票池更新任务...'
        }, namespace='/scheduler')
        
        try:
            # 1. 清空旧的候选池
            num_deleted = db.session.query(CandidateStock).delete()
            logger.info(f"已清空旧的候选池，共删除 {num_deleted} 条记录。")

            # 2. 获取所有活跃的A股股票
            all_stocks = Stock.query.filter(Stock.is_active == True).all()
            total_stocks = len(all_stocks)
            if not all_stocks:
                logger.warning("数据库中没有活跃股票，任务提前结束。")
                socketio.emit('job_status', {
                    'job_name': 'candidate_pool', 'status': 'completed', 
                    'message': '数据库中没有活跃股票，任务结束。'
                }, namespace='/scheduler')
                return
            
            logger.info(f"将扫描 {total_stocks} 只活跃股票。")
            socketio.emit('job_progress', {
                'job_name': 'candidate_pool', 'progress': 0, 'total': total_stocks,
                'message': f'准备扫描 {total_stocks} 只股票...'
            }, namespace='/scheduler')

            new_candidates = []
            for i, stock in enumerate(all_stocks):
                # 每处理10只股票就通过websocket发送一次进度更新
                if (i + 1) % 10 == 0:
                    socketio.emit('job_progress', {
                        'job_name': 'candidate_pool',
                        'progress': i + 1,
                        'total': total_stocks,
                        'message': f'正在扫描: {stock.code} ({i+1}/{total_stocks})'
                    }, namespace='/scheduler')

                try:
                    # 获取足够计算指标的历史数据 - 从数据库读取
                    df = _get_history_from_db(stock.code, days_ago=100)
                    if df.empty or len(df) < 60:
                        continue

                    df_with_indicators = _calculate_indicators(df)
                    is_candidate, reason = _check_golden_cross_candidate(df_with_indicators)
                    
                    if is_candidate:
                        logger.info(f"发现候选股票: {stock.code} ({stock.name}) - 原因: {reason}")
                        candidate = CandidateStock(code=stock.code, name=stock.name, reason=reason)
                        new_candidates.append(candidate)

                except Exception as e:
                    logger.error(f"处理股票 {stock.code} 时出错: {e}", exc_info=False)
                    # 不再重新抛出异常，而是记录错误并继续处理下一只股票
                    # raise
            
            # 3. 批量插入新的候选者
            if new_candidates:
                db.session.add_all(new_candidates)
                db.session.commit()
                message = f"任务完成！成功将 {len(new_candidates)} 只股票添加到候选池。"
                logger.info(message)
                socketio.emit('job_status', {
                    'job_name': 'candidate_pool', 'status': 'completed', 'message': message
                }, namespace='/scheduler')
            else:
                db.session.commit() # 确保删除操作被提交
                message = "任务完成，本次扫描未发现新的候选股票。"
                logger.info(message)
                socketio.emit('job_status', {
                    'job_name': 'candidate_pool', 'status': 'completed', 'message': message
                }, namespace='/scheduler')

        except Exception as e:
            db.session.rollback()
            error_message = f"更新候选股票池任务发生严重错误: {e}"
            logger.error(error_message, exc_info=True)
            socketio.emit('job_status', {
                'job_name': 'candidate_pool', 'status': 'failed', 'message': str(e)
            }, namespace='/scheduler')

if __name__ == '__main__':
    # 允许直接运行此脚本进行测试
    # 注意：直接运行时需要一个有效的app context
    app = create_app()
    with app.app_context():
        update_candidate_pool() 