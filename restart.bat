@echo off
setlocal EnableExtensions
chcp 65001 >nul

REM === Всегда работаем из папки скрипта ===
cd /d "%~dp0"
echo [INFO] Папка проекта: %CD%
echo.

REM === Быстрый подъём Docker (пересоберёт только изменившиеся слои) ===
set COMPOSE_DOCKER_CLI_BUILD=1
set DOCKER_BUILDKIT=1

REM === Определяем команду docker compose ===
set "DC="
docker compose version >nul 2>&1
if errorlevel 1 (
    docker-compose --version >nul 2>&1
    if errorlevel 1 (
        echo [DOCKER] Neither "docker compose" nor "docker-compose" found.
        pause
        exit /b 1
    )
    set "DC=docker-compose"
)
if "%DC%"=="" set "DC=docker compose"

echo [DOCKER] %DC% up -d --build
%DC% up -d --build
if errorlevel 1 (
    echo [DOCKER] Compose failed.
    pause
    exit /b 1
)

echo.
echo [OK] Контейнеры:
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo [LOGS] Последние строки логов приложения:
docker logs --tail=80 movie_lottery_app

endlocal

