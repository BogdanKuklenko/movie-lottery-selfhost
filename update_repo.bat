@echo off
setlocal EnableExtensions

rem === КУДА ПУШИМ ===
set "REPO_URL=https://github.com/BogdanKuklenko/movie-lottery-selfhost.git"

rem Работать из папки, где лежит батник
cd /d "%~dp0"

rem --- Git установлен? ---
git --version >nul 2>&1
if errorlevel 1 (
  echo [GIT] Git not found. Install: https://git-scm.com/download/win
  goto :end
)

rem --- init, если не репозиторий ---
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  git init
  git branch -M main
)

rem --- текущий origin (если есть) ---
set "ORIGIN_URL="
for /f "delims=" %%R in ('git remote get-url origin 2^>nul') do set "ORIGIN_URL=%%R"
if defined ORIGIN_URL echo [GIT] origin=%ORIGIN_URL%

rem --- защита: НЕ пушим в старый репозиторий ---
set "CHK=%ORIGIN_URL:movie-lottery-refactored.git=%"
if not "%CHK%"=="%ORIGIN_URL%" (
  echo [GIT] ABORT: origin points to movie-lottery-refactored.git
  goto :end
)

rem --- привязываем/чинем origin на selfhost ---
if not defined ORIGIN_URL git remote add origin "%REPO_URL%"
set "CHK2=%ORIGIN_URL:movie-lottery-selfhost.git=%"
if "%CHK2%"=="%ORIGIN_URL%" git remote set-url origin "%REPO_URL%"

rem --- убеждаемся, что мы на main ---
set "CURBR="
for /f "delims=" %%B in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "CURBR=%%B"
if not defined CURBR git checkout -B main
if /I not "%CURBR%"=="main" git checkout -B main

rem --- базовые игноры ---
if not exist ".gitignore" (
  >.gitignore echo .env
  >>.gitignore echo .env.*
  >>.gitignore echo __pycache__/
  >>.gitignore echo *.pyc
  >>.gitignore echo .vscode/
  >>.gitignore echo .idea/
  >>.gitignore echo .DS_Store
  >>.gitignore echo venv/
  >>.gitignore echo .venv/
  >>.gitignore echo *.log
)
if not exist ".gitattributes" (
  >.gitattributes echo *.sh text eol=lf
)

rem --- сообщение коммита ---
set "MSG=%*"
if "%MSG%"=="" set "MSG=update"

rem --- add/commit ---
git add -A
git diff --cached --quiet
if %errorlevel%==0 (
  echo [GIT] No changes to commit.
)
if not %errorlevel%==0 (
  git commit -m "%MSG%"
)

rem --- push ---
git rev-parse --abbrev-ref --symbolic-full-name @{u} >nul 2>&1
if errorlevel 1 (
  echo [GIT] push -u origin main
  git push -u origin main
)
if not errorlevel 1 (
  echo [GIT] push
  git push
)

rem =======================
rem === DOCKER DEPLOY  ===
rem =======================
echo [DOCKER] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
  echo [DOCKER] Docker Desktop not found or not in PATH. Skipping.
  goto :end
)

set "DC="
docker compose version >nul 2>&1
if errorlevel 1 (
  docker-compose --version >nul 2>&1
  if errorlevel 1 (
    echo [DOCKER] Neither "docker compose" nor "docker-compose" found. Skipping.
    goto :end
  )
  set "DC=docker-compose"
)
if "%DC%"=="" set "DC=docker compose"

echo [DOCKER] %DC% up -d --build
%DC% up -d --build
if errorlevel 1 (
  echo [DOCKER] Compose failed.
  goto :end
)

echo [DOCKER] Containers:
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo [DOCKER] App logs (tail 50):
docker logs --tail=50 movie_lottery_app

:end
echo [DONE]
endlocal
