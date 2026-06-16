import asyncio
import os
import sys
import logging

# Добавляем корень проекта в sys.path
sys.path.append(os.getcwd())

from src.ai.agents.devops_agent_extended import DevOpsAgentExtended

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DevOpsDemo")

async def run_demo():
    print("\n🐳 [DEMO] Starting Local DevOps Analysis\n")
    
    agent = DevOpsAgentExtended()
    
    # 1. Анализируем MVP конфиг (он точно есть и проще)
    target_file = "docker-compose.mvp.yml"
    if not os.path.exists(target_file):
        # Fallback на обычный
        target_file = "docker-compose.yml"
    
    if not os.path.exists(target_file):
        print(f"❌ No docker-compose file found to analyze.")
        return

    print(f"📄 Analyzing configuration: {target_file}...")
    
    result = await agent.analyze_local_infrastructure(target_file)
    
    # Вывод результатов
    print("\n🔍 Static Analysis Results:")
    static = result["static_analysis"]
    print(f"   Version: {static.get('version')}")
    print(f"   Services found: {static.get('service_count')}")
    
    if static.get("security_issues"):
        print("\n   ⚠️ Security Issues:")
        for issue in static["security_issues"]:
            print(f"      - [{issue['severity'].upper()}] {issue['message']}")
    
    if static.get("performance_issues"):
        print("\n   ⚠️ Performance/Reliability Issues:")
        for issue in static["performance_issues"]:
            print(f"      - [{issue['severity'].upper()}] {issue['message']}")
            
    # Runtime анализ
    print("\n🏃 Runtime Status (Real Docker Containers):")
    runtime = result["runtime_status"]
    if not runtime:
        print("   No containers found (or docker not running/accessible).")
    else:
        for container in runtime:
            print(f"   - {container['name']} ({container['image']}): {container['state'].upper()}")

    # Корреляция
    print("\n🔗 Infrastructure Correlation:")
    correlation = result["correlation"]
    for svc, status in correlation.items():
        icon = "✅" if status['runtime_status'] and status['runtime_status'].startswith("Up") else "💤"
        print(f"   {icon} Service '{svc}': {status['runtime_status'] or 'Not Running'}")

    print("\n✅ Analysis Complete. This data comes from YOUR local filesystem and Docker engine.")

if __name__ == "__main__":
    asyncio.run(run_demo())

