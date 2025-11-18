"""add ban fields to library_movie

Revision ID: 7b4ec1771b6a
Revises: a6a3b6c6d4d9
Create Date: 2025-12-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b4ec1771b6a'
down_revision = 'a6a3b6c6d4d9'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('library_movie'):
        column_names = {col['name'] for col in inspector.get_columns('library_movie')}

        if 'ban_until' not in column_names:
            op.add_column('library_movie', sa.Column('ban_until', sa.DateTime(), nullable=True))

        if 'ban_applied_by' not in column_names:
            op.add_column('library_movie', sa.Column('ban_applied_by', sa.String(length=120), nullable=True))

        if 'ban_cost' not in column_names:
            op.add_column('library_movie', sa.Column('ban_cost', sa.Integer(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('library_movie'):
        column_names = {col['name'] for col in inspector.get_columns('library_movie')}

        if 'ban_cost' in column_names:
            op.drop_column('library_movie', 'ban_cost')

        if 'ban_applied_by' in column_names:
            op.drop_column('library_movie', 'ban_applied_by')

        if 'ban_until' in column_names:
            op.drop_column('library_movie', 'ban_until')
