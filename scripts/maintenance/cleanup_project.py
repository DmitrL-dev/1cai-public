
#!/usr/bin/env python3
"""
Cleanup script for Enterprise 1C AI Development Stack
Удаляет устаревшие, дублирующиеся и ненужные файлы
"""

from pathlib import Path

# Файлы для удаления
FILES_TO_DELETE = [
    # 1. Устаревшие статус-отчеты
    "ПРОЕКТ_85_ПРОЦЕНТОВ.md",
    "ПРОЕКТ_95_ПРОЦЕНТОВ.md",
    "РЕАЛИЗАЦИЯ_ЗАВЕРШЕНА.md",
    "РЕАЛИЗАЦИЯ_НАЧАТА.md",
    "ФИНАЛ_95_ПРОЦЕНТОВ.md",
    "ФИНАЛЬНЫЙ_СТАТУС.md",
    
    # 2. Множественные отчеты реализации
    "IMPLEMENTATION_COMPLETE.md",
    "FINAL_IMPLEMENTATION_STATUS.md",
    "ИТОГОВЫЙ_ОТЧЕТ_РЕАЛИЗАЦИИ.md",
    "ИТОГОВЫЙ_ОТЧЕТ.md",
    "ИТОГОВЫЙ_ОТЧЕТ_ВЫПОЛНЕНИЯ.md",
    "ИТОГОВЫЙ_ОТЧЕТ_ОБ_ИСПРАВЛЕНИИ.md",
    "ПРОГРЕСС_РЕАЛИЗАЦИИ.md",
    "IMPLEMENTATION_SUMMARY.md",
    
    # 3. Старые варианты ИТС
    "ИТС_ВАРИАНТ_2_РЕЗУЛЬТАТ.md",
    "ВАРИАНТ_2_ИТОГИ.md",
    "ВАРИАНТ_3_ГОТОВ_ФИНАЛ.md",
    "ВАРИАНТ_3_ГОТОВ.md",
    "ВАШ_ПРОЕКТ_ГОТОВ.md",
    "КОРНЕВАЯ_ДИРЕКТОРИЯ_ГОТОВА.md",
    "ЗАГРУЗКА_ВСЕХ_КОНФИГУРАЦИЙ.md",
    "ЗАГРУЗКА_ИТС_ГОТОВА.md",
    "ИТС_АВТОРИЗАЦИЯ_РАБОТАЕТ.md",
    "ИТС_БИБЛИОТЕКА_ИНТЕГРАЦИЯ.md",
    "ИСПРАВЛЕНИЕ_ИТС_АВТОРИЗАЦИЯ.md",
    "ИСПРАВЛЕНИЕ_ПАРСИНГА_ИТС.md",
    "РЕЗЮМЕ_ИТС_ИНТЕГРАЦИЯ.md",
    "РЕЗЮМЕ_ПАРСИНГ_ИТС.md",
    
    # 4. Множественные финальные отчеты
    "FINAL_REPORT_V2.md",
    "final-report.md",
    "final-combined-report.md",
    "FINAL_PROJECT_SUMMARY.md",
    "SUMMARY_REPORT.md",
    "PRODUCT_SUMMARY.md",
    
    # 5. Старые скрипты парсинга
    "parse_1c_config.py",
    "parse_1c_config_advanced.py",
    "parse_1c_config_final.py",
    "parse_1c_config_fixed.py",
    
    # 6. Временные тестовые файлы
    "test_complete_workflow_fixed.js",
    "test_complete_workflow.js",
    "test_data_transformation.js",
    "test_its_api_correct.py",
    "test_its_api.py",
    "test_its_auth.py",
    "test_xml_structure.py",
    "test_website_functionality.html",
    "final_test_after_fix.js",
    "detailed_demo_test.js",
    "test-credentials.txt",  # SECURITY!
    "test-progress.md",
    
    # 7. HTML тестовые страницы ИТС
    "its_api_response__db_metod8dev_browse_13_-1_3190.html",
    "its_api_response__db_metod8dev_browse_13_-1_3199.html",
    "its_api_response__db_metod8dev_browse_13_-1_3272.html",
    "its_api_response__db_metod8dev_browse_13_-1.html",
    "its_api_response__db_metod8dev_content_100010_hdoc.html",
    "its_api_response__db_metod8dev_search_all.html",
    "its_api_response__db_metod8dev_search.html",
    "its_api_response.html",
    "its_erp_page.html",
    "its_main_page.html",
    "its_test_page.html",
    "its_working_content.html",
    
    # 8. Дублирующиеся deployment отчеты
    "DEPLOYMENT_GUIDE.md",
    "DEPLOYMENT_INSTRUCTIONS.md",
    "deployment-report.md",
    "final-deployment-report-updated.md",
    "final-deployment-report.md",
    
    # 9. Дубликат service
    "src/services/configuration-knowledge-base.py",
    
    # 10. Архивные скрипты
    "create_archive.py",
    "create_final_archive.py",
    "simple_archive.py",
    "update_archive.py",
    "final_update_archive.py",
    "AI_Ecosystem_1C_Complete_Project.zip",
    
    # 11. Старые Quick Start
    "QUICK_START_V2.md",
    "QUICKSTART.md",
    
    # 12. Bug reports
    "bug_fix_report.md",
    "bug_report.md",
    "error_handling_fix_report.md",
    "error_handling_implementation_report.md",
    "final_fix_report.md",
    "fix_icon_imports_summary.md",
    "fix_method_call_arity_report.md",
    "fix_possibly_undefined_report.md",
    "icon_imports_fix_report.md",
    "improvements-report.md",
    "monaco_editor_fixes_report.md",
    "service_fixes_report.txt",
    "split_fix_report.md",
    "mobile_optimization_fixes_summary.md",
    "MATHEMATICAL_OPERATION_ERRORS_FIX_REPORT.md",
    
    # 13. Устаревшие планы
    "ADDITIONAL_IMPROVEMENTS_PLAN.md",
    "agents_expansion_plan.md",
    "AUTOMATION_PLAN_SUMMARY.md",
    "ПЛАН_ИНТЕГРАЦИИ_КОНФИГУРАЦИЙ.md",
    "ПЛАН_СЛЕДУЮЩИХ_ШАГОВ.md",
    "NEXT_STEPS.md",
    "WEEK1_COMPLETE.md",
    "project_enhancement_recommendations.md",
    "РЕКОМЕНДАЦИИ_ВЫПОЛНЕНЫ.md",
    "РЕКОМЕНДАЦИИ_ПО_МЕТАДАННЫМ.md",
    
    # 14. Прочие дубликаты
    "ИСПРАВЛЕНИЯ_ВЫПОЛНЕНЫ.md",
    "ИСПРАВЛЕНИЯ_ОШИБОК.md",
    "ДИАГНОСТИКА_И_ИСПРАВЛЕНИЯ.md",
    "ОТЧЕТ_ОБ_ИСПРАВЛЕНИИ_РЕЗУЛЬТАТОВ.md",
    "РЕЗУЛЬТАТЫ_ПАРСИНГА_DO.md",
    "РЕЗУЛЬТАТЫ_ТЕСТИРОВАНИЯ_САЙТА.md",
    "website_restoration_report.md",
    "website_test_report.md",
    "enhanced_demo.html",
    "original-style-combined.html",
    "combined-demo.html",
    "final-demo.html",
    "demo_fix_demonstration.html",
    "downloaded_js.js",
    
    # 15. Анализы (можно оставить в docs/, удалить из корня)
    "analyze_1c_metadata_viewer.py",
    "analyze_bsl_extension.py",
    "analyze_its_page.py",
    "deep_xml_analysis.py",
    "check_all_results.py",
    "check_archive.py",
    "check_do_results.py",
    "check_xml_structure.py",
    "find_config_ids.py",
    "find_its_api.py",
    "find_its_endpoints.py",
    "improve_bsl_parser.py",
    "improve_parser_with_mcp.py",
    "setup_directories.py",
    
    # 16. Устаревшие отчеты
    "АНАЛИЗ_1C_METADATA_VIEWER.md",
    "АНАЛИЗ_BSL_РАСШИРЕНИЯ.md",
    "АНАЛИЗ_ВАРИАНТОВ.md",
    "АНАЛИЗ_ПРОЕКТА_ОШИБКИ_И_УЛУЧШЕНИЯ.md",
    "ИТОГОВЫЙ_АНАЛИЗ_ПЛАГИНОВ.md",
    "Architecture_Analysis_Report.md",
    "Architecture_Analysis_Summary.md",
    "DEMO_OPTIMIZATION_REPORT.md",
    "DEMO_PROJECTS_ANALYSIS_REPORT.md",
    "Detailed_Optimization_Plan.md",
    "PROJECT_RESTRUCTURING_REPORT.md",
    "FINAL_RESTRUCTURING_REPORT.md",
    "PROJECT_STATISTICS_AND_ACHIEVEMENTS.md",
    
    # 17. Completion reports (устарели)
    "SUPABASE_INTEGRATION_COMPLETION_REPORT.md",
    "INTEGRATION_TESTS_COMPLETION_REPORT.md",
    "TASK_COMPLETION_REPORT.md",
    "CICD_PIPELINE_SUMMARY.md",
    "Gateway_Implementation_Report.md",
    "ENCRYPTED_CREDENTIALS_REPORT.md",
    "PRODUCTION_CONFIGS_REPORT.md",
    "enhanced_scenarios_report.md",
    "final_inspection_report.md",
    "final_verification_report.md",
    "testing-summary.md",
    "testing_instructions.md",
    "diagnostic_version_instructions.md",
    "final_diagnostic_instructions.md",
    
    # 18. Старые demo
    "example_import_data.json",
    "example_template.json",
    
    # 19. Nginx дубликаты
    "nginx.conf",  # Есть в nginx/nginx.conf
]


def delete_files(dry_run: bool = True):
    """
    Удаляет файлы из списка
    
    Args:
        dry_run: Если True, только показывает что будет удалено
    """
    project_root = Path(".")
    deleted_count = 0
    not_found_count = 0
    total_size = 0
    
    print("="*60)
    print("CLEANUP PROJECT - Enterprise 1C AI Stack")
    print("="*60)
    print(f"Mode: {'DRY RUN (preview)' if dry_run else 'REAL DELETE'}")
    print(f"Total files to check: {len(FILES_TO_DELETE)}")
    print("="*60)
    print()
    
    for file_path in FILES_TO_DELETE:
        full_path = project_root / file_path
        
        if full_path.exists():
            file_size = full_path.stat().st_size
            total_size += file_size
            size_kb = file_size / 1024
            
            if dry_run:
                print(f"[WILL DELETE] {file_path} ({size_kb:.1f} KB)")
            else:
                try:
                    full_path.unlink()
                    print(f"[DELETED] {file_path} ({size_kb:.1f} KB)")
                    deleted_count += 1
                except Exception as e:
                    print(f"[ERROR] {file_path}: {e}")
        else:
            not_found_count += 1
            if dry_run:
                print(f"[NOT FOUND] {file_path}")
    
    print()
    print("="*60)
    print("SUMMARY")
    print("="*60)
    
    if dry_run:
        print(f"Files that will be deleted: {len(FILES_TO_DELETE) - not_found_count}")
        print(f"Files not found: {not_found_count}")
        print(f"Total space to free: {total_size / (1024*1024):.2f} MB")
        print()
        print("WARNING: This was a DRY RUN. No files were deleted.")
        print("To actually delete files, run:")
        print("  python cleanup_project.py --execute")
    else:
        print(f"Files deleted: {deleted_count}")
        print(f"Files not found: {not_found_count}")
        print(f"Space freed: {total_size / (1024*1024):.2f} MB")
        print()
        print("OK: Cleanup completed!")
    
    print("="*60)


if __name__ == "__main__":
    import sys

    # Check if user wants to execute
    dry_run = "--execute" not in sys.argv
    
    if not dry_run:
        print("\nWARNING: This will PERMANENTLY delete files!")
        response = input("Are you sure? Type 'yes' to confirm: ")
        if response.lower() != 'yes':
            print("Cancelled.")
            sys.exit(0)
    
    delete_files(dry_run=dry_run)

