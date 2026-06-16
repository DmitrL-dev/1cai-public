# Restore Manual Fixes from Backup
# This script restores your manual fixes that were backed up

Write-Host "=" * 80
Write-Host "RESTORING MANUAL FIXES FROM BACKUP"
Write-Host "=" * 80
Write-Host ""

$backupDir = "c:\1cAI\backup_before_restore_20251128_154813"
$targetDir = "c:\1cAI"

if (-not (Test-Path $backupDir)) {
    Write-Host "❌ Backup directory not found: $backupDir" -ForegroundColor Red
    exit 1
}

Write-Host "Step 1: Restoring files from backup..."
Write-Host ""

# Restore src directory
Copy-Item -Path "$backupDir\src\*" -Destination "$targetDir\src\" -Recurse -Force

Write-Host "✅ Files restored from backup" -ForegroundColor Green
Write-Host ""

Write-Host "Step 2: Verifying restoration..."
Write-Host ""

# Re-run pylint to check
Write-Host "Running pylint to verify..."
pylint src/ --output-format=json 2>$null | Out-File -FilePath "pylint_results_after_manual_restore.json" -Encoding utf8

$results = Get-Content "pylint_results_after_manual_restore.json" -Raw | ConvertFrom-Json
$parsingErrors = $results | Where-Object { $_.'message-id' -eq 'E0001' }
$totalIssues = $results.Count

Write-Host ""
Write-Host "=" * 80
Write-Host "RESULTS"
Write-Host "=" * 80
Write-Host "Total issues:         $totalIssues"
Write-Host "Parsing errors:       $($parsingErrors.Count)"
Write-Host "Other issues:         $($totalIssues - $parsingErrors.Count)"
Write-Host ""

if ($parsingErrors.Count -lt 100) {
    Write-Host "🎉 Great progress! Only $($parsingErrors.Count) parsing errors remain!" -ForegroundColor Green
}
elseif ($parsingErrors.Count -lt 150) {
    Write-Host "✅ Good progress! $($parsingErrors.Count) parsing errors remain" -ForegroundColor Green
}
else {
    Write-Host "⚠️ Still have $($parsingErrors.Count) parsing errors" -ForegroundColor Yellow
}

Write-Host "=" * 80
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Review the remaining issues"
Write-Host "2. Commit your fixes to git"
Write-Host "3. Continue fixing remaining issues"
