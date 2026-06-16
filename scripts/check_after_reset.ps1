# Quick Pylint Check After Git Reset
# Check if parsing errors are fixed

Write-Host "Checking Python files after git reset..."
Write-Host ""

# Test a few critical files
$testFiles = @(
    "src/ai/code_dna.py",
    "src/ai/agents/analytics_kpi_with_graph.py",
    "src/api/admin_audit.py"
)

$validCount = 0
$invalidCount = 0

foreach ($file in $testFiles) {
    Write-Host "Testing: $file"
    
    $result = python -c "import ast; ast.parse(open('$file', 'r', encoding='utf-8').read()); print('OK')" 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Valid" -ForegroundColor Green
        $validCount++
    }
    else {
        Write-Host "  ❌ Invalid: $result" -ForegroundColor Red
        $invalidCount++
    }
}

Write-Host ""
Write-Host "Results:"
Write-Host "  Valid:   $validCount" -ForegroundColor Green
Write-Host "  Invalid: $invalidCount" -ForegroundColor Red

if ($invalidCount -eq 0) {
    Write-Host ""
    Write-Host "🎉 All test files are valid! Running full pylint..." -ForegroundColor Green
    Write-Host ""
    
    # Run full pylint
    pylint src/ --output-format=json --exit-zero > pylint_results_final.json 2>&1
    
    $results = Get-Content pylint_results_final.json -Raw | ConvertFrom-Json
    $parsingErrors = $results | Where-Object { $_.'message-id' -eq 'E0001' }
    $totalIssues = $results.Count
    
    Write-Host "=" * 70
    Write-Host "FINAL RESULTS"
    Write-Host "=" * 70
    Write-Host "Total issues:    $totalIssues"
    Write-Host "Parsing errors:  $($parsingErrors.Count)"
    Write-Host "Other issues:    $($totalIssues - $parsingErrors.Count)"
    Write-Host "=" * 70
    
    if ($parsingErrors.Count -eq 0) {
        Write-Host ""
        Write-Host "🎉🎉🎉 SUCCESS! NO PARSING ERRORS! 🎉🎉🎉" -ForegroundColor Green
        Write-Host "Project is now functional!" -ForegroundColor Green
    }
}
