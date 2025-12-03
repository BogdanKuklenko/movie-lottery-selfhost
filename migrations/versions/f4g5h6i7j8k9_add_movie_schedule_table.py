"""Add movie_schedule table for calendar timers

Revision ID: f4g5h6i7j8k9
Revises: e2f3g4h5i6j7
Create Date: 2025-12-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4g5h6i7j8k9'
down_revision = 'e2f3g4h5i6j7'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'movie_schedule' not in existing_tables:
        op.create_table(
            'movie_schedule',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('library_movie_id', sa.Integer(), nullable=False),
            sa.Column('scheduled_date', sa.DateTime(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
            sa.Column('postponed_until', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['library_movie_id'],
                ['library_movie.id'],
                ondelete='CASCADE'
            ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('library_movie_id', 'scheduled_date', name='unique_movie_schedule_date')
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'movie_schedule' in existing_tables:
        op.drop_table('movie_schedule')

