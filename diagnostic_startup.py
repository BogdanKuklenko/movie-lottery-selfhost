#!/usr/bin/env python
"""
Diagnostic Script for Render Deployment Issues
Показывает использование памяти и время на каждом этапе загрузки приложения
"""

import os
import sys
import time
import psutil
import gc

# Цвета для логов
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def get_memory_mb():
    """Получить использование памяти в MB"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

def log_step(step_name, start_time, start_memory):
    """Логировать шаг с временем и памятью"""
    elapsed = time.time() - start_time
    memory_now = get_memory_mb()
    memory_delta = memory_now - start_memory
    
    status = Colors.GREEN + "✓" + Colors.END
    if elapsed > 5:
        status = Colors.YELLOW + "⚠" + Colors.END
    if elapsed > 10:
        status = Colors.RED + "✗" + Colors.END
    
    print(f"{status} {step_name:50} | {elapsed:6.2f}s | {memory_now:7.1f} MB | +{memory_delta:6.1f} MB")
    return time.time(), memory_now

def print_separator():
    print("=" * 90)

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{text}{Colors.END}")
    print_separator()

# Начало диагностики
print_header("🔍 DIAGNOSTIC STARTUP REPORT - Movie Lottery")

# Системная информация
print(f"\n{Colors.BOLD}System Information:{Colors.END}")
print(f"  Python Version: {sys.version}")
print(f"  Platform: {sys.platform}")
print(f"  CPU Count: {psutil.cpu_count()}")
print(f"  Total RAM: {psutil.virtual_memory().total / 1024 / 1024 / 1024:.1f} GB")
print(f"  Available RAM: {psutil.virtual_memory().available / 1024 / 1024 / 1024:.1f} GB")
print(f"  PID: {os.getpid()}")

# Переменные окружения
print(f"\n{Colors.BOLD}Environment Variables:{Colors.END}")
print(f"  RENDER: {os.environ.get('RENDER', 'Not Set')}")
print(f"  DATABASE_URL: {'Set' if os.environ.get('DATABASE_URL') else 'Not Set'}")
print(f"  PORT: {os.environ.get('PORT', '10000')}")
print(f"  PYTHON_VERSION: {os.environ.get('PYTHON_VERSION', 'Not Set')}")

# Начинаем измерения
print_header("📊 Memory & Time Analysis")
print(f"{'Step':<50} | {'Time':>6} | {'Memory':>7} | {'Delta':>6}")
print_separator()

start_time = time.time()
start_memory = get_memory_mb()

print(f"  Baseline (script start)                          | {0:6.2f}s | {start_memory:7.1f} MB | +  0.0 MB")

# Шаг 1: Импорт os
step_start = time.time()
step_memory = start_memory
import os as _os_test
step_start, step_memory = log_step("Import: os", step_start, step_memory)

# Шаг 2: Импорт Flask
step_start_time = time.time()
step_start_memory = get_memory_mb()
from flask import Flask
step_start, step_memory = log_step("Import: Flask", step_start_time, step_start_memory)

# Шаг 3: Импорт SQLAlchemy
step_start_time = time.time()
step_start_memory = get_memory_mb()
from flask_sqlalchemy import SQLAlchemy
step_start, step_memory = log_step("Import: Flask-SQLAlchemy", step_start_time, step_start_memory)

# Шаг 4: Импорт Flask-Migrate
step_start_time = time.time()
step_start_memory = get_memory_mb()
from flask_migrate import Migrate
step_start, step_memory = log_step("Import: Flask-Migrate", step_start_time, step_start_memory)

# Шаг 5: Импорт requests
step_start_time = time.time()
step_start_memory = get_memory_mb()
import requests
step_start, step_memory = log_step("Import: requests", step_start_time, step_start_memory)

# Шаг 6: Импорт qbittorrentapi
step_start_time = time.time()
step_start_memory = get_memory_mb()
try:
    from qbittorrentapi import Client
    step_start, step_memory = log_step("Import: qbittorrentapi", step_start_time, step_start_memory)
except Exception as e:
    print(f"{Colors.RED}✗ Import qbittorrentapi FAILED: {e}{Colors.END}")
    step_memory = get_memory_mb()

# Шаг 7: Создание приложения
step_start_time = time.time()
step_start_memory = get_memory_mb()
print(f"\n{Colors.BOLD}Creating Flask Application...{Colors.END}")

try:
    from movie_lottery import create_app
    step_start, step_memory = log_step("Import: movie_lottery.create_app", step_start_time, step_start_memory)
    
    # Создание app
    step_start_time = time.time()
    step_start_memory = get_memory_mb()
    app = create_app()
    step_start, step_memory = log_step("Execute: create_app()", step_start_time, step_start_memory)
    
    # Тестирование app context
    step_start_time = time.time()
    step_start_memory = get_memory_mb()
    with app.app_context():
        from movie_lottery import db
        # Пробуем подключиться к БД
        try:
            db.engine.connect()
            step_start, step_memory = log_step("Database: Connection Test", step_start_time, step_start_memory)
        except Exception as e:
            print(f"{Colors.RED}✗ Database connection FAILED: {e}{Colors.END}")
            step_memory = get_memory_mb()
    
    # Импорт всех модулей
    step_start_time = time.time()
    step_start_memory = get_memory_mb()
    try:
        from movie_lottery import models
        step_start, step_memory = log_step("Import: movie_lottery.models", step_start_time, step_start_memory)
    except Exception as e:
        print(f"{Colors.RED}✗ Import models FAILED: {e}{Colors.END}")
    
    step_start_time = time.time()
    step_start_memory = get_memory_mb()
    try:
        from movie_lottery.routes import main_routes, api_routes
        step_start, step_memory = log_step("Import: movie_lottery.routes", step_start_time, step_start_memory)
    except Exception as e:
        print(f"{Colors.RED}✗ Import routes FAILED: {e}{Colors.END}")
    
    step_start_time = time.time()
    step_start_memory = get_memory_mb()
    try:
        from movie_lottery.utils import helpers, kinopoisk
        step_start, step_memory = log_step("Import: movie_lottery.utils", step_start_time, step_start_memory)
    except Exception as e:
        print(f"{Colors.RED}✗ Import utils FAILED: {e}{Colors.END}")

except Exception as e:
    print(f"\n{Colors.RED}{Colors.BOLD}✗ CRITICAL ERROR:{Colors.END} {e}")
    import traceback
    traceback.print_exc()

# Garbage collection
gc.collect()
memory_after_gc = get_memory_mb()

# Итоги
total_time = time.time() - start_time
total_memory = get_memory_mb()

print_header("📈 Final Statistics")
print(f"  Total Startup Time: {Colors.BOLD}{total_time:.2f} seconds{Colors.END}")
print(f"  Initial Memory: {start_memory:.1f} MB")
print(f"  Final Memory: {total_memory:.1f} MB")
print(f"  Memory Growth: {Colors.BOLD}+{total_memory - start_memory:.1f} MB{Colors.END}")
print(f"  After GC: {memory_after_gc:.1f} MB")

# Анализ
print_header("🔍 Analysis")

if total_time > 30:
    print(f"  {Colors.RED}⚠ CRITICAL:{Colors.END} Startup time exceeds 30 seconds!")
    print(f"     This will cause worker timeout on default gunicorn config.")
elif total_time > 15:
    print(f"  {Colors.YELLOW}⚠ WARNING:{Colors.END} Startup time is high ({total_time:.1f}s)")
    print(f"     May cause issues on slow servers.")
else:
    print(f"  {Colors.GREEN}✓ OK:{Colors.END} Startup time is acceptable ({total_time:.1f}s)")

if total_memory > 400:
    print(f"  {Colors.RED}⚠ CRITICAL:{Colors.END} Memory usage is too high ({total_memory:.0f} MB)")
    print(f"     Free tier (512 MB) may run out of memory!")
elif total_memory > 300:
    print(f"  {Colors.YELLOW}⚠ WARNING:{Colors.END} Memory usage is high ({total_memory:.0f} MB)")
    print(f"     Close to free tier limit.")
else:
    print(f"  {Colors.GREEN}✓ OK:{Colors.END} Memory usage is acceptable ({total_memory:.0f} MB)")

# Рекомендации
print_header("💡 Recommendations")

if total_time > 30:
    print(f"  • Increase gunicorn timeout to at least {int(total_time * 2)} seconds")
    print(f"  • Current config has timeout=300, make sure it's being loaded!")
    print(f"  • Check Render start command includes: --config gunicorn_config.py")

if total_memory > 350:
    print(f"  • Consider lazy importing heavy modules (qbittorrentapi, requests)")
    print(f"  • Disable Flask-Migrate on production")
    print(f"  • Consider upgrading to Starter plan (2GB RAM)")

if os.environ.get('DATABASE_URL'):
    print(f"  • Database URL is configured")
else:
    print(f"  {Colors.YELLOW}⚠{Colors.END} DATABASE_URL not set - using SQLite (slower)")

print_separator()
print(f"\n{Colors.BOLD}Diagnostic complete. Share this log to identify the issue.{Colors.END}\n")

