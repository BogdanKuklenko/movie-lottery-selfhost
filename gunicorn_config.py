# gunicorn_config.py
# Конфигурация для gunicorn на Render.com

import os
import multiprocessing

# Bind
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Worker Settings
workers = 1  # Только 1 worker для экономии памяти на бесплатном плане
worker_class = "sync"
worker_connections = 100  # Снижено с 1000 для экономии памяти
max_requests = 500  # Перезапуск worker'а чаще для освобождения памяти
max_requests_jitter = 50

# Timeout Settings - КРИТИЧНО для Render.com
timeout = 300  # Увеличено до 5 минут для медленного старта на бесплатном плане
graceful_timeout = 60
keepalive = 2

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process Naming
proc_name = "movie-lottery"

# Preload
preload_app = False  # НЕ предзагружаем приложение для экономии памяти

