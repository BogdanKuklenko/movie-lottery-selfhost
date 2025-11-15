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
    op.create_table(
        'poll_voter_profile',
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('total_points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('device_label', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('token')
    )

    with op.batch_alter_table('vote', schema=None) as batch_op:
        batch_op.add_column(sa.Column('points_awarded', sa.Integer(), nullable=False, server_default='0'))
        batch_op.alter_column(
            'voter_token',
            existing_type=sa.String(length=32),
            type_=sa.String(length=64),
            existing_nullable=False,
        )
        batch_op.create_foreign_key(
            'fk_vote_voter_token_profile',
            'poll_voter_profile',
            ['voter_token'],
            ['token'],
        )

    _backfill_profiles()

    with op.batch_alter_table('vote', schema=None) as batch_op:
        batch_op.alter_column('points_awarded', existing_type=sa.Integer(), server_default=None)
    with op.batch_alter_table('poll_voter_profile', schema=None) as batch_op:
        batch_op.alter_column('total_points', existing_type=sa.Integer(), server_default=None)


def downgrade():
    with op.batch_alter_table('vote', schema=None) as batch_op:
        batch_op.drop_constraint('fk_vote_voter_token_profile', type_='foreignkey')
        batch_op.drop_column('points_awarded')
        batch_op.alter_column(
            'voter_token',
            existing_type=sa.String(length=64),
            type_=sa.String(length=32),
            existing_nullable=False,
        )

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
