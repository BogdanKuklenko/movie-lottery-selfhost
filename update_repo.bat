@echo off
setlocal EnableExtensions

rem === КУДА ПУШИМ ===
set "REPO_URL=https://github.com/BogdanKuklenko/movie-lottery-selfhost.git"

rem Работать из папки, где лежит батник
cd /d "%~dp0"

rem --- Git установлен? ---
git --version >nul 2>&1
if errorlevel 1 (
  echo Git not found. Install: https://git-scm.com/download/win
  exit /b 1
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
if defined ORIGIN_URL echo origin=%ORIGIN_URL%

rem --- защита: НЕ пушим в старый репозиторий ---
set "CHK=%ORIGIN_URL:movie-lottery-refactored.git=%"
if not "%CHK%"=="%ORIGIN_URL%" (
  echo ABORT: origin points to movie-lottery-refactored.git
  exit /b 1
)

rem --- привязываем/чинем origin на selfhost ---
if not defined ORIGIN_URL (
  git remote add origin "%REPO_URL%"
) else (
  set "CHK2=%ORIGIN_URL:movie-lottery-selfhost.git=%"
  if "%CHK2%"=="%ORIGIN_URL%" git remote set-url origin "%REPO_URL%"
)

rem --- убеждаемся, что мы на main ---
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

rem --- add/commit/push ---
git add -A
git diff --cached --quiet && (
  echo No changes to commit.
) || (
  git commit -m "%MSG%"
)

git rev-parse --abbrev-ref --symbolic-full-name @{u} >nul 2>&1
if errorlevel 1 (
  git push -u origin main
) else (
  git push
)

echo Done.
endlocal
