import asyncio
import os
import sys
import logging

# Добавляем корень проекта в sys.path
sys.path.append(os.getcwd())

from src.ai.self_evolving_ai import SelfEvolvingAI

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("EvoDemo")

async def run_demo():
    print("\n🧬 [DEMO] Starting Self-Evolving AI Analysis\n")
    
    # Инициализируем (без реального LLM, так как нам важен этап сбора метрик)
    evo_system = SelfEvolvingAI(llm_provider=None)
    
    print("🔍 Collecting metrics from REAL infrastructure...")
    
    # Запускаем только этап анализа (так как полный evolve требует LLM для генерации улучшений)
    metrics = await evo_system._analyze_performance()
    
    print("\n📊 Real-Time Performance Metrics:")
    print(f"   Accuracy:          {metrics.accuracy * 100:.1f}% (Percentage of healthy services)")
    print(f"   Error Rate:        {metrics.error_rate * 100:.1f}%")
    print(f"   Latency Score:     {metrics.latency_ms} ms")
    print(f"   Throughput Score:  {metrics.throughput}")
    print(f"   User Satisfaction: {metrics.user_satisfaction}")
    
    if metrics.accuracy < 1.0:
        print("\n⚠️ System detected degradation! Evolution triggered.")
        # Здесь пошла бы генерация улучшений через LLM
        print("   (In full mode, AI would now generate Dockerfile fixes or scaling rules)")
    else:
        print("\n✅ System is healthy. Evolution cycle monitoring...")

if __name__ == "__main__":
    asyncio.run(run_demo())

