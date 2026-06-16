# Start All Services Script
# Запускает всю инфраструктуру: Docker + Backend + Frontend

Write-Host "🚀 Starting 1C AI Stack - Full Stack..." -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Gray

# Шаг 1: Запустить Docker инфраструктуру
Write-Host "`n📦 Step 1: Starting Docker infrastructure..." -ForegroundColor Yellow
Set-Location -Path "c:\1cAI"

Write-Host "Starting PostgreSQL, Redis, Qdrant, Neo4j..." -ForegroundColor Cyan
docker-compose up -d postgres redis qdrant neo4j

# Подождать пока БД запустится
Write-Host "Waiting for databases to be ready..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

# Шаг 2: Запустить Backend в новом окне
Write-Host "`n🐍 Step 2: Starting Backend (Python/FastAPI)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-File", "c:\1cAI\start-backend.ps1"

# Подождать пока backend запустится
Write-Host "Waiting for backend to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 3

# Шаг 3: Запустить Frontend в новом окне
Write-Host "`n⚛️  Step 3: Starting Frontend (React/Vite)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-File", "c:\1cAI\start-frontend.ps1"

# Итоги
Write-Host "`n" + "=" * 60 -ForegroundColor Gray
Write-Host "✅ All services started!" -ForegroundColor Green
Write-Host "`nServices:" -ForegroundColor White
Write-Host "  🐘 PostgreSQL:  " -NoNewline -ForegroundColor Cyan
Write-Host "localhost:5432" -ForegroundColor White
Write-Host "  📮 Redis:       " -NoNewline -ForegroundColor Cyan
Write-Host "localhost:6379" -ForegroundColor White
Write-Host "  🔍 Qdrant:      " -NoNewline -ForegroundColor Cyan
Write-Host "localhost:6333" -ForegroundColor White
Write-Host "  🕸️  Neo4j:       " -NoNewline -ForegroundColor Cyan
Write-Host "localhost:7687" -ForegroundColor White
Write-Host "`n  🐍 Backend:     " -NoNewline -ForegroundColor Yellow
Write-Host "http://localhost:8000" -ForegroundColor White
Write-Host "  📚 Swagger UI:  " -NoNewline -ForegroundColor Yellow
Write-Host "http://localhost:8000/docs" -ForegroundColor White
Write-Host "`n  ⚛️  Frontend:    " -NoNewline -ForegroundColor Magenta
Write-Host "http://localhost:3001" -ForegroundColor White

Write-Host "`n" + "=" * 60 -ForegroundColor Gray
Write-Host "Press Ctrl+C to stop this script (services will continue running)" -ForegroundColor Gray
Write-Host "To stop all services: docker-compose down" -ForegroundColor Gray

# Держать окно открытым
Read-Host "`nPress Enter to close this window"
