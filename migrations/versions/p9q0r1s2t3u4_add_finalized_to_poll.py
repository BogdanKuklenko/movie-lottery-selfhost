"""add finalized to poll

Revision ID: p9q0r1s2t3u4
Revises: o8p9q0r1s2t3
Create Date: 2025-12-24 14:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p9q0r1s2t3u4'
down_revision = 'o8p9q0r1s2t3'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем колонку finalized в таблицу poll
    # True означает что бейдж победителя уже был применён
    with op.batch_alter_table('poll', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('finalized', sa.Boolean(), nullable=False, server_default=sa.text('FALSE'))
        )


def downgrade():
    with op.batch_alter_table('poll', schema=None) as batch_op:
        batch_op.drop_column('finalized')

