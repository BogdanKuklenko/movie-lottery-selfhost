"""add winner_badge to poll

Revision ID: o8p9q0r1s2t3
Revises: n7o8p9q0r1s2
Create Date: 2025-12-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'o8p9q0r1s2t3'
down_revision = 'n7o8p9q0r1s2'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем колонку winner_badge в таблицу poll
    # Бейдж победителя сохраняется при создании опроса
    with op.batch_alter_table('poll', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('winner_badge', sa.String(30), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('poll', schema=None) as batch_op:
        batch_op.drop_column('winner_badge')
