from flask_socketio import emit, join_room, leave_room
import logging

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
    
    @socketio.on('leave_stock')
    def handle_leave_stock(data):
        """离开股票实时数据房间"""
        stock_code = data.get('stock_code')
        if stock_code:
            leave_room(f'stock_{stock_code}')
            emit('status', {'message': f'已离开股票 {stock_code} 实时数据'})
            logger.info(f'客户端离开股票 {stock_code} 房间')
    
    @socketio.on('join_collection')
    def handle_join_collection():
        """加入数据采集状态房间"""
        join_room('data_collection')
        emit('status', {'message': '已加入数据采集状态监听'})
        logger.info('客户端加入数据采集房间') 