"""add earned_points_total to poll_voter_profile"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6c02aafab4f4'
down_revision = '9d5eb7c9c2af'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    added_column = False
    if inspector.has_table('poll_voter_profile'):
        column_names = {col['name'] for col in inspector.get_columns('poll_voter_profile')}
        if 'earned_points_total' not in column_names:
            op.add_column(
                'poll_voter_profile',
                sa.Column('earned_points_total', sa.Integer(), nullable=False, server_default='0'),
            )
            added_column = True

    _backfill_earned_points(bind)

    if added_column:
        op.alter_column(
            'poll_voter_profile',
            'earned_points_total',
            existing_type=sa.Integer(),
            server_default=None,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table('poll_voter_profile'):
        column_names = {col['name'] for col in inspector.get_columns('poll_voter_profile')}
        if 'earned_points_total' in column_names:
            op.drop_column('poll_voter_profile', 'earned_points_total')


def _backfill_earned_points(bind):
    inspector = sa.inspect(bind)
    if not inspector.has_table('poll_voter_profile'):
        return

    metadata = sa.MetaData()
    profile_table = sa.Table('poll_voter_profile', metadata, autoload_with=bind)

    vote_table = None
    if inspector.has_table('vote'):
        vote_table = sa.Table('vote', metadata, autoload_with=bind)

    earned_totals = {}
    if vote_table is not None:
        earned_expr = sa.func.sum(
            sa.case((vote_table.c.points_awarded > 0, vote_table.c.points_awarded), else_=0)
        )
        result = bind.execute(
            sa.select(vote_table.c.voter_token, earned_expr).group_by(vote_table.c.voter_token)
        )
        earned_totals = {row[0]: row[1] or 0 for row in result if row[0]}

    if not earned_totals:
        bind.execute(profile_table.update().values(earned_points_total=0))
        return

    for token, total in earned_totals.items():
        bind.execute(
            profile_table.update()
            .where(profile_table.c.token == token)
            .values(earned_points_total=int(total))
        )
