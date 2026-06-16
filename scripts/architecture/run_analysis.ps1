# Architecture Analysis Runner

Write-Host "Running architecture analysis..." -ForegroundColor Cyan
Write-Host ""

python scripts/architecture/analyze_all.py

Write-Host ""
Write-Host "Results saved to: architecture_analysis.json" -ForegroundColor Green
Write-Host ""
Write-Host "To view results:" -ForegroundColor Yellow
Write-Host "  code architecture_analysis.json" -ForegroundColor Gray
