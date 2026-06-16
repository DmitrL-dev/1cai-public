
#!/usr/bin/env python3
"""
Индексация публичной GitHub репозитории
Клонирует репозиторий, парсит BSL/1C код и индексирует в PostgreSQL, Neo4j, Qdrant

Usage:
    python scripts/index_github_repo.py --repo DmitrL-dev/1cai-public
    python scripts/index_github_repo.py --repo DmitrL-dev/1cai-public --skip-clone
"""

import argparse
import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

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
    try:
        from src.db.neo4j_client import Neo4jClient
    except ImportError:
        Neo4jClient = None
        logger.warning("Neo4jClient not available")
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure you're in the project root and dependencies are installed")
    sys.exit(1)


class GitHubRepoIndexer:
    """Индексация GitHub репозитории в PostgreSQL, Neo4j, Qdrant"""
    
    def __init__(self, repo: str, work_dir: str = "./temp_repos"):
        """
        Args:
            repo: GitHub репозиторий в формате owner/repo (например, DmitrL-dev/1cai-public)
            work_dir: Временная директория для клонирования
        """
        self.repo = repo
        self.work_dir = Path(work_dir)
        self.repo_dir = self.work_dir / repo.replace("/", "_")
        self.repo_url = f"https://github.com/{repo}.git"
        
        # Clients
        self.pg_client = None
        self.neo4j_client = None
        self.qdrant_client = None
        self.embedding_service = None
        
        # Stats
        self.stats = {
            'files_processed': 0,
            'functions_indexed': 0,
            'modules_indexed': 0,
            'errors': 0
        }
    
    def connect_services(self) -> bool:
        """Подключение ко всем сервисам"""
        try:
            # PostgreSQL
            logger.info("Connecting to PostgreSQL...")
            self.pg_client = PostgreSQLSaver()
            if not self.pg_client.connect():
                logger.error("Failed to connect to PostgreSQL")
                return False
            logger.info("✓ Connected to PostgreSQL")
            
            # Neo4j
            if Neo4jClient:
                logger.info("Connecting to Neo4j...")
                try:
                    self.neo4j_client = Neo4jClient()
                    if not self.neo4j_client.connect():
                        logger.warning("Neo4j not available, skipping graph indexing")
                        self.neo4j_client = None
                    else:
                        logger.info("✓ Connected to Neo4j")
                except Exception as e:
                    logger.warning(f"Neo4j not available: {e}")
                    self.neo4j_client = None
            else:
                logger.info("Neo4jClient not available, skipping graph indexing")
                self.neo4j_client = None
            
            # Qdrant
            logger.info("Connecting to Qdrant...")
            self.qdrant_client = QdrantClient()
            if not self.qdrant_client.connect():
                logger.error("Failed to connect to Qdrant")
                return False
            logger.info("✓ Connected to Qdrant")
            
            # Embedding service
            logger.info("Initializing EmbeddingService...")
            self.embedding_service = EmbeddingService()
            logger.info("✓ EmbeddingService ready")
            
            return True
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    def clone_repo(self, skip_clone: bool = False) -> bool:
        """Клонирование репозитории"""
        if skip_clone and self.repo_dir.exists():
            logger.info(f"Using existing repo at {self.repo_dir}")
            return True
        
        if self.repo_dir.exists():
            logger.info(f"Removing existing directory: {self.repo_dir}")
            shutil.rmtree(self.repo_dir)
        
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Cloning {self.repo_url} to {self.repo_dir}...")
        try:
            subprocess.run(
                ["git", "clone", self.repo_url, str(self.repo_dir)],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"✓ Repository cloned successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone repository: {e}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error("git not found. Please install git")
            return False
    
    def find_bsl_files(self) -> List[Path]:
        """Поиск всех BSL/1C файлов в репозитории"""
        bsl_files = []
        
        # Расширения файлов BSL/1C
        extensions = ['.bsl', '.os', '.txt']  # .txt для модулей 1С
        
        logger.info(f"Searching for BSL files in {self.repo_dir}...")
        
        for ext in extensions:
            for file_path in self.repo_dir.rglob(f"*{ext}"):
                # Пропускаем большие файлы и служебные директории
                if any(skip in str(file_path) for skip in ['.git', 'node_modules', '__pycache__', '.venv']):
                    continue
                
                try:
                    if file_path.stat().st_size > 10 * 1024 * 1024:  # > 10MB
                        logger.warning(f"Skipping large file: {file_path}")
                        continue
                except OSError:
                    continue
                
                bsl_files.append(file_path)
        
        logger.info(f"Found {len(bsl_files)} BSL files")
        return bsl_files
    
    def parse_bsl_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Парсинг BSL файла"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
            
            if not code.strip():
                return None
            
            # Используем упрощенный парсер (можно заменить на AST парсер)
            from src.ai.agents.code_review.bsl_parser import BSLParser
            
            parser = BSLParser()
            parsed = parser.parse(code)
            
            # Добавляем метаданные о файле
            parsed['file_path'] = str(file_path.relative_to(self.repo_dir))
            parsed['repo'] = self.repo
            parsed['indexed_at'] = datetime.now().isoformat()
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            self.stats['errors'] += 1
            return None
    
    def index_to_postgres(self, parsed_data: Dict[str, Any], file_path: Path) -> bool:
        """Индексация в PostgreSQL"""
        try:
            # Определяем конфигурацию из пути файла
            config_name = "PUBLIC_REPO"
            module_name = parsed_data.get('file_path', 'unknown')
            
            # Сохраняем конфигурацию
            config_id = self.pg_client.save_configuration({
                'name': config_name,
                'full_name': f"GitHub: {self.repo}",
                'version': '1.0.0',
                'metadata': {
                    'source': 'github',
                    'repo': self.repo,
                    'indexed_at': datetime.now().isoformat()
                }
            })
            
            # Сохраняем модуль
            module_id = self.pg_client.save_module({
                'configuration_id': config_id,
                'name': module_name,
                'type': 'Module',
                'code': parsed_data.get('code', ''),
                'metadata': {
                    'file_path': parsed_data.get('file_path'),
                    'repo': self.repo
                }
            })
            
            # Сохраняем функции
            functions = parsed_data.get('functions', [])
            for func in functions:
                self.pg_client.save_function({
                    'module_id': module_id,
                    'name': func.get('name', 'unknown'),
                    'description': func.get('description', ''),
                    'is_exported': func.get('is_exported', False),
                    'parameters': func.get('parameters', []),
                    'code': func.get('code', ''),
                    'code_preview': func.get('code', '')[:500]
                })
                self.stats['functions_indexed'] += 1
            
            self.stats['modules_indexed'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error indexing to PostgreSQL: {e}")
            self.stats['errors'] += 1
            return False
    
    def index_to_qdrant(self, parsed_data: Dict[str, Any], file_path: Path) -> bool:
        """Индексация в Qdrant с векторизацией"""
        try:
            functions = parsed_data.get('functions', [])
            
            for func in functions:
                # Генерируем embedding
                func_text = f"{func.get('name', '')} {func.get('description', '')} {func.get('code', '')[:1000]}"
                embedding = self.embedding_service.encode_function({
                    'name': func.get('name', ''),
                    'description': func.get('description', ''),
                    'code': func.get('code', '')[:1000]
                })
                
                # Метаданные
                metadata = {
                    'function_name': func.get('name', ''),
                    'description': func.get('description', ''),
                    'module': parsed_data.get('file_path', ''),
                    'configuration': 'PUBLIC_REPO',
                    'repo': self.repo,
                    'code_preview': func.get('code', '')[:500]
                }
                
                # Добавляем в Qdrant
                import uuid
                point_id = str(uuid.uuid4())
                self.qdrant_client.add_code(point_id, embedding, metadata)
            
            return True
            
        except Exception as e:
            logger.error(f"Error indexing to Qdrant: {e}")
            self.stats['errors'] += 1
            return False
    
    def index_to_neo4j(self, parsed_data: Dict[str, Any], file_path: Path) -> bool:
        """Индексация в Neo4j (граф зависимостей)"""
        if not self.neo4j_client:
            return True  # Neo4j не обязателен
        
        try:
            # Создаем узлы и связи
            config_name = "PUBLIC_REPO"
            module_name = parsed_data.get('file_path', 'unknown')
            
            # Узел конфигурации
            self.neo4j_client.create_configuration_node(config_name, {
                'repo': self.repo,
                'source': 'github'
            })
            
            # Узел модуля
            self.neo4j_client.create_module_node(config_name, module_name, {
                'file_path': parsed_data.get('file_path'),
                'repo': self.repo
            })
            
            # Узлы функций
            functions = parsed_data.get('functions', [])
            for func in functions:
                func_name = func.get('name', 'unknown')
                self.neo4j_client.create_function_node(
                    config_name,
                    module_name,
                    func_name,
                    {
                        'description': func.get('description', ''),
                        'is_exported': func.get('is_exported', False)
                    }
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error indexing to Neo4j: {e}")
            self.stats['errors'] += 1
            return False
    
    def index_repo(self, skip_clone: bool = False) -> bool:
        """Основной метод индексации"""
        logger.info(f"{'='*60}")
        logger.info(f"Indexing repository: {self.repo}")
        logger.info(f"{'='*60}")
        
        # 1. Подключение к сервисам
        if not self.connect_services():
            return False
        
        # 2. Клонирование репозитории
        if not self.clone_repo(skip_clone=skip_clone):
            return False
        
        # 3. Поиск BSL файлов
        bsl_files = self.find_bsl_files()
        if not bsl_files:
            logger.warning("No BSL files found in repository")
            return True  # Не ошибка, просто нет файлов
        
        # 4. Парсинг и индексация
        logger.info(f"\nProcessing {len(bsl_files)} files...")
        for i, file_path in enumerate(bsl_files, 1):
            logger.info(f"[{i}/{len(bsl_files)}] Processing {file_path.name}...")
            
            # Парсинг
            parsed_data = self.parse_bsl_file(file_path)
            if not parsed_data:
                continue
            
            # Индексация
            self.index_to_postgres(parsed_data, file_path)
            self.index_to_qdrant(parsed_data, file_path)
            self.index_to_neo4j(parsed_data, file_path)
            
            self.stats['files_processed'] += 1
        
        # 5. Статистика
        logger.info(f"\n{'='*60}")
        logger.info("Indexing completed!")
        logger.info(f"{'='*60}")
        logger.info(f"Files processed: {self.stats['files_processed']}")
        logger.info(f"Modules indexed: {self.stats['modules_indexed']}")
        logger.info(f"Functions indexed: {self.stats['functions_indexed']}")
        logger.info(f"Errors: {self.stats['errors']}")
        
        return True
    
    def cleanup(self):
        """Очистка временных файлов"""
        if self.repo_dir.exists():
            logger.info(f"Cleaning up {self.repo_dir}...")
            shutil.rmtree(self.repo_dir)


def main():
    parser = argparse.ArgumentParser(description="Index GitHub repository")
    parser.add_argument(
        "--repo",
        type=str,
        default="DmitrL-dev/1cai-public",
        help="GitHub repository in format owner/repo (default: DmitrL-dev/1cai-public)"
    )
    parser.add_argument(
        "--skip-clone",
        action="store_true",
        help="Skip cloning if repo already exists"
    )
    parser.add_argument(
        "--work-dir",
        type=str,
        default="./temp_repos",
        help="Working directory for cloning (default: ./temp_repos)"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up cloned repository after indexing"
    )
    
    args = parser.parse_args()
    
    indexer = GitHubRepoIndexer(repo=args.repo, work_dir=args.work_dir)
    
    try:
        success = indexer.index_repo(skip_clone=args.skip_clone)
        if success:
            logger.info("✅ Repository indexed successfully!")
            sys.exit(0)
        else:
            logger.error("❌ Failed to index repository")
            sys.exit(1)
    finally:
        if args.cleanup:
            indexer.cleanup()


if __name__ == "__main__":
    main()

