from datetime import datetime, timedelta
from flask import current_app
from sqlalchemy.exc import OperationalError, ProgrammingError
from . import db
from .utils.helpers import vladivostok_now

class MovieIdentifier(db.Model):
    __tablename__ = 'movie_identifier'
    kinopoisk_id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    magnet_link = db.Column(db.Text, nullable=False)

class Lottery(db.Model):
    id = db.Column(db.String(6), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=vladivostok_now)
    result_name = db.Column(db.String(200), nullable=True)
    result_poster = db.Column(db.String(500), nullable=True)
    result_year = db.Column(db.String(10), nullable=True)
    movies = db.relationship('Movie', backref='lottery', lazy=True, cascade="all, delete-orphan")

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kinopoisk_id = db.Column(db.Integer, nullable=True)
    name = db.Column(db.String(200), nullable=False)
    search_name = db.Column(db.String(200), nullable=True)
    poster = db.Column(db.String(500), nullable=True)
    year = db.Column(db.String(10), nullable=False)
    lottery_id = db.Column(db.String(6), db.ForeignKey('lottery.id'), nullable=False)
    description = db.Column(db.Text, nullable=True)
    rating_kp = db.Column(db.Float, nullable=True)
    genres = db.Column(db.String(200), nullable=True)
    countries = db.Column(db.String(200), nullable=True)

class LibraryMovie(db.Model):
    __tablename__ = 'library_movie'
    id = db.Column(db.Integer, primary_key=True)
    kinopoisk_id = db.Column(db.Integer, unique=True, nullable=True)
    name = db.Column(db.String(200), nullable=False)
    search_name = db.Column(db.String(200), nullable=True)
    poster = db.Column(db.String(500), nullable=True)  # Внешний URL (устаревшее)
    poster_file_path = db.Column(db.String(500), nullable=True)  # Локальный путь к постеру
    year = db.Column(db.String(10), nullable=True)
    description = db.Column(db.Text, nullable=True)
    rating_kp = db.Column(db.Float, nullable=True)
    genres = db.Column(db.String(200), nullable=True)
    countries = db.Column(db.String(200), nullable=True)
    trailer_file_path = db.Column(db.String(500), nullable=True)
    trailer_mime_type = db.Column(db.String(100), nullable=True)
    trailer_file_size = db.Column(db.Integer, nullable=True)
    added_at = db.Column(db.DateTime, nullable=False, default=vladivostok_now)
    bumped_at = db.Column(db.DateTime, nullable=False, default=vladivostok_now)
    badge = db.Column(db.String(30), nullable=True)  # Бейдж: favorite, ban, watchlist, top, watched, new или custom_ID
    points = db.Column(db.Integer, nullable=False, default=1)
    ban_until = db.Column(db.DateTime, nullable=True)
    ban_applied_by = db.Column(db.String(120), nullable=True)
    ban_cost = db.Column(db.Integer, nullable=True)
    ban_cost_per_month = db.Column(db.Integer, nullable=True)  # Индивидуальная цена за месяц бана (по умолчанию 1)
    trailer_view_cost = db.Column(db.Integer, nullable=True)  # Стоимость просмотра трейлера в баллах (по умолчанию 1)

    @property
    def has_local_poster(self):
        """Проверяет, есть ли локальный постер."""
        try:
            return bool(self.poster_file_path)
        except (OperationalError, ProgrammingError):
            return False

    @property
    def has_local_trailer(self):
        # Безопасный доступ к атрибуту, который может отсутствовать в БД
        try:
            trailer_path = self.trailer_file_path
            return bool(trailer_path)
        except (OperationalError, ProgrammingError):
            return False

    def refresh_ban_status(self):
        """Переводит фильм из бана в watchlist после истечения срока."""
        if self.badge != 'ban' or not self.ban_until:
            return False

        if vladivostok_now() >= self.ban_until:
            self.badge = 'watchlist'
            self.ban_until = None
            self.ban_applied_by = None
            self.ban_cost = None
            self.bumped_at = vladivostok_now()
            return True
        return False

    @property
    def ban_status(self):
        if self.badge != 'ban':
            return 'none'
        if not self.ban_until:
            return 'pending'
        return 'active' if vladivostok_now() < self.ban_until else 'expired'

    @property
    def ban_remaining_seconds(self):
        if self.badge != 'ban' or not self.ban_until:
            return 0
        remaining = (self.ban_until - vladivostok_now()).total_seconds()
        return max(0, int(remaining))

    @classmethod
    def refresh_all_bans(cls):
        """Пакетно обновляет истёкшие баны."""
        from . import db
        now = vladivostok_now()
        try:
            expired = cls.query.filter(
                cls.badge == 'ban',
                cls.ban_until.isnot(None),
                cls.ban_until <= now,
            ).all()
        except (OperationalError, ProgrammingError) as exc:
            current_app.logger.warning(
                "Skipping ban refresh because column is missing. Run pending migrations. Error: %s",
                exc,
            )
            # Откатываем транзакцию после ошибки
            try:
                db.session.rollback()
            except Exception:
                pass
            return False

        changed = False
        for movie in expired:
            changed = movie.refresh_ban_status() or changed

        return changed

class CustomBadge(db.Model):
    """Кастомный бейдж, созданный пользователем."""
    __tablename__ = 'custom_badge'
    id = db.Column(db.Integer, primary_key=True)
    emoji = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=vladivostok_now)


class MovieSchedule(db.Model):
    """Таймер/расписание для фильма в календаре."""
    __tablename__ = 'movie_schedule'
    id = db.Column(db.Integer, primary_key=True)
    library_movie_id = db.Column(
        db.Integer,
        db.ForeignKey('library_movie.id', ondelete='CASCADE'),
        nullable=False
    )
    scheduled_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, confirmed
    postponed_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=vladivostok_now)

    library_movie = db.relationship(
        'LibraryMovie',
        backref=db.backref('schedules', lazy=True, cascade='all, delete-orphan')
    )

    __table_args__ = (
        db.UniqueConstraint('library_movie_id', 'scheduled_date', name='unique_movie_schedule_date'),
    )

    @property
    def is_due(self):
        """Проверяет, наступило ли время уведомления."""
        if self.status != 'pending':
            return False
        now = vladivostok_now()
        check_time = self.postponed_until if self.postponed_until else self.scheduled_date
        return now >= check_time

    @classmethod
    def cleanup_expired(cls):
        """Удаляет истёкшие pending таймеры (прошло более 24 часов после даты)."""
        from . import db
        now = vladivostok_now()
        # Удаляем таймеры, которые просрочены более чем на 24 часа и всё ещё pending
        threshold = now - timedelta(hours=24)
        try:
            expired = cls.query.filter(
                cls.status == 'pending',
                db.or_(
                    db.and_(cls.postponed_until.isnot(None), cls.postponed_until < threshold),
                    db.and_(cls.postponed_until.is_(None), cls.scheduled_date < threshold)
                )
            ).all()
            count = len(expired)
            for schedule in expired:
                db.session.delete(schedule)
            if count > 0:
                db.session.commit()
            return count
        except (OperationalError, ProgrammingError) as exc:
            current_app.logger.warning(
                "Skipping schedule cleanup: %s", exc
            )
            try:
                db.session.rollback()
            except Exception:
                pass
            return 0


class BackgroundPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poster_url = db.Column(db.String(500), unique=True, nullable=False)
    pos_top = db.Column(db.Float, nullable=False)
    pos_left = db.Column(db.Float, nullable=False)
    rotation = db.Column(db.Integer, nullable=False)
    z_index = db.Column(db.Integer, nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=vladivostok_now)


class PollCreatorToken(db.Model):
    __tablename__ = 'poll_creator_token'

    id = db.Column(db.Integer, primary_key=True)
    creator_token = db.Column(db.String(64), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=vladivostok_now)
    last_seen = db.Column(
        db.DateTime,
        nullable=False,
        default=vladivostok_now,
        onupdate=vladivostok_now,
    )


class PollSettings(db.Model):
    __tablename__ = 'poll_settings'

    id = db.Column(db.Integer, primary_key=True, default=1)
    custom_vote_cost = db.Column(db.Integer, nullable=False, default=10)
    poll_duration_hours = db.Column(db.Integer, nullable=False, default=24, server_default=db.text('24'))
    created_at = db.Column(db.DateTime, nullable=False, default=vladivostok_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=vladivostok_now,
        onupdate=vladivostok_now,
    )


class Poll(db.Model):
    id = db.Column(db.String(8), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=vladivostok_now)
    expires_at = db.Column(db.DateTime, nullable=False)
    creator_token = db.Column(db.String(64), nullable=False)
    forced_winner_movie_id = db.Column(db.Integer, nullable=True)
    notifications_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text('FALSE'))
    theme = db.Column(db.String(30), nullable=False, default='default', server_default='default')  # Тема оформления опроса
    movies = db.relationship('PollMovie', backref='poll', lazy=True, cascade="all, delete-orphan")
    votes = db.relationship('Vote', backref='poll', lazy=True, cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super(Poll, self).__init__(**kwargs)
        if not self.expires_at:
            self.expires_at = vladivostok_now() + timedelta(hours=24)
    
    @property
    def is_expired(self):
        return vladivostok_now() > self.expires_at

    @property
    def winners(self):
        """Возвращает список фильмов-победителей с максимальным количеством голосов"""
        forced_winner = None
        if self.forced_winner_movie_id:
            forced_winner = next(
                (movie for movie in self.movies if movie.id == self.forced_winner_movie_id),
                None,
            )

        if forced_winner:
            return [forced_winner]

        if not self.votes:
            return []
        
        # Подсчитываем голоса для каждого фильма
        vote_counts = {}
        for vote in self.votes:
            vote_counts[vote.movie_id] = vote_counts.get(vote.movie_id, 0) + 1
        
        if not vote_counts:
            return []
        
        max_votes = max(vote_counts.values())
        winner_movie_ids = [movie_id for movie_id, count in vote_counts.items() if count == max_votes]
        
        return [movie for movie in self.movies if movie.id in winner_movie_ids]
    
    def get_vote_counts(self):
        """Возвращает словарь {movie_id: количество голосов}"""
        vote_counts = {}
        for vote in self.votes:
            vote_counts[vote.movie_id] = vote_counts.get(vote.movie_id, 0) + 1
        return vote_counts

class PollMovie(db.Model):
    __tablename__ = 'poll_movie'
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.String(8), db.ForeignKey('poll.id'), nullable=False)
    kinopoisk_id = db.Column(db.Integer, nullable=True)
    name = db.Column(db.String(200), nullable=False)
    search_name = db.Column(db.String(200), nullable=True)
    poster = db.Column(db.String(500), nullable=True)
    year = db.Column(db.String(10), nullable=True)
    description = db.Column(db.Text, nullable=True)
    rating_kp = db.Column(db.Float, nullable=True)
    genres = db.Column(db.String(200), nullable=True)
    countries = db.Column(db.String(200), nullable=True)
    points = db.Column(db.Integer, nullable=False, default=1)
    ban_until = db.Column(db.DateTime, nullable=True)

    @property
    def ban_status(self):
        if not self.ban_until:
            return 'none'
        return 'active' if vladivostok_now() < self.ban_until else 'expired'

    @property
    def ban_remaining_seconds(self):
        if not self.ban_until:
            return 0
        remaining = (self.ban_until - vladivostok_now()).total_seconds()
        return max(0, int(remaining))

    @property
    def is_banned(self):
        return self.ban_status == 'active'


class PollVoterProfile(db.Model):
    __tablename__ = 'poll_voter_profile'

    token = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.String(128), unique=True, nullable=True)
    total_points = db.Column(db.Integer, nullable=False, default=0)
    points_accrued_total = db.Column(
        db.Integer, nullable=False, default=0, server_default=db.text('0')
    )
    device_label = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=vladivostok_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=vladivostok_now,
        onupdate=vladivostok_now,
    )
    # Streak fields for consecutive voting bonus
    voting_streak = db.Column(db.Integer, nullable=False, default=0, server_default=db.text('0'))
    last_vote_date = db.Column(db.Date, nullable=True)
    max_voting_streak = db.Column(db.Integer, nullable=False, default=0, server_default=db.text('0'))
    # Уведомления о новых голосах
    notifications_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text('0'))

    votes = db.relationship('Vote', back_populates='profile', lazy=True)
    push_subscriptions = db.relationship('PushSubscription', back_populates='profile', lazy=True, cascade='all, delete-orphan')


class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.String(8), db.ForeignKey('poll.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('poll_movie.id'), nullable=False)
    voter_token = db.Column(
        db.String(64),
        db.ForeignKey('poll_voter_profile.token'),
        nullable=False,
    )  # Токен для идентификации голосующего
    voted_at = db.Column(db.DateTime, nullable=False, default=vladivostok_now)
    points_awarded = db.Column(db.Integer, nullable=False, default=0)

    profile = db.relationship('PollVoterProfile', back_populates='votes')

    __table_args__ = (
        db.UniqueConstraint('poll_id', 'voter_token', name='unique_voter_per_poll'),
    )


class PointsTransaction(db.Model):
    """История всех операций с баллами пользователей."""
    __tablename__ = 'points_transaction'

    id = db.Column(db.Integer, primary_key=True)
    voter_token = db.Column(db.String(64), nullable=False, index=True)
    transaction_type = db.Column(db.String(30), nullable=False)  # vote, custom_vote, trailer, ban
    amount = db.Column(db.Integer, nullable=False)  # положительный = начисление, отрицательный = списание
    balance_before = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(255), nullable=True)  # детали операции
    movie_name = db.Column(db.String(200), nullable=True)
    poll_id = db.Column(db.String(8), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=vladivostok_now, index=True)

    # Типы транзакций
    TYPE_VOTE = 'vote'  # Начисление за голосование
    TYPE_CUSTOM_VOTE = 'custom_vote'  # Списание за кастомный голос
    TYPE_TRAILER = 'trailer'  # Списание за просмотр трейлера
    TYPE_BAN = 'ban'  # Списание за бан фильма
    TYPE_ADMIN = 'admin'  # Ручное изменение админом

    @property
    def is_credit(self):
        """Проверяет, является ли транзакция начислением."""
        return self.amount > 0

    @property
    def formatted_amount(self):
        """Возвращает сумму с + или - для отображения."""
        return f"+{self.amount}" if self.amount > 0 else str(self.amount)

    @property
    def type_emoji(self):
        """Возвращает эмодзи для типа транзакции."""
        emojis = {
            self.TYPE_VOTE: '🎬',
            self.TYPE_CUSTOM_VOTE: '🎯',
            self.TYPE_TRAILER: '📺',
            self.TYPE_BAN: '🚫',
            self.TYPE_ADMIN: '👤',
        }
        return emojis.get(self.transaction_type, '💰')

    @property
    def type_label(self):
        """Возвращает человекочитаемое название типа."""
        labels = {
            self.TYPE_VOTE: 'Голосование',
            self.TYPE_CUSTOM_VOTE: 'Кастомный голос',
            self.TYPE_TRAILER: 'Трейлер',
            self.TYPE_BAN: 'Бан фильма',
            self.TYPE_ADMIN: 'Админ',
        }
        return labels.get(self.transaction_type, self.transaction_type)


class PushSubscription(db.Model):
    """Подписки на push-уведомления о новых голосах."""
    __tablename__ = 'push_subscription'

    id = db.Column(db.Integer, primary_key=True)
    voter_token = db.Column(
        db.String(64),
        db.ForeignKey('poll_voter_profile.token', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    p256dh_key = db.Column(db.Text, nullable=False)
    auth_key = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=vladivostok_now)

    profile = db.relationship('PollVoterProfile', back_populates='push_subscriptions')
