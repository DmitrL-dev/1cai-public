
#!/usr/bin/env python3
"""
EDT Configuration Parser
Парсер для EDT (Enterprise Development Tools) выгрузки конфигураций 1С

Версия: 1.0.0
Дата: 2025-11-06

Поддерживает:
- Чтение .bsl файлов (код)
- Парсинг XML метаданных
- Объединение кода + метаданные
- Создание enriched dataset для обучения моделей
"""

import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Добавляем путь к улучшенному BSL парсеру
parser_parent = Path(__file__).parent.parent
sys.path.insert(0, str(parser_parent))
sys.path.insert(0, str(parser_parent.parent))

try:
    from parsers.improve_bsl_parser import ImprovedBSLParser
except ImportError:
    try:
        from scripts.parsers.improve_bsl_parser import ImprovedBSLParser
    except ImportError:
        ImprovedBSLParser = None
        if __name__ == "__main__":
            print("[WARNING] ImprovedBSLParser не найден, используем базовый парсинг")


class EDTConfigurationParser:
    """
    Парсер для EDT выгрузки 1С конфигураций
    
    Поддерживает:
    - Чтение структуры папок EDT
    - Парсинг .bsl файлов (код)
    - Парсинг .xml файлов (метаданные)
    - Объединение кода + метаданные
    - Создание enriched dataset
    """
    
    def __init__(self, edt_root_path: Path):
        """
        Инициализация парсера
        
        Args:
            edt_root_path: Путь к корню EDT выгрузки
        """
        self.edt_root = Path(edt_root_path)
        self.bsl_parser = ImprovedBSLParser() if ImprovedBSLParser else None
        
        # Статистика
        self.stats = defaultdict(int)
        self.errors = []
        
        # Результаты
        self.modules = []
        self.objects = []
        self.functions = []
        
    def parse_configuration(self, config_name: str = "ERPCPM") -> Dict[str, Any]:
        """
        Парсинг всей конфигурации EDT
        
        Args:
            config_name: Имя конфигурации
            
        Returns:
            Словарь с результатами парсинга
        """
        print("=" * 80)
        print(f"ПАРСИНГ EDT КОНФИГУРАЦИИ: {config_name}")
        print("=" * 80)
        print(f"Путь: {self.edt_root}")
        print()
        
        start_time = time.time()
        
        # 1. Парсинг общих модулей
        print("[*] Парсинг общих модулей...")
        common_modules = self.parse_common_modules()
        print(f"    Найдено общих модулей: {len(common_modules)}")
        
        # 2. Парсинг справочников
        print("[*] Парсинг справочников...")
        catalogs = self.parse_catalogs()
        print(f"    Найдено справочников: {len(catalogs)}")
        
        # 3. Парсинг документов
        print("[*] Парсинг документов...")
        documents = self.parse_documents()
        print(f"    Найдено документов: {len(documents)}")
        
        elapsed = time.time() - start_time
        
        # Сводная статистика
        print()
        print("=" * 80)
        print("РЕЗУЛЬТАТЫ ПАРСИНГА")
        print("=" * 80)
        print(f"Время выполнения: {elapsed:.2f} секунд")
        print(f"Общих модулей: {len(common_modules)}")
        print(f"Справочников: {len(catalogs)}")
        print(f"Документов: {len(documents)}")
        print(f"Всего функций: {self.stats['functions']}")
        print(f"Всего процедур: {self.stats['procedures']}")
        print(f"Ошибок: {len(self.errors)}")
        print("=" * 80)
        
        return {
            'status': 'success',
            'config_name': config_name,
            'common_modules': common_modules,
            'catalogs': catalogs,
            'documents': documents,
            'stats': dict(self.stats),
            'errors': self.errors,
            'parse_time': elapsed
        }
    
    def parse_common_modules(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Парсинг общих модулей
        
        Args:
            limit: Ограничение количества модулей (для тестирования)
            
        Returns:
            Список распарсенных модулей
        """
        modules_path = self.edt_root / "CommonModules"
        if not modules_path.exists():
            print(f"[WARNING] Папка CommonModules не найдена: {modules_path}")
            return []
        
        modules = []
        module_dirs = list(modules_path.iterdir())
        
        # Ограничение для тестирования
        if limit:
            module_dirs = module_dirs[:limit]
            print(f"    Ограничение: парсинг первых {limit} модулей")
            total = limit
        
        total = len(module_dirs)
        processed = 0
        
        for module_dir in module_dirs:
            if not module_dir.is_dir():
                continue
            
            try:
                module_data = self.parse_single_common_module(module_dir)
                if module_data:
                    modules.append(module_data)
                    processed += 1
                    
                    # Прогресс каждые 100 модулей
                    if processed % 100 == 0:
                        print(f"    Обработано: {processed}/{total} модулей")
                        
            except Exception as e:
                error_msg = f"Ошибка парсинга модуля {module_dir.name}: {str(e)}"
                self.errors.append(error_msg)
                print(f"[ERROR] {error_msg}")
        
        self.stats['common_modules'] = len(modules)
        return modules
    
    def parse_single_common_module(self, module_dir: Path) -> Optional[Dict[str, Any]]:
        """
        Парсинг одного общего модуля
        
        Args:
            module_dir: Путь к папке модуля
            
        Returns:
            Словарь с данными модуля или None
        """
        module_name = module_dir.name
        
        # Ищем .bsl файл
        bsl_file = None
        for ext_path in [module_dir / "Ext" / "Module.bsl", 
                        module_dir / "Module.bsl",
                        module_dir.glob("**/Module.bsl")]:
            if isinstance(ext_path, Path) and ext_path.exists():
                bsl_file = ext_path
                break
            elif isinstance(ext_path, type(module_dir.glob(""))):
                # Это glob результат
                bsl_files = list(ext_path)
                if bsl_files:
                    bsl_file = bsl_files[0]
                    break
        
        if not bsl_file or not bsl_file.exists():
            # Модуль без кода - пропускаем
            return None
        
        # Читаем код
        try:
            with open(bsl_file, 'r', encoding='utf-8') as f:
                code = f.read()
        except Exception as e:
            self.errors.append(f"Ошибка чтения {bsl_file}: {str(e)}")
            return None
        
        # Парсим BSL код
        if self.bsl_parser:
            bsl_result = self.bsl_parser.parse(code)
            functions = bsl_result.get('functions', [])
            procedures = bsl_result.get('procedures', [])
        else:
            # Базовый парсинг без улучшенного парсера
            functions, procedures = self._basic_parse_bsl(code)
        
        self.stats['functions'] += len(functions)
        self.stats['procedures'] += len(procedures)
        
        # Ищем XML метаданные
        xml_file = module_dir / f"{module_name}.xml"
        metadata = None
        if xml_file.exists():
            metadata = self._parse_module_xml(xml_file)
        
        # Создаем enriched данные
        module_data = {
            'name': module_name,
            'object_type': 'CommonModule',
            'module_type': 'Module',
            'code': code[:10000],  # Первые 10KB для примера
            'code_length': len(code),
            'code_file': str(bsl_file.relative_to(self.edt_root)),
            'functions': functions[:50],  # Ограничиваем для размера
            'procedures': procedures[:50],
            'functions_count': len(functions),
            'procedures_count': len(procedures),
            'metadata': metadata,
            'source_path': str(module_dir.relative_to(self.edt_root))
        }
        
        return module_data
    
    def _basic_parse_bsl(self, code: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Базовый парсинг BSL кода (если ImprovedBSLParser недоступен)
        
        Args:
            code: BSL код
            
        Returns:
            (functions, procedures)
        """
        functions = []
        procedures = []
        
        # Паттерн для функций
        func_pattern = r'(?:Экспорт\s+)?Функция\s+(\w+)\s*\(([^)]*)\)'
        for match in re.finditer(func_pattern, code, re.IGNORECASE):
            func_name = match.group(1)
            params_str = match.group(2) if match.group(2) else ""
            
            # Находим тело функции
            start_pos = match.end()
            end_match = re.search(r'КонецФункции', code[start_pos:], re.IGNORECASE)
            if end_match:
                body = code[start_pos:start_pos + end_match.start()]
            else:
                body = ""
            
            functions.append({
                'name': func_name,
                'parameters': self._parse_parameters(params_str),
                'body': body[:1000],  # Первые 1KB
                'body_length': len(body),
                'is_export': 'Экспорт' in match.group(0)
            })
        
        # Паттерн для процедур
        proc_pattern = r'(?:Экспорт\s+)?Процедура\s+(\w+)\s*\(([^)]*)\)'
        for match in re.finditer(proc_pattern, code, re.IGNORECASE):
            proc_name = match.group(1)
            params_str = match.group(2) if match.group(2) else ""
            
            # Находим тело процедуры
            start_pos = match.end()
            end_match = re.search(r'КонецПроцедуры', code[start_pos:], re.IGNORECASE)
            if end_match:
                body = code[start_pos:start_pos + end_match.start()]
            else:
                body = ""
            
            procedures.append({
                'name': proc_name,
                'parameters': self._parse_parameters(params_str),
                'body': body[:1000],  # Первые 1KB
                'body_length': len(body),
                'is_export': 'Экспорт' in match.group(0)
            })
        
        return functions, procedures
    
    def _parse_parameters(self, params_str: str) -> List[Dict]:
        """Парсинг параметров функции/процедуры"""
        if not params_str or not params_str.strip():
            return []
        
        params = []
        for param in params_str.split(','):
            param = param.strip()
            if param:
                params.append({
                    'name': param,
                    'has_default': '=' in param
                })
        
        return params
    
    def _parse_module_xml(self, xml_file: Path) -> Optional[Dict[str, Any]]:
        """
        Парсинг XML метаданных модуля
        
        Args:
            xml_file: Путь к XML файлу
            
        Returns:
            Словарь с метаданными или None
        """
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            metadata = {
                'synonym': root.get('Synonym', ''),
                'comment': root.get('Comment', ''),
                'properties': {}
            }
            
            # Извлекаем свойства
            for prop in root.findall('.//Property'):
                prop_name = prop.get('Name', '')
                prop_value = prop.text or ''
                if prop_name:
                    metadata['properties'][prop_name] = prop_value
            
            return metadata
            
        except Exception as e:
            self.errors.append(f"Ошибка парсинга XML {xml_file}: {str(e)}")
            return None
    
    def parse_catalogs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Парсинг справочников
        
        Args:
            limit: Ограничение количества (для тестирования)
            
        Returns:
            Список распарсенных справочников
        """
        catalogs_path = self.edt_root / "Catalogs"
        if not catalogs_path.exists():
            return []
        
        catalogs = []
        catalog_dirs = list(catalogs_path.iterdir())
        
        if limit:
            catalog_dirs = catalog_dirs[:limit]
        
        for catalog_dir in catalog_dirs:
            if not catalog_dir.is_dir():
                continue
            
            try:
                catalog_data = self.parse_single_catalog(catalog_dir)
                if catalog_data:
                    catalogs.append(catalog_data)
            except Exception as e:
                self.errors.append(f"Ошибка парсинга справочника {catalog_dir.name}: {str(e)}")
        
        self.stats['catalogs'] = len(catalogs)
        return catalogs
    
    def parse_single_catalog(self, catalog_dir: Path) -> Optional[Dict[str, Any]]:
        """
        Парсинг одного справочника
        
        Args:
            catalog_dir: Путь к папке справочника
            
        Returns:
            Словарь с данными справочника или None
        """
        catalog_name = catalog_dir.name
        
        # Ищем XML метаданные
        xml_file = catalog_dir / f"{catalog_name}.xml"
        metadata = None
        if xml_file.exists():
            metadata = self._parse_catalog_xml(xml_file)
        
        # Ищем модули
        manager_module = None
        object_module = None
        
        manager_bsl = catalog_dir / "Ext" / "ManagerModule.bsl"
        if manager_bsl.exists():
            manager_module = self._read_module_code(manager_bsl)
        
        object_bsl = catalog_dir / "Ext" / "ObjectModule.bsl"
        if object_bsl.exists():
            object_module = self._read_module_code(object_bsl)
        
        catalog_data = {
            'name': catalog_name,
            'object_type': 'Catalog',
            'metadata': metadata,
            'manager_module': manager_module,
            'object_module': object_module,
            'source_path': str(catalog_dir.relative_to(self.edt_root))
        }
        
        return catalog_data
    
    def _parse_catalog_xml(self, xml_file: Path) -> Optional[Dict[str, Any]]:
        """Парсинг XML метаданных справочника"""
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            metadata = {
                'synonym': root.get('Synonym', ''),
                'comment': root.get('Comment', ''),
                'attributes': [],
                'tabular_sections': []
            }
            
            # Извлекаем реквизиты
            for attr in root.findall('.//Attribute'):
                attr_name = attr.get('Name', '')
                attr_type = attr.get('Type', '')
                if attr_name:
                    metadata['attributes'].append({
                        'name': attr_name,
                        'type': attr_type
                    })
            
            # Извлекаем табличные части
            for tab_section in root.findall('.//TabularSection'):
                section_name = tab_section.get('Name', '')
                if section_name:
                    metadata['tabular_sections'].append({
                        'name': section_name,
                        'columns': []
                    })
            
            return metadata
            
        except Exception as e:
            self.errors.append(f"Ошибка парсинга XML справочника {xml_file}: {str(e)}")
            return None
    
    def _read_module_code(self, bsl_file: Path) -> Optional[Dict[str, Any]]:
        """Чтение и парсинг кода модуля"""
        try:
            with open(bsl_file, 'r', encoding='utf-8') as f:
                code = f.read()
            
            if self.bsl_parser:
                result = self.bsl_parser.parse(code)
            else:
                functions, procedures = self._basic_parse_bsl(code)
                result = {
                    'functions': functions,
                    'procedures': procedures
                }
            
            return {
                'code': code[:5000],  # Первые 5KB
                'code_length': len(code),
                'functions': result.get('functions', [])[:20],
                'procedures': result.get('procedures', [])[:20],
                'functions_count': len(result.get('functions', [])),
                'procedures_count': len(result.get('procedures', []))
            }
            
        except Exception as e:
            self.errors.append(f"Ошибка чтения модуля {bsl_file}: {str(e)}")
            return None
    
    def parse_documents(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Парсинг документов
        
        Args:
            limit: Ограничение количества (для тестирования)
            
        Returns:
            Список распарсенных документов
        """
        documents_path = self.edt_root / "Documents"
        if not documents_path.exists():
            return []
        
        documents = []
        document_dirs = list(documents_path.iterdir())
        
        if limit:
            document_dirs = document_dirs[:limit]
        
        for doc_dir in document_dirs:
            if not doc_dir.is_dir():
                continue
            
            try:
                doc_data = self.parse_single_document(doc_dir)
                if doc_data:
                    documents.append(doc_data)
            except Exception as e:
                self.errors.append(f"Ошибка парсинга документа {doc_dir.name}: {str(e)}")
        
        self.stats['documents'] = len(documents)
        return documents
    
    def parse_single_document(self, doc_dir: Path) -> Optional[Dict[str, Any]]:
        """
        Парсинг одного документа
        
        Args:
            doc_dir: Путь к папке документа
            
        Returns:
            Словарь с данными документа или None
        """
        doc_name = doc_dir.name
        
        # Ищем XML метаданные
        xml_file = doc_dir / f"{doc_name}.xml"
        metadata = None
        if xml_file.exists():
            metadata = self._parse_document_xml(xml_file)
        
        # Ищем модули
        manager_module = None
        object_module = None
        
        manager_bsl = doc_dir / "Ext" / "ManagerModule.bsl"
        if manager_bsl.exists():
            manager_module = self._read_module_code(manager_bsl)
        
        object_bsl = doc_dir / "Ext" / "ObjectModule.bsl"
        if object_bsl.exists():
            object_module = self._read_module_code(object_bsl)
        
        doc_data = {
            'name': doc_name,
            'object_type': 'Document',
            'metadata': metadata,
            'manager_module': manager_module,
            'object_module': object_module,
            'source_path': str(doc_dir.relative_to(self.edt_root))
        }
        
        return doc_data
    
    def _parse_document_xml(self, xml_file: Path) -> Optional[Dict[str, Any]]:
        """Парсинг XML метаданных документа"""
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            metadata = {
                'synonym': root.get('Synonym', ''),
                'comment': root.get('Comment', ''),
                'attributes': [],
                'tabular_sections': []
            }
            
            # Извлекаем реквизиты
            for attr in root.findall('.//Attribute'):
                attr_name = attr.get('Name', '')
                attr_type = attr.get('Type', '')
                if attr_name:
                    metadata['attributes'].append({
                        'name': attr_name,
                        'type': attr_type
                    })
            
            # Извлекаем табличные части
            for tab_section in root.findall('.//TabularSection'):
                section_name = tab_section.get('Name', '')
                if section_name:
                    metadata['tabular_sections'].append({
                        'name': section_name,
                        'columns': []
                    })
            
            return metadata
            
        except Exception as e:
            self.errors.append(f"Ошибка парсинга XML документа {xml_file}: {str(e)}")
            return None
    
    def save_results(self, results: Dict[str, Any], output_file: Path):
        """
        Сохранение результатов парсинга
        
        Args:
            results: Результаты парсинга
            output_file: Путь к файлу для сохранения
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n[+] Результаты сохранены: {output_file}")


def main():
    """Главная функция для тестирования"""
    # Путь к EDT выгрузке
    edt_path = Path("./1c_configurations/ERPCPM")
    
    if not edt_path.exists():
        print(f"[ERROR] Папка не найдена: {edt_path}")
        print("Убедитесь что выгрузка EDT находится в ./1c_configurations/ERPCPM/")
        return 1
    
    # Создаем парсер
    parser = EDTConfigurationParser(edt_path)
    
    # Парсим с ограничением для тестирования
    print("\n[INFO] Тестовый запуск: парсинг первых 100 общих модулей\n")
    results = parser.parse_common_modules(limit=100)
    
    # Сохраняем результаты тестирования
    test_results = {
        'status': 'success',
        'test_mode': True,
        'limit': 100,
        'common_modules': results,
        'stats': dict(parser.stats),
        'errors': parser.errors
    }
    
    # Сохраняем тестовые результаты
    output_dir = Path("./output/edt_parser")
    output_dir.mkdir(parents=True, exist_ok=True)
    test_output_file = output_dir / "edt_parse_test_100_modules.json"
    parser.save_results(test_results, test_output_file)
    
    print(f"\n[+] Тестовые результаты сохранены: {test_output_file}")
    print(f"\n[INFO] Для полного парсинга запустите: parser.parse_configuration()")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

