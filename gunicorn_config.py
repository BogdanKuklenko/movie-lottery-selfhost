"""Gunicorn configuration for Render.com deployment."""
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Worker processes
workers = 1  # Single worker for memory conservation on free tier
worker_class = "sync"
worker_connections = 100
max_requests = 500
max_requests_jitter = 50

# Timeout settings - critical for Render.com
timeout = 300  # 5 minutes for slow startup on free tier
graceful_timeout = 60
keepalive = 2

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "movie-lottery"

# Don't preload app for memory conservation
preload_app = False
