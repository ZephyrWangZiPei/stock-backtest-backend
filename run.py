import os
import logging
from app import create_app, db, socketio
from app.models import *
from flask_migrate import Migrate

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 创建应用
app = create_app(os.getenv('FLASK_ENV', 'development'))

# 初始化 Flask-Migrate
migrate = Migrate(app, db)

@app.shell_context_processor
def make_shell_context():
    """Shell上下文处理器"""
    return {
        'db': db,
        'Stock': Stock,
        'DailyData': DailyData,
        'Strategy': Strategy,
        'BacktestResult': BacktestResult,
        'BacktestTrade': BacktestTrade,
        'UserWatchlist': UserWatchlist,
        'RealtimeData': RealtimeData,
        'UpdateLog': UpdateLog
    }

@app.cli.command()
def init_db():
    """初始化数据库"""
    db.create_all()
    print("数据库初始化完成")

@app.cli.command()
def collect_stocks():
    """采集股票基础信息"""
    from app.data_collector import DataCollector
    collector = DataCollector()
    result = collector.collect_all_stocks()
    print(f"采集完成: 成功 {result['success']}, 失败 {result['error']}")

@app.cli.command()
def collect_history():
    """采集历史数据"""
    from app.data_collector import DataCollector
    collector = DataCollector()
    result = collector.collect_historical_data()
    print(f"采集完成: 成功 {result['success']}, 失败 {result['error']}")

@app.cli.command("sync-data")
def sync_data():
    """使用BaoStock同步历史数据，支持断点续传。"""
    from app.data_collector import DataCollector
    print("开始使用BaoStock同步数据...")
    collector = DataCollector()
    result = collector.initialize_with_baostock()
    print(f"同步完成: {result.get('message')}")

@app.cli.command("recreate-db")
def recreate_db():
    """Drops and recreates the database tables."""
    db.drop_all()
    db.create_all()
    print("Database tables recreated.")

@app.cli.command("seed-db")
def seed_db():
    """Seeds the database with initial data."""
    from app.models import Strategy
    import json

    # Check if a strategy with this identifier already exists
    if Strategy.query.filter_by(identifier='dual_moving_average').first():
        print("Dual Moving Average strategy already exists.")
        return

    dma_strategy = Strategy(
        name='双均线交叉策略',
        description='当短期移动平均线从下方穿越长期移动平均线时买入（金叉），从上方穿越时卖出（死叉）。',
        identifier='dual_moving_average',
        parameters=json.dumps({
            'short_window': 5,
            'long_window': 20,
            'stop_loss_pct': 0.1,  # 10%止损
            'take_profit_pct': 0.3 # 30%止盈
        })
    )
    db.session.add(dma_strategy)
    db.session.commit()
    print("Database seeded with Dual Moving Average strategy.")

@app.cli.command("update-stock-list")
def update_stock_list():
    """Updates the stock list from Baostock."""
    from app.data_collector.baostock_client import BaostockClient
    from app.models import Stock
    from datetime import datetime, timedelta

    print("Updating stock list from Baostock...")
    with BaostockClient() as client:
        trade_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        stocks_df = client.get_all_stocks(trade_date)
        stocks_df = stocks_df[stocks_df['tradeStatus'] == '1'] # Filter for trading stocks

        existing_codes = {s.code for s in Stock.query.all()}
        
        new_stocks_count = 0
        for _, row in stocks_df.iterrows():
            if row['code'] not in existing_codes:
                market_map = {'sh': 'SH', 'sz': 'SZ'}
                market = market_map.get(row['code'].split('.')[0])
                stock = Stock(
                    code=row['code'],
                    name=row['code_name'],
                    market=market,
                    stock_type='stock'
                )
                db.session.add(stock)
                new_stocks_count += 1

    if new_stocks_count > 0:
        db.session.commit()
        print(f"Added {new_stocks_count} new stocks to the database.")
    else:
        print("Stock list is already up to date.")

@app.cli.command("calculate-indicators")
def calculate_indicators():
    """Calculates and fills technical indicators for all stocks."""
    from app.data_collector import DataCollector
    
    print("Starting technical indicator calculation...")
    collector = DataCollector()
    collector.calculate_and_fill_indicators()
    print("Technical indicator calculation finished.")

if __name__ == '__main__':
    # 开发环境使用socketio.run
    socketio.run(app, debug=True, host='0.0.0.0', port=5000) 