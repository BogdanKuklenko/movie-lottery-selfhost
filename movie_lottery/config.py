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
    
    # Формируем абсолютный путь к БД в папке instance
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(os.path.dirname(basedir), 'instance')
    
    SQLALCHEMY_DATABASE_URI = db_uri or f'sqlite:///{os.path.join(instance_dir, "lottery.db")}'
    
    # Настройки для PostgreSQL - таймауты для предотвращения зависаний
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # Проверка соединения перед использованием
        'pool_recycle': 300,    # Переиспользование соединений через 5 минут
        'connect_args': {
            'connect_timeout': 10,  # Timeout подключения 10 секунд
        } if db_uri else {}
    }

    # Настройки qBittorrent
    QBIT_HOST = os.environ.get('QBIT_HOST')
    QBIT_PORT = os.environ.get('QBIT_PORT')
    QBIT_USERNAME = os.environ.get('QBIT_USERNAME')
    QBIT_PASSWORD = os.environ.get('QBIT_PASSWORD')
    
    # API ключ для Кинопоиска
    KINOPOISK_API_TOKEN = os.environ.get('KINOPOISK_API_TOKEN')
    