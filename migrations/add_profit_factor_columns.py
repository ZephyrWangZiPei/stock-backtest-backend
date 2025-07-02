#!/usr/bin/env python3
"""临时迁移脚本：为 backtest_results 与 top_strategy_stocks 表添加 profit_factor、expectancy 字段（如缺失）。
使用方式：
    python migrations/add_profit_factor_columns.py
仅需运行一次；在生产环境请改用 Alembic 正式迁移。
"""
import os
import sys
import sqlalchemy as sa

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
sys.path.insert(0, PROJECT_ROOT)

from app import create_app, db

commands = [
    # backtest_results
    "ALTER TABLE backtest_results ADD COLUMN profit_factor NUMERIC(10,4)",
    "ALTER TABLE backtest_results ADD COLUMN expectancy NUMERIC(10,4)",
    # top_strategy_stocks
    "ALTER TABLE top_strategy_stocks ADD COLUMN profit_factor NUMERIC(10,4)",
]

def column_exists(conn, table, column):
    insp = sa.inspect(conn)
    return column in [c['name'] for c in insp.get_columns(table)]


def run():
    app = create_app()
    with app.app_context():
        engine = db.engine
        with engine.connect() as conn:
            for stmt in commands:
                parts = stmt.split()
                table = parts[2]
                col = parts[5]
                if column_exists(conn, table, col):
                    print(f"{table}.{col} already exists, skip.")
                    continue
                try:
                    conn.execute(sa.text(stmt))
                    print(f"Added {table}.{col}")
                except Exception as e:
                    print(f"Failed to execute {stmt}: {e}")

if __name__ == '__main__':
    run() 