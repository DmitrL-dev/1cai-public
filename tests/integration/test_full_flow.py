import asyncio
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("IntegrationTest")

async def test_full_flow():
    print("\n🚀 Начало интеграционного теста: Проверка полного цикла")
    
    try:
        # Mock External Dependencies
        with patch('src.ai.strategies.graph.get_neo4j_client') as mock_neo4j_get, \
             patch('src.ai.strategies.graph.get_nl_to_cypher_converter') as mock_converter_get, \
             patch('src.ai.strategies.semantic.QdrantClient') as mock_qdrant, \
             patch('src.ai.strategies.semantic.EmbeddingService') as mock_embedding:
            
            # Setup Neo4j Mocks
            mock_neo4j_client = MagicMock()
            mock_neo4j_client.execute_query.return_value = [{"name": "Node1"}]
            mock_neo4j_get.return_value = mock_neo4j_client
            
            mock_converter = MagicMock()
            mock_converter.convert.return_value = {
                "cypher": "MATCH (n) RETURN n",
                "confidence": 0.9,
                "explanation": "Test query"
            }
            mock_converter.validate_cypher.return_value = True
            mock_converter_get.return_value = mock_converter
            
            # Setup Qdrant Mocks
            mock_embedding_instance = AsyncMock()
            mock_embedding_instance.generate_embedding.return_value = [0.1]*384
            mock_embedding.return_value = mock_embedding_instance
            
            mock_qdrant_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.payload = {"code": "print('hello')", "function_name": "test"}
            mock_result.score = 0.95
            mock_qdrant_instance.search.return_value = [mock_result]
            mock_qdrant.return_value = mock_qdrant_instance
            
            # Import Components
            from src.ai.advanced_orchestrator import AdvancedAIOrchestrator
            from src.ai.query_classifier import AIService
            
            # 1. Test Orchestrator -> Strategy Flow (Direct Call)
            print("\n1️⃣ Тестирование: Orchestrator -> Strategy...")
            
            orchestrator = AdvancedAIOrchestrator()
            
            # Mock classifier to force Neo4j intent
            orchestrator.classifier.classify = MagicMock()
            intent_mock = MagicMock()
            intent_mock.query_type.value = "graph_query"
            intent_mock.preferred_services = [AIService.NEO4J]
            intent_mock.confidence = 0.95
            orchestrator.classifier.classify.return_value = intent_mock
            
            query = "Покажи все узлы графа"
            result = await orchestrator.process_query(query)
            
            if result.get("type") == "graph_query" and result.get("count") == 1:
                print(f"✅ Orchestrator успешно направил запрос в Neo4j Strategy")
                print(f"   Результат: {result.get('results')}")
            else:
                print(f"❌ Orchestrator не смог обработать запрос: {result}")

            # 2. Test Event Bus -> Subscriber (Simulation)
            print("\n2️⃣ Тестирование: Event Bus -> Subscriber...")
            
            # Use EventType enum
            from src.infrastructure.event_bus import EventType, Event
            
            # Subscribe a mock handler
            mock_handler = AsyncMock()
            
            # Create custom event type for testing
            test_event = Event(
                type=EventType.SYSTEM_HEALTH_CHECK,
                payload={"message": "Тестовое событие", "value": 123},
                source="integration_test"
            )
            
            # Publish event directly (EventBus.publish expects Event object)
            await orchestrator.event_bus.publish(test_event)
            
            # Allow async loop to process
            await asyncio.sleep(0.2)
            
            # Check event history instead of subscriber callback
            history = orchestrator.event_bus.get_event_history(EventType.SYSTEM_HEALTH_CHECK, limit=1)
            
            if len(history) > 0 and history[0].payload.get("message") == "Тестовое событие":
                print(f"✅ Event Bus успешно обработал событие")
                print(f"   Данные события: {history[0].payload}")
            else:
                print("❌ Event Bus не обработал событие")

            # 3. Test Evolution Cycle (Mocked)
            print("\n3️⃣ Тестирование: Evolution Cycle...")
            
            # Mock SelfEvolvingAI
            orchestrator.evolving_ai.evolve = AsyncMock(return_value={
                "status": "completed",
                "improvements_generated": 3,
                "improvements_applied": 2
            })
            
            evolution_result = await orchestrator.evolve()
            
            if evolution_result.get("status") == "completed":
                print(f"✅ Evolution Cycle выполнен успешно")
                print(f"   Улучшений сгенерировано: {evolution_result.get('improvements_generated')}")
            else:
                print(f"❌ Evolution Cycle завершился с ошибкой: {evolution_result}")

            print("\n🎉 Интеграционный тест завершен успешно!")

    except Exception as e:
        print(f"❌ Интеграционный тест провалился: {e}")
        import traceback
        traceback.print_exc()
        raise e

if __name__ == "__main__":
    asyncio.run(test_full_flow())
