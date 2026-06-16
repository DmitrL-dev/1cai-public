
"""
Production Performance Audit Example
Полный цикл анализа production производительности

Uses:
- TechLogAnalyzer - парсинг tech log
- AIIssueClassifier - ML классификация
- SQLOptimizer - оптимизация запросов
- RASMonitor - real-time мониторинг
- ArchitectAgentExtended - итоговые рекомендации
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from datetime import datetime

from src.ai.agents.ai_issue_classifier import AIIssueClassifier
from src.ai.agents.ras_monitor import RASMonitor
from src.ai.agents.sql_optimizer import SQLOptimizer
from src.ai.agents.tech_log_analyzer import TechLogAnalyzer


async def full_production_audit():
    """
    Полный аудит production производительности
    
    Workflow:
    1. Парсинг tech log
    2. RAS мониторинг
    3. AI классификация проблем
    4. SQL оптимизация
    5. Итоговый отчет
    """
    print("="*70)
    print("PRODUCTION PERFORMANCE AUDIT")
    print("Full workflow demonstration")
    print("="*70)
    
    # Инициализация компонентов
    tech_log = TechLogAnalyzer()
    ras_monitor = RASMonitor()
    classifier = AIIssueClassifier()
    sql_optimizer = SQLOptimizer("postgresql")
    
    # ==========================================
    # ШАГ 1: TECH LOG ANALYSIS
    # ==========================================
    print("\n[1/5] Analyzing Tech Log...")
    
    # Mock данные (в реальности - парсинг реального tech log)
    mock_log_data = {
        'events': [],
        'events_count': 1500,
        'by_type': {
            'DBMSSQL': 450,
            'CALL': 800,
            'EXCP': 150,
            'TLOCK': 100
        }
    }
    
    # Анализ
    perf_analysis = await tech_log.analyze_performance(mock_log_data)
    
    print(f"  [OK] Events analyzed: {perf_analysis['events_analyzed']}")
    print(f"  [OK] Issues found: {perf_analysis['summary']['total_issues']}")
    print(f"  [OK] Critical: {perf_analysis['summary']['critical_issues']}")
    
    # ==========================================
    # ШАГ 2: RAS MONITORING
    # ==========================================
    print("\n[2/5] Checking Cluster Health (RAS)...")
    
    await ras_monitor.connect()
    cluster_health = await ras_monitor.get_cluster_health()
    
    print(f"  [OK] Cluster: {cluster_health['cluster_info'].name}")
    print(f"  [OK] Active Sessions: {cluster_health['active_sessions']}")
    print(f"  [OK] Working Processes: {cluster_health['working_processes']}")
    print(f"  [OK] Health Status: {cluster_health['health_status']}")
    
    # ==========================================
    # ШАГ 3: AI ISSUE CLASSIFICATION
    # ==========================================
    print("\n[3/5] AI Classification of Issues...")
    
    # Mock issue
    test_issue = {
        'type': 'slow_query',
        'sql': 'SELECT * FROM orders WHERE UPPER(customer_name) = "ACME"',
        'duration_ms': 15300,
        'severity': 'critical',
        'context': 'Sales report generation'
    }
    
    classified = await classifier.classify_issue(test_issue)
    
    print(f"  [OK] Category: {classified.category}")
    print(f"  [OK] Confidence: {classified.confidence}")
    print(f"  [OK] Root Cause: {classified.root_cause}")
    print(f"  [OK] Auto-fix: {classified.auto_fix_available}")
    
    # ==========================================
    # ШАГ 4: SQL OPTIMIZATION
    # ==========================================
    print("\n[4/5] Optimizing Slow Queries...")
    
    if classified.auto_fix_available:
        optimization = await sql_optimizer.optimize_query(
            test_issue['sql'],
            {'database': 'postgresql'}
        )
        
        print(f"  [OK] Anti-patterns found: {len(optimization['anti_patterns_found'])}")
        print(f"  [OK] Optimizations: {len(optimization['optimizations'])}")
        print(f"  [OK] Index recommendations: {len(optimization['index_recommendations'])}")
        print(f"  [OK] Expected improvement: {optimization['expected_improvement']}")
    
    # ==========================================
    # ШАГ 5: FINAL REPORT
    # ==========================================
    print("\n[5/5] Generating Final Report...")
    
    final_report = {
        "audit_date": datetime.now().isoformat(),
        "scope": "Production environment",
        "data_sources": [
            "Tech Log (1,500 events)",
            "RAS (cluster health)",
            "AI Classification"
        ],
        "findings": {
            "critical_issues": perf_analysis['summary']['critical_issues'],
            "slow_queries": len(perf_analysis['top_slow_queries']),
            "slow_methods": len(perf_analysis['top_slow_methods']),
            "exceptions": perf_analysis['exceptions']['total_exceptions'],
            "cluster_health": cluster_health['health_status']
        },
        "optimizations": {
            "sql_optimizations": len(optimization['optimizations']) if classified.auto_fix_available else 0,
            "index_recommendations": len(optimization['index_recommendations']) if classified.auto_fix_available else 0
        },
        "expected_improvement": {
            "sql_queries": "10x-100x faster",
            "overall_performance": "50-200% improvement"
        },
        "action_plan": [
            "1. Применить SQL оптимизации (приоритет 1)",
            "2. Добавить рекомендованные индексы",
            "3. Оптимизировать медленные методы",
            "4. Исправить источники исключений",
            "5. Мониторить метрики после изменений"
        ]
    }
    
    print(f"  [OK] Report generated")
    print(f"\n" + "="*70)
    print("AUDIT SUMMARY")
    print("="*70)
    print(f"Critical Issues: {final_report['findings']['critical_issues']}")
    print(f"Slow Queries: {final_report['findings']['slow_queries']}")
    print(f"Cluster Health: {final_report['findings']['cluster_health']}")
    print(f"\nOptimizations Available:")
    print(f"  SQL: {final_report['optimizations']['sql_optimizations']}")
    print(f"  Indexes: {final_report['optimizations']['index_recommendations']}")
    print(f"\nExpected Improvement:")
    print(f"  SQL: {final_report['expected_improvement']['sql_queries']}")
    print(f"  Overall: {final_report['expected_improvement']['overall_performance']}")
    print(f"\n" + "="*70)
    print("[SUCCESS] Production audit completed!")
    print("="*70)
    print("\nComponents demonstrated:")
    print("  [OK] TechLogAnalyzer - tech log parsing")
    print("  [OK] RASMonitor - cluster health")
    print("  [OK] AIIssueClassifier - ML classification")
    print("  [OK] SQLOptimizer - query optimization")
    print("  [OK] Full workflow - end-to-end")
    print("="*70)


async def main():
    await full_production_audit()


if __name__ == "__main__":
    asyncio.run(main())


