import calendar
import mimetypes
import os
import random
import re
import secrets
import threading
import uuid
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from .. import db
from ..models import (
    CustomBadge,
    Movie,
    Lottery,
    MovieIdentifier,
    LibraryMovie,
    Poll,
    PollCreatorToken,
    PollMovie,
    PollVoterProfile,
    PushSubscription,
    Vote,
)
from ..utils.kinopoisk import get_movie_data_from_kinopoisk, get_movies_by_release_date
from ..utils.video_processing import apply_faststart
from ..utils.helpers import (
    build_external_url,
    build_telegram_share_url,
    calculate_streak_bonus,
    change_voter_points_balance,
    ensure_background_photo,
    ensure_poll_tables,
    ensure_voter_profile,
    ensure_voter_profile_for_user,
    generate_unique_id,
    generate_unique_poll_id,
    get_custom_vote_cost,
    get_poll_duration_minutes,
    get_poll_settings,
    get_voter_streak_info,
    get_voter_transactions,
    get_voter_transactions_summary,
    log_points_transaction,
    prevent_caching,
    rotate_voter_token,
    update_poll_settings,
    update_voter_streak,
    vladivostok_now,
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


def _plural_months(n):
    """Возвращает правильное склонение слова 'месяц' для числа n."""
    if n % 10 == 1 and n % 100 != 11:
        return 'месяц'
    elif 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
        return 'месяца'
    else:
        return 'месяцев'


def _get_json_payload():
    """Возвращает тело запроса в формате JSON или None, если оно некорректно."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _get_custom_vote_cost():
    return get_custom_vote_cost()


def _get_trailer_settings():
    config = current_app.config
    allowed_mime_types = config.get('TRAILER_ALLOWED_MIME_TYPES') or []
    max_size = config.get('TRAILER_MAX_FILE_SIZE') or 0
    upload_dir = config.get('TRAILER_UPLOAD_DIR')
    media_root = config.get('TRAILER_MEDIA_ROOT') or upload_dir
    relative_dir = config.get('TRAILER_UPLOAD_SUBDIR', 'trailers')

    return {
        'allowed_mime_types': [mime.lower() for mime in allowed_mime_types],
        'max_size': int(max_size) if max_size else 0,
        'upload_dir': upload_dir,
        'media_root': media_root,
        'relative_dir': relative_dir,
    }


def _remove_trailer_file(movie, settings):
    if not movie or not movie.trailer_file_path:
        return

    media_root = settings.get('media_root') or ''
    absolute_path = os.path.join(media_root, movie.trailer_file_path)
    try:
        if os.path.exists(absolute_path):
            os.remove(absolute_path)
    except OSError as exc:
        current_app.logger.warning('Не удалось удалить старый трейлер %s: %s', absolute_path, exc)


def _get_poster_settings():
    """Возвращает настройки для хранения постеров."""
    config = current_app.config
    media_root = config.get('TRAILER_MEDIA_ROOT')
    upload_dir = config.get('POSTER_UPLOAD_DIR')
    relative_dir = config.get('POSTER_UPLOAD_SUBDIR', 'posters')

    return {
        'upload_dir': upload_dir,
        'media_root': media_root,
        'relative_dir': relative_dir,
    }


def _download_and_save_poster(poster_url, movie_id):
    """
    Скачивает постер по URL и сохраняет локально.
    Возвращает относительный путь к файлу или None при ошибке.
    """
    if not poster_url:
        return None

    settings = _get_poster_settings()
    upload_dir = settings.get('upload_dir')

    if not upload_dir:
        current_app.logger.warning('Директория для постеров не настроена')
        return None

    # Исправляем URL если нужно
    fixed_url = _fix_poster_url(poster_url)

    try:
        import requests
        response = requests.get(fixed_url, timeout=15, stream=True)
        response.raise_for_status()

        # Определяем расширение файла
        content_type = response.headers.get('Content-Type', '').lower()
        if 'jpeg' in content_type or 'jpg' in content_type:
            ext = '.jpg'
        elif 'png' in content_type:
            ext = '.png'
        elif 'webp' in content_type:
            ext = '.webp'
        else:
            ext = '.jpg'  # По умолчанию

        filename = f"poster_{movie_id}{ext}"
        os.makedirs(upload_dir, exist_ok=True)
        absolute_path = os.path.join(upload_dir, filename)

        with open(absolute_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        relative_path = os.path.join(settings.get('relative_dir', 'posters'), filename)
        current_app.logger.info('Постер сохранён: %s', relative_path)
        return relative_path

    except Exception as exc:
        current_app.logger.warning('Не удалось скачать постер %s: %s', fixed_url, exc)
        return None


def _remove_poster_file(movie):
    """Удаляет локальный файл постера."""
    if not movie:
        return

    try:
        poster_path = movie.poster_file_path
    except Exception:
        return

    if not poster_path:
        return

    settings = _get_poster_settings()
    media_root = settings.get('media_root') or ''
    absolute_path = os.path.join(media_root, poster_path)

    try:
        if os.path.exists(absolute_path):
            os.remove(absolute_path)
            current_app.logger.info('Постер удалён: %s', absolute_path)
    except OSError as exc:
        current_app.logger.warning('Не удалось удалить постер %s: %s', absolute_path, exc)


def _serialize_library_movie(movie):
    # Безопасно получаем атрибуты трейлера, которые могут отсутствовать в БД
    try:
        trailer_file_path = movie.trailer_file_path
        trailer_mime_type = movie.trailer_mime_type
        trailer_file_size = movie.trailer_file_size
        has_local_trailer = bool(trailer_file_path)
    except Exception:
        # Если колонки trailer_* ещё не существуют в БД
        trailer_file_path = None
        trailer_mime_type = None
        trailer_file_size = None
        has_local_trailer = False
    
    # Безопасно получаем стоимость просмотра трейлера
    try:
        trailer_view_cost = movie.trailer_view_cost
    except Exception:
        trailer_view_cost = None

    # Безопасно получаем локальный постер
    try:
        poster_file_path = movie.poster_file_path
        has_local_poster = bool(poster_file_path)
    except Exception:
        poster_file_path = None
        has_local_poster = False

    # Если есть локальный постер - используем его, иначе внешний URL
    if has_local_poster:
        poster_url = f'/api/posters/{movie.id}'
    else:
        poster_url = _fix_poster_url(movie.poster)
    
    return {
        'id': movie.id,
        'kinopoisk_id': movie.kinopoisk_id,
        'name': movie.name,
        'search_name': movie.search_name,
        'year': movie.year,
        'poster': poster_url,
        'has_local_poster': has_local_poster,
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
        'trailer_file_path': trailer_file_path,
        'trailer_mime_type': trailer_mime_type,
        'trailer_file_size': trailer_file_size,
        'has_local_trailer': has_local_trailer,
        'trailer_view_cost': trailer_view_cost,
    }


def _refresh_library_bans():
    try:
        if LibraryMovie.refresh_all_bans():
            db.session.commit()
    except Exception as exc:
        current_app.logger.warning("Ошибка при обновлении банов библиотеки: %s", exc)
        db.session.rollback()


def _serialize_poll_settings(settings):
    # Безопасно получаем poll_duration_minutes (для совместимости при миграции)
    try:
        poll_duration = getattr(settings, 'poll_duration_minutes', 1440) if settings else 1440
        if poll_duration is None:
            poll_duration = 1440
    except (AttributeError, OperationalError, ProgrammingError):
        poll_duration = 1440

    # Безопасно получаем winner_badge (для совместимости при миграции)
    try:
        winner_badge = getattr(settings, 'winner_badge', None) if settings else None
        if winner_badge and isinstance(winner_badge, str) and winner_badge.strip():
            winner_badge = winner_badge.strip()
        else:
            winner_badge = None
    except (AttributeError, OperationalError, ProgrammingError):
        winner_badge = None

    return {
        'custom_vote_cost': _get_custom_vote_cost(),
        'poll_duration_minutes': poll_duration,
        'winner_badge': winner_badge,
        'updated_at': settings.updated_at.isoformat() if settings and settings.updated_at else None,
        'created_at': settings.created_at.isoformat() if settings and settings.created_at else None,
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

    now = vladivostok_now()
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
        httponly=True,
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
        httponly=True,
    )

    if user_id:
        # user_id cookie остаётся доступным для JS (используется для отображения)
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


@api_bp.route('/polls/voter-stats/<string:voter_token>', methods=['DELETE'])
def delete_voter_profile(voter_token):
    """Delete a voter profile and its votes. Requires ADMIN_SECRET_KEY in Authorization header.
    This endpoint is intended to be used from the admin UI only.
    """
    import os
    auth_header = request.headers.get('Authorization', '')
    admin_secret = os.environ.get('ADMIN_SECRET_KEY')
    if not admin_secret:
        return jsonify({'error': 'Admin deletion disabled (ADMIN_SECRET_KEY not set)'}), 403
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing Authorization header'}), 401
    provided = auth_header[7:]
    if provided != admin_secret:
        current_app.logger.warning('Unauthorized attempt to delete voter profile %s from %s', voter_token, request.remote_addr)
        return jsonify({'error': 'Invalid admin secret'}), 403

    try:
        # Delete votes first to avoid FK constraint issues
        db.session.query(Vote).filter(Vote.voter_token == voter_token).delete(synchronize_session=False)
        deleted = db.session.query(PollVoterProfile).filter(PollVoterProfile.token == voter_token).delete(synchronize_session=False)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error('Error deleting voter profile %s: %s', voter_token, exc)
        return jsonify({'error': 'Failed to delete voter profile'}), 500

    if deleted:
        return jsonify({'success': True, 'deleted': int(deleted)})
    return jsonify({'success': True, 'deleted': 0})

@api_bp.route('/polls/settings', methods=['PATCH'])
def update_poll_settings_api():
    data = _get_json_payload()
    if data is None:
        return jsonify({'error': 'Передайте JSON в теле запроса'}), 400

    # Проверяем что передан хотя бы один параметр
    has_custom_vote_cost = 'custom_vote_cost' in data
    has_poll_duration = 'poll_duration_minutes' in data
    has_winner_badge = 'winner_badge' in data

    if not has_custom_vote_cost and not has_poll_duration and not has_winner_badge:
        return jsonify({'error': 'Передайте custom_vote_cost, poll_duration_minutes или winner_badge в теле запроса'}), 400

    new_cost = None
    new_duration = None
    new_winner_badge = None

    if has_custom_vote_cost:
        new_cost = data.get('custom_vote_cost')
        if isinstance(new_cost, bool) or not isinstance(new_cost, int):
            return jsonify({'error': 'custom_vote_cost должен быть целым числом'}), 400
        if new_cost < 0:
            return jsonify({'error': 'custom_vote_cost не может быть отрицательным'}), 400

    if has_poll_duration:
        new_duration = data.get('poll_duration_minutes')
        if isinstance(new_duration, bool) or not isinstance(new_duration, int):
            return jsonify({'error': 'poll_duration_minutes должен быть целым числом'}), 400
        if new_duration < 1:
            return jsonify({'error': 'poll_duration_minutes должен быть не менее 1 минуты'}), 400
        if new_duration > 5256000:
            return jsonify({'error': 'poll_duration_minutes не может превышать 5256000 минут (10 лет)'}), 400

    if has_winner_badge:
        new_winner_badge = data.get('winner_badge')
        # winner_badge может быть строкой, None или пустой строкой
        if new_winner_badge is not None and not isinstance(new_winner_badge, str):
            return jsonify({'error': 'winner_badge должен быть строкой или null'}), 400
        # Валидация допустимых значений
        allowed_badges = ['favorite', 'watchlist', 'top', 'watched', 'new', '', 'none', None]
        if new_winner_badge and new_winner_badge not in allowed_badges:
            # Проверяем формат кастомного бейджа
            if not new_winner_badge.startswith('custom_'):
                return jsonify({'error': 'Недопустимое значение winner_badge'}), 400
            # Проверяем что кастомный бейдж существует
            try:
                custom_id = int(new_winner_badge.split('_')[1])
                custom_badge = CustomBadge.query.get(custom_id)
                if not custom_badge:
                    return jsonify({'error': 'Кастомный бейдж не найден'}), 404
            except (ValueError, IndexError):
                return jsonify({'error': 'Некорректный формат кастомного бейджа'}), 400

    settings = update_poll_settings(
        custom_vote_cost=new_cost,
        poll_duration_minutes=new_duration,
        winner_badge=new_winner_badge
    )
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
    profile.updated_at = vladivostok_now()

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
        httponly=True,
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


def _fix_poster_url(poster_url):
    """Исправляет URL постера с нерабочего домена на рабочий."""
    if not poster_url:
        return poster_url
    # image.openmoviedb.com больше не работает, заменяем на avatars.mds.yandex.net
    if 'image.openmoviedb.com/kinopoisk-images/' in poster_url:
        return poster_url.replace(
            'image.openmoviedb.com/kinopoisk-images/',
            'avatars.mds.yandex.net/get-kinopoisk-image/'
        )
    return poster_url


def _serialize_poll_movie(movie):
    if not movie:
        return None

    # Получаем данные из библиотеки, если фильм там есть
    library_movie = None
    ban_cost_per_month = None
    has_trailer = False
    trailer_view_cost = None
    
    if movie.kinopoisk_id:
        library_movie = LibraryMovie.query.filter_by(kinopoisk_id=movie.kinopoisk_id).first()
    if not library_movie and movie.name and movie.year:
        library_movie = LibraryMovie.query.filter_by(name=movie.name, year=movie.year).first()
    
    if library_movie:
        if library_movie.ban_cost_per_month is not None:
            ban_cost_per_month = library_movie.ban_cost_per_month
        has_trailer = library_movie.has_local_trailer
        trailer_view_cost = library_movie.trailer_view_cost if library_movie.trailer_view_cost is not None else 1

    # Приоритет локальному постеру из библиотеки
    poster = None
    if library_movie:
        try:
            if library_movie.poster_file_path:
                poster = f'/api/posters/{library_movie.id}'
        except Exception:
            pass
    
    # Если нет локального постера - используем внешний URL с исправлением домена
    if not poster:
        poster = movie.poster
        if library_movie and library_movie.poster:
            poster = library_movie.poster
        poster = _fix_poster_url(poster)

    return {
        "id": movie.id,
        "kinopoisk_id": movie.kinopoisk_id,
        "name": movie.name,
        "search_name": movie.search_name,
        "poster": poster,
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
        "has_trailer": has_trailer,
        "trailer_view_cost": trailer_view_cost,
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
        "createdAt": lottery.created_at.isoformat(),
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

    # Загружаем только базовые колонки через load_only
    # Колонки трейлера обрабатываем через getattr() в сериализации
    from sqlalchemy.orm import load_only
    try:
        movies = (
            LibraryMovie.query
            .options(load_only(
                LibraryMovie.id,
                LibraryMovie.kinopoisk_id,
                LibraryMovie.name,
                LibraryMovie.search_name,
                LibraryMovie.poster,
                LibraryMovie.year,
                LibraryMovie.description,
                LibraryMovie.rating_kp,
                LibraryMovie.genres,
                LibraryMovie.countries,
                LibraryMovie.added_at,
                LibraryMovie.bumped_at,
                LibraryMovie.badge,
                LibraryMovie.points,
                LibraryMovie.ban_until,
                LibraryMovie.ban_applied_by,
                LibraryMovie.ban_cost,
                LibraryMovie.ban_cost_per_month,
            ))
            .order_by(LibraryMovie.bumped_at.desc())
            .all()
        )
    except (OperationalError, ProgrammingError) as exc:
        current_app.logger.warning(
            "LibraryMovie.bumped_at unavailable, falling back to added_at sorting. "
            "Run pending migrations. Error: %s",
            exc,
        )
        db.session.rollback()
        movies = (
            LibraryMovie.query
            .options(load_only(
                LibraryMovie.id,
                LibraryMovie.kinopoisk_id,
                LibraryMovie.name,
                LibraryMovie.search_name,
                LibraryMovie.poster,
                LibraryMovie.year,
                LibraryMovie.description,
                LibraryMovie.rating_kp,
                LibraryMovie.genres,
                LibraryMovie.countries,
                LibraryMovie.added_at,
                LibraryMovie.badge,
                LibraryMovie.points,
                LibraryMovie.ban_until,
                LibraryMovie.ban_applied_by,
                LibraryMovie.ban_cost,
                LibraryMovie.ban_cost_per_month,
            ))
            .order_by(LibraryMovie.added_at.desc())
            .all()
        )

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


@api_bp.route('/library/search', methods=['GET'])
def search_library_movie():
    """
    Поиск фильма в библиотеке по названию.
    Используется для открытия модального окна фильма из истории транзакций.
    
    Query params:
        name: название фильма для поиска (точное совпадение или частичное)
    
    Returns:
        JSON с данными фильма или 404 если не найден
    """
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({"success": False, "message": "Параметр 'name' обязателен"}), 400
    
    # Сначала пробуем точное совпадение
    movie = LibraryMovie.query.filter_by(name=name).first()
    
    # Если не найден - ищем по частичному совпадению (ILIKE)
    if not movie:
        movie = LibraryMovie.query.filter(
            LibraryMovie.name.ilike(f'%{name}%')
        ).first()
    
    if not movie:
        return jsonify({"success": False, "message": "Фильм не найден в библиотеке"}), 404
    
    # Сериализуем данные фильма
    data = _serialize_library_movie(movie)
    
    # Добавляем информацию о magnet-ссылке
    identifier = None
    if movie.kinopoisk_id:
        identifier = MovieIdentifier.query.filter_by(kinopoisk_id=movie.kinopoisk_id).first()
    
    data['has_magnet'] = bool(identifier)
    data['magnet_link'] = identifier.magnet_link if identifier else ''
    data['is_on_client'] = False
    data['torrent_hash'] = None
    
    return prevent_caching(jsonify({"success": True, "movie": data}))


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

    poster_url = movie_data.get('poster')
    movie_for_poster = None

    if existing_movie:
        for key, value in movie_data.items():
            if hasattr(existing_movie, key) and value is not None:
                setattr(existing_movie, key, value)
        existing_movie.bumped_at = vladivostok_now()
        movie_for_poster = existing_movie
        message = "Информация о фильме в библиотеке обновлена."
    else:
        new_movie = LibraryMovie(**movie_data)
        if new_movie.added_at is None:
            now = vladivostok_now()
            new_movie.added_at = now
            new_movie.bumped_at = now
        else:
            new_movie.bumped_at = new_movie.added_at
        db.session.add(new_movie)
        db.session.flush()  # Получаем ID для нового фильма
        movie_for_poster = new_movie
        message = "Фильм добавлен в библиотеку."

    # Скачиваем постер локально если его ещё нет
    if movie_for_poster and poster_url:
        try:
            has_local = movie_for_poster.poster_file_path
        except Exception:
            has_local = None

        if not has_local:
            poster_path = _download_and_save_poster(poster_url, movie_for_poster.id)
            if poster_path:
                movie_for_poster.poster_file_path = poster_path

    # Add poster to background when movie is added to library
    if poster_url:
        ensure_background_photo(poster_url)

    db.session.commit()
    return jsonify({"success": True, "message": message})


@api_bp.route('/library/add-from-url', methods=['POST'])
def add_library_movie_from_url():
    """
    Добавление фильма в библиотеку по URL или ID Кинопоиска.
    Используется браузерным расширением для быстрого добавления фильмов.
    
    Принимает JSON: {"url": "https://www.kinopoisk.ru/film/12345/"}
    или: {"url": "12345"} (просто ID)
    """
    payload = _get_json_payload()
    if payload is None:
        return jsonify({
            "success": False, 
            "message": "Некорректный JSON-запрос."
        }), 400

    url = payload.get('url', '').strip()
    if not url:
        return jsonify({
            "success": False, 
            "message": "URL или ID фильма не указан."
        }), 400

    # Получаем данные фильма с Кинопоиска
    movie_data, error = get_movie_data_from_kinopoisk(url)
    
    if not movie_data:
        message = "Фильм не найден на Кинопоиске."
        if error and error.get('message'):
            message = error['message']
        return jsonify({
            "success": False, 
            "message": message
        }), 404

    # Проверяем, есть ли уже этот фильм в библиотеке
    kinopoisk_id = movie_data.get('kinopoisk_id')
    existing_movie = None
    
    if kinopoisk_id:
        existing_movie = LibraryMovie.query.filter_by(kinopoisk_id=kinopoisk_id).first()

    if not existing_movie:
        existing_movie = LibraryMovie.query.filter_by(
            name=movie_data['name'], 
            year=movie_data.get('year')
        ).first()

    poster_url = movie_data.get('poster')
    movie_for_poster = None

    if existing_movie:
        # Обновляем данные существующего фильма
        for key, value in movie_data.items():
            if hasattr(existing_movie, key) and value is not None:
                setattr(existing_movie, key, value)
        existing_movie.bumped_at = vladivostok_now()
        movie_for_poster = existing_movie
        message = f"Фильм «{movie_data['name']}» уже был в библиотеке. Данные обновлены."
        is_new = False
    else:
        # Создаём новый фильм
        new_movie = LibraryMovie(**movie_data)
        now = vladivostok_now()
        new_movie.added_at = now
        new_movie.bumped_at = now
        db.session.add(new_movie)
        db.session.flush()
        movie_for_poster = new_movie
        message = f"Фильм «{movie_data['name']}» добавлен в библиотеку!"
        is_new = True

    # Скачиваем постер локально если его ещё нет
    if movie_for_poster and poster_url:
        try:
            has_local = movie_for_poster.poster_file_path
        except Exception:
            has_local = None

        if not has_local:
            poster_path = _download_and_save_poster(poster_url, movie_for_poster.id)
            if poster_path:
                movie_for_poster.poster_file_path = poster_path

    # Add poster to background
    if poster_url:
        ensure_background_photo(poster_url)

    db.session.commit()
    
    return jsonify({
        "success": True, 
        "message": message,
        "movie": {
            "id": movie_for_poster.id,
            "name": movie_data['name'],
            "year": movie_data.get('year'),
            "poster": poster_url,
            "is_new": is_new
        }
    })


@api_bp.route('/library/<int:movie_id>', methods=['DELETE'])
def remove_library_movie(movie_id):
    library_movie = LibraryMovie.query.get_or_404(movie_id)
    _remove_trailer_file(library_movie, _get_trailer_settings())
    _remove_poster_file(library_movie)
    db.session.delete(library_movie)
    db.session.commit()
    return jsonify({"success": True, "message": "Фильм удален из библиотеки."})


@api_bp.route('/movies/<int:movie_id>/trailer-local', methods=['POST'])
def upload_local_trailer(movie_id):
    library_movie = LibraryMovie.query.get_or_404(movie_id)
    settings = _get_trailer_settings()

    trailer_file = request.files.get('trailer')
    if not trailer_file or not trailer_file.filename:
        return jsonify({"success": False, "message": "Файл трейлера не найден в запросе."}), 400

    if not settings.get('upload_dir'):
        return jsonify({"success": False, "message": "Директория загрузки трейлеров не настроена."}), 500

    mimetype = (trailer_file.mimetype or '').lower()
    allowed_mime_types = settings.get('allowed_mime_types', [])
    if allowed_mime_types and mimetype and mimetype not in allowed_mime_types:
        return jsonify({"success": False, "message": "Недопустимый тип файла. Загрузите видеофайл."}), 400

    try:
        trailer_file.stream.seek(0, os.SEEK_END)
        file_size = trailer_file.stream.tell()
        trailer_file.stream.seek(0)
    except Exception:
        file_size = request.content_length or 0

    max_size = settings.get('max_size') or 0
    if max_size and file_size and file_size > max_size:
        return jsonify({"success": False, "message": "Размер файла превышает допустимый лимит."}), 400

    original_ext = os.path.splitext(trailer_file.filename)[1].lower()
    guessed_ext = mimetypes.guess_extension(mimetype or '') or ''
    safe_ext = original_ext if original_ext else guessed_ext
    filename = f"movie_{movie_id}_{uuid.uuid4().hex}{safe_ext}"

    os.makedirs(settings['upload_dir'], exist_ok=True)
    absolute_path = os.path.join(settings['upload_dir'], filename)
    previous_trailer_path = library_movie.trailer_file_path

    try:
        trailer_file.save(absolute_path)
    except Exception as exc:
        current_app.logger.exception('Не удалось сохранить трейлер: %s', exc)
        return jsonify({"success": False, "message": "Не удалось сохранить трейлер на сервере."}), 500

    # Apply faststart optimization for web playback
    faststart_result = apply_faststart(absolute_path)
    if faststart_result['success'] and faststart_result['new_size']:
        file_size = faststart_result['new_size']
    elif not faststart_result['success']:
        current_app.logger.warning('Не удалось применить faststart: %s', faststart_result['message'])

    relative_path = os.path.join(settings.get('relative_dir', 'trailers'), filename)
    library_movie.trailer_file_path = relative_path
    library_movie.trailer_mime_type = mimetype or None
    library_movie.trailer_file_size = file_size if file_size else None
    library_movie.bumped_at = vladivostok_now()

    if previous_trailer_path:
        temp_movie = LibraryMovie(trailer_file_path=previous_trailer_path)
        _remove_trailer_file(temp_movie, settings)

    db.session.commit()

    identifier = None
    if library_movie.kinopoisk_id:
        identifier = MovieIdentifier.query.filter_by(kinopoisk_id=library_movie.kinopoisk_id).first()

    data = _serialize_library_movie(library_movie)
    data['has_magnet'] = bool(identifier)
    data['magnet_link'] = identifier.magnet_link if identifier else ''
    data['is_on_client'] = False
    data['torrent_hash'] = None

    return jsonify({"success": True, "movie": data})


@api_bp.route('/trailers/apply-faststart', methods=['POST'])
def batch_apply_faststart():
    """Apply faststart optimization to all existing trailers."""
    settings = _get_trailer_settings()
    upload_dir = settings.get('upload_dir')

    if not upload_dir:
        return jsonify({
            "success": False,
            "message": "Директория загрузки трейлеров не настроена."
        }), 500

    # Find all library movies with trailers
    movies_with_trailers = LibraryMovie.query.filter(
        LibraryMovie.trailer_file_path.isnot(None),
        LibraryMovie.trailer_file_path != ''
    ).all()

    results = {
        'total': len(movies_with_trailers),
        'processed': 0,
        'skipped': 0,
        'failed': 0,
        'details': []
    }

    for movie in movies_with_trailers:
        # Construct absolute path from relative path
        relative_path = movie.trailer_file_path
        # Remove the relative_dir prefix if present to get just the filename
        filename = os.path.basename(relative_path)
        absolute_path = os.path.join(upload_dir, filename)

        if not os.path.exists(absolute_path):
            results['skipped'] += 1
            results['details'].append({
                'movie_id': movie.id,
                'name': movie.name,
                'status': 'skipped',
                'message': 'Файл не найден'
            })
            continue

        faststart_result = apply_faststart(absolute_path)

        if faststart_result['success']:
            # Update file size in DB if changed
            if faststart_result['new_size']:
                movie.trailer_file_size = faststart_result['new_size']

            results['processed'] += 1
            results['details'].append({
                'movie_id': movie.id,
                'name': movie.name,
                'status': 'processed',
                'message': faststart_result['message']
            })
        else:
            results['failed'] += 1
            results['details'].append({
                'movie_id': movie.id,
                'name': movie.name,
                'status': 'failed',
                'message': faststart_result['message']
            })

    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Обработано: {results['processed']}, пропущено: {results['skipped']}, ошибок: {results['failed']}",
        "results": results
    })


@api_bp.route('/posters/migrate-all', methods=['POST'])
def migrate_all_posters():
    """Скачивает все постеры локально для фильмов без локальных постеров."""
    movies = LibraryMovie.query.all()

    results = {
        'total': len(movies),
        'downloaded': 0,
        'skipped': 0,
        'failed': 0,
        'details': []
    }

    for movie in movies:
        # Проверяем, есть ли уже локальный постер
        try:
            has_local = bool(movie.poster_file_path)
        except Exception:
            has_local = False

        if has_local:
            results['skipped'] += 1
            results['details'].append({
                'movie_id': movie.id,
                'name': movie.name,
                'status': 'skipped',
                'message': 'Постер уже скачан'
            })
            continue

        if not movie.poster:
            results['skipped'] += 1
            results['details'].append({
                'movie_id': movie.id,
                'name': movie.name,
                'status': 'skipped',
                'message': 'Нет URL постера'
            })
            continue

        poster_path = _download_and_save_poster(movie.poster, movie.id)

        if poster_path:
            try:
                movie.poster_file_path = poster_path
                results['downloaded'] += 1
                results['details'].append({
                    'movie_id': movie.id,
                    'name': movie.name,
                    'status': 'downloaded',
                    'message': f'Сохранено: {poster_path}'
                })
            except Exception as exc:
                results['failed'] += 1
                results['details'].append({
                    'movie_id': movie.id,
                    'name': movie.name,
                    'status': 'failed',
                    'message': f'Ошибка сохранения: {exc}'
                })
        else:
            results['failed'] += 1
            results['details'].append({
                'movie_id': movie.id,
                'name': movie.name,
                'status': 'failed',
                'message': 'Не удалось скачать постер'
            })

    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Скачано: {results['downloaded']}, пропущено: {results['skipped']}, ошибок: {results['failed']}",
        "results": results
    })


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
    library_movie.bumped_at = vladivostok_now()
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
        library_movie.bumped_at = vladivostok_now()
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
    library_movie.bumped_at = vladivostok_now()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Цена за месяц бана обновлена.",
        "ban_cost_per_month": library_movie.ban_cost_per_month,
    })


@api_bp.route('/library/<int:movie_id>/trailer-view-cost', methods=['PUT'])
def update_library_movie_trailer_view_cost(movie_id):
    """Обновление цены за просмотр трейлера для фильма"""
    data = _get_json_payload()
    if data is None:
        return jsonify({"success": False, "message": "Некорректный JSON-запрос."}), 400

    raw_cost = data.get('trailer_view_cost')
    
    # Если значение None или null, устанавливаем None (используется значение по умолчанию 1)
    if raw_cost is None:
        library_movie = LibraryMovie.query.get_or_404(movie_id)
        library_movie.trailer_view_cost = None
        library_movie.bumped_at = vladivostok_now()
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Цена за просмотр трейлера сброшена к значению по умолчанию.",
            "trailer_view_cost": None,
        })

    try:
        cost = int(raw_cost)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Цена за просмотр трейлера должна быть целым числом."}), 400

    if cost < 0 or cost > 999:
        return jsonify({"success": False, "message": "Цена за просмотр трейлера должна быть в диапазоне от 0 до 999."}), 400

    library_movie = LibraryMovie.query.get_or_404(movie_id)
    library_movie.trailer_view_cost = cost
    library_movie.bumped_at = vladivostok_now()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Цена за просмотр трейлера обновлена.",
        "trailer_view_cost": library_movie.trailer_view_cost,
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


# Доступные темы для опросов
POLL_AVAILABLE_THEMES = ['default', 'newyear']


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

    # Получаем тему опроса (из payload или cookie)
    poll_theme = payload.get('theme') or request.cookies.get('poll_theme', 'default')
    if poll_theme not in POLL_AVAILABLE_THEMES:
        poll_theme = 'default'

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

    # Получаем время жизни опроса из настроек (фиксируем на момент создания)
    poll_duration_mins = get_poll_duration_minutes()
    expires_at = vladivostok_now() + timedelta(minutes=poll_duration_mins)

    new_poll = Poll(
        id=generate_unique_poll_id(),
        creator_token=creator_token,
        theme=poll_theme,
        expires_at=expires_at
    )
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
        "results_url": results_url,
        "theme": new_poll.theme
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
    streak_info = get_voter_streak_info(profile)

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

    # Безопасный доступ к полю theme (на случай если колонка ещё не создана в БД)
    try:
        poll_theme = poll.theme or 'default'
    except Exception:
        poll_theme = 'default'

    response = prevent_caching(jsonify({
        "poll_id": poll.id,
        "movies": movies_data,
        "created_at": poll.created_at.isoformat(),
        "expires_at": poll.expires_at.isoformat(),
        "has_voted": bool(existing_vote),
        "voted_movie": voted_movie_data,
        "voted_points_delta": voted_points_delta,
        "total_votes": len(poll.votes),
        "points_balance": points_balance,
        "points_earned_total": points_earned_total,
        "voter_token": voter_token,
        "user_id": user_id,
        "custom_vote_cost": custom_vote_cost,
        "custom_vote_cost_updated_at": poll_settings.updated_at.isoformat() if poll_settings and poll_settings.updated_at else None,
        "can_vote_custom": can_vote_custom,
        "is_expired": poll.is_expired,
        "theme": poll_theme,
        "closed_by_ban": closed_by_ban,
        "forced_winner": _serialize_poll_movie(poll.winners[0]) if closed_by_ban and poll.winners else None,
        "poll_settings": _serialize_poll_settings(poll_settings),
        "streak": streak_info,
    }))

    return _set_voter_cookies(response, voter_token, user_id)


@api_bp.route('/polls/streak-info', methods=['GET'])
def get_streak_info():
    """Получение информации о streak текущего пользователя"""
    identity = _resolve_voter_identity()
    voter_token = identity['voter_token']
    profile = identity['profile']
    user_id = identity['user_id']
    db.session.commit()

    streak_info = get_voter_streak_info(profile)
    points_balance = profile.total_points or 0
    points_earned_total = profile.points_accrued_total or 0

    response = prevent_caching(jsonify({
        "streak": streak_info,
        "points_balance": points_balance,
        "points_earned_total": points_earned_total,
        "voter_token": voter_token,
        "user_id": user_id,
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
    profile = identity['profile']

    # Проверяем, не голосовал ли уже этот пользователь
    existing_vote = Vote.query.filter_by(poll_id=poll_id, voter_token=voter_token).first()
    if existing_vote:
        return jsonify({"error": "Вы уже проголосовали в этом опросе"}), 400

    # Обновляем streak и получаем бонус
    streak_result = update_voter_streak(profile)
    streak_bonus = streak_result.get('streak_bonus', 0)

    default_points_per_vote = current_app.config.get('POLL_POINTS_PER_VOTE', 1)
    base_points = _normalize_poll_movie_points(movie.points, default_points_per_vote)
    
    # Общее количество баллов = базовые + streak бонус
    points_awarded = base_points + streak_bonus

    # Создаём новый голос
    new_vote = Vote(
        poll_id=poll_id,
        movie_id=movie_id,
        voter_token=voter_token,
        points_awarded=points_awarded,
    )
    db.session.add(new_vote)

    balance_before = profile.total_points or 0  # баланс до начисления
    new_balance = change_voter_points_balance(
        voter_token,
        points_awarded,
        device_label=device_label,
    )

    # Логируем транзакцию
    if points_awarded != 0:
        description = f"Голосование за «{movie.name}»"
        if streak_bonus > 0:
            description += f" (+{base_points} базовых +{streak_bonus} бонус)"
        log_points_transaction(
            voter_token=voter_token,
            transaction_type='vote',
            amount=points_awarded,
            balance_before=balance_before,
            balance_after=new_balance,
            description=description,
            movie_name=movie.name,
            poll_id=poll_id,
        )

    db.session.commit()

    # Отправляем push-уведомления о новом голосе в фоновом потоке (не блокирует ответ)
    try:
        total_votes = Vote.query.filter_by(poll_id=poll_id).count()
        voted_movie_name = movie.name
        current_app.logger.info(f'[Push] Голос получен в опросе {poll_id}, запуск отправки уведомлений в фоне...')
        
        # Запускаем отправку в отдельном потоке с копией app context
        app = current_app._get_current_object()
        
        def send_notifications_async():
            with app.app_context():
                try:
                    send_vote_notifications(
                        poll_id=poll_id,
                        voted_movie_name=voted_movie_name,
                        total_votes=total_votes,
                    )
                except Exception as e:
                    app.logger.error(f'[Push] Ошибка в фоновом потоке отправки push-уведомлений: {e}', exc_info=True)
        
        thread = threading.Thread(target=send_notifications_async, daemon=True)
        thread.start()
    except Exception as e:
        current_app.logger.error(f'[Push] Ошибка запуска фоновой отправки push-уведомлений для опроса {poll_id}: {e}', exc_info=True)

    # Fetch updated profile to get current points_accrued_total
    profile = ensure_voter_profile(voter_token, device_label=device_label)
    points_accrued = profile.points_accrued_total or 0
    streak_info = get_voter_streak_info(profile)

    # Формируем сообщение с учётом streak
    if points_awarded > 0:
        if streak_bonus > 0:
            success_message = f"Голос учтён! +{base_points} баллов +{streak_bonus} бонус за серию = {points_awarded} баллов!"
        else:
            success_message = f"Голос учтён! +{points_awarded} баллов к вашему счёту."
    else:
        success_message = "Голос учтён! Приятного просмотра!"

    response = prevent_caching(jsonify({
        "success": True,
        "message": success_message,
        "movie_name": movie.name,
        "base_points": base_points,
        "streak_bonus": streak_bonus,
        "points_awarded": points_awarded,
        "points_balance": new_balance,
        "points_earned_total": points_accrued,
        "voted_movie": _serialize_poll_movie(movie),
        "streak": streak_info,
        "streak_continued": streak_result.get('streak_continued', False),
        "streak_broken": streak_result.get('streak_broken', False),
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

    now_utc = vladivostok_now()
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
        library_movie.bumped_at = vladivostok_now()
        library_ban_data = _serialize_library_movie(library_movie)

    new_balance = change_voter_points_balance(
        voter_token,
        -total_cost,
        device_label=device_label,
    )

    # Логируем транзакцию
    months_word = _plural_months(months)
    log_points_transaction(
        voter_token=voter_token,
        transaction_type='ban',
        amount=-total_cost,
        balance_before=balance_before,
        balance_after=new_balance,
        description=f"Бан «{movie.name}» на {months} {months_word}",
        movie_name=movie.name,
        poll_id=poll_id,
    )

    active_movies_after = _get_active_poll_movies(poll)
    forced_winner = None
    closed_by_ban = False
    if len(active_movies_after) == 1:
        forced_winner = active_movies_after[0]
        poll.forced_winner_movie_id = forced_winner.id
        poll.expires_at = vladivostok_now()
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
    balance_before = profile.total_points or 0

    new_balance = change_voter_points_balance(
        voter_token,
        points_awarded,
        device_label=device_label,
    )

    if new_balance < 0:
        db.session.rollback()
        return jsonify({"error": "Недостаточно баллов для кастомного голосования"}), 400

    # Логируем транзакцию
    movie_name = movie_data.get('name') or poll_movie.name
    log_points_transaction(
        voter_token=voter_token,
        transaction_type='custom_vote',
        amount=points_awarded,
        balance_before=balance_before,
        balance_after=new_balance,
        description=f"Кастомный голос за «{movie_name}»",
        movie_name=movie_name,
        poll_id=poll_id,
    )

    new_vote = Vote(
        poll_id=poll_id,
        movie_id=poll_movie.id,
        voter_token=voter_token,
        points_awarded=points_awarded,
    )
    db.session.add(new_vote)

    db.session.commit()

    # Отправляем push-уведомления о новом голосе в фоновом потоке (не блокирует ответ)
    try:
        total_votes = Vote.query.filter_by(poll_id=poll_id).count()
        voted_movie_name = movie_name
        current_app.logger.info(f'[Push] Кастомный голос получен в опросе {poll_id}, запуск отправки уведомлений в фоне...')
        
        app = current_app._get_current_object()
        
        def send_notifications_async():
            with app.app_context():
                try:
                    send_vote_notifications(
                        poll_id=poll_id,
                        voted_movie_name=voted_movie_name,
                        total_votes=total_votes,
                    )
                except Exception as e:
                    app.logger.error(f'[Push] Ошибка в фоновом потоке отправки push-уведомлений: {e}', exc_info=True)
        
        thread = threading.Thread(target=send_notifications_async, daemon=True)
        thread.start()
    except Exception as e:
        current_app.logger.error(f'[Push] Ошибка запуска фоновой отправки push-уведомлений для опроса {poll_id}: {e}', exc_info=True)

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
                "countries": w.countries,
                "points": w.points if w.points is not None else 1,
            }
            for w in winners
        ],
        "custom_vote_cost": _get_custom_vote_cost(),
        "poll_settings": _serialize_poll_settings(poll_settings),
        "created_at": poll.created_at.isoformat(),
        "expires_at": poll.expires_at.isoformat(),
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
        
        # Собираем список забаненных фильмов
        banned_movies = [
            {
                "id": m.id,
                "name": m.name,
                "year": m.year,
                "poster": m.poster,
                "ban_until": m.ban_until.isoformat() if m.ban_until else None,
            }
            for m in poll.movies
            if m.ban_status == 'active'
        ]
        
        polls_data.append({
            "poll_id": poll.id,
            "created_at": poll.created_at.isoformat(),
            "expires_at": poll.expires_at.isoformat(),
            "is_expired": poll.is_expired,
            "closed_by_ban": bool(poll.forced_winner_movie_id),
            "total_votes": len(poll.votes),
            "movies_count": len(poll.movies),
            "notifications_enabled": bool(poll.notifications_enabled),
            "winners": [
                {
                    "id": w.id,
                    "name": w.name,
                    "search_name": w.search_name,
                    "poster": w.poster,
                    "year": w.year,
                    "countries": w.countries,
                    "points": w.points if w.points is not None else 1,
                    "votes": vote_counts.get(w.id, 0)
                }
                for w in winners
            ],
            "banned_movies": banned_movies,
            "poll_url": build_external_url('main.view_poll', poll_id=poll.id),
            "results_url": build_external_url('main.view_poll_results', poll_id=poll.id)
        })

    return prevent_caching(jsonify({"polls": polls_data}))


@api_bp.route('/polls/cleanup-expired', methods=['POST'])
def cleanup_expired_polls_api():
    """Удаление истёкших опросов (можно вызывать по cron или вручную).
    
    Перед удалением проверяет настройку winner_badge:
    - Если бейдж победителя настроен и победитель ровно один,
      применяет бейдж к соответствующему фильму в библиотеке.
    
    Использует ту же функцию что и scheduler.
    """
    from ..utils.helpers import cleanup_expired_polls as do_cleanup
    
    count = do_cleanup()
    
    return jsonify({
        "success": True,
        "deleted_count": count,
    })


@api_bp.route('/polls/<poll_id>/watch-trailer', methods=['POST'])
def watch_trailer_in_poll(poll_id):
    """Просмотр трейлера фильма в опросе с оплатой баллами"""
    poll = Poll.query.get_or_404(poll_id)

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

    # Ищем фильм в библиотеке по kinopoisk_id или name+year
    library_movie = None
    if movie.kinopoisk_id:
        library_movie = LibraryMovie.query.filter_by(kinopoisk_id=movie.kinopoisk_id).first()
    if not library_movie and movie.name and movie.year:
        library_movie = LibraryMovie.query.filter_by(name=movie.name, year=movie.year).first()

    if not library_movie:
        return jsonify({"error": "Фильм не найден в библиотеке"}), 404

    # Проверяем наличие трейлера
    if not library_movie.has_local_trailer:
        return jsonify({"error": "Трейлер для этого фильма не загружен"}), 404

    # Получаем стоимость просмотра
    trailer_cost = library_movie.trailer_view_cost if library_movie.trailer_view_cost is not None else 1

    # Получаем профиль пользователя
    identity = _resolve_voter_identity()
    voter_token = identity['voter_token']
    device_label = identity['device_label']
    user_id = identity['user_id']
    profile = identity['profile']
    balance_before = profile.total_points or 0

    # Проверяем баланс
    if trailer_cost > 0 and balance_before < trailer_cost:
        return jsonify({
            "error": f"Недостаточно баллов для просмотра трейлера. Требуется {trailer_cost} баллов.",
            "required_cost": trailer_cost,
            "points_balance": balance_before,
        }), 403

    # Списываем баллы
    new_balance = balance_before
    if trailer_cost > 0:
        new_balance = change_voter_points_balance(
            voter_token,
            -trailer_cost,
            device_label=device_label,
        )

        # Логируем транзакцию
        log_points_transaction(
            voter_token=voter_token,
            transaction_type='trailer',
            amount=-trailer_cost,
            balance_before=balance_before,
            balance_after=new_balance,
            description=f"Просмотр трейлера «{movie.name}»",
            movie_name=movie.name,
            poll_id=poll_id,
        )

        db.session.commit()

    # Fetch updated profile
    profile = ensure_voter_profile(voter_token, device_label=device_label)
    points_accrued = profile.points_accrued_total or 0

    # Формируем URL для трейлера
    settings = _get_trailer_settings()
    trailer_url = f"/api/trailers/{library_movie.id}/stream"

    response = prevent_caching(jsonify({
        "success": True,
        "trailer_url": trailer_url,
        "trailer_mime_type": library_movie.trailer_mime_type,
        "movie_name": movie.name,
        "cost_deducted": trailer_cost,
        "points_balance": new_balance,
        "points_earned_total": points_accrued,
    }))

    return _set_voter_cookies(response, voter_token, user_id)


@api_bp.route('/trailers/<int:movie_id>/stream', methods=['GET'])
def stream_trailer(movie_id):
    """Отдача видеофайла трейлера"""
    from flask import send_file, Response
    
    library_movie = LibraryMovie.query.get_or_404(movie_id)
    
    if not library_movie.has_local_trailer:
        return jsonify({"error": "Трейлер не найден"}), 404

    settings = _get_trailer_settings()
    media_root = settings.get('media_root') or ''
    
    # trailer_file_path хранится как "trailers/filename.mp4"
    # media_root = instance/media
    # Итоговый путь: instance/media/trailers/filename.mp4
    # Нормализуем путь для кроссплатформенности
    normalized_file_path = library_movie.trailer_file_path.replace('\\', '/').replace('/', os.sep)
    trailer_path = os.path.normpath(os.path.join(media_root, normalized_file_path))
    
    # Защита от path traversal: проверяем, что путь не выходит за пределы media_root
    normalized_media_root = os.path.normpath(media_root)
    if not trailer_path.startswith(normalized_media_root + os.sep) and trailer_path != normalized_media_root:
        current_app.logger.warning('Path traversal attempt detected: %s', trailer_path)
        return jsonify({"error": "Недопустимый путь к файлу"}), 400
    
    current_app.logger.debug('Streaming trailer: media_root=%s, file_path=%s, full_path=%s', 
                             media_root, library_movie.trailer_file_path, trailer_path)

    if not os.path.exists(trailer_path):
        current_app.logger.error('Файл трейлера не найден: %s', trailer_path)
        return jsonify({"error": "Файл трейлера не найден"}), 404

    mime_type = library_movie.trailer_mime_type or 'video/mp4'

    # Поддержка Range requests для видео
    file_size = os.path.getsize(trailer_path)
    range_header = request.headers.get('Range')

    if range_header:
        # Парсим Range header
        byte_start = 0
        byte_end = file_size - 1
        
        range_match = re.match(r'bytes=(\d*)-(\d*)', range_header)
        if range_match:
            start_str, end_str = range_match.groups()
            if start_str:
                byte_start = int(start_str)
            if end_str:
                byte_end = int(end_str)
        
        byte_end = min(byte_end, file_size - 1)
        content_length = byte_end - byte_start + 1

        def generate():
            with open(trailer_path, 'rb') as f:
                f.seek(byte_start)
                remaining = content_length
                chunk_size = 1024 * 1024  # 1MB chunks для быстрого стриминга
                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        response = Response(
            generate(),
            status=206,
            mimetype=mime_type,
            direct_passthrough=True
        )
        response.headers['Content-Range'] = f'bytes {byte_start}-{byte_end}/{file_size}'
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Length'] = content_length
        response.headers['Content-Type'] = mime_type
        # Запрет кэширования для корректной работы после замены трейлера
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    else:
        response = send_file(
            trailer_path,
            mimetype=mime_type,
            as_attachment=False,
        )
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Length'] = file_size
        # Запрет кэширования для корректной работы после замены трейлера
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response


@api_bp.route('/movies/<int:kinopoisk_id>/trailer-info', methods=['GET'])
def get_trailer_info(kinopoisk_id):
    """Получение информации о трейлере фильма по kinopoisk_id"""
    library_movie = LibraryMovie.query.filter_by(kinopoisk_id=kinopoisk_id).first()
    
    if not library_movie:
        return jsonify({
            "has_trailer": False,
            "trailer_view_cost": None,
        })

    return jsonify({
        "has_trailer": library_movie.has_local_trailer,
        "trailer_view_cost": library_movie.trailer_view_cost if library_movie.trailer_view_cost is not None else 1,
        "movie_id": library_movie.id,
    })


@api_bp.route('/posters/<int:movie_id>', methods=['GET'])
def get_poster(movie_id):
    """Отдача локального постера фильма"""
    from flask import send_file
    
    library_movie = LibraryMovie.query.get_or_404(movie_id)
    
    try:
        poster_path = library_movie.poster_file_path
    except Exception:
        poster_path = None
    
    if not poster_path:
        return jsonify({"error": "Постер не найден"}), 404

    settings = _get_poster_settings()
    media_root = settings.get('media_root') or ''
    
    # Нормализуем путь для кроссплатформенности
    normalized_path = poster_path.replace('\\', '/').replace('/', os.sep)
    absolute_path = os.path.normpath(os.path.join(media_root, normalized_path))
    
    # Защита от path traversal: проверяем, что путь не выходит за пределы media_root
    normalized_media_root = os.path.normpath(media_root)
    if not absolute_path.startswith(normalized_media_root + os.sep) and absolute_path != normalized_media_root:
        current_app.logger.warning('Path traversal attempt detected for poster: %s', absolute_path)
        return jsonify({"error": "Недопустимый путь к файлу"}), 400
    
    if not os.path.exists(absolute_path):
        current_app.logger.error('Файл постера не найден: %s', absolute_path)
        return jsonify({"error": "Файл постера не найден"}), 404

    # Определяем MIME-тип по расширению
    ext = os.path.splitext(absolute_path)[1].lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp',
    }
    mime_type = mime_types.get(ext, 'image/jpeg')

    response = send_file(
        absolute_path,
        mimetype=mime_type,
        as_attachment=False,
    )
    # Кешируем постеры на долгий срок
    response.headers['Cache-Control'] = 'public, max-age=31536000'
    return response


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

    # Поддержка кастомных бейджей в формате custom_ID
    is_custom_badge = False
    if badge_type and badge_type.startswith('custom_'):
        try:
            custom_id = int(badge_type.split('_')[1])
            custom_badge = CustomBadge.query.get(custom_id)
            if not custom_badge:
                return jsonify({"success": False, "message": "Кастомный бейдж не найден"}), 404
            is_custom_badge = True
        except (ValueError, IndexError):
            return jsonify({"success": False, "message": "Некорректный формат кастомного бейджа"}), 400
    elif badge_type and badge_type not in allowed_badges:
        return jsonify({"success": False, "message": "Недопустимый тип бейджа"}), 400

    ban_until = None
    ban_applied_by = None
    ban_cost = None

    if badge_type == 'ban':
        ban_until_raw = payload.get('ban_until')
        ban_duration_months = payload.get('ban_duration_months')

        now_utc = vladivostok_now()
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
    library_movie.bumped_at = vladivostok_now()
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
    library_movie.bumped_at = vladivostok_now()
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
    
    # Добавляем все типы стандартных бейджей с нулевыми значениями для отсутствующих
    all_badges = ['favorite', 'ban', 'watchlist', 'top', 'watched', 'new']
    result = {badge: stats.get(badge, 0) for badge in all_badges}

    # Добавляем статистику для кастомных бейджей
    custom_badges = CustomBadge.query.all()
    for custom_badge in custom_badges:
        badge_key = f"custom_{custom_badge.id}"
        result[badge_key] = stats.get(badge_key, 0)

    return jsonify(result)

@api_bp.route('/library/badges/<badge_type>/movies', methods=['GET'])
def get_movies_by_badge(badge_type):
    """Получение списка фильмов с определённым бейджем для создания опроса"""
    allowed_badges = ['favorite', 'ban', 'watchlist', 'top', 'watched', 'new']

    # Поддержка кастомных бейджей в формате custom_ID
    is_custom_badge = False
    if badge_type.startswith('custom_'):
        try:
            custom_id = int(badge_type.split('_')[1])
            custom_badge = CustomBadge.query.get(custom_id)
            if not custom_badge:
                return jsonify({"error": "Кастомный бейдж не найден"}), 404
            is_custom_badge = True
        except (ValueError, IndexError):
            return jsonify({"error": "Некорректный формат кастомного бейджа"}), 400
    elif badge_type not in allowed_badges:
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

    # Сохраняем общее количество до ограничения
    total_count = len(movies)
    
    # Перемешиваем фильмы для рандомного порядка в опросе
    random.shuffle(movies)
    
    # Ограничиваем количество фильмов до 25
    limited = False
    if len(movies) > 25:
        movies = movies[:25]
        limited = True
    
    movies_data = [_serialize_library_movie(movie) for movie in movies]
    
    return jsonify({
        'movies': movies_data,
        'total': total_count,
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
            streak_info = get_voter_streak_info(profile)
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
                'streak': streak_info,
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
    profile.updated_at = vladivostok_now()
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
    profile.updated_at = vladivostok_now()
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
    profile.updated_at = vladivostok_now()
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
    profile.updated_at = vladivostok_now()
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


@api_bp.route('/polls/voter-stats/<string:voter_token>/transactions', methods=['GET'])
def get_voter_transactions_api(voter_token):
    """Получение истории транзакций баллов пользователя."""
    profile = PollVoterProfile.query.get_or_404(voter_token)

    # Параметры пагинации
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(max(per_page, 1), 100)  # Ограничиваем от 1 до 100
    offset = (page - 1) * per_page

    # Фильтр по типу транзакции
    transaction_type = request.args.get('type')

    transactions = get_voter_transactions(
        voter_token=voter_token,
        limit=per_page,
        offset=offset,
        transaction_type=transaction_type,
    )

    summary = get_voter_transactions_summary(voter_token)

    # Сериализуем транзакции
    transactions_data = []
    for t in transactions:
        transactions_data.append({
            'id': t.id,
            'type': t.transaction_type,
            'type_label': t.type_label,
            'type_emoji': t.type_emoji,
            'amount': t.amount,
            'formatted_amount': t.formatted_amount,
            'is_credit': t.is_credit,
            'balance_before': t.balance_before,
            'balance_after': t.balance_after,
            'description': t.description,
            'movie_name': t.movie_name,
            'poll_id': t.poll_id,
            'created_at': t.created_at.isoformat() if t.created_at else None,
        })

    payload = {
        'voter_token': voter_token,
        'user_id': profile.user_id,
        'device_label': profile.device_label,
        'current_balance': profile.total_points or 0,
        'transactions': transactions_data,
        'summary': summary,
        'page': page,
        'per_page': per_page,
    }

    return prevent_caching(jsonify(payload))


# --- Маршруты для управления кастомными бейджами ---

@api_bp.route('/custom-badges', methods=['GET'])
def get_custom_badges():
    """Получение списка всех кастомных бейджей"""
    badges = CustomBadge.query.order_by(CustomBadge.created_at.desc()).all()
    return jsonify({
        "success": True,
        "badges": [
            {
                "id": badge.id,
                "emoji": badge.emoji,
                "name": badge.name,
                "badge_key": f"custom_{badge.id}",
                "created_at": badge.created_at.isoformat() if badge.created_at else None,
            }
            for badge in badges
        ]
    })


@api_bp.route('/custom-badges', methods=['POST'])
def create_custom_badge():
    """Создание нового кастомного бейджа"""
    payload = _get_json_payload()
    if payload is None:
        return jsonify({"success": False, "message": "Некорректный JSON-запрос"}), 400

    emoji = (payload.get('emoji') or '').strip()
    name = (payload.get('name') or '').strip()

    if not emoji:
        return jsonify({"success": False, "message": "Эмодзи обязателен"}), 400

    if len(emoji) > 10:
        return jsonify({"success": False, "message": "Эмодзи слишком длинный (максимум 10 символов)"}), 400

    if not name:
        return jsonify({"success": False, "message": "Название обязательно"}), 400

    if len(name) > 50:
        return jsonify({"success": False, "message": "Название слишком длинное (максимум 50 символов)"}), 400

    badge = CustomBadge(emoji=emoji, name=name)
    db.session.add(badge)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Кастомный бейдж создан",
        "badge": {
            "id": badge.id,
            "emoji": badge.emoji,
            "name": badge.name,
            "badge_key": f"custom_{badge.id}",
            "created_at": badge.created_at.isoformat() if badge.created_at else None,
        }
    }), 201


@api_bp.route('/custom-badges/<int:badge_id>', methods=['DELETE'])
def delete_custom_badge(badge_id):
    """Удаление кастомного бейджа"""
    badge = CustomBadge.query.get_or_404(badge_id)

    # Сбрасываем бейдж у всех фильмов с этим кастомным бейджем
    badge_key = f"custom_{badge_id}"
    movies_with_badge = LibraryMovie.query.filter_by(badge=badge_key).all()
    for movie in movies_with_badge:
        movie.badge = None
        movie.bumped_at = vladivostok_now()

    db.session.delete(badge)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Кастомный бейдж удалён",
        "affected_movies": len(movies_with_badge)
    })


@api_bp.route('/custom-badges/<int:badge_id>', methods=['PUT'])
def update_custom_badge(badge_id):
    """Обновление кастомного бейджа"""
    badge = CustomBadge.query.get_or_404(badge_id)

    payload = _get_json_payload()
    if payload is None:
        return jsonify({"success": False, "message": "Некорректный JSON-запрос"}), 400

    emoji = payload.get('emoji')
    name = payload.get('name')

    if emoji is not None:
        emoji = emoji.strip()
        if not emoji:
            return jsonify({"success": False, "message": "Эмодзи не может быть пустым"}), 400
        if len(emoji) > 10:
            return jsonify({"success": False, "message": "Эмодзи слишком длинный (максимум 10 символов)"}), 400
        badge.emoji = emoji

    if name is not None:
        name = name.strip()
        if not name:
            return jsonify({"success": False, "message": "Название не может быть пустым"}), 400
        if len(name) > 50:
            return jsonify({"success": False, "message": "Название слишком длинное (максимум 50 символов)"}), 400
        badge.name = name

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Кастомный бейдж обновлён",
        "badge": {
            "id": badge.id,
            "emoji": badge.emoji,
            "name": badge.name,
            "badge_key": f"custom_{badge.id}",
            "created_at": badge.created_at.isoformat() if badge.created_at else None,
        }
    })


# --- Маршруты для управления расписаниями/таймерами фильмов ---

from ..models import MovieSchedule


def _serialize_schedule(schedule):
    """Сериализует расписание для JSON-ответа."""
    movie = schedule.library_movie
    poster_url = None
    if movie:
        if movie.poster_file_path:
            poster_url = f"/api/posters/{movie.id}"
        else:
            poster_url = movie.poster
    
    return {
        "id": schedule.id,
        "library_movie_id": schedule.library_movie_id,
        "scheduled_date": schedule.scheduled_date.isoformat() if schedule.scheduled_date else None,
        "status": schedule.status,
        "postponed_until": schedule.postponed_until.isoformat() if schedule.postponed_until else None,
        "created_at": schedule.created_at.isoformat() if schedule.created_at else None,
        "is_due": schedule.is_due,
        "movie": {
            "id": movie.id,
            "name": movie.name,
            "year": movie.year,
            "poster": poster_url,
            "poster_url": poster_url,
        } if movie else None,
    }


@api_bp.route('/schedules', methods=['GET'])
def get_all_schedules():
    """Получение всех активных расписаний для календаря."""
    try:
        # Получаем год и месяц из query params для фильтрации
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        
        query = MovieSchedule.query.join(LibraryMovie)
        
        if year and month:
            # Фильтруем по месяцу
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
            query = query.filter(
                MovieSchedule.scheduled_date >= start_date,
                MovieSchedule.scheduled_date < end_date
            )
        
        schedules = query.order_by(MovieSchedule.scheduled_date.asc()).all()
        
        return jsonify({
            "success": True,
            "schedules": [_serialize_schedule(s) for s in schedules]
        })
    except (OperationalError, ProgrammingError) as exc:
        current_app.logger.warning("Ошибка получения расписаний: %s", exc)
        db.session.rollback()
        return jsonify({"success": True, "schedules": []})


@api_bp.route('/schedules/notifications', methods=['GET'])
def get_schedule_notifications():
    """Получение таймеров, требующих уведомления (наступила дата, статус pending)."""
    try:
        now = vladivostok_now()
        
        # Получаем все pending расписания, у которых наступила дата
        schedules = MovieSchedule.query.join(LibraryMovie).filter(
            MovieSchedule.status == 'pending',
            db.or_(
                db.and_(
                    MovieSchedule.postponed_until.isnot(None),
                    MovieSchedule.postponed_until <= now
                ),
                db.and_(
                    MovieSchedule.postponed_until.is_(None),
                    MovieSchedule.scheduled_date <= now
                )
            )
        ).order_by(MovieSchedule.scheduled_date.asc()).all()
        
        return jsonify({
            "success": True,
            "notifications": [_serialize_schedule(s) for s in schedules]
        })
    except (OperationalError, ProgrammingError) as exc:
        current_app.logger.warning("Ошибка получения уведомлений: %s", exc)
        db.session.rollback()
        return jsonify({"success": True, "notifications": []})


@api_bp.route('/releases', methods=['GET'])
def get_releases():
    """
    Получение фильмов по дате релиза для календаря.
    
    Query params:
        year: int - Год (обязательный)
        month: int - Месяц 1-12 (обязательный)
        country: str - 'russia', 'world' или 'digital' (по умолчанию 'russia')
    
    Returns:
        {
            "success": true,
            "releases": {
                "2025-01-15": [...фильмы...],
                "2025-01-20": [...фильмы...],
                ...
            },
            "total": 50
        }
    """
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    country = request.args.get('country', 'russia')
    
    if not year or not month:
        return jsonify({
            "success": False,
            "error": "Требуются параметры year и month"
        }), 400
    
    if month < 1 or month > 12:
        return jsonify({
            "success": False,
            "error": "Месяц должен быть от 1 до 12"
        }), 400
    
    if country not in ('russia', 'world', 'digital'):
        return jsonify({
            "success": False,
            "error": "Параметр country должен быть 'russia', 'world' или 'digital'"
        }), 400
    
    movies, error = get_movies_by_release_date(year, month, country)
    
    if error:
        error_code = error.get('code', 'unknown')
        error_message = error.get('message', 'Неизвестная ошибка')
        
        if error_code == 'missing_token':
            return jsonify({
                "success": False,
                "error": "API Кинопоиска не настроен"
            }), 503
        
        current_app.logger.warning("Ошибка получения релизов: %s", error_message)
        return jsonify({
            "success": False,
            "error": error_message
        }), 502
    
    # Группируем фильмы по дате релиза
    releases_by_date = {}
    for movie in movies or []:
        release_date = movie.get('release_date')
        if not release_date:
            continue
        
        # Нормализуем дату к формату YYYY-MM-DD
        try:
            if 'T' in release_date:
                date_key = release_date.split('T')[0]
            else:
                date_key = release_date[:10]
            
            if date_key not in releases_by_date:
                releases_by_date[date_key] = []
            releases_by_date[date_key].append(movie)
        except Exception as exc:
            current_app.logger.debug("Ошибка парсинга даты релиза %s: %s", release_date, exc)
            continue
    
    return jsonify({
        "success": True,
        "releases": releases_by_date,
        "total": len(movies or []),
        "country": country
    })


@api_bp.route('/library/<int:movie_id>/schedule', methods=['POST'])
def add_movie_schedule(movie_id):
    """Добавление таймера для фильма."""
    library_movie = LibraryMovie.query.get_or_404(movie_id)
    
    payload = _get_json_payload()
    if payload is None:
        return jsonify({"success": False, "message": "Некорректный JSON-запрос"}), 400
    
    scheduled_date_raw = payload.get('scheduled_date')
    if not scheduled_date_raw:
        return jsonify({"success": False, "message": "Дата обязательна"}), 400
    
    # Парсим дату
    try:
        if 'T' in scheduled_date_raw:
            scheduled_date = datetime.fromisoformat(scheduled_date_raw.replace('Z', '+00:00'))
        else:
            # Если передана только дата без времени, устанавливаем время 12:00
            scheduled_date = datetime.strptime(scheduled_date_raw, '%Y-%m-%d')
            scheduled_date = scheduled_date.replace(hour=12, minute=0, second=0)
    except (ValueError, TypeError) as e:
        current_app.logger.warning("Ошибка парсинга даты %s: %s", scheduled_date_raw, e)
        return jsonify({"success": False, "message": "Некорректный формат даты"}), 400
    
    # Проверяем, что дата в будущем
    now = vladivostok_now()
    if scheduled_date < now:
        return jsonify({"success": False, "message": "Дата должна быть в будущем"}), 400
    
    # Проверяем уникальность (фильм + дата)
    # Нормализуем дату до дня для проверки уникальности
    date_only = scheduled_date.replace(hour=0, minute=0, second=0, microsecond=0)
    next_day = date_only + timedelta(days=1)
    
    existing = MovieSchedule.query.filter(
        MovieSchedule.library_movie_id == movie_id,
        MovieSchedule.scheduled_date >= date_only,
        MovieSchedule.scheduled_date < next_day
    ).first()
    
    if existing:
        return jsonify({"success": False, "message": "Таймер на эту дату уже существует"}), 409
    
    schedule = MovieSchedule(
        library_movie_id=movie_id,
        scheduled_date=scheduled_date,
        status='pending',
        created_at=vladivostok_now()
    )
    
    db.session.add(schedule)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": "Таймер добавлен",
        "schedule": _serialize_schedule(schedule)
    }), 201


@api_bp.route('/library/<int:movie_id>/schedules', methods=['GET'])
def get_movie_schedules(movie_id):
    """Получение всех таймеров для конкретного фильма."""
    library_movie = LibraryMovie.query.get_or_404(movie_id)
    
    schedules = MovieSchedule.query.filter_by(
        library_movie_id=movie_id
    ).order_by(MovieSchedule.scheduled_date.asc()).all()
    
    return jsonify({
        "success": True,
        "schedules": [_serialize_schedule(s) for s in schedules]
    })


@api_bp.route('/schedules/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    """Удаление таймера."""
    schedule = MovieSchedule.query.get_or_404(schedule_id)
    
    db.session.delete(schedule)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": "Таймер удалён"
    })


@api_bp.route('/schedules/<int:schedule_id>/confirm', methods=['PUT'])
def confirm_schedule(schedule_id):
    """Подтверждение просмотра (меняет статус на confirmed)."""
    schedule = MovieSchedule.query.get_or_404(schedule_id)
    
    schedule.status = 'confirmed'
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": "Просмотр подтверждён",
        "schedule": _serialize_schedule(schedule)
    })


@api_bp.route('/schedules/<int:schedule_id>/postpone', methods=['PUT'])
def postpone_schedule(schedule_id):
    """Откладывание уведомления на указанное время."""
    schedule = MovieSchedule.query.get_or_404(schedule_id)
    
    payload = _get_json_payload()
    if payload is None:
        return jsonify({"success": False, "message": "Некорректный JSON-запрос"}), 400
    
    minutes = payload.get('minutes', 60)
    try:
        minutes = int(minutes)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "minutes должен быть числом"}), 400
    
    if minutes <= 0:
        return jsonify({"success": False, "message": "minutes должен быть положительным"}), 400
    
    # Максимум можно отложить на 7 дней
    if minutes > 7 * 24 * 60:
        return jsonify({"success": False, "message": "Максимум можно отложить на 7 дней"}), 400
    
    schedule.postponed_until = vladivostok_now() + timedelta(minutes=minutes)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": f"Уведомление отложено на {minutes} минут",
        "schedule": _serialize_schedule(schedule)
    })


# ============================================================================
# Push Notifications API - Уведомления о новых голосах
# ============================================================================

def send_vote_notifications(poll_id, voted_movie_name, total_votes):
    """
    Отправляет push-уведомления админу о новом голосе в опросе.
    
    Уведомления отправляются только если:
    1. Глобально включены (VOTE_NOTIFICATIONS_ENABLED)
    2. Для конкретного опроса включены (poll.notifications_enabled)
    3. Есть активные подписки админа
    
    Args:
        poll_id: ID опроса
        voted_movie_name: Название фильма, за который проголосовали
        total_votes: Общее количество голосов
    """
    import json
    
    # Проверяем, включены ли уведомления глобально
    globally_enabled = current_app.config.get('VOTE_NOTIFICATIONS_ENABLED', True)
    if not globally_enabled:
        current_app.logger.debug(f'[Push] Уведомления отключены глобально для опроса {poll_id}')
        return
    
    # Проверяем, включены ли уведомления для этого опроса
    poll = Poll.query.get(poll_id)
    if not poll:
        current_app.logger.warning(f'[Push] Опрос {poll_id} не найден')
        return
    
    current_app.logger.debug(f'[Push] Проверка опроса {poll_id}: notifications_enabled={poll.notifications_enabled}')
    
    if not poll.notifications_enabled:
        current_app.logger.debug(f'[Push] Уведомления отключены для опроса {poll_id} (notifications_enabled={poll.notifications_enabled}). Пропуск отправки.')
        return
    
    vapid_private_key = current_app.config.get('VAPID_PRIVATE_KEY')
    vapid_claims_email = current_app.config.get('VAPID_CLAIMS_EMAIL', 'mailto:admin@example.com')
    
    if not vapid_private_key:
        current_app.logger.debug('VAPID_PRIVATE_KEY не настроен, push-уведомления отключены')
        return
    
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        current_app.logger.warning('pywebpush не установлен, push-уведомления недоступны')
        return
    
    # Получаем все подписки админа (без фильтрации по voter_token)
    subscriptions = PushSubscription.query.all()
    
    if not subscriptions:
        current_app.logger.debug(f'[Push] Нет активных подписок для отправки уведомлений о голосе в опросе {poll_id}')
        return
    
    current_app.logger.info(f'[Push] Отправка уведомлений для опроса {poll_id}: найдено {len(subscriptions)} подписок')
    
    # Формируем payload для уведомления
    payload = json.dumps({
        'title': '🗳️ Новый голос!',
        'body': f'За «{voted_movie_name}» проголосовали. Всего: {total_votes}',
        'icon': '/static/icons/icon128.png',
        'badge': '/static/icons/icon32.png',
        'tag': f'vote-{poll_id}',
        'data': {
            'poll_id': poll_id,
            'url': f'/p/{poll_id}/results',
        },
    })
    
    failed_endpoints = []
    
    success_count = 0
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {
                        'p256dh': sub.p256dh_key,
                        'auth': sub.auth_key,
                    },
                },
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={'sub': vapid_claims_email},
            )
            success_count += 1
            current_app.logger.debug(f'[Push] Уведомление успешно отправлено на {sub.endpoint[:50]}...')
        except WebPushException as e:
            current_app.logger.warning(f'[Push] Ошибка отправки на {sub.endpoint[:50]}: {e}')
            # Если подписка больше не действительна (404, 410), удаляем её
            if e.response and e.response.status_code in (404, 410):
                failed_endpoints.append(sub.endpoint)
        except Exception as e:
            current_app.logger.error(f'[Push] Неожиданная ошибка при отправке: {e}')
    
    current_app.logger.info(f'[Push] Отправлено {success_count} из {len(subscriptions)} уведомлений для опроса {poll_id}')
    
    # Удаляем недействительные подписки
    if failed_endpoints:
        try:
            PushSubscription.query.filter(
                PushSubscription.endpoint.in_(failed_endpoints)
            ).delete(synchronize_session=False)
            db.session.commit()
        except Exception as e:
            current_app.logger.error('Error deleting invalid subscriptions: %s', e)
            db.session.rollback()


@api_bp.route('/polls/push/vapid-key', methods=['GET'])
def get_vapid_public_key():
    """Получить публичный VAPID ключ для подписки на push-уведомления."""
    public_key = current_app.config.get('VAPID_PUBLIC_KEY')
    
    if not public_key:
        return jsonify({'error': 'Push-уведомления не настроены на сервере'}), 503
    
    return jsonify({
        'vapid_public_key': public_key,
        'enabled': current_app.config.get('VOTE_NOTIFICATIONS_ENABLED', True),
    })


@api_bp.route('/polls/push/subscribe', methods=['POST'])
def subscribe_to_push():
    """Подписаться на push-уведомления о новых голосах (для админа)."""
    payload = _get_json_payload()
    if not payload:
        return jsonify({'error': 'Некорректный JSON-запрос'}), 400
    
    subscription = payload.get('subscription')
    if not subscription or not subscription.get('endpoint'):
        return jsonify({'error': 'Некорректные данные подписки'}), 400
    
    keys = subscription.get('keys', {})
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')
    
    if not p256dh or not auth:
        return jsonify({'error': 'Отсутствуют ключи подписки'}), 400
    
    endpoint = subscription['endpoint']
    
    try:
        # Получаем или создаём voter_token для текущего пользователя
        identity = _resolve_voter_identity()
        voter_token = identity['voter_token']
        
        # Коммитим профиль если он был только что создан
        db.session.commit()
        
        # Проверяем, нет ли уже такой подписки
        existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
        
        if existing:
            # Обновляем существующую подписку
            existing.p256dh_key = p256dh
            existing.auth_key = auth
            existing.voter_token = voter_token
        else:
            # Создаём новую подписку
            new_sub = PushSubscription(
                voter_token=voter_token,
                endpoint=endpoint,
                p256dh_key=p256dh,
                auth_key=auth,
            )
            db.session.add(new_sub)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'subscribed': True,
        })
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Ошибка сохранения подписки'}), 500
    except Exception as e:
        current_app.logger.error('Error subscribing to push: %s', e)
        db.session.rollback()
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


@api_bp.route('/polls/push/unsubscribe', methods=['POST'])
def unsubscribe_from_push():
    """Отписаться от push-уведомлений (удаляет все подписки админа)."""
    payload = _get_json_payload() or {}
    endpoint = payload.get('endpoint')
    
    try:
        if endpoint:
            # Удаляем конкретную подписку
            PushSubscription.query.filter_by(endpoint=endpoint).delete()
        else:
            # Удаляем все подписки
            PushSubscription.query.delete()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'subscribed': False,
        })
    except Exception as e:
        current_app.logger.error('Error unsubscribing from push: %s', e)
        db.session.rollback()
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


@api_bp.route('/polls/notifications/settings', methods=['GET'])
def get_notifications_settings():
    """Получить текущие настройки уведомлений админа."""
    has_subscription = PushSubscription.query.first() is not None
    
    vapid_configured = bool(current_app.config.get('VAPID_PUBLIC_KEY'))
    globally_enabled = current_app.config.get('VOTE_NOTIFICATIONS_ENABLED', True)
    
    return jsonify({
        'has_push_subscription': has_subscription,
        'vapid_configured': vapid_configured,
        'globally_enabled': globally_enabled,
    })


@api_bp.route('/polls/<poll_id>/notifications', methods=['GET'])
def get_poll_notifications_status(poll_id):
    """Получить статус уведомлений для конкретного опроса."""
    poll = Poll.query.get_or_404(poll_id)
    
    has_subscription = PushSubscription.query.first() is not None
    vapid_configured = bool(current_app.config.get('VAPID_PUBLIC_KEY'))
    
    return jsonify({
        'poll_id': poll_id,
        'notifications_enabled': bool(poll.notifications_enabled),
        'has_push_subscription': has_subscription,
        'vapid_configured': vapid_configured,
    })


@api_bp.route('/polls/<poll_id>/notifications', methods=['POST'])
def toggle_poll_notifications(poll_id):
    """Включить/выключить уведомления для конкретного опроса."""
    # Проверяем, что это создатель опроса
    creator_token = _read_creator_token_from_request()
    if not creator_token:
        current_app.logger.warning(f'[Push] Попытка изменить уведомления для опроса {poll_id} без авторизации')
        return jsonify({'error': 'Необходима авторизация'}), 401
    
    poll = Poll.query.get_or_404(poll_id)
    
    # Проверяем, что токен совпадает с создателем опроса
    if poll.creator_token != creator_token:
        current_app.logger.warning(f'[Push] Попытка изменить уведомления для опроса {poll_id} с неверным токеном')
        return jsonify({'error': 'Нет доступа к этому опросу'}), 403
    
    # Получаем желаемое состояние из запроса
    data = _get_json_payload() or {}
    enabled = data.get('enabled')
    
    old_value = poll.notifications_enabled
    if enabled is None:
        # Если не указано - переключаем
        poll.notifications_enabled = not poll.notifications_enabled
    else:
        poll.notifications_enabled = bool(enabled)
    
    db.session.commit()
    
    current_app.logger.info(f'[Push] Уведомления для опроса {poll_id} изменены: {old_value} -> {poll.notifications_enabled}')
    
    return jsonify({
        'success': True,
        'poll_id': poll_id,
        'notifications_enabled': poll.notifications_enabled,
    })
