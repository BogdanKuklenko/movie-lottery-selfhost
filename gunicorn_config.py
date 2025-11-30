"""Gunicorn configuration for deployment."""
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Worker processes
workers = int(os.environ.get('GUNICORN_WORKERS', 2))
threads = int(os.environ.get('GUNICORN_THREADS', 4))
worker_class = "gthread"  # Threaded workers для лучшего стриминга
worker_connections = 100
max_requests = 1000
max_requests_jitter = 50

# Timeout settings - увеличены для стриминга видео
timeout = 600  # 10 минут для больших видео файлов
graceful_timeout = 120
keepalive = 65  # Keep-alive соединения живыми 65 сек (больше чем default браузеров ~60s)

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "movie-lottery"

# Don't preload app for memory conservation
preload_app = False
