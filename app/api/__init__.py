from flask import Blueprint
from flask_restx import Api

# 创建蓝图
api_bp = Blueprint('api', __name__, url_prefix='/api')

# 创建API文档
api = Api(
    api_bp,
    version='1.0',
    title='Stock Scan API',
    description='A comprehensive API for stock analysis and backtesting.',
    doc='/doc'
)

# 导入命名空间
from .data_collection import ns as data_collection_ns
from .data_query import ns as data_query_ns
from .strategies import ns as strategies_ns
from .backtest import ns as backtest_ns
from .stocks import ns as stocks_ns
from .signals import ns as signals_ns
from .system_stats import ns as system_stats_ns
from .jobs import ns as jobs_ns
from .top_backtest import ns as top_backtest_ns
from .top_strategy_api import ns as top_strategy_ns
from .deepseek_api import deepseek_bp # 导入 DeepSeek API 蓝图

# 注册命名空间
api.add_namespace(data_collection_ns, path='/data-collection')
api.add_namespace(data_query_ns, path='/data-query')
api.add_namespace(strategies_ns, path='/strategies')
api.add_namespace(backtest_ns, path='/backtests')
api.add_namespace(stocks_ns, path='/stocks')
api.add_namespace(signals_ns, path='/signals')
api.add_namespace(system_stats_ns, path='/stats')
api.add_namespace(jobs_ns, path='/jobs')
api.add_namespace(top_backtest_ns, path='/backtests/top')
api.add_namespace(top_strategy_ns, path='/top-strategy')

def init_api(app):
    """初始化所有API蓝图"""
    from .scheduler_api import init_scheduler_api
    
    # 注册主 API 蓝图
    if 'api' not in app.blueprints:
        app.register_blueprint(api_bp)

    # 注册 DeepSeek API 蓝图
    if 'deepseek_api' not in app.blueprints:
        app.register_blueprint(deepseek_bp)
    
    # 初始化调度器API
    scheduler_bp = init_scheduler_api(app, app.scheduler)
    
    return app 