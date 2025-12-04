import random
import secrets
import string
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, quote_plus

from flask import current_app, url_for
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from .. import db

# Часовой пояс Владивостока (UTC+10)
VLADIVOSTOK_TZ = timezone(timedelta(hours=10))

def vladivostok_now():
    """
    Возвращает текущее время в часовом поясе Владивостока (UTC+10).
    Используется вместо datetime.utcnow() для синхронизации времени на сайте.
    """
    return datetime.now(VLADIVOSTOK_TZ).replace(tzinfo=None)
from ..models import (
    BackgroundPhoto,
    Lottery,
    Poll,
    PollCreatorToken,
    PollSettings,
    PollMovie,
    PollVoterProfile,
    PointsTransaction,
    Vote,
)


class _FallbackVoterProfile:
    """In-memory profile used when the points tables are unavailable."""

    __slots__ = (
        'token',
        'device_label',
        'total_points',
        'points_accrued_total',
        'created_at',
        'updated_at',
        'user_id',
        'voting_streak',
        'last_vote_date',
        'max_voting_streak',
        '_is_fallback',
    )

    def __init__(self, token, device_label=None, user_id=None):
        now = vladivostok_now()
        self.token = token
        self.device_label = device_label
        self.total_points = 0
        self.points_accrued_total = 0
        self.created_at = now
        self.updated_at = now
        self.user_id = user_id
        self.voting_streak = 0
        self.last_vote_date = None
        self.max_voting_streak = 0
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


def _handle_missing_voter_table(error, voter_token, device_label=None, user_id=None):
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
    return _FallbackVoterProfile(voter_token, device_label, user_id)


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


def ensure_poll_voter_user_id_column():
    """Добавляет отсутствующие критичные колонки в poll_voter_profile."""
    engine = db.engine

    try:
        inspector = inspect(engine)
    except Exception:
        return False

    table_name = 'poll_voter_profile'
    if table_name not in inspector.get_table_names():
        return False

    existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
    needs_user_id = 'user_id' not in existing_columns
    needs_points_accrued = 'points_accrued_total' not in existing_columns

    if not (needs_user_id or needs_points_accrued):
        return False

    dialect = engine.dialect.name

    try:
        with engine.begin() as connection:
            statements = []
            if needs_user_id:
                if dialect == 'postgresql':
                    statements.append(
                        "ALTER TABLE poll_voter_profile "
                        "ADD COLUMN IF NOT EXISTS user_id VARCHAR(128) UNIQUE"
                    )
                else:
                    statements.append(
                        "ALTER TABLE poll_voter_profile ADD COLUMN user_id VARCHAR(128) UNIQUE"
                    )

            if needs_points_accrued:
                if dialect == 'postgresql':
                    statements.append(
                        "ALTER TABLE poll_voter_profile "
                        "ADD COLUMN IF NOT EXISTS points_accrued_total INTEGER NOT NULL DEFAULT 0"
                    )
                else:
                    statements.append(
                        "ALTER TABLE poll_voter_profile ADD COLUMN points_accrued_total INTEGER DEFAULT 0"
                    )

            for stmt in statements:
                connection.execute(text(stmt))

            if needs_points_accrued:
                connection.execute(text(
                    "UPDATE poll_voter_profile "
                    "SET points_accrued_total = COALESCE(points_accrued_total, 0)"
                ))

        logger = getattr(current_app, 'logger', None)
        added_columns = []
        if needs_user_id:
            added_columns.append('user_id')
        if needs_points_accrued:
            added_columns.append('points_accrued_total')
        message = (
            'Автоматически добавлены колонки в poll_voter_profile: '
            + ', '.join(added_columns)
        )
        if logger:
            logger.info(message)
        else:
            print(message)
        return True
    except Exception as exc:
        logger = getattr(current_app, 'logger', None)
        message = 'Не удалось автоматически обновить таблицу poll_voter_profile (user_id).'
        if logger:
            logger.warning('%s Ошибка: %s', message, exc)
        else:
            print(f"{message} Ошибка: {exc}")
        return False


def ensure_library_movie_columns():
    """Ensure optional columns for the library exist (bumped_at, points)."""
    engine = db.engine

    try:
        inspector = inspect(engine)
    except Exception:
        return False

    table_name = 'library_movie'
    if table_name not in inspector.get_table_names():
        return False

    existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
    missing_columns = []

    if 'bumped_at' not in existing_columns:
        missing_columns.append('bumped_at')
    if 'points' not in existing_columns:
        missing_columns.append('points')
    if 'ban_until' not in existing_columns:
        missing_columns.append('ban_until')
    if 'ban_applied_by' not in existing_columns:
        missing_columns.append('ban_applied_by')
    if 'ban_cost' not in existing_columns:
        missing_columns.append('ban_cost')
    if 'ban_cost_per_month' not in existing_columns:
        missing_columns.append('ban_cost_per_month')

    if not missing_columns:
        return False

    dialect = engine.dialect.name

    try:
        with engine.begin() as connection:
            if 'bumped_at' in missing_columns:
                if dialect == 'postgresql':
                    connection.execute(text(
                        "ALTER TABLE library_movie "
                        "ADD COLUMN IF NOT EXISTS bumped_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()"
                    ))
                else:
                    connection.execute(text("ALTER TABLE library_movie ADD COLUMN bumped_at DATETIME"))
                connection.execute(text(
                    "UPDATE library_movie SET bumped_at = COALESCE(bumped_at, added_at)"
                ))

            if 'points' in missing_columns:
                default_clause = 'INTEGER DEFAULT 1'
                if dialect == 'postgresql':
                    connection.execute(text(
                        "ALTER TABLE library_movie "
                        "ADD COLUMN IF NOT EXISTS points INTEGER NOT NULL DEFAULT 1"
                    ))
                else:
                    connection.execute(text(
                        f"ALTER TABLE library_movie ADD COLUMN points {default_clause}"
                    ))
                connection.execute(text(
                    "UPDATE library_movie SET points = COALESCE(points, 1)"
                ))

            if 'ban_until' in missing_columns:
                if dialect == 'postgresql':
                    connection.execute(text(
                        "ALTER TABLE library_movie "
                        "ADD COLUMN IF NOT EXISTS ban_until TIMESTAMP WITHOUT TIME ZONE"
                    ))
                else:
                    connection.execute(text("ALTER TABLE library_movie ADD COLUMN ban_until DATETIME"))

            if 'ban_applied_by' in missing_columns:
                if dialect == 'postgresql':
                    connection.execute(text(
                        "ALTER TABLE library_movie "
                        "ADD COLUMN IF NOT EXISTS ban_applied_by VARCHAR(120)"
                    ))
                else:
                    connection.execute(text("ALTER TABLE library_movie ADD COLUMN ban_applied_by VARCHAR(120)"))

            if 'ban_cost' in missing_columns:
                if dialect == 'postgresql':
                    connection.execute(text(
                        "ALTER TABLE library_movie "
                        "ADD COLUMN IF NOT EXISTS ban_cost INTEGER"
                    ))
                else:
                    connection.execute(text("ALTER TABLE library_movie ADD COLUMN ban_cost INTEGER"))

            if 'ban_cost_per_month' in missing_columns:
                if dialect == 'postgresql':
                    connection.execute(text(
                        "ALTER TABLE library_movie "
                        "ADD COLUMN IF NOT EXISTS ban_cost_per_month INTEGER"
                    ))
                else:
                    connection.execute(text("ALTER TABLE library_movie ADD COLUMN ban_cost_per_month INTEGER"))

        logger = getattr(current_app, 'logger', None)
        message = (
            'Автоматически добавлены отсутствующие колонки в library_movie: '
            + ', '.join(missing_columns)
        )
        if logger:
            logger.info(message)
        else:
            print(message)
        return True
    except Exception as exc:
        logger = getattr(current_app, 'logger', None)
        message = 'Не удалось автоматически обновить таблицу library_movie.'
        if logger:
            logger.warning('%s Ошибка: %s', message, exc)
        else:
            print(f"{message} Ошибка: {exc}")
        return False


def ensure_poll_movie_points_column():
    """Добавляет колонку points в poll_movie, если её ещё нет."""
    engine = db.engine

    try:
        inspector = inspect(engine)
    except Exception:
        return False

    table_name = 'poll_movie'
    if table_name not in inspector.get_table_names():
        return False

    existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
    if 'points' in existing_columns:
        return False

    dialect = engine.dialect.name

    try:
        with engine.begin() as connection:
            if dialect == 'postgresql':
                connection.execute(text(
                    "ALTER TABLE poll_movie "
                    "ADD COLUMN IF NOT EXISTS points INTEGER NOT NULL DEFAULT 1"
                ))
            else:
                connection.execute(text(
                    "ALTER TABLE poll_movie ADD COLUMN points INTEGER DEFAULT 1"
                ))
            connection.execute(text(
                "UPDATE poll_movie SET points = COALESCE(points, 1)"
            ))

        logger = getattr(current_app, 'logger', None)
        message = 'Автоматически добавлена колонка points в poll_movie.'
        if logger:
            logger.info(message)
        else:
            print(message)
        return True
    except Exception as exc:
        logger = getattr(current_app, 'logger', None)
        message = 'Не удалось автоматически обновить таблицу poll_movie.'
        if logger:
            logger.warning('%s Ошибка: %s', message, exc)
        else:
            print(f"{message} Ошибка: {exc}")
        return False


def ensure_poll_movie_ban_column():
    """Добавляет колонку ban_until в poll_movie, если её ещё нет."""
    engine = db.engine

    try:
        inspector = inspect(engine)
    except Exception:
        return False

    table_name = 'poll_movie'
    if table_name not in inspector.get_table_names():
        return False

    existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
    if 'ban_until' in existing_columns:
        return False

    dialect = engine.dialect.name

    try:
        with engine.begin() as connection:
            if dialect == 'postgresql':
                connection.execute(text(
                    "ALTER TABLE poll_movie "
                    "ADD COLUMN IF NOT EXISTS ban_until TIMESTAMP WITHOUT TIME ZONE"
                ))
            else:
                connection.execute(text("ALTER TABLE poll_movie ADD COLUMN ban_until DATETIME"))

        logger = getattr(current_app, 'logger', None)
        message = 'Автоматически добавлена колонка ban_until в poll_movie.'
        if logger:
            logger.info(message)
        else:
            print(message)
        return True
    except Exception as exc:
        logger = getattr(current_app, 'logger', None)
        message = 'Не удалось автоматически обновить таблицу poll_movie (ban_until).'
        if logger:
            logger.warning('%s Ошибка: %s', message, exc)
        else:
            print(f"{message} Ошибка: {exc}")
        return False


def ensure_poll_forced_winner_column():
    """Добавляет колонку forced_winner_movie_id в poll, если её нет."""
    engine = db.engine

    try:
        inspector = inspect(engine)
    except Exception:
        return False

    table_name = 'poll'
    if table_name not in inspector.get_table_names():
        return False

    existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
    if 'forced_winner_movie_id' in existing_columns:
        return False

    dialect = engine.dialect.name

    try:
        with engine.begin() as connection:
            if dialect == 'postgresql':
                connection.execute(text(
                    "ALTER TABLE poll "
                    "ADD COLUMN IF NOT EXISTS forced_winner_movie_id INTEGER"
                ))
            else:
                connection.execute(text(
                    "ALTER TABLE poll ADD COLUMN forced_winner_movie_id INTEGER"
                ))

        logger = getattr(current_app, 'logger', None)
        message = 'Автоматически добавлена колонка forced_winner_movie_id в poll.'
        if logger:
            logger.info(message)
        else:
            print(message)
        return True
    except Exception as exc:
        logger = getattr(current_app, 'logger', None)
        message = 'Не удалось автоматически обновить таблицу poll (forced_winner_movie_id).'
        if logger:
            logger.warning('%s Ошибка: %s', message, exc)
        else:
            print(f"{message} Ошибка: {exc}")
        return False


def ensure_poll_tables():
    """
    Ensure that all tables required for polls exist.

    На некоторых окружениях миграции могут не запускаться автоматически,
    поэтому таблицы опросов создаём по требованию.
    """

    engine = db.engine

    try:
        inspector = inspect(engine)
    except Exception as exc:
        logger = getattr(current_app, 'logger', None)
        if logger:
            logger.warning('Не удалось проверить таблицы опросов: %s', exc)
        else:
            print(f"Не удалось проверить таблицы опросов: {exc}")
        return False

    required_tables = {
        'poll': Poll.__table__,
        'poll_movie': PollMovie.__table__,
        'poll_voter_profile': PollVoterProfile.__table__,
        'vote': Vote.__table__,
        'poll_creator_token': PollCreatorToken.__table__,
        'poll_settings': PollSettings.__table__,
    }
    existing_tables = set(inspector.get_table_names())
    missing_tables = [name for name in required_tables if name not in existing_tables]

    if not missing_tables:
        return False

    try:
        with engine.begin() as connection:
            for table_name in missing_tables:
                required_tables[table_name].create(bind=connection, checkfirst=True)
        logger = getattr(current_app, 'logger', None)
        if logger:
            logger.info('Автоматически созданы таблицы опросов: %s', ', '.join(missing_tables))
        else:
            print(f"Автоматически созданы таблицы опросов: {', '.join(missing_tables)}")
        return True
    except Exception as exc:
        logger = getattr(current_app, 'logger', None)
        message = 'Не удалось автоматически создать таблицы опросов.'
        if logger:
            logger.error('%s Ошибка: %s', message, exc)
        else:
            print(f"{message} Ошибка: {exc}")
        return False


def _get_default_custom_vote_cost():
    try:
        return max(0, int(current_app.config.get('POLL_CUSTOM_VOTE_COST', 10)))
    except (TypeError, ValueError):
        return 10


def get_poll_settings(create_if_missing=True):
    """Получить или создать настройки опросов."""
    default_cost = _get_default_custom_vote_cost()
    try:
        settings = PollSettings.query.get(1)
        if settings is None and create_if_missing:
            settings = PollSettings(id=1, custom_vote_cost=default_cost)
            db.session.add(settings)
            db.session.commit()
        return settings
    except (ProgrammingError, OperationalError) as exc:
        db.session.rollback()
        logger = getattr(current_app, 'logger', None)
        message = 'Таблица настроек опросов недоступна.'
        if logger:
            logger.warning('%s Ошибка: %s', message, exc)
        else:
            print(f"{message} Ошибка: {exc}")
        return None


def get_custom_vote_cost():
    """Вернуть актуальную стоимость кастомного голоса."""
    default_cost = _get_default_custom_vote_cost()
    settings = get_poll_settings(create_if_missing=True)
    if not settings:
        return default_cost

    try:
        return max(0, int(settings.custom_vote_cost))
    except (TypeError, ValueError):
        return default_cost


def update_poll_settings(*, custom_vote_cost=None):
    settings = get_poll_settings(create_if_missing=True)
    if not settings:
        return None

    updated = False
    if custom_vote_cost is not None:
        settings.custom_vote_cost = max(0, int(custom_vote_cost))
        updated = True

    if updated:
        settings.updated_at = vladivostok_now()
        db.session.commit()

    return settings


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
        expired_polls = Poll.query.filter(Poll.expires_at <= vladivostok_now()).all()
        count = len(expired_polls)
        
        for poll in expired_polls:
            db.session.delete(poll)
        
        db.session.commit()
        return count
    except Exception as e:
        db.session.rollback()
        print(f"Ошибка при очистке опросов: {e}")
        return 0


def ensure_voter_profile(voter_token, device_label=None, user_id=None):
    """Создать или обновить профиль голосующего."""
    if not voter_token:
        raise ValueError('voter_token is required to manage poll points')

    normalized_label = (device_label or '').strip() or None
    if normalized_label:
        normalized_label = normalized_label[:255]

    normalized_user_id = (user_id or '').strip() or None
    if normalized_user_id:
        normalized_user_id = normalized_user_id[:128]

    now = vladivostok_now()
    try:
        profile = PollVoterProfile.query.get(voter_token)
    except (ProgrammingError, OperationalError) as exc:
        return _handle_missing_voter_table(exc, voter_token, normalized_label, normalized_user_id)

    if profile:
        changed = False
        if normalized_label and profile.device_label != normalized_label:
            profile.device_label = normalized_label
            changed = True
        if normalized_user_id and not profile.user_id:
            existing_with_user = PollVoterProfile.query.filter_by(user_id=normalized_user_id).first()
            if not existing_with_user:
                profile.user_id = normalized_user_id
                changed = True
        if changed:
            profile.updated_at = now
    else:
        profile = PollVoterProfile(
            token=voter_token,
            user_id=normalized_user_id,
            device_label=normalized_label,
            total_points=0,
            points_accrued_total=0,
            created_at=now,
            updated_at=now,
        )
        try:
            db.session.add(profile)
        except (ProgrammingError, OperationalError) as exc:
            return _handle_missing_voter_table(exc, voter_token, normalized_label, normalized_user_id)

    try:
        db.session.flush()
    except (ProgrammingError, OperationalError) as exc:
        return _handle_missing_voter_table(exc, voter_token, normalized_label, normalized_user_id)

    return profile


def ensure_voter_profile_for_user(user_id, device_label=None):
    """Получить или создать профиль голосующего по user_id."""
    if not user_id or not str(user_id).strip():
        raise ValueError('user_id is required to manage poll points')

    normalized_label = (device_label or '').strip() or None
    if normalized_label:
        normalized_label = normalized_label[:255]

    normalized_user_id = str(user_id).strip()[:128]
    now = vladivostok_now()

    try:
        profile = PollVoterProfile.query.filter_by(user_id=normalized_user_id).first()
    except (ProgrammingError, OperationalError) as exc:
        return _handle_missing_voter_table(exc, secrets.token_hex(16), normalized_label, normalized_user_id)

    if profile:
        if normalized_label and profile.device_label != normalized_label:
            profile.device_label = normalized_label
            profile.updated_at = now
    else:
        profile = PollVoterProfile(
            token=secrets.token_hex(16),
            user_id=normalized_user_id,
            device_label=normalized_label,
            total_points=0,
            points_accrued_total=0,
            created_at=now,
            updated_at=now,
        )
        try:
            db.session.add(profile)
        except (ProgrammingError, OperationalError) as exc:
            return _handle_missing_voter_table(exc, profile.token, normalized_label, normalized_user_id)

    try:
        db.session.flush()
    except (ProgrammingError, OperationalError) as exc:
        return _handle_missing_voter_table(exc, profile.token, normalized_label, normalized_user_id)

    return profile


def rotate_voter_token(profile, update_votes=False):
    """Перевыпустить токен голосующего.

    По умолчанию голоса остаются привязанными к исходному токену, чтобы
    сохранить историю начислений. При необходимости можно явно запросить
    обновление связанных записей голосов, передав ``update_votes=True``.
    """
    if not profile:
        return None

    old_token = profile.token
    new_token = secrets.token_hex(16)
    profile.token = new_token
    profile.updated_at = vladivostok_now()

    if getattr(profile, '_is_fallback', False):
        return new_token

    if update_votes:
        try:
            Vote.query.filter_by(voter_token=old_token).update({'voter_token': new_token})
            db.session.flush()
        except (ProgrammingError, OperationalError) as exc:
            fallback = _handle_missing_voter_table(
                exc,
                new_token,
                getattr(profile, 'device_label', None),
                getattr(profile, 'user_id', None),
            )
            return getattr(fallback, 'token', new_token)

    return new_token


def change_voter_points_balance(voter_token, delta, device_label=None, commit=False):
    """Атомарно изменить баланс голосующего и вернуть новое значение."""
    profile = ensure_voter_profile(voter_token, device_label=device_label)
    if delta:
        profile.total_points = (profile.total_points or 0) + delta
        if delta > 0:
            profile.points_accrued_total = (profile.points_accrued_total or 0) + delta
        if not getattr(profile, '_is_fallback', False):
            profile.updated_at = vladivostok_now()

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


# --- Voting Streak Functions ---

def calculate_streak_bonus(streak_days):
    """
    Рассчитать бонус за серию голосований подряд.
    
    Прогрессивная шкала:
    - 2 дня: +1 балл
    - 3-4 дня: +2 балла
    - 5-6 дней: +3 балла
    - 7+ дней: +5 баллов
    
    При streak = 1 (первый день или после сброса) бонус не начисляется.
    """
    if streak_days < 2:
        return 0
    if streak_days == 2:
        return 1
    if streak_days <= 4:
        return 2
    if streak_days <= 6:
        return 3
    return 5


def get_next_streak_milestone(current_streak):
    """
    Получить информацию о следующем milestone streak.
    
    Возвращает dict с:
    - next_milestone: следующая веха
    - days_remaining: дней до неё
    - next_bonus: бонус на следующей вехе
    """
    milestones = [2, 3, 5, 7]
    
    for milestone in milestones:
        if current_streak < milestone:
            return {
                'next_milestone': milestone,
                'days_remaining': milestone - current_streak,
                'next_bonus': calculate_streak_bonus(milestone),
            }
    
    # Уже на максимальном уровне
    return {
        'next_milestone': None,
        'days_remaining': 0,
        'next_bonus': calculate_streak_bonus(current_streak),
    }


def update_voter_streak(profile):
    """
    Обновить streak голосующего при новом голосовании.
    
    Возвращает dict с:
    - previous_streak: предыдущий streak
    - new_streak: новый streak
    - streak_bonus: бонус за серию
    - is_new_streak: True если начата новая серия
    - streak_continued: True если серия продолжена
    - streak_broken: True если серия была прервана
    """
    if getattr(profile, '_is_fallback', False):
        return {
            'previous_streak': 0,
            'new_streak': 1,
            'streak_bonus': 0,
            'is_new_streak': True,
            'streak_continued': False,
            'streak_broken': False,
        }
    
    now = vladivostok_now()
    today = now.date()
    
    previous_streak = getattr(profile, 'voting_streak', 0) or 0
    last_vote_date = getattr(profile, 'last_vote_date', None)
    
    is_new_streak = False
    streak_continued = False
    streak_broken = False
    
    if last_vote_date is None:
        # Первое голосование
        new_streak = 1
        is_new_streak = True
    elif last_vote_date == today:
        # Уже голосовал сегодня - streak не меняется
        new_streak = previous_streak
    elif last_vote_date == today - timedelta(days=1):
        # Голосовал вчера - продолжаем streak
        new_streak = previous_streak + 1
        streak_continued = True
    else:
        # Пропустил день(и) - streak сбрасывается
        new_streak = 1
        is_new_streak = True
        if previous_streak > 0:
            streak_broken = True
    
    # Обновляем профиль
    try:
        profile.voting_streak = new_streak
        profile.last_vote_date = today
        
        # Обновляем максимальный streak если нужно
        max_streak = getattr(profile, 'max_voting_streak', 0) or 0
        if new_streak > max_streak:
            profile.max_voting_streak = new_streak
        
        profile.updated_at = now
    except (AttributeError, TypeError):
        # Колонки streak ещё не существуют в БД
        pass
    
    streak_bonus = calculate_streak_bonus(new_streak)
    
    return {
        'previous_streak': previous_streak,
        'new_streak': new_streak,
        'streak_bonus': streak_bonus,
        'is_new_streak': is_new_streak,
        'streak_continued': streak_continued,
        'streak_broken': streak_broken,
    }


def get_voter_streak_info(profile):
    """
    Получить полную информацию о streak пользователя.
    
    Возвращает dict с:
    - current_streak: текущий streak
    - max_streak: максимальный достигнутый streak
    - current_bonus: текущий бонус за streak
    - next_milestone: информация о следующем milestone
    - last_vote_date: дата последнего голосования (ISO string)
    - streak_active: True если streak активен (голосовал сегодня или вчера)
    """
    if getattr(profile, '_is_fallback', False):
        return {
            'current_streak': 0,
            'max_streak': 0,
            'current_bonus': 0,
            'next_milestone': get_next_streak_milestone(0),
            'last_vote_date': None,
            'streak_active': False,
        }
    
    now = vladivostok_now()
    today = now.date()
    
    current_streak = getattr(profile, 'voting_streak', 0) or 0
    max_streak = getattr(profile, 'max_voting_streak', 0) or 0
    last_vote_date = getattr(profile, 'last_vote_date', None)
    
    # Проверяем, активен ли streak (голосовал сегодня или вчера)
    streak_active = False
    if last_vote_date:
        days_since_vote = (today - last_vote_date).days
        streak_active = days_since_vote <= 1
        
        # Если пропустил день, streak фактически = 0 для отображения
        if days_since_vote > 1:
            current_streak = 0
    
    return {
        'current_streak': current_streak,
        'max_streak': max_streak,
        'current_bonus': calculate_streak_bonus(current_streak),
        'next_milestone': get_next_streak_milestone(current_streak),
        'last_vote_date': last_vote_date.isoformat() if last_vote_date else None,
        'streak_active': streak_active,
    }


def ensure_voter_streak_columns():
    """Добавляет колонки streak в poll_voter_profile, если их ещё нет."""
    engine = db.engine

    try:
        inspector = inspect(engine)
    except Exception:
        return False

    table_name = 'poll_voter_profile'
    if table_name not in inspector.get_table_names():
        return False

    existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
    missing_columns = []

    if 'voting_streak' not in existing_columns:
        missing_columns.append('voting_streak')
    if 'last_vote_date' not in existing_columns:
        missing_columns.append('last_vote_date')
    if 'max_voting_streak' not in existing_columns:
        missing_columns.append('max_voting_streak')

    if not missing_columns:
        return False

    dialect = engine.dialect.name

    try:
        with engine.begin() as connection:
            if 'voting_streak' in missing_columns:
                if dialect == 'postgresql':
                    connection.execute(text(
                        "ALTER TABLE poll_voter_profile "
                        "ADD COLUMN IF NOT EXISTS voting_streak INTEGER NOT NULL DEFAULT 0"
                    ))
                else:
                    connection.execute(text(
                        "ALTER TABLE poll_voter_profile ADD COLUMN voting_streak INTEGER DEFAULT 0"
                    ))
                connection.execute(text(
                    "UPDATE poll_voter_profile SET voting_streak = COALESCE(voting_streak, 0)"
                ))

            if 'last_vote_date' in missing_columns:
                if dialect == 'postgresql':
                    connection.execute(text(
                        "ALTER TABLE poll_voter_profile "
                        "ADD COLUMN IF NOT EXISTS last_vote_date DATE"
                    ))
                else:
                    connection.execute(text(
                        "ALTER TABLE poll_voter_profile ADD COLUMN last_vote_date DATE"
                    ))

            if 'max_voting_streak' in missing_columns:
                if dialect == 'postgresql':
                    connection.execute(text(
                        "ALTER TABLE poll_voter_profile "
                        "ADD COLUMN IF NOT EXISTS max_voting_streak INTEGER NOT NULL DEFAULT 0"
                    ))
                else:
                    connection.execute(text(
                        "ALTER TABLE poll_voter_profile ADD COLUMN max_voting_streak INTEGER DEFAULT 0"
                    ))
                connection.execute(text(
                    "UPDATE poll_voter_profile SET max_voting_streak = COALESCE(max_voting_streak, 0)"
                ))

        logger = getattr(current_app, 'logger', None)
        message = (
            'Автоматически добавлены колонки streak в poll_voter_profile: '
            + ', '.join(missing_columns)
        )
        if logger:
            logger.info(message)
        else:
            print(message)
        return True
    except Exception as exc:
        logger = getattr(current_app, 'logger', None)
        message = 'Не удалось автоматически обновить таблицу poll_voter_profile (streak).'
        if logger:
            logger.warning('%s Ошибка: %s', message, exc)
        else:
            print(f"{message} Ошибка: {exc}")
        return False


# --- Points Transaction Logging ---

def ensure_points_transaction_table():
    """Создаёт таблицу points_transaction, если её ещё нет."""
    engine = db.engine

    try:
        inspector = inspect(engine)
    except Exception:
        return False

    if 'points_transaction' in inspector.get_table_names():
        return False

    dialect = engine.dialect.name

    try:
        with engine.begin() as connection:
            if dialect == 'postgresql':
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS points_transaction (
                        id SERIAL PRIMARY KEY,
                        voter_token VARCHAR(64) NOT NULL,
                        transaction_type VARCHAR(30) NOT NULL,
                        amount INTEGER NOT NULL,
                        balance_before INTEGER NOT NULL,
                        balance_after INTEGER NOT NULL,
                        description VARCHAR(255),
                        movie_name VARCHAR(200),
                        poll_id VARCHAR(8),
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
                    )
                """))
            else:
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS points_transaction (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        voter_token VARCHAR(64) NOT NULL,
                        transaction_type VARCHAR(30) NOT NULL,
                        amount INTEGER NOT NULL,
                        balance_before INTEGER NOT NULL,
                        balance_after INTEGER NOT NULL,
                        description VARCHAR(255),
                        movie_name VARCHAR(200),
                        poll_id VARCHAR(8),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))

            # Создаём индексы
            if dialect == 'postgresql':
                connection.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_points_transaction_voter_token "
                    "ON points_transaction (voter_token)"
                ))
                connection.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_points_transaction_created_at "
                    "ON points_transaction (created_at)"
                ))
            else:
                connection.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_points_transaction_voter_token "
                    "ON points_transaction (voter_token)"
                ))
                connection.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_points_transaction_created_at "
                    "ON points_transaction (created_at)"
                ))

        logger = getattr(current_app, 'logger', None)
        message = 'Автоматически создана таблица points_transaction.'
        if logger:
            logger.info(message)
        else:
            print(message)
        return True
    except Exception as exc:
        logger = getattr(current_app, 'logger', None)
        message = 'Не удалось автоматически создать таблицу points_transaction.'
        if logger:
            logger.warning('%s Ошибка: %s', message, exc)
        else:
            print(f"{message} Ошибка: {exc}")
        return False


def log_points_transaction(
    voter_token,
    transaction_type,
    amount,
    balance_before,
    balance_after,
    description=None,
    movie_name=None,
    poll_id=None,
    commit=False,
):
    """
    Записывает транзакцию баллов в БД и выводит удобочитаемый лог.

    Args:
        voter_token: Токен пользователя
        transaction_type: Тип операции (vote, custom_vote, trailer, ban, admin)
        amount: Сумма изменения (положительная = начисление, отрицательная = списание)
        balance_before: Баланс до операции
        balance_after: Баланс после операции
        description: Описание операции
        movie_name: Название фильма (если применимо)
        poll_id: ID опроса (если применимо)
        commit: Делать ли commit после записи

    Returns:
        PointsTransaction или None при ошибке
    """
    # Сначала убедимся, что таблица существует
    ensure_points_transaction_table()

    logger = getattr(current_app, 'logger', None)

    # Форматируем сумму с +/-
    formatted_amount = f"+{amount}" if amount > 0 else str(amount)

    # Формируем консольный лог
    type_labels = {
        'vote': 'VOTE',
        'custom_vote': 'CUSTOM',
        'trailer': 'TRAILER',
        'ban': 'BAN',
        'admin': 'ADMIN',
    }
    type_label = type_labels.get(transaction_type, transaction_type.upper())

    # Получаем user_id если есть
    user_id = None
    try:
        profile = PollVoterProfile.query.get(voter_token)
        if profile:
            user_id = profile.user_id or profile.device_label or voter_token[:8]
    except Exception:
        user_id = voter_token[:8]

    # Формируем читаемый лог
    movie_part = f" | {movie_name}" if movie_name else ""
    poll_part = f" | poll:{poll_id}" if poll_id else ""
    log_message = (
        f"[POINTS] {type_label:8} | {user_id or voter_token[:8]:15} | "
        f"{formatted_amount:>6} | balance: {balance_before} → {balance_after}"
        f"{movie_part}{poll_part}"
    )

    if logger:
        logger.info(log_message)
    else:
        print(log_message)

    # Записываем в БД
    try:
        transaction = PointsTransaction(
            voter_token=voter_token,
            transaction_type=transaction_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            description=description,
            movie_name=movie_name,
            poll_id=poll_id,
        )
        db.session.add(transaction)

        if commit:
            db.session.commit()
        else:
            db.session.flush()

        return transaction
    except (ProgrammingError, OperationalError) as exc:
        db.session.rollback()
        if logger:
            logger.warning('Не удалось записать транзакцию баллов: %s', exc)
        return None
    except Exception as exc:
        db.session.rollback()
        if logger:
            logger.warning('Ошибка записи транзакции: %s', exc)
        return None


def get_voter_transactions(voter_token, limit=50, offset=0, transaction_type=None):
    """
    Получает историю транзакций пользователя.

    Args:
        voter_token: Токен пользователя
        limit: Максимум записей
        offset: Смещение для пагинации
        transaction_type: Фильтр по типу транзакции (опционально)

    Returns:
        list[PointsTransaction]
    """
    ensure_points_transaction_table()

    try:
        query = PointsTransaction.query.filter_by(voter_token=voter_token)

        if transaction_type:
            query = query.filter_by(transaction_type=transaction_type)

        return query.order_by(PointsTransaction.created_at.desc())\
            .offset(offset).limit(limit).all()
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return []


def get_voter_transactions_summary(voter_token):
    """
    Получает сводку по транзакциям пользователя.

    Returns:
        dict с total_earned, total_spent, transaction_count
    """
    ensure_points_transaction_table()

    try:
        transactions = PointsTransaction.query.filter_by(voter_token=voter_token).all()

        total_earned = sum(t.amount for t in transactions if t.amount > 0)
        total_spent = abs(sum(t.amount for t in transactions if t.amount < 0))

        # Группировка по типам
        by_type = {}
        for t in transactions:
            if t.transaction_type not in by_type:
                by_type[t.transaction_type] = {'count': 0, 'total': 0}
            by_type[t.transaction_type]['count'] += 1
            by_type[t.transaction_type]['total'] += t.amount

        return {
            'total_earned': total_earned,
            'total_spent': total_spent,
            'transaction_count': len(transactions),
            'by_type': by_type,
        }
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return {
            'total_earned': 0,
            'total_spent': 0,
            'transaction_count': 0,
            'by_type': {},
        }

