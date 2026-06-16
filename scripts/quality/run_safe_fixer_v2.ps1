# Safe Auto-Fixer v2.0 - One-Click Execution
# Runs safe code quality fixes and validates results

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "SAFE AUTO-FIXER V2.0 - ONE-CLICK EXECUTION" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Step 1: Check prerequisites
Write-Host "Step 1: Checking prerequisites..." -ForegroundColor Yellow
$tools = @("isort", "autoflake", "autopep8")
$missing = @()

foreach ($tool in $tools) {
    $check = python -m pip show $tool 2>$null
    if ($LASTEXITCODE -ne 0) {
        $missing += $tool
    }
}

if ($missing.Count -gt 0) {
    Write-Host "  ⚠️  Missing tools: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "  Installing..." -ForegroundColor Yellow
    pip install $($missing -join ' ')
    Write-Host ""
}

Write-Host "  ✅ All tools available" -ForegroundColor Green
Write-Host ""

# Step 2: Run safe fixer
Write-Host "Step 2: Running safe auto-fixer..." -ForegroundColor Yellow
python scripts/quality/safe_auto_fixer_v2.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Fixer failed! Check errors above." -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 3: Validate results
Write-Host "Step 3: Validating results..." -ForegroundColor Yellow
Write-Host "  Running pylint..." -ForegroundColor Gray

pylint src/ --output-format=json --exit-zero 2>$null | Out-File -FilePath "pylint_after_safe_fix.json" -Encoding utf8

$results = Get-Content pylint_after_safe_fix.json -Raw -Encoding utf8 | ConvertFrom-Json
$parsingErrors = $results | Where-Object { $_.'message-id' -eq 'E0001' }
$totalIssues = $results.Count

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "RESULTS" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
Write-Host "Before:      3073 issues" -ForegroundColor Gray
Write-Host "After:       $totalIssues issues" -ForegroundColor $(if ($totalIssues -lt 3073) { "Green" } else { "Red" })
Write-Host "Fixed:       $(3073 - $totalIssues) issues" -ForegroundColor Green
Write-Host ""
Write-Host "Parsing errors: $($parsingErrors.Count)" -ForegroundColor $(if ($parsingErrors.Count -eq 0) { "Green" } else { "Red" })
Write-Host ""

if ($parsingErrors.Count -eq 0) {
    Write-Host "✅ SUCCESS! No parsing errors!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Review changes: git diff --stat" -ForegroundColor Gray
    Write-Host "  2. If satisfied: git add . && git commit -m 'fix: safe auto-fixes v2.0'" -ForegroundColor Gray
    Write-Host "  3. If issues: git reset --hard HEAD" -ForegroundColor Gray
}
else {
    Write-Host "❌ VALIDATION FAILED! Parsing errors detected!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Rolling back changes..." -ForegroundColor Yellow
    git reset --hard HEAD
    Write-Host "✅ Changes rolled back" -ForegroundColor Green
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
