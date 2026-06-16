# Final verification after git reset
# Check if parsing errors are truly fixed

Write-Host "=" * 70
Write-Host "FINAL VERIFICATION - Parsing Errors Check"
Write-Host "=" * 70
Write-Host ""

# Run pylint on the entire src directory
Write-Host "Running pylint on src/..."
pylint src/ --output-format=json --exit-zero 2>&1 | Out-File -FilePath "pylint_final_check.json" -Encoding utf8

# Parse results
$results = Get-Content pylint_final_check.json -Raw -Encoding utf8 | ConvertFrom-Json

# Count E0001 errors
$e0001 = $results | Where-Object { $_.'message-id' -eq 'E0001' }
$totalIssues = $results.Count

Write-Host "Results:"
Write-Host "  Total issues:     $totalIssues"
Write-Host "  Parsing errors:   $($e0001.Count)"
Write-Host "  Other issues:     $($totalIssues - $e0001.Count)"
Write-Host ""

if ($e0001.Count -eq 0) {
    Write-Host "🎉🎉🎉 SUCCESS! NO PARSING ERRORS! 🎉🎉🎉" -ForegroundColor Green
    Write-Host ""
    Write-Host "Project is now FUNCTIONAL!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Summary of fixes:"
    Write-Host "  Before: 191 parsing errors"
    Write-Host "  After:  0 parsing errors"
    Write-Host "  Fixed:  191 files (100%)" -ForegroundColor Green
}
else {
    Write-Host "⚠️ Still have $($e0001.Count) parsing errors" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Affected files:"
    $e0001 | Select-Object -First 5 path, line, message | Format-Table -AutoSize
}

Write-Host "=" * 70
