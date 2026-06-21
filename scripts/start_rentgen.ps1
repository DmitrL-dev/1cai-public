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

if (-not $env:ENVIRONMENT) { $env:ENVIRONMENT = "development" }
if (-not $env:APP_ENV) { $env:APP_ENV = $env:ENVIRONMENT }
if (-not $env:JWT_SECRET) {
    $env:JWT_SECRET = "rentgen-local-dev-secret-change-for-production-2026-06-18"
}
if (-not $env:JWT_SECRET_KEY) { $env:JWT_SECRET_KEY = $env:JWT_SECRET }

function Up($p) { [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) }
function PortCommandLine($p) {
    $conn = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $conn) { return "" }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" -ErrorAction SilentlyContinue
    if ($proc) { return [string]$proc.CommandLine }
    return ""
}
function FreePort($start) {
    $p = $start
    while (Up $p) { $p += 1 }
    return $p
}
function FindPortalPort($from, $to) {
    $portalPath = [regex]::Escape((Join-Path $root "portal"))
    foreach ($p in $from..$to) {
        if (-not (Up $p)) { continue }
        $cmd = PortCommandLine $p
        if (($cmd -match "vite") -and ($cmd -match $portalPath)) {
            return $p
        }
    }
    return $null
}

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

# 3) Portal on :3000, or the next free port if :3000 is occupied by another app.
$portalPort = FindPortalPort 3000 3010
$portalAlready = $null -ne $portalPort
if (-not $portalAlready) {
    $portalPort = 3000
    if (Up 3000) {
        $portalPort = FreePort 3001
        Write-Host "[3/3] :3000 is busy; using portal -> http://localhost:$portalPort" -ForegroundColor Cyan
    }
    if (-not (Up $portalPort)) {
        Write-Host "[3/3] Starting portal   -> http://localhost:$portalPort" -ForegroundColor Cyan
        Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev", "--", "--port", "$portalPort", "--strictPort" `
            -WorkingDirectory (Join-Path $root "portal") -WindowStyle Hidden
    } else {
        Write-Host "[3/3] Portal already on :$portalPort" -ForegroundColor DarkGray
    }
} else {
    Write-Host "[3/3] Portal already on :$portalPort" -ForegroundColor DarkGray
}

Start-Sleep -Seconds 6
Write-Host ""
Write-Host "1С:Рентген is up:" -ForegroundColor Green
Write-Host "  Workspace     :  http://localhost:$portalPort"
Write-Host "  Launch Room   :  http://localhost:$portalPort/launch-room"
Write-Host "  Killer Demo   :  http://localhost:$portalPort/killer-demo"
Write-Host "  Board Pack    :  http://localhost:$portalPort/board-pack"
Write-Host "  Approvals     :  http://localhost:$portalPort/approvals"
Write-Host "  Audit Log     :  http://localhost:$portalPort/audit"
Write-Host "  Config intake :  http://localhost:$portalPort/configurations"
Write-Host "  Platform      :  http://localhost:$portalPort/platform-doctor"
Write-Host "  Lock Radar    :  http://localhost:$portalPort/lock-radar"
Write-Host "  Extensions    :  http://localhost:$portalPort/extension-safety"
Write-Host "  Update room   :  http://localhost:$portalPort/update-war-room"
Write-Host "  Rights/RLS    :  http://localhost:$portalPort/rights-rls"
Write-Host "  Value packs   :  http://localhost:$portalPort/value-packs"
Write-Host "  Business Case :  http://localhost:$portalPort/business-case"
Write-Host "  Productize    :  http://localhost:$portalPort/productization"
Write-Host "  Evidence      :  http://localhost:$portalPort/evidence-bundle"
Write-Host "  Vendor audit  :  http://localhost:$portalPort/vendor-portfolio"
Write-Host "  Change impact :  http://localhost:$portalPort/change"
Write-Host "  Risk hotspots :  http://localhost:$portalPort/quality"
Write-Host "  API docs      :  http://127.0.0.1:8000/docs"
Write-Host "  (Dev login: open the portal, click 'Dev Mode' for a real demo JWT)" -ForegroundColor DarkGray
