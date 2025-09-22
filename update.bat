@echo off
chcp 65001 > nul

:: --- Батник для автоматического обновления репозитория GitHub v2 ---

:: Переходим в папку, где лежит сам батник
cd /d "%~dp0"

echo.
echo ==================================================
echo         АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ GITHUB
echo ==================================================
echo.

:: Проверяем, существует ли файл с комментарием
if not exist "commit_message.txt" (
    echo ОШИБКА: Файл 'commit_message.txt' не найден!
    echo Создайте его и напишите внутри комментарий к изменениям.
    pause
    exit
)

:: Читаем комментарий из файла 'commit_message.txt'
set /p commit_message=<commit_message.txt

:: Проверяем, не пустой ли комментарий
if "%commit_message%"=="" (
    echo.
    echo ОШИБКА: Комментарий в файле 'commit_message.txt' не может быть пустым!
    echo Обновление отменено.
    echo.
    pause
    exit
)

echo Комментарий для коммита: %commit_message%
echo.
echo --- 1. Добавляю все измененные файлы (git add .)...
git add .

echo.
echo --- 2. Сохраняю изменения (git commit)...
git commit -m "%commit_message%"

echo.
echo --- 3. Загружаю на GitHub (git push)...
git push

echo.
echo ==================================================
echo          ОБНОВЛЕНИЕ ЗАВЕРШЕНО!
echo ==================================================
echo.
pause