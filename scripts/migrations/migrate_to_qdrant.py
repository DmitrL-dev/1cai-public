
#!/usr/bin/env python3
"""
Миграция данных из PostgreSQL в Qdrant
Векторизация кода и документации для семантического поиска
"""

import logging
import sys
import uuid

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from src.db.postgres_saver import PostgreSQLSaver
    from src.db.qdrant_client import QdrantClient
    from src.services.embedding_service import EmbeddingService
except ImportError as e:
    logger.error(f"Import error: {e}")
    sys.exit(1)


class QdrantMigrator:
    """Migrates code to Qdrant with vector embeddings"""
    
    def __init__(self):
        self.pg_client = None
        self.qdrant_client = None
        self.embedding_service = None
        self.stats = {
            'functions_indexed': 0,
            'modules_indexed': 0,
            'errors': 0
        }
    
    def connect(self) -> bool:
        """Connect to all services"""
        try:
            # PostgreSQL
            self.pg_client = PostgreSQLSaver()
            if not self.pg_client.connect():
                return False
            logger.info("✓ Connected to PostgreSQL")
            
            # Qdrant
            self.qdrant_client = QdrantClient()
            if not self.qdrant_client.connect():
                return False
            logger.info("✓ Connected to Qdrant")
            
            # Embedding service
            self.embedding_service = EmbeddingService()
            logger.info("✓ Embedding service ready")
            
            return True
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    def setup_collections(self):
        """Create Qdrant collections"""
        logger.info("\nSetting up Qdrant collections...")
        self.qdrant_client.create_collections()
        logger.info("✓ Collections created")
    
    def migrate_functions(self):
        """Migrate functions with embeddings"""
        logger.info("\n" + "="*60)
        logger.info("Migrating Functions to Qdrant")
        logger.info("="*60)
        
        # Get all functions with modules and configurations
        self.pg_client.cur.execute("""
            SELECT 
                f.id, f.name, f.description, f.is_exported,
                f.parameters, f.code,
                m.name as module_name,
                c.name as config_name,
                o.object_type, o.name as object_name
            FROM functions f
            JOIN modules m ON m.id = f.module_id
            JOIN configurations c ON c.id = m.configuration_id
            LEFT JOIN objects o ON o.id = m.object_id
            WHERE f.code IS NOT NULL AND f.code != ''
            ORDER BY c.name, m.name, f.name
        """)
        
        functions = self.pg_client.cur.fetchall()
        total = len(functions)
        
        logger.info(f"Found {total} functions to vectorize")
        
        # Process in batches
        batch_size = 50
        for i in range(0, total, batch_size):
            batch = functions[i:i+batch_size]
            
            logger.info(f"Processing batch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}...")
            
            for func in batch:
                try:
                    (func_id, name, description, is_exported, parameters, code,
                     module_name, config_name, object_type, object_name) = func
                    
                    # Generate embedding
                    embedding = self.embedding_service.encode_function({
                        'name': name,
                        'description': description,
                        'parameters': parameters or []
                    })
                    
                    # Prepare metadata
                    metadata = {
                        'function_id': str(func_id),
                        'name': name,
                        'description': description or '',
                        'module': module_name,
                        'configuration': config_name,
                        'object_type': object_type or '',
                        'object_name': object_name or '',
                        'is_exported': is_exported,
                        'code_preview': code[:500] if code else ''
                    }
                    
                    # Add to Qdrant
                    point_id = str(uuid.uuid4())
                    self.qdrant_client.add_code(point_id, embedding, metadata)
                    
                    self.stats['functions_indexed'] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing function {name}: {e}")
                    self.stats['errors'] += 1
            
            if (i + batch_size) % 200 == 0:
                logger.info(f"  Progress: {min(i + batch_size, total)}/{total} functions")
    
    def run_migration(self):
        """Run full migration"""
        logger.info("="*60)
        logger.info("Qdrant Vectorization Migration")
        logger.info("Enterprise 1C AI Development Stack")
        logger.info("="*60)
        
        # Connect
        if not self.connect():
            logger.error("Cannot proceed")
            return False
        
        # Setup
        self.setup_collections()
        
        # Migrate
        self.migrate_functions()
        
        # Stats
        self.print_statistics()
        
        # Verify
        self.verify()
        
        return True
    
    def print_statistics(self):
        """Print migration statistics"""
        logger.info("\n" + "="*60)
        logger.info("MIGRATION STATISTICS")
        logger.info("="*60)
        logger.info(f"Functions indexed: {self.stats['functions_indexed']}")
        logger.info(f"Errors:            {self.stats['errors']}")
        logger.info("="*60)
    
    def verify(self):
        """Verify Qdrant collections"""
        logger.info("\n" + "="*60)
        logger.info("VERIFICATION")
        logger.info("="*60)
        
        try:
            stats = self.qdrant_client.get_statistics()
            
            for collection, info in stats.items():
                logger.info(f"\n{collection}:")
                logger.info(f"  Vectors: {info.get('vectors_count', 0)}")
                logger.info(f"  Points:  {info.get('points_count', 0)}")
                logger.info(f"  Status:  {info.get('status', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Verification error: {e}")
    
    def cleanup(self):
        """Cleanup"""
        if self.pg_client:
            self.pg_client.disconnect()
        logger.info("✓ Disconnected")


def main():
    """Main entry point"""
    migrator = QdrantMigrator()
    
    try:
        success = migrator.run_migration()
        migrator.cleanup()
        
        if success:
            logger.info("\n✓ MIGRATION COMPLETED!")
            logger.info("\nNext: Test semantic search")
            logger.info("  python test_semantic_search.py")
            return 0
        else:
            logger.error("\n✗ MIGRATION FAILED")
            return 1
            
    except KeyboardInterrupt:
        logger.info("\nInterrupted")
        migrator.cleanup()
        return 1
    except Exception as e:
        logger.error(f"\nError: {e}")
        migrator.cleanup()
        return 1


if __name__ == "__main__":
    sys.exit(main())





