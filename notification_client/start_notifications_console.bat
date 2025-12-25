@echo off
:: Запуск клиента уведомлений Movie Lottery (с консолью для отладки)

cd /d "%~dp0"

:: Проверяем наличие Python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python не найден! Установите Python и добавьте в PATH.
    pause
    exit /b 1
)

:: Проверяем зависимости
python -c "import socketio" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Установка зависимостей...
    pip install -r requirements.txt
)

:: Запускаем напрямую notification_client.py (без ожидания Docker)
echo Запуск клиента уведомлений...
python notification_client.py --server http://localhost:8888
pause



