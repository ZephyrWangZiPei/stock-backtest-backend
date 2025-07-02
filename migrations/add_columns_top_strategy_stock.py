#!/usr/bin/env python3
"""临时迁移脚本：为 top_strategy_stocks 表添加 trade_count、win_rate_lb、expectancy 字段
仅在缺少字段时运行一次即可。
"""
import sys, os, sqlalchemy as sa

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, '..'))

from app import create_app, db

add_column_statements = [
    "ALTER TABLE top_strategy_stocks ADD COLUMN trade_count INTEGER",
    "ALTER TABLE top_strategy_stocks ADD COLUMN win_rate_lb NUMERIC(10,4)",
    "ALTER TABLE top_strategy_stocks ADD COLUMN expectancy NUMERIC(10,4)"
]

def column_exists(connection, table_name, column_name):
    insp = sa.inspect(connection)
    columns = [c['name'] for c in insp.get_columns(table_name)]
    return column_name in columns

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        engine = db.engine
        with engine.connect() as conn:
            for stmt in add_column_statements:
                col_name = stmt.split()[4]
                if column_exists(conn, 'top_strategy_stocks', col_name):
                    print(f"Column {col_name} already exists, skip.")
                    continue
                try:
                    conn.execute(sa.text(stmt))
                    print(f"Added column {col_name}.")
                except Exception as e:
                    print(f"Failed to add {col_name}: {e}") 