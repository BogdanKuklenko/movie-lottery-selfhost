"""Add points_accrued_total to poll_voter_profile

Revision ID: 1f4d79d2663e
Revises: bae28d248f18
Create Date: 2025-06-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1f4d79d2663e'
down_revision = 'bae28d248f18'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'poll_voter_profile' not in inspector.get_table_names():
        return

    existing_columns = {column['name'] for column in inspector.get_columns('poll_voter_profile')}
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

    existing_columns = {column['name'] for column in inspector.get_columns('poll_voter_profile')}
    if 'points_accrued_total' not in existing_columns:
        return

    with op.batch_alter_table('poll_voter_profile') as batch_op:
        batch_op.drop_column('points_accrued_total')
