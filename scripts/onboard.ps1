# 1C:Rentgen -- onboard YOUR OWN 1C configuration into the local store.
#
#   powershell -ExecutionPolicy Bypass -File scripts\onboard.ps1 -ConfigPath <unpacked 1C config> [-Force]
#
# Runs the 3-step token-free pipeline, in order, stopping on the first failure:
#   1) go\bsl-scan.exe -mode callgraph <config>     -> data\rentgen_callgraph.ndjson
#   2) python -m tools.bsl_scoring run --config-path <config> --output gabriel_runs\scores.json
#   3) python tools\rentgen\build_store.py          -> data\rentgen.db
#
# Honest scope: this rebuilds THE single local SQLite store (data\rentgen.db).
# Today the tool holds ONE configuration per install -- re-running OVERWRITES the
# existing store. There is no multi-config UI upload yet.
#
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads a BOM-less .ps1 in
# the system ANSI codepage, so non-ASCII chars corrupt parsing.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $ConfigPath,

    [switch] $Force
)

$ErrorActionPreference = "Stop"

# Repo root is the parent of scripts\
$root = Split-Path -Parent $PSScriptRoot
$py   = "C:\Python311\python.exe"          # bundled .venv is broken; use system 3.11
$env:IGNORE_PY_VERSION_CHECK = "1"

$bslScan = Join-Path $root "go\bsl-scan.exe"
$ndjson  = Join-Path $root "data\rentgen_callgraph.ndjson"
$scores  = Join-Path $root "gabriel_runs\scores.json"
$buildPy = Join-Path $root "tools\rentgen\build_store.py"
$db      = Join-Path $root "data\rentgen.db"

function Fail($msg) {
    Write-Host ""
    Write-Host "ERROR: $msg" -ForegroundColor Red
    exit 1
}

# --- Validate inputs BEFORE running anything (no side effects on bad input) ---

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    Fail "-ConfigPath is required. Pass the path to an unpacked 1C configuration (a directory of .bsl files)."
}
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    Fail "Config path not found: $ConfigPath"
}
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Container)) {
    Fail "Config path is not a directory: $ConfigPath  (expected an unpacked 1C config, not a file)."
}
if (-not (Test-Path -LiteralPath $py)) {
    Fail "Python 3.11 not found at $py. Install it or edit the `$py variable in this script."
}
if (-not (Test-Path -LiteralPath $bslScan)) {
    Fail "Scanner not found: $bslScan  (expected the shipped go\bsl-scan.exe)."
}
if (-not (Test-Path -LiteralPath $buildPy)) {
    Fail "Builder not found: $buildPy"
}

$configFull = (Resolve-Path -LiteralPath $ConfigPath).Path

# --- Honest banner ---

Write-Host "1C:Rentgen onboarding" -ForegroundColor Green
Write-Host "  Config : $configFull"
Write-Host "  Store  : $db"
Write-Host "           (THE single local store -- one config per install; this run rebuilds it)"
if ((Test-Path -LiteralPath $db) -and (-not $Force)) {
    Write-Host "  Note   : an existing store will be OVERWRITTEN. Pass -Force to skip this notice." -ForegroundColor Yellow
}
Write-Host ""

# Make sure output directories exist (gabriel_runs / data are normally present, but be safe)
foreach ($dir in @((Split-Path -Parent $ndjson), (Split-Path -Parent $scores))) {
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
}

# --- Step 1: call graph (NDJSON to stdout, redirected to data\rentgen_callgraph.ndjson) ---

Write-Host "[1/3] Call graph: go\bsl-scan.exe -mode callgraph -> data\rentgen_callgraph.ndjson" -ForegroundColor Cyan
& $bslScan -mode callgraph $configFull > $ndjson
if ($LASTEXITCODE -ne 0) {
    Fail "bsl-scan failed (exit $LASTEXITCODE). Call graph not produced -- store NOT rebuilt."
}
if ((-not (Test-Path -LiteralPath $ndjson)) -or ((Get-Item -LiteralPath $ndjson).Length -eq 0)) {
    Fail "bsl-scan produced an empty call graph ($ndjson). Is '$configFull' an unpacked 1C config with .bsl files? Store NOT rebuilt."
}

# --- Step 2: quality scores -> gabriel_runs\scores.json ---

Write-Host "[2/3] Scores: python -m tools.bsl_scoring run --output gabriel_runs\scores.json" -ForegroundColor Cyan
& $py -m tools.bsl_scoring run --config-path $configFull --output $scores
if ($LASTEXITCODE -ne 0) {
    Fail "bsl_scoring failed (exit $LASTEXITCODE). Scores not produced -- store NOT rebuilt."
}
if (-not (Test-Path -LiteralPath $scores)) {
    Fail "bsl_scoring did not write $scores. Store NOT rebuilt."
}

# --- Step 3: build the single SQLite store -> data\rentgen.db ---

Write-Host "[3/3] Build store: python tools\rentgen\build_store.py -> data\rentgen.db (~30s)" -ForegroundColor Cyan
& $py $buildPy
if ($LASTEXITCODE -ne 0) {
    Fail "build_store.py failed (exit $LASTEXITCODE). data\rentgen.db may be incomplete."
}
if (-not (Test-Path -LiteralPath $db)) {
    Fail "build_store.py finished but $db is missing."
}

# --- Success ---

Write-Host ""
Write-Host "Done. Local store rebuilt:" -ForegroundColor Green
Write-Host "  $db"
Write-Host ""
Write-Host "Next:" -ForegroundColor Green
Write-Host "  Start the stack : powershell -ExecutionPolicy Bypass -File scripts\start_rentgen.ps1"
Write-Host "  (or backend only: set IGNORE_PY_VERSION_CHECK=1, then run uvicorn src.main:app on 127.0.0.1:8000)"
Write-Host "  Then open       : http://localhost:3000/quality   (risk hotspots)"
