# cleanup_old_docs.ps1
# Script to remove outdated documentation files

$FilesToDelete = @(
    # Дубликаты финальных отчетов
    "🎉_ПРОЕКТ_ЗАВЕРШЕН_100_ПРОЦЕНТОВ.md",
    "ПРОЕКТ_100_ПРОЦЕНТОВ.md",
    "ПРОЕКТ_95_ПРОЦЕНТОВ.md",
    "ПРОЕКТ_85_ПРОЦЕНТОВ.md",
    "ФИНАЛ_95_ПРОЦЕНТОВ.md",
    "РЕАЛИЗАЦИЯ_ПОЛНОСТЬЮ_ЗАВЕРШЕНА.md",
    "РЕАЛИЗАЦИЯ_ЗАВЕРШЕНА.md",
    "ВАШ_ПРОЕКТ_ГОТОВ.md",
    "НАЧНИТЕ_ОТСЮДА.md",
    "ФИНАЛЬНЫЙ_СТАТУС.md",
    "IMPLEMENTATION_COMPLETE.md",
    "FINAL_IMPLEMENTATION_STATUS.md",
    
    # Старые итоговые отчеты
    "ИТОГОВЫЙ_ОТЧЕТ.md",
    "ИТОГОВЫЙ_ОТЧЕТ_ВЫПОЛНЕНИЯ.md",
    "ИТОГОВЫЙ_ОТЧЕТ_РЕАЛИЗАЦИИ.md",
    "ИТОГОВЫЙ_АНАЛИЗ_ПЛАГИНОВ.md",
    
    # Промежуточные отчеты
    "ПРОГРЕСС_РЕАЛИЗАЦИИ.md",
    "РЕАЛИЗАЦИЯ_НАЧАТА.md",
    "WEEK1_COMPLETE.md",
    "IMPLEMENTATION_SUMMARY.md",
    
    # Старые варианты
    "ВАРИАНТ_2_ИТОГИ.md",
    "ВАРИАНТ_3_ГОТОВ.md",
    "ВАРИАНТ_3_ГОТОВ_ФИНАЛ.md",
    "ИТС_ВАРИАНТ_2_РЕЗУЛЬТАТ.md",
    "АНАЛИЗ_ВАРИАНТОВ.md",
    
    # Старые отчеты ИТС
    "ИТС_АВТОРИЗАЦИЯ_РАБОТАЕТ.md",
    "ИСПРАВЛЕНИЕ_ИТС_АВТОРИЗАЦИЯ.md",
    "ИСПРАВЛЕНИЕ_ПАРСИНГА_ИТС.md",
    "ИТС_БИБЛИОТЕКА_ИНТЕГРАЦИЯ.md",
    "ЗАГРУЗКА_ИТС_ГОТОВА.md",
    "РЕЗЮМЕ_ПАРСИНГ_ИТС.md",
    "РЕЗЮМЕ_ИТС_ИНТЕГРАЦИЯ.md",
    
    # Промежуточные этапы
    "ЭТАПЫ_3_4_ЗАВЕРШЕНЫ.md",
    "ШАГИ_РЕАЛИЗАЦИИ_ЭТАП_1.md",
    "ШАГИ_РЕАЛИЗАЦИИ_ЭТАП_2.md",
    
    # Исправления
    "ИСПРАВЛЕНИЯ_ОШИБОК.md",
    "ИСПРАВЛЕНИЯ_ВЫПОЛНЕНЫ.md",
    "АНАЛИЗ_ПРОЕКТА_ОШИБКИ_И_УЛУЧШЕНИЯ.md",
    
    # Дубликаты архитектора
    "🎉_AI_АРХИТЕКТОР_ФИНАЛ.md",
    "FINAL_ARCHITECT_SUMMARY.md",
    "AI_ARCHITECT_READY.md",
    "ARCHITECT_AI_ANALYSIS_AND_GROWTH.md",
    "START_ARCHITECT_AI.md",
    "ARCHITECT_AI_WITH_ITS_COMPLETE.md",
    
    # Cleanup отчеты
    "RUN_MIGRATION.md",
    "CLEANUP_SUCCESS.md",
    "CLEANUP_REPORT.md",
    "CONFIGURATIONS_CLEANUP_GUIDE.md",
    
    # Старые планы
    "ПЛАН_СЛЕДУЮЩИХ_ШАГОВ.md",
    "ПЛАН_РАЗВИТИЯ_И_ИННОВАЦИИ.md",
    "ПЛАН_ИНТЕГРАЦИИ_КОНФИГУРАЦИЙ.md",
    "ПЛАН_РЕАЛИЗАЦИИ_АВТОМАТИЗАЦИИ_1С.md",
    "РАСШИРЕННЫЙ_ПЛАН_АВТОМАТИЗАЦИИ_1С_AI.md",
    
    # Прочие старые
    "NEXT_STEPS.md",
    "INDEX.md",
    "todo.md",
    "MULTI_ROLE_COMPLETE.md",
    "EDT_PLUGIN_COMPLETE.md",
    "original-style-final-report.md",
    
    # Старые анализы
    "АНАЛИЗ_BSL_РАСШИРЕНИЯ.md",
    "АНАЛИЗ_1C_METADATA_VIEWER.md",
    "КОРНЕВАЯ_ДИРЕКТОРИЯ_ГОТОВА.md",
    "ЗАГРУЗКА_ВСЕХ_КОНФИГУРАЦИЙ.md",
    
    # Промежуточные результаты
    "РЕЗУЛЬТАТЫ_ПАРСИНГА_DO.md",
    "РЕКОМЕНДАЦИИ_ПО_МЕТАДАННЫМ.md",
    "РЕКОМЕНДАЦИИ_ВЫПОЛНЕНЫ.md",
    "РЕАЛИЗАЦИЯ_РЕКОМЕНДАЦИЙ.md",
    "РЕСУРСЫ_ДЛЯ_РЕАЛИЗАЦИИ.md",
    
    # Текущий анализ
    "TECH_LOG_INTEGRATION_ANALYSIS.md"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Documentation Cleanup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Files to delete: $($FilesToDelete.Count)" -ForegroundColor Yellow
Write-Host ""

$DeletedCount = 0
$NotFoundCount = 0

foreach ($File in $FilesToDelete) {
    if (Test-Path $File) {
        try {
            Remove-Item $File -Force
            Write-Host "[DELETED] $File" -ForegroundColor Green
            $DeletedCount++
        } catch {
            Write-Host "[ERROR] Failed to delete $File : $($_.Exception.Message)" -ForegroundColor Red
        }
    } else {
        Write-Host "[NOT FOUND] $File" -ForegroundColor Gray
        $NotFoundCount++
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Cleanup Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deleted: $DeletedCount files" -ForegroundColor Green
Write-Host "Not found: $NotFoundCount files" -ForegroundColor Gray
Write-Host ""
Write-Host "Cleanup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan


