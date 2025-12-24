import atexit
import os

from flask import Flask

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_socketio import SocketIO

from .diagnostic_middleware import start_diagnostics, checkpoint, finish_diagnostics

_diag = start_diagnostics()
db = SQLAlchemy()
scheduler = BackgroundScheduler()
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')


def _configure_cors(app):
    """Настраивает CORS для API опросов, чтобы ими можно было пользоваться с разных доменов."""
    raw_origins = app.config.get('POLL_API_ALLOWED_ORIGINS')
    origins = []

    if raw_origins:
        origins = [origin.strip() for origin in raw_origins.split(',') if origin.strip()]
    elif app.config.get('POLL_API_BASE_URL'):
        # Если указан отдельный базовый URL для API опросов,
        # по умолчанию разрешаем кросс-доменные запросы.
        origins = ['*']

    if not origins:
        return

    CORS(app, resources={r"/api/polls/*": {"origins": origins}})


def create_app():
    """
    Factory function for creating and configuring a Flask application instance.
    """
    checkpoint("create_app() started")
    
    app = Flask(__name__, instance_relative_config=True)
    checkpoint("Flask instance created")

    app.config.from_object('movie_lottery.config.Config')
    checkpoint("Config loaded")

    _configure_cors(app)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Ensure trailer upload directory exists
    trailer_dir = app.config.get('TRAILER_UPLOAD_DIR')
    if trailer_dir:
        try:
            os.makedirs(trailer_dir, exist_ok=True)
        except OSError as exc:
            app.logger.warning('Не удалось создать директорию для трейлеров %s: %s', trailer_dir, exc)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    checkpoint("ProxyFix configured")

    db.init_app(app)
    checkpoint("SQLAlchemy initialized")

    Migrate(app, db)
    checkpoint("Flask-Migrate initialized")

    with app.app_context():
        from .utils.helpers import (
            ensure_library_movie_columns,
            ensure_poll_movie_points_column,
            ensure_poll_movie_ban_column,
            ensure_poll_forced_winner_column,
            ensure_poll_voter_user_id_column,
            ensure_poll_tables,
            ensure_vote_points_column,
            ensure_voter_streak_columns,
        )

        ensure_poll_tables()
        ensure_poll_voter_user_id_column()
        ensure_vote_points_column()
        ensure_poll_movie_points_column()
        ensure_poll_movie_ban_column()
        ensure_poll_forced_winner_column()
        ensure_library_movie_columns()
        ensure_voter_streak_columns()

    from . import models
    checkpoint("Models imported")

    from .routes.main_routes import main_bp
    checkpoint("main_routes imported")
    
    from .routes.api_routes import api_bp
    checkpoint("api_routes imported")
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    checkpoint("Blueprints registered")

    socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')
    checkpoint("SocketIO initialized")

    from .cli import register_cli

    register_cli(app)
    
    # Запускаем планировщик для очистки истёкших опросов и таймеров
    # ВАЖНО: При использовании gunicorn с несколькими воркерами нужно запускать
    # планировщик только в одном процессе, чтобы избежать дублирования задач.
    # Используем файловую блокировку для гарантии единственного экземпляра.
    def _should_start_scheduler():
        """Проверяет, нужно ли запускать планировщик в этом процессе."""
        # В режиме разработки Flask проверяем reloader
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'false':
            return False
        if os.environ.get('FLASK_DEBUG_RELOADER'):
            return False
        
        # Для gunicorn: используем файловую блокировку (только Unix/Linux)
        # Только первый процесс, который захватит lock, запустит scheduler
        try:
            import fcntl
        except ImportError:
            # Windows не поддерживает fcntl, запускаем scheduler 
            # (в production всегда Linux/Docker)
            return True
        
        import tempfile
        lock_file = os.path.join(tempfile.gettempdir(), 'movie_lottery_scheduler.lock')
        try:
            # Открываем или создаём lock-файл
            lock_fd = os.open(lock_file, os.O_CREAT | os.O_RDWR)
            # Пытаемся захватить эксклюзивную блокировку без ожидания
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Записываем PID для отладки
            os.write(lock_fd, f'{os.getpid()}\n'.encode())
            os.fsync(lock_fd)
            # Не закрываем файл - блокировка должна держаться пока процесс жив
            # Сохраняем дескриптор чтобы он не был закрыт GC
            app._scheduler_lock_fd = lock_fd
            return True
        except (BlockingIOError, OSError):
            # Другой процесс уже держит блокировку
            return False
    
    if not scheduler.running and _should_start_scheduler():
        from .utils.helpers import finalize_poll, vladivostok_now
        from .models import MovieSchedule, Poll
        
        def cleanup_schedules_job():
            with app.app_context():
                count = MovieSchedule.cleanup_expired()
                if count > 0:
                    app.logger.info("Удалено истёкших таймеров: %d", count)
        
        scheduler.add_job(
            func=cleanup_schedules_job,
            trigger=IntervalTrigger(hours=1),
            id='cleanup_schedules',
            name='Cleanup expired movie schedules',
            replace_existing=True
        )
        
        # Периодическая проверка истёкших опросов и присвоение бейджей
        # Проверяем каждые 10 секунд для быстрого срабатывания
        def finalize_expired_polls_job():
            with app.app_context():
                try:
                    now = vladivostok_now()
                    
                    # Находим все истёкшие опросы, которые ещё не были финализированы
                    expired_polls = Poll.query.filter(
                        Poll.expires_at <= now,
                        Poll.finalized == False  # noqa: E712
                    ).all()
                    
                    for poll in expired_polls:
                        if finalize_poll(poll.id):
                            app.logger.info("Финализирован опрос %s", poll.id)
                except Exception as e:
                    app.logger.warning("Ошибка проверки истёкших опросов: %s", e)
        
        scheduler.add_job(
            func=finalize_expired_polls_job,
            trigger=IntervalTrigger(seconds=10),  # Проверяем каждые 10 секунд
            id='finalize_expired_polls',
            name='Finalize expired polls and apply winner badges',
            replace_existing=True
        )
        
        scheduler.start()
        checkpoint("Scheduler started (single instance with file lock)")
        
        # При старте сразу финализируем пропущенные опросы
        finalize_expired_polls_job()
        
        # Останавливаем scheduler при завершении приложения
        atexit.register(lambda: scheduler.shutdown() if scheduler.running else None)
    
    finish_diagnostics()
    return app