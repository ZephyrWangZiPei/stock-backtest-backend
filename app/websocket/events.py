from flask_socketio import emit, join_room, leave_room
import logging
from datetime import datetime
from app.api.realtime import _fetch_realtime_data
from app.data_collector.baostock_client import BaostockClient

logger = logging.getLogger(__name__)

def register_socketio_events(socketio):
    """注册WebSocket事件"""
    
    @socketio.on('connect')
    def handle_connect():
        logger.info('客户端连接')
        emit('status', {'message': '连接成功'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info('客户端断开连接')
    
    @socketio.on('join_stock')
    def handle_join_stock(data):
        """加入股票实时数据房间"""
        stock_code = data.get('stock_code')
        if stock_code:
            join_room(f'stock_{stock_code}')
            emit('status', {'message': f'已加入股票 {stock_code} 实时数据'})
            logger.info(f'客户端加入股票 {stock_code} 房间')
            
            # 立即发送一次实时数据
            try:
                realtime_data = _fetch_realtime_data(stock_code)
                if 'error' not in realtime_data:
                    emit('realtime_data', {
                        'stock_code': stock_code,
                        'data': realtime_data,
                        'timestamp': datetime.now().isoformat()
                    })
            except Exception as e:
                logger.error(f'发送实时数据失败: {e}')
    
    @socketio.on('leave_stock')
    def handle_leave_stock(data):
        """离开股票实时数据房间"""
        stock_code = data.get('stock_code')
        if stock_code:
            leave_room(f'stock_{stock_code}')
            emit('status', {'message': f'已离开股票 {stock_code} 实时数据'})
            logger.info(f'客户端离开股票 {stock_code} 房间')
    
    @socketio.on('join_watchlist')
    def handle_join_watchlist(data):
        """加入自选股房间，接收批量实时数据"""
        stock_codes = data.get('stock_codes', [])
        if stock_codes:
            join_room('watchlist')
            emit('status', {'message': f'已加入自选股监听，共 {len(stock_codes)} 只股票'})
            logger.info(f'客户端加入自选股房间，监听 {len(stock_codes)} 只股票')
            
            # 立即发送一次批量实时数据
            try:
                batch_data = {}
                for code in stock_codes[:20]:  # 限制最多20只股票
                    realtime_data = _fetch_realtime_data(code)
                    if 'error' not in realtime_data:
                        batch_data[code] = realtime_data
                
                if batch_data:
                    emit('watchlist_data', {
                        'data': batch_data,
                        'timestamp': datetime.now().isoformat()
                    })
            except Exception as e:
                logger.error(f'发送自选股数据失败: {e}')
    
    @socketio.on('leave_watchlist')
    def handle_leave_watchlist():
        """离开自选股房间"""
        leave_room('watchlist')
        emit('status', {'message': '已离开自选股监听'})
        logger.info('客户端离开自选股房间')
    
    @socketio.on('join_collection')
    def handle_join_collection():
        """加入数据采集状态房间"""
        join_room('data_collection')
        emit('status', {'message': '已加入数据采集状态监听'})
        logger.info('客户端加入数据采集房间')
    
    @socketio.on('request_market_summary')
    def handle_request_market_summary():
        """请求市场概况数据"""
        logger.info("收到来自 WebSocket 的市场概况数据请求。")
        try:
            from app.api.realtime import _fetch_realtime_data
            
            # 获取主要指数数据
            major_indices = ['sh.000001', 'sz.399001', 'sz.399006']
            summary_data = []
            
            # 使用单个客户端会话处理所有指数
            with BaostockClient() as client:
                for index_code in major_indices:
                    try:
                        data = _fetch_realtime_data(index_code, baostock_client=client)
                        if 'error' not in data:
                            index_name = {
                                'sh.000001': '上证指数',
                                'sz.399001': '深证成指', 
                                'sz.399006': '创业板指'
                            }.get(index_code, index_code)
                            
                            summary_data.append({
                                'name': index_name,
                                'code': index_code,
                                'current_price': data.get('current_price'),
                                'change_amount': data.get('change_amount'),
                                'change_rate': data.get('change_rate')
                            })
                    except Exception as e:
                        logger.warning(f"获取指数 {index_code} 数据失败: {e}")
                        continue
            
            logger.info(f"成功获取 {len(summary_data)} 个指数的市场概况，准备通过 WebSocket 发送。")
            emit('market_summary', {
                'indices': summary_data,
                'update_time': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f'获取市场概况失败: {e}')
            emit('error', {'message': '获取市场概况失败'})

def broadcast_realtime_data(socketio, stock_codes=None):
    """
    广播实时数据到相关房间
    这个函数可以被定时任务调用
    """
    if not stock_codes:
        # 如果没有指定股票代码，可以从活跃房间或数据库获取
        return
    
    try:
        batch_data = {}
        for code in stock_codes:
            try:
                realtime_data = _fetch_realtime_data(code)
                if 'error' not in realtime_data:
                    batch_data[code] = realtime_data
                    
                    # 发送到单独的股票房间
                    socketio.emit('realtime_data', {
                        'stock_code': code,
                        'data': realtime_data,
                        'timestamp': datetime.now().isoformat()
                    }, room=f'stock_{code}')
                    
            except Exception as e:
                logger.error(f'获取股票 {code} 实时数据失败: {e}')
        
        # 发送批量数据到自选股房间
        if batch_data:
            socketio.emit('watchlist_data', {
                'data': batch_data,
                'timestamp': datetime.now().isoformat()
            }, room='watchlist')
            
        logger.info(f'已广播 {len(batch_data)} 只股票的实时数据')
        
    except Exception as e:
        logger.error(f'广播实时数据失败: {e}') 