@echo off
setlocal EnableExtensions

REM === Always work from script directory ===
cd /d "%~dp0"
echo [INFO] Project directory: %CD%
echo.

REM === Fast Docker build (rebuilds only changed layers) ===
set COMPOSE_DOCKER_CLI_BUILD=1
set DOCKER_BUILDKIT=1

REM === Detect docker compose command ===
set "DC="
docker compose version >nul 2>&1
if errorlevel 1 (
    docker-compose --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Neither "docker compose" nor "docker-compose" found.
        pause
        exit /b 1
    )
    set "DC=docker-compose"
)
if "%DC%"=="" set "DC=docker compose"

REM === Check argument for full rebuild ===
if "%1"=="--no-cache" (
    echo [DOCKER] Full rebuild mode without cache
)

echo [DOCKER] Stopping containers...
%DC% down
if errorlevel 1 (
    echo [WARNING] Some containers may not be running
)

echo [DOCKER] Building images and starting containers...
if "%1"=="--no-cache" (
    %DC% build --no-cache
    if errorlevel 1 (
        echo [DOCKER] Build failed.
        pause
        exit /b 1
    )
    %DC% up -d --force-recreate
) else (
    %DC% up -d --build --force-recreate
)
if errorlevel 1 (
    echo [DOCKER] Compose failed.
    pause
    exit /b 1
)

echo.
echo [OK] Containers status:
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo [LOGS] Application logs (last 80 lines):
docker logs --tail=80 movie_lottery_app

echo.
echo ========================================
echo [DONE] Update completed successfully!
echo ========================================
pause

endlocal
