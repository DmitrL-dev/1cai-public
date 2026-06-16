
"""
Simple Demo - AI Architect (без Neo4j, без emoji)
Демонстрация возможностей без зависимостей
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from datetime import datetime


async def demo_adr_generation():
    """Демо: Генерация ADR"""
    print("\n" + "="*70)
    print("DEMO: ADR Generation")
    print("="*70)
    
    # Симуляция генерации ADR
    adr = {
        "adr_id": f"ADR-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "title": "Vybor shiny dannykh dlya B2B integraciy",
        "date": datetime.now().isoformat()[:10],
        "status": "accepted",
        "decision": "Apache Kafka + REST (gibrid)",
        "alternatives": [
            {"option": "Apache Kafka", "total_score": 7.2},
            {"option": "RabbitMQ", "total_score": 7.4},
            {"option": "REST API", "total_score": 7.6}
        ]
    }
    
    print(f"\n[OK] ADR created: {adr['adr_id']}")
    print(f"     Title: {adr['title']}")
    print(f"     Decision: {adr['decision']}")
    print(f"\n[OK] Best Alternative: {adr['alternatives'][0]['option']} (score: {adr['alternatives'][0]['total_score']})")


async def demo_anti_pattern_detection():
    """Демо: Детекция anti-patterns"""
    print("\n" + "="*70)
    print("DEMO: Anti-Pattern Detection")
    print("="*70)
    
    # Симуляция детекции
    result = {
        "anti_patterns_count": 15,
        "overall_score": 6.8,
        "quality_grade": "C (Acceptable)",
        "by_severity": {
            "critical": 2,
            "high": 5,
            "medium": 6,
            "low": 2
        },
        "priority_fixes": [
            {
                "type": "God Object",
                "location": "ObshegoNaznacheniya",
                "severity": "critical",
                "estimated_days": 5,
                "refactoring_effort": "High",
                "recommendation": "Razbit modul na specializirovannye moduli"
            },
            {
                "type": "Circular Dependency",
                "location": "Prodazhi -> Sklad -> Prodazhi",
                "severity": "critical",
                "estimated_days": 3,
                "refactoring_effort": "Medium",
                "recommendation": "Razorvat cikl cherez sobytiya"
            }
        ]
    }
    
    print(f"\n[OK] Results:")
    print(f"     Found: {result['anti_patterns_count']} anti-patterns")
    print(f"     Quality: {result['quality_grade']}")
    print(f"     Score: {result['overall_score']}/10")
    
    print(f"\n[OK] By severity:")
    for severity, count in result['by_severity'].items():
        print(f"     {severity}: {count}")
    
    print(f"\n[OK] Top-3 Priority Fixes:")
    for i, fix in enumerate(result['priority_fixes'][:3], 1):
        print(f"     {i}. [{fix['severity'].upper()}] {fix['type']}: {fix['location']}")
        print(f"        Effort: {fix['refactoring_effort']} ({fix['estimated_days']} days)")


async def demo_technology_selection():
    """Демо: Выбор технологий"""
    print("\n" + "="*70)
    print("DEMO: Technology Selection")
    print("="*70)
    
    # Симуляция выбора
    stack = {
        "recommended_stack": {
            "integration_bus": {
                "option": "Apache Kafka",
                "score": 9.2,
                "reason": "Vysokaya propusknaya sposobnost"
            },
            "api_gateway": {
                "option": "Kong",
                "score": 8.5,
                "reason": "Rate limiting, monitoring"
            },
            "caching": {
                "option": "Redis",
                "score": 9.0,
                "reason": "Universalnost i proizvoditelnost"
            }
        },
        "architecture_pattern": "Event-Driven Microservices",
        "estimated_cost": "Medium",
        "implementation_complexity": "High"
    }
    
    print(f"\n[OK] Recommended Stack:")
    for category, tech in stack['recommended_stack'].items():
        print(f"\n     {category.upper()}:")
        print(f"       Technology: {tech['option']}")
        print(f"       Score: {tech['score']}/10")
        print(f"       Reason: {tech['reason']}")
    
    print(f"\n[OK] Architecture Pattern: {stack['architecture_pattern']}")
    print(f"[OK] Cost: {stack['estimated_cost']}")
    print(f"[OK] Complexity: {stack['implementation_complexity']}")


async def demo_performance_analysis():
    """Демо: Анализ производительности"""
    print("\n" + "="*70)
    print("DEMO: Performance Analysis")
    print("="*70)
    
    # Симуляция анализа
    result = {
        "apdex_score": 0.75,
        "performance_grade": "Fair",
        "bottlenecks": [
            {
                "type": "slow_query",
                "location": "Otchet.ProdazhiZaPeriod",
                "current_value": 15.3,
                "threshold": 3.0,
                "impact": "high",
                "recommendations": [
                    "Dobavit indeksy na chasto ispolzuemye polya",
                    "Ispolzovat vremennye tablicy",
                    "Optimizirovat JOIN zaprosy"
                ]
            }
        ],
        "estimated_improvement": {
            "potential_speedup": "45%",
            "effort": "high",
            "estimated_days": 8
        }
    }
    
    print(f"\n[OK] Performance Metrics:")
    print(f"     Apdex Score: {result['apdex_score']}")
    print(f"     Grade: {result['performance_grade']}")
    
    print(f"\n[OK] Bottlenecks found: {len(result['bottlenecks'])}")
    for bn in result['bottlenecks']:
        print(f"     [{bn['impact'].upper()}] {bn['location']}")
        print(f"       Current: {bn['current_value']:.1f}s | Threshold: {bn['threshold']}s")
        print(f"       Tips: {len(bn['recommendations'])} recommendations")
    
    print(f"\n[OK] Optimization Potential:")
    print(f"     Speedup: {result['estimated_improvement']['potential_speedup']}")
    print(f"     Effort: {result['estimated_improvement']['effort']}")
    print(f"     Days: {result['estimated_improvement']['estimated_days']}")


async def demo_graph_analysis():
    """Демо: Граф-анализ"""
    print("\n" + "="*70)
    print("DEMO: Architecture Graph Analysis")
    print("="*70)
    
    # Симуляция граф-анализа
    result = {
        "config_name": "ERP",
        "metrics": {
            "modules_count": 125,
            "coupling_score": 0.67,
            "cohesion_score": 0.85,
            "overall_score": 7.2
        },
        "issues": {
            "cyclic_dependencies": 3,
            "god_objects": 2,
            "orphan_modules": 5
        },
        "health_status": "moderate"
    }
    
    print(f"\n[OK] Architecture Metrics:")
    print(f"     Modules: {result['metrics']['modules_count']}")
    print(f"     Coupling: {result['metrics']['coupling_score']:.2f} (moderate)")
    print(f"     Cohesion: {result['metrics']['cohesion_score']:.2f} (excellent)")
    print(f"     Overall Score: {result['metrics']['overall_score']:.1f}/10")
    print(f"     Health: {result['health_status']}")
    
    print(f"\n[OK] Issues:")
    print(f"     Cyclic dependencies: {result['issues']['cyclic_dependencies']}")
    print(f"     God Objects: {result['issues']['god_objects']}")
    print(f"     Orphan modules: {result['issues']['orphan_modules']}")


async def main():
    """Запуск всех демо"""
    print("\n" + "="*70)
    print("AI ARCHITECT DEMOS - All Features")
    print("="*70)
    
    # Demo 1: Graph Analysis
    await demo_graph_analysis()
    
    # Demo 2: ADR Generation
    await demo_adr_generation()
    
    # Demo 3: Anti-Pattern Detection
    await demo_anti_pattern_detection()
    
    # Demo 4: Technology Selection
    await demo_technology_selection()
    
    # Demo 5: Performance Analysis
    await demo_performance_analysis()
    
    print("\n" + "="*70)
    print("[SUCCESS] All demos completed!")
    print("="*70)
    print("\nAI Architect features demonstrated:")
    print("  [OK] Graph Analysis - architecture metrics")
    print("  [OK] ADR Generation - architecture decisions")
    print("  [OK] Anti-Pattern Detection - quality analysis")
    print("  [OK] Technology Selection - tech stack recommendations")
    print("  [OK] Performance Analysis - bottleneck detection")
    print("\nTotal: 5 major features, 18 MCP tools available!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())


