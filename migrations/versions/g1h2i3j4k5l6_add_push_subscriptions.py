"""Add push_subscription table and notifications_enabled to profile

Revision ID: g1h2i3j4k5l6
Revises: h1i2j3k4l5m6
Create Date: 2025-12-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g1h2i3j4k5l6'
down_revision = 'h1i2j3k4l5m6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Создаём таблицу push_subscription
    if 'push_subscription' not in inspector.get_table_names():
        op.create_table(
            'push_subscription',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column(
                'voter_token',
                sa.String(64),
                sa.ForeignKey('poll_voter_profile.token', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('endpoint', sa.Text(), nullable=False, unique=True),
            sa.Column('p256dh_key', sa.Text(), nullable=False),
            sa.Column('auth_key', sa.Text(), nullable=False),
            sa.Column(
                'created_at',
                sa.DateTime(),
                nullable=False,
                server_default=sa.text('CURRENT_TIMESTAMP'),
            ),
        )
        # Индекс для быстрого поиска по voter_token
        op.create_index(
            'ix_push_subscription_voter_token',
            'push_subscription',
            ['voter_token'],
        )

    # Добавляем notifications_enabled в poll_voter_profile
    if 'poll_voter_profile' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('poll_voter_profile')}
        
        if 'notifications_enabled' not in existing_columns:
            with op.batch_alter_table('poll_voter_profile', schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        'notifications_enabled',
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.text('FALSE'),
                    )
                )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Удаляем колонку notifications_enabled
    if 'poll_voter_profile' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('poll_voter_profile')}
        
        if 'notifications_enabled' in existing_columns:
            with op.batch_alter_table('poll_voter_profile', schema=None) as batch_op:
                batch_op.drop_column('notifications_enabled')

    # Удаляем таблицу push_subscription
    if 'push_subscription' in inspector.get_table_names():
        op.drop_index('ix_push_subscription_voter_token', table_name='push_subscription')
        op.drop_table('push_subscription')

