# Run API Locally (Windows PowerShell Version)
$ErrorActionPreference = "Stop"

# 0. Ensure we are in the project root
$ScriptDir = Split-Path $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path $ScriptDir -Parent

if (Test-Path "$ProjectRoot\src\main.py") {
    Write-Host "Changing working directory to project root: $ProjectRoot" -ForegroundColor Gray
    Set-Location $ProjectRoot
} else {
    Write-Error "Could not find src\main.py in project root ($ProjectRoot). Are you running this script from the correct location?"
}

Write-Host "🚀 STARTING API SERVER (Local Mode)" -ForegroundColor Cyan
Write-Host "=================================="

# 1. Set Environment Variables
# Connecting to localhost because ports are mapped in docker-compose
$env:DATABASE_URL = "postgresql://admin:changeme@localhost:5432/knowledge_base"
# Also set individual variables for compatibility
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_DB = "knowledge_base"
$env:POSTGRES_USER = "admin"
$env:POSTGRES_PASSWORD = "changeme"
$env:REDIS_HOST = "localhost"
$env:REDIS_PORT = "6379"
$env:REDIS_PASSWORD = ""
$env:ENVIRONMENT = "development"
$env:LOG_LEVEL = "info"
# Optional: Disable OpenTelemetry console exporter to reduce noise
$env:OTEL_CONSOLE_EXPORTER = "false"
# Optional: Ignore Python version check if running on 3.10 or 3.12
$env:IGNORE_PY_VERSION_CHECK = "1"

Write-Host "Configuration:" -ForegroundColor Gray
Write-Host "   DATABASE_URL: $env:DATABASE_URL"
Write-Host "   POSTGRES: $env:POSTGRES_USER@$env:POSTGRES_HOST`:$env:POSTGRES_PORT/$env:POSTGRES_DB"
Write-Host "   REDIS: $env:REDIS_HOST`:$env:REDIS_PORT"

# 2. Check Dependencies
Write-Host "Checking dependencies..." -ForegroundColor Gray
try {
    # Install critical dependencies if missing
    pip install marko bleach
    
    if (-not (Get-Command uvicorn -ErrorAction SilentlyContinue)) {
        Write-Host "Installing core dependencies..." -ForegroundColor Yellow
        pip install fastapi uvicorn redis asyncpg pydantic-settings prometheus-fastapi-instrumentator opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-asyncpg opentelemetry-instrumentation-redis opentelemetry-exporter-otlp apscheduler
    }
} catch {
    Write-Warning "Dependency check failed. Attempting to run anyway..."
}

# 3. Run Server
Write-Host "Launching Uvicorn..." -ForegroundColor Green
# Using --reload for development experience
# Using --host 127.0.0.1 for better Windows compatibility
# Using port 8001 to avoid conflicts (8000 is often busy)
uvicorn src.main:app --host 127.0.0.1 --port 8001 --reload

