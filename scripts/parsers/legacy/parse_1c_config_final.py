
#!/usr/bin/env python3
"""
Финальный парсер конфигураций 1С
Корректно обрабатывает UTF-8 BOM и кириллические теги
Версия: 3.0.0
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

try:
    from src.services.configuration_knowledge_base import get_knowledge_base
except ImportError as e:
    print(f"[ERROR] Ошибка импорта: {e}")
    sys.exit(1)


class Final1CConfigParser:
    """Финальный парсер конфигураций 1С с поддержкой кириллических тегов"""
    
    def __init__(self):
        self.kb = get_knowledge_base()
        self.config_dir = Path("./1c_configurations")
        self.stats = {
            'modules': 0,
            'functions': 0,
            'patterns': 0,
            'objects': 0
        }
        
    def parse_configuration(self, config_name: str, config_file: Path) -> Dict[str, Any]:
        """Парсинг конфигурации 1С с правильной обработкой UTF-8 и кириллицы"""
        file_size_mb = config_file.stat().st_size / 1024 / 1024
        print(f"[INFO] Парсинг {config_file.name} ({file_size_mb:.1f} MB)...")
        
        try:
            # Правильно обрабатываем UTF-8 BOM
            with open(config_file, 'rb') as f:
                raw_bytes = f.read()
                # Убираем BOM если есть
                if raw_bytes.startswith(b'\xef\xbb\xbf'):
                    raw_bytes = raw_bytes[3:]
                content = raw_bytes.decode('utf-8')
            
            # Парсим XML
            root = ET.fromstring(content)
            
            print(f"[INFO] Root tag: {root.tag}")
            print(f"[INFO] Начало извлечения данных...")
            
            # Извлекаем модули из разных мест
            modules = []
            
            # 1. Общие модули
            common_modules = root.findall('.//ОбщийМодуль')
            print(f"[INFO] Найдено общих модулей: {len(common_modules)}")
            
            for cm in common_modules:
                module_data = self.extract_common_module(cm, config_name, config_file)
                if module_data:
                    modules.append(module_data)
                    self.stats['modules'] += 1
            
            # 2. Модули документов
            documents = root.findall('.//Документ')
            print(f"[INFO] Найдено документов: {len(documents)}")
            self.stats['objects'] += len(documents)
            
            for doc in documents[:100]:  # Ограничиваем для производительности
                module_data = self.extract_document_modules(doc, config_name, config_file)
                modules.extend(module_data)
                self.stats['modules'] += len(module_data)
            
            # 3. Модули справочников
            catalogs = root.findall('.//Справочник')
            print(f"[INFO] Найдено справочников: {len(catalogs)}")
            self.stats['objects'] += len(catalogs)
            
            for cat in catalogs[:100]:
                module_data = self.extract_catalog_modules(cat, config_name, config_file)
                modules.extend(module_data)
                self.stats['modules'] += len(module_data)
            
            # 4. Модули регистров
            registers = root.findall('.//РегистрСведений') + root.findall('.//РегистрНакопления')
            print(f"[INFO] Найдено регистров: {len(registers)}")
            self.stats['objects'] += len(registers)
            
            # Сохраняем все модули
            for module in modules:
                self.save_module_to_kb(module, config_name)
            
            print(f"[OK] Извлечено: {len(modules)} модулей")
            
            return {
                "modules": len(modules),
                "functions": self.stats['functions'],
                "objects": self.stats['objects'],
                "status": "success"
            }
        
        except ET.ParseError as e:
            print(f"[ERROR] Ошибка парсинга XML: {e}")
            return {"status": "error", "error": f"XML ParseError: {str(e)}"}
        except Exception as e:
            print(f"[ERROR] Неожиданная ошибка: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e)}
    
    def extract_common_module(self, cm_elem, config_name: str, config_file: Path) -> Optional[Dict[str, Any]]:
        """Извлечение общего модуля"""
        try:
            module_name = cm_elem.get('Имя', '')
            if not module_name:
                return None
            
            # Ищем код модуля
            module_code_elem = cm_elem.find('.//Модуль')
            if module_code_elem is None or not module_code_elem.text:
                return None
            
            module_code = module_code_elem.text
            
            # Извлекаем функции
            functions = self.extract_functions_advanced(module_code)
            self.stats['functions'] += len(functions)
            
            # Извлекаем паттерны
            patterns = self.extract_patterns_advanced(module_code)
            self.stats['patterns'] += len(patterns)
            
            module_data = {
                "name": f"ОбщийМодуль_{module_name}",
                "object_type": "ОбщийМодуль",
                "object_name": module_name,
                "module_type": "Модуль",
                "code": module_code[:10000],
                "code_length": len(module_code),
                "source_file": str(config_file.relative_to(self.config_dir)),
                "functions": functions[:50],
                "patterns": patterns,
                "description": f"Общий модуль {module_name}"
            }
            
            return module_data
        
        except Exception as e:
            print(f"[WARN] Ошибка извлечения общего модуля: {e}")
            return None
    
    def extract_document_modules(self, doc_elem, config_name: str, config_file: Path) -> List[Dict[str, Any]]:
        """Извлечение модулей документа"""
        modules = []
        
        try:
            doc_name = doc_elem.get('Имя', '')
            if not doc_name:
                return modules
            
            # Объектный модуль
            obj_module_elem = doc_elem.find('.//ОбъектныйМодуль')
            if obj_module_elem is not None and obj_module_elem.text:
                module_data = self.create_module_data(
                    obj_module_elem.text,
                    doc_name,
                    "Документ",
                    "ОбъектныйМодуль",
                    config_name,
                    config_file
                )
                if module_data:
                    modules.append(module_data)
            
            # Модуль формы
            form_modules = doc_elem.findall('.//МодульФормы')
            for fm_elem in form_modules[:5]:  # Ограничиваем
                if fm_elem.text:
                    module_data = self.create_module_data(
                        fm_elem.text,
                        doc_name,
                        "Документ",
                        "МодульФормы",
                        config_name,
                        config_file
                    )
                    if module_data:
                        modules.append(module_data)
        
        except Exception as e:
            print(f"[WARN] Ошибка извлечения модулей документа: {e}")
        
        return modules
    
    def extract_catalog_modules(self, cat_elem, config_name: str, config_file: Path) -> List[Dict[str, Any]]:
        """Извлечение модулей справочника"""
        modules = []
        
        try:
            cat_name = cat_elem.get('Имя', '')
            if not cat_name:
                return modules
            
            # Объектный модуль
            obj_module_elem = cat_elem.find('.//ОбъектныйМодуль')
            if obj_module_elem is not None and obj_module_elem.text:
                module_data = self.create_module_data(
                    obj_module_elem.text,
                    cat_name,
                    "Справочник",
                    "ОбъектныйМодуль",
                    config_name,
                    config_file
                )
                if module_data:
                    modules.append(module_data)
        
        except Exception as e:
            print(f"[WARN] Ошибка извлечения модулей справочника: {e}")
        
        return modules
    
    def create_module_data(self, code: str, obj_name: str, obj_type: str,
                          module_type: str, config_name: str, config_file: Path) -> Optional[Dict[str, Any]]:
        """Создание структуры данных модуля"""
        if not code or len(code.strip()) < 10:
            return None
        
        # Извлекаем функции
        functions = self.extract_functions_advanced(code)
        self.stats['functions'] += len(functions)
        
        # Извлекаем паттерны
        patterns = self.extract_patterns_advanced(code)
        self.stats['patterns'] += len(patterns)
        
        module_name = f"{obj_type}_{obj_name}_{module_type}"
        
        return {
            "name": module_name,
            "object_type": obj_type,
            "object_name": obj_name,
            "module_type": module_type,
            "code": code[:10000],
            "code_length": len(code),
            "source_file": str(config_file.relative_to(self.config_dir)),
            "functions": functions[:50],
            "patterns": patterns,
            "description": f"{module_type} для {obj_type} {obj_name}"
        }
    
    def extract_functions_advanced(self, code: str) -> List[Dict[str, Any]]:
        """Улучшенное извлечение функций из BSL"""
        functions = []
        
        if not code or len(code) < 10:
            return functions
        
        # Паттерн для функций и процедур BSL
        pattern = r'(?:Функция|Процедура)\s+(\w+)\s*(?:\(([^)]*)\))?\s*(?:\s*Экспорт)?'
        
        matches = re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE)
        
        for match in matches:
            func_name = match.group(1)
            params_str = match.group(2) or ""
            
            # Парсинг параметров
            params = []
            if params_str:
                for param_part in re.split(r',\s*(?![^()]*\))', params_str):
                    param_part = param_part.strip()
                    if param_part:
                        param_name = param_part.split('=')[0].split(':')[0].strip().split()[0]
                        if param_name:
                            params.append(param_name)
            
            functions.append({
                "name": func_name,
                "parameters": params,
                "signature": match.group(0)[:300]
            })
            
            if len(functions) >= 100:
                break
        
        return functions
    
    def extract_patterns_advanced(self, code: str) -> List[Dict[str, Any]]:
        """Извлечение паттернов"""
        patterns = []
        
        if not code:
            return patterns
        
        # Паттерн 1: Запросы
        if re.search(r'Новый\s+Запрос', code, re.IGNORECASE):
            patterns.append({
                "type": "query",
                "pattern": "Новый Запрос",
                "count": len(re.findall(r'Новый\s+Запрос', code, re.IGNORECASE))
            })
        
        # Паттерн 2: Обработка ошибок
        if re.search(r'Попытка\s+.*\s+Исключение', code, re.IGNORECASE | re.DOTALL):
            patterns.append({
                "type": "error_handling",
                "pattern": "Попытка-Исключение",
                "count": 1
            })
        
        return patterns
    
    def save_module_to_kb(self, module_data: Dict, config_name: str):
        """Сохранение модуля в базу знаний"""
        try:
            self.kb.add_module_documentation(
                config_name=config_name.lower(),
                module_name=module_data["name"],
                documentation=module_data
            )
        except Exception as e:
            print(f"[WARN] Ошибка сохранения: {e}")


def load_all_configurations():
    """Загрузка всех конфигураций"""
    print("=" * 70)
    print("ФИНАЛЬНАЯ ЗАГРУЗКА КОНФИГУРАЦИЙ 1С")
    print("=" * 70)
    
    parser = Final1CConfigParser()
    config_dir = Path("./1c_configurations")
    
    supported_configs = {
        "ERP": "Управление предприятием 2",
        "UT": "Управление торговлей",
        "ZUP": "Зарплата и управление персоналом",
        "BUH": "Бухгалтерия предприятия",
        "HOLDING": "Управление холдингом",
        "BUHBIT": "Бухгалтерия БИТ",
        "DO": "Документооборот",
        "KA": "Комплексная автоматизация"
    }
    
    results = {}
    total_modules = 0
    total_functions = 0
    
    config_files = list(config_dir.rglob("config.xml"))
    print(f"\n[INFO] Найдено конфигураций: {len(config_files)}")
    
    for config_file in config_files:
        parent_dir = config_file.parent.name
        config_name = parent_dir.upper()
        
        if config_name not in supported_configs:
            continue
        
        config_full_name = supported_configs[config_name]
        file_size_mb = config_file.stat().st_size / 1024 / 1024
        
        print(f"\n{'='*70}")
        print(f"Обработка: {config_name} ({config_full_name})")
        print(f"Файл: {config_file.name} ({file_size_mb:.1f} MB)")
        print(f"{'='*70}")
        
        try:
            result = parser.parse_configuration(config_name, config_file)
            
            if result.get("status") == "success":
                modules_count = result.get("modules", 0)
                functions_count = result.get("functions", 0)
                total_modules += modules_count
                total_functions += functions_count
                
                results[config_name] = {
                    "status": "success",
                    "modules": modules_count,
                    "functions": functions_count,
                    "objects": result.get("objects", 0)
                }
                
                print(f"\n[OK] {config_name}: {modules_count} модулей, {functions_count} функций")
            else:
                results[config_name] = result
                print(f"[ERROR] {config_name}: {result.get('error', 'Unknown')}")
        
        except Exception as e:
            print(f"[ERROR] Критическая ошибка: {e}")
            results[config_name] = {"status": "error", "error": str(e)}
    
    print(f"\n{'='*70}")
    print("ИТОГИ:")
    print(f"{'='*70}")
    
    for config_name, result in results.items():
        if result.get("status") == "success":
            print(f"[OK] {config_name:10} | Модулей: {result.get('modules', 0):5} | "
                  f"Функций: {result.get('functions', 0):5} | Объектов: {result.get('objects', 0):5}")
        else:
            print(f"[ERROR] {config_name:10} | {result.get('error', 'Unknown')}")
    
    print(f"{'='*70}")
    print(f"ВСЕГО: {total_modules} модулей, {total_functions} функций")
    print(f"{'='*70}")
    
    return results


if __name__ == "__main__":
    try:
        load_all_configurations()
    except KeyboardInterrupt:
        print("\n[INFO] Прервано пользователем")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)





