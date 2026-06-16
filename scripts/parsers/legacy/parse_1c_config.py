
#!/usr/bin/env python3
"""
Продвинутый парсер конфигураций 1С
Поддерживает большие XML файлы и специфичную структуру 1С
Версия: 1.0.0
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
    print(f"Ошибка импорта: {e}")
    sys.exit(1)


class OneCConfigParser:
    """Парсер конфигураций 1С с поддержкой больших файлов"""
    
    def __init__(self):
        self.kb = get_knowledge_base()
        self.config_dir = Path("./1c_configurations")
    
    def parse_configuration(self, config_name: str, config_file: Path) -> Dict[str, Any]:
        """Парсинг конфигурации 1С"""
        print(f"[INFO] Парсинг {config_file.name} ({config_file.stat().st_size / 1024 / 1024:.1f} MB)...")
        
        try:
            # Используем итеративный парсинг для больших файлов
            context = ET.iterparse(str(config_file), events=('start', 'end'))
            context = iter(context)
            event, root = next(context)
            
            modules = []
            patterns = []
            api_usage = []
            
            current_obj = None
            obj_stack = []
            
            for event, elem in context:
                if event == 'start':
                    obj_stack.append(elem)
                    
                    # Определяем тип объекта 1С
                    if elem.tag in ['Document', 'Catalog', 'RegisterInformation', 
                                   'RegisterAccumulation', 'RegisterAccounting',
                                   'Report', 'DataProcessor', 'CommonModule', 
                                   'Configuration', 'Subsystem']:
                        current_obj = {
                            'type': elem.tag,
                            'name': elem.get('name', ''),
                            'element': elem
                        }
                
                elif event == 'end':
                    if current_obj and elem == current_obj.get('element'):
                        # Извлекаем данные объекта
                        module_data = self.extract_object_data(current_obj, config_name, config_file)
                        if module_data:
                            modules.append(module_data)
                        
                        # Извлекаем паттерны
                        pattern = self.extract_patterns(elem, config_name)
                        if pattern:
                            patterns.append(pattern)
                        
                        current_obj = None
                    
                    # Очищаем элемент из памяти
                    elem.clear()
                    root.clear()
                    
                    if elem in obj_stack:
                        obj_stack.remove(elem)
            
            return {
                "modules": modules,
                "patterns": patterns,
                "api_usage": api_usage,
                "status": "success"
            }
        
        except ET.ParseError as e:
            print(f"[ERROR] Ошибка парсинга XML: {e}")
            return {"status": "error", "error": str(e)}
        except Exception as e:
            print(f"[ERROR] Ошибка обработки: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e)}
    
    def extract_object_data(self, obj: Dict, config_name: str, config_file: Path) -> Optional[Dict[str, Any]]:
        """Извлечение данных объекта"""
        try:
            elem = obj['element']
            obj_type = obj['type']
            obj_name = obj['name']
            
            if not obj_name:
                return None
            
            # Поиск модулей объекта
            modules_data = []
            
            # Объектный модуль
            obj_module = elem.find('.//ObjectModule')
            if obj_module is not None and obj_module.text:
                modules_data.append({
                    'type': 'ObjectModule',
                    'code': obj_module.text[:5000],
                    'name': f'{obj_type}_{obj_name}_ОбъектныйМодуль'
                })
            
            # Модуль формы
            form_modules = elem.findall('.//FormModule')
            for form_module in form_modules:
                if form_module.text:
                    modules_data.append({
                        'type': 'FormModule',
                        'code': form_module.text[:5000],
                        'name': f'{obj_type}_{obj_name}_МодульФормы'
                    })
            
            # Модуль команды
            command_modules = elem.findall('.//CommandModule')
            for cmd_module in command_modules:
                if cmd_module.text:
                    modules_data.append({
                        'type': 'CommandModule',
                        'code': cmd_module.text[:5000],
                        'name': f'{obj_type}_{obj_name}_МодульКоманды'
                    })
            
            # Общий модуль
            if obj_type == 'CommonModule':
                module_elem = elem.find('.//Module')
                if module_elem is not None and module_elem.text:
                    modules_data.append({
                        'type': 'CommonModule',
                        'code': module_elem.text[:5000],
                        'name': f'ОбщийМодуль_{obj_name}'
                    })
            
            if not modules_data:
                return None
            
            # Сохраняем каждый модуль
            for module_data in modules_data:
                functions = self.extract_functions(module_data['code'])
                
                full_module_data = {
                    "name": module_data['name'],
                    "object_type": obj_type,
                    "object_name": obj_name,
                    "module_type": module_data['type'],
                    "code": module_data['code'],
                    "source_file": str(config_file.relative_to(self.config_dir)),
                    "functions": functions,
                    "description": f"Модуль {obj_type} {obj_name}"
                }
                
                # Добавляем в базу знаний
                self.kb.add_module_documentation(
                    config_name=config_name.lower(),
                    module_name=full_module_data["name"],
                    documentation=full_module_data
                )
            
            return {
                "object_name": obj_name,
                "object_type": obj_type,
                "modules_count": len(modules_data)
            }
        
        except Exception as e:
            print(f"[WARN] Ошибка извлечения данных объекта: {e}")
            return None
    
    def extract_functions(self, code: str) -> List[Dict[str, Any]]:
        """Извлечение функций из BSL кода"""
        functions = []
        
        if not code or len(code) < 10:
            return functions
        
        # Паттерн для функций и процедур BSL
        pattern = r'(?:Функция|Процедура)\s+(\w+)\s*(?:\(([^)]*)\))?'
        
        matches = re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE)
        
        for match in matches:
            func_name = match.group(1)
            params_str = match.group(2) or ""
            
            # Парсинг параметров
            params = []
            if params_str:
                for param in re.split(r',\s*(?![^()]*\))', params_str):
                    param = param.strip()
                    if param:
                        # Извлекаем имя параметра
                        param_name = param.split('=')[0].strip().split()[0]
                        params.append(param_name)
            
            functions.append({
                "name": func_name,
                "parameters": params,
                "signature": match.group(0)[:200]  # Ограничиваем длину
            })
            
            if len(functions) >= 50:  # Ограничиваем количество
                break
        
        return functions
    
    def extract_patterns(self, elem: ET.Element, config_name: str) -> Optional[Dict[str, Any]]:
        """Извлечение паттернов использования"""
        try:
            # Поиск типичных паттернов 1С
            code_elements = elem.findall('.//*')
            patterns_found = []
            
            for code_elem in code_elements:
                if code_elem.text:
                    text = code_elem.text
                    
                    # Паттерн: Запрос
                    if re.search(r'Новый\s+Запрос', text, re.IGNORECASE):
                        patterns_found.append({
                            "type": "query",
                            "pattern": "Новый Запрос",
                            "description": "Использование запросов к БД"
                        })
                    
                    # Паттерн: Обработка ошибок
                    if re.search(r'Попытка\s+.*\s+Исключение', text, re.IGNORECASE):
                        patterns_found.append({
                            "type": "error_handling",
                            "pattern": "Попытка-Исключение",
                            "description": "Обработка исключений"
                        })
            
            if patterns_found:
                return {
                    "configuration": config_name.lower(),
                    "patterns": patterns_found
                }
        
        except Exception as e:
            pass
        
        return None


def load_all_configurations():
    """Загрузка всех конфигураций"""
    print("=" * 60)
    print("Загрузка конфигураций 1С в базу знаний")
    print("=" * 60)
    
    parser = OneCConfigParser()
    config_dir = Path("./1c_configurations")
    
    # Поддерживаемые конфигурации (расширенный список)
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
    
    # Поиск всех config.xml файлов
    config_files = list(config_dir.rglob("config.xml"))
    
    print(f"\n[INFO] Найдено файлов конфигураций: {len(config_files)}")
    
    for config_file in config_files:
        # Определяем конфигурацию по имени директории
        parent_dir = config_file.parent.name
        config_name = parent_dir.upper()
        
        # Проверяем, поддерживается ли конфигурация
        if config_name not in supported_configs:
            print(f"[SKIP] Неизвестная конфигурация: {config_name}")
            print(f"[INFO] Добавьте её в supported_configs если нужно обработать")
            continue
        
        config_full_name = supported_configs[config_name]
        print(f"\n[INFO] Обработка: {config_name} ({config_full_name})")
        
        print(f"\n{'='*60}")
        print(f"Обработка: {config_name}")
        print(f"{'='*60}")
        
        try:
            result = parser.parse_configuration(config_name, config_file)
            
            if result["status"] == "success":
                modules_count = len(result.get("modules", []))
                total_modules += modules_count
                results[config_name] = {
                    "modules": modules_count,
                    "patterns": len(result.get("patterns", [])),
                    "status": "success"
                }
                print(f"[OK] Загружено: {modules_count} модулей")
            else:
                results[config_name] = result
                print(f"[ERROR] Ошибка: {result.get('error', 'Unknown')}")
        
        except Exception as e:
            print(f"[ERROR] Критическая ошибка: {e}")
            results[config_name] = {"status": "error", "error": str(e)}
    
    print("\n" + "=" * 60)
    print("Итоги:")
    print("=" * 60)
    
    for config_name, result in results.items():
        if result.get("status") == "success":
            print(f"[OK] {config_name}: {result.get('modules', 0)} модулей")
        else:
            print(f"[ERROR] {config_name}: {result.get('error', 'Unknown error')}")
    
    print(f"\n[OK] Всего загружено модулей: {total_modules}")
    print("\n[OK] Загрузка завершена!")
    
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

