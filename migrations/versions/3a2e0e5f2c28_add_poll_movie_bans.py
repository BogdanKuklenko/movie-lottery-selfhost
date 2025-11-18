"""add poll movie bans and forced winner

Revision ID: 3a2e0e5f2c28
Revises: 0b2e3e72e167
Create Date: 2025-05-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3a2e0e5f2c28'
down_revision = '0b2e3e72e167'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('poll_movie', sa.Column('ban_until', sa.DateTime(), nullable=True))
    op.add_column('poll', sa.Column('forced_winner_movie_id', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('poll', 'forced_winner_movie_id')
    op.drop_column('poll_movie', 'ban_until')
