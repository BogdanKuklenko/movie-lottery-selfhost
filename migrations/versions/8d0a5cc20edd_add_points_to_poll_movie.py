"""add points to poll_movie"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8d0a5cc20edd'
down_revision = ('4fd8ec70ffb0', 'bae28d248f18')
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('poll_movie'):
        return

    existing_columns = {col['name'] for col in inspector.get_columns('poll_movie')}
    if 'points' not in existing_columns:
        op.add_column(
            'poll_movie',
            sa.Column('points', sa.Integer(), nullable=True, server_default=sa.text('1')),
        )

    op.execute(sa.text('UPDATE poll_movie SET points = COALESCE(points, 1)'))

    if bind.dialect.name != 'sqlite':
        op.alter_column(
            'poll_movie',
            'points',
            existing_type=sa.Integer(),
            nullable=False,
            server_default=sa.text('1'),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('poll_movie'):
        return

    existing_columns = {col['name'] for col in inspector.get_columns('poll_movie')}
    if 'points' in existing_columns:
        op.drop_column('poll_movie', 'points')
