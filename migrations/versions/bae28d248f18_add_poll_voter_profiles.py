"""add poll voter profiles

Revision ID: bae28d248f18
Revises: 0b2e3e72e167
Create Date: 2025-11-15 06:39:22.912344

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bae28d248f18'
down_revision = '0b2e3e72e167'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())
    created_profile_table = False

    if 'poll_voter_profile' not in table_names:
        op.create_table(
            'poll_voter_profile',
            sa.Column('token', sa.String(length=64), nullable=False),
            sa.Column('total_points', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('device_label', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('token')
        )
        created_profile_table = True

    if 'vote' in table_names:
        vote_columns = {column['name']: column for column in inspector.get_columns('vote')}
        fk_names = {fk['name'] for fk in inspector.get_foreign_keys('vote') if fk.get('name')}

        with op.batch_alter_table('vote', schema=None) as batch_op:
            if 'points_awarded' not in vote_columns:
                batch_op.add_column(sa.Column('points_awarded', sa.Integer(), nullable=False, server_default='0'))

            voter_token_column = vote_columns.get('voter_token')
            if voter_token_column:
                current_length = getattr(voter_token_column['type'], 'length', None)
                if current_length is None or current_length < 64:
                    batch_op.alter_column(
                        'voter_token',
                        existing_type=sa.String(length=current_length or 32),
                        type_=sa.String(length=64),
                        existing_nullable=False,
                    )

            if 'fk_vote_voter_token_profile' not in fk_names:
                batch_op.create_foreign_key(
                    'fk_vote_voter_token_profile',
                    'poll_voter_profile',
                    ['voter_token'],
                    ['token'],
                )

        with op.batch_alter_table('vote', schema=None) as batch_op:
            if 'points_awarded' in vote_columns:
                batch_op.alter_column('points_awarded', existing_type=sa.Integer(), server_default=None)

    if created_profile_table and 'vote' in table_names:
        _backfill_profiles()

    if 'poll_voter_profile' in table_names or created_profile_table:
        with op.batch_alter_table('poll_voter_profile', schema=None) as batch_op:
            profile_columns = {column['name'] for column in inspector.get_columns('poll_voter_profile')}
            if 'total_points' in profile_columns:
                batch_op.alter_column('total_points', existing_type=sa.Integer(), server_default=None)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())

    if 'vote' in table_names:
        vote_columns = {column['name']: column for column in inspector.get_columns('vote')}
        fk_names = {fk['name'] for fk in inspector.get_foreign_keys('vote') if fk.get('name')}

        with op.batch_alter_table('vote', schema=None) as batch_op:
            if 'fk_vote_voter_token_profile' in fk_names:
                batch_op.drop_constraint('fk_vote_voter_token_profile', type_='foreignkey')

            if 'points_awarded' in vote_columns:
                batch_op.drop_column('points_awarded')

            voter_token_column = vote_columns.get('voter_token')
            if voter_token_column:
                current_length = getattr(voter_token_column['type'], 'length', None)
                if current_length is None or current_length > 32:
                    batch_op.alter_column(
                        'voter_token',
                        existing_type=sa.String(length=current_length or 64),
                        type_=sa.String(length=32),
                        existing_nullable=False,
                    )

    if 'poll_voter_profile' in table_names:
        op.drop_table('poll_voter_profile')


def _backfill_profiles():
    bind = op.get_bind()
    metadata = sa.MetaData()

    vote_table = sa.Table('vote', metadata, autoload_with=bind)
    profile_table = sa.Table('poll_voter_profile', metadata, autoload_with=bind)

    tokens = [row[0] for row in bind.execute(sa.select(sa.distinct(vote_table.c.voter_token)))]
    now = datetime.utcnow()

    payload = [
        {
            'token': token,
            'total_points': 0,
            'device_label': None,
            'created_at': now,
            'updated_at': now,
        }
        for token in tokens
        if token
    ]

    if payload:
        bind.execute(profile_table.insert(), payload)
