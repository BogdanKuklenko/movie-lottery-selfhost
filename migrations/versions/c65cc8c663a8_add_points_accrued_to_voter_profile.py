"""add points accrued to voter profile

Revision ID: c65cc8c663a8
Revises: 3a2e0e5f2c28
Create Date: 2025-11-26 08:23:37.135847

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c65cc8c663a8'
down_revision = '3a2e0e5f2c28'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'poll_voter_profile' not in inspector.get_table_names():
        return

    existing_columns = {col['name'] for col in inspector.get_columns('poll_voter_profile')}
    if 'points_accrued_total' in existing_columns:
        return

    with op.batch_alter_table('poll_voter_profile') as batch_op:
        batch_op.add_column(
            sa.Column(
                'points_accrued_total',
                sa.Integer(),
                nullable=False,
                server_default='0',
            )
        )

    with op.batch_alter_table('poll_voter_profile') as batch_op:
        batch_op.alter_column('points_accrued_total', server_default=None)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'poll_voter_profile' not in inspector.get_table_names():
        return

    existing_columns = {col['name'] for col in inspector.get_columns('poll_voter_profile')}
    if 'points_accrued_total' not in existing_columns:
        return

    with op.batch_alter_table('poll_voter_profile') as batch_op:
        batch_op.drop_column('points_accrued_total')
