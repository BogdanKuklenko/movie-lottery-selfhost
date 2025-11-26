from flask import Blueprint, render_template, current_app, request
from sqlalchemy.exc import OperationalError, ProgrammingError

from .. import db
from ..models import Lottery, LibraryMovie, MovieIdentifier, Poll
from ..utils.helpers import (
    get_background_photos,
    build_external_url,
    build_telegram_share_url,
    get_custom_vote_cost,
)

main_bp = Blueprint('main', __name__)


@main_bp.app_context_processor
def inject_poll_settings():
    return {
        'poll_api_base_url': current_app.config.get('POLL_API_BASE_URL'),
    }


def _get_custom_vote_cost():
    return get_custom_vote_cost()

@main_bp.route('/health')
def health():
    """Health check endpoint for Render.com monitoring"""
    return {"status": "ok"}, 200

@main_bp.route('/')
def index():
    return render_template('index.html', background_photos=get_background_photos())

@main_bp.route('/wait/<lottery_id>')
def wait_for_result(lottery_id):
    lottery = Lottery.query.get_or_404(lottery_id)
    play_url = build_external_url('main.play_lottery', lottery_id=lottery.id)
    telegram_share_url = build_telegram_share_url(play_url)
    return render_template(
        'wait.html',
        lottery_id=lottery_id,
        background_photos=get_background_photos(),
        play_url=play_url,
        telegram_share_url=telegram_share_url,
    )

@main_bp.route('/history')
def history():
    lotteries = Lottery.query.order_by(Lottery.created_at.desc()).all()
    
    # Collect all unique kinopoisk IDs from winners to avoid N+1 queries
    kp_ids = set()
    for lottery in lotteries:
        winner_movie = next((m for m in lottery.movies if m.name == lottery.result_name), None)
        if winner_movie and winner_movie.kinopoisk_id:
            kp_ids.add(winner_movie.kinopoisk_id)
            winner_movie.is_on_client = False
            winner_movie.torrent_hash = None
    
    # Fetch all identifiers in one query
    identifiers = {}
    if kp_ids:
        identifier_list = MovieIdentifier.query.filter(MovieIdentifier.kinopoisk_id.in_(kp_ids)).all()
        identifiers = {i.kinopoisk_id: i for i in identifier_list}

    return render_template(
        'history.html',
        lotteries=lotteries,
        identifiers=identifiers,
        background_photos=get_background_photos()
    )

@main_bp.route('/library')
def library():
    # Обновляем истёкшие баны перед отображением списка
    if LibraryMovie.refresh_all_bans():
        db.session.commit()

    try:
        library_movies = LibraryMovie.query.order_by(LibraryMovie.bumped_at.desc()).all()
    except (OperationalError, ProgrammingError) as exc:
        current_app.logger.warning(
            "LibraryMovie.bumped_at unavailable, falling back to added_at sorting. "
            "Run pending migrations. Error: %s",
            exc,
        )
        library_movies = LibraryMovie.query.order_by(LibraryMovie.added_at.desc()).all()
    
    # Fetch all identifiers in one query to avoid N+1
    kp_ids = [m.kinopoisk_id for m in library_movies if m.kinopoisk_id]
    identifiers_map = {}
    if kp_ids:
        identifiers = MovieIdentifier.query.filter(MovieIdentifier.kinopoisk_id.in_(kp_ids)).all()
        identifiers_map = {i.kinopoisk_id: i for i in identifiers}
    
    for movie in library_movies:
        identifier = identifiers_map.get(movie.kinopoisk_id)
        movie.has_magnet = bool(identifier)
        movie.magnet_link = identifier.magnet_link if identifier else ''
        movie.is_on_client = False
        movie.torrent_hash = None
            
    return render_template(
        'library.html',
        library_movies=library_movies,
        background_photos=get_background_photos()
    )

@main_bp.route('/l/<lottery_id>')
def play_lottery(lottery_id):
    lottery = Lottery.query.get_or_404(lottery_id)
    result_obj = {
        "name": lottery.result_name, 
        "poster": lottery.result_poster, 
        "year": lottery.result_year
    } if lottery.result_name else None
    
    return render_template(
        'play.html', 
        lottery=lottery, 
        result=result_obj, 
        background_photos=get_background_photos()
    )

@main_bp.route('/p/<poll_id>')
def view_poll(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    return render_template(
        'poll.html',
        poll=poll,
        custom_vote_cost=_get_custom_vote_cost(),
        background_photos=get_background_photos()
    )


@main_bp.route('/p/<poll_id>/results')
def view_poll_results(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    return render_template(
        'poll_results.html',
        poll=poll,
        poll_url=build_external_url('main.view_poll', poll_id=poll.id),
        background_photos=get_background_photos(),
    )


@main_bp.route('/admin/poll-points')
def admin_poll_points():
    return render_template('admin_poll_points.html')

@main_bp.route('/admin/init-db', methods=['POST'])
def init_db():
    """
    Initialize or reinitialize the database.
    Requires the ADMIN_SECRET_KEY environment variable to be set correctly.
    Only accessible via POST request with proper secret key in Authorization header.
    """
    import os
    
    # Get admin secret from environment
    admin_secret = os.environ.get('ADMIN_SECRET_KEY')
    if not admin_secret:
        return {"error": "Admin initialization disabled (ADMIN_SECRET_KEY not set)"}, 403
    
    # Check Authorization header
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return {"error": "Missing or invalid Authorization header"}, 401
    
    provided_secret = auth_header[7:]  # Remove 'Bearer ' prefix
    if provided_secret != admin_secret:
        current_app.logger.warning(f"Failed init_db attempt with incorrect secret from {request.remote_addr}")
        return {"error": "Invalid secret key"}, 403
    
    try:
        from .. import db
        with db.get_app().app_context():
            db.drop_all()
            db.create_all()
        return {"status": "success", "message": "Database reinitialized"}, 200
    except Exception as e:
        current_app.logger.error(f"Error reinitializing database: {str(e)}")
        return {"error": "Database reinitialization failed"}, 500
