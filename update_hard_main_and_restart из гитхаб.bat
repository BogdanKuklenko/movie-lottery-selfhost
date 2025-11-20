@echo off
setlocal EnableExtensions
chcp 65001 >nul

REM === Всегда работаем из папки скрипта (важно для .env и docker-compose.yml) ===
cd /d "%~dp0"
echo [INFO] Папка проекта: %CD%

REM === Жёстко обновляем только отслеживаемые файлы с origin/main ===
echo [GIT] fetch origin main ...
git fetch origin main

echo [GIT] reset --hard origin/main ...
git reset --hard origin/main

REM ВАЖНО:
REM - reset --hard перезапишет ИЗМЕНЁННЫЕ ОТСЛЕЖИВАЕМЫЕ файлы (жёстко).
REM - НЕ будет удалять неотслеживаемые файлы/папки (того, чего нет в репозитории).
REM - Мы НЕ вызываем 'git clean', чтобы ничего лишнего не удалялось.

REM === Быстрый подъём Docker (пересоберёт только изменившиеся слои) ===
set COMPOSE_DOCKER_CLI_BUILD=1
set DOCKER_BUILDKIT=1

echo [DOCKER] docker compose up -d --build
docker compose up -d --build

echo.
echo [OK] Контейнеры:
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo [LOGS] Последние строки логов приложения:
docker logs --tail=80 movie_lottery_app

endlocal
