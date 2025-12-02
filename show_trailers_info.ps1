# Скрипт для просмотра информации о трейлерах в Docker контейнере

Write-Host "=== Информация о трейлерах ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "Общий размер и количество файлов:" -ForegroundColor Yellow
docker exec movie_lottery_app sh -c "du -sh /app/instance/media/trailers && echo 'Количество файлов:' && ls -1 /app/instance/media/trailers/*.mp4 /app/instance/media/trailers/*.webm 2>/dev/null | wc -l"

Write-Host ""
Write-Host "Список всех трейлеров:" -ForegroundColor Yellow
docker exec movie_lottery_app ls -lh /app/instance/media/trailers/*.mp4 /app/instance/media/trailers/*.webm 2>/dev/null | Select-Object -Skip 1

Write-Host ""
Write-Host "Путь в контейнере: /app/instance/media/trailers/" -ForegroundColor Green
Write-Host "Docker volume: movie-lottery-refactored_media_data" -ForegroundColor Green





