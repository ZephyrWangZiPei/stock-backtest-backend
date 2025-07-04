from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_restx import Api
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_migrate import Migrate
import logging
from logging.handlers import RotatingFileHandler
import os
import redis
from app.services.deepseek_service import DeepSeekService

# 初始化扩展
db = SQLAlchemy()
socketio = SocketIO()
migrate = Migrate()
redis_client = None
deepseek_service = None

# 全局应用实例，供调度任务使用
_current_app_instance = None

def create_app(config_name=None):
    global _current_app_instance
    
    app = Flask(__name__)
    
    # 配置
    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'development')
    
    # 导入配置
    from config import Config, DevelopmentConfig, ProductionConfig
    config_map = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'default': DevelopmentConfig
    }
    app.config.from_object(config_map.get(config_name, DevelopmentConfig))
    
    # 设置日志
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/stock-scan.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Stock-Scan startup')
    
    # 设置全局应用实例
    _current_app_instance = app
    
    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    socketio.init_app(app, 
                     cors_allowed_origins="*",
                     async_mode='threading',
                     logger=True,
                     engineio_logger=True)
    
    # 初始化Redis
    global redis_client, deepseek_service
    redis_client = redis.Redis(
        host=app.config['REDIS_HOST'],
        port=app.config['REDIS_PORT'],
        db=app.config['REDIS_DB'],
        decode_responses=True
    )

    # 初始化DeepSeekService
    deepseek_api_key = app.config.get('DEEPSEEK_API_KEY')
    deepseek_service = DeepSeekService(api_key=deepseek_api_key)
    app.deepseek_service = deepseek_service
    
    # 初始化调度器
    from app.scheduler import TaskScheduler
    scheduler = TaskScheduler()
    scheduler.init_app(app)
    scheduler.init_socketio(socketio)
    app.scheduler = scheduler  # 将调度器添加到应用实例
    
    # 注册蓝图
    from app.api import init_api
    init_api(app)
    
    # 注册自定义命令行
    from .commands import register_commands
    register_commands(app)
    
    # 启动调度器（保证持久化任务被加载并且核心任务存在）
    scheduler.start()
    
    # 注册WebSocket断开连接事件处理器
    @socketio.on('disconnect', namespace='/scheduler')
    def handle_scheduler_disconnect():
        app.logger.info('Scheduler client disconnected')
    
    return app 