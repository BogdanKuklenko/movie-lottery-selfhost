# F:\GPT\movie-lottery V2\movie_lottery\config.py
import os

class Config:
    """Базовый класс конфигурации."""
    # Ключ для защиты сессий и форм. В реальном приложении его лучше сгенерировать.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a_super_secret_key')
    
    # Настройки базы данных
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    db_uri = os.environ.get('DATABASE_URL')
    if db_uri and db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = db_uri or 'sqlite:///instance/lottery.db'

    # Настройки qBittorrent
    QBIT_HOST = os.environ.get('QBIT_HOST')
    QBIT_PORT = os.environ.get('QBIT_PORT')
    QBIT_USERNAME = os.environ.get('QBIT_USERNAME')
    QBIT_PASSWORD = os.environ.get('QBIT_PASSWORD')
    
    # API ключ для Кинопоиска
    KINOPOISK_API_TOKEN = os.environ.get('KINOPOISK_API_TOKEN')
    