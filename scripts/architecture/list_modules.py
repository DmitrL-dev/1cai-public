from pathlib import Path

def list_modules():
    p = Path("src/modules")
    if not p.exists():
        print(f"❌ Путь {p} не существует!")
        return

    files = [f.name for f in p.glob("*.py") if not f.name.startswith("__")]
    print(f"📂 Файлов в {p}: {len(files)}")
    print("-" * 20)
    
    # Выведем первые 50 для анализа
    for f in sorted(files)[:50]:
        print(f)

if __name__ == "__main__":
    list_modules()
