from datetime import datetime, timedelta
from flask import current_app
from sqlalchemy.exc import OperationalError, ProgrammingError
from . import db

class MovieIdentifier(db.Model):
    __tablename__ = 'movie_identifier'
    kinopoisk_id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    magnet_link = db.Column(db.Text, nullable=False)

class Lottery(db.Model):
    id = db.Column(db.String(6), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
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
    poster = db.Column(db.String(500), nullable=True)
    year = db.Column(db.String(10), nullable=True)
    description = db.Column(db.Text, nullable=True)
    rating_kp = db.Column(db.Float, nullable=True)
    genres = db.Column(db.String(200), nullable=True)
    countries = db.Column(db.String(200), nullable=True)
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    bumped_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    badge = db.Column(db.String(20), nullable=True)  # Бейдж: favorite, ban, watchlist, top, watched, new
    points = db.Column(db.Integer, nullable=False, default=1)
    ban_until = db.Column(db.DateTime, nullable=True)
    ban_applied_by = db.Column(db.String(120), nullable=True)
    ban_cost = db.Column(db.Integer, nullable=True)
    ban_cost_per_month = db.Column(db.Integer, nullable=True)  # Индивидуальная цена за месяц бана (по умолчанию 1)

    def refresh_ban_status(self):
        """Переводит фильм из бана в watchlist после истечения срока."""
        if self.badge != 'ban' or not self.ban_until:
            return False

        if datetime.utcnow() >= self.ban_until:
            self.badge = 'watchlist'
            self.ban_until = None
            self.ban_applied_by = None
            self.ban_cost = None
            self.bumped_at = datetime.utcnow()
            return True
        return False

    @property
    def ban_status(self):
        if self.badge != 'ban':
            return 'none'
        if not self.ban_until:
            return 'pending'
        return 'active' if datetime.utcnow() < self.ban_until else 'expired'

    @property
    def ban_remaining_seconds(self):
        if self.badge != 'ban' or not self.ban_until:
            return 0
        remaining = (self.ban_until - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))

    @classmethod
    def refresh_all_bans(cls):
        """Пакетно обновляет истёкшие баны."""
        now = datetime.utcnow()
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
            return False

        changed = False
        for movie in expired:
            changed = movie.refresh_ban_status() or changed

        return changed

class BackgroundPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poster_url = db.Column(db.String(500), unique=True, nullable=False)
    pos_top = db.Column(db.Float, nullable=False)
    pos_left = db.Column(db.Float, nullable=False)
    rotation = db.Column(db.Integer, nullable=False)
    z_index = db.Column(db.Integer, nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class PollCreatorToken(db.Model):
    __tablename__ = 'poll_creator_token'

    id = db.Column(db.Integer, primary_key=True)
    creator_token = db.Column(db.String(64), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_seen = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class PollSettings(db.Model):
    __tablename__ = 'poll_settings'

    id = db.Column(db.Integer, primary_key=True, default=1)
    custom_vote_cost = db.Column(db.Integer, nullable=False, default=10)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class Poll(db.Model):
    id = db.Column(db.String(8), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    creator_token = db.Column(db.String(64), nullable=False)
    forced_winner_movie_id = db.Column(db.Integer, nullable=True)
    movies = db.relationship('PollMovie', backref='poll', lazy=True, cascade="all, delete-orphan")
    votes = db.relationship('Vote', backref='poll', lazy=True, cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super(Poll, self).__init__(**kwargs)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(hours=24)
    
    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at

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
        return 'active' if datetime.utcnow() < self.ban_until else 'expired'

    @property
    def ban_remaining_seconds(self):
        if not self.ban_until:
            return 0
        remaining = (self.ban_until - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))

    @property
    def is_banned(self):
        return self.ban_status == 'active'


class PollVoterProfile(db.Model):
    __tablename__ = 'poll_voter_profile'

    token = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.String(128), unique=True, nullable=True)
    total_points = db.Column(db.Integer, nullable=False, default=0)
    points_accrued_total = db.Column(db.Integer, nullable=False, default=0)
    device_label = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    votes = db.relationship('Vote', back_populates='profile', lazy=True)


class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.String(8), db.ForeignKey('poll.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('poll_movie.id'), nullable=False)
    voter_token = db.Column(
        db.String(64),
        db.ForeignKey('poll_voter_profile.token'),
        nullable=False,
    )  # Токен для идентификации голосующего
    voted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    points_awarded = db.Column(db.Integer, nullable=False, default=0)

    profile = db.relationship('PollVoterProfile', back_populates='votes')

    __table_args__ = (
        db.UniqueConstraint('poll_id', 'voter_token', name='unique_voter_per_poll'),
    )
