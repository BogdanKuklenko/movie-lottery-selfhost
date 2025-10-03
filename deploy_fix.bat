@echo off
echo ========================================
echo Развертывание исправления базы данных
echo ========================================
echo.

echo Шаг 1: Добавление файлов в Git...
git add start.sh RENDER_DEPLOYMENT.md deploy_fix.bat movie_lottery/__init__.py
echo.

echo Шаг 2: Создание коммита...
git commit -m "Fix: Add database migration script for Render deployment"
echo.

echo Шаг 3: Отправка на GitHub...
git push origin codex
echo.

echo ========================================
echo Готово!
echo ========================================
echo.
echo Следующие шаги:
echo 1. Зайдите на https://render.com
echo 2. Откройте ваш сервис movie-lottery
echo 3. Перейдите в Settings
echo 4. Измените Start Command на: bash start.sh
echo 5. Сохраните изменения
echo 6. Render автоматически перезапустит сервис
echo.
echo После перезапуска проверьте логи - должно появиться:
echo "Database migrations completed successfully"
echo.
pause

