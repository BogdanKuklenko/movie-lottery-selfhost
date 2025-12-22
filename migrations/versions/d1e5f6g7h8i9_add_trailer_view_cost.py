"""Add trailer_view_cost to library_movie

Revision ID: d1e5f6g7h8i9
Revises: 8a175a66ea7c
Create Date: 2025-11-29 21:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1e5f6g7h8i9'
down_revision = '8a175a66ea7c'
branch_labels = None
depends_on = None


def upgrade():
    # Add trailer_view_cost column to library_movie table
    with op.batch_alter_table('library_movie', schema=None) as batch_op:
        batch_op.add_column(sa.Column('trailer_view_cost', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('library_movie', schema=None) as batch_op:
        batch_op.drop_column('trailer_view_cost')
























