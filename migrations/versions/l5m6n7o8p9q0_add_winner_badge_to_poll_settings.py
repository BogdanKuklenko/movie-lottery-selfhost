"""add winner_badge to poll_settings

Revision ID: l5m6n7o8p9q0
Revises: k4l5m6n7o8p9
Create Date: 2024-12-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'l5m6n7o8p9q0'
down_revision = 'k4l5m6n7o8p9'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем колонку winner_badge в таблицу poll_settings
    # NULL или пустая строка означает "без изменения бейджа победителя"
    with op.batch_alter_table('poll_settings', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('winner_badge', sa.String(30), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('poll_settings', schema=None) as batch_op:
        batch_op.drop_column('winner_badge')

