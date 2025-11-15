import random
import secrets
import string
from datetime import datetime
from urllib.parse import urljoin, quote_plus

from flask import current_app, url_for
from sqlalchemy.exc import ProgrammingError

from .. import db
from ..models import BackgroundPhoto, Lottery, Poll, PollVoterProfile

def _is_unique(model, identifier):
    """Helper to check identifier uniqueness, resilient to missing tables."""
    try:
        return model.query.get(identifier) is None
    except ProgrammingError:
        # Таблица ещё не создана (например, до применения миграций).
        # Откатываем сессию и считаем идентификатор уникальным.
        db.session.rollback()
        return True


def generate_unique_id(length=6):
    """Generate a unique ID for lottery."""
    characters = string.ascii_lowercase + string.digits
    while True:
        lottery_id = ''.join(random.choices(characters, k=length))
        if _is_unique(Lottery, lottery_id):
            return lottery_id


def generate_unique_poll_id(length=8):
    """Generate a unique ID for poll."""
    characters = string.ascii_lowercase + string.digits
    while True:
        poll_id = ''.join(random.choices(characters, k=length))
        if _is_unique(Poll, poll_id):
            return poll_id


def get_background_photos():
    """Get the last 20 background images from the database."""
    try:
        photos = BackgroundPhoto.query.order_by(BackgroundPhoto.added_at.desc()).limit(20).all()
        return [
            {
                "poster_url": photo.poster_url,
                "pos_top": photo.pos_top,
                "pos_left": photo.pos_left,
                "rotation": photo.rotation,
                "z_index": photo.z_index,
            }
            for photo in photos
        ]
    except (ProgrammingError, Exception):
        return []


def ensure_background_photo(poster_url):
    """
    Add poster URL to background photos database if it doesn't exist yet.
    """
    if not poster_url:
        return

    try:
        if BackgroundPhoto.query.filter_by(poster_url=poster_url).first():
            return

        max_z_index = db.session.query(db.func.max(BackgroundPhoto.z_index)).scalar() or 0
        
        new_photo = BackgroundPhoto(
            poster_url=poster_url,
            pos_top=random.uniform(5, 65),
            pos_left=random.uniform(5, 75),
            rotation=random.randint(-30, 30),
            z_index=max_z_index + 1,
        )
        db.session.add(new_photo)
    except Exception:
        pass


def cleanup_expired_polls():
    """
    Удаляет истёкшие опросы из базы данных.
    Эту функцию можно вызывать периодически через scheduler или cron.
    """
    try:
        expired_polls = Poll.query.filter(Poll.expires_at <= datetime.utcnow()).all()
        count = len(expired_polls)
        
        for poll in expired_polls:
            db.session.delete(poll)
        
        db.session.commit()
        return count
    except Exception as e:
        db.session.rollback()
        print(f"Ошибка при очистке опросов: {e}")
        return 0


def ensure_voter_profile(voter_token, device_label=None):
    """Создать или обновить профиль голосующего."""
    if not voter_token:
        raise ValueError('voter_token is required to manage poll points')

    normalized_label = (device_label or '').strip() or None
    if normalized_label:
        normalized_label = normalized_label[:255]

    now = datetime.utcnow()
    profile = PollVoterProfile.query.get(voter_token)
    if profile:
        if normalized_label and profile.device_label != normalized_label:
            profile.device_label = normalized_label
            profile.updated_at = now
    else:
        profile = PollVoterProfile(
            token=voter_token,
            device_label=normalized_label,
            total_points=0,
            created_at=now,
            updated_at=now,
        )
        db.session.add(profile)

    db.session.flush()
    return profile


def change_voter_points_balance(voter_token, delta, device_label=None, commit=False):
    """Атомарно изменить баланс голосующего и вернуть новое значение."""
    profile = ensure_voter_profile(voter_token, device_label=device_label)
    if delta:
        profile.total_points = (profile.total_points or 0) + delta
        profile.updated_at = datetime.utcnow()

    if commit:
        db.session.commit()
    else:
        db.session.flush()

    return profile.total_points or 0


def build_external_url(endpoint, **values):
    """Построить абсолютный URL, учитывая публичный базовый адрес если он задан."""
    public_base = current_app.config.get('PUBLIC_BASE_URL')
    if public_base:
        relative_url = url_for(endpoint, _external=False, **values)
        base = public_base.rstrip('/') + '/'
        return urljoin(base, relative_url.lstrip('/'))

    return url_for(endpoint, _external=True, **values)


def build_telegram_share_url(target_url, message=None):
    """Сформировать ссылку для шаринга в Telegram с заданным текстом."""
    if not target_url:
        return ''

    text = message or 'Привет! Предлагаю тебе определить, какой фильм мы посмотрим. Нажми на ссылку и испытай удачу!'
    encoded_url = quote_plus(target_url)
    encoded_text = quote_plus(text)
    return f'https://t.me/share/url?url={encoded_url}&text={encoded_text}'


def extract_admin_secret(req, payload=None):
    """Извлекает админский секрет из заголовков, Basic Auth, тела или query-параметров."""
    if req is None:
        return None

    payload = payload or {}

    header_keys = (
        'X-Admin-Secret',
        'X-Poll-Admin-Secret',
        'X-Poll-Secret',
    )
    for header in header_keys:
        header_value = req.headers.get(header)
        if header_value:
            return header_value

    if hasattr(payload, 'get'):
        candidate = payload.get('admin_secret') or payload.get('secret')
        if candidate:
            return candidate

    if req.is_json and isinstance(payload, dict):
        candidate = payload.get('admin_secret') or payload.get('secret')
        if candidate:
            return candidate

    auth = getattr(req, 'authorization', None)
    if auth and getattr(auth, 'password', None):
        return auth.password

    return None


def validate_admin_secret(provided_secret):
    """Проверяет админский секрет и возвращает (is_valid, message, status_code)."""
    expected_secret = current_app.config.get('POLL_ADMIN_SECRET') or current_app.config.get('POLL_POINTS_ADMIN_SECRET')
    if not expected_secret:
        return False, 'Админский секрет не настроен на сервере.', 503

    if provided_secret in (None, ''):
        return False, 'Требуется админский секрет.', 401

    try:
        is_valid = secrets.compare_digest(str(provided_secret), str(expected_secret))
    except Exception:
        return False, 'Неверный админский секрет.', 403

    if not is_valid:
        return False, 'Неверный админский секрет.', 403

    return True, None, 200


