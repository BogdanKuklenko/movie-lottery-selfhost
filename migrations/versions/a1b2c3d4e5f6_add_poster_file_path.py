"""Add poster_file_path to library_movie

Revision ID: a1b2c3d4e5f6
Revises: e2f3g4h5i6j7
Create Date: 2025-12-01 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'e2f3g4h5i6j7'
branch_labels = None
depends_on = None


def upgrade():
    # Add poster_file_path column for local poster storage
    with op.batch_alter_table('library_movie', schema=None) as batch_op:
        batch_op.add_column(sa.Column('poster_file_path', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('library_movie', schema=None) as batch_op:
        batch_op.drop_column('poster_file_path')

