"""
Безопасный инструмент для атомарного рефакторинга.
Переносит файлы одного домена и обновляет импорты.

Использование:
python scripts/architecture/safe_domain_mover.py --domain marketplace --keywords marketplace product catalog
"""

import shutil
import argparse
from pathlib import Path
from typing import List

class DomainMover:
    def __init__(self, src_dir: str = "src"):
        self.src_dir = Path(src_dir)
        self.modules_dir = self.src_dir / "modules"
        self.backup_dir = Path("backup_atomic")

    def move_domain(self, domain_name: str, keywords: List[str], dry_run: bool = True):
        print(f"\n🛡️  Атомарный рефакторинг домена: '{domain_name}'")
        print(f"   Ключевые слова: {keywords}")
        print(f"   Режим: {'DRY RUN (Тест)' if dry_run else 'LIVE (Выполнение)'}")

        # 1. Поиск файлов
        files_to_move = []
        for file_path in self.modules_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue
            
            # Проверяем, подходит ли файл под ключевые слова
            if any(k in file_path.name.lower() for k in keywords):
                files_to_move.append(file_path)

        if not files_to_move:
            print("❌ Файлы не найдены.")
            return

        print(f"\n📄 Найдено файлов для переноса: {len(files_to_move)}")
        for f in files_to_move[:5]:
            print(f"   - {f.name}")
        if len(files_to_move) > 5:
            print(f"   ... и еще {len(files_to_move) - 5}")

        # 2. Подготовка путей
        target_dir = self.modules_dir / domain_name
        
        # 3. Выполнение (или симуляция)
        if dry_run:
            print("\n🔍 Анализ изменений импортов (DRY RUN)...")
            self._simulate_import_updates(files_to_move, domain_name)
        else:
            self._create_backup()
            print(f"\n🚀 Перемещение файлов в {target_dir}...")
            target_dir.mkdir(exist_ok=True)
            
            # Создаем __init__.py если нет
            init_file = target_dir / "__init__.py"
            if not init_file.exists():
                init_file.touch()

            # Перемещаем файлы
            moved_files_map = {} # old_name -> new_import_path
            for src_file in files_to_move:
                dst_file = target_dir / src_file.name
                shutil.move(str(src_file), str(dst_file))
                
                # Формируем маппинг для обновления импортов
                # old: src.modules.file_name
                # new: src.modules.domain.file_name
                old_import = f"src.modules.{src_file.stem}"
                new_import = f"src.modules.{domain_name}.{src_file.stem}"
                moved_files_map[old_import] = new_import

            print("🔄 Обновление импортов во всем проекте...")
            self._update_project_imports(moved_files_map)
            print("✅ Готово.")

    def _simulate_import_updates(self, files: List[Path], domain: str):
        print("   Будут обновлены импорты для:")
        for f in files:
            print(f"   src.modules.{f.stem} -> src.modules.{domain}.{f.stem}")

    def _create_backup(self):
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
        shutil.copytree(self.src_dir, self.backup_dir / "src")
        print(f"📦 Бэкап создан в {self.backup_dir}")

    def _update_project_imports(self, mapping: dict):
        count = 0
        for py_file in self.src_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = content
                modified = False
                
                for old_imp, new_imp in mapping.items():
                    # Простая замена строк (можно улучшить через AST, но для начала regex/replace надежнее для путей)
                    # Ищем "from src.modules.X import" или "import src.modules.X"
                    if old_imp in new_content:
                        new_content = new_content.replace(old_imp, new_imp)
                        modified = True
                
                if modified:
                    with open(py_file, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    count += 1
            except Exception as e:
                print(f"⚠️ Ошибка обработки {py_file}: {e}")
        print(f"   Обновлено файлов с импортами: {count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", required=True, help="Имя новой папки домена (например, auth)")
    parser.add_argument("--keywords", nargs="+", required=True, help="Ключевые слова для поиска файлов")
    parser.add_argument("--live", action="store_true", help="Выполнить изменения (по умолчанию dry-run)")
    
    args = parser.parse_args()
    
    mover = DomainMover()
    mover.move_domain(args.domain, args.keywords, dry_run=not args.live)
