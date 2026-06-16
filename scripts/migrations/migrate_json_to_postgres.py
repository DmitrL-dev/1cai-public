
#!/usr/bin/env python3
"""
Миграция данных из JSON (knowledge_base) в PostgreSQL
Enterprise 1C AI Development Stack
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Setup logging
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
    from src.db.postgres_saver import PostgreSQLSaver
except ImportError:
    logger.error("PostgreSQLSaver not found. Make sure src/db/postgres_saver.py exists")
    sys.exit(1)


class JSONToPostgresMigrator:
    """Migrates data from JSON knowledge base to PostgreSQL"""
    
    def __init__(self):
        self.kb_path = Path("./knowledge_base")
        self.db_saver = None
        self.stats = {
            'configs': 0,
            'modules': 0,
            'functions': 0,
            'errors': 0
        }
    
    def connect_db(self) -> bool:
        """Connect to PostgreSQL"""
        try:
            self.db_saver = PostgreSQLSaver()
            if self.db_saver.connect():
                logger.info("✓ Connected to PostgreSQL")
                return True
            else:
                logger.error("✗ Failed to connect to PostgreSQL")
                return False
        except Exception as e:
            logger.error(f"✗ Database connection error: {e}")
            return False
    
    def find_json_files(self) -> List[Path]:
        """Find all JSON knowledge base files"""
        json_files = []
        
        # Look for .json files in knowledge_base/
        for json_file in self.kb_path.glob("*.json"):
            if json_file.name != "package.json":  # Skip if any
                json_files.append(json_file)
        
        return json_files
    
    def load_json_file(self, json_file: Path) -> Dict[str, Any]:
        """Load JSON file"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"✓ Loaded {json_file.name}")
            return data
        except Exception as e:
            logger.error(f"✗ Error loading {json_file.name}: {e}")
            self.stats['errors'] += 1
            return {}
    
    def migrate_configuration(self, config_name: str, data: Dict[str, Any]) -> bool:
        """Migrate one configuration from JSON to PostgreSQL"""
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"Migrating: {config_name}")
            logger.info(f"{'='*60}")
            
            # Create configuration
            config_id = self.db_saver.save_configuration({
                'name': config_name.upper(),
                'full_name': data.get('name', f'Конфигурация {config_name}'),
                'version': data.get('version'),
                'metadata': {
                    'source': 'json_migration',
                    'migrated_at': datetime.now().isoformat(),
                    'original_file': f'{config_name}.json'
                }
            })
            
            if not config_id:
                logger.error(f"✗ Failed to create configuration: {config_name}")
                self.stats['errors'] += 1
                return False
            
            logger.info(f"✓ Created configuration: {config_name} (ID: {config_id})")
            self.stats['configs'] += 1
            
            # Migrate modules
            modules = data.get('modules', [])
            logger.info(f"  Migrating {len(modules)} modules...")
            
            for idx, module in enumerate(modules, 1):
                try:
                    # Create object if needed
                    object_id = None
                    object_type = module.get('object_type')
                    object_name = module.get('object_name')
                    
                    if object_type and object_name:
                        object_id = self.db_saver.save_object(config_id, {
                            'type': object_type,
                            'name': object_name,
                            'description': module.get('description', '')
                        })
                    
                    # Prepare module data
                    module_data = {
                        'name': module.get('name', f'Module_{idx}'),
                        'module_type': module.get('module_type'),
                        'code': module.get('code', ''),
                        'description': module.get('description', ''),
                        'source_file': module.get('source_file', ''),
                        'functions': [],
                        'procedures': [],
                        'api_usage': module.get('api_usage', []),
                        'regions': module.get('regions', [])
                    }
                    
                    # Combine functions and procedures
                    all_functions = []
                    
                    # Add functions
                    for func in module.get('functions', []):
                        func['type'] = 'Function'
                        all_functions.append(func)
                    
                    # Add procedures
                    for proc in module.get('procedures', []):
                        proc['type'] = 'Procedure'
                        all_functions.append(proc)
                    
                    module_data['functions'] = all_functions
                    
                    # Save module
                    module_id = self.db_saver.save_module(config_id, module_data, object_id)
                    
                    if module_id:
                        self.stats['modules'] += 1
                        self.stats['functions'] += len(all_functions)
                        
                        if idx % 10 == 0:
                            logger.info(f"  Progress: {idx}/{len(modules)} modules...")
                    else:
                        logger.warning(f"  ⚠ Failed to save module: {module_data['name']}")
                        self.stats['errors'] += 1
                
                except Exception as e:
                    logger.error(f"  ✗ Error migrating module #{idx}: {e}")
                    self.stats['errors'] += 1
                    continue
            
            logger.info(f"✓ Completed: {config_name}")
            logger.info(f"  Modules: {len(modules)}")
            return True
            
        except Exception as e:
            logger.error(f"✗ Error migrating configuration {config_name}: {e}")
            self.stats['errors'] += 1
            return False
    
    def run_migration(self):
        """Run full migration"""
        logger.info("="*60)
        logger.info("JSON to PostgreSQL Migration")
        logger.info("Enterprise 1C AI Development Stack")
        logger.info("="*60)
        
        # Connect to database
        if not self.connect_db():
            logger.error("Cannot proceed without database connection")
            return False
        
        # Find JSON files
        json_files = self.find_json_files()
        
        if not json_files:
            logger.warning("No JSON files found in knowledge_base/")
            logger.info(f"Looking in: {self.kb_path.absolute()}")
            return False
        
        logger.info(f"\nFound {len(json_files)} configuration(s):")
        for jf in json_files:
            logger.info(f"  - {jf.name}")
        
        # Migrate each configuration
        for json_file in json_files:
            config_name = json_file.stem  # Filename without .json
            data = self.load_json_file(json_file)
            
            if data:
                self.migrate_configuration(config_name, data)
        
        # Print statistics
        self.print_statistics()
        
        # Verify migration
        self.verify_migration()
        
        return True
    
    def print_statistics(self):
        """Print migration statistics"""
        logger.info("\n" + "="*60)
        logger.info("MIGRATION STATISTICS")
        logger.info("="*60)
        logger.info(f"Configurations migrated: {self.stats['configs']}")
        logger.info(f"Modules migrated:        {self.stats['modules']}")
        logger.info(f"Functions migrated:      {self.stats['functions']}")
        logger.info(f"Errors:                  {self.stats['errors']}")
        logger.info("="*60)
    
    def verify_migration(self):
        """Verify data in PostgreSQL"""
        logger.info("\n" + "="*60)
        logger.info("VERIFICATION")
        logger.info("="*60)
        
        try:
            # Get statistics from database
            db_stats = self.db_saver.get_statistics()
            
            logger.info(f"Database contains:")
            logger.info(f"  Configurations: {db_stats.get('configurations', 0)}")
            logger.info(f"  Objects:        {db_stats.get('objects', 0)}")
            logger.info(f"  Modules:        {db_stats.get('modules', 0)}")
            logger.info(f"  Functions:      {db_stats.get('functions', 0)}")
            logger.info(f"  Total lines:    {db_stats.get('total_lines', 0):,}")
            
            # Check if numbers match
            if db_stats.get('modules', 0) == self.stats['modules']:
                logger.info("\n✓ Migration successful! Numbers match.")
            else:
                logger.warning("\n⚠ Warning: Module count mismatch!")
                logger.warning(f"  Expected: {self.stats['modules']}")
                logger.warning(f"  Got:      {db_stats.get('modules', 0)}")
            
        except Exception as e:
            logger.error(f"✗ Verification error: {e}")
    
    def cleanup(self):
        """Cleanup resources"""
        if self.db_saver:
            self.db_saver.disconnect()
            logger.info("✓ Disconnected from database")


def main():
    """Main entry point"""
    migrator = JSONToPostgresMigrator()
    
    try:
        success = migrator.run_migration()
        migrator.cleanup()
        
        if success:
            logger.info("\n" + "="*60)
            logger.info("✓ MIGRATION COMPLETED SUCCESSFULLY!")
            logger.info("="*60)
            logger.info("\nNext steps:")
            logger.info("1. Open PgAdmin: http://localhost:5050")
            logger.info("2. Connect to database 'knowledge_base'")
            logger.info("3. Run query: SELECT * FROM v_configuration_summary;")
            return 0
        else:
            logger.error("\n" + "="*60)
            logger.error("✗ MIGRATION FAILED")
            logger.error("="*60)
            return 1
            
    except KeyboardInterrupt:
        logger.info("\n\nMigration interrupted by user")
        migrator.cleanup()
        return 1
    except Exception as e:
        logger.error(f"\n\nUnexpected error: {e}")
        migrator.cleanup()
        return 1


if __name__ == "__main__":
    sys.exit(main())





