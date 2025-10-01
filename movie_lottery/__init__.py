import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix

# Диагностика запуска (только на Render или если включена)
from .diagnostic_middleware import start_diagnostics, checkpoint, finish_diagnostics
_diag = start_diagnostics()

db = SQLAlchemy()

def create_app():
    """
    Фабрика для создания и конфигурации экземпляра приложения Flask.
    """
    checkpoint("create_app() started")
    
    app = Flask(__name__, instance_relative_config=True)
    checkpoint("Flask instance created")

    app.config.from_object('movie_lottery.config.Config')
    checkpoint("Config loaded")
    
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

    # Импортируем модели (нужно для миграций и регистрации моделей)
    from . import models
    checkpoint("Models imported")
    
    # Регистрируем blueprints
    from .routes.main_routes import main_bp
    checkpoint("main_routes imported")
    
    from .routes.api_routes import api_bp
    checkpoint("api_routes imported")
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    checkpoint("Blueprints registered")

    # НЕ создаем таблицы при каждом старте worker'а - это замедляет запуск
    # Таблицы должны быть созданы через миграции или вручную
    # Это критично для избежания timeout'ов на production-серверах
    
    finish_diagnostics()
    return app