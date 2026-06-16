
#!/usr/bin/env python3
"""
Создание dataset для обучения ML моделей
Шаг 2: Создание dataset для обучения ML моделей

Создает enriched dataset с:
- Кодом функций
- Контекстом объекта
- Метаданными
- Паттернами использования
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


def load_parse_results(results_file: Path) -> Dict[str, Any]:
    """Загрузка результатов парсинга"""
    if not results_file.exists():
        raise FileNotFoundError(
            f"Файл {results_file} не найден. Сначала запустите парсер EDT или укажите путь через --input"
        )

    print("Загрузка результатов парсинга...")
    with results_file.open('r', encoding='utf-8') as f:
        return json.load(f)

def extract_api_calls(code: str) -> List[str]:
    """Извлечение API calls из кода"""
    api_patterns = [
        r'Запрос\.',
        r'Справочники\.',
        r'Документы\.',
        r'РегистрыСведений\.',
        r'РегистрыНакопления\.',
        r'ТаблицаЗначений\.',
        r'Структура\.',
        r'Соответствие\.',
        r'СписокЗначений\.'
    ]
    
    apis = set()
    for pattern in api_patterns:
        matches = re.findall(pattern, code, re.IGNORECASE)
        apis.update(matches)
    
    return list(apis)

def classify_function_type(func_name: str, code: str) -> str:
    """Классификация типа функции"""
    name_lower = func_name.lower()
    code_lower = code.lower()
    
    if 'запрос' in name_lower or 'query' in name_lower or 'запрос.' in code_lower:
        return 'query'
    elif 'заполнить' in name_lower or 'fill' in name_lower:
        return 'fill'
    elif 'проверить' in name_lower or 'check' in name_lower or 'validate' in name_lower:
        return 'validation'
    elif 'рассчитать' in name_lower or 'calculate' in name_lower:
        return 'calculation'
    elif 'получить' in name_lower or 'get' in name_lower:
        return 'getter'
    elif 'установить' in name_lower or 'set' in name_lower:
        return 'setter'
    elif 'обработать' in name_lower or 'process' in name_lower:
        return 'processing'
    elif 'сформировать' in name_lower or 'generate' in name_lower:
        return 'generation'
    else:
        return 'other'

def calculate_complexity(code: str) -> int:
    """Простой расчет сложности кода"""
    complexity = 1  # Базовая сложность
    
    # Добавляем за каждую конструкцию
    complexity += len(re.findall(r'\bЕсли\b', code, re.IGNORECASE))
    complexity += len(re.findall(r'\bИначеЕсли\b', code, re.IGNORECASE))
    complexity += len(re.findall(r'\bДля\b', code, re.IGNORECASE))
    complexity += len(re.findall(r'\bПока\b', code, re.IGNORECASE))
    complexity += len(re.findall(r'\bПопытка\b', code, re.IGNORECASE))
    
    return complexity

def create_training_example(func: Dict, module_name: str, object_type: str, 
                            metadata: Dict = None) -> Dict:
    """Создание обучающего примера"""
    func_name = func.get('name', '')
    func_body = func.get('body', '')
    params = func.get('parameters', [])
    
    # Базовый пример
    example = {
        'function_name': func_name,
        'parameters': params,
        'code': func_body,
        'is_export': func.get('is_export', False),
        
        # Контекст
        'context': {
            'module_name': module_name,
            'object_type': object_type
        },
        
        # Метаданные функции
        'metadata': {
            'code_length': len(func_body),
            'params_count': len(params),
            'complexity': calculate_complexity(func_body),
            'function_type': classify_function_type(func_name, func_body)
        },
        
        # API usage
        'api_usage': extract_api_calls(func_body)
    }
    
    # Добавляем метаданные объекта если есть
    if metadata:
        example['context']['object_metadata'] = {
            'attributes': metadata.get('attributes', []),
            'tabular_sections': metadata.get('tabular_sections', [])
        }
    
    return example

def create_dataset_from_common_modules(data: Dict, limit: int = None) -> List[Dict]:
    """Создание dataset из общих модулей"""
    print("\nОбработка общих модулей...")
    
    dataset = []
    modules = data.get('common_modules', [])
    
    if limit:
        modules = modules[:limit]
    
    processed = 0
    for module in modules:
        module_name = module.get('name', '')
        
        # Функции
        for func in module.get('functions', []):
            example = create_training_example(
                func, module_name, 'CommonModule'
            )
            dataset.append(example)
        
        # Процедуры
        for proc in module.get('procedures', []):
            example = create_training_example(
                proc, module_name, 'CommonModule'
            )
            dataset.append(example)
        
        processed += 1
        if processed % 100 == 0:
            print(f"  Обработано модулей: {processed}/{len(modules)}")
    
    print(f"  Создано примеров: {len(dataset):,}")
    return dataset

def create_dataset_from_catalogs(data: Dict, limit: int = None) -> List[Dict]:
    """Создание dataset из справочников"""
    print("\nОбработка справочников...")
    
    dataset = []
    catalogs = data.get('catalogs', [])
    
    if limit:
        catalogs = catalogs[:limit]
    
    for catalog in catalogs:
        catalog_name = catalog.get('name', '')
        metadata = catalog.get('metadata', {})
        
        # Модуль менеджера
        manager = catalog.get('manager_module')
        if manager:
            for func in manager.get('functions', []):
                example = create_training_example(
                    func, f"Catalog.{catalog_name}.ManagerModule", 
                    'CatalogManager', metadata
                )
                dataset.append(example)
        
        # Модуль объекта
        obj_module = catalog.get('object_module')
        if obj_module:
            for func in obj_module.get('functions', []):
                example = create_training_example(
                    func, f"Catalog.{catalog_name}.ObjectModule",
                    'CatalogObject', metadata
                )
                dataset.append(example)
    
    print(f"  Создано примеров: {len(dataset):,}")
    return dataset

def create_dataset_from_documents(data: Dict, limit: int = None) -> List[Dict]:
    """Создание dataset из документов"""
    print("\nОбработка документов...")
    
    dataset = []
    documents = data.get('documents', [])
    
    if limit:
        documents = documents[:limit]
    
    for doc in documents:
        doc_name = doc.get('name', '')
        metadata = doc.get('metadata', {})
        
        # Модуль менеджера
        manager = doc.get('manager_module')
        if manager:
            for func in manager.get('functions', []):
                example = create_training_example(
                    func, f"Document.{doc_name}.ManagerModule",
                    'DocumentManager', metadata
                )
                dataset.append(example)
        
        # Модуль объекта
        obj_module = doc.get('object_module')
        if obj_module:
            for func in obj_module.get('functions', []):
                example = create_training_example(
                    func, f"Document.{doc_name}.ObjectModule",
                    'DocumentObject', metadata
                )
                dataset.append(example)
    
    print(f"  Создано примеров: {len(dataset):,}")
    return dataset

def analyze_dataset(dataset: List[Dict]) -> Dict:
    """Анализ созданного dataset"""
    print("\n" + "=" * 80)
    print("АНАЛИЗ DATASET")
    print("=" * 80)
    
    # Статистика по типам функций
    func_types = defaultdict(int)
    object_types = defaultdict(int)
    complexity_distribution = defaultdict(int)
    api_usage_count = defaultdict(int)
    
    total_code_length = 0
    export_count = 0
    total_examples = len(dataset)
    
    for example in dataset:
        func_type = example['metadata']['function_type']
        func_types[func_type] += 1
        
        obj_type = example['context']['object_type']
        object_types[obj_type] += 1
        
        complexity = example['metadata']['complexity']
        if complexity <= 5:
            complexity_distribution['simple'] += 1
        elif complexity <= 10:
            complexity_distribution['medium'] += 1
        else:
            complexity_distribution['complex'] += 1
        
        total_code_length += example['metadata']['code_length']
        
        if example['is_export']:
            export_count += 1
        
        for api in example['api_usage']:
            api_usage_count[api] += 1
    
    print(f"\nВсего примеров: {total_examples:,}")
    if total_examples:
        export_pct = export_count / total_examples * 100
        avg_code = total_code_length / total_examples
    else:
        export_pct = 0
        avg_code = 0
    print(f"Экспортных функций: {export_count:,} ({export_pct:.1f}%)")
    print(f"Средняя длина кода: {avg_code:.0f} символов")
    
    if total_examples:
        print(f"\nРаспределение по типам функций:")
        for func_type, count in sorted(func_types.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {func_type:<20} {count:>6,} ({count/total_examples*100:>5.1f}%)")
        
        print(f"\nРаспределение по типам объектов:")
        for obj_type, count in sorted(object_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {obj_type:<20} {count:>6,} ({count/total_examples*100:>5.1f}%)")
        
        print(f"\nРаспределение по сложности:")
        for complexity, count in sorted(complexity_distribution.items()):
            print(f"  {complexity:<20} {count:>6,} ({count/total_examples*100:>5.1f}%)")
    
    if api_usage_count:
        print(f"\nТОП-10 используемых API:")
        for api, count in sorted(api_usage_count.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {api:<30} {count:>6,}")
    
    return {
        'schema_version': '1.0.0',
        'total': total_examples,
        'export_count': export_count,
        'avg_code_length': avg_code,
        'function_types': dict(func_types),
        'object_types': dict(object_types),
        'complexity_distribution': dict(complexity_distribution),
        'api_usage': dict(api_usage_count)
    }

def parse_args():
    parser = argparse.ArgumentParser(description="Создание ML dataset для 1C AI Stack")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("./output/edt_parser/full_parse_with_metadata.json"),
        help="Путь к full_parse_with_metadata.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./output/dataset"),
        help="Каталог для сохранения итоговых файлов",
    )
    parser.add_argument(
        "--limit-common",
        type=int,
        default=500,
        help="Ограничение на количество общих модулей (0 = без ограничений)",
    )
    parser.add_argument(
        "--config-name",
        default="Configuration",
        help="Имя конфигурации для отчёта",
    )
    return parser.parse_args()


def main():
    """Главная функция"""
    args = parse_args()

    print("=" * 80)
    print(f"СОЗДАНИЕ ML DATASET ДЛЯ {args.config_name.upper()}")
    print("=" * 80)

    try:
        data = load_parse_results(args.input)
    except (FileNotFoundError, json.JSONDecodeError) as err:
        print(f"Ошибка загрузки данных: {err}")
        return 1

    print("\nСоздание dataset...")

    limit_common = args.limit_common or None
    dataset_common = create_dataset_from_common_modules(data, limit=limit_common)
    dataset_catalogs = create_dataset_from_catalogs(data)
    dataset_documents = create_dataset_from_documents(data)

    full_dataset = dataset_common + dataset_catalogs + dataset_documents
    stats = analyze_dataset(full_dataset)
    stats["config_name"] = args.config_name

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_file = output_dir / "ml_training_dataset.json"
    print("\nСохранение dataset...")
    with dataset_file.open('w', encoding='utf-8') as f:
        json.dump(full_dataset, f, ensure_ascii=False, indent=2)
    print(f"  Dataset: {dataset_file} ({dataset_file.stat().st_size / 1024 / 1024:.2f} MB)")

    stats_file = output_dir / "dataset_statistics.json"
    with stats_file.open('w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  Статистика: {stats_file}")

    compact_dataset = [
        {k: v for k, v in example.items() if k != 'code'}
        for example in full_dataset
    ]
    compact_file = output_dir / "ml_training_dataset_compact.json"
    with compact_file.open('w', encoding='utf-8') as f:
        json.dump(compact_dataset, f, ensure_ascii=False, indent=2)
    print(f"  Компактная версия: {compact_file} ({compact_file.stat().st_size / 1024 / 1024:.2f} MB)")

    print("\n" + "=" * 80)
    print("DATASET СОЗДАН!")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())




