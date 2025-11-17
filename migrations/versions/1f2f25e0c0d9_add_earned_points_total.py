"""add earned_points_total to poll voter profile

Revision ID: 1f2f25e0c0d9
Revises: c2f0bb848b2d
Create Date: 2025-10-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1f2f25e0c0d9'
down_revision = 'c2f0bb848b2d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('poll_voter_profile', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('earned_points_total', sa.Integer(), nullable=False, server_default='0')
        )
        batch_op.alter_column('earned_points_total', server_default=None)


def downgrade():
    with op.batch_alter_table('poll_voter_profile', schema=None) as batch_op:
        batch_op.drop_column('earned_points_total')
