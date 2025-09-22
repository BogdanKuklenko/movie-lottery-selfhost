import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# --- НАЧАЛО ИСПРАВЛЕНИЯ ---
# Импортируем наше приложение и базу данных
# Это позволяет Alembic "увидеть" ваши модели и конфигурацию
from movie_lottery import create_app, db

# Создаем экземпляр приложения Flask, чтобы получить его конфигурацию
app = create_app()

# Указываем Alembic на метаданные наших моделей (самый важный шаг)
target_metadata = db.metadata
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---


# это объект конфигурации Alembic, который предоставляет
# доступ к значениям в используемом .ini файле.
config = context.config

# Интерпретируем файл конфигурации для логирования Python.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Запуск миграций в 'оффлайн' режиме."""
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
    """Запуск миграций в 'онлайн' режиме."""
    # Используем движок SQLAlchemy из нашего Flask-приложения
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