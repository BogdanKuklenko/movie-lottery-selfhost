# gunicorn_config.py
# Конфигурация для gunicorn на Render.com

import os
import multiprocessing

# Bind
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Worker Settings
workers = 1  # Только 1 worker для экономии памяти на бесплатном плане
worker_class = "sync"
worker_connections = 1000
max_requests = 1000  # Перезапуск worker'а после 1000 запросов (предотвращает утечки памяти)
max_requests_jitter = 50

# Timeout Settings - КЛЮЧЕВОЕ ИЗМЕНЕНИЕ
timeout = 120  # Увеличено с 30 до 120 секунд
graceful_timeout = 30
keepalive = 5

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process Naming
proc_name = "movie-lottery"

# Preload
preload_app = False  # НЕ предзагружаем приложение для экономии памяти

