#!/usr/bin/env bash
set -e

echo "[entrypoint] Waiting for DB at ${DB_HOST}:${DB_PORT}..."
until python -c "import socket,sys; s=socket.socket(); s.settimeout(1); 
import os; host=os.environ.get('DB_HOST','db'); port=int(os.environ.get('DB_PORT','5432'));
sys.exit(0 if not s.connect_ex((host,port)) else 1)"; do
  sleep 1
done
echo "[entrypoint] DB is up."

# Alembic: миграции (только если конфиг валиден)
if [ -f "migrations/alembic.ini" ] || [ -f "migrations/env.py" ]; then
  if [ -f "migrations/alembic.ini" ] && grep -q "^script_location\\s*=" migrations/alembic.ini; then
    echo "[entrypoint] Running Alembic migrations..."
    alembic -c migrations/alembic.ini upgrade head || alembic upgrade head || true
  else
    echo "[entrypoint] Alembic config is missing 'script_location' — skipping migrations."
  fi
fi


# Подбираем способ запуска приложения + даём максимум логов

echo "[entrypoint] Diagnosing Python import..."
python - <<'PY'
import importlib, traceback
try:
    m = importlib.import_module('movie_lottery')
    print("[diagnostic] import movie_lottery OK:", getattr(m, "__file__", "<no __file__>"))
    has_factory = hasattr(m, "create_app")
    print("[diagnostic] create_app found:", has_factory)
except Exception as e:
    print("[diagnostic] FAILED to import movie_lottery:", e)
    traceback.print_exc()
    raise
PY

echo "[entrypoint] Starting app..."

# 1) wsgi.py:app
if [ -f "wsgi.py" ]; then
  echo "[entrypoint] Using wsgi:app via gunicorn"
  exec gunicorn -b 0.0.0.0:8000 --access-logfile - --error-logfile - wsgi:app
fi

# 2) movie_lottery:create_app()
python - <<'PY' >/dev/null 2>&1
import importlib, sys
try:
    m = importlib.import_module('movie_lottery')
    sys.exit(0 if hasattr(m, 'create_app') else 1)
except Exception:
    sys.exit(1)
PY
if [ $? -eq 0 ]; then
  echo "[entrypoint] Using movie_lottery:create_app() via gunicorn"
  exec gunicorn -b 0.0.0.0:8000 --access-logfile - --error-logfile - 'movie_lottery:create_app()'
fi

# 3) app.py:app
if [ -f "app.py" ]; then
  echo "[entrypoint] Using app:app via gunicorn"
  exec gunicorn -b 0.0.0.0:8000 --access-logfile - --error-logfile - app:app
fi

# 4) Фолбэк — flask run (чтобы увидеть полную трассу в логах)
if [ -d "movie_lottery" ]; then
  export FLASK_APP=movie_lottery
fi
export FLASK_ENV=${FLASK_ENV:-production}
echo "[entrypoint] Falling back to: python -m flask run"
exec python -m flask run --host=0.0.0.0 --port=8000
