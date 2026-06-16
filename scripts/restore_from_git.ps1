# Restore Damaged Files from Git
# This script restores all damaged/incomplete files from git

Write-Host "=" * 80
Write-Host "RESTORING DAMAGED FILES FROM GIT"
Write-Host "=" * 80
Write-Host ""

# Check git status first
Write-Host "Step 1: Checking git status..."
Write-Host ""

$gitStatus = git status --short src/
$modifiedFiles = $gitStatus | Where-Object { $_ -match '^\s*M\s+' }

Write-Host "Modified files in src/: $($modifiedFiles.Count)"
Write-Host ""

# Backup current state
Write-Host "Step 2: Creating backup of current state..."
$backupDir = "c:\1cAI\backup_before_restore_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

Copy-Item -Path "c:\1cAI\src" -Destination "$backupDir\src" -Recurse -Force
Write-Host "Backup created: $backupDir"
Write-Host ""

# Restore from git
Write-Host "Step 3: Restoring files from git..."
Write-Host ""

git checkout -- src/

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Files restored successfully from git" -ForegroundColor Green
}
else {
    Write-Host "❌ Git restore failed" -ForegroundColor Red
    Write-Host "You can manually restore from backup: $backupDir"
    exit 1
}

Write-Host ""
Write-Host "Step 4: Verifying restoration..."
Write-Host ""

# Re-run pylint to check
Write-Host "Running pylint to verify..."
pylint src/ --output-format=json 2>$null | Out-File -FilePath "pylint_results_after_restore.json" -Encoding utf8

$results = Get-Content "pylint_results_after_restore.json" -Raw | ConvertFrom-Json
$parsingErrors = $results | Where-Object { $_.'message-id' -eq 'E0001' }

Write-Host ""
Write-Host "=" * 80
Write-Host "RESULTS"
Write-Host "=" * 80
Write-Host "Parsing errors after restore: $($parsingErrors.Count)"
Write-Host "Backup location: $backupDir"
Write-Host ""

if ($parsingErrors.Count -eq 0) {
    Write-Host "🎉 SUCCESS! All parsing errors fixed!" -ForegroundColor Green
}
elseif ($parsingErrors.Count -lt 50) {
    Write-Host "✅ Major improvement! Only $($parsingErrors.Count) errors remain" -ForegroundColor Green
}
else {
    Write-Host "⚠️ Still have $($parsingErrors.Count) parsing errors" -ForegroundColor Yellow
}

Write-Host "=" * 80
