# Stop All Services Script
# Останавливает все сервисы

Write-Host "🛑 Stopping 1C AI Stack..." -ForegroundColor Red

# Остановить Docker контейнеры
Write-Host "Stopping Docker containers..." -ForegroundColor Yellow
Set-Location -Path "c:\1cAI"
docker-compose down

Write-Host "`n✅ All Docker services stopped!" -ForegroundColor Green
Write-Host "`n⚠️  Backend and Frontend processes are still running in separate windows." -ForegroundColor Yellow
Write-Host "Close those PowerShell windows manually or press Ctrl+C in them." -ForegroundColor Gray

Read-Host "`nPress Enter to close"
