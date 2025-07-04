"""add ai_analysis_report field

Revision ID: 95bc0f832711
Revises: 669ad868ce71
Create Date: 2025-07-04 21:32:18.537209

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '95bc0f832711'
down_revision = '669ad868ce71'
branch_labels = None
depends_on = None


def upgrade():
    """仅向 backtest_results 表添加 ai_analysis_report 字段"""
    with op.batch_alter_table('backtest_results', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ai_analysis_report', sa.Text(), nullable=True, comment='AI 分析报告'))


def downgrade():
    """回滚时删除 ai_analysis_report 字段"""
    with op.batch_alter_table('backtest_results', schema=None) as batch_op:
        batch_op.drop_column('ai_analysis_report')
