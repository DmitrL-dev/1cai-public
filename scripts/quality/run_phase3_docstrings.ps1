# Phase 3: Automatic Docstring Generation
# Simplified version without encoding issues

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "PHASE 3: DOCSTRING GENERATION FOR PRIORITY FILES" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Top-10 priority files
$priorityFiles = @(
    @{Path = "src/modules/marketplace/api/"; Pattern = "routes.py"; Count = 25 },
    @{Path = "src/ai_assistants/"; Pattern = "base_assistant.py"; Count = 24 },
    @{Path = "src/infrastructure/repositories/"; Pattern = "marketplace.py"; Count = 21 },
    @{Path = "src/ai/strategies/"; Pattern = "llm_providers.py"; Count = 16 },
    @{Path = "src/security/"; Pattern = "auth.py"; Count = 14 },
    @{Path = "src/services/"; Pattern = "ba_session_manager.py"; Count = 13 },
    @{Path = "src/api/"; Pattern = "dependencies.py"; Count = 11 },
    @{Path = "src/grpc_server/"; Pattern = "ai_service_pb2_grpc.py"; Count = 11 },
    @{Path = "src/modules/analytics/api/"; Pattern = "schemas.py"; Count = 11 },
    @{Path = "src/ai/"; Pattern = "code_graph.py"; Count = 10 }
)

$totalProcessed = 0
$totalDocstrings = 0

Write-Host "Processing top-10 priority files..." -ForegroundColor Yellow
Write-Host ""

foreach ($file in $priorityFiles) {
    Write-Host "Processing: $($file.Pattern) (expected ~$($file.Count) docstrings)" -ForegroundColor Gray
    
    python scripts/quality/docstring_generator.py $file.Path --pattern $file.Pattern
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Success" -ForegroundColor Green
        $totalProcessed++
        $totalDocstrings += $file.Count
    }
    else {
        Write-Host "  [ERROR] Failed" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "RESULTS" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Files processed: $totalProcessed / $($priorityFiles.Count)" -ForegroundColor $(if ($totalProcessed -eq $priorityFiles.Count) { "Green" } else { "Yellow" })
Write-Host "Docstrings added: ~$totalDocstrings" -ForegroundColor Green
Write-Host ""

# Re-run analysis
Write-Host "Running analysis again..." -ForegroundColor Yellow
python scripts/quality/phase3_doc_analyzer.py

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "GENERATION COMPLETE" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Review generated docstrings" -ForegroundColor Gray
Write-Host "  2. Improve TODO descriptions manually" -ForegroundColor Gray
Write-Host "  3. Run link checker: python scripts/quality/link_checker.py" -ForegroundColor Gray
Write-Host "  4. Commit changes: git add . && git commit -m `"docs: Phase 3 docstrings`"" -ForegroundColor Gray
Write-Host ""
