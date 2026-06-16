# 1С:Рентген — one-command launch (backend + portal). No Docker, no Neo4j.
#
#   powershell -ExecutionPolicy Bypass -File scripts\start_rentgen.ps1
#
# Builds the SQLite call-graph/quality store on first run (~30s), then starts
# the FastAPI backend (:8000) and the React portal (:3000) if not already up.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = "C:\Python311\python.exe"          # bundled .venv is broken; use system 3.11
$env:IGNORE_PY_VERSION_CHECK = "1"

function Up($p) { [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) }

# 1) Build the store if missing (data/rentgen.db from callgraph NDJSON + scores.json)
$db = Join-Path $root "data\rentgen.db"
if (-not (Test-Path $db)) {
    Write-Host "[1/3] Building Рентген store (one-time, ~30s)..." -ForegroundColor Cyan
    & $py (Join-Path $root "tools\rentgen\build_store.py")
} else {
    Write-Host "[1/3] Store present: $db" -ForegroundColor DarkGray
}

# 2) Backend on :8000
if (-not (Up 8000)) {
    Write-Host "[2/3] Starting backend  -> http://127.0.0.1:8000" -ForegroundColor Cyan
    Start-Process -FilePath $py `
        -ArgumentList "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $root -WindowStyle Hidden
} else {
    Write-Host "[2/3] Backend already on :8000" -ForegroundColor DarkGray
}

# 3) Portal on :3000 (Vite proxies /api -> :8000)
if (-not (Up 3000)) {
    Write-Host "[3/3] Starting portal   -> http://localhost:3000" -ForegroundColor Cyan
    Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" `
        -WorkingDirectory (Join-Path $root "portal") -WindowStyle Hidden
} else {
    Write-Host "[3/3] Portal already on :3000" -ForegroundColor DarkGray
}

Start-Sleep -Seconds 6
Write-Host ""
Write-Host "1С:Рентген is up:" -ForegroundColor Green
Write-Host "  Risk hotspots :  http://localhost:3000/quality"
Write-Host "  Call graph    :  http://localhost:3000/rentgen"
Write-Host "  API docs      :  http://127.0.0.1:8000/docs"
Write-Host "  (Dev login: open the portal, click 'Dev Mode (skip auth)')" -ForegroundColor DarkGray
