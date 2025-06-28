from flask import request
from flask_restx import Namespace, Resource, fields
from app.data_collector import DataCollector
import threading
from app import create_app  # 导入 create_app

ns = Namespace('data', description='数据采集接口')

# 定义响应模型
collection_response_model = ns.model('CollectionResponse', {
    'success': fields.Boolean(description='是否成功'),
    'message': fields.String(description='响应消息'),
    'data': fields.Raw(description='返回数据')
})

# 全局变量用于跟踪采集状态
collection_status = {
    'is_running': False,
    'current_task': None,
    'progress': 0,
    'total': 0,
    'message': ''
}

def create_task_app():
    """为后台任务创建一个独立的应用实例"""
    app = create_app(config_name='development')
    return app

@ns.route('/collect/stocks')
class CollectStocks(Resource):
    @ns.doc('采集股票基础信息')
    @ns.marshal_with(collection_response_model)
    def post(self):
        """采集所有股票基础信息"""
        global collection_status
        
        if collection_status['is_running']:
            return {
                'success': False,
                'message': '数据采集正在进行中，请稍后再试',
                'data': collection_status
            }, 400
        
        def collect_task():
            global collection_status
            app = create_task_app()
            with app.app_context():
                collection_status['is_running'] = True
                collection_status['current_task'] = 'collecting_stocks'
                collection_status['message'] = '正在采集股票基础信息...'
                
                try:
                    collector = DataCollector()
                    result = collector.collect_all_stocks()
                    
                    collection_status['message'] = f'采集完成: 成功 {result["success"]}, 失败 {result["error"]}'
                    collection_status['progress'] = result['success']
                    collection_status['total'] = result['total']
                    
                except Exception as e:
                    collection_status['message'] = f'采集失败: {str(e)}'
                finally:
                    collection_status['is_running'] = False
                    collection_status['current_task'] = None
        
        # 启动后台任务
        thread = threading.Thread(target=collect_task)
        thread.daemon = True
        thread.start()
        
        return {
            'success': True,
            'message': '数据采集任务已启动',
            'data': collection_status
        }

@ns.route('/collect/status')
class CollectionStatus(Resource):
    @ns.doc('获取采集状态')
    @ns.marshal_with(collection_response_model)
    def get(self):
        """获取当前数据采集状态"""
        return {
            'success': True,
            'message': '获取状态成功',
            'data': collection_status
        }

@ns.route('/collect/history')
class CollectHistory(Resource):
    @ns.doc('采集所有股票的历史数据')
    @ns.marshal_with(collection_response_model)
    def post(self):
        """采集所有股票近3年的日线历史数据"""
        global collection_status
        
        if collection_status['is_running']:
            return {
                'success': False,
                'message': '数据采集正在进行中，请稍后再试',
                'data': collection_status
            }, 400
        
        def collect_task():
            global collection_status
            app = create_task_app()
            with app.app_context():
                collection_status['is_running'] = True
                collection_status['current_task'] = 'collecting_history'
                collection_status['progress'] = 0
                
                try:
                    collector = DataCollector()
                    
                    # 先获取总数用于进度条
                    from app.models import Stock
                    total_stocks = Stock.query.filter(Stock.is_active == True).count()
                    collection_status['total'] = total_stocks
                    collection_status['message'] = f'准备采集 {total_stocks} 支股票的历史数据...'

                    def progress_update():
                        collection_status['progress'] += 1
                        collection_status['message'] = f"正在处理: {collection_status['progress']}/{collection_status['total']}"

                    result = collector.collect_historical_data(progress_callback=progress_update)
                    
                    collection_status['message'] = f'历史数据采集完成: 成功 {result["success"]}, 失败 {result["error"]}'
                    
                except Exception as e:
                    collection_status['message'] = f'采集失败: {str(e)}'
                finally:
                    collection_status['is_running'] = False
                    collection_status['current_task'] = None
        
        thread = threading.Thread(target=collect_task)
        thread.daemon = True
        thread.start()
        
        return {
            'success': True,
            'message': '历史数据采集任务已启动',
            'data': collection_status
        }

@ns.route('/initialize/tushare')
class InitializeDatabase(Resource):
    @ns.doc('使用Tushare全量初始化数据库')
    @ns.marshal_with(collection_response_model)
    def post(self):
        """
        清空并使用Tushare数据重新填充整个数据库。
        这是一个非常耗时的操作，请谨慎使用。
        """
        global collection_status
        
        if collection_status['is_running']:
            return {'success': False, 'message': '任务正在进行中'}, 400

        def task():
            global collection_status
            app = create_task_app()
            with app.app_context():
                collection_status['is_running'] = True
                collection_status['current_task'] = 'tushare_initialize'
                collection_status['progress'] = 0
                collection_status['total'] = 0
                collection_status['message'] = 'Tushare数据库初始化任务开始...'

                def progress_update(current, total):
                    collection_status['progress'] = current
                    collection_status['total'] = total
                    collection_status['message'] = f"正在处理: {current}/{total}"

                try:
                    collector = DataCollector()
                    result = collector.initialize_database_with_tushare(progress_callback=progress_update)
                    collection_status['message'] = f"初始化完成: 成功 {result['success']}, 失败 {result['error']}"
                except Exception as e:
                    collection_status['message'] = f"初始化失败: {e}"
                finally:
                    collection_status['is_running'] = False
                    collection_status['current_task'] = None

        thread = threading.Thread(target=task)
        thread.daemon = True
        thread.start()

        return {'success': True, 'message': 'Tushare数据库初始化任务已启动'}

@ns.route('/initialize/baostock')
class InitializeWithBaostock(Resource):
    @ns.doc('使用BaoStock全量初始化数据库 (推荐)')
    @ns.marshal_with(collection_response_model)
    def post(self):
        """
        (推荐) 使用BaoStock清空并重新填充数据库。稳定、免费。
        这是一个非常耗时的操作，请谨慎使用。
        """
        global collection_status
        
        if collection_status['is_running']:
            return {'success': False, 'message': '任务正在进行中'}, 400

        def task():
            global collection_status
            app = create_task_app()
            with app.app_context():
                collection_status['is_running'] = True
                collection_status['current_task'] = 'baostock_initialize'
                collection_status['message'] = 'BaoStock数据库初始化任务开始...'

                def progress_update(current, total):
                    collection_status['progress'] = current
                    collection_status['total'] = total
                    collection_status['message'] = f"BaoStock处理中: {current}/{total}"

                try:
                    collector = DataCollector()
                    result = collector.initialize_with_baostock(progress_callback=progress_update)
                    collection_status['message'] = f"BaoStock初始化完成: 成功 {result['success']}, 失败 {result['error']}"
                except Exception as e:
                    collection_status['message'] = f"BaoStock初始化失败: {e}"
                finally:
                    collection_status['is_running'] = False
                    collection_status['current_task'] = None

        thread = threading.Thread(target=task)
        thread.daemon = True
        thread.start()

        return {'success': True, 'message': 'BaoStock数据库初始化任务已启动'} 