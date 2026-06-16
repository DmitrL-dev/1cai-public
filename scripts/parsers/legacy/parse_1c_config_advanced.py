
#!/usr/bin/env python3
"""
Продвинутый парсер конфигураций 1С
Поддерживает реальную структуру XML 1С и большие файлы
Версия: 2.0.0
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


class Advanced1CConfigParser:
    """Продвинутый парсер конфигураций 1С"""
    
    def __init__(self):
        self.kb = get_knowledge_base()
        self.config_dir = Path("./1c_configurations")
        self.modules_loaded = 0
        self.functions_extracted = 0
        self.patterns_found = 0
        
    def parse_configuration(self, config_name: str, config_file: Path) -> Dict[str, Any]:
        """Парсинг конфигурации 1С с улучшенным извлечением данных"""
        file_size_mb = config_file.stat().st_size / 1024 / 1024
        print(f"[INFO] Парсинг {config_file.name} ({file_size_mb:.1f} MB)...")
        
        try:
            # Используем итеративный парсер для больших файлов
            context = ET.iterparse(str(config_file), events=('start', 'end'))
            context = iter(context)
            
            # Пропускаем корневой элемент
            event, root = next(context)
            
            modules = []
            common_modules = []
            metadata_objects = []
            
            current_path = []
            module_buffer = {}
            
            print("[INFO] Начало парсинга XML...")
            
            for event, elem in context:
                if event == 'start':
                    current_path.append(elem.tag)
                    tag_path = '/'.join(current_path)
                    
                    # Определяем объекты метаданных
                    if elem.tag in ['Document', 'Catalog', 'RegisterInformation', 
                                   'RegisterAccumulation', 'RegisterAccounting',
                                   'Report', 'DataProcessor', 'CommonModule',
                                   'Constant', 'Enum', 'Task', 'WSReference',
                                   'BusinessProcess', 'ChartOfCharacteristicTypes',
                                   'ChartOfAccounts', 'ExchangePlan']:
                        
                        obj_name = elem.get('name', '')
                        if obj_name:
                            metadata_objects.append({
                                'type': elem.tag,
                                'name': obj_name,
                                'path': tag_path
                            })
                    
                    # Сохраняем атрибуты для объектов с модулями
                    if elem.tag in ['ObjectModule', 'Module', 'FormModule', 
                                   'CommandModule', 'RecordSetModule', 'ManagerModule']:
                        module_type = elem.tag
                        # Сохраняем контекст для модуля
                        if current_path:
                            parent_tags = current_path[:-1]
                            module_buffer[module_type] = {
                                'path': tag_path,
                                'parent_tags': parent_tags,
                                'element': elem
                            }
                
                elif event == 'end':
                    # Извлекаем модули когда элемент закрывается
                    if elem.tag in ['ObjectModule', 'Module', 'FormModule', 
                                   'CommandModule', 'RecordSetModule', 'ManagerModule']:
                        if elem.tag in module_buffer:
                            module_data = self.extract_module_data(
                                module_buffer[elem.tag],
                                config_name,
                                config_file,
                                metadata_objects
                            )
                            if module_data:
                                if 'CommonModule' in module_buffer[elem.tag]['parent_tags']:
                                    common_modules.append(module_data)
                                else:
                                    modules.append(module_data)
                            del module_buffer[elem.tag]
                    
                    # Очищаем из памяти для больших файлов
                    if len(current_path) > 10:  # Глубокая вложенность
                        elem.clear()
                    
                    if current_path and current_path[-1] == elem.tag:
                        current_path.pop()
                
                # Прогресс для больших файлов
                if self.modules_loaded % 100 == 0 and self.modules_loaded > 0:
                    print(f"[INFO] Обработано модулей: {self.modules_loaded}")
            
            print(f"[OK] Найдено: {len(modules)} модулей объектов, {len(common_modules)} общих модулей")
            
            # Сохраняем все модули
            all_modules = modules + common_modules
            for module in all_modules:
                self.save_module_to_kb(module, config_name)
            
            return {
                "modules": len(modules),
                "common_modules": len(common_modules),
                "total_modules": len(all_modules),
                "functions": self.functions_extracted,
                "metadata_objects": len(metadata_objects),
                "status": "success"
            }
        
        except ET.ParseError as e:
            print(f"[ERROR] Ошибка парсинга XML: {e}")
            return {"status": "error", "error": f"XML ParseError: {str(e)}"}
        except MemoryError:
            print(f"[ERROR] Недостаточно памяти для обработки файла {config_file.name}")
            return {"status": "error", "error": "MemoryError"}
        except Exception as e:
            print(f"[ERROR] Неожиданная ошибка: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e)}
    
    def extract_module_data(self, module_info: Dict, config_name: str, 
                          config_file: Path, metadata_objects: List[Dict]) -> Optional[Dict[str, Any]]:
        """Извлечение данных модуля"""
        try:
            elem = module_info['element']
            module_type = elem.tag
            parent_tags = module_info.get('parent_tags', [])
            
            # Получаем код модуля
            module_code = elem.text or ""
            if not module_code or len(module_code.strip()) < 10:
                return None
            
            # Определяем контекст объекта
            object_name = ""
            object_type = ""
            
            # Ищем родительский объект
            for parent_tag in reversed(parent_tags):
                if parent_tag in ['Document', 'Catalog', 'RegisterInformation', 
                                'RegisterAccumulation', 'RegisterAccounting',
                                'Report', 'DataProcessor', 'CommonModule']:
                    object_type = parent_tag
                    # Имя объекта будет в атрибутах родителя
                    break
            
            # Попытка извлечь имя из пути
            path_parts = module_info.get('path', '').split('/')
            for i, part in enumerate(path_parts):
                if part in ['Document', 'Catalog', 'RegisterInformation', 
                           'RegisterAccumulation', 'RegisterAccounting',
                           'Report', 'DataProcessor', 'CommonModule']:
                    # Следующий элемент может содержать имя
                    if i + 1 < len(path_parts):
                        potential_name = path_parts[i + 1]
                        if potential_name and not potential_name.startswith('{'):
                            object_name = potential_name
                            break
            
            # Если не нашли через путь, ищем в метаданных
            if not object_name:
                for obj in metadata_objects:
                    if obj['type'] == object_type or (not object_type and obj['path'] in module_info.get('path', '')):
                        object_name = obj['name']
                        object_type = obj['type']
                        break
            
            # Формируем имя модуля
            if module_type == 'CommonModule' or 'CommonModule' in parent_tags:
                module_name = f"ОбщийМодуль_{object_name or 'Unknown'}"
                object_type = "CommonModule"
            else:
                module_name = f"{object_type}_{object_name or 'Unknown'}_{module_type}"
            
            # Извлекаем функции
            functions = self.extract_functions_advanced(module_code)
            self.functions_extracted += len(functions)
            
            # Извлекаем паттерны
            patterns = self.extract_patterns_advanced(module_code)
            self.patterns_found += len(patterns)
            
            module_data = {
                "name": module_name,
                "object_type": object_type,
                "object_name": object_name or "Unknown",
                "module_type": module_type,
                "code": module_code[:10000],  # Ограничиваем для базы знаний
                "code_length": len(module_code),
                "source_file": str(config_file.relative_to(self.config_dir)),
                "functions": functions[:50],  # Ограничиваем количество функций
                "patterns": patterns,
                "description": f"{module_type} для {object_type} {object_name or 'Unknown'}"
            }
            
            self.modules_loaded += 1
            
            return module_data
        
        except Exception as e:
            print(f"[WARN] Ошибка извлечения модуля: {e}")
            return None
    
    def extract_functions_advanced(self, code: str) -> List[Dict[str, Any]]:
        """Улучшенное извлечение функций из BSL кода"""
        functions = []
        
        if not code or len(code) < 10:
            return functions
        
        # Паттерн для функций и процедур BSL (более точный)
        # Учитываем параметры с типами, значениями по умолчанию
        pattern = r'(?:Функция|Процедура)\s+(\w+)\s*(?:\(([^)]*)\))?\s*(?:\s*Экспорт)?'
        
        matches = re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE)
        
        for match in matches:
            func_name = match.group(1)
            params_str = match.group(2) or ""
            
            # Парсинг параметров (более сложный)
            params = []
            if params_str:
                # Разделяем параметры, учитывая вложенные скобки
                param_parts = []
                current_param = ""
                depth = 0
                
                for char in params_str:
                    if char == '(':
                        depth += 1
                        current_param += char
                    elif char == ')':
                        depth -= 1
                        current_param += char
                    elif char == ',' and depth == 0:
                        if current_param.strip():
                            param_parts.append(current_param.strip())
                        current_param = ""
                    else:
                        current_param += char
                
                if current_param.strip():
                    param_parts.append(current_param.strip())
                
                for param_part in param_parts:
                    param_part = param_part.strip()
                    if param_part:
                        # Извлекаем имя параметра (до = или :)
                        param_name = param_part.split('=')[0].split(':')[0].strip().split()[0]
                        if param_name:
                            params.append(param_name)
            
            # Извлекаем возвращаемое значение для функций
            return_value = None
            if 'Функция' in match.group(0):
                # Ищем "Возврат" после определения функции
                func_start = match.end()
                func_code = code[func_start:func_start + 5000]  # Смотрим 5000 символов дальше
                return_match = re.search(r'Возврат\s+([^;\n]+)', func_code, re.IGNORECASE)
                if return_match:
                    return_value = return_match.group(1).strip()
            
            functions.append({
                "name": func_name,
                "parameters": params,
                "signature": match.group(0)[:300],  # Ограничиваем длину
                "return_value": return_value
            })
            
            if len(functions) >= 100:  # Ограничиваем количество
                break
        
        return functions
    
    def extract_patterns_advanced(self, code: str) -> List[Dict[str, Any]]:
        """Извлечение паттернов использования из кода"""
        patterns = []
        
        if not code or len(code) < 10:
            return patterns
        
        # Паттерн 1: Запросы к БД
        if re.search(r'Новый\s+Запрос', code, re.IGNORECASE):
            patterns.append({
                "type": "query",
                "pattern": "Новый Запрос",
                "description": "Использование запросов к базе данных",
                "count": len(re.findall(r'Новый\s+Запрос', code, re.IGNORECASE))
            })
        
        # Паттерн 2: Обработка ошибок
        if re.search(r'Попытка\s+.*\s+Исключение', code, re.IGNORECASE | re.DOTALL):
            patterns.append({
                "type": "error_handling",
                "pattern": "Попытка-Исключение",
                "description": "Обработка исключений",
                "count": len(re.findall(r'Попытка\s+.*\s+Исключение', code, re.IGNORECASE | re.DOTALL))
            })
        
        # Паттерн 3: Работа с объектами
        if re.search(r'ПолучитьОбъект\(|СоздатьОбъект\(', code, re.IGNORECASE):
            patterns.append({
                "type": "object_management",
                "pattern": "ПолучитьОбъект/СоздатьОбъект",
                "description": "Работа с объектами метаданных",
                "count": len(re.findall(r'ПолучитьОбъект\(|СоздатьОбъект\(', code, re.IGNORECASE))
            })
        
        # Паттерн 4: Циклы по массивам
        if re.search(r'Для\s+\w+\s*=\s*\w+\s+По\s+\w+\.\w+\(\)', code, re.IGNORECASE):
            patterns.append({
                "type": "iteration",
                "pattern": "Для...По",
                "description": "Итерация по коллекциям",
                "count": len(re.findall(r'Для\s+\w+\s*=\s*\w+\s+По\s+\w+\.\w+\(\)', code, re.IGNORECASE))
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
            print(f"[WARN] Ошибка сохранения модуля {module_data.get('name', 'Unknown')}: {e}")


def load_all_configurations():
    """Загрузка всех конфигураций"""
    print("=" * 70)
    print("ПРОДВИНУТАЯ ЗАГРУЗКА КОНФИГУРАЦИЙ 1С В БАЗУ ЗНАНИЙ")
    print("=" * 70)
    
    parser = Advanced1CConfigParser()
    config_dir = Path("./1c_configurations")
    
    # Поддерживаемые конфигурации
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
    
    # Поиск всех config.xml файлов
    config_files = list(config_dir.rglob("config.xml"))
    
    print(f"\n[INFO] Найдено файлов конфигураций: {len(config_files)}")
    
    for config_file in config_files:
        parent_dir = config_file.parent.name
        config_name = parent_dir.upper()
        
        if config_name not in supported_configs:
            print(f"[SKIP] Неизвестная конфигурация: {config_name}")
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
                modules_count = result.get("total_modules", 0)
                functions_count = result.get("functions", 0)
                total_modules += modules_count
                total_functions += functions_count
                
                results[config_name] = {
                    "status": "success",
                    "modules": modules_count,
                    "common_modules": result.get("common_modules", 0),
                    "functions": functions_count,
                    "metadata_objects": result.get("metadata_objects", 0)
                }
                
                print(f"\n[OK] {config_name}: {modules_count} модулей, {functions_count} функций")
            else:
                results[config_name] = result
                print(f"[ERROR] {config_name}: {result.get('error', 'Unknown error')}")
        
        except KeyboardInterrupt:
            print(f"\n[INFO] Прервано пользователем при обработке {config_name}")
            break
        except Exception as e:
            print(f"[ERROR] Критическая ошибка при обработке {config_name}: {e}")
            results[config_name] = {"status": "error", "error": str(e)}
    
    print(f"\n{'='*70}")
    print("ИТОГИ ЗАГРУЗКИ:")
    print(f"{'='*70}")
    
    for config_name, result in results.items():
        if result.get("status") == "success":
            print(f"[OK] {config_name:10} | Модулей: {result.get('modules', 0):5} | "
                  f"Функций: {result.get('functions', 0):5} | Объектов: {result.get('metadata_objects', 0):5}")
        else:
            print(f"[ERROR] {config_name:10} | {result.get('error', 'Unknown error')}")
    
    print(f"{'='*70}")
    print(f"ВСЕГО: {total_modules} модулей, {total_functions} функций")
    print(f"{'='*70}")
    
    print("\n[OK] Загрузка завершена!")
    print("\nСледующие шаги:")
    print("1. Проверьте базу знаний: GET /api/knowledge-base/configurations")
    print("2. Используйте рекомендации в Code Review")
    print("3. Изучите извлеченные паттерны и функции")
    
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





