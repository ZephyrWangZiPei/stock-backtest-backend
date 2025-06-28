import click
from app import db
from app.models import Strategy, BacktestResult
from app.strategies import STRATEGY_MAP
import re

def _camel_to_snake(name):
    """将大驼峰命名转换为下划线命名，并移除 'Strategy' 后缀"""
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()
    return name.replace('_strategy', '')

def _generate_default_name(identifier: str) -> str:
    """根据标识符生成一个默认的、可读的名称"""
    return identifier.replace('_', ' ').title()

def register_commands(app):
    @app.cli.command('sync-strategies')
    def sync_strategies():
        """自动发现并同步策略到数据库"""
        click.echo("开始同步策略到数据库...")
        
        try:
            for identifier, strategy_class in STRATEGY_MAP.items():
                strategy = Strategy.query.filter_by(identifier=identifier).first()
                
                if not strategy:
                    # 如果策略不存在，则创建
                    docstring = strategy_class.__doc__
                    description = docstring.strip().split('\\n')[0] if docstring else "无详细描述"
                    
                    default_params = {}
                    param_defs = strategy_class.get_parameter_definitions()
                    for param_def in param_defs:
                        default_params[param_def['name']] = param_def['default']

                    new_strategy = Strategy(
                        identifier=identifier,
                        name=_generate_default_name(identifier),
                        description=description,
                        parameters=str(default_params) # 存储默认参数
                    )
                    db.session.add(new_strategy)
                    click.echo(f"  + 新增策略: {identifier}")
                else:
                    # 可选：如果策略已存在，可以更新其描述等信息
                    click.echo(f"  = 已存在策略: {identifier} (跳过)")

            db.session.commit()
            click.echo("策略同步完成！")
        except Exception as e:
            db.session.rollback()
            click.echo(f"发生错误: {e}")

    @app.cli.command('clean-faulty-strategies')
    def clean_faulty_strategies():
        """删除因为bug导致名字错误的策略，并级联删除相关的回测记录"""
        click.echo("开始清理错误的策略条目及关联的回测...")
        try:
            faulty_strategies = Strategy.query.filter(Strategy.id > 1).all()
            if not faulty_strategies:
                click.echo("没有找到需要清理的策略。")
                return
            
            for strategy in faulty_strategies:
                click.echo(f" - 正在删除策略: ID={strategy.id}, Name='{strategy.name}'")
                # ORM会处理级联删除 BacktestResult 和 BacktestTrade
                db.session.delete(strategy)
            
            db.session.commit()
            click.echo("清理完成！")
        except Exception as e:
            db.session.rollback()
            click.echo(f"清理时发生错误: {e}") 