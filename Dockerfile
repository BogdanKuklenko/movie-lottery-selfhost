# ---- Base ----
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Системные пакеты для psycopg2 и т.п. + ffmpeg для обработки видео
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev curl bash ca-certificates ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/

# Устанавливаем зависимости проекта + то, что часто нужно в проде
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir gunicorn alembic psycopg2-binary

# Копируем весь проект
COPY . /app

# Точка входа (ожидание БД, миграции, запуск)
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
