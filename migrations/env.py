import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# --- НАЧАЛО ИСПРАВЛЕНИЯ ---
# Импортируем наше приложение и базу данных
from movie_lottery import create_app, db

# Создаем экземпляр приложения Flask, чтобы получить его конфигурацию
# Переменная окружения DATABASE_URL будет автоматически подхвачена Render
app = create_app()

# Указываем Alembic на метаданные наших моделей (самый важный шаг)
target_metadata = db.metadata
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = app.config.get('SQLALCHEMY_DATABASE_URI') # Используем URI из приложения
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Используем конфигурацию SQLAlchemy из нашего приложения Flask
    connectable = db.engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()