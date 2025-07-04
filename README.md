# Stock Scan Backend

> 股票推荐与回测系统后端服务

基于 Python Flask 框架，结合 SQLAlchemy ORM 构建的高性能后端API服务，旨在为股票分析与交易策略回测提供坚实的数据和逻辑支持。它集成了数据采集、策略回测引擎、实时行情推送、技术指标计算、数据管理以及交互式API文档等核心功能。

## 🚨 重要提醒：防止重复回测

### 问题描述
在Top回测功能中，存在两个不同的API端点可能导致重复执行：

1. **推荐使用（异步）**: `/api/jobs/run/top_strategy_backtest`
   - 包含DeepSeek AI分析
   - 异步执行，有进度提示
   - 结果保存到数据库
   - 包含防重复执行机制

2. **已废弃（同步）**: `/api/backtests/top/`
   - 不包含AI分析
   - 同步执行，可能超时
   - 只返回结果，不保存

### 解决方案
- ✅ 已添加防重复执行机制
- ✅ 已标记废弃API并添加警告
- ✅ 前端使用推荐的异步API
- ✅ 添加任务状态检查

### 使用建议
- 始终使用异步API: `POST /api/jobs/run/top_strategy_backtest`
- 避免在任务运行期间重复点击
- 通过WebSocket监控任务进度
- 如遇到重复执行，检查是否同时调用了两个API

## ✨ 功能特性

-   🔄 **数据采集系统**: 自动化、定期地从主流财经数据源（如 BaoStock、Tushare）采集A股、ETF等金融产品的基本信息和详尽的历史行情数据，确保数据的新鲜度和完整性。
-   🧠 **策略回测引擎**: 提供一个灵活、可扩展的交易策略回测框架。开发者可以轻松接入自定义的交易策略，并对历史数据进行模拟回测，评估策略在不同市场条件下的表现，支持多种性能指标计算。
-   📡 **实时状态推送**: 利用 WebSocket 技术实现应用内部状态（如回测任务进度、数据采集状态、调度器状态）的低延迟推送，确保前后端数据的实时同步。此模块为**未来的实时行情数据推送奠定了技术基础**。
-   📊 **技术指标计算**: 内置丰富的技术分析指标（如MACD、RSI、均线等）计算模块，可以直接应用于历史或实时行情数据，为策略开发和图表展示提供支持。
-   🗄️ **数据管理**: 提供一套完整的RESTful API接口，用于对股票基础信息、历史数据、策略定义、回测结果、用户自选股等数据进行存储、查询、更新和删除操作。
-   🤖 **AI 智能分析**: 集成 DeepSeek 大语言模型，提供智能股票分析和推荐服务。支持文本分析（如新闻、财报）、股票走势分析、以及基于历史回测数据的潜力股票推荐，为投资决策提供AI辅助建议。
-   📝 **交互式文档**: 集成 Swagger UI (通过 Flask-RESTX 实现)，自动生成并提供可视化的API文档。开发者和前端工程师可以方便地浏览所有可用API端点、请求参数、响应结构，并直接进行API测试。
-   ⚡ **后台任务处理**: 利用 Python threading 和 APScheduler 任务调度器处理耗时操作，如大规模历史数据采集、定时数据更新等，避免阻塞主应用进程，提升系统响应速度和用户体验。
-   🔐 **数据安全**: 采用 SQLAlchemy ORM 进行数据库操作，有效防范SQL注入。同时，通过连接池管理和事务机制，确保数据操作的原子性、一致性和并发安全性。

## 🛠️ 技术栈

本项目基于以下主要技术栈构建，旨在提供高性能、可扩展的后端服务：

### 核心框架

-   **Flask `3.0.3`**: 轻量级且高度灵活的 Python Web 应用框架，用于构建RESTful API。
-   **Flask-RESTX `1.3.0`**: Flask 的扩展，用于快速构建RESTful API，并自动生成符合 OpenAPI 规范的交互式文档（Swagger UI）。
-   **SQLAlchemy `2.0.41`**: 强大的 Python SQL 工具包和对象关系映射 (ORM) 库，用于与数据库进行高效、类型安全的数据交互。
-   **Flask-Migrate `4.0.7`**: 基于 Alembic 的 Flask 扩展，用于管理数据库模式的创建和版本迁移。

### 数据库与缓存

-   **MySQL**: 项目的主数据库，用于持久化存储股票基础信息、历史行情、策略数据、回测结果等核心业务数据。通过 `PyMySQL` 进行连接。
-   **Redis `5.0.1`**: 高性能的内存数据结构存储，主要用作应用缓存和 WebSocket 消息缓存。

### 数据处理与分析

-   **Pandas `2.2.2`**: 领先的 Python 数据分析库，提供高性能、易用的数据结构（DataFrame）和数据分析工具，广泛应用于数据清洗、转换和指标计算。
-   **NumPy `1.26.4`**: Python 科学计算的基础库，提供高性能的多维数组对象和相关工具，为 Pandas 和其他数值计算库提供底层支持。
-   **pandas-ta `0.3.14b0`**: 一个易于使用的 Pandas 技术分析扩展库，集成了数百种常见的技术指标，便于在回测和实时分析中应用。

### 数据源集成

-   **BaoStock `0.8.9`**: 一个免费开源的证券数据接口，提供便捷的方式获取股票历史数据、财务数据等。
-   **Tushare**: 另一个强大的财经数据接口，提供更全面的金融数据服务，作为 BaoStock 的备用或补充数据源。

### AI 服务集成

-   **DeepSeek API**: 集成 DeepSeek 大语言模型，提供智能股票分析和推荐服务。通过自然语言处理技术，对股票的技术指标、历史表现等进行深度分析，为投资决策提供AI辅助建议。
-   **OpenAI**: 项目中集成了 OpenAI API 支持，可用于文本分析和智能推荐等功能。

### 实时通信

-   **Flask-SocketIO `5.3.6`**: Flask 的 Socket.IO 集成，用于构建 WebSocket 服务器，实现客户端与服务器之间的实时双向通信，主要用于行情数据推送。
-   **eventlet `0.35.2`**: 一个并发网络库，为 Flask-SocketIO 提供异步支持，使其能够处理高并发的 WebSocket 连接。

### 任务调度与后台处理

-   **APScheduler `3.10.4`**: 一个轻量级但功能强大的 Python 任务调度库，支持多种调度方式，用于定期执行如每日数据更新、股票列表更新、数据清理等任务。
-   **Python Threading**: 使用 Python 标准库的 threading 模块处理后台长时间运行的任务，如数据采集、复杂回测计算等。

### 部署工具

-   **Gunicorn `21.2.0`**: 一个 UNIX 下的 WSGI HTTP 服务器，适用于部署 Flask 应用到生产环境。
-   **Uvicorn `0.30.1`**: 一个快速的 ASGI 服务器，与 Gunicorn 结合使用，可以更好地支持异步应用，尤其在与 Flask-SocketIO 结合时性能更优。

## 📁 项目结构

```
stock-backtest-backend/
├── app/                            # 应用的核心模块，包含蓝图、模型、API接口、业务逻辑等
│   ├── __init__.py                # 应用工厂函数和基本配置，初始化 Flask 应用
│   ├── commands.py                # 自定义 Flask CLI 命令，例如数据采集、数据库初始化等
│   ├── api/                       # RESTful API 蓝图和资源定义，每个文件代表一个业务模块的API
│   │   ├── stocks.py              # 股票基础信息和历史行情API
│   │   ├── backtest.py            # 策略回测任务创建、查询和结果API
│   │   ├── strategies.py          # 交易策略的增删改查API
│   │   ├── data_collection.py     # 数据采集任务触发和状态查询API
│   │   ├── deepseek_api.py        # DeepSeek AI分析接口API
│   │   ├── watchlist.py           # 用户自选股管理API
│   │   └── scheduler_api.py       # 异步任务调度管理API
│   ├── models/                    # SQLAlchemy 数据模型定义，映射数据库表结构
│   │   ├── stock.py               # 股票相关数据模型
│   │   ├── strategy.py            # 交易策略定义模型
│   │   ├── backtest.py            # 回测任务及结果模型
│   │   ├── top_strategy_stock.py  # AI推荐的潜力股票模型
│   │   └── ...                    # 其他数据模型文件
│   ├── strategies/                # 交易策略实现，每个文件是一个具体的策略类
│   │   ├── base_strategy.py       # 策略基类，定义策略通用接口
│   │   ├── dual_moving_average.py # 双均线策略示例
│   │   ├── macd_strategy.py       # MACD 策略示例
│   │   └── rsi_strategy.py        # RSI 策略示例
│   ├── services/                  # 业务服务层，封装复杂的业务逻辑
│   │   ├── deepseek_service.py    # DeepSeek AI服务封装
│   │   └── ...                    # 其他服务文件
│   ├── backtester/                # 策略回测引擎的实现逻辑
│   ├── data_collector/            # 股票数据采集的具体实现，与数据源交互
│   ├── scheduler/                 # 异步任务调度器配置和任务定义
│   └── websocket/                 # WebSocket 事件处理和消息广播逻辑
├── migrations/                     # Alembic 数据库迁移脚本目录
├── config.py                       # 项目配置，包含开发、测试、生产环境配置
├── run.py                          # 应用的启动入口脚本 (开发模式)
├── manage.py                       # Flask-Migrate 和其他自定义管理命令的入口
├── requirements.txt                # Python 项目依赖包列表
└── .flaskenv                       # Flask 环境变量配置，用于开发环境
```

## 🚀 快速开始

### 环境要求

在部署和运行后端服务之前，请确保您的系统满足以下最低要求：

-   **Python**: `3.10+` 版本
-   **MySQL**: `5.7+` 或 `8.0+` 版本数据库服务
-   **Redis**: `6.0+` 版本服务

### 1. 克隆项目

首先，将项目仓库克隆到本地：

```bash
git clone https://github.com/your-repo/stock-scan.git # 替换为您的实际仓库地址
cd stock-scan/stock-backtest-backend
```

### 2. 创建并激活虚拟环境

强烈推荐使用 Python 虚拟环境来管理项目依赖，以避免与系统或其他项目产生冲突：

```bash
# 对于 Windows 用户
python -m venv venv
.\venv\Scripts\activate

# 对于 macOS/Linux 用户
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

激活虚拟环境后，安装 `requirements.txt` 中列出的所有 Python 依赖包：

```bash
pip install -r requirements.txt
```

### 4. 环境配置

在项目根目录 (`stock-backtest-backend/`) 下创建 `.env` 文件，并根据您的实际环境配置以下变量：

**重要提示**: 
- 为了避免敏感信息（如数据库密码、API密钥）被意外提交到版本控制系统，请确保 `.env` 文件已添加到 `.gitignore` 中。
- 建议创建 `.env.example` 文件作为配置模板，其中包含所有必需的环境变量名称但不包含实际值。

```env
# 数据库连接配置 (MySQL)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password # 替换为您的MySQL密码
MYSQL_DB=stock_scan_db            # 替换为您的数据库名称

# Redis 连接配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Flask 应用配置
SECRET_KEY=super-secret-key-please-change-in-production # 生产环境务必更改为复杂随机字符串
FLASK_APP=run.py         # 指定 Flask 应用的入口文件
FLASK_ENV=development    # 设置为 development 可开启调试模式
FLASK_DEBUG=true         # 在开发环境下设置为 true，生产环境设置为 false

# AI 服务配置
# DeepSeek API 密钥 (用于股票分析和推荐功能)
DEEPSEEK_API_KEY=your_deepseek_api_key_here # 替换为您的DeepSeek API密钥

# 数据源 API Token (例如 Tushare)
# 如果使用 Tushare, 请在此处配置您的 Token
TUSHARE_TOKEN=your_tushare_token_here # 替换为您的Tushare Token
```

**重要提示**: `SECRET_KEY` 在生产环境中必须设置为一个强随机字符串，以保障应用安全。

### 5. 初始化数据库

首次运行或数据库结构变更时，需要进行数据库初始化和迁移。请确保您的 MySQL 和 Redis 服务已启动：

```bash
# 确保您的虚拟环境已激活

# 1. 初始化 Alembic 迁移仓库 (仅首次运行项目时执行一次)
flask db init

# 2. 生成数据库迁移脚本 (当模型有变化时执行)
# 命令会检测 app/models/ 下模型的变化，并生成相应的迁移文件
flask db migrate -m "Initial migration for all models" 

# 3. 执行数据库迁移，将脚本应用到数据库
flask db upgrade

# 4. (可选) 初始化策略基础数据（如果您的应用需要预置策略）
flask seed-db
```

### 6. 启动服务

**开发模式 (推荐)**：

```bash
# 使用 Flask 内置开发服务器
python run.py

# 或者使用 Flask CLI 命令启动 (与 run.py 效果类似)
# flask run --host=0.0.0.0 --port=5000
```

服务将运行在 `http://localhost:5000`。

**生产模式 (推荐)**：

为生产环境部署，推荐使用 Gunicorn 结合 Uvicorn 和 Eventlet 来部署 Flask 应用，尤其当应用包含 Socket.IO 功能时。可以配合 Supervisor 或 Docker 进行进程管理。

```bash
# 启动 Gunicorn + Eventlet (推荐用于 SocketIO)
gunicorn -k eventlet -w 4 "run:socketio" -b 0.0.0.0:5000 --preload

# 或者，如果不需要 SocketIO，只运行普通的 Flask 应用
# gunicorn -w 4 "run:app" -b 0.0.0.0:5000 --preload
```
`run:socketio` 指的是 `run.py` 文件中 `socketio` 实例。`-w 4` 表示启动4个 worker 进程。

### 7. 数据采集 (首次运行或定期更新必需)

后端服务需要历史数据才能进行回测和分析。首次部署后，请执行以下命令采集数据：

```bash
# 确保您的虚拟环境已激活

# 采集所有股票的基础信息 (代码、名称等)
flask collect-stocks

# 采集所有股票的历史K线数据 (耗时较长，建议在后台运行，例如使用 nohup 或 tmux)
flask collect-history

# 也可以通过 API 触发 (需服务已运行)
# curl -X POST http://localhost:5000/api/data/collect/stocks
# curl -X POST http://localhost:5000/api/data/collect/history
```

## 📚 API 文档

### Swagger UI (交互式 API 文档)

访问 `http://localhost:5000/api/doc`，即可在浏览器中查看由 Flask-RESTX 自动生成的交互式 API 文档。您可以在此页面查看所有可用API端点、详细的请求参数、响应示例，并直接发送测试请求。

### 主要 API 端点概览

| 模块          | 端点                                    | HTTP 方法 | 描述                                       |
| :------------ | :-------------------------------------- | :-------- | :----------------------------------------- |
| **股票信息**    | `/api/stocks`                           | `GET`     | 获取所有股票的基础信息列表                 |
|               | `/api/stocks/<string:code>`             | `GET`     | 获取指定股票代码的详细信息                 |
|               | `/api/stocks/<string:code>/daily`       | `GET`     | 获取指定股票的历史日K线数据                |
| **策略管理**    | `/api/strategies`                       | `GET`     | 获取所有已注册的交易策略列表               |
|               | `/api/strategies/<int:id>`              | `GET`     | 获取指定ID策略的详细信息                   |
| **回测系统**    | `/api/backtests`                        | `POST`    | 提交一个新的回测任务                       |
|               | `/api/backtests/<int:id>`               | `GET`     | 获取指定回测任务的详细结果和进度           |
| **数据采集**    | `/api/data/collect/stocks`              | `POST`    | 触发后台任务，采集所有股票的基础信息       |
|               | `/api/data/collect/history`             | `POST`    | 触发后台任务，采集所有股票的历史行情数据   |
|               | `/api/data/collect/status`              | `GET`     | 获取当前数据采集任务的状态和进度           |
| **实时行情**    | `/api/realtime/<string:code>`           | `GET`     | 获取指定股票的实时报价（如果可用）         |
| **自选股管理**  | `/api/watchlist`                        | `GET`     | 获取当前用户的自选股列表                   |
|               | `/api/watchlist`                        | `POST`    | 将指定股票添加到自选股列表                 |
|               | `/api/watchlist/<string:code>`          | `DELETE`  | 从自选股列表中移除指定股票                 |
| **任务调度**    | `/api/scheduler/jobs`                   | `GET`     | 获取所有定时任务的状态和详情               |
|               | `/api/scheduler/jobs/<string:job_id>`   | `POST`    | 暂停/恢复指定定时任务                      |
| **AI 分析**     | `/api/deepseek/analyze-text`            | `POST`    | 使用DeepSeek分析文本内容（如新闻、财报）   |
|               | `/api/deepseek/analyze-stock`           | `POST`    | 使用DeepSeek分析股票走势和买卖点          |
|               | `/api/deepseek/recommend-stocks`        | `POST`    | 基于回测数据使用DeepSeek推荐潜力股票       |

### WebSocket 事件 (实时数据推送)

后端通过 Socket.IO 提供实时数据推送服务，主要用于实时行情和任务进度更新。

-   **连接端点**: `ws://localhost:5000/` (Socket.IO 默认路径)

-   **事件监听示例**:

    ```javascript
    // 前端 JavaScript 示例
    import { io } from 'socket.io-client';

    const socket = io('ws://localhost:5000');

    socket.on('connect', () => {
        console.log('WebSocket 连接成功!');
        // 连接成功后，可以根据需要订阅事件，例如订阅特定股票的实时状态或任务进度
        // socket.emit('subscribe', { codes: ['000001.SZ', '000002.SZ'] }); // 此处为未来实时行情订阅预留
    });

    socket.on('realtime_data', (data) => {
        // 接收到实时行情数据 (当前可能为模拟数据或未来功能)
        console.log('收到实时数据:', data);
        // data 结构通常包含 stock_code, latest_price, timestamp 等
    });

    socket.on('job_status', (data) => {
        // 接收到后台任务状态更新 (例如数据采集、回测任务)
        console.log('任务状态:', data);
        // data 结构通常包含 job_id, status, message 等
    });

    socket.on('job_progress', (data) => {
        // 接收到后台任务进度更新
        console.log('任务进度:', data);
        // data 结构通常包含 job_id, progress, current_step, total_steps 等
    });

    socket.on('scheduler_status', (data) => {
        // 接收到调度器状态更新
        console.log('调度器状态:', data);
        // data 结构通常包含 scheduler_status, running_jobs_count, next_run_time 等
    });

    socket.on('disconnect', () => {
        console.log('WebSocket 连接断开.');
    });

    // 发送订阅请求的示例 (前端调用)
    // socket.emit('subscribe', { codes: ['股票代码1', '股票代码2'] }); // 未来实时行情功能使用
    // 取消订阅
    // socket.emit('unsubscribe', { codes: ['股票代码1'] }); // 未来实时行情功能使用
    ```

## 🔧 开发指南

### 1. 添加新的交易策略

要为回测引擎添加新的交易策略，请遵循以下步骤：

1.  在 `app/strategies/` 目录下创建一个新的 Python 文件，例如 `your_custom_strategy.py`。
2.  新策略类必须继承自 `app.strategies.base_strategy.BaseStrategy`，并实现其所有抽象方法。
    ```python
    # app/strategies/your_custom_strategy.py
    from .base_strategy import BaseStrategy
    import pandas as pd

    class YourCustomStrategy(BaseStrategy):
        @classmethod
        def get_identifier(cls) -> str:
            return 'your_custom_strategy_id' # 策略的唯一标识符
        
        @classmethod
        def get_name(cls) -> str:
            return '您的自定义策略名称' # 策略的友好名称
        
        @classmethod
        def get_description(cls) -> str:
            return '这是一个描述您的自定义策略功能的简短文本。'
        
        @classmethod
        def get_parameters_schema(cls) -> dict: # 如果策略有参数，定义JSON Schema
            return {
                "type": "object",
                "properties": {
                    "short_window": {"type": "integer", "default": 5, "description": "短期均线周期"},
                    "long_window": {"type": "integer", "default": 20, "description": "长期均线周期"}
                },
                "required": ["short_window", "long_window"]
            }

        def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
            """
            根据输入的历史数据和策略参数生成交易信号。
            返回的DataFrame应包含 'signal' 列 (1:买入, -1:卖出, 0:持有)。
            """
            # 示例: 简单的均线交叉策略
            df['short_ma'] = df['close'].rolling(window=params.get('short_window', 5)).mean()
            df['long_ma'] = df['close'].rolling(window=params.get('long_window', 20)).mean()
            
            signal = [0] * len(df)
            for i in range(1, len(df)): # 遍历数据生成信号
                if df['short_ma'].iloc[i-1] < df['long_ma'].iloc[i-1] and df['short_ma'].iloc[i] > df['long_ma'].iloc[i]:
                    signal[i] = 1  # 买入信号
                elif df['short_ma'].iloc[i-1] > df['long_ma'].iloc[i-1] and df['short_ma'].iloc[i] < df['long_ma'].iloc[i]:
                    signal[i] = -1 # 卖出信号
            df['signal'] = signal
            return df
    ```
3.  确保您的新策略文件在 `app/strategies/__init__.py` 中被导入，以便回测引擎能够发现它。

### 2. 编写单元测试

为确保代码质量和功能正确性，请为您的新功能或修改编写单元测试。测试文件通常位于与源代码对应的 `tests/` 目录下。

```bash
# 运行所有测试
pip install pytest
pytest

# 运行指定模块的测试
# pytest tests/unit/test_your_module.py
```

### 3. 数据库管理与迁移

当您修改了 `app/models/` 下的 SQLAlchemy 模型时，需要生成并应用数据库迁移：

```bash
# 1. 生成新的迁移脚本 (每次模型变化后执行)
flask db migrate -m "Add new_column to existing_table" 

# 2. 应用迁移到数据库
flask db upgrade

# 3. 回滚最近一次迁移 (谨慎操作)
# flask db downgrade
```

### 4. 代码风格与质量

本项目遵循 PEP 8 Python 编码规范。建议使用以下工具进行代码格式化和静态分析：

-   **Black**: 格式化工具
-   **isort**: 导入排序工具
-   **Flake8**: 代码风格和质量检查

```bash
# 安装工具
pip install black isort flake8

# 格式化代码 (在项目根目录执行)
black .
isort .

# 运行静态分析
flake8 .
```

## ☁️ 部署

### 生产环境部署

推荐使用 Gunicorn 作为 WSGI 服务器，结合 Uvicorn 和 Eventlet 来部署 Flask 应用，尤其当应用包含 Socket.IO 功能时。可以配合 Supervisor 或 Docker 进行进程管理。

**示例 `supervisor` 配置 (`/etc/supervisor/conf.d/stock_backend.conf`)**

```ini
[program:stock_backend]
command = /path/to/your/venv/bin/gunicorn -k eventlet -w 4 "run:socketio" -b 0.0.0.0:5000
directory = /path/to/your/stock-scan/stock-backtest-backend
user = www-data
autostart = true
autorestart = true
redirect_stderr = true
stdout_logfile = /var/log/stock_backend/gunicorn_access.log
stderr_logfile = /var/log/stock_backend/gunicorn_error.log
environment=FLASK_ENV="production",SECRET_KEY="your_strong_secret_key"
```

请将 `/path/to/your/venv/bin/gunicorn` 和 `/path/to/your/stock-scan/stock-backtest-backend` 替换为实际路径，并将 `SECRET_KEY` 替换为生产环境专用的强密码。

### Docker 部署 (未来计划)

后续版本将提供 Docker Compose 文件，以简化容器化部署流程。

## 🤝 贡献指南

我们非常欢迎社区的贡献，无论是新功能、bug 修复还是文档改进！

1.  **Fork 项目**: 将本仓库 Fork 到您的 GitHub 账户。
2.  **克隆到本地**: 克隆您 Fork 的仓库到本地机器。
3.  **创建分支**: 为您的功能或修复创建一个新的分支 (e.g., `feature/add-new-strategy` 或 `fix/bug-report-123`)。
4.  **提交更改**: 在您的分支上进行开发并提交更改。请确保提交信息清晰明了，遵循 [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) 规范。
5.  **编写测试**: 为您的更改编写相应的单元测试和集成测试，并确保所有测试通过。
6.  **提交 Pull Request**: 将您的分支推送到 GitHub，并创建一个 Pull Request 到本项目的 `main` 分支。请在 PR 描述中详细说明您的更改。

在提交 Pull Request 之前，请确保您的代码通过了所有测试和代码风格检查。

## 📄 许可证

本项目采用 **MIT 许可证** 发布。详情请参阅 `LICENSE` 文件。

## ❓ 常见问题 (FAQ)

### 1. 为什么数据采集命令执行很慢？

历史数据采集需要从外部数据源获取大量数据，网络延迟和数据量大小都会影响其速度。建议在后台运行 `flask collect-history` 命令，并通过日志监控其进度。

### 2. 如何更新 Tushare Token？

修改项目根目录下的 `.env` 文件中的 `TUSHARE_TOKEN` 变量，然后重启后端服务即可生效。

### 3. 如何获取 DeepSeek API 密钥？

访问 [DeepSeek 官网](https://platform.deepseek.com/) 注册账号并获取 API 密钥，然后在 `.env` 文件中配置 `DEEPSEEK_API_KEY` 变量。

### 4. 如何查看后端日志？

日志文件默认存储在项目根目录下的 `logs/` 文件夹中。您可以查看 `app.log` 等文件。

## 🔒 安全提醒

**重要**: 请务必保护好您的 API 密钥和数据库密码等敏感信息：

1. **永远不要**将 `.env` 文件提交到版本控制系统（Git）
2. **永远不要**在代码中硬编码 API 密钥或密码
3. 定期更换 API 密钥，特别是在密钥可能泄露的情况下
4. 在生产环境中使用强密码和复杂的 `SECRET_KEY`
5. 限制数据库用户权限，避免使用 root 用户运行应用

如果您发现 API 密钥或密码可能已泄露，请立即：
- 更换相关的 API 密钥
- 修改数据库密码
- 检查系统日志，确认是否有异常访问

## 🔗 相关链接

以下是一些与本项目相关的官方文档和有用资源：

-   [Flask 官方文档](https://flask.palletsprojects.com/)
-   [Flask-RESTX 文档](https://flask-restx.readthedocs.io/)
-   [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
-   [Celery 文档](https://docs.celeryq.dev/)
-   [Redis 官方网站](https://redis.io/)
-   [MySQL 官方网站](https://www.mysql.com/)
-   [BaoStock 官方文档](http://baostock.com/)
-   [Tushare 官方网站](https://tushare.pro/)
-   [Swagger UI](https://swagger.io/tools/swagger-ui/) 