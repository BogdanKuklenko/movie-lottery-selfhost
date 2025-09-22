# F:\GPT\movie-lottery V2\movie_lottery\__init__.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix

# Создаем экземпляр SQLAlchemy, но пока не привязываем его к приложению
db = SQLAlchemy()

def create_app():
    """
    Фабрика для создания и конфигурации экземпляра приложения Flask.
    """
    app = Flask(__name__, instance_relative_config=True)

    # Загружаем конфигурацию из файла config.py
    app.config.from_object('movie_lottery.config.Config')
    
    # Убедимся, что папка 'instance' существует.
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Применяем ProxyFix для корректной работы за прокси-сервером
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Инициализируем базу данных для нашего приложения
    db.init_app(app)

    with app.app_context():
        # Импортируем маршруты (Blueprints)
        from .routes.main_routes import main_bp
        from .routes.api_routes import api_bp
        
        # Регистрируем Blueprints в приложении
        app.register_blueprint(main_bp)
        app.register_blueprint(api_bp)

        # Создаем все таблицы базы данных, если их еще нет
        # Импортируем модели здесь, чтобы они были известны SQLAlchemy
        from . import models
        db.create_all()
        
        return app