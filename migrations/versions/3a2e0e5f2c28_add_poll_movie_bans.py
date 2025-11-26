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
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())

    if 'poll_movie' in table_names:
        poll_movie_columns = {column['name'] for column in inspector.get_columns('poll_movie')}
        if 'ban_until' not in poll_movie_columns:
            op.add_column('poll_movie', sa.Column('ban_until', sa.DateTime(), nullable=True))

    if 'poll' in table_names:
        poll_columns = {column['name'] for column in inspector.get_columns('poll')}
        if 'forced_winner_movie_id' not in poll_columns:
            op.add_column('poll', sa.Column('forced_winner_movie_id', sa.Integer(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())

    if 'poll' in table_names:
        poll_columns = {column['name'] for column in inspector.get_columns('poll')}
        if 'forced_winner_movie_id' in poll_columns:
            op.drop_column('poll', 'forced_winner_movie_id')

    if 'poll_movie' in table_names:
        poll_movie_columns = {column['name'] for column in inspector.get_columns('poll_movie')}
        if 'ban_until' in poll_movie_columns:
            op.drop_column('poll_movie', 'ban_until')
