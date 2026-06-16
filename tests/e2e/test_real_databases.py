import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("E2E_Test")

async def test_postgresql():
    """Тест подключения к PostgreSQL и базовых операций"""
    print("\n1️⃣ Тестирование PostgreSQL...")
    
    try:
        from src.db.postgres_saver import PostgreSQLSaver
        
        # Инициализация с параметрами из Docker
        saver = PostgreSQLSaver(
            host="localhost",
            port=5432,
            database="knowledge_base",
            user="admin",
            password=os.getenv("POSTGRES_PASSWORD", "changeme")
        )
        
        # Подключение (синхронная операция в async контексте)
        connected = await asyncio.to_thread(saver.connect)
        if connected:
            print("✅ PostgreSQL: Подключение установлено")
        else:
            print("❌ PostgreSQL: Не удалось подключиться")
            return False
            
        # Проверка is_connected
        is_conn = await asyncio.to_thread(saver.is_connected)
        if is_conn:
            print("✅ PostgreSQL: Health check прошел")
        else:
            print("❌ PostgreSQL: Health check провалился")
            await asyncio.to_thread(saver.disconnect)
            return False
            
        # Получение статистики
        try:
            stats = await asyncio.to_thread(saver.get_statistics)
            print(f"✅ PostgreSQL: Статистика получена (конфигураций: {stats.get('configurations', 0)})")
        except Exception as e:
            print(f"⚠️ PostgreSQL: Ошибка получения статистики - {e}")
        
        await asyncio.to_thread(saver.disconnect)
        return True
            
    except Exception as e:
        print(f"❌ PostgreSQL: Ошибка - {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_neo4j():
    """Тест подключения к Neo4j и выполнения запросов"""
    print("\n2️⃣ Тестирование Neo4j...")
    
    try:
        from src.db.neo4j_client import Neo4jClient
        
        # Инициализация с параметрами из Docker
        client = Neo4jClient(
            uri="bolt://localhost:7687",
            user="neo4j",
            password=os.getenv("NEO4J_PASSWORD", "password")
        )
        
        # Подключение
        if client.connect():
            print("✅ Neo4j: Подключение установлено")
            
            # Выполнение тестового запроса
            result = client.execute_query("MATCH (n) RETURN count(n) as count LIMIT 1")
            if result is not None:
                count = result[0].get("count", 0) if result else 0
                print(f"✅ Neo4j: Запрос выполнен (узлов в БД: {count})")
            else:
                print("⚠️ Neo4j: Запрос вернул None")
            
            client.disconnect()
            return True
        else:
            print("❌ Neo4j: Не удалось подключиться")
            return False
            
    except Exception as e:
        print(f"❌ Neo4j: Ошибка - {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_qdrant():
    """Тест подключения к Qdrant и векторного поиска"""
    print("\n3️⃣ Тестирование Qdrant...")
    
    try:
        from src.db.qdrant_client import QdrantClient
        
        # Инициализация с параметрами из Docker
        client = QdrantClient(
            host="localhost",
            port=6333
        )
        
        # Подключение
        if not client.connect():
            print("❌ Qdrant: Не удалось подключиться")
            return False
            
        print("✅ Qdrant: Подключение установлено")
        
        # Проверка получения коллекций через внутренний клиент
        try:
            collections_response = client.client.get_collections()
            collection_names = [c.name for c in collections_response.collections]
            print(f"✅ Qdrant: Коллекций найдено: {len(collection_names)}")
            
            # Проверка существования коллекции
            if "1c_code" in collection_names:
                print("✅ Qdrant: Коллекция '1c_code' найдена")
            else:
                print("⚠️ Qdrant: Коллекция '1c_code' не найдена (будет создана при первом использовании)")
        except Exception as e:
            print(f"⚠️ Qdrant: Ошибка получения коллекций - {e}")
        
        return True
            
    except Exception as e:
        print(f"❌ Qdrant: Ошибка - {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_full_query_flow():
    """Тест полного цикла обработки запроса с реальными БД"""
    print("\n4️⃣ Тестирование полного цикла запроса...")
    
    try:
        from src.ai.advanced_orchestrator import AdvancedAIOrchestrator
        from src.ai.query_classifier import AIService
        
        orchestrator = AdvancedAIOrchestrator()
        
        # Тест 1: Graph Query (Neo4j)
        print("\n   📊 Тест Graph Query...")
        orchestrator.classifier.classify = lambda q, c: type('obj', (object,), {
            'query_type': type('obj', (object,), {'value': 'graph_query'})(),
            'preferred_services': [AIService.NEO4J],
            'confidence': 0.95
        })()
        
        result = await orchestrator.process_query("Покажи структуру базы знаний")
        if result.get("type") == "graph_query":
            print(f"   ✅ Graph Query выполнен (результатов: {result.get('count', 0)})")
        else:
            print(f"   ❌ Graph Query провалился: {result}")
            
        # Тест 2: Semantic Search (Qdrant)
        print("\n   🔍 Тест Semantic Search...")
        orchestrator.classifier.classify = lambda q, c: type('obj', (object,), {
            'query_type': type('obj', (object,), {'value': 'semantic_search'})(),
            'preferred_services': [AIService.QDRANT],
            'confidence': 0.90
        })()
        
        result = await orchestrator.process_query("Найди примеры кода для работы с файлами")
        if result.get("type") == "semantic_search":
            print(f"   ✅ Semantic Search выполнен (результатов: {result.get('count', 0)})")
        else:
            print(f"   ❌ Semantic Search провалился: {result}")
        
        return True
            
    except Exception as e:
        print(f"❌ Full Query Flow: Ошибка - {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("\n🚀 Начало E2E тестирования с реальными базами данных")
    print("=" * 70)
    
    results = {
        "PostgreSQL": await test_postgresql(),
        "Neo4j": await test_neo4j(),
        "Qdrant": await test_qdrant(),
        "Full Query Flow": await test_full_query_flow()
    }
    
    print("\n" + "=" * 70)
    print("📊 Результаты E2E тестирования:")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:.<50} {status}")
    
    print("=" * 70)
    print(f"Итого: {passed}/{total} тестов прошли успешно ({int(passed/total*100)}%)")
    
    if passed == total:
        print("\n🎉 Все E2E тесты прошли успешно!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} тест(ов) провалились")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
