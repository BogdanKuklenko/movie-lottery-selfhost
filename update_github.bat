@echo off
chcp 65001 > nul

:: ==================================================
::  УЛУЧШЕННЫЙ БАТНИК ДЛЯ ОБНОВЛЕНИЯ GITHUB
::  Версия: 3.0
::  Дата: 01.10.2025
:: ==================================================

cd /d "%~dp0"

echo.
echo ╔══════════════════════════════════════════════════╗
echo ║      АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ GITHUB            ║
echo ╚══════════════════════════════════════════════════╝
echo.

:: Проверяем текущую ветку
for /f "tokens=*" %%i in ('git branch --show-current') do set current_branch=%%i
echo [i] Текущая ветка: %current_branch%
echo.

:: Проверяем статус репозитория
echo [1/6] Проверяем состояние репозитория...
git status

echo.
echo ─────────────────────────────────────────────────
echo.

:: Спрашиваем пользователя, продолжить ли
set /p continue="Продолжить обновление? (Y/N): "
if /i not "%continue%"=="Y" (
    echo.
    echo [!] Обновление отменено пользователем.
    echo.
    pause
    exit /b
)

echo.
echo [2/6] Добавляем все изменения (git add .)...
git add .

if errorlevel 1 (
    echo.
    echo [X] ОШИБКА при добавлении файлов!
    pause
    exit /b 1
)

echo.
echo ─────────────────────────────────────────────────
echo.

:: Проверяем, есть ли что коммитить
git diff --cached --quiet
if errorlevel 1 (
    echo [3/6] Создаем коммит...
    echo.
    
    :: Проверяем файл с сообщением коммита
    if exist "commit_message.txt" (
        set /p commit_message=<commit_message.txt
        
        if not "!commit_message!"=="" (
            echo Используем сообщение из commit_message.txt: !commit_message!
            git commit -m "!commit_message!"
        ) else (
            set /p commit_message="Введите сообщение коммита: "
            git commit -m "!commit_message!"
        )
    ) else (
        set /p commit_message="Введите сообщение коммита: "
        git commit -m "!commit_message!"
    )
    
    if errorlevel 1 (
        echo.
        echo [X] ОШИБКА при создании коммита!
        pause
        exit /b 1
    )
) else (
    echo [3/6] Нет изменений для коммита.
)

echo.
echo ─────────────────────────────────────────────────
echo.

:: Подтягиваем изменения с сервера
echo [4/6] Подтягиваем изменения с GitHub (git pull)...
git pull origin %current_branch%

if errorlevel 1 (
    echo.
    echo [!] ВНИМАНИЕ: Возможен конфликт при pull!
    echo Проверьте конфликты и повторите обновление.
    pause
    exit /b 1
)

echo.
echo ─────────────────────────────────────────────────
echo.

:: Отправляем изменения на GitHub
echo [5/6] Отправляем изменения на GitHub (git push)...
git push origin %current_branch%

if errorlevel 1 (
    echo.
    echo [X] ОШИБКА при отправке на GitHub!
    echo Проверьте подключение к интернету и права доступа.
    pause
    exit /b 1
)

echo.
echo ─────────────────────────────────────────────────
echo.

:: Показываем финальный статус
echo [6/6] Проверяем финальный статус...
git status

echo.
echo ╔══════════════════════════════════════════════════╗
echo ║         ✓ ОБНОВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО!         ║
echo ╚══════════════════════════════════════════════════╝
echo.
echo Ветка: %current_branch%
echo Репозиторий: https://github.com/BogdanKuklenko/movie-lottery-refactored
echo.
pause

