@echo off
chcp 65001 > nul

:: ==================================================
::  БЫСТРАЯ ОТПРАВКА НА GITHUB (Quick Push)
::  Использование: quick_push.bat "Ваше сообщение"
:: ==================================================

cd /d "%~dp0"

:: Получаем сообщение коммита
if "%~1"=="" (
    echo.
    echo ИСПОЛЬЗОВАНИЕ: quick_push.bat "Ваше сообщение коммита"
    echo.
    echo ПРИМЕР: quick_push.bat "Исправил баги"
    echo.
    pause
    exit /b 1
)

set commit_msg=%~1

:: Получаем текущую ветку
for /f "tokens=*" %%i in ('git branch --show-current') do set branch=%%i

echo.
echo ══════════════════════════════════════
echo   БЫСТРАЯ ОТПРАВКА НА GITHUB
echo ══════════════════════════════════════
echo.
echo Ветка: %branch%
echo Сообщение: %commit_msg%
echo.

:: Добавляем, коммитим и пушим одной командой
git add . && git commit -m "%commit_msg%" && git push origin %branch%

if errorlevel 1 (
    echo.
    echo [X] Произошла ошибка!
    pause
    exit /b 1
) else (
    echo.
    echo [✓] Успешно отправлено на GitHub!
    echo.
    timeout /t 2 >nul
)

