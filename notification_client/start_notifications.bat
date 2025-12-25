@echo off
:: Запуск клиента уведомлений Movie Lottery
:: Можно добавить в автозагрузку Windows: shell:startup

:: Переходим в папку скрипта
cd /d "F:\Сайт опрос\movie-lottery-refactored\notification_client"

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

:: Запускаем скрипт автозапуска (следит за Docker)
echo Запуск клиента уведомлений...
pythonw start_with_docker.py
