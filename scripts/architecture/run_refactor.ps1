# Comprehensive Architecture Refactoring

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "COMPREHENSIVE ARCHITECTURE REFACTORING" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "This will:" -ForegroundColor Yellow
Write-Host "  1. Restructure modules/ (321 files)" -ForegroundColor Gray
Write-Host "  2. Reorganize ai/ (113 files)" -ForegroundColor Gray
Write-Host "  3. Split main.py (687 lines)" -ForegroundColor Gray
Write-Host "  4. Fix 8 circular dependencies" -ForegroundColor Gray
Write-Host ""

Write-Host "Step 1: DRY RUN (preview changes)" -ForegroundColor Yellow
python scripts/architecture/refactor_master.py --dry-run

Write-Host ""
Write-Host "Review the changes above." -ForegroundColor Yellow
Write-Host ""
$confirm = Read-Host "Apply changes? (yes/no)"

if ($confirm -eq "yes") {
    Write-Host ""
    Write-Host "Step 2: Applying changes..." -ForegroundColor Green
    python scripts/architecture/refactor_master.py
    
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host "REFACTORING COMPLETE!" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Review changes: git diff" -ForegroundColor Gray
    Write-Host "  2. Run tests: pytest" -ForegroundColor Gray
    Write-Host "  3. Commit: git add . && git commit -m 'refactor: Phase 4 architecture improvements'" -ForegroundColor Gray
}
else {
    Write-Host ""
    Write-Host "Refactoring cancelled." -ForegroundColor Yellow
}
