"""add poll_settings table

Revision ID: a6a3b6c6d4d9
Revises: 0b2e3e72e167
Create Date: 2025-02-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a6a3b6c6d4d9'
down_revision = '0b2e3e72e167'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table('poll_settings'):
        return

    op.create_table(
        'poll_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('custom_vote_cost', sa.Integer(), nullable=False, server_default=sa.text('10')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
    )

    op.execute(
        sa.text(
            "INSERT INTO poll_settings (id, custom_vote_cost)"
            " SELECT 1, 10"
            " WHERE NOT EXISTS (SELECT 1 FROM poll_settings WHERE id = 1)"
        )
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table('poll_settings'):
        op.drop_table('poll_settings')
