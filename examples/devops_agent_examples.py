
"""
Примеры использования DevOps AI Agent
Демонстрация всех возможностей
"""

import sys
from pathlib import Path

# Добавить путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio

from src.ai.agents.devops_agent_extended import DevOpsAgentExtended


async def example_1_cicd_optimization():
    """
    Пример 1: Оптимизация CI/CD pipeline
    """
    print("="*70)
    print("EXAMPLE 1: CI/CD Pipeline Optimization")
    print("="*70)
    
    agent = DevOpsAgentExtended()
    
    # Mock pipeline config
    pipeline_config = {
        "name": "CI/CD Pipeline",
        "jobs": ["build", "test", "deploy"]
    }
    
    # Mock metrics
    metrics = {
        "total_duration": 1500,  # 25 minutes
        "build_time": 300,       # 5 minutes
        "test_time": 900,        # 15 minutes
        "deploy_time": 300       # 5 minutes
    }
    
    result = await agent.optimize_pipeline(pipeline_config, metrics)
    
    print("\n[OK] Current Pipeline Performance:")
    print(f"     Total Duration: {result['analysis']['current_metrics']['total_duration']} sec (25 min)")
    print(f"     Health Score: {result['analysis']['overall_health']:.1f}/10")
    
    print("\n[OK] Top 3 Optimization Recommendations:")
    for i, rec in enumerate(result['recommendations'][:3], 1):
        print(f"\n     {i}. {rec['optimization']}")
        print(f"        Stage: {rec['stage']}")
        print(f"        Expected Speedup: {rec['expected_speedup_percent']}%")
        print(f"        Effort: {rec['effort']}")
        print(f"        Priority: {rec['priority']}")
    
    print("\n[OK] Expected Improvement After Optimizations:")
    imp = result['expected_improvement']
    print(f"     Current: {imp['current_duration_sec']} sec")
    print(f"     Expected: {imp['expected_duration_sec']} sec")
    print(f"     Time Saved: {imp['time_saved_sec']} sec")
    print(f"     Speedup: {imp['speedup_percent']}%")
    
    print("\n[OK] Optimized Pipeline YAML generated!")
    print("="*70)


async def example_2_log_analysis():
    """
    Пример 2: AI анализ логов
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: AI Log Analysis")
    print("="*70)
    
    agent = DevOpsAgentExtended()
    
    # Mock log content
    log_content = """
2025-11-03 10:15:23 INFO  Application started
2025-11-03 10:15:45 INFO  Database connection established
2025-11-03 10:16:12 ERROR OutOfMemoryError: Java heap space
2025-11-03 10:16:15 ERROR OutOfMemoryError: Java heap space
2025-11-03 10:16:18 WARN  High memory usage: 95%
2025-11-03 10:17:00 ERROR Connection refused: database timeout
2025-11-03 10:17:05 ERROR Connection refused: database timeout
2025-11-03 10:17:10 ERROR Connection refused: database timeout
2025-11-03 10:18:00 INFO  Application recovering
2025-11-03 10:19:00 ERROR NullPointerException at line 145
2025-11-03 10:20:00 ERROR Deadlock detected in transaction
2025-11-03 10:21:00 WARN  Performance degradation detected
2025-11-03 10:22:00 ERROR Permission denied: /var/log/app.log
    """
    
    result = await agent.analyze_logs(log_content, "application")
    
    print("\n[OK] Log Analysis Summary:")
    summary = result['summary']
    print(f"     Errors Found: {summary['errors_found']}")
    print(f"     Warnings Found: {summary['warnings_found']}")
    print(f"     Anomalies Detected: {summary['anomalies_found']}")
    
    print("\n[OK] Errors by Category:")
    for category, count in result['errors_by_category'].items():
        print(f"     {category}: {count} errors")
    
    print("\n[OK] Detected Anomalies:")
    for anomaly in result['anomalies']:
        print(f"     - {anomaly['type']}")
        print(f"       Severity: {anomaly['severity']}")
        print(f"       Possible Cause: {anomaly['possible_cause']}")
    
    print("\n[OK] Detected Patterns:")
    for pattern in result['patterns']:
        print(f"     - {pattern['pattern']} (count: {pattern['count']})")
    
    print("\n[OK] Recommendations:")
    for rec in result['recommendations']:
        print(f"     - {rec}")
    
    print("="*70)


async def example_3_cost_optimization():
    """
    Пример 3: Оптимизация затрат на инфраструктуру
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Infrastructure Cost Optimization")
    print("="*70)
    
    agent = DevOpsAgentExtended()
    
    # Mock current infrastructure
    current_setup = {
        "instance_type": "m5.2xlarge",
        "instance_count": 3,
        "pricing_model": "on_demand"
    }
    
    # Mock usage metrics
    usage_metrics = {
        "cpu_avg": 35,      # 35% average CPU
        "memory_avg": 45,   # 45% average memory
        "storage_iops": 800 # 800 IOPS
    }
    
    result = await agent.optimize_costs(current_setup, usage_metrics)
    
    print("\n[OK] Cost Analysis:")
    print(f"     Current Cost: ${result['current_cost_month']:.2f}/month")
    print(f"     Optimized Cost: ${result['optimized_cost_month']:.2f}/month")
    print(f"     Monthly Savings: ${result['total_savings_month']:.2f} ({result['savings_percent']}%)")
    print(f"     Annual Savings: ${result['annual_savings']:.2f}")
    
    print("\n[OK] Top Optimization Opportunities:")
    for i, opt in enumerate(result['optimizations'][:3], 1):
        print(f"\n     {i}. {opt['resource']}")
        print(f"        Current: {opt['current']}")
        print(f"        Recommended: {opt['recommended']}")
        print(f"        Monthly Savings: ${opt['savings_month']:.2f} ({opt['savings_percent']}%)")
        print(f"        Risk: {opt['risk']} | Effort: {opt['effort']}")
        print(f"        Reason: {opt['reason']}")
    
    print("="*70)


async def example_4_iac_generation():
    """
    Пример 4: Генерация Infrastructure as Code (Terraform)
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: IaC (Terraform) Generation")
    print("="*70)
    
    agent = DevOpsAgentExtended()
    
    # Requirements for infrastructure
    requirements = {
        "provider": "aws",
        "services": ["compute", "database", "cache"],
        "environment": "production",
        "budget": "medium"
    }
    
    result = await agent.generate_iac(requirements)
    
    print("\n[OK] Generated Terraform Files:")
    print(f"     - main.tf ({len(result['main.tf'])} chars)")
    print(f"     - variables.tf ({len(result['variables.tf'])} chars)")
    print(f"     - outputs.tf ({len(result['outputs.tf'])} chars)")
    
    print("\n[OK] main.tf Preview:")
    print("     " + "-"*66)
    for line in result['main.tf'].split('\n')[:15]:
        print(f"     {line}")
    print("     ... (truncated)")
    print("     " + "-"*66)
    
    print("\n[OK] Services Configured:")
    for service in requirements['services']:
        print(f"     - {service.capitalize()}")
    
    print("\n[OK] Terraform files are ready to use!")
    print("     Run: terraform init && terraform plan")
    
    print("="*70)


async def example_5_full_devops_workflow():
    """
    Пример 5: Полный DevOps workflow
    """
    print("\n" + "="*70)
    print("EXAMPLE 5: Full DevOps Workflow")
    print("="*70)
    
    agent = DevOpsAgentExtended()
    
    print("\n[STEP 1/4] Optimizing CI/CD Pipeline...")
    pipeline_result = await agent.optimize_pipeline(
        {"name": "Main Pipeline"},
        {"total_duration": 1800, "build_time": 400, "test_time": 1100, "deploy_time": 300}
    )
    print(f"     OK - Expected speedup: {pipeline_result['expected_improvement']['speedup_percent']}%")
    
    print("\n[STEP 2/4] Analyzing Production Logs...")
    log_result = await agent.analyze_logs(
        "2025-11-03 ERROR Connection timeout\n2025-11-03 ERROR Memory leak detected",
        "application"
    )
    print(f"     OK - Found {log_result['summary']['errors_found']} errors, {log_result['summary']['anomalies_found']} anomalies")
    
    print("\n[STEP 3/4] Optimizing Infrastructure Costs...")
    cost_result = await agent.optimize_costs(
        {"instance_type": "m5.4xlarge", "instance_count": 5, "pricing_model": "on_demand"},
        {"cpu_avg": 30, "memory_avg": 40}
    )
    print(f"     OK - Potential savings: ${cost_result['total_savings_month']:.2f}/month ({cost_result['savings_percent']}%)")
    
    print("\n[STEP 4/4] Generating IaC (Terraform)...")
    iac_result = await agent.generate_iac({
        "provider": "aws",
        "services": ["compute", "database"],
        "environment": "staging"
    })
    print(f"     OK - Generated {len(iac_result)} Terraform files")
    
    print("\n" + "="*70)
    print("[SUCCESS] Full DevOps Workflow Completed!")
    print("="*70)
    print("\nResults Summary:")
    print(f"  - CI/CD Pipeline: {pipeline_result['expected_improvement']['speedup_percent']}% faster")
    print(f"  - Log Issues: {log_result['summary']['errors_found']} errors detected")
    print(f"  - Cost Savings: ${cost_result['annual_savings']:.2f}/year")
    print(f"  - IaC Files: {len(iac_result)} files generated")
    print("="*70)


async def main():
    """Запуск всех примеров"""
    print("="*70)
    print("   DevOps AI Agent - Usage Examples")
    print("="*70)
    
    # Пример 1: CI/CD Optimization
    await example_1_cicd_optimization()
    
    # Пример 2: Log Analysis
    await example_2_log_analysis()
    
    # Пример 3: Cost Optimization
    await example_3_cost_optimization()
    
    # Пример 4: IaC Generation
    await example_4_iac_generation()
    
    # Пример 5: Full Workflow
    await example_5_full_devops_workflow()
    
    print("\n" + "="*70)
    print("[SUCCESS] All DevOps AI examples completed!")
    print("="*70)
    print("\nDevOps AI Agent features demonstrated:")
    print("  [OK] CI/CD Pipeline Optimization - automated analysis & recommendations")
    print("  [OK] AI Log Analysis - pattern detection & anomaly detection")
    print("  [OK] Cost Optimization - infrastructure rightsizing & savings")
    print("  [OK] IaC Generation - Terraform code generation")
    print("  [OK] Full DevOps Workflow - end-to-end automation")
    print("\nTotal: 4 major features, ~15 capabilities!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())


