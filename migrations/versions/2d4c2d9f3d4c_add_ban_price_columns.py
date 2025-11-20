"""add ban price columns to library and poll movies

Revision ID: 2d4c2d9f3d4c
Revises: 0b2e3e72e167
Create Date: 2026-02-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2d4c2d9f3d4c'
down_revision = '0b2e3e72e167'
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column):
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(table_name):
        return

    existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
    if column.name in existing_columns:
        return

    op.add_column(table_name, column)


def upgrade():
    _add_column_if_missing('library_movie', sa.Column('ban_price', sa.Integer(), nullable=False, server_default='1'))
    _add_column_if_missing('poll_movie', sa.Column('ban_price', sa.Integer(), nullable=False, server_default='1'))

    bind = op.get_bind()
    try:
        bind.execute(sa.text("UPDATE library_movie SET ban_price = 1 WHERE ban_price IS NULL"))
        bind.execute(sa.text("UPDATE poll_movie SET ban_price = 1 WHERE ban_price IS NULL"))
    except Exception:
        # Silent fallback: if table missing in some environments
        pass


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('library_movie'):
        columns = {col['name'] for col in inspector.get_columns('library_movie')}
        if 'ban_price' in columns:
            op.drop_column('library_movie', 'ban_price')

    if inspector.has_table('poll_movie'):
        columns = {col['name'] for col in inspector.get_columns('poll_movie')}
        if 'ban_price' in columns:
            op.drop_column('poll_movie', 'ban_price')
