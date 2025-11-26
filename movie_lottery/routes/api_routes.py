import calendar
import random
import re
import secrets
from collections import defaultdict
from datetime import datetime, time, timezone
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from .. import db
from ..models import (
    Movie,
    Lottery,
    MovieIdentifier,
    LibraryMovie,
    Poll,
    PollCreatorToken,
    PollMovie,
    PollVoterProfile,
    Vote,
)
from ..utils.kinopoisk import get_movie_data_from_kinopoisk
from ..utils.helpers import (
    build_external_url,
    build_telegram_share_url,
    change_voter_points_balance,
    ensure_background_photo,
    ensure_poll_tables,
    ensure_voter_profile,
    ensure_voter_profile_for_user,
    generate_unique_id,
    generate_unique_poll_id,
    get_custom_vote_cost,
    get_poll_settings,
    prevent_caching,
    rotate_voter_token,
    update_poll_settings,
)

api_bp = Blueprint('api', __name__, url_prefix='/api')


POLL_CREATOR_COOKIE = 'poll_creator_token'
POLL_CREATOR_HEADER = 'X-Poll-Creator-Token'
POLL_CREATOR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year
VOTER_TOKEN_COOKIE = 'voter_token'
VOTER_TOKEN_HEADER = 'X-Poll-Voter-Token'
VOTER_USER_ID_COOKIE = 'voter_user_id'
VOTER_USER_ID_HEADER = 'X-Poll-User-Id'
VOTER_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
_CREATOR_TOKEN_RE = re.compile(r'^[a-f0-9]{32}$', re.IGNORECASE)
_VOTER_TOKEN_RE = re.compile(r'^[a-f0-9]{32}$', re.IGNORECASE)


def _resolve_device_label():
    header_label = request.headers.get('X-Device-Label')
    if header_label:
        return header_label[:255]

    user_agent = getattr(request, 'user_agent', None)
    if user_agent:
        agent_str = getattr(user_agent, 'string', None)
        if agent_str:
            return agent_str[:255]

    return None


def _normalize_device_label(raw_label=None):
    if isinstance(raw_label, str):
        trimmed = raw_label.strip()
        if trimmed:
            return trimmed[:255]
    return None


def _get_json_payload():
    """Возвращает тело запроса в формате JSON или None, если оно некорректно."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _get_custom_vote_cost():
    return get_custom_vote_cost()


def _serialize_library_movie(movie):
    return {
        'id': movie.id,
        'kinopoisk_id': movie.kinopoisk_id,
        'name': movie.name,
        'search_name': movie.search_name,
        'year': movie.year,
        'poster': movie.poster,
        'description': movie.description,
        'rating_kp': movie.rating_kp,
        'genres': movie.genres,
        'countries': movie.countries,
        'badge': movie.badge,
        'points': movie.points if movie.points is not None else 1,
        'ban_until': movie.ban_until.isoformat() if movie.ban_until else None,
        'ban_status': movie.ban_status,
        'ban_remaining_seconds': movie.ban_remaining_seconds,
        'ban_applied_by': movie.ban_applied_by,
        'ban_cost': movie.ban_cost,
        'ban_cost_per_month': movie.ban_cost_per_month,
    }


def _refresh_library_bans():
    if LibraryMovie.refresh_all_bans():
        db.session.commit()


def _serialize_poll_settings(settings):
    return {
        'custom_vote_cost': _get_custom_vote_cost(),
        'updated_at': settings.updated_at.isoformat() + 'Z' if settings and settings.updated_at else None,
        'created_at': settings.created_at.isoformat() + 'Z' if settings and settings.created_at else None,
    }


def _read_creator_token_from_request():
    raw_token = request.cookies.get(POLL_CREATOR_COOKIE) or request.headers.get(POLL_CREATOR_HEADER)
    if not raw_token:
        return None
    token = raw_token.strip().lower()
    return token if _CREATOR_TOKEN_RE.match(token) else None


def _touch_creator_token(token):
    if not token:
        return

    now = datetime.utcnow()
    try:
        record = PollCreatorToken.query.filter_by(creator_token=token).first()
    except (ProgrammingError, OperationalError) as exc:
        db.session.rollback()
        logger = getattr(current_app, 'logger', None)
        if logger:
            logger.warning('Таблица poll_creator_token недоступна: %s', exc)
        return

    if record:
        record.last_seen = now
    else:
        db.session.add(PollCreatorToken(creator_token=token, created_at=now, last_seen=now))


def _get_or_issue_creator_token():
    token = _read_creator_token_from_request()
    issued_new = False
    if not token:
        token = secrets.token_hex(16)
        issued_new = True

    _touch_creator_token(token)
    return token, issued_new


def _set_creator_cookie(response, token):
    if not response or not token:
        return response

    response.set_cookie(
        POLL_CREATOR_COOKIE,
        token,
        max_age=POLL_CREATOR_COOKIE_MAX_AGE,
        samesite='Lax',
        secure=request.is_secure,
    )
    return response


def _normalize_user_id(raw_value):
    if raw_value is None:
        return None

    user_id = str(raw_value).strip()
    return user_id[:128] if user_id else None


def _suggest_user_ids(preferred, limit=3):
    base = _normalize_user_id(preferred)
    if not base or limit <= 0:
        return []

    try:
        existing_ids = {
            row[0]
            for row in db.session.query(PollVoterProfile.user_id)
            .filter(PollVoterProfile.user_id.isnot(None))
            .all()
        }
    except (ProgrammingError, OperationalError):
        existing_ids = set()

    suggestions = []
    suffix = 1
    separator = '-' if base and base[-1].isdigit() else ' '

    while len(suggestions) < limit and suffix < 10_000:
        candidate = f"{base}{separator}{suffix}"[:128]
        if candidate != base and candidate not in existing_ids:
            suggestions.append(candidate)
            existing_ids.add(candidate)
        suffix += 1

    return suggestions


def _read_user_id_from_request():
    raw_user_id = request.cookies.get(VOTER_USER_ID_COOKIE) or request.headers.get(VOTER_USER_ID_HEADER)
    return _normalize_user_id(raw_user_id)


def _set_voter_cookies(response, voter_token, user_id=None):
    if not response or not voter_token:
        return response

    response.set_cookie(
        VOTER_TOKEN_COOKIE,
        voter_token,
        max_age=VOTER_COOKIE_MAX_AGE,
        samesite='Lax',
        secure=request.is_secure,
    )

    if user_id:
        response.set_cookie(
            VOTER_USER_ID_COOKIE,
            user_id,
            max_age=VOTER_COOKIE_MAX_AGE,
            samesite='Lax',
            secure=request.is_secure,
        )

    return response


def _read_voter_token_from_request():
    raw_voter_token = request.headers.get(VOTER_TOKEN_HEADER) or request.args.get('voter_token')
    if isinstance(raw_voter_token, str):
        trimmed = raw_voter_token.strip()
        if _VOTER_TOKEN_RE.match(trimmed):
            return trimmed
    return None


def _resolve_voter_identity():
    device_label = _resolve_device_label()
    user_id = _read_user_id_from_request()

    raw_voter_token = _read_voter_token_from_request()

    if user_id:
        profile = ensure_voter_profile_for_user(user_id, device_label=device_label)
        voter_token = profile.token
    else:
        voter_token = raw_voter_token or request.cookies.get(VOTER_TOKEN_COOKIE)
        profile = None

        if voter_token:
            profile = ensure_voter_profile(voter_token, device_label=device_label)
        elif device_label:
            try:
                profile = (
                    PollVoterProfile.query.filter_by(device_label=device_label)
                    .order_by(PollVoterProfile.updated_at.desc())
                    .first()
                )
            except (ProgrammingError, OperationalError):
                profile = None

            if profile:
                voter_token = profile.token

        if profile is None:
            voter_token = voter_token or secrets.token_hex(16)
            profile = ensure_voter_profile(voter_token, device_label=device_label)

    return {
        'voter_token': voter_token,
        'profile': profile,
        'user_id': user_id,
        'device_label': device_label,
        'requested_voter_token': raw_voter_token,
    }


@api_bp.route('/polls/settings', methods=['GET'])
def get_poll_settings_api():
    settings = get_poll_settings()
    payload = _serialize_poll_settings(settings)
    payload['source'] = 'database' if settings else 'default'
    return prevent_caching(jsonify(payload))


@api_bp.route('/polls/settings', methods=['PATCH'])
def update_poll_settings_api():
    data = _get_json_payload()
    if data is None or 'custom_vote_cost' not in data:
        return jsonify({'error': 'Передайте custom_vote_cost в теле запроса'}), 400

    new_cost = data.get('custom_vote_cost')
    if isinstance(new_cost, bool) or not isinstance(new_cost, int):
        return jsonify({'error': 'custom_vote_cost должен быть целым числом'}), 400
    if new_cost < 0:
        return jsonify({'error': 'custom_vote_cost не может быть отрицательным'}), 400

    settings = update_poll_settings(custom_vote_cost=new_cost)
    if not settings:
        return jsonify({'error': 'Сервис настроек временно недоступен'}), 503

    return prevent_caching(jsonify(_serialize_poll_settings(settings)))


@api_bp.route('/polls/auth/login', methods=['POST'])
def login_with_user_id():
    data = _get_json_payload()
    if data is None or 'user_id' not in data:
        return jsonify({'error': 'Передайте user_id в теле запроса'}), 400

    user_id = _normalize_user_id(data.get('user_id'))
    if not user_id:
        return jsonify({'error': 'Некорректный user_id'}), 400

    raw_label = data.get('device_label') if isinstance(data, dict) else None
    device_label = _normalize_device_label(raw_label) or _resolve_device_label()

    try:
        profile = ensure_voter_profile_for_user(user_id, device_label=device_label)
        db.session.commit()
    except ValueError:
        return jsonify({'error': 'user_id обязателен'}), 400

    points_earned_total = profile.points_accrued_total or 0
    payload = {
        'user_id': user_id,
        'voter_token': profile.token,
        'device_label': profile.device_label,
        'points_balance': profile.total_points or 0,
        'points_earned_total': points_earned_total,
        'points_accrued_total': points_earned_total,
        'created_at': profile.created_at.isoformat() if profile.created_at else None,
        'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
    }

    response = prevent_caching(jsonify(payload))
    return _set_voter_cookies(response, profile.token, profile.user_id)


@api_bp.route('/polls/auth/register', methods=['POST'])
def register_user_id():
    data = _get_json_payload()
    if data is None or 'user_id' not in data:
        return jsonify({'error': 'Передайте user_id в теле запроса'}), 400

    user_id = _normalize_user_id(data.get('user_id'))
    if not user_id:
        return jsonify({'error': 'Некорректный user_id'}), 400

    device_label = _normalize_device_label(data.get('device_label')) or _resolve_device_label()

    def _build_profile_payload(profile_obj):
        points_earned_total = profile_obj.points_accrued_total or 0
        return {
            'success': True,
            'user_id': profile_obj.user_id,
            'voter_token': profile_obj.token,
            'device_label': profile_obj.device_label,
            'points_balance': profile_obj.total_points or 0,
            'points_earned_total': points_earned_total,
            'points_accrued_total': points_earned_total,
            'created_at': profile_obj.created_at.isoformat() if profile_obj.created_at else None,
            'updated_at': profile_obj.updated_at.isoformat() if profile_obj.updated_at else None,
        }

    try:
        existing = PollVoterProfile.query.filter_by(user_id=user_id).first()
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return jsonify({'error': 'Сервис временно недоступен'}), 503

    if existing:
        try:
            profile = ensure_voter_profile_for_user(user_id, device_label=device_label)
            db.session.commit()
        except ValueError:
            return jsonify({'error': 'user_id обязателен'}), 400

        payload = _build_profile_payload(profile)
        response = prevent_caching(jsonify(payload))
        return _set_voter_cookies(response, profile.token, profile.user_id)

    desired_token = request.cookies.get(VOTER_TOKEN_COOKIE) or secrets.token_hex(16)
    profile = ensure_voter_profile(desired_token, device_label=device_label)

    if profile.user_id and profile.user_id != user_id:
        desired_token = secrets.token_hex(16)
        profile = ensure_voter_profile(desired_token, device_label=device_label)

    profile.user_id = user_id
    profile.updated_at = datetime.utcnow()

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        try:
            profile = ensure_voter_profile_for_user(user_id, device_label=device_label)
            db.session.commit()
        except ValueError:
            return jsonify({'error': 'user_id обязателен'}), 400
        except (ProgrammingError, OperationalError):
            db.session.rollback()
            return jsonify({'error': 'Сервис временно недоступен'}), 503
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return jsonify({'error': 'Сервис временно недоступен'}), 503

    payload = _build_profile_payload(profile)
    response = prevent_caching(jsonify(payload))
    return _set_voter_cookies(response, profile.token, profile.user_id)


@api_bp.route('/polls/auth/logout', methods=['POST'])
def logout_with_user_id():
    data = _get_json_payload() or {}
    raw_label = data.get('device_label') if isinstance(data, dict) else None
    device_label = _normalize_device_label(raw_label) or _resolve_device_label()
    voter_token = request.cookies.get(VOTER_TOKEN_COOKIE)
    user_id = _normalize_user_id(data.get('user_id') if isinstance(data, dict) else None) or _read_user_id_from_request()

    rotate_token = isinstance(data, dict) and bool(data.get('rotate_token'))

    try:
        if user_id:
            profile = ensure_voter_profile_for_user(user_id, device_label=device_label)
        elif voter_token:
            profile = ensure_voter_profile(voter_token, device_label=device_label)
        else:
            return jsonify({'error': 'Не удалось определить профиль для выхода'}), 400

        previous_token = profile.token
        new_token = rotate_voter_token(profile) if rotate_token else None
        db.session.commit()
    except ValueError:
        return jsonify({'error': 'Не удалось определить профиль для выхода'}), 400
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return jsonify({'error': 'Сервис временно недоступен'}), 503

    payload = {
        'success': True,
        'user_id': profile.user_id,
        'voter_token': profile.token,
        'previous_token': previous_token,
        'rotated_token': new_token,
        'points_balance': profile.total_points or 0,
        'points_earned_total': profile.points_accrued_total or 0,
        'device_label': profile.device_label,
        'created_at': profile.created_at.isoformat() if profile.created_at else None,
        'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
    }

    response = prevent_caching(jsonify(payload))
    response.set_cookie(
        VOTER_TOKEN_COOKIE,
        '',
        max_age=0,
        samesite='Lax',
        secure=request.is_secure,
    )
    response.set_cookie(
        VOTER_USER_ID_COOKIE,
        '',
        max_age=0,
        samesite='Lax',
        secure=request.is_secure,
    )
    return response


def _parse_iso_date(raw_value, for_end=False):
    if not raw_value:
        return None

    value = str(raw_value).strip()
    if not value:
        return None

    normalized = value.replace('Z', '+00:00') if value.endswith('Z') else value
    date_only = 'T' not in normalized and ' ' not in normalized and '+' not in normalized

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

    if date_only and for_end:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)

    return parsed


def _align_to_end_of_day(dt):
    return datetime.combine(dt.date(), time(23, 59, 59))


def _add_months(dt, months):
    total_months = dt.month - 1 + months
    year = dt.year + total_months // 12
    month = total_months % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


def _calculate_ban_until(base_time, months):
    end_of_base_day = _align_to_end_of_day(base_time)
    return _add_months(end_of_base_day, months)


def _prepare_voter_filters(args):
    token = (args.get('token') or '').strip()
    poll_id = (args.get('poll_id') or '').strip()
    device_label = (args.get('device_label') or '').strip()
    user_id = _normalize_user_id(args.get('user_id'))
    date_from = _parse_iso_date(args.get('date_from'))
    date_to = _parse_iso_date(args.get('date_to'), for_end=True)

    requires_vote_filters = any([poll_id, date_from, date_to])

    return {
        'token': token,
        'poll_id': poll_id,
        'device_label': device_label,
        'user_id': user_id,
        'date_from': date_from,
        'date_to': date_to,
        'requires_vote_filters': requires_vote_filters,
    }


def _apply_vote_filters(query, filters):
    poll_id = filters.get('poll_id')
    date_from = filters.get('date_from')
    date_to = filters.get('date_to')

    if poll_id:
        query = query.filter(Vote.poll_id == poll_id)
    if date_from:
        query = query.filter(Vote.voted_at >= date_from)
    if date_to:
        query = query.filter(Vote.voted_at <= date_to)
    return query


def _group_votes_by_token(tokens, filters):
    votes_by_token = defaultdict(list)
    if not tokens:
        return votes_by_token

    vote_query = (
        db.session.query(Vote, Poll, PollMovie)
        .join(Poll, Vote.poll_id == Poll.id)
        .join(PollMovie, Vote.movie_id == PollMovie.id)
        .filter(Vote.voter_token.in_(tokens))
    )

    vote_query = _apply_vote_filters(vote_query, filters)
    vote_query = vote_query.order_by(Vote.voted_at.desc())

    for vote, poll, poll_movie in vote_query.all():
        votes_by_token[vote.voter_token].append({
            'poll_id': vote.poll_id,
            'poll_title': getattr(poll, 'title', None),
            'poll_created_at': poll.created_at.isoformat() if poll and poll.created_at else None,
            'poll_expires_at': poll.expires_at.isoformat() if poll and poll.expires_at else None,
            'movie_id': vote.movie_id,
            'movie_name': poll_movie.name if poll_movie else None,
            'movie_year': poll_movie.year if poll_movie else None,
            'points_awarded': vote.points_awarded,
            'voted_at': vote.voted_at.isoformat() if vote.voted_at else None,
        })

    return votes_by_token


def _serialize_poll_movie(movie):
    if not movie:
        return None

    # Получаем индивидуальную цену за месяц бана из библиотеки, если фильм там есть
    ban_cost_per_month = None
    if movie.kinopoisk_id:
        library_movie = LibraryMovie.query.filter_by(kinopoisk_id=movie.kinopoisk_id).first()
        if library_movie and library_movie.ban_cost_per_month is not None:
            ban_cost_per_month = library_movie.ban_cost_per_month
    elif movie.name and movie.year:
        library_movie = LibraryMovie.query.filter_by(name=movie.name, year=movie.year).first()
        if library_movie and library_movie.ban_cost_per_month is not None:
            ban_cost_per_month = library_movie.ban_cost_per_month

    return {
        "id": movie.id,
        "kinopoisk_id": movie.kinopoisk_id,
        "name": movie.name,
        "search_name": movie.search_name,
        "poster": movie.poster,
        "year": movie.year,
        "description": movie.description,
        "rating_kp": movie.rating_kp,
        "genres": movie.genres,
        "countries": movie.countries,
        "points": movie.points if movie.points is not None else 1,
        "ban_until": movie.ban_until.isoformat() if getattr(movie, 'ban_until', None) else None,
        "ban_status": getattr(movie, 'ban_status', 'none'),
        "ban_remaining_seconds": getattr(movie, 'ban_remaining_seconds', 0),
        "ban_cost_per_month": ban_cost_per_month,
    }


def _is_movie_banned_for_poll(movie_data):
    ban_status = str(movie_data.get('ban_status') or '').lower()
    if ban_status in {'active', 'pending'}:
        return True

    library_movie = None
    movie_id = movie_data.get('id')
    if movie_id:
        library_movie = LibraryMovie.query.get(movie_id)
    elif movie_data.get('kinopoisk_id'):
        library_movie = LibraryMovie.query.filter_by(kinopoisk_id=movie_data.get('kinopoisk_id')).first()
    elif movie_data.get('name') and movie_data.get('year'):
        library_movie = LibraryMovie.query.filter_by(
            name=movie_data.get('name'),
            year=movie_data.get('year'),
        ).first()

    if library_movie and library_movie.badge == 'ban':
        return library_movie.ban_status in {'active', 'pending'}

    return False


def _check_movies_banned_batch(movies_data):
    """
    Batch-check multiple movies for ban status to avoid N+1 queries.
    Returns a set of banned movie data (uses index-based identification).
    """
    banned_indices = set()
    
    # Quick check: movies with direct ban_status
    for idx, movie_data in enumerate(movies_data):
        ban_status = str(movie_data.get('ban_status') or '').lower()
        if ban_status in {'active', 'pending'}:
            banned_indices.add(idx)
    
    # Batch fetch library movies by kinopoisk_id
    kinopoisk_ids = [
        movie['kinopoisk_id'] 
        for idx, movie in enumerate(movies_data) 
        if idx not in banned_indices and movie.get('kinopoisk_id')
    ]
    
    if kinopoisk_ids:
        library_movies_by_kp = {
            m.kinopoisk_id: m 
            for m in LibraryMovie.query.filter(LibraryMovie.kinopoisk_id.in_(kinopoisk_ids)).all()
        }
    else:
        library_movies_by_kp = {}
    
    # Check by name/year for movies without kinopoisk_id
    name_year_pairs = [
        (movie['name'], movie['year'], idx)
        for idx, movie in enumerate(movies_data) 
        if idx not in banned_indices 
        and not movie.get('kinopoisk_id') 
        and movie.get('name') 
        and movie.get('year')
    ]
    
    if name_year_pairs:
        names = [pair[0] for pair in name_year_pairs]
        years = [pair[1] for pair in name_year_pairs]
        library_movies_by_name_year = {
            (m.name, m.year): m 
            for m in LibraryMovie.query.filter(
                LibraryMovie.name.in_(names),
                LibraryMovie.year.in_(years)
            ).all()
        }
    else:
        library_movies_by_name_year = {}
    
    # Mark banned movies
    for idx, movie in enumerate(movies_data):
        if idx in banned_indices:
            continue
            
        library_movie = None
        
        if movie.get('kinopoisk_id'):
            library_movie = library_movies_by_kp.get(movie['kinopoisk_id'])
        elif movie.get('name') and movie.get('year'):
            library_movie = library_movies_by_name_year.get((movie['name'], movie['year']))
        
        if library_movie and library_movie.badge == 'ban':
            if library_movie.ban_status in {'active', 'pending'}:
                banned_indices.add(idx)
    
    return banned_indices


def _get_active_poll_movies(poll):
    return [movie for movie in poll.movies if not getattr(movie, 'is_banned', False)]


def _normalize_poll_movie_points(raw_value, default=1):
    try:
        normalized_default = int(default)
    except (TypeError, ValueError):
        normalized_default = 1

    try:
        points = int(raw_value)
    except (TypeError, ValueError):
        points = normalized_default

    return max(0, min(999, points))

# --- Routes for movies and lotteries ---

@api_bp.route('/fetch-movie', methods=['POST'])
def get_movie_info():
    payload = _get_json_payload()
    if payload is None:
        return jsonify({"error": "Некорректный JSON-запрос"}), 400

    query = payload.get('query')
    if not query:
        return jsonify({"error": "Пустой запрос"}), 400
    movie_data, error = get_movie_data_from_kinopoisk(query)
    if movie_data:
        # Add poster to background when fetched from Kinopoisk
        if poster := movie_data.get('poster'):
            ensure_background_photo(poster)
        current_app.logger.info(
            "Успешно получены данные Кинопоиска для запроса '%s'.", query
        )
        return jsonify(movie_data)
    if error:
        code = error.get('code')
        message = error.get('message') or 'Неизвестная ошибка при обращении к Кинопоиску.'

        if code == 'missing_token':
            current_app.logger.error(message)
            payload = {"error": message, "message": message, "code": code}
            return jsonify(payload), 503

        if code == 'http_error':
            status = error.get('status') or 502
            current_app.logger.warning(message)
            current_app.logger.debug(
                "Kinopoisk API error (%s) for query '%s'.", status, query
            )
            payload = {"error": message, "message": message, "code": code, "status": status}
            return jsonify(payload), status

        if code == 'network_error':
            current_app.logger.error(message)
            payload = {"error": message, "message": message, "code": code}
            return jsonify(payload), 502

        current_app.logger.error(message)
        payload = {"error": message, "message": message, "code": code}
        return jsonify(payload), 500

    not_found_message = "Фильм не найден"
    current_app.logger.info(not_found_message)
    current_app.logger.debug("Фильм не найден для запроса '%s'.", query)
    return jsonify({"error": not_found_message, "message": not_found_message}), 404

@api_bp.route('/create', methods=['POST'])
def create_lottery():
    payload = _get_json_payload()
    if payload is None:
        return jsonify({"error": "Некорректный JSON-запрос"}), 400

    movies_json = payload.get('movies')
    if not movies_json or len(movies_json) < 2:
        return jsonify({"error": "Нужно добавить хотя бы два фильма"}), 400

    new_lottery = Lottery(id=generate_unique_id())
    db.session.add(new_lottery)

    for movie_data in movies_json:
        new_movie = Movie(
            kinopoisk_id=movie_data.get('kinopoisk_id'),
            name=movie_data['name'],
            search_name=movie_data.get('search_name'),
            poster=movie_data.get('poster'),
            year=movie_data.get('year'),
            description=movie_data.get('description'),
            rating_kp=movie_data.get('rating_kp'),
            genres=movie_data.get('genres'),
            countries=movie_data.get('countries'),
            lottery=new_lottery
        )
        db.session.add(new_movie)
        if poster := movie_data.get('poster'):
            ensure_background_photo(poster)

    db.session.commit()

    wait_url = build_external_url('main.wait_for_result', lottery_id=new_lottery.id)
    return jsonify({"wait_url": wait_url})

@api_bp.route('/draw/<lottery_id>', methods=['POST'])
def draw_winner(lottery_id):
    lottery = Lottery.query.get_or_404(lottery_id)
    if lottery.result_name:
        return jsonify({
            "name": lottery.result_name, 
            "poster": lottery.result_poster, 
            "year": lottery.result_year
        })
    
    winner = random.choice(lottery.movies)
    lottery.result_name = winner.name
    lottery.result_poster = winner.poster
    lottery.result_year = winner.year
    db.session.commit()
    return jsonify({
        "name": winner.name, 
        "poster": winner.poster, 
        "year": winner.year
    })

@api_bp.route('/result/<lottery_id>')
def get_result_data(lottery_id):
    lottery = Lottery.query.get_or_404(lottery_id)
    
    # Collect all kinopoisk IDs to fetch identifiers in one query (avoid N+1)
    kp_ids = [m.kinopoisk_id for m in lottery.movies if m.kinopoisk_id]
    identifiers_map = {}
    if kp_ids:
        identifiers = MovieIdentifier.query.filter(MovieIdentifier.kinopoisk_id.in_(kp_ids)).all()
        identifiers_map = {i.kinopoisk_id: i for i in identifiers}
    
    movies_data = []
    for m in lottery.movies:
        identifier = identifiers_map.get(m.kinopoisk_id)
        movies_data.append({
            "kinopoisk_id": m.kinopoisk_id,
            "name": m.name,
            "search_name": m.search_name,
            "poster": m.poster,
            "year": m.year,
            "description": m.description,
            "rating_kp": m.rating_kp,
            "genres": m.genres,
            "countries": m.countries,
            "has_magnet": bool(identifier),
            "magnet_link": identifier.magnet_link if identifier else None,
            "is_on_client": False,
            "torrent_hash": None
        })

    result_data = next((m for m in movies_data if m["name"] == lottery.result_name), None) if lottery.result_name else None
    play_url = build_external_url('main.play_lottery', lottery_id=lottery.id)
    telegram_share_url = build_telegram_share_url(play_url)
    return jsonify({
        "movies": movies_data,
        "result": result_data,
        "createdAt": lottery.created_at.isoformat() + "Z",
        "play_url": play_url,
        "telegram_share_url": telegram_share_url,
    })
    
@api_bp.route('/delete-lottery/<lottery_id>', methods=['POST'])
def delete_lottery(lottery_id):
    lottery_to_delete = Lottery.query.get_or_404(lottery_id)
    db.session.delete(lottery_to_delete)
    db.session.commit()
    return jsonify({"success": True, "message": "Лотерея успешно удалена."})

# --- Маршруты для Библиотеки ---

@api_bp.route('/library', methods=['GET'])
def get_library_movies():
    _refresh_library_bans()

    try:
        movies = LibraryMovie.query.order_by(LibraryMovie.bumped_at.desc()).all()
    except (OperationalError, ProgrammingError) as exc:
        current_app.logger.warning(
            "LibraryMovie.bumped_at unavailable, falling back to added_at sorting. "
            "Run pending migrations. Error: %s",
            exc,
        )
        movies = LibraryMovie.query.order_by(LibraryMovie.added_at.desc()).all()

    kp_ids = [m.kinopoisk_id for m in movies if m.kinopoisk_id]
    identifiers_map = {}
    if kp_ids:
        identifiers = MovieIdentifier.query.filter(MovieIdentifier.kinopoisk_id.in_(kp_ids)).all()
        identifiers_map = {i.kinopoisk_id: i for i in identifiers}

    payload = []
    for movie in movies:
        data = _serialize_library_movie(movie)
        identifier = identifiers_map.get(movie.kinopoisk_id)
        data['has_magnet'] = bool(identifier)
        data['magnet_link'] = identifier.magnet_link if identifier else ''
        data['is_on_client'] = False
        data['torrent_hash'] = None
        payload.append(data)

    return prevent_caching(jsonify({'movies': payload}))


@api_bp.route('/library', methods=['POST'])
def add_library_movie():
    payload = _get_json_payload()
    if payload is None:
        return jsonify({"success": False, "message": "Некорректный JSON-запрос."}), 400

    movie_data = payload.get('movie', {})
    if not movie_data.get('name'):
        return jsonify({"success": False, "message": "Не удалось определить название фильма."}), 400

    existing_movie = None
    kinopoisk_id = movie_data.get('kinopoisk_id')
    if kinopoisk_id:
        existing_movie = LibraryMovie.query.filter_by(kinopoisk_id=kinopoisk_id).first()

    if not existing_movie:
        existing_movie = LibraryMovie.query.filter_by(
            name=movie_data['name'], 
            year=movie_data.get('year')
        ).first()

    if existing_movie:
        for key, value in movie_data.items():
            if hasattr(existing_movie, key) and value is not None:
                setattr(existing_movie, key, value)
        existing_movie.bumped_at = datetime.utcnow()
        message = "Информация о фильме в библиотеке обновлена."
    else:
        new_movie = LibraryMovie(**movie_data)
        if new_movie.added_at is None:
            now = datetime.utcnow()
            new_movie.added_at = now
            new_movie.bumped_at = now
        else:
            new_movie.bumped_at = new_movie.added_at
        db.session.add(new_movie)
        message = "Фильм добавлен в библиотеку."

    # Add poster to background when movie is added to library
    if poster := movie_data.get('poster'):
        ensure_background_photo(poster)

    db.session.commit()
    return jsonify({"success": True, "message": message})

@api_bp.route('/library/<int:movie_id>', methods=['DELETE'])
def remove_library_movie(movie_id):
    library_movie = LibraryMovie.query.get_or_404(movie_id)
    db.session.delete(library_movie)
    db.session.commit()
    return jsonify({"success": True, "message": "Фильм удален из библиотеки."})


@api_bp.route('/library/<int:movie_id>/points', methods=['PUT'])
def update_library_movie_points(movie_id):
    data = _get_json_payload()
    if data is None:
        return jsonify({"success": False, "message": "Некорректный JSON-запрос."}), 400

    raw_points = data.get('points')
    try:
        points = int(raw_points)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Баллы должны быть целым числом."}), 400

    if points < 0 or points > 999:
        return jsonify({"success": False, "message": "Баллы должны быть в диапазоне от 0 до 999."}), 400

    library_movie = LibraryMovie.query.get_or_404(movie_id)
    library_movie.points = points
    library_movie.bumped_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Баллы обновлены.",
        "points": library_movie.points,
    })


@api_bp.route('/library/<int:movie_id>/ban-cost-per-month', methods=['PUT'])
def update_library_movie_ban_cost_per_month(movie_id):
    """Обновление индивидуальной цены за месяц бана для фильма"""
    data = _get_json_payload()
    if data is None:
        return jsonify({"success": False, "message": "Некорректный JSON-запрос."}), 400

    raw_cost = data.get('ban_cost_per_month')
    
    # Если значение None или null, устанавливаем None (используется значение по умолчанию 1)
    if raw_cost is None:
        library_movie = LibraryMovie.query.get_or_404(movie_id)
        library_movie.ban_cost_per_month = None
        library_movie.bumped_at = datetime.utcnow()
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Цена за месяц бана сброшена к значению по умолчанию.",
            "ban_cost_per_month": None,
        })

    try:
        cost = int(raw_cost)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Цена за месяц бана должна быть целым числом."}), 400

    if cost < 1 or cost > 999:
        return jsonify({"success": False, "message": "Цена за месяц бана должна быть в диапазоне от 1 до 999."}), 400

    library_movie = LibraryMovie.query.get_or_404(movie_id)
    library_movie.ban_cost_per_month = cost
    library_movie.bumped_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Цена за месяц бана обновлена.",
        "ban_cost_per_month": library_movie.ban_cost_per_month,
    })

# --- Маршруты для работы с торрентами ---

@api_bp.route('/movie-magnet', methods=['POST'])
def save_movie_magnet():
    data = _get_json_payload()
    if data is None:
        return jsonify({"success": False, "message": "Некорректный JSON-запрос"}), 400
    kinopoisk_id = data.get('kinopoisk_id')
    magnet_link = (data.get('magnet_link') or '').strip()

    if not kinopoisk_id:
        return jsonify({"success": False, "message": "Отсутствует ID фильма"}), 400

    identifier = MovieIdentifier.query.get(kinopoisk_id)
    
    if magnet_link:
        if identifier:
            identifier.magnet_link = magnet_link
        else:
            identifier = MovieIdentifier(kinopoisk_id=kinopoisk_id, magnet_link=magnet_link)
            db.session.add(identifier)
        message = "Magnet-ссылка сохранена."
    elif identifier:
        db.session.delete(identifier)
        message = "Magnet-ссылка удалена."
    else:
        message = "Действий не требуется."

    db.session.commit()
    refreshed_identifier = MovieIdentifier.query.get(kinopoisk_id)
    return jsonify({
        "success": True, "message": message,
        "has_magnet": bool(refreshed_identifier),
        "magnet_link": refreshed_identifier.magnet_link if refreshed_identifier else "",
    })


# Torrent functionality removed - магнет-ссылки сохраняются, но без автоматической загрузки


# --- Маршруты для опросов ---


@api_bp.route('/polls/create', methods=['POST'])
def create_poll():
    """Создание нового опроса"""
    payload = _get_json_payload()
    if payload is None:
        return jsonify({"error": "Некорректный JSON-запрос"}), 400

    movies_json = payload.get('movies')
    if not movies_json or len(movies_json) < 2:
        return jsonify({"error": "Нужно добавить хотя бы два фильма"}), 400
    
    if len(movies_json) > 25:
        return jsonify({"error": "Максимум 25 фильмов в опросе"}), 400

    _refresh_library_bans()

    # Batch-check for banned movies to avoid N+1 queries
    banned_indices = _check_movies_banned_batch(movies_json)
    if banned_indices:
        idx = list(banned_indices)[0]
        movie_name = movies_json[idx].get('name') or 'Неизвестный фильм'
        return jsonify({
            "error": f"Фильм \"{movie_name}\" находится в бане и не может быть добавлен в опрос"
        }), 422

    creator_token, _ = _get_or_issue_creator_token()

    new_poll = Poll(id=generate_unique_poll_id(), creator_token=creator_token)
    db.session.add(new_poll)

    for movie_data in movies_json:
        new_movie = PollMovie(
            kinopoisk_id=movie_data.get('kinopoisk_id'),
            name=movie_data['name'],
            search_name=movie_data.get('search_name'),
            poster=movie_data.get('poster'),
            year=movie_data.get('year'),
            description=movie_data.get('description'),
            rating_kp=movie_data.get('rating_kp'),
            genres=movie_data.get('genres'),
            countries=movie_data.get('countries'),
            points=_normalize_poll_movie_points(movie_data.get('points')),
            poll=new_poll
        )
        db.session.add(new_movie)
        if poster := movie_data.get('poster'):
            ensure_background_photo(poster)

    db.session.commit()

    poll_url = build_external_url('main.view_poll', poll_id=new_poll.id)
    results_url = build_external_url('main.view_poll_results', poll_id=new_poll.id)

    response = jsonify({
        "poll_id": new_poll.id,
        "poll_url": poll_url,
        "results_url": results_url
    })

    return _set_creator_cookie(response, creator_token)


@api_bp.route('/polls/<poll_id>', methods=['GET'])
def get_poll(poll_id):
    """Получение данных опроса"""
    poll = Poll.query.get_or_404(poll_id)

    closed_by_ban = bool(poll.forced_winner_movie_id)

    if poll.is_expired and not closed_by_ban:
        return jsonify({"error": "Опрос истёк"}), 410

    poll_settings = get_poll_settings()

    identity = _resolve_voter_identity()
    voter_token = identity['voter_token']
    profile = identity['profile']
    user_id = identity['user_id']
    points_balance = profile.total_points or 0
    db.session.commit()

    points_earned_total = profile.points_accrued_total or 0

    # Проверяем, голосовал ли уже этот пользователь
    existing_vote = Vote.query.filter_by(poll_id=poll_id, voter_token=voter_token).first()
    
    movies_data = []
    movies_by_id = {}
    for m in poll.movies:
        movies_by_id[m.id] = m
        movies_data.append(_serialize_poll_movie(m))

    voted_movie_data = None
    voted_points_delta = None
    if existing_vote:
        voted_movie_data = _serialize_poll_movie(movies_by_id.get(existing_vote.movie_id))
        voted_points_delta = existing_vote.points_awarded

    custom_vote_cost = _get_custom_vote_cost()
    can_vote_custom = not poll.is_expired and not existing_vote and points_balance >= custom_vote_cost

    response = prevent_caching(jsonify({
        "poll_id": poll.id,
        "movies": movies_data,
        "created_at": poll.created_at.isoformat() + "Z",
        "expires_at": poll.expires_at.isoformat() + "Z",
        "has_voted": bool(existing_vote),
        "voted_movie": voted_movie_data,
        "voted_points_delta": voted_points_delta,
        "total_votes": len(poll.votes),
        "points_balance": points_balance,
        "points_earned_total": points_earned_total,
        "voter_token": voter_token,
        "user_id": user_id,
        "custom_vote_cost": custom_vote_cost,
        "custom_vote_cost_updated_at": poll_settings.updated_at.isoformat() + "Z" if poll_settings and poll_settings.updated_at else None,
        "can_vote_custom": can_vote_custom,
        "is_expired": poll.is_expired,
        "closed_by_ban": closed_by_ban,
        "forced_winner": _serialize_poll_movie(poll.winners[0]) if closed_by_ban and poll.winners else None,
        "poll_settings": _serialize_poll_settings(poll_settings),
    }))

    return _set_voter_cookies(response, voter_token, user_id)


@api_bp.route('/polls/<poll_id>/vote', methods=['POST'])
def vote_in_poll(poll_id):
    """Голосование в опросе"""
    poll = Poll.query.get_or_404(poll_id)

    closed_by_ban = bool(poll.forced_winner_movie_id)

    if poll.is_expired and not closed_by_ban:
        return jsonify({"error": "Опрос истёк"}), 410

    if closed_by_ban:
        return jsonify({
            "error": "Голосование завершено из-за банов",
            "forced_winner": _serialize_poll_movie(poll.winners[0]) if poll.winners else None,
        }), 409

    payload = _get_json_payload()
    if payload is None:
        return jsonify({"error": "Некорректный JSON-запрос"}), 400

    movie_id = payload.get('movie_id')
    if not movie_id:
        return jsonify({"error": "Не указан фильм"}), 400
    
    # Проверяем, что фильм принадлежит этому опросу
    movie = PollMovie.query.filter_by(id=movie_id, poll_id=poll_id).first()
    if not movie:
        return jsonify({"error": "Фильм не найден в опросе"}), 404

    if getattr(movie, 'is_banned', False):
        return jsonify({"error": "Фильм заблокирован для голосования"}), 403
    
    identity = _resolve_voter_identity()
    voter_token = identity['voter_token']
    device_label = identity['device_label']
    user_id = identity['user_id']

    # Проверяем, не голосовал ли уже этот пользователь
    existing_vote = Vote.query.filter_by(poll_id=poll_id, voter_token=voter_token).first()
    if existing_vote:
        return jsonify({"error": "Вы уже проголосовали в этом опросе"}), 400

    default_points_per_vote = current_app.config.get('POLL_POINTS_PER_VOTE', 1)
    points_awarded = _normalize_poll_movie_points(movie.points, default_points_per_vote)

    # Создаём новый голос
    new_vote = Vote(
        poll_id=poll_id,
        movie_id=movie_id,
        voter_token=voter_token,
        points_awarded=points_awarded,
    )
    db.session.add(new_vote)

    new_balance = change_voter_points_balance(
        voter_token,
        points_awarded,
        device_label=device_label,
    )

    db.session.commit()

    # Fetch updated profile to get current points_accrued_total
    profile = ensure_voter_profile(voter_token, device_label=device_label)
    points_accrued = profile.points_accrued_total or 0

    if points_awarded > 0:
        success_message = f"Голос учтён! +{points_awarded} баллов к вашему счёту."
    else:
        success_message = "Голос учтён! Приятного просмотра!"

    response = prevent_caching(jsonify({
        "success": True,
        "message": success_message,
        "movie_name": movie.name,
        "points_awarded": points_awarded,
        "points_balance": new_balance,
        "points_earned_total": points_accrued,
        "voted_movie": _serialize_poll_movie(movie),
    }))

    return _set_voter_cookies(response, voter_token, user_id)


@api_bp.route('/polls/<poll_id>/ban', methods=['POST'])
def ban_poll_movie(poll_id):
    poll = Poll.query.get_or_404(poll_id)

    closed_by_ban = bool(poll.forced_winner_movie_id)
    if poll.is_expired and not closed_by_ban:
        return jsonify({"error": "Опрос истёк"}), 410

    if closed_by_ban:
        return jsonify({
            "error": "Голосование уже завершено из-за банов",
            "forced_winner": _serialize_poll_movie(poll.winners[0]) if poll.winners else None,
        }), 409

    payload = _get_json_payload()
    if payload is None:
        return jsonify({"error": "Некорректный JSON-запрос"}), 400

    movie_id = payload.get('movie_id')
    months = payload.get('months')

    try:
        movie_id = int(movie_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Некорректный идентификатор фильма"}), 400

    try:
        months = int(months)
    except (TypeError, ValueError):
        return jsonify({"error": "Количество месяцев должно быть числом"}), 400

    if months <= 0:
        return jsonify({"error": "Минимальный бан — 1 месяц"}), 400

    movie = PollMovie.query.filter_by(id=movie_id, poll_id=poll_id).first()
    if not movie:
        return jsonify({"error": "Фильм не найден в опросе"}), 404

    active_movies_before = _get_active_poll_movies(poll)
    if not movie.is_banned and len(active_movies_before) <= 1:
        return jsonify({"error": "Нельзя забанить последний фильм"}), 409

    identity = _resolve_voter_identity()
    voter_token = identity['voter_token']
    device_label = identity['device_label']
    user_id = identity['user_id']
    profile = identity['profile']
    balance_before = profile.total_points or 0

    # Получаем индивидуальную цену за месяц бана из библиотеки
    library_movie = None
    if movie.kinopoisk_id:
        library_movie = LibraryMovie.query.filter_by(kinopoisk_id=movie.kinopoisk_id).first()
    if not library_movie and movie.name and movie.year:
        library_movie = LibraryMovie.query.filter_by(name=movie.name, year=movie.year).first()

    # Используем индивидуальную цену за месяц, если она установлена, иначе 1 балл за месяц
    cost_per_month = library_movie.ban_cost_per_month if library_movie and library_movie.ban_cost_per_month is not None else 1
    total_cost = cost_per_month * months

    if balance_before < total_cost:
        return jsonify({"error": f"Недостаточно баллов для бана. Требуется {total_cost} баллов ({cost_per_month} × {months} месяцев)"}), 403

    now_utc = datetime.utcnow()
    base_time = (
        movie.ban_until
        if movie.is_banned and movie.ban_until and movie.ban_until > now_utc
        else now_utc
    )
    movie.ban_until = _calculate_ban_until(base_time, months)

    library_ban_data = None
    if library_movie:
        library_movie.badge = 'ban'
        library_movie.ban_until = movie.ban_until
        library_movie.ban_applied_by = device_label or 'poll-ban'
        library_movie.ban_cost = total_cost
        library_movie.bumped_at = datetime.utcnow()
        library_ban_data = _serialize_library_movie(library_movie)

    new_balance = change_voter_points_balance(
        voter_token,
        -total_cost,
        device_label=device_label,
    )

    active_movies_after = _get_active_poll_movies(poll)
    forced_winner = None
    closed_by_ban = False
    if len(active_movies_after) == 1:
        forced_winner = active_movies_after[0]
        poll.forced_winner_movie_id = forced_winner.id
        poll.expires_at = datetime.utcnow()
        closed_by_ban = True

    db.session.commit()

    # Fetch updated profile to get current points_accrued_total
    profile = ensure_voter_profile(voter_token, device_label=device_label)
    points_accrued = profile.points_accrued_total or 0

    response = prevent_caching(jsonify({
        "success": True,
        "ban_until": movie.ban_until.isoformat() if movie.ban_until else None,
        "ban_status": movie.ban_status,
        "ban_remaining_seconds": movie.ban_remaining_seconds,
        "points_balance": new_balance,
        "points_earned_total": points_accrued,
        "closed_by_ban": closed_by_ban,
        "forced_winner": _serialize_poll_movie(forced_winner) if forced_winner else None,
        "library_ban": library_ban_data,
    }))

    return _set_voter_cookies(response, voter_token, user_id)


@api_bp.route('/polls/<poll_id>/custom-vote', methods=['POST'])
def custom_vote(poll_id):
    poll = Poll.query.get_or_404(poll_id)

    closed_by_ban = bool(poll.forced_winner_movie_id)

    if poll.is_expired and not closed_by_ban:
        return jsonify({"error": "Опрос истёк"}), 410

    if closed_by_ban:
        return jsonify({
            "error": "Голосование завершено из-за банов",
            "forced_winner": _serialize_poll_movie(poll.winners[0]) if poll.winners else None,
        }), 409

    payload = _get_json_payload()
    if payload is None:
        return jsonify({"error": "Некорректный JSON-запрос"}), 400

    raw_query = payload.get('query') or ''
    query = raw_query.strip()
    if not query:
        return jsonify({"error": "Пустой запрос"}), 400

    kinopoisk_id = payload.get('kinopoisk_id')

    identity = _resolve_voter_identity()
    voter_token = identity['voter_token']
    device_label = identity['device_label']
    user_id = identity['user_id']

    existing_vote = Vote.query.filter_by(poll_id=poll_id, voter_token=voter_token).first()
    if existing_vote:
        return jsonify({"error": "Вы уже проголосовали в этом опросе"}), 400

    profile = identity['profile']
    cost = _get_custom_vote_cost()
    current_balance = profile.total_points or 0

    if current_balance < cost:
        return jsonify({"error": "Недостаточно баллов для кастомного голосования"}), 400

    movie_data, error = get_movie_data_from_kinopoisk(query)
    if not movie_data:
        message = "Фильм не найден"
        if error and error.get('message'):
            message = error['message']
        status_code = error.get('status') if isinstance(error, dict) else None
        return jsonify({"error": message}), status_code or 404

    if kinopoisk_id and not movie_data.get('kinopoisk_id'):
        movie_data['kinopoisk_id'] = kinopoisk_id

    resolved_kinopoisk_id = movie_data.get('kinopoisk_id') or kinopoisk_id

    existing_movie = None
    if resolved_kinopoisk_id:
        existing_movie = PollMovie.query.filter_by(
            poll_id=poll_id, kinopoisk_id=resolved_kinopoisk_id
        ).first()

    if not existing_movie:
        existing_movie = PollMovie.query.filter_by(
            poll_id=poll_id,
            name=movie_data.get('name'),
            year=movie_data.get('year'),
        ).first()

    if existing_movie:
        poll_movie = existing_movie
    else:
        poll_movie = PollMovie(
            poll=poll,
            kinopoisk_id=movie_data.get('kinopoisk_id'),
            name=movie_data.get('name'),
            search_name=movie_data.get('search_name'),
            poster=movie_data.get('poster'),
            year=movie_data.get('year'),
            description=movie_data.get('description'),
            rating_kp=movie_data.get('rating_kp'),
            genres=movie_data.get('genres'),
            countries=movie_data.get('countries'),
            points=_normalize_poll_movie_points(movie_data.get('points'), 1),
        )
        db.session.add(poll_movie)
        if poster := movie_data.get('poster'):
            ensure_background_photo(poster)

    db.session.flush()

    points_awarded = -cost

    new_balance = change_voter_points_balance(
        voter_token,
        points_awarded,
        device_label=device_label,
    )

    if new_balance < 0:
        db.session.rollback()
        return jsonify({"error": "Недостаточно баллов для кастомного голосования"}), 400

    new_vote = Vote(
        poll_id=poll_id,
        movie_id=poll_movie.id,
        voter_token=voter_token,
        points_awarded=points_awarded,
    )
    db.session.add(new_vote)

    db.session.commit()

    # Fetch updated profile to get current points_accrued_total
    profile = ensure_voter_profile(voter_token, device_label=device_label)
    points_accrued = profile.points_accrued_total or 0

    response = prevent_caching(jsonify({
        "success": True,
        "movie": _serialize_poll_movie(poll_movie),
        "points_awarded": points_awarded,
        "points_balance": new_balance,
        "points_earned_total": points_accrued,
        "has_voted": True,
    }))

    return _set_voter_cookies(response, voter_token, user_id)


@api_bp.route('/polls/<poll_id>/results', methods=['GET'])
def get_poll_results(poll_id):
    """Получение результатов опроса"""
    poll = Poll.query.get_or_404(poll_id)

    closed_by_ban = bool(poll.forced_winner_movie_id)

    if poll.is_expired and not closed_by_ban:
        return jsonify({"error": "Опрос истёк"}), 410

    poll_settings = get_poll_settings()
    
    # Получаем статистику голосов
    vote_counts = poll.get_vote_counts()
    winners = poll.winners
    
    movies_with_votes = []
    for movie in poll.movies:
        votes = vote_counts.get(movie.id, 0)
        movies_with_votes.append({
            "id": movie.id,
            "kinopoisk_id": movie.kinopoisk_id,
            "name": movie.name,
            "search_name": movie.search_name,
            "poster": movie.poster,
            "year": movie.year,
            "description": movie.description,
            "rating_kp": movie.rating_kp,
            "genres": movie.genres,
            "countries": movie.countries,
            "points": movie.points if movie.points is not None else 1,
            "ban_until": movie.ban_until.isoformat() if movie.ban_until else None,
            "ban_status": movie.ban_status,
            "ban_remaining_seconds": movie.ban_remaining_seconds,
            "votes": votes,
            "is_winner": movie in winners
        })
    
    # Сортируем по количеству голосов
    movies_with_votes.sort(key=lambda x: x['votes'], reverse=True)
    
    return prevent_caching(jsonify({
        "poll_id": poll.id,
        "movies": movies_with_votes,
        "total_votes": len(poll.votes),
        "winners": [
            {
                "id": w.id,
                "name": w.name,
                "search_name": w.search_name,
                "poster": w.poster,
                "year": w.year,
                "points": w.points if w.points is not None else 1,
            }
            for w in winners
        ],
        "custom_vote_cost": _get_custom_vote_cost(),
        "poll_settings": _serialize_poll_settings(poll_settings),
        "created_at": poll.created_at.isoformat() + "Z",
        "expires_at": poll.expires_at.isoformat() + "Z",
        "closed_by_ban": closed_by_ban,
    }))


@api_bp.route('/polls/my-polls', methods=['GET'])
def get_my_polls():
    """Получение последних опросов с результатами."""
    creator_token = _read_creator_token_from_request()
    if not creator_token:
        return prevent_caching(jsonify({"polls": []}))

    _touch_creator_token(creator_token)

    polls = (
        Poll.query
        .filter_by(creator_token=creator_token)
        .order_by(Poll.created_at.desc())
        .limit(100)
        .all()
    )
    
    polls_data = []
    for poll in polls:
        # Проверяем, есть ли голоса или форсированный победитель
        if len(poll.votes) == 0 and not poll.forced_winner_movie_id:
            continue
        
        vote_counts = poll.get_vote_counts()
        winners = poll.winners
        
        polls_data.append({
            "poll_id": poll.id,
            "created_at": poll.created_at.isoformat() + "Z",
            "expires_at": poll.expires_at.isoformat() + "Z",
            "is_expired": poll.is_expired,
            "closed_by_ban": bool(poll.forced_winner_movie_id),
            "total_votes": len(poll.votes),
            "movies_count": len(poll.movies),
            "winners": [
                {
                    "id": w.id,
                    "name": w.name,
                    "search_name": w.search_name,
                    "poster": w.poster,
                    "year": w.year,
                    "points": w.points if w.points is not None else 1,
                    "votes": vote_counts.get(w.id, 0)
                }
                for w in winners
            ],
            "poll_url": build_external_url('main.view_poll', poll_id=poll.id),
            "results_url": build_external_url('main.view_poll_results', poll_id=poll.id)
        })

    return prevent_caching(jsonify({"polls": polls_data}))


@api_bp.route('/polls/cleanup-expired', methods=['POST'])
def cleanup_expired_polls():
    """Удаление истёкших опросов (можно вызывать по cron или вручную)"""
    expired_polls = Poll.query.filter(Poll.expires_at <= datetime.utcnow()).all()
    count = len(expired_polls)
    
    for poll in expired_polls:
        db.session.delete(poll)
    
    db.session.commit()
    return jsonify({"success": True, "deleted_count": count})


# --- Маршруты для управления бейджами ---

@api_bp.route('/library/<int:movie_id>/badge', methods=['PUT'])
def set_movie_badge(movie_id):
    """Установка бейджа для фильма в библиотеке"""
    _refresh_library_bans()
    library_movie = LibraryMovie.query.get_or_404(movie_id)

    payload = _get_json_payload()
    if payload is None:
        return jsonify({"success": False, "message": "Некорректный JSON-запрос"}), 400

    badge_type = payload.get('badge')
    allowed_badges = ['favorite', 'ban', 'watchlist', 'top', 'watched', 'new']

    if badge_type and badge_type not in allowed_badges:
        return jsonify({"success": False, "message": "Недопустимый тип бейджа"}), 400

    ban_until = None
    ban_applied_by = None
    ban_cost = None

    if badge_type == 'ban':
        ban_until_raw = payload.get('ban_until')
        ban_duration_months = payload.get('ban_duration_months')

        now_utc = datetime.utcnow()
        base_time = (
            library_movie.ban_until
            if library_movie.badge == 'ban' and library_movie.ban_until and library_movie.ban_until > now_utc
            else now_utc
        )

        if ban_until_raw is not None:
            parsed_until = _parse_iso_date(ban_until_raw)
            if parsed_until is None:
                return jsonify({"success": False, "message": "Некорректная дата окончания бана"}), 400
            ban_until = _align_to_end_of_day(parsed_until)
        else:
            duration_value = 1 if ban_duration_months is None else ban_duration_months
            try:
                months = int(duration_value)
            except (TypeError, ValueError):
                return jsonify({"success": False, "message": "Длительность бана должна быть числом месяцев"}), 400

            if months <= 0:
                return jsonify({"success": False, "message": "Минимальный бан — 1 месяц"}), 400

            ban_until = _calculate_ban_until(base_time, months)

        ban_applied_by = (payload.get('ban_applied_by') or '').strip() or None
        raw_cost = payload.get('ban_cost')
        try:
            ban_cost = int(raw_cost) if raw_cost is not None else None
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Стоимость бана должна быть числом"}), 400

    library_movie.badge = badge_type
    library_movie.ban_until = ban_until
    library_movie.ban_applied_by = ban_applied_by
    library_movie.ban_cost = ban_cost
    library_movie.bumped_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Бейдж установлен" if badge_type else "Бейдж удалён",
        "badge": badge_type,
        "ban_until": library_movie.ban_until.isoformat() if library_movie.ban_until else None,
        "ban_status": library_movie.ban_status,
        "ban_remaining_seconds": library_movie.ban_remaining_seconds,
        "ban_applied_by": library_movie.ban_applied_by,
        "ban_cost": library_movie.ban_cost,
    })

@api_bp.route('/library/<int:movie_id>/badge', methods=['DELETE'])
def remove_movie_badge(movie_id):
    """Удаление бейджа у фильма в библиотеке"""
    library_movie = LibraryMovie.query.get_or_404(movie_id)
    library_movie.badge = None
    library_movie.ban_until = None
    library_movie.ban_applied_by = None
    library_movie.ban_cost = None
    library_movie.bumped_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Бейдж удалён",
        "badge": None,
        "ban_status": library_movie.ban_status,
        "ban_remaining_seconds": library_movie.ban_remaining_seconds,
        "ban_applied_by": library_movie.ban_applied_by,
        "ban_cost": library_movie.ban_cost,
    })

@api_bp.route('/library/badges/stats', methods=['GET'])
def get_badge_stats():
    """Получение статистики по бейджам в библиотеке"""
    _refresh_library_bans()
    badge_stats = db.session.query(
        LibraryMovie.badge,
        func.count(LibraryMovie.id).label('count')
    ).filter(
        LibraryMovie.badge.isnot(None)
    ).group_by(
        LibraryMovie.badge
    ).all()
    
    stats = {badge: count for badge, count in badge_stats}
    
    # Добавляем все типы бейджей с нулевыми значениями для отсутствующих
    all_badges = ['favorite', 'ban', 'watchlist', 'top', 'watched', 'new']
    result = {badge: stats.get(badge, 0) for badge in all_badges}

    return jsonify(result)

@api_bp.route('/library/badges/<badge_type>/movies', methods=['GET'])
def get_movies_by_badge(badge_type):
    """Получение списка фильмов с определённым бейджем для создания опроса"""
    allowed_badges = ['favorite', 'ban', 'watchlist', 'top', 'watched', 'new']

    if badge_type not in allowed_badges:
        return jsonify({"error": "Недопустимый тип бейджа"}), 400

    _refresh_library_bans()
    movies = LibraryMovie.query.filter_by(badge=badge_type).all()

    banned_movies = [m for m in movies if m.ban_status in {'active', 'pending'}]

    if banned_movies:
        if badge_type == 'ban':
            return jsonify({"error": "Нельзя использовать фильмы с активным баном для опросов"}), 403
        movies = [m for m in movies if m not in banned_movies]

    if len(movies) < 2:
        return jsonify({"error": "Недостаточно доступных фильмов для создания опроса (минимум 2)"}), 422

    # Ограничиваем количество фильмов до 25
    limited = False
    if len(movies) > 25:
        movies = movies[:25]
        limited = True
    
    movies_data = [_serialize_library_movie(movie) for movie in movies]
    
    return jsonify({
        'movies': movies_data,
        'total': len(movies),
        'limited': limited
    })


@api_bp.route('/polls/voter-stats', methods=['GET'])
def list_voter_stats():
    filters = _prepare_voter_filters(request.args)

    try:
        try:
            per_page = int(request.args.get('per_page', 25))
        except (TypeError, ValueError):
            per_page = 25
        per_page = max(1, min(100, per_page))

        try:
            page = int(request.args.get('page', 1))
        except (TypeError, ValueError):
            page = 1
        page = max(1, page)

        sort_map = {
            'token': PollVoterProfile.token,
            'user_id': PollVoterProfile.user_id,
            'device_label': PollVoterProfile.device_label,
            'total_points': PollVoterProfile.total_points,
            'points_accrued_total': PollVoterProfile.points_accrued_total,
            'created_at': PollVoterProfile.created_at,
            'updated_at': PollVoterProfile.updated_at,
        }
        sort_by = request.args.get('sort_by', 'updated_at')
        sort_column = sort_map.get(sort_by, PollVoterProfile.updated_at)
        sort_order = request.args.get('sort_order', 'desc').lower()
        order_clause = sort_column.asc() if sort_order == 'asc' else sort_column.desc()

        query = PollVoterProfile.query

        if filters['token']:
            query = query.filter(PollVoterProfile.token.ilike(f"%{filters['token']}%"))

        if filters['device_label']:
            query = query.filter(PollVoterProfile.device_label.ilike(f"%{filters['device_label']}%"))

        if filters['user_id']:
            query = query.filter(PollVoterProfile.user_id.ilike(f"%{filters['user_id']}%"))

        if filters['requires_vote_filters']:
            query = query.join(PollVoterProfile.votes)
            query = _apply_vote_filters(query, filters)
            query = query.distinct()

        query = query.order_by(order_clause)

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        profiles = pagination.items
        tokens = [profile.token for profile in profiles if profile.token]
        votes_map = _group_votes_by_token(tokens, filters)

        items = []
        for profile in profiles:
            votes = votes_map.get(profile.token, [])
            filtered_points = sum((vote.get('points_awarded') or 0) for vote in votes)
            last_vote_at = votes[0]['voted_at'] if votes else None
            earned_total = profile.points_accrued_total or 0
            items.append({
                'voter_token': profile.token,
                'user_id': profile.user_id,
                'device_label': profile.device_label,
                'total_points': profile.total_points or 0,
                'points_accrued_total': earned_total,
                'points_earned_total': earned_total,
                'filtered_points': filtered_points,
                'created_at': profile.created_at.isoformat() if profile.created_at else None,
                'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
                'last_vote_at': last_vote_at,
                'votes_count': len(votes),
                'votes': votes,
            })

        payload = {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'pages': pagination.pages,
            'total': pagination.total,
            'items': items,
        }

        return prevent_caching(jsonify(payload))
    except (OperationalError, ProgrammingError) as exc:
        db.session.rollback()
        logger = getattr(current_app, 'logger', None)
        if logger:
            logger.exception('Не удалось получить статистику голосующих: %s', exc)

        try:
            ensure_poll_tables()
        except Exception as ensure_exc:  # pragma: no cover - best effort recovery
            if logger:
                logger.warning('Не удалось восстановить таблицы голосования: %s', ensure_exc)

        return jsonify({'error': 'Сервис временно недоступен'}), 503



@api_bp.route('/polls/voter-stats/<string:voter_token>', methods=['GET'])
def voter_stats_details(voter_token):
    filters = _prepare_voter_filters(request.args)
    profile = PollVoterProfile.query.get_or_404(voter_token)
    votes_map = _group_votes_by_token([profile.token], filters)
    votes = votes_map.get(profile.token, [])
    filtered_points = sum((vote.get('points_awarded') or 0) for vote in votes)

    earned_total = profile.points_accrued_total or 0
    payload = {
        'voter_token': profile.token,
        'user_id': profile.user_id,
        'device_label': profile.device_label,
        'total_points': profile.total_points or 0,
        'points_accrued_total': earned_total,
        'points_earned_total': earned_total,
        'filtered_points': filtered_points,
        'created_at': profile.created_at.isoformat() if profile.created_at else None,
        'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
        'last_vote_at': votes[0]['voted_at'] if votes else None,
        'votes_count': len(votes),
        'votes': votes,
    }

    return prevent_caching(jsonify(payload))


@api_bp.route('/polls/voter-stats/<string:voter_token>/device-label', methods=['PATCH'])
def update_voter_device_label(voter_token):
    data = _get_json_payload()
    if data is None or 'device_label' not in data:
        return jsonify({'error': 'Передайте device_label в теле запроса'}), 400

    raw_label = data.get('device_label')
    if raw_label is not None and not isinstance(raw_label, str):
        return jsonify({'error': 'Метка устройства должна быть строкой или null'}), 400

    normalized_label = None
    if isinstance(raw_label, str):
        trimmed = raw_label.strip()
        if trimmed:
            normalized_label = trimmed[:255]

    profile = PollVoterProfile.query.get_or_404(voter_token)
    profile.device_label = normalized_label
    profile.updated_at = datetime.utcnow()
    db.session.commit()

    earned_total = profile.points_accrued_total or 0
    payload = {
        'voter_token': profile.token,
        'user_id': profile.user_id,
        'device_label': profile.device_label,
        'total_points': profile.total_points or 0,
        'points_accrued_total': earned_total,
        'points_earned_total': earned_total,
        'created_at': profile.created_at.isoformat() if profile.created_at else None,
        'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
    }

    return prevent_caching(jsonify(payload))


@api_bp.route('/polls/voter-stats/<string:voter_token>/points', methods=['PATCH'])
def update_voter_total_points(voter_token):
    data = _get_json_payload()
    if data is None or 'total_points' not in data:
        return jsonify({'error': 'Передайте total_points в теле запроса'}), 400

    new_points = data.get('total_points')
    if isinstance(new_points, bool) or not isinstance(new_points, int):
        return jsonify({'error': 'total_points должен быть целым числом'}), 400

    profile = PollVoterProfile.query.get_or_404(voter_token)
    profile.total_points = new_points
    profile.updated_at = datetime.utcnow()
    db.session.commit()

    earned_total = profile.points_accrued_total or 0
    payload = {
        'voter_token': profile.token,
        'user_id': profile.user_id,
        'device_label': profile.device_label,
        'total_points': profile.total_points or 0,
        'points_accrued_total': earned_total,
        'points_earned_total': earned_total,
        'created_at': profile.created_at.isoformat() if profile.created_at else None,
        'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
    }

    return prevent_caching(jsonify(payload))


@api_bp.route('/polls/voter-stats/<string:voter_token>/user-id', methods=['PATCH'])
def update_voter_user_id(voter_token):
    data = _get_json_payload()
    if data is None or 'user_id' not in data:
        return jsonify({'error': 'Передайте user_id в теле запроса'}), 400

    raw_user_id = data.get('user_id')
    if raw_user_id is not None and not isinstance(raw_user_id, (str, int)):
        return jsonify({'error': 'user_id должен быть строкой или null'}), 400

    normalized_user_id = _normalize_user_id(raw_user_id)

    profile = PollVoterProfile.query.get_or_404(voter_token)
    profile.user_id = normalized_user_id
    profile.updated_at = datetime.utcnow()
    db.session.commit()

    earned_total = profile.points_accrued_total or 0
    payload = {
        'voter_token': profile.token,
        'user_id': profile.user_id,
        'device_label': profile.device_label,
        'total_points': profile.total_points or 0,
        'points_accrued_total': earned_total,
        'points_earned_total': earned_total,
        'created_at': profile.created_at.isoformat() if profile.created_at else None,
        'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
    }

    return prevent_caching(jsonify(payload))


@api_bp.route('/polls/voter-stats/<string:voter_token>/points-accrued', methods=['PATCH'])
def update_voter_points_accrued_total(voter_token):
    data = _get_json_payload()
    if data is None or 'points_accrued_total' not in data:
        return jsonify({'error': 'Передайте points_accrued_total в теле запроса'}), 400

    new_value = data.get('points_accrued_total')
    if isinstance(new_value, bool) or not isinstance(new_value, int):
        return jsonify({'error': 'points_accrued_total должен быть целым числом'}), 400

    profile = PollVoterProfile.query.get_or_404(voter_token)
    profile.points_accrued_total = new_value
    profile.updated_at = datetime.utcnow()
    db.session.commit()

    earned_total = profile.points_accrued_total or 0
    payload = {
        'voter_token': profile.token,
        'user_id': profile.user_id,
        'device_label': profile.device_label,
        'total_points': profile.total_points or 0,
        'points_accrued_total': earned_total,
        'points_earned_total': earned_total,
        'created_at': profile.created_at.isoformat() if profile.created_at else None,
        'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
    }

    return prevent_caching(jsonify(payload))
