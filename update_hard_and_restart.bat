@echo off
setlocal EnableExtensions
chcp 65001 >nul

REM === Всегда работаем из папки скрипта (важно для .env и docker-compose.yml) ===
cd /d "%~dp0"
echo [INFO] Папка проекта: %CD%

REM === Проверка наличия git-репозитория и origin ===
git rev-parse --is-inside-work-tree >nul 2>nul || (echo [GIT] Здесь нет git-репозитория. Останов. & goto :end)

for /f "usebackq tokens=*" %%i in (`git remote get-url origin 2^>nul`) do set ORIGIN_URL=%%i
if not defined ORIGIN_URL (echo [GIT] Не найден удаленный origin. Останов. & goto :end)
echo [GIT] origin=%ORIGIN_URL%

REM === Жёстко приводим к origin/main (все локальные правки будут потеряны) ===
echo [GIT] fetch...
git fetch --all || goto :fail_git
echo [GIT] reset --hard origin/main...
git reset --hard origin/main || goto :fail_git

REM Удалим незаконтролированные файлы/папки, НО сохраним игнорируемые (например .env)
echo [GIT] clean -fd (сохраняем .gitignore-файлы)...
git clean -fd || goto :fail_git

REM === Быстрый перезапуск Docker (пересоберёт ТОЛЬКО при необходимости) ===
set COMPOSE_DOCKER_CLI_BUILD=1
set DOCKER_BUILDKIT=1

echo [DOCKER] docker compose up -d --build
docker compose up -d --build || goto :fail_docker

echo.
echo [OK] Сервер обновлён и перезапущен. Состояние контейнеров:
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo [LOGS] Последние строки логов приложения:
docker logs --tail=80 movie_lottery_app
goto :end

:fail_git
echo [GIT] Ошибка при жёстком обновлении. Проверь подключение к GitHub и наличие ветки main.
goto :end

:fail_docker
echo [DOCKER] Ошибка при запуске Docker. Проверь Docker Desktop/службу и вывод выше.
goto :end

:end
endlocal
