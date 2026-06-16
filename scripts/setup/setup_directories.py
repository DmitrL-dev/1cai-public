
#!/usr/bin/env python3
"""
Скрипт для подготовки корневой директории проекта
Создает необходимые директории для работы системы
"""

from pathlib import Path


def create_directories():
    """Создание необходимых директорий"""
    
    # Корневая директория проекта
    root = Path(".")
    
    # Директории для конфигураций 1С
    config_dirs = [
        "1c_configurations/ERP",
        "1c_configurations/UT",
        "1c_configurations/ZUP",
        "1c_configurations/BUH",
        "1c_configurations/HOLDING"
    ]
    
    # Директории для базы знаний
    knowledge_dirs = [
        "knowledge_base",
        "knowledge_base/ERP",
        "knowledge_base/UT",
        "knowledge_base/ZUP",
        "knowledge_base/BUH",
        "knowledge_base/HOLDING"
    ]
    
    # Директории для логов
    log_dirs = [
        "logs"
    ]
    
    # Директории для результатов анализа
    output_dirs = [
        "output",
        "output/analyses",
        "output/tests",
        "output/documentation"
    ]
    
    # Директории для кэша
    cache_dirs = [
        "cache"
    ]
    
    # Все директории для создания
    all_dirs = config_dirs + knowledge_dirs + log_dirs + output_dirs + cache_dirs
    
    print("Создание директорий...")
    print("=" * 60)
    
    created = []
    existing = []
    
    for dir_path in all_dirs:
        full_path = root / dir_path
        if full_path.exists():
            existing.append(dir_path)
            print(f"[OK] Уже существует: {dir_path}")
        else:
            full_path.mkdir(parents=True, exist_ok=True)
            created.append(dir_path)
            print(f"[+] Создана: {dir_path}")
    
    print("=" * 60)
    print(f"\nСтатистика:")
    print(f"  [+] Создано новых: {len(created)}")
    print(f"  [OK] Уже существовало: {len(existing)}")
    
    # Создание README файлов
    create_readme_files(root, config_dirs)
    
    print("\n[OK] Подготовка корневой директории завершена!")


def create_readme_files(root: Path, config_dirs: list):
    """Создание README файлов с инструкциями"""
    
    # README для конфигураций
    config_readme = """# Конфигурации 1С

Эта директория предназначена для хранения XML файлов конфигураций 1С.

## Структура

- `ERP/` - Управление предприятием 2
- `UT/` - Управление торговлей
- `ZUP/` - Зарплата и управление персоналом
- `BUH/` - Бухгалтерия предприятия
- `HOLDING/` - Управление холдингом

## Загрузка конфигураций

### Через API:

```bash
curl -X POST "http://localhost:8000/api/knowledge-base/load-from-directory" \\
  -H "Content-Type: application/json" \\
  -d '{"directory_path": "./1c_configurations/ERP/"}'
```

### Формат файлов:

Разместите XML файлы конфигураций 1С в соответствующих поддиректориях.

Например:
- `1c_configurations/ERP/config.xml`
- `1c_configurations/UT/config.xml`
"""

    readme_path = root / "1c_configurations" / "README.md"
    if not readme_path.exists():
        readme_path.write_text(config_readme, encoding="utf-8")
        print(f"[+] Создан README: {readme_path}")
    
    # README для базы знаний
    kb_readme = """# База знаний

Эта директория содержит базу знаний по типовым конфигурациям 1С.

## Структура

База знаний сохраняется в формате JSON:
- `ERP.json` - знания по ERP
- `UT.json` - знания по УТ
- `ZUP.json` - знания по ЗУП
- `BUH.json` - знания по Бухгалтерии
- `HOLDING.json` - знания по Управлению холдингом

## Формат данных

Каждый JSON файл содержит:
- Модули и их документация
- Best practices
- Общие паттерны
- Использование API
- Советы по производительности
- Известные проблемы

## Автоматическое создание

Файлы создаются автоматически при:
- Загрузке конфигураций через API
- Добавлении документации модулей
- Добавлении best practices
"""

    kb_readme_path = root / "knowledge_base" / "README.md"
    if not kb_readme_path.exists():
        kb_readme_path.write_text(kb_readme, encoding="utf-8")
        print(f"[+] Создан README: {kb_readme_path}")
    
    # README для output
    output_readme = """# Результаты анализа

Эта директория содержит результаты анализа кода.

## Структура

- `analyses/` - результаты анализа кода
- `tests/` - сгенерированные тесты
- `documentation/` - сгенерированная документация

## Использование

Результаты сохраняются автоматически при:
- Анализе кода через API
- Генерации тестов
- Генерации документации

Можно также сохранять результаты вручную через CLI или API.
"""

    output_readme_path = root / "output" / "README.md"
    if not output_readme_path.exists():
        output_readme_path.write_text(output_readme, encoding="utf-8")
        print(f"[+] Создан README: {output_readme_path}")


if __name__ == "__main__":
    create_directories()

