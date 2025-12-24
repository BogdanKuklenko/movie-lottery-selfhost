"""add cascade to vote foreign keys

Revision ID: n7o8p9q0r1s2
Revises: m6n7o8p9q0r1
Create Date: 2025-12-22 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'n7o8p9q0r1s2'
down_revision = 'm6n7o8p9q0r1'
branch_labels = None
depends_on = None


def upgrade():
    # Удаляем старые внешние ключи и создаём новые с ON DELETE CASCADE
    with op.batch_alter_table('vote', schema=None) as batch_op:
        # Удаляем старые FK constraints, если они существуют (чтобы миграция была идемпотентной)
        conn = op.get_bind()
        fk_names = {fk['name'] for fk in sa.inspect(conn).get_foreign_keys('vote')}
        if 'vote_poll_id_fkey' in fk_names:
            batch_op.drop_constraint('vote_poll_id_fkey', type_='foreignkey')
        if 'vote_movie_id_fkey' in fk_names:
            batch_op.drop_constraint('vote_movie_id_fkey', type_='foreignkey')
        
        # Создаём новые FK constraints с CASCADE
        batch_op.create_foreign_key(
            'vote_poll_id_fkey', 'poll',
            ['poll_id'], ['id'],
            ondelete='CASCADE'
        )
        batch_op.create_foreign_key(
            'vote_movie_id_fkey', 'poll_movie',
            ['movie_id'], ['id'],
            ondelete='CASCADE'
        )


def downgrade():
    # Возвращаем FK без CASCADE
    with op.batch_alter_table('vote', schema=None) as batch_op:
        conn = op.get_bind()
        fk_names = {fk['name'] for fk in sa.inspect(conn).get_foreign_keys('vote')}
        if 'vote_poll_id_fkey' in fk_names:
            batch_op.drop_constraint('vote_poll_id_fkey', type_='foreignkey')
        if 'vote_movie_id_fkey' in fk_names:
            batch_op.drop_constraint('vote_movie_id_fkey', type_='foreignkey')
        
        batch_op.create_foreign_key(
            'vote_poll_id_fkey', 'poll',
            ['poll_id'], ['id']
        )
        batch_op.create_foreign_key(
            'vote_movie_id_fkey', 'poll_movie',
            ['movie_id'], ['id']
        )

