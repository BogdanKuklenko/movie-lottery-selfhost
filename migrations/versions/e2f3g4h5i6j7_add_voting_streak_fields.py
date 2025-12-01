"""Add voting streak fields to poll_voter_profile

Revision ID: e2f3g4h5i6j7
Revises: d1e5f6g7h8i9
Create Date: 2025-12-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2f3g4h5i6j7'
down_revision = 'd1e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'poll_voter_profile' not in inspector.get_table_names():
        return

    existing_columns = {col['name'] for col in inspector.get_columns('poll_voter_profile')}

    with op.batch_alter_table('poll_voter_profile', schema=None) as batch_op:
        if 'voting_streak' not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    'voting_streak',
                    sa.Integer(),
                    nullable=False,
                    server_default='0',
                )
            )

        if 'last_vote_date' not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    'last_vote_date',
                    sa.Date(),
                    nullable=True,
                )
            )

        if 'max_voting_streak' not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    'max_voting_streak',
                    sa.Integer(),
                    nullable=False,
                    server_default='0',
                )
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'poll_voter_profile' not in inspector.get_table_names():
        return

    existing_columns = {col['name'] for col in inspector.get_columns('poll_voter_profile')}

    with op.batch_alter_table('poll_voter_profile', schema=None) as batch_op:
        if 'voting_streak' in existing_columns:
            batch_op.drop_column('voting_streak')

        if 'last_vote_date' in existing_columns:
            batch_op.drop_column('last_vote_date')

        if 'max_voting_streak' in existing_columns:
            batch_op.drop_column('max_voting_streak')



