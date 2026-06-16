"""
Скрипт для рефакторинга Self-Healing компонентов в src/ai.
Переносит файлы в src/ai/healing/ и обновляет импорты.
"""

import shutil
from pathlib import Path

class HealingRefactorer:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.src_dir = Path("src")
        self.ai_dir = self.src_dir / "ai"
        self.target_dir = self.ai_dir / "healing"
        
        # Маппинг: старое имя файла -> новое имя (внутри target_dir)
        self.moves = {
            "self_healing_code.py": "code.py",
            "self_healing_code_advanced.py": "advanced.py"
        }

    def run(self):
        print(f"🔧 Рефакторинг Self-Healing (Dry Run: {self.dry_run})")
        
        # 1. Проверка файлов
        for old_name in self.moves:
            if not (self.ai_dir / old_name).exists():
                print(f"❌ Файл не найден: {old_name}")
                return

        # 2. Создание директории
        if not self.dry_run:
            self.target_dir.mkdir(exist_ok=True)
            (self.target_dir / "__init__.py").touch()
        else:
            print(f"   [Plan] Создать директорию {self.target_dir}")

        # 3. Перемещение файлов и сбор правил замены
        replacements = {}
        
        for old_name, new_name in self.moves.items():
            old_path = self.ai_dir / old_name
            new_path = self.target_dir / new_name
            
            if self.dry_run:
                print(f"   [Plan] Переместить {old_name} -> healing/{new_name}")
            else:
                shutil.move(str(old_path), str(new_path))
                print(f"   ✅ Перемещен {old_name}")

            # Формируем правила замены импортов
            # old: src.ai.self_healing_code
            # new: src.ai.healing.code
            old_module = f"src.ai.{old_name[:-3]}"
            new_module = f"src.ai.healing.{new_name[:-3]}"
            replacements[old_module] = new_module

        # 4. Обновление импортов
        self._update_imports(replacements)

    def _update_imports(self, replacements):
        print("\n🔍 Поиск и обновление импортов...")
        count = 0
        
        for py_file in self.src_dir.rglob("*.py"):
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                new_content = content
                modified = False
                
                for old_mod, new_mod in replacements.items():
                    # Простая замена строк импорта
                    if f"from {old_mod}" in new_content:
                        new_content = new_content.replace(f"from {old_mod}", f"from {new_mod}")
                        modified = True
                    
                    if f"import {old_mod}" in new_content:
                        new_content = new_content.replace(f"import {old_mod}", f"import {new_mod}")
                        modified = True

                if modified:
                    print(f"   📝 Обнаружено в: {py_file.name}")
                    if not self.dry_run:
                        with open(py_file, "w", encoding="utf-8") as f:
                            f.write(new_content)
                    count += 1
            except Exception:
                pass
        
        if self.dry_run:
            print(f"   [Plan] Будет обновлено файлов: {count}")
        else:
            print(f"   ✅ Обновлено файлов: {count}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Выполнить изменения")
    args = parser.parse_args()
    
    refactorer = HealingRefactorer(dry_run=not args.live)
    refactorer.run()
