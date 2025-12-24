# Скрипт для копирования трейлеров из Docker контейнера на локальный компьютер

$localDir = ".\instance\media\trailers"
$containerPath = "/app/instance/media/trailers"

# Создаём локальную директорию, если её нет
if (-not (Test-Path $localDir)) {
    New-Item -ItemType Directory -Path $localDir -Force | Out-Null
    Write-Host "Создана директория: $localDir" -ForegroundColor Green
}

Write-Host "Копирование трейлеров из Docker контейнера..." -ForegroundColor Yellow

# Копируем все файлы трейлеров
docker cp movie_lottery_app:$containerPath $localDir

Write-Host "Готово! Трейлеры скопированы в: $localDir" -ForegroundColor Green
Write-Host ""
Write-Host "Файлы:" -ForegroundColor Cyan
Get-ChildItem $localDir -Filter "*.mp4" | Select-Object Name, @{Name="Размер (MB)";Expression={[math]::Round($_.Length/1MB, 2)}} | Format-Table -AutoSize
























