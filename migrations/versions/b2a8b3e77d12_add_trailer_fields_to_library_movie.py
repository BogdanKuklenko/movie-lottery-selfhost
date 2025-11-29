"""add trailer fields to library movie

Revision ID: b2a8b3e77d12
Revises: 9d5eb7c9c2af
Create Date: 2025-01-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2a8b3e77d12'
down_revision = '9d5eb7c9c2af'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('library_movie'):
        column_names = {col['name'] for col in inspector.get_columns('library_movie')}

        if 'trailer_file_path' not in column_names:
            op.add_column('library_movie', sa.Column('trailer_file_path', sa.String(length=500), nullable=True))

        if 'trailer_mime_type' not in column_names:
            op.add_column('library_movie', sa.Column('trailer_mime_type', sa.String(length=100), nullable=True))

        if 'trailer_file_size' not in column_names:
            op.add_column('library_movie', sa.Column('trailer_file_size', sa.Integer(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('library_movie'):
        column_names = {col['name'] for col in inspector.get_columns('library_movie')}

        if 'trailer_file_size' in column_names:
            op.drop_column('library_movie', 'trailer_file_size')

        if 'trailer_mime_type' in column_names:
            op.drop_column('library_movie', 'trailer_mime_type')

        if 'trailer_file_path' in column_names:
            op.drop_column('library_movie', 'trailer_file_path')
