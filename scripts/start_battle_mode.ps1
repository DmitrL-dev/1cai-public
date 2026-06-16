# Start Battle Mode (Windows PowerShell Version)
$ErrorActionPreference = "Stop"

# 0. Ensure we are in the project root
$ScriptDir = Split-Path $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path $ScriptDir -Parent

if (Test-Path "$ProjectRoot\docker-compose.mvp.yml") {
    Write-Host "Changing working directory to project root: $ProjectRoot" -ForegroundColor Gray
    Set-Location $ProjectRoot
} else {
    Write-Error "Could not find docker-compose.mvp.yml in project root ($ProjectRoot). Are you running this script from the correct location?"
}

Write-Host "STARTING BATTLE MODE (Windows Infrastructure)" -ForegroundColor Cyan
Write-Host "============================================="

# 1. Start Infrastructure (Safe Mode - preserves data)
Write-Host "Ensuring PostgreSQL and Redis are running..." -ForegroundColor Green
docker compose -f docker-compose.mvp.yml up -d postgres redis

# 2. Wait for PostgreSQL
Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Yellow
$max_retries = 30
$retry_count = 0
$db_ready = $false

while (-not $db_ready -and $retry_count -lt $max_retries) {
    try {
        docker exec 1c-ai-postgres pg_isready -U admin | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $db_ready = $true
        } else {
            throw "Not ready"
        }
    }
    catch {
        Write-Host "   ...waiting for database..." -ForegroundColor DarkGray
        Start-Sleep -Seconds 2
        $retry_count++
    }
}

if (-not $db_ready) {
    Write-Error "Database failed to start within 60 seconds."
}

Write-Host "Database is up!" -ForegroundColor Green

# 3. Apply Schema (if missing)
Write-Host "Verifying/Applying Schema..." -ForegroundColor Green
try {
    # Check if table tenants exists
    $check_table = docker exec 1c-ai-postgres psql -U admin -d knowledge_base -tAc "SELECT to_regclass('public.tenants');"
    
    if ([string]::IsNullOrWhiteSpace($check_table.Trim())) {
        Write-Host "   Schema missing. Applying db/init/01_schema.sql..." -ForegroundColor Yellow
        # Read schema file content
        $schema_content = Get-Content "db/init/01_schema.sql" -Raw
        # Apply via docker exec (passing content via stdin is tricky in PS to Docker, so we copy file)
        
        docker cp db/init/01_schema.sql 1c-ai-postgres:/tmp/schema.sql
        docker exec 1c-ai-postgres psql -U admin -d knowledge_base -f /tmp/schema.sql
        Write-Host "   ✅ Schema applied successfully." -ForegroundColor Green
    } else {
        Write-Host "   ✅ Schema already exists." -ForegroundColor Green
    }
} catch {
    Write-Error "Failed to apply schema: $_"
}

# 4. Seed Data
Write-Host "Seeding demo data..." -ForegroundColor Green

# Check for Python
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "   Running seeder via local Python..." -ForegroundColor Gray
    
    # Set env var for the session
    $env:DATABASE_URL = "postgresql://admin:changeme@localhost:5432/knowledge_base"
    
    # Try installing asyncpg if missing (ignoring errors if pip fails)
    try {
        pip install asyncpg 2>$null
    } catch {}

    python scripts/seed_demo_data.py
} else {
    Write-Host "Python not found on host. Trying to run seeder inside Docker..." -ForegroundColor Yellow
    docker run --rm --network 1c-ai-network `
        -v ${PWD}:/app `
        -w /app `
        -e DATABASE_URL="postgresql://admin:changeme@postgres:5432/knowledge_base" `
        python:3.11-slim `
        bash -c "pip install asyncpg; python scripts/seed_demo_data.py"
}

Write-Host "============================================="
Write-Host "BATTLE MODE READY!" -ForegroundColor Cyan
Write-Host "   - Database: localhost:5432 (knowledge_base)"
Write-Host "   - Redis: localhost:6379"
Write-Host "   - Data: Seeded with realistic demo content"
