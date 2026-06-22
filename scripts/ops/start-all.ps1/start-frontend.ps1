# Start Frontend Script
# Запускает Vite dev server на хосте

Write-Host "🚀 Starting 1C AI Stack Frontend..." -ForegroundColor Green

# Перейти в директорию frontend
Set-Location -Path "c:\1cAI\portal"

# Запустить Vite dev server
Write-Host "Starting Vite dev server..." -ForegroundColor Cyan
npm run dev
