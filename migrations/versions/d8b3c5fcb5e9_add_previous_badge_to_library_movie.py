"""add previous badge to library_movie

Revision ID: d8b3c5fcb5e9
Revises: 0b2e3e72e167
Create Date: 2025-05-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8b3c5fcb5e9'
down_revision = '0b2e3e72e167'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('library_movie'):
        column_names = {col['name'] for col in inspector.get_columns('library_movie')}
        if 'previous_badge' not in column_names:
            op.add_column('library_movie', sa.Column('previous_badge', sa.String(length=20), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('library_movie'):
        column_names = {col['name'] for col in inspector.get_columns('library_movie')}
        if 'previous_badge' in column_names:
            op.drop_column('library_movie', 'previous_badge')
