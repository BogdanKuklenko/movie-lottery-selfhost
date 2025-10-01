@echo off
chcp 65001 > nul

:: ==================================================
::  ПОЛУЧИТЬ ПОСЛЕДНИЕ ИЗМЕНЕНИЯ С GITHUB
:: ==================================================

cd /d "%~dp0"

for /f "tokens=*" %%i in ('git branch --show-current') do set branch=%%i

echo.
echo ══════════════════════════════════════
echo   ОБНОВЛЕНИЕ ИЗ GITHUB
echo ══════════════════════════════════════
echo.
echo Ветка: %branch%
echo.

git pull origin %branch%

if errorlevel 1 (
    echo.
    echo [X] Ошибка при получении изменений!
    pause
    exit /b 1
) else (
    echo.
    echo [✓] Изменения успешно получены!
    echo.
    pause
)

