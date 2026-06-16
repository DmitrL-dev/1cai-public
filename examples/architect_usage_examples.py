
"""
Примеры использования AI Архитектора
Демонстрация всех возможностей
"""

import sys
from pathlib import Path

# Добавить путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio

from src.ai.agents.architect_agent_extended import ArchitectAgentExtended
from src.ai.agents.performance_analyzer import PerformanceAnalyzer
from src.ai.agents.technology_selector import TechnologySelector


async def example_1_graph_analysis():
    """
    Пример 1: Граф-анализ архитектуры конфигурации
    
    Use Case: Архитектор хочет понять состояние архитектуры ERP
    """
    print("="*70)
    print("EXAMPLE 1: Graph Analysis - Анализ архитектуры ERP")
    print("="*70)
    
    architect = ArchitectAgentExtended()
    
    # Полный граф-анализ
    result = await architect.analyze_architecture_graph("ERP", deep_analysis=True)
    
    if 'error' not in result:
        print(f"\n📊 Метрики архитектуры:")
        print(f"  Модулей: {result['metrics']['modules_count']}")
        print(f"  Coupling Score: {result['metrics']['coupling_score']:.2f} ({result['detailed_coupling']['status']})")
        print(f"  Cohesion Score: {result['metrics']['cohesion_score']:.2f} ({result['detailed_cohesion']['status']})")
        print(f"  Overall Score: {result['metrics']['overall_score']:.1f}/10")
        print(f"  Health Status: {result['health_status']}")
        
        print(f"\n🔴 Проблемы:")
        print(f"  Циклические зависимости: {len(result['issues']['cyclic_dependencies'])}")
        print(f"  God Objects: {len(result['issues']['god_objects'])}")
        print(f"  Orphan Modules: {len(result['issues']['orphan_modules'])}")
        
        if result['issues']['cyclic_dependencies']:
            print(f"\n  Пример цикла:")
            cycle = result['issues']['cyclic_dependencies'][0]
            print(f"    {' → '.join(cycle['path'])}")
        
        if result['issues']['god_objects']:
            print(f"\n  God Object:")
            god = result['issues']['god_objects'][0]
            print(f"    {god['name']} ({god['functions_count']} функций, complexity: {god['complexity_score']})")
        
        print(f"\n💡 Рекомендации ({len(result['recommendations'])}):")
        for rec in result['recommendations'][:3]:
            print(f"  [{rec['priority'].upper()}] {rec['recommendation']}")
    else:
        print(f"Error: {result['error']}")


async def example_2_adr_generation():
    """
    Пример 2: Генерация ADR для архитектурного решения
    
    Use Case: Выбор шины данных для B2B интеграции
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: ADR Generation - Выбор технологии интеграции")
    print("="*70)
    
    architect = ArchitectAgentExtended()
    
    # Генерация ADR
    adr = await architect.generate_adr(
        title="Выбор шины данных для B2B интеграций",
        context="""
B2B-портал требует интеграции с 1С:ERP для приема заказов.
Ожидаемая нагрузка: 10,000 заказов/день, пики до 500 заказов/час.
Требования: SLA 99.9%, время отклика < 2 секунды.
        """,
        problem="""
Синхронные REST вызовы приводят к:
- Таймаутам при пиковых нагрузках
- Деградации производительности портала
- Потере заказов при недоступности 1С
        """,
        alternatives=[
            {
                "option": "REST API (синхронный)",
                "pros": ["Простота", "Прямой доступ", "Низкая сложность"],
                "cons": ["Таймауты", "Нет очереди", "Single point of failure"],
                "scores": {
                    "feasibility": 9,
                    "cost": 9,
                    "complexity": 8,
                    "performance": 5,
                    "maintainability": 7
                }
            },
            {
                "option": "RabbitMQ",
                "pros": ["Очереди", "Надежность", "Retry механизмы"],
                "cons": ["Дополнительный компонент", "Требует мониторинга"],
                "scores": {
                    "feasibility": 8,
                    "cost": 7,
                    "complexity": 6,
                    "performance": 8,
                    "maintainability": 8
                }
            },
            {
                "option": "Apache Kafka",
                "pros": ["Высокая пропускная способность", "Event streaming", "Durability"],
                "cons": ["Операционная сложность", "Требует экспертизы", "Стоимость"],
                "scores": {
                    "feasibility": 7,
                    "cost": 6,
                    "complexity": 5,
                    "performance": 10,
                    "maintainability": 7
                }
            }
        ],
        decision="Использовать Apache Kafka для событий + REST для синхронных запросов (гибрид)",
        rationale="""
Kafka обеспечивает:
- Масштабируемость для растущей нагрузки
- Event sourcing для аудита
- Decoupling между порталом и 1С
- Гарантированную доставку

REST оставляем для:
- Синхронных запросов (проверка остатков, цен)
- Простых операций чтения
        """,
        consequences={
            "pros": [
                "Устойчивость к пиковым нагрузкам",
                "Масштабируемость (linear scaling)",
                "Event sourcing и аудит",
                "Decoupling систем"
            ],
            "cons": [
                "Требуется обучение команды Kafka",
                "Операционная сложность (мониторинг, troubleshooting)",
                "Стоимость инфраструктуры увеличится на 30%"
            ]
        }
    )
    
    print(f"\n✅ ADR создан: {adr['adr']['adr_id']}")
    print(f"   Title: {adr['adr']['title']}")
    print(f"   Decision: {adr['adr']['decision'][:80]}...")
    print(f"\n📁 Markdown сохранен: {adr['file_path']}")
    print(f"\n🏆 Best Alternative: {adr['adr']['alternatives'][0]['option']} (score: {adr['adr']['alternatives'][0]['total_score']})")


async def example_3_anti_pattern_detection():
    """
    Пример 3: Детекция anti-patterns
    
    Use Case: Аудит качества архитектуры перед релизом
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Anti-Pattern Detection - Аудит качества")
    print("="*70)
    
    architect = ArchitectAgentExtended()
    
    # Детекция anti-patterns
    result = await architect.detect_anti_patterns("ERP", include_code_analysis=False)
    
    print(f"\n📊 Результаты анализа:")
    print(f"  Найдено anti-patterns: {result['anti_patterns_count']}")
    print(f"  Quality Score: {result['overall_score']:.1f}/10")
    print(f"  Quality Grade: {result['quality_grade']}")
    
    print(f"\n📈 По категориям severity:")
    for severity, count in result['by_severity'].items():
        print(f"  {severity}: {count}")
    
    print(f"\n🔥 Top-5 Priority Fixes:")
    for i, fix in enumerate(result['priority_fixes'][:5], 1):
        print(f"  {i}. [{fix['severity'].upper()}] {fix['type']}: {fix['location']}")
        print(f"     Effort: {fix['refactoring_effort']} ({fix['estimated_days']} days)")
        print(f"     → {fix['recommendation'][:70]}...")
    
    if result['refactoring_roadmap']:
        print(f"\n📅 Refactoring Roadmap:")
        for phase in result['refactoring_roadmap'][:3]:
            print(f"  {phase['phase']}: {phase['task']}")


async def example_4_technology_selection():
    """
    Пример 4: Выбор технологического стека
    
    Use Case: Проектирование архитектуры нового модуля интеграции
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Technology Selection - Выбор стека")
    print("="*70)
    
    selector = TechnologySelector()
    
    requirements = {
        "scale": "high",
        "availability": 0.999,
        "performance": "< 2s response time",
        "load": "10000 orders/day",
        "integration_type": "event-driven"
    }
    
    constraints = {
        "budget": "medium",
        "team_skills": ["BSL", "Python", "PostgreSQL"],
        "existing_tech": ["1С:ERP", "PostgreSQL", "Redis"],
        "compliance": ["152-ФЗ"],
        "deployment": "on-premise"
    }
    
    result = await selector.recommend_technology_stack(requirements, constraints)
    
    print(f"\n🛠️ Рекомендованный стек:")
    for category, tech in result['recommended_stack'].items():
        print(f"\n  {category.upper()}:")
        print(f"    Technology: {tech['option']}")
        print(f"    Score: {tech['score']}/10")
        print(f"    Reason: {tech['reason']}")
    
    print(f"\n🏗️ Architecture Pattern: {result['architecture_pattern']}")
    print(f"💰 Estimated Cost: {result['estimated_cost']}")
    print(f"⚙️ Complexity: {result['implementation_complexity']}")
    
    print(f"\n📅 Migration Plan ({len(result['migration_plan'])} phases):")
    for phase in result['migration_plan']:
        print(f"  Phase {phase['phase']}: {phase['component']} - {phase['technology']}")


async def example_5_performance_analysis():
    """
    Пример 5: Анализ производительности
    
    Use Case: Поиск узких мест перед peak season
    """
    print("\n" + "="*70)
    print("EXAMPLE 5: Performance Analysis - Поиск узких мест")
    print("="*70)
    
    analyzer = PerformanceAnalyzer()
    
    # Mock metrics from Prometheus/Grafana
    metrics = {
        'current_users': 1500,
        'memory_usage': 0.82,
        'cpu_usage': 0.68,
        'response_times': [1.2, 1.8, 2.1, 15.3, 1.5, 2.3, 1.9, 14.7]  # 2 outliers
    }
    
    result = await analyzer.analyze_performance("ERP", metrics)
    
    print(f"\n⚡ Performance Metrics:")
    print(f"  Apdex Score: {result['apdex_score']}")
    print(f"  Grade: {result['performance_grade']}")
    
    print(f"\n🔍 Bottlenecks found: {len(result['bottlenecks'])}")
    for bn in result['bottlenecks'][:3]:
        print(f"  [{bn['impact'].upper()}] {bn['location']}")
        print(f"    Current: {bn['current_value']:.1f}s | Threshold: {bn['threshold']}s")
        print(f"    Recommendations: {len(bn['recommendations'])} tips")
    
    print(f"\n📈 Scalability Assessment:")
    print(f"  Current: {result['scalability_assessment']['current_capacity']}")
    print(f"  Predicted: {result['scalability_assessment']['predicted_capacity']}")
    print(f"  Strategy: {result['scalability_assessment']['scaling_strategy']}")
    
    print(f"\n💎 Optimization Potential:")
    print(f"  Speedup: {result['estimated_improvement']['potential_speedup']}")
    print(f"  Effort: {result['estimated_improvement']['effort']}")
    print(f"  Days: {result['estimated_improvement']['estimated_days']}")


async def example_6_comprehensive_workflow():
    """
    Пример 6: Полный workflow архитектора
    
    Use Case: Проектирование нового модуля с нуля
    """
    print("\n" + "="*70)
    print("EXAMPLE 6: Comprehensive Workflow - Полный цикл проектирования")
    print("="*70)
    
    architect = ArchitectAgentExtended()
    tech_selector = TechnologySelector()
    perf_analyzer = PerformanceAnalyzer()
    
    # Шаг 1: Анализ текущей архитектуры
    print("\n[1/5] Analyzing current architecture...")
    graph_analysis = await architect.analyze_architecture_graph("ERP")
    print(f"  ✓ Overall Score: {graph_analysis['metrics']['overall_score']:.1f}/10")
    
    # Шаг 2: Детекция проблем
    print("\n[2/5] Detecting anti-patterns...")
    anti_patterns = await architect.detect_anti_patterns("ERP")
    print(f"  ✓ Found {anti_patterns['anti_patterns_count']} anti-patterns")
    print(f"  ✓ Quality Grade: {anti_patterns['quality_grade']}")
    
    # Шаг 3: Выбор технологий
    print("\n[3/5] Recommending technology stack...")
    tech_stack = await tech_selector.recommend_technology_stack(
        requirements={"scale": "high", "integration_type": "event-driven"},
        constraints={"budget": "medium", "team_skills": ["BSL", "Python"]}
    )
    print(f"  ✓ Pattern: {tech_stack['architecture_pattern']}")
    print(f"  ✓ Stack: {len(tech_stack['recommended_stack'])} components")
    
    # Шаг 4: Анализ производительности
    print("\n[4/5] Analyzing performance...")
    performance = await perf_analyzer.analyze_performance("ERP")
    print(f"  ✓ Apdex: {performance['apdex_score']} ({performance['performance_grade']})")
    print(f"  ✓ Bottlenecks: {len(performance['bottlenecks'])}")
    
    # Шаг 5: Генерация ADR
    print("\n[5/5] Generating ADR...")
    adr = await architect.generate_adr(
        title="Архитектура модуля B2B интеграции",
        context="Новый B2B портал для приема заказов",
        problem="Требуется масштабируемая и надежная интеграция",
        alternatives=tech_stack['recommended_stack'],
        decision=f"Использовать {tech_stack['architecture_pattern']}",
        rationale="Обеспечивает масштабируемость и устойчивость",
        consequences={
            "pros": ["Масштабируемость", "Устойчивость"],
            "cons": ["Сложность"]
        }
    )
    print(f"  ✓ ADR created: {adr['adr']['adr_id']}")
    
    print(f"\n✅ Comprehensive analysis completed!")
    print(f"\n📊 Summary:")
    print(f"  Current Architecture Score: {graph_analysis['metrics']['overall_score']:.1f}/10")
    print(f"  Quality Grade: {anti_patterns['quality_grade']}")
    print(f"  Performance Grade: {performance['performance_grade']}")
    print(f"  Recommended Pattern: {tech_stack['architecture_pattern']}")
    print(f"  ADR: {adr['file_path']}")


async def main():
    """Запуск всех примеров"""
    print("="*70)
    print("   AI Architect Examples - Usage Demonstrations")
    print("="*70)
    
    # Пример 1
    await example_1_graph_analysis()
    
    # Пример 2
    await example_2_adr_generation()
    
    # Пример 3
    await example_3_anti_pattern_detection()
    
    # Пример 4
    await example_4_technology_selection()
    
    # Пример 5
    await example_5_performance_analysis()
    
    # Пример 6 - полный workflow
    await example_6_comprehensive_workflow()
    
    print(f"\n{'='*70}")
    print("✅ All examples completed!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())

