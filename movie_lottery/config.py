import os


class Config:
    """Base configuration class for the application."""

    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError(
            "SECRET_KEY environment variable must be set for security. "
            "Generate one using: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL')
    try:
        POLL_POINTS_PER_VOTE = int(os.environ.get('POLL_POINTS_PER_VOTE', 1))
    except (TypeError, ValueError):
        POLL_POINTS_PER_VOTE = 1

    try:
        POLL_CUSTOM_VOTE_COST = int(os.environ.get('POLL_CUSTOM_VOTE_COST', 10))
    except (TypeError, ValueError):
        POLL_CUSTOM_VOTE_COST = 10

    # Дополнительные настройки API опросов
    POLL_API_BASE_URL = os.environ.get('POLL_API_BASE_URL')
    POLL_API_ALLOWED_ORIGINS = os.environ.get('POLL_API_ALLOWED_ORIGINS')

    # Database settings
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    db_uri = os.environ.get('DATABASE_URL')
    if db_uri and db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)
    
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(os.path.dirname(basedir), 'instance')
    
    SQLALCHEMY_DATABASE_URI = db_uri or f'sqlite:///{os.path.join(instance_dir, "lottery.db")}'
    
    # PostgreSQL settings - optimized for memory conservation
    connect_args = {}
    if db_uri and db_uri.startswith('postgresql'):
        connect_args['connect_timeout'] = 10

    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 1,
        'max_overflow': 0,
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': connect_args,
    }

    # qBittorrent settings
    QBIT_HOST = os.environ.get('QBIT_HOST')
    QBIT_PORT = os.environ.get('QBIT_PORT')
    QBIT_USERNAME = os.environ.get('QBIT_USERNAME')
    QBIT_PASSWORD = os.environ.get('QBIT_PASSWORD')

    # Kinopoisk API key
    KINOPOISK_API_TOKEN = os.environ.get('KINOPOISK_API_TOKEN') or os.environ.get('KINOPOISK_API_KEY')
    KINOPOISK_API_KEY = KINOPOISK_API_TOKEN

    # Trailer upload settings
    TRAILER_UPLOAD_SUBDIR = os.environ.get('TRAILER_UPLOAD_SUBDIR', 'trailers')
    TRAILER_MEDIA_ROOT = os.environ.get('TRAILER_MEDIA_ROOT') or os.path.join(instance_dir, 'media')
    TRAILER_UPLOAD_DIR = os.path.join(TRAILER_MEDIA_ROOT, TRAILER_UPLOAD_SUBDIR)

    raw_mime_types = os.environ.get('TRAILER_ALLOWED_MIME_TYPES', 'video/mp4,video/webm')
    TRAILER_ALLOWED_MIME_TYPES = [mt.strip().lower() for mt in raw_mime_types.split(',') if mt.strip()]

    try:
        TRAILER_MAX_FILE_SIZE = int(os.environ.get('TRAILER_MAX_FILE_SIZE', 100 * 1024 * 1024))
    except (TypeError, ValueError):
        TRAILER_MAX_FILE_SIZE = 100 * 1024 * 1024
