"""Add notifications_enabled to poll

Revision ID: i2j3k4l5m6n7
Revises: g1h2i3j4k5l6
Create Date: 2025-12-17 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i2j3k4l5m6n7'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле notifications_enabled в таблицу poll
    # По умолчанию FALSE - уведомления выключены
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = [col['name'] for col in inspector.get_columns('poll')]
    
    if 'notifications_enabled' not in existing_columns:
        op.add_column(
            'poll',
            sa.Column(
                'notifications_enabled',
                sa.Boolean(),
                nullable=False,
                server_default=sa.text('FALSE'),
            )
        )


def downgrade():
    op.drop_column('poll', 'notifications_enabled')












