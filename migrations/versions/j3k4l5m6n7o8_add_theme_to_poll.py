"""add theme to poll

Revision ID: j3k4l5m6n7o8
Revises: i2j3k4l5m6n7
Create Date: 2024-12-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'j3k4l5m6n7o8'
down_revision = 'i2j3k4l5m6n7'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем колонку theme в таблицу poll
    with op.batch_alter_table('poll', schema=None) as batch_op:
        batch_op.add_column(sa.Column('theme', sa.String(30), nullable=False, server_default='default'))


def downgrade():
    with op.batch_alter_table('poll', schema=None) as batch_op:
        batch_op.drop_column('theme')





