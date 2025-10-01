import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix

db = SQLAlchemy()

def create_app():
    """
    Фабрика для создания и конфигурации экземпляра приложения Flask.
    """
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_object('movie_lottery.config.Config')
    
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    db.init_app(app)
    
    Migrate(app, db)

    # Импортируем модели (нужно для миграций и регистрации моделей)
    from . import models
    
    # Регистрируем blueprints
    from .routes.main_routes import main_bp
    from .routes.api_routes import api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    # Создаем таблицы БД, если их нет (только в dev режиме)
    with app.app_context():
        db.create_all()
    
    return app