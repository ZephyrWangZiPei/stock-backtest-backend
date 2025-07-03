# Stock Scan Backend

> 股票推荐与回测系统后端服务

基于 Flask + SQLAlchemy 构建的高性能股票分析后端API服务，提供数据采集、策略回测、实时行情推送等核心功能。

## ✨ 功能特性

- 🔄 **数据采集系统**: 自动化采集A股/ETF基础信息和历史行情数据
- 🧠 **策略回测引擎**: 可插拔的交易策略回测框架
- 📡 **实时行情推送**: WebSocket实时数据推送服务
- 📊 **技术指标计算**: 内置多种技术指标算法
- 🗄️ **数据管理**: 完整的数据存储和查询API
- 📝 **交互式文档**: Swagger UI自动生成的API文档
- ⚡ **异步任务**: Celery分布式任务队列
- 🔐 **数据安全**: 数据库连接池和事务管理

## 🛠️ 技术栈

### 核心框架
- **Flask 3.0.3**: 轻量级Web应用框架
- **Flask-RESTX 1.3.0**: RESTful API框架 + Swagger文档
- **SQLAlchemy 2.0.41**: Python SQL工具包和ORM
- **Flask-Migrate 4.0.7**: 数据库迁移工具

### 数据库 & 缓存
- **MySQL**: 主数据库 (通过PyMySQL连接)
- **Redis 5.0.1**: 缓存和实时数据存储

### 数据处理
- **Pandas 2.2.2**: 数据分析和处理
- **NumPy 1.26.4**: 数值计算
- **pandas-ta 0.3.14b0**: 技术指标计算库

### 数据源
- **BaoStock 0.8.9**: 免费开源证券数据接口
- **Tushare**: 财经数据接口 (备用)

### 实时通信
- **Flask-SocketIO 5.3.6**: WebSocket实时通信
- **eventlet 0.35.2**: 异步网络库

### 任务调度
- **Celery 5.3.6**: 分布式任务队列
- **APScheduler 3.10.4**: 定时任务调度器

### 部署工具
- **Gunicorn 21.2.0**: WSGI HTTP服务器
- **Uvicorn 0.30.1**: ASGI服务器

## 📁 项目结构

```
backend/
├── app/                    # 应用核心模块
│   ├── __init__.py        # 应用工厂和配置
│   ├── commands.py        # Flask CLI命令
│   ├── api/               # REST API接口
│   │   ├── stocks.py      # 股票信息API
│   │   ├── backtest.py    # 回测API
│   │   ├── strategies.py  # 策略管理API
│   │   ├── data_collection.py  # 数据采集API
│   │   ├── realtime.py    # 实时行情API
│   │   ├── watchlist.py   # 自选股API
│   │   └── scheduler_api.py    # 任务调度API
│   ├── models/            # 数据模型
│   │   ├── stock.py       # 股票模型
│   │   ├── strategy.py    # 策略模型
│   │   ├── backtest.py    # 回测结果模型
│   │   └── ...
│   ├── strategies/        # 交易策略
│   │   ├── base_strategy.py        # 策略基类
│   │   ├── dual_moving_average.py  # 双均线策略
│   │   ├── macd_strategy.py        # MACD策略
│   │   └── rsi_strategy.py         # RSI策略
│   ├── backtester/        # 回测引擎
│   ├── data_collector/    # 数据采集模块
│   ├── scheduler/         # 任务调度模块
│   └── websocket/         # WebSocket处理
├── migrations/            # 数据库迁移文件
├── config.py             # 配置文件
├── run.py                # 应用启动入口
├── manage.py             # 管理脚本
└── requirements.txt      # Python依赖包
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- MySQL 5.7+ / 8.0+
- Redis 6.0+

### 1. 克隆项目

```bash
git clone <repository-url>
cd stock-scan/backend
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 环境配置

创建 `.env` 文件：

```env
# 数据库配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DB=stock_scan

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Flask配置
SECRET_KEY=your-secret-key-change-in-production
FLASK_ENV=development
FLASK_DEBUG=true

# 数据源配置
TUSHARE_TOKEN=your_tushare_token
```

### 5. 初始化数据库

```bash
# 初始化迁移
flask db init

# 创建迁移文件
flask db migrate -m "Initial migration"

# 执行迁移
flask db upgrade

# 初始化策略数据
flask seed-db
```

### 6. 启动服务

```bash
# 开发模式
python run.py

# 或使用Flask命令
flask run --host=0.0.0.0 --port=5000
```

服务将运行在 `http://localhost:5000`

### 7. 数据采集 (首次运行必需)

```bash
# 采集股票基础信息
flask collect-stocks

# 采集历史数据 (耗时较长，建议后台运行)
flask collect-history

# 或使用API接口
curl -X POST http://localhost:5000/api/data-collection/stocks
curl -X POST http://localhost:5000/api/data-collection/history
```

## 📚 API 文档

### Swagger UI

访问 `http://localhost:5000/api/doc` 查看完整的交互式API文档。

### 主要API端点

| 模块 | 端点 | 描述 |
|------|------|------|
| **股票信息** | `GET /api/stocks` | 获取股票列表 |
| | `GET /api/stocks/{code}` | 获取单只股票信息 |
| | `GET /api/stocks/{code}/daily` | 获取股票历史数据 |
| **策略管理** | `GET /api/strategies` | 获取策略列表 |
| | `GET /api/strategies/{id}` | 获取策略详情 |
| **回测系统** | `POST /api/backtests` | 创建回测任务 |
| | `GET /api/backtests/{id}` | 获取回测结果 |
| **数据采集** | `POST /api/data-collection/stocks` | 触发股票信息采集 |
| | `POST /api/data-collection/history` | 触发历史数据采集 |
| **实时行情** | `GET /api/realtime/{code}` | 获取实时股价 |
| **自选股** | `GET /api/watchlist` | 获取自选股列表 |
| | `POST /api/watchlist` | 添加自选股 |

### WebSocket 事件

```python
# 连接到WebSocket
ws://localhost:5000/socket.io/

# 监听实时数据
socket.on('realtime_data', function(data) {
    console.log('实时数据:', data);
});

# 订阅股票
socket.emit('subscribe', {codes: ['000001.SZ', '000002.SZ']});
```

## 🔧 开发指南

### 添加新的交易策略

1. 在 `app/strategies/` 目录创建新策略文件：

```python
# app/strategies/your_strategy.py
from .base_strategy import BaseStrategy
import pandas as pd

class YourStrategy(BaseStrategy):
    @classmethod
    def get_identifier(cls):
        return 'your_strategy'
    
    @classmethod
    def get_name(cls):
        return '您的策略名称'
    
    @classmethod
    def get_description(cls):
        return '策略描述'
    
    @classmethod
    def get_parameters(cls):
        return {
            'param1': {'type': 'int', 'default': 10, 'description': '参数1描述'},
            'param2': {'type': 'float', 'default': 0.05, 'description': '参数2描述'}
        }
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        # 实现策略逻辑
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0  # 0=持有, 1=买入, -1=卖出
        
        # 您的策略逻辑
        # ...
        
        return signals
```

2. 在 `app/strategies/__init__.py` 中注册策略：

```python
from .your_strategy import YourStrategy

STRATEGY_MAP = {
    # ... 现有策略
    YourStrategy.get_identifier(): YourStrategy,
}
```

3. 同步策略到数据库：

```bash
flask seed-db
```

### 添加新的API端点

```python
# app/api/your_module.py
from flask_restx import Namespace, Resource, fields

ns = Namespace('your_module', description='模块描述')

@ns.route('/endpoint')
class YourResource(Resource):
    @ns.doc('操作描述')
    def get(self):
        """获取数据"""
        return {'message': 'success'}
    
    @ns.doc('创建数据')
    @ns.expect(your_model)
    def post(self):
        """创建数据"""
        return {'message': 'created'}, 201
```

### 数据库模型

```python
# app/models/your_model.py
from app import db
from datetime import datetime

class YourModel(db.Model):
    __tablename__ = 'your_table'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat()
        }
```

## 🗃️ 数据库管理

### 常用迁移命令

```bash
# 创建新迁移
flask db migrate -m "描述信息"

# 执行迁移
flask db upgrade

# 回滚迁移
flask db downgrade

# 查看迁移历史
flask db history

# 查看当前版本
flask db current
```

### 数据库命令

```bash
# 重新创建数据库表
flask recreate-db

# 初始化数据库
flask init-db

# 更新股票列表
flask update-stock-list

# 计算技术指标
flask calculate-indicators
```

## 📊 性能优化

### 数据库优化

```python
# 连接池配置 (config.py)
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,          # 连接池大小
    'pool_timeout': 20,       # 连接超时
    'pool_recycle': -1,       # 连接回收时间
    'pool_pre_ping': True     # 连接预检查
}
```

### 缓存策略

```python
# 使用Redis缓存
import redis
from flask import current_app

redis_client = redis.Redis(
    host=current_app.config['REDIS_HOST'],
    port=current_app.config['REDIS_PORT'],
    db=current_app.config['REDIS_DB']
)

# 缓存股票数据
def get_stock_data(code):
    cache_key = f"stock:{code}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 从数据库获取数据
    data = fetch_from_db(code)
    redis_client.setex(cache_key, 3600, json.dumps(data))
    return data
```

## 🚀 部署指南

### 生产环境配置

```bash
# 使用Gunicorn部署
gunicorn -w 4 -b 0.0.0.0:5000 --worker-class eventlet run:app

# 使用Supervisor进程管理
# /etc/supervisor/conf.d/stock-scan.conf
[program:stock-scan]
command=/path/to/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 run:app
directory=/path/to/stock-scan/backend
user=www-data
autostart=true
autorestart=true
```

### Docker部署

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "run:app"]
```

### Nginx配置

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 🧪 测试

### 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-cov

# 运行测试
pytest

# 生成覆盖率报告
pytest --cov=app tests/
```

### API测试示例

```python
# tests/test_api.py
def test_get_stocks(client):
    response = client.get('/api/stocks')
    assert response.status_code == 200
    assert 'data' in response.json

def test_create_backtest(client):
    data = {
        'strategy_id': 1,
        'stock_codes': ['000001.SZ'],
        'start_date': '2023-01-01',
        'end_date': '2023-12-31',
        'initial_capital': 100000
    }
    response = client.post('/api/backtests', json=data)
    assert response.status_code == 201
```

## 🔍 监控与日志

### 日志配置

```python
# 日志配置 (run.py)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
```

### 性能监控

```python
# 添加请求监控
@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request
def after_request(response):
    duration = time.time() - g.start_time
    app.logger.info(f"Request: {request.method} {request.path} - {response.status_code} - {duration:.3f}s")
    return response
```

## 🚧 待开发功能

- [ ] 更多技术指标策略 (KDJ, BOLL等)
- [ ] 多因子模型支持
- [ ] 实时风险监控
- [ ] 策略组合优化
- [ ] 机器学习预测模型
- [ ] 分布式回测支持
- [ ] API限流和认证
- [ ] 数据质量监控

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支: `git checkout -b feature/new-feature`
3. 提交更改: `git commit -am 'Add new feature'`
4. 推送分支: `git push origin feature/new-feature`
5. 提交 Pull Request

### 代码规范

- 遵循 PEP 8 Python编码规范
- 添加适当的文档字符串
- 编写单元测试
- 使用类型注解

## 📄 许可证

MIT License

---

## 🔗 相关链接

- [Flask 文档](https://flask.palletsprojects.com/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [Flask-RESTX 文档](https://flask-restx.readthedocs.io/)
- [BaoStock 文档](http://baostock.com/)
- [Pandas 文档](https://pandas.pydata.org/)
- [Redis 文档](https://redis.io/documentation)

## 💬 技术支持

如有问题或建议，请提交 Issue 或联系开发团队。

### 常见问题

**Q: 数据采集失败怎么办？**
A: 检查网络连接和BaoStock服务状态，确保数据库连接正常。

**Q: 回测结果不准确？**
A: 确认历史数据完整性，检查策略参数配置是否正确。

**Q: WebSocket连接失败？**
A: 检查防火墙设置和端口是否被占用，确认eventlet正确安装。 