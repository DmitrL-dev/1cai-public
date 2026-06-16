# Start Backend Script
# Запускает FastAPI backend на хосте

Write-Host "🚀 Starting 1C AI Stack Backend..." -ForegroundColor Green

# Перейти в директорию проекта
Set-Location -Path "c:\1cAI"

# Активировать venv
Write-Host "Activating Python venv..." -ForegroundColor Cyan
& .\venv\Scripts\Activate.ps1

# Запустить backend
Write-Host "Starting FastAPI server on http://localhost:8000..." -ForegroundColor Cyan
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
