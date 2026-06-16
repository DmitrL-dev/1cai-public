import asyncio
import logging
from unittest.mock import MagicMock, patch, AsyncMock

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

async def verify_data_layer():
    print("\n🔍 Verifying Data Layer...")
    
    try:
        # 1. Neo4j Strategy
        print("Checking Neo4j Strategy...")
        with patch('src.ai.strategies.graph.get_neo4j_client') as mock_get_client, \
             patch('src.ai.strategies.graph.get_nl_to_cypher_converter') as mock_get_converter:
            
            from src.ai.strategies.graph import Neo4jStrategy
            
            # Mock Client
            mock_client = MagicMock()
            mock_client.execute_query = MagicMock(return_value=["Node1", "Node2"])
            mock_get_client.return_value = mock_client
            
            # Mock Converter
            mock_converter = MagicMock()
            mock_converter.convert.return_value = {
                "cypher": "MATCH (n) RETURN n",
                "confidence": 0.9,
                "explanation": "Test query"
            }
            mock_converter.validate_cypher.return_value = True
            mock_get_converter.return_value = mock_converter
            
            strategy = Neo4jStrategy()
            result = await strategy.execute("Show me nodes", {})
            
            if result.get("type") == "graph_query" and result.get("count") == 2:
                print("✅ Neo4jStrategy executed query successfully")
            else:
                print(f"❌ Neo4jStrategy failed: {result}")

        # 2. Qdrant Strategy
        print("Checking Qdrant Strategy...")
        with patch('src.ai.strategies.semantic.QdrantClient') as mock_qdrant, \
             patch('src.ai.strategies.semantic.EmbeddingService') as mock_embedding:
            
            from src.ai.strategies.semantic import QdrantStrategy
            
            # Mock Embedding
            mock_embedding_instance = AsyncMock()
            mock_embedding_instance.generate_embedding.return_value = [0.1, 0.2, 0.3]
            mock_embedding.return_value = mock_embedding_instance
            
            # Mock Qdrant
            mock_qdrant_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.payload = {"code": "print('hello')", "function_name": "test"}
            mock_result.score = 0.95
            mock_qdrant_instance.search.return_value = [mock_result]
            mock_qdrant.return_value = mock_qdrant_instance
            
            strategy = QdrantStrategy()
            result = await strategy.execute("Find print code", {})
            
            if result.get("type") == "semantic_search" and result.get("count") == 1:
                print("✅ QdrantStrategy executed search successfully")
            else:
                print(f"❌ QdrantStrategy failed: {result}")

        # 3. Postgres Saver
        print("Checking PostgresSaver...")
        try:
            # Mock psycopg2 before importing
            with patch('psycopg2.pool.ThreadedConnectionPool') as mock_pool, \
                 patch('psycopg2.connect') as mock_connect:
                
                from src.db.postgres_saver import PostgreSQLSaver
                
                saver = PostgreSQLSaver(password="dummy")
                saver.connect()
                print("✅ PostgreSQLSaver initialized and connected (mocked)")
                
        except ImportError:
             print("⚠️ PostgreSQLSaver not found or import error")
        except Exception as e:
             print(f"❌ PostgreSQLSaver verification failed: {e}")

    except Exception as e:
        print(f"❌ Data Layer verification failed: {e}")
        raise e

if __name__ == "__main__":
    asyncio.run(verify_data_layer())
