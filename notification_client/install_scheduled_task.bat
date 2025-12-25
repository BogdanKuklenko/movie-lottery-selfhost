@echo off
:: Установка Windows Scheduled Task для автозапуска клиента уведомлений
:: ТРЕБУЮТСЯ ПРАВА АДМИНИСТРАТОРА!

echo ========================================
echo Movie Lottery - Установка автозапуска
echo ========================================
echo.

:: Проверяем права администратора
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ОШИБКА: Запустите этот скрипт от имени Администратора!
    echo Правый клик на файле - "Запуск от имени администратора"
    pause
    exit /b 1
)

cd /d "%~dp0"

echo Импорт задачи в Планировщик Windows...
schtasks /create /tn "MovieLotteryNotifications" /xml "MovieLotteryNotifications.xml" /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo УСПЕХ! Задача создана.
    echo.
    echo Клиент уведомлений будет:
    echo - Запускаться при старте Windows
    echo - Проверяться каждые 5 минут
    echo - Автоматически перезапускаться при падении
    echo.
    echo Для проверки откройте: taskschd.msc
) else (
    echo ОШИБКА при создании задачи!
)

pause

