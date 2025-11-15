"""add bumped_at to library_movie"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d5eb7c9c2af'
down_revision = 'f3443ff64408'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table('library_movie'):
        column_names = {col['name'] for col in inspector.get_columns('library_movie')}

        if 'bumped_at' not in column_names:
            op.add_column(
                'library_movie',
                sa.Column(
                    'bumped_at',
                    sa.DateTime(),
                    nullable=True,
                    server_default=sa.text('CURRENT_TIMESTAMP')
                )
            )

        op.execute(sa.text('UPDATE library_movie SET bumped_at = added_at WHERE bumped_at IS NULL'))

        if bind.dialect.name != 'sqlite':
            op.alter_column(
                'library_movie',
                'bumped_at',
                existing_type=sa.DateTime(),
                nullable=False,
                server_default=sa.text('CURRENT_TIMESTAMP')
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table('library_movie'):
        column_names = {col['name'] for col in inspector.get_columns('library_movie')}

        if 'bumped_at' in column_names:
            op.drop_column('library_movie', 'bumped_at')
