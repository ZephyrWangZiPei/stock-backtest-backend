#!/usr/bin/env python
"""
数据管理脚本
用于执行各种数据更新和维护任务
"""

import click
from datetime import datetime, timedelta
from app import create_app, db, socketio
from app.scheduler.tasks import DataUpdateTask

app = create_app()

@click.group()
def cli():
    """股票数据管理工具"""
    pass

@cli.command()
@click.option('--date', '-d', help='指定日期 (YYYY-MM-DD格式，默认为今天)')
def update_daily(date):
    """更新每日数据"""
    with app.app_context():
        task = DataUpdateTask(app)
        click.echo(f"开始更新每日数据 (日期: {date or '今天'})")
        
        result = task.update_daily_data(date)
        
        if result['success']:
            click.echo(click.style(f"✅ {result['message']}", fg='green'))
            if result['data']:
                data = result['data']
                click.echo(f"更新统计: 成功 {data.get('success', 0)}, 失败 {data.get('error', 0)}")
        else:
            click.echo(click.style(f"❌ {result['message']}", fg='red'))

@cli.command()
def update_stocks():
    """更新股票列表"""
    with app.app_context():
        task = DataUpdateTask(app)
        click.echo("开始更新股票列表...")
        
        result = task.update_stock_list()
        
        if result['success']:
            click.echo(click.style(f"✅ {result['message']}", fg='green'))
            if result['data']:
                data = result['data']
                click.echo(f"更新统计: 成功 {data.get('success', 0)}, 失败 {data.get('error', 0)}")
        else:
            click.echo(click.style(f"❌ {result['message']}", fg='red'))

@cli.command()
@click.option('--days', '-d', default=3650, help='保留数据的天数 (默认: 3650天)')
def cleanup_data(days):
    """清理旧数据"""
    with app.app_context():
        task = DataUpdateTask(app)
        click.echo(f"开始清理 {days} 天前的旧数据...")
        
        result = task.cleanup_old_data(days)
        
        if result['success']:
            click.echo(click.style(f"✅ {result['message']}", fg='green'))
        else:
            click.echo(click.style(f"❌ {result['message']}", fg='red'))

@cli.command()
@click.option('--start', '-s', required=True, help='开始日期 (YYYY-MM-DD)')
@click.option('--end', '-e', help='结束日期 (YYYY-MM-DD，默认为今天)')
@click.option('--stocks', help='指定股票代码，用逗号分隔')
def batch_update(start, end, stocks):
    """批量更新历史数据"""
    with app.app_context():
        task = DataUpdateTask(app)
        stock_codes = stocks.split(',') if stocks else None
        
        click.echo(f"开始批量更新历史数据:")
        click.echo(f"  日期范围: {start} 到 {end or '今天'}")
        click.echo(f"  股票范围: {'指定股票' if stock_codes else '所有股票'}")
        
        result = task.batch_update_historical_data(start, end, stock_codes)
        
        if result['success']:
            click.echo(click.style(f"✅ {result['message']}", fg='green'))
            if result['data']:
                data = result['data']
                click.echo(f"处理统计: 成功 {data.get('success', 0)}, 失败 {data.get('error', 0)}")
        else:
            click.echo(click.style(f"❌ {result['message']}", fg='red'))

@cli.command()
def auto_update():
    """自动更新 - 检查并更新缺失的数据"""
    with app.app_context():
        click.echo("开始自动更新检查...")
        
        # 检查最近5个交易日的数据
        task = DataUpdateTask(app)
        today = datetime.now()
        
        for i in range(5):
            check_date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            
            # 检查该日期是否有数据
            from app.models import DailyData
            data_count = DailyData.query.filter_by(
                trade_date=datetime.strptime(check_date, '%Y-%m-%d').date()
            ).count()
            
            if data_count == 0 and task._is_trading_day(check_date):
                click.echo(f"发现 {check_date} 缺少数据，开始更新...")
                result = task.update_daily_data(check_date)
                
                if result['success']:
                    click.echo(click.style(f"✅ {check_date} 数据更新完成", fg='green'))
                else:
                    click.echo(click.style(f"❌ {check_date} 数据更新失败: {result['message']}", fg='red'))
            else:
                click.echo(f"📊 {check_date} 数据正常 (共 {data_count} 条)")

@cli.command()
def scheduler_status():
    """查看调度器状态"""
    with app.app_context():
        if hasattr(app, 'scheduler') and app.scheduler:
            jobs = app.scheduler.get_jobs()
            click.echo(f"调度器状态: {'运行中' if app.scheduler.scheduler.running else '已停止'}")
            click.echo(f"定时任务数量: {len(jobs)}")
            
            if jobs:
                click.echo("\n定时任务列表:")
                for job in jobs:
                    status = "✅" if job.next_run_time else "⏸️"
                    next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else "未安排"
                    click.echo(f"  {status} {job.name} (ID: {job.id}) - 下次运行: {next_run}")
        else:
            click.echo(click.style("调度器未初始化", fg='red'))

@cli.command()
def setup_jobs():
    """初始化并设置所有预定义的定时任务"""
    with app.app_context():
        if hasattr(app, 'scheduler') and app.scheduler:
            click.echo("开始设置定时任务...")
            
            # 添加每日数据更新任务
            app.scheduler.add_daily_data_update_job()
            
            # 添加周末数据清理任务
            app.scheduler.add_weekend_data_cleanup_job()
            
            # 添加月度股票列表更新任务
            app.scheduler.add_stock_list_update_job()
            
            click.echo(click.style("✅ 定时任务设置完成", fg='green'))
            
            # 打印状态
            scheduler_status.callback()
        else:
            click.echo(click.style("调度器未初始化, 无法设置任务", fg='red'))

@cli.command()
@click.option('--date', '-d', help='指定日期 (YYYY-MM-DD格式，默认为今天)')
def check_data(date):
    """检查指定日期的数据入库情况"""
    with app.app_context():
        from app.models import DailyData
        from datetime import datetime, date as dt_date

        check_date: dt_date
        if not date:
            check_date = datetime.now().date()
            date_str = "今天"
        else:
            check_date = datetime.strptime(date, '%Y-%m-%d').date()
            date_str = date

        click.echo(f"正在查询 {date_str} ({check_date}) 的数据...")
        count = DailyData.query.filter_by(trade_date=check_date).count()

        if count > 0:
            click.echo(click.style(f"✅ 在 {check_date} 找到了 {count} 条数据。", fg='green'))
        else:
            click.echo(click.style(f"❌ 在 {check_date} 没有找到任何数据。", fg='red'))

@cli.command()
def data_status():
    """显示数据库整体状态"""
    with app.app_context():
        from app.models import Stock, DailyData
        from datetime import datetime, timedelta
        
        click.echo("=== 数据库状态检查 ===")
        
        # 基本统计
        stock_count = Stock.query.count()
        active_stock_count = Stock.query.filter(Stock.is_active == True).count()
        total_daily_data = DailyData.query.count()
        
        click.echo(f"股票总数: {stock_count}")
        click.echo(f"活跃股票数: {active_stock_count}")
        click.echo(f"日线数据总数: {total_daily_data}")
        
        # 最近7天数据统计
        click.echo("\n=== 最近7天数据统计 ===")
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).date()
            count = DailyData.query.filter(DailyData.trade_date == date).count()
            weekday = date.strftime('%A')
            status = "✅" if count > 0 else "❌"
            click.echo(f"{status} {date} ({weekday}): {count}条")
        
        # 最新数据
        click.echo("\n=== 最新数据样本 ===")
        recent_data = DailyData.query.order_by(DailyData.trade_date.desc()).limit(5).all()
        if recent_data:
            for data in recent_data:
                click.echo(f"  {data.stock.code} - {data.trade_date} - 收盘价: {data.close_price}")
        else:
            click.echo("  没有找到任何数据")
        
        # 数据完整性检查
        click.echo("\n=== 数据完整性检查 ===")
        latest_date = DailyData.query.order_by(DailyData.trade_date.desc()).first()
        if latest_date:
            latest_date_count = DailyData.query.filter(DailyData.trade_date == latest_date.trade_date).count()
            completeness = (latest_date_count / active_stock_count) * 100 if active_stock_count > 0 else 0
            click.echo(f"最新交易日 ({latest_date.trade_date}) 数据完整性: {completeness:.1f}% ({latest_date_count}/{active_stock_count})")
        else:
            click.echo("无法确定数据完整性")

if __name__ == '__main__':
    cli() 