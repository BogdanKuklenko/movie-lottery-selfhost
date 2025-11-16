"""add points to library_movie"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4fd8ec70ffb0'
down_revision = '0b2e3e72e167'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table('library_movie'):
        column_names = {col['name'] for col in inspector.get_columns('library_movie')}

        if 'points' not in column_names:
            op.add_column(
                'library_movie',
                sa.Column(
                    'points',
                    sa.Integer(),
                    nullable=True,
                    server_default=sa.text('1')
                )
            )

        op.execute(sa.text('UPDATE library_movie SET points = 1 WHERE points IS NULL'))

        if bind.dialect.name != 'sqlite':
            op.alter_column(
                'library_movie',
                'points',
                existing_type=sa.Integer(),
                nullable=False,
                server_default=sa.text('1')
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table('library_movie'):
        column_names = {col['name'] for col in inspector.get_columns('library_movie')}

        if 'points' in column_names:
            op.drop_column('library_movie', 'points')
