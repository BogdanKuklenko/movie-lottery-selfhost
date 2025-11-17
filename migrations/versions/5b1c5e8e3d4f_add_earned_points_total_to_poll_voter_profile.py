"""add earned_points_total to poll voter profile

Revision ID: 5b1c5e8e3d4f
Revises: 0b2e3e72e167
Create Date: 2025-02-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '5b1c5e8e3d4f'
down_revision = '0b2e3e72e167'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'poll_voter_profile',
        sa.Column('earned_points_total', sa.Integer(), nullable=False, server_default='0'),
    )
    op.alter_column('poll_voter_profile', 'earned_points_total', server_default=None)


def downgrade():
    op.drop_column('poll_voter_profile', 'earned_points_total')
