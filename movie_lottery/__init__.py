import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from flask_cors import CORS
import atexit

from .diagnostic_middleware import start_diagnostics, checkpoint, finish_diagnostics

_diag = start_diagnostics()
db = SQLAlchemy()
scheduler = BackgroundScheduler()


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
        )

        ensure_poll_tables()
        ensure_poll_voter_user_id_column()
        ensure_vote_points_column()
        ensure_poll_movie_points_column()
        ensure_poll_movie_ban_column()
        ensure_poll_forced_winner_column()
        ensure_library_movie_columns()

    from . import models
    checkpoint("Models imported")

    from .routes.main_routes import main_bp
    checkpoint("main_routes imported")
    
    from .routes.api_routes import api_bp
    checkpoint("api_routes imported")
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    checkpoint("Blueprints registered")

    from .cli import register_cli

    register_cli(app)
    
    # Запускаем планировщик для очистки истёкших опросов
    # В продакшене (Gunicorn) или в режиме разработки, но не в reloader процессе
    if not scheduler.running:
        # В режиме разработки запускаем только в основном процессе (не в reloader)
        # В продакшене (без reloader) всегда запускаем
        if os.environ.get('WERKZEUG_RUN_MAIN') != 'false' and not os.environ.get('FLASK_DEBUG_RELOADER'):
            from .utils.helpers import cleanup_expired_polls
            
            def cleanup_job():
                with app.app_context():
                    count = cleanup_expired_polls()
                    if count > 0:
                        app.logger.info(f"Удалено истёкших опросов: {count}")
            
            scheduler.add_job(
                func=cleanup_job,
                trigger=IntervalTrigger(hours=1),  # Запускаем каждый час
                id='cleanup_polls',
                name='Cleanup expired polls',
                replace_existing=True
            )
            scheduler.start()
            checkpoint("Scheduler started")
            
            # Останавливаем scheduler при завершении приложения
            atexit.register(lambda: scheduler.shutdown() if scheduler.running else None)
    
    finish_diagnostics()
    return app