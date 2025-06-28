"""add update logs table

Revision ID: add_update_logs_table
Revises: 60cc216b6234
Create Date: 2024-03-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_update_logs_table'
down_revision = '60cc216b6234'  # 修改为现有的头部版本
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('update_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_name', sa.String(length=50), nullable=False),
        sa.Column('last_update', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_name')
    )

def downgrade():
    op.drop_table('update_logs') 