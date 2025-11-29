"""add library movie trailer table

Revision ID: 3c9c6fa8d5c2
Revises: 25ef3a9435e3
Create Date: 2025-01-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c9c6fa8d5c2'
down_revision = '25ef3a9435e3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'library_movie_trailer',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('movie_id', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('mime_type', sa.String(length=120), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['movie_id'], ['library_movie.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('movie_id'),
    )


def downgrade():
    op.drop_table('library_movie_trailer')
