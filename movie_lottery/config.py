import os


class Config:
    """Base configuration class for the application."""

    SECRET_KEY = os.environ.get('SECRET_KEY', 'a_super_secret_key')
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL')
    POLL_CREATOR_TOKEN_SECRET = os.environ.get('POLL_CREATOR_TOKEN_SECRET')
    try:
        POLL_POINTS_PER_VOTE = int(os.environ.get('POLL_POINTS_PER_VOTE', 1))
    except (TypeError, ValueError):
        POLL_POINTS_PER_VOTE = 1
    POLL_POINTS_ADMIN_SECRET = os.environ.get('POLL_POINTS_ADMIN_SECRET')
    POLL_ADMIN_SECRET = os.environ.get('POLL_ADMIN_SECRET') or POLL_POINTS_ADMIN_SECRET
    
    # Database settings
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    db_uri = os.environ.get('DATABASE_URL')
    if db_uri and db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)
    
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(os.path.dirname(basedir), 'instance')
    
    SQLALCHEMY_DATABASE_URI = db_uri or f'sqlite:///{os.path.join(instance_dir, "lottery.db")}'
    
    # PostgreSQL settings - optimized for memory conservation
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 1,
        'max_overflow': 0,
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {
            'connect_timeout': 10,
        } if db_uri else {}
    }

    # qBittorrent settings
    QBIT_HOST = os.environ.get('QBIT_HOST')
    QBIT_PORT = os.environ.get('QBIT_PORT')
    QBIT_USERNAME = os.environ.get('QBIT_USERNAME')
    QBIT_PASSWORD = os.environ.get('QBIT_PASSWORD')
    
    # Kinopoisk API key
    KINOPOISK_API_TOKEN = os.environ.get('KINOPOISK_API_TOKEN') or os.environ.get('KINOPOISK_API_KEY')
    KINOPOISK_API_KEY = KINOPOISK_API_TOKEN
