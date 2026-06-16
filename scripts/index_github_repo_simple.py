
#!/usr/bin/env python3
"""
Упрощенная индексация публичной GitHub репозитории
Клонирует репозиторий и показывает статистику по BSL/1C файлам

Usage:
    python scripts/index_github_repo_simple.py --repo DmitrL-dev/1cai-public
"""

import argparse
import json
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


class SimpleGitHubRepoIndexer:
    """Упрощенная индексация GitHub репозитории (без БД)"""
    
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
        
        # Stats
        self.stats = {
            'files_found': 0,
            'files_processed': 0,
            'functions_found': 0,
            'modules_found': 0,
            'total_lines': 0,
            'errors': 0
        }
        self.files_info = []
    
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
        
        # Расширения файлов BSL/1C и других релевантных
        extensions = ['.bsl', '.os', '.txt', '.py', '.js', '.ts', '.md', '.yaml', '.yml', '.json']
        
        logger.info(f"Searching for BSL files in {self.repo_dir}...")
        
        for ext in extensions:
            for file_path in self.repo_dir.rglob(f"*{ext}"):
                # Пропускаем служебные директории (проверяем части пути)
                path_parts = file_path.parts
                if any(part.startswith('.') and part != '.' for part in path_parts):  # .git, .venv и т.д.
                    continue
                if any(skip in part for part in path_parts for skip in ['node_modules', '__pycache__']):
                    continue
                
                try:
                    if file_path.stat().st_size > 10 * 1024 * 1024:  # > 10MB
                        logger.warning(f"Skipping large file: {file_path}")
                        continue
                except OSError:
                    continue
                
                bsl_files.append(file_path)
        
        self.stats['files_found'] = len(bsl_files)
        logger.info(f"Found {len(bsl_files)} BSL files")
        return bsl_files
    
    def parse_bsl_file_simple(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Упрощенный парсинг BSL файла (regex-based)"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
            
            if not code.strip():
                return None
            
            lines = code.split('\n')
            self.stats['total_lines'] += len(lines)
            
            # Простой regex парсинг функций
            import re

            # Паттерн для функций/процедур
            func_pattern = r'(?:Функция|Процедура)\s+(\w+)\s*\([^)]*\)\s*(?:Экспорт)?'
            functions = re.findall(func_pattern, code, re.IGNORECASE | re.MULTILINE)
            
            # Подсчет регионов
            region_pattern = r'#Область\s+(\w+)'
            regions = re.findall(region_pattern, code, re.IGNORECASE)
            
            file_info = {
                'file_path': str(file_path.relative_to(self.repo_dir)),
                'repo': self.repo,
                'size_bytes': file_path.stat().st_size,
                'lines_count': len(lines),
                'functions_count': len(functions),
                'functions': functions[:10],  # Первые 10 функций
                'regions_count': len(regions),
                'regions': regions[:5],  # Первые 5 регионов
                'indexed_at': datetime.now().isoformat()
            }
            
            self.stats['functions_found'] += len(functions)
            if functions:
                self.stats['modules_found'] += 1
            
            return file_info
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            self.stats['errors'] += 1
            return None
    
    def index_repo(self, skip_clone: bool = False) -> bool:
        """Основной метод индексации"""
        logger.info(f"{'='*60}")
        logger.info(f"Indexing repository: {self.repo}")
        logger.info(f"{'='*60}")
        
        # 1. Клонирование репозитории
        if not self.clone_repo(skip_clone=skip_clone):
            return False
        
        # 2. Поиск BSL файлов
        bsl_files = self.find_bsl_files()
        if not bsl_files:
            logger.warning("No BSL files found in repository")
            return True  # Не ошибка, просто нет файлов
        
        # 3. Парсинг файлов
        logger.info(f"\nProcessing {len(bsl_files)} files...")
        for i, file_path in enumerate(bsl_files, 1):
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(bsl_files)} files processed...")
            
            file_info = self.parse_bsl_file_simple(file_path)
            if file_info:
                self.files_info.append(file_info)
                self.stats['files_processed'] += 1
        
        # 4. Сохранение статистики
        self.save_statistics()
        
        # 5. Вывод статистики
        logger.info(f"\n{'='*60}")
        logger.info("Indexing completed!")
        logger.info(f"{'='*60}")
        logger.info(f"Files found: {self.stats['files_found']}")
        logger.info(f"Files processed: {self.stats['files_processed']}")
        logger.info(f"Modules found: {self.stats['modules_found']}")
        logger.info(f"Functions found: {self.stats['functions_found']}")
        logger.info(f"Total lines: {self.stats['total_lines']:,}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"\nStatistics saved to: output/indexing/{self.repo.replace('/', '_')}_stats.json")
        
        return True
    
    def save_statistics(self):
        """Сохранение статистики в JSON"""
        output_dir = Path("output/indexing")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        stats_file = output_dir / f"{self.repo.replace('/', '_')}_stats.json"
        
        data = {
            'repo': self.repo,
            'indexed_at': datetime.now().isoformat(),
            'statistics': self.stats,
            'files': self.files_info[:100]  # Первые 100 файлов
        }
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ Statistics saved to {stats_file}")
    
    def cleanup(self):
        """Очистка временных файлов"""
        if self.repo_dir.exists():
            logger.info(f"Cleaning up {self.repo_dir}...")
            shutil.rmtree(self.repo_dir)


def main():
    parser = argparse.ArgumentParser(description="Simple GitHub repository indexer (no DB required)")
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
    
    indexer = SimpleGitHubRepoIndexer(repo=args.repo, work_dir=args.work_dir)
    
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

