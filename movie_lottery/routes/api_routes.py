import random
import re
import secrets
from collections import defaultdict
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.exc import OperationalError, ProgrammingError

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
    generate_unique_id,
    ensure_background_photo,
    generate_unique_poll_id,
    build_external_url,
    build_telegram_share_url,
    ensure_voter_profile,
    change_voter_points_balance,
    prevent_caching,
    ensure_poll_tables,
)

api_bp = Blueprint('api', __name__, url_prefix='/api')


POLL_CREATOR_COOKIE = 'poll_creator_token'
POLL_CREATOR_HEADER = 'X-Poll-Creator-Token'
POLL_CREATOR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year
_CREATOR_TOKEN_RE = re.compile(r'^[a-f0-9]{32}$', re.IGNORECASE)


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


def _get_json_payload():
    """Возвращает тело запроса в формате JSON или None, если оно некорректно."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _get_custom_vote_cost():
    try:
        return max(0, int(current_app.config.get('POLL_CUSTOM_VOTE_COST', 10)))
    except (TypeError, ValueError):
        return 10


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


def _prepare_voter_filters(args):
    token = (args.get('token') or '').strip()
    poll_id = (args.get('poll_id') or '').strip()
    device_label = (args.get('device_label') or '').strip()
    date_from = _parse_iso_date(args.get('date_from'))
    date_to = _parse_iso_date(args.get('date_to'), for_end=True)

    requires_vote_filters = any([poll_id, date_from, date_to])

    return {
        'token': token,
        'poll_id': poll_id,
        'device_label': device_label,
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
    }


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
        existing_movie.bumped_at = db.func.now()
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
    library_movie.bumped_at = db.func.now()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Баллы обновлены.",
        "points": library_movie.points,
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
    
    if poll.is_expired:
        return jsonify({"error": "Опрос истёк"}), 410
    
    # Получаем токен голосующего из cookie или генерируем новый
    voter_token = request.cookies.get('voter_token')
    if not voter_token:
        voter_token = secrets.token_hex(16)

    device_label = _resolve_device_label()
    profile = ensure_voter_profile(voter_token, device_label=device_label)
    points_balance = profile.total_points or 0
    db.session.commit()

    # Проверяем, голосовал ли уже этот пользователь
    existing_vote = Vote.query.filter_by(poll_id=poll_id, voter_token=voter_token).first()
    
    movies_data = []
    movies_by_id = {}
    for m in poll.movies:
        movies_by_id[m.id] = m
        movies_data.append(_serialize_poll_movie(m))

    voted_movie_data = None
    if existing_vote:
        voted_movie_data = _serialize_poll_movie(movies_by_id.get(existing_vote.movie_id))

    custom_vote_cost = _get_custom_vote_cost()
    can_vote_custom = not poll.is_expired and not existing_vote and points_balance >= custom_vote_cost

    response = prevent_caching(jsonify({
        "poll_id": poll.id,
        "movies": movies_data,
        "created_at": poll.created_at.isoformat() + "Z",
        "expires_at": poll.expires_at.isoformat() + "Z",
        "has_voted": bool(existing_vote),
        "voted_movie": voted_movie_data,
        "total_votes": len(poll.votes),
        "points_balance": points_balance,
        "custom_vote_cost": custom_vote_cost,
        "can_vote_custom": can_vote_custom,
    }))

    # Устанавливаем cookie с токеном голосующего
    if not request.cookies.get('voter_token'):
        response.set_cookie('voter_token', voter_token, max_age=60*60*24*30)  # 30 дней

    return response


@api_bp.route('/polls/<poll_id>/vote', methods=['POST'])
def vote_in_poll(poll_id):
    """Голосование в опросе"""
    poll = Poll.query.get_or_404(poll_id)

    if poll.is_expired:
        return jsonify({"error": "Опрос истёк"}), 410

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
    
    # Получаем или создаём токен голосующего
    voter_token = request.cookies.get('voter_token')
    if not voter_token:
        voter_token = secrets.token_hex(16)

    device_label = _resolve_device_label()

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
        "voted_movie": _serialize_poll_movie(movie),
    }))
    
    # Устанавливаем cookie с токеном
    if not request.cookies.get('voter_token'):
        response.set_cookie('voter_token', voter_token, max_age=60*60*24*30)

    return response


@api_bp.route('/polls/<poll_id>/custom-vote', methods=['POST'])
def custom_vote(poll_id):
    poll = Poll.query.get_or_404(poll_id)

    if poll.is_expired:
        return jsonify({"error": "Опрос истёк"}), 410

    payload = _get_json_payload()
    if payload is None:
        return jsonify({"error": "Некорректный JSON-запрос"}), 400

    raw_query = payload.get('query') or ''
    query = raw_query.strip()
    if not query:
        return jsonify({"error": "Пустой запрос"}), 400

    kinopoisk_id = payload.get('kinopoisk_id')

    voter_token = request.cookies.get('voter_token') or secrets.token_hex(16)
    device_label = _resolve_device_label()

    existing_vote = Vote.query.filter_by(poll_id=poll_id, voter_token=voter_token).first()
    if existing_vote:
        return jsonify({"error": "Вы уже проголосовали в этом опросе"}), 400

    profile = ensure_voter_profile(voter_token, device_label=device_label)
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

    new_balance = change_voter_points_balance(
        voter_token,
        -cost,
        device_label=device_label,
    )

    if new_balance < 0:
        db.session.rollback()
        return jsonify({"error": "Недостаточно баллов для кастомного голосования"}), 400

    new_vote = Vote(
        poll_id=poll_id,
        movie_id=poll_movie.id,
        voter_token=voter_token,
        points_awarded=-cost,
    )
    db.session.add(new_vote)

    db.session.commit()

    response = prevent_caching(jsonify({
        "success": True,
        "movie": _serialize_poll_movie(poll_movie),
        "points_balance": new_balance,
        "has_voted": True,
    }))

    if not request.cookies.get('voter_token'):
        response.set_cookie('voter_token', voter_token, max_age=60*60*24*30)

    return response


@api_bp.route('/polls/<poll_id>/results', methods=['GET'])
def get_poll_results(poll_id):
    """Получение результатов опроса"""
    poll = Poll.query.get_or_404(poll_id)

    if poll.is_expired:
        return jsonify({"error": "Опрос истёк"}), 410
    
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
        "created_at": poll.created_at.isoformat() + "Z",
        "expires_at": poll.expires_at.isoformat() + "Z"
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
        # Проверяем, есть ли голоса
        if len(poll.votes) == 0:
            continue
        
        vote_counts = poll.get_vote_counts()
        winners = poll.winners
        
        polls_data.append({
            "poll_id": poll.id,
            "created_at": poll.created_at.isoformat() + "Z",
            "expires_at": poll.expires_at.isoformat() + "Z",
            "is_expired": poll.is_expired,
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
    library_movie = LibraryMovie.query.get_or_404(movie_id)

    payload = _get_json_payload()
    if payload is None:
        return jsonify({"success": False, "message": "Некорректный JSON-запрос"}), 400

    badge_type = payload.get('badge')
    allowed_badges = ['favorite', 'watchlist', 'top', 'watched', 'new']
    
    if badge_type and badge_type not in allowed_badges:
        return jsonify({"success": False, "message": "Недопустимый тип бейджа"}), 400
    
    library_movie.badge = badge_type
    db.session.commit()
    
    return jsonify({
        "success": True, 
        "message": "Бейдж установлен" if badge_type else "Бейдж удалён",
        "badge": badge_type
    })

@api_bp.route('/library/<int:movie_id>/badge', methods=['DELETE'])
def remove_movie_badge(movie_id):
    """Удаление бейджа у фильма в библиотеке"""
    library_movie = LibraryMovie.query.get_or_404(movie_id)
    library_movie.badge = None
    db.session.commit()
    
    return jsonify({"success": True, "message": "Бейдж удалён"})

@api_bp.route('/library/badges/stats', methods=['GET'])
def get_badge_stats():
    """Получение статистики по бейджам в библиотеке"""
    from sqlalchemy import func
    
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
    all_badges = ['favorite', 'watchlist', 'top', 'watched', 'new']
    result = {badge: stats.get(badge, 0) for badge in all_badges}
    
    return jsonify(result)

@api_bp.route('/library/badges/<badge_type>/movies', methods=['GET'])
def get_movies_by_badge(badge_type):
    """Получение списка фильмов с определённым бейджем для создания опроса"""
    allowed_badges = ['favorite', 'watchlist', 'top', 'watched', 'new']
    
    if badge_type not in allowed_badges:
        return jsonify({"error": "Недопустимый тип бейджа"}), 400
    
    movies = LibraryMovie.query.filter_by(badge=badge_type).all()
    
    if len(movies) < 2:
        return jsonify({"error": f"Недостаточно фильмов с бейджем '{badge_type}' для создания опроса (минимум 2)"}), 400
    
    # Ограничиваем количество фильмов до 25
    limited = False
    if len(movies) > 25:
        movies = movies[:25]
        limited = True
    
    movies_data = []
    for movie in movies:
        movies_data.append({
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
        })
    
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
            'device_label': PollVoterProfile.device_label,
            'total_points': PollVoterProfile.total_points,
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
            items.append({
                'voter_token': profile.token,
                'device_label': profile.device_label,
                'total_points': profile.total_points or 0,
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

    payload = {
        'voter_token': profile.token,
        'device_label': profile.device_label,
        'total_points': profile.total_points or 0,
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

    payload = {
        'voter_token': profile.token,
        'device_label': profile.device_label,
        'total_points': profile.total_points or 0,
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

    payload = {
        'voter_token': profile.token,
        'device_label': profile.device_label,
        'total_points': profile.total_points or 0,
        'created_at': profile.created_at.isoformat() if profile.created_at else None,
        'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
    }

    return prevent_caching(jsonify(payload))
