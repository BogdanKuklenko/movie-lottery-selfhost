@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem === НАСТРОЙКА: укажи URL своего репозитория (HTTPS) ===
set "REPO_URL=https://github.com/USER/movie-lottery-selfhost.git"

rem === Рабочая папка = папка, где лежит этот батник ===
cd /d "%~dp0"

rem --- проверка, установлен ли git ---
git --version >nul 2>&1 || (
  echo [ERROR] Git не найден. Установи Git for Windows и перезапусти.
  exit /b 1
)

rem --- инициализация репозитория, если нужно ---
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo [INIT] git init
  git init
  git branch -M main
)

rem --- .gitignore / .gitattributes создадим, если их нет ---
if not exist ".gitignore" (
  echo .env>>.gitignore
  echo .env.*>>.gitignore
  echo __pycache__/>>.gitignore
  echo *.pyc>>.gitignore
  echo .vscode/>>.gitignore
  echo .idea/>>.gitignore
  echo .DS_Store>>.gitignore
  echo venv/>>.gitignore
  echo .venv/>>.gitignore
  echo *.log>>.gitignore
)
if not exist ".gitattributes" (
  echo *.sh text eol=lf>.gitattributes
)

rem --- привяжем origin, если не привязан ---
git remote get-url origin >nul 2>&1
if errorlevel 1 (
  if "%REPO_URL%"=="" (
    echo [ERROR] Не задан REPO_URL. Открой update_repo.bat и пропиши адрес репозитория.
    exit /b 1
  )
  echo [INIT] git remote add origin %REPO_URL%
  git remote add origin "%REPO_URL%"
)

rem --- коммит ---
set "MSG=%*"
if "%MSG%"=="" (
  for /f "tokens=1-4 delims=.:/ " %%a in ("%date% %time%") do set "MSG=update %%a %%b %%c"
)
echo [COMMIT] %MSG%
git add -A
git commit -m "%MSG%" 2>nul
if errorlevel 1 (
  echo [INFO] Нет изменений для коммита.
) else (
  echo [PUSH] origin main
)

rem --- первый push может требовать -u ---
git rev-parse --abbrev-ref --symbolic-full-name @{u} >nul 2>&1
if errorlevel 1 (
  git push -u origin main
) else (
  git push
)

echo [DONE]
endlocal
