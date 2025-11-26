import click
from flask.cli import with_appcontext
from sqlalchemy import func

from . import db
from .models import PollVoterProfile, Vote


def register_cli(app):
    @app.cli.command("backfill-poll-voter-points")
    @with_appcontext
    def backfill_poll_voter_points():
        """Backfill points_accrued_total using historical positive vote awards."""
        results = (
            db.session.query(Vote.voter_token, func.sum(Vote.points_awarded))
            .filter(Vote.points_awarded > 0)
            .group_by(Vote.voter_token)
            .all()
        )

        updated = 0
        skipped_missing_profiles = 0

        for voter_token, total_awarded in results:
            profile = PollVoterProfile.query.get(voter_token)
            if not profile:
                skipped_missing_profiles += 1
                continue

            new_total = int(total_awarded or 0)
            if profile.points_accrued_total != new_total:
                profile.points_accrued_total = new_total
                updated += 1

        db.session.commit()

        click.echo(f"Processed {len(results)} voter tokens with positive awards.")
        click.echo(f"Updated {updated} profiles.")
        if skipped_missing_profiles:
            click.echo(
                f"Skipped {skipped_missing_profiles} tokens with missing profiles."
            )
