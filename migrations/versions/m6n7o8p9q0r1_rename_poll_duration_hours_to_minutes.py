"""rename poll_duration_hours to poll_duration_minutes

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
Create Date: 2024-12-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm6n7o8p9q0r1'
down_revision = 'l5m6n7o8p9q0'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite не поддерживает ALTER COLUMN напрямую, используем batch_alter_table
    with op.batch_alter_table('poll_settings', schema=None) as batch_op:
        # Добавляем новую колонку poll_duration_minutes
        batch_op.add_column(
            sa.Column('poll_duration_minutes', sa.Integer(), nullable=False, server_default=sa.text('1440'))
        )
    
    # Конвертируем существующие значения из часов в минуты
    op.execute('UPDATE poll_settings SET poll_duration_minutes = poll_duration_hours * 60')
    
    # Удаляем старую колонку poll_duration_hours
    with op.batch_alter_table('poll_settings', schema=None) as batch_op:
        batch_op.drop_column('poll_duration_hours')


def downgrade():
    with op.batch_alter_table('poll_settings', schema=None) as batch_op:
        # Добавляем обратно poll_duration_hours
        batch_op.add_column(
            sa.Column('poll_duration_hours', sa.Integer(), nullable=False, server_default=sa.text('24'))
        )
    
    # Конвертируем минуты обратно в часы (округляем вверх)
    op.execute('UPDATE poll_settings SET poll_duration_hours = (poll_duration_minutes + 59) / 60')
    
    with op.batch_alter_table('poll_settings', schema=None) as batch_op:
        batch_op.drop_column('poll_duration_minutes')

