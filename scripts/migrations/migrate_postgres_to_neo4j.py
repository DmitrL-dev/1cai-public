
#!/usr/bin/env python3
"""
Миграция данных из PostgreSQL в Neo4j
Создание графа метаданных 1С
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not installed")

try:
    from src.db.neo4j_client import Neo4jClient
    from src.db.postgres_saver import PostgreSQLSaver
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure src/db/ modules exist")
    sys.exit(1)


class PostgresToNeo4jMigrator:
    """Migrates data from PostgreSQL to Neo4j graph"""
    
    def __init__(self):
        self.pg_client = None
        self.neo4j_client = None
        self.stats = {
            'configs': 0,
            'objects': 0,
            'modules': 0,
            'functions': 0,
            'calls': 0,
            'errors': 0
        }
    
    def connect_databases(self) -> bool:
        """Connect to both databases"""
        try:
            # PostgreSQL
            self.pg_client = PostgreSQLSaver()
            if not self.pg_client.connect():
                logger.error("Failed to connect to PostgreSQL")
                return False
            logger.info("✓ Connected to PostgreSQL")
            
            # Neo4j
            self.neo4j_client = Neo4jClient()
            if not self.neo4j_client.connect():
                logger.error("Failed to connect to Neo4j")
                return False
            logger.info("✓ Connected to Neo4j")
            
            return True
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    def setup_neo4j_schema(self):
        """Create constraints and indexes in Neo4j"""
        logger.info("\nSetting up Neo4j schema...")
        self.neo4j_client.create_constraints()
        logger.info("✓ Neo4j schema ready")
    
    def migrate_configurations(self):
        """Migrate all configurations"""
        logger.info("\n" + "="*60)
        logger.info("Migrating Configurations")
        logger.info("="*60)
        
        # Get all configurations from PostgreSQL
        self.pg_client.cur.execute("""
            SELECT id, name, full_name, version, metadata
            FROM configurations
            ORDER BY name
        """)
        
        configs = self.pg_client.cur.fetchall()
        
        for config in configs:
            config_id, name, full_name, version, metadata = config
            
            logger.info(f"\nMigrating configuration: {name}")
            
            # Create in Neo4j
            success = self.neo4j_client.create_configuration({
                'name': name,
                'full_name': full_name,
                'version': version,
                'metadata': metadata or {}
            })
            
            if success:
                self.stats['configs'] += 1
                logger.info(f"  ✓ Created: {name}")
                
                # Migrate objects
                self.migrate_objects(config_id, name)
                
                # Migrate modules
                self.migrate_modules(config_id, name)
            else:
                logger.error(f"  ✗ Failed: {name}")
                self.stats['errors'] += 1
    
    def migrate_objects(self, config_id: str, config_name: str):
        """Migrate objects for a configuration"""
        self.pg_client.cur.execute("""
            SELECT object_type, name, synonym, description
            FROM objects
            WHERE configuration_id = %s
            ORDER BY object_type, name
        """, (config_id,))
        
        objects = self.pg_client.cur.fetchall()
        logger.info(f"  Migrating {len(objects)} objects...")
        
        for obj in objects:
            obj_type, name, synonym, description = obj
            
            success = self.neo4j_client.create_object(config_name, {
                'type': obj_type,
                'name': name,
                'synonym': synonym,
                'description': description
            })
            
            if success:
                self.stats['objects'] += 1
            else:
                self.stats['errors'] += 1
    
    def migrate_modules(self, config_id: str, config_name: str):
        """Migrate modules for a configuration"""
        self.pg_client.cur.execute("""
            SELECT 
                m.id, m.name, m.module_type, m.code_hash,
                m.description, m.line_count,
                o.object_type, o.name as object_name
            FROM modules m
            LEFT JOIN objects o ON o.id = m.object_id
            WHERE m.configuration_id = %s
            ORDER BY m.name
        """, (config_id,))
        
        modules = self.pg_client.cur.fetchall()
        logger.info(f"  Migrating {len(modules)} modules...")
        
        for idx, mod in enumerate(modules, 1):
            (mod_id, name, module_type, code_hash, description, 
             line_count, object_type, object_name) = mod
            
            full_name = f"{config_name}.{name}"
            
            success = self.neo4j_client.create_module(config_name, {
                'full_name': full_name,
                'name': name,
                'module_type': module_type,
                'code_hash': code_hash,
                'description': description,
                'line_count': line_count,
                'object_type': object_type,
                'object_name': object_name
            })
            
            if success:
                self.stats['modules'] += 1
                
                # Migrate functions for this module
                self.migrate_functions(mod_id, full_name)
                
                if idx % 50 == 0:
                    logger.info(f"    Progress: {idx}/{len(modules)} modules")
            else:
                self.stats['errors'] += 1
    
    def migrate_functions(self, module_id: str, module_full_name: str):
        """Migrate functions for a module"""
        self.pg_client.cur.execute("""
            SELECT 
                name, function_type, is_exported, parameters,
                return_type, region, description, complexity_score
            FROM functions
            WHERE module_id = %s
            ORDER BY name
        """, (module_id,))
        
        functions = self.pg_client.cur.fetchall()
        
        for func in functions:
            (name, func_type, is_exported, parameters, 
             return_type, region, description, complexity) = func
            
            success = self.neo4j_client.create_function(module_full_name, {
                'name': name,
                'type': func_type,
                'is_exported': is_exported,
                'parameters': parameters or [],
                'return_type': return_type,
                'region': region,
                'description': description,
                'complexity': complexity or 1
            })
            
            if success:
                self.stats['functions'] += 1
            else:
                self.stats['errors'] += 1
    
    def run_migration(self):
        """Run full migration"""
        logger.info("="*60)
        logger.info("PostgreSQL to Neo4j Migration")
        logger.info("Enterprise 1C AI Development Stack")
        logger.info("="*60)
        
        # Connect
        if not self.connect_databases():
            logger.error("Cannot proceed without database connections")
            return False
        
        # Setup Neo4j schema
        self.setup_neo4j_schema()
        
        # Migrate data
        self.migrate_configurations()
        
        # Print statistics
        self.print_statistics()
        
        # Verify
        self.verify_migration()
        
        return True
    
    def print_statistics(self):
        """Print migration statistics"""
        logger.info("\n" + "="*60)
        logger.info("MIGRATION STATISTICS")
        logger.info("="*60)
        logger.info(f"Configurations: {self.stats['configs']}")
        logger.info(f"Objects:        {self.stats['objects']}")
        logger.info(f"Modules:        {self.stats['modules']}")
        logger.info(f"Functions:      {self.stats['functions']}")
        logger.info(f"Errors:         {self.stats['errors']}")
        logger.info("="*60)
    
    def verify_migration(self):
        """Verify data in Neo4j"""
        logger.info("\n" + "="*60)
        logger.info("VERIFICATION")
        logger.info("="*60)
        
        try:
            # Get statistics from Neo4j
            neo4j_stats = self.neo4j_client.get_statistics()
            
            logger.info("Neo4j contains:")
            logger.info(f"  Configurations: {neo4j_stats.get('configurations', 0)}")
            logger.info(f"  Objects:        {neo4j_stats.get('objects', 0)}")
            logger.info(f"  Modules:        {neo4j_stats.get('modules', 0)}")
            logger.info(f"  Functions:      {neo4j_stats.get('functions', 0)}")
            logger.info(f"  Function calls: {neo4j_stats.get('function_calls', 0)}")
            
            # Compare with PostgreSQL
            pg_stats = self.pg_client.get_statistics()
            
            logger.info("\nPostgreSQL has:")
            logger.info(f"  Modules:   {pg_stats.get('modules', 0)}")
            logger.info(f"  Functions: {pg_stats.get('functions', 0)}")
            
            if neo4j_stats.get('modules') == pg_stats.get('modules'):
                logger.info("\n✓ Migration successful! Module counts match.")
            else:
                logger.warning("\n⚠ Warning: Module count mismatch!")
            
        except Exception as e:
            logger.error(f"Verification error: {e}")
    
    def cleanup(self):
        """Cleanup connections"""
        if self.pg_client:
            self.pg_client.disconnect()
        if self.neo4j_client:
            self.neo4j_client.disconnect()
        logger.info("✓ Disconnected from databases")


def main():
    """Main entry point"""
    migrator = PostgresToNeo4jMigrator()
    
    try:
        success = migrator.run_migration()
        migrator.cleanup()
        
        if success:
            logger.info("\n" + "="*60)
            logger.info("✓ MIGRATION COMPLETED SUCCESSFULLY!")
            logger.info("="*60)
            logger.info("\nNext steps:")
            logger.info("1. Open Neo4j Browser: http://localhost:7474")
            logger.info("2. Login: neo4j / (your NEO4J_PASSWORD)")
            logger.info("3. Run query: MATCH (c:Configuration) RETURN c")
            return 0
        else:
            logger.error("\n✗ MIGRATION FAILED")
            return 1
            
    except KeyboardInterrupt:
        logger.info("\nMigration interrupted")
        migrator.cleanup()
        return 1
    except Exception as e:
        logger.error(f"\nUnexpected error: {e}")
        migrator.cleanup()
        return 1


if __name__ == "__main__":
    sys.exit(main())





