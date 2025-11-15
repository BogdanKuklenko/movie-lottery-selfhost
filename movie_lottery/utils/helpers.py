import random
import string
from datetime import datetime
from urllib.parse import urljoin, quote_plus

from flask import current_app, url_for
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from .. import db
from ..models import (
    BackgroundPhoto,
    Lottery,
    Poll,
    PollCreatorToken,
    PollVoterProfile,
)


class _FallbackVoterProfile:
    """In-memory profile used when the points tables are unavailable."""

    __slots__ = (
        'token', 'device_label', 'total_points', 'created_at', 'updated_at', '_is_fallback'
    )

    def __init__(self, token, device_label=None):
        now = datetime.utcnow()
        self.token = token
        self.device_label = device_label
        self.total_points = 0
        self.created_at = now
        self.updated_at = now
        self._is_fallback = True

def _is_unique(model, identifier):
    """Helper to check identifier uniqueness, resilient to missing tables."""
    try:
        return model.query.get(identifier) is None
    except (ProgrammingError, OperationalError):
        # Таблица ещё не создана (например, до применения миграций).
        # Откатываем сессию и считаем идентификатор уникальным.
        db.session.rollback()
        return True


def _handle_missing_voter_table(error, voter_token, device_label=None):
    """Rollback the session, log the issue and return a fallback profile."""
    db.session.rollback()
    logger = getattr(current_app, 'logger', None)
    message = (
        'Таблица профилей голосующих недоступна. '
        'Голосование доступно, но начисление баллов временно отключено.'
    )
    if logger:
        logger.warning('%s Ошибка: %s', message, error)
    else:
        print(f"{message} Ошибка: {error}")
    return _FallbackVoterProfile(voter_token, device_label)


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


def ensure_vote_points_column():
    """Make sure the vote table has the points_awarded column."""
    engine = db.engine

    try:
        inspector = inspect(engine)
    except Exception:
        return

    if 'vote' not in inspector.get_table_names():
        return

    vote_columns = {col['name'] for col in inspector.get_columns('vote')}
    if 'points_awarded' in vote_columns:
        return

    ddl = "ALTER TABLE vote ADD COLUMN points_awarded INTEGER DEFAULT 0"
    if engine.dialect.name == 'postgresql':
        ddl = "ALTER TABLE vote ADD COLUMN IF NOT EXISTS points_awarded INTEGER NOT NULL DEFAULT 0"

    try:
        with engine.begin() as connection:
            connection.execute(text(ddl))
            if engine.dialect.name != 'postgresql':
                connection.execute(text("UPDATE vote SET points_awarded = 0 WHERE points_awarded IS NULL"))
    except Exception as exc:
        logger = getattr(current_app, 'logger', None)
        message = 'Не удалось автоматически обновить таблицу голосов (points_awarded).'
        if logger:
            logger.warning('%s Ошибка: %s', message, exc)
        else:
            print(f"{message} Ошибка: {exc}")


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


def ensure_creator_token_record(token):
    """Гарантирует, что токен организатора сохранён в общей таблице."""
    if not token:
        return None

    now = datetime.utcnow()

    try:
        entry = PollCreatorToken.query.filter_by(creator_token=token).first()
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return None

    if entry:
        entry.last_seen = now
    else:
        entry = PollCreatorToken(
            creator_token=token,
            created_at=now,
            last_seen=now,
        )
        db.session.add(entry)

    try:
        db.session.flush()
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return None

    return entry


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
    try:
        profile = PollVoterProfile.query.get(voter_token)
    except (ProgrammingError, OperationalError) as exc:
        return _handle_missing_voter_table(exc, voter_token, normalized_label)
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
        try:
            db.session.add(profile)
        except (ProgrammingError, OperationalError) as exc:
            return _handle_missing_voter_table(exc, voter_token, normalized_label)

    try:
        db.session.flush()
    except (ProgrammingError, OperationalError) as exc:
        return _handle_missing_voter_table(exc, voter_token, normalized_label)

    return profile


def change_voter_points_balance(voter_token, delta, device_label=None, commit=False):
    """Атомарно изменить баланс голосующего и вернуть новое значение."""
    profile = ensure_voter_profile(voter_token, device_label=device_label)
    if delta:
        profile.total_points = (profile.total_points or 0) + delta
        if not getattr(profile, '_is_fallback', False):
            profile.updated_at = datetime.utcnow()

    if getattr(profile, '_is_fallback', False):
        return profile.total_points or 0

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


def prevent_caching(response):
    """Добавить заголовки no-cache к ответу Flask."""
    if response is None:
        return None

    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


