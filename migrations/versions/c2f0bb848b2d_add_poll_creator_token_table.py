"""add_poll_creator_token_table

Revision ID: c2f0bb848b2d
Revises: f3443ff64408
Create Date: 2025-10-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2f0bb848b2d'
down_revision = 'f3443ff64408'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table('poll_creator_token'):
        op.create_table(
            'poll_creator_token',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('creator_token', sa.String(length=64), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('last_seen', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('creator_token', name='uq_poll_creator_token_token'),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('poll_creator_token'):
        op.drop_table('poll_creator_token')
