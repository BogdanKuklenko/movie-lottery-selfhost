"""add poll_duration_hours to poll_settings

Revision ID: k4l5m6n7o8p9
Revises: j3k4l5m6n7o8
Create Date: 2024-12-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k4l5m6n7o8p9'
down_revision = 'j3k4l5m6n7o8'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем колонку poll_duration_hours в таблицу poll_settings
    # По умолчанию 24 часа (текущее поведение)
    with op.batch_alter_table('poll_settings', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('poll_duration_hours', sa.Integer(), nullable=False, server_default=sa.text('24'))
        )


def downgrade():
    with op.batch_alter_table('poll_settings', schema=None) as batch_op:
        batch_op.drop_column('poll_duration_hours')

