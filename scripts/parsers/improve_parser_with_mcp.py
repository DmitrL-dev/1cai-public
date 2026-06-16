
#!/usr/bin/env python3
"""
Улучшенный парсер конфигураций 1С на основе логики mcp_Метаданные
Версия: 2.0.0
"""

import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

try:
    from src.services.configuration_knowledge_base import get_knowledge_base
except ImportError as e:
    print(f"[ERROR] Ошибка импорта: {e}")
    sys.exit(1)


class Improved1CConfigParser:
    """
    Улучшенный парсер на основе логики из mcp_Метаданные
    Понимает структуру 1С конфигураций и извлекает все модули
    """
    
    # Типы объектов метаданных 1С (из знаний о структуре)
    METADATA_OBJECT_TYPES = {
        # Основные объекты
        'Документ': 'Document',
        'Справочник': 'Catalog',
        'ОбщийМодуль': 'CommonModule',
        'РегистрСведений': 'RegisterInformation',
        'РегистрНакопления': 'RegisterAccumulation',
        'РегистрБухгалтерии': 'RegisterAccounting',
        'Отчет': 'Report',
        'Обработка': 'DataProcessor',
        'ПланСчетов': 'ChartOfAccounts',
        'ПланВидовХарактеристик': 'ChartOfCharacteristicTypes',
        'ПланВидовРасчета': 'ChartOfCalculationTypes',
        'БизнесПроцесс': 'BusinessProcess',
        'Задача': 'Task',
        'Константа': 'Constant',
        'Перечисление': 'Enum',
        'ВнешняяОбработка': 'ExternalDataProcessor',
        'ВнешнийОтчет': 'ExternalReport',
        'HTTPСервис': 'HTTPService',
        'WSСсылка': 'WSReference',
        'ПланОбмена': 'ExchangePlan',
        
        # Английские варианты (для совместимости)
        'Document': 'Document',
        'Catalog': 'Catalog',
        'CommonModule': 'CommonModule',
        'RegisterInformation': 'RegisterInformation',
        'RegisterAccumulation': 'RegisterAccumulation',
        'RegisterAccounting': 'RegisterAccounting',
        'Report': 'Report',
        'DataProcessor': 'DataProcessor',
    }
    
    # Типы модулей в объектах 1С
    MODULE_TYPES = {
        'Модуль': 'Module',                    # Общий модуль
        'МодульОбъекта': 'ObjectModule',        # Модуль объекта
        'МодульМенеджера': 'ManagerModule',     # Модуль менеджера
        'МодульФормы': 'FormModule',           # Модуль формы
        'МодульКоманды': 'CommandModule',       # Модуль команды
        'МодульНабораЗаписей': 'RecordSetModule', # Модуль набора записей
    }
    
    def __init__(self):
        self.kb = get_knowledge_base()
        self.config_dir = Path("./1c_configurations")
        self.stats = defaultdict(int)
    
    def parse_configuration(self, config_name: str, config_file: Path) -> Dict[str, Any]:
        """Парсинг конфигурации 1С с улучшенной логикой"""
        file_size_mb = config_file.stat().st_size / 1024 / 1024
        print(f"[INFO] Парсинг {config_file.name} ({file_size_mb:.1f} MB)...")
        
        try:
            # Правильно обрабатываем UTF-8 BOM
            with open(config_file, 'rb') as f:
                raw_bytes = f.read()
                if raw_bytes.startswith(b'\xef\xbb\xbf'):
                    raw_bytes = raw_bytes[3:]
                content = raw_bytes.decode('utf-8')
            
            # Парсим XML
            root = ET.fromstring(content)
            
            print(f"[INFO] Root tag: {root.tag}")
            
            # Извлекаем все метаданные
            metadata = self.extract_all_metadata(root, config_name, config_file)
            
            # Сохраняем в базу знаний
            for module in metadata.get('modules', []):
                self.save_module_to_kb(module, config_name)
            
            return {
                'status': 'success',
                'modules': metadata['modules'],
                'objects': metadata['objects'],
                'stats': dict(self.stats)
            }
            
        except Exception as e:
            print(f"[ERROR] Ошибка парсинга: {e}")
            import traceback
            traceback.print_exc()
            return {'status': 'error', 'error': str(e)}
    
    def extract_all_metadata(self, root: ET.Element, config_name: str, config_file: Path) -> Dict[str, Any]:
        """Извлечение всех метаданных из корня XML"""
        modules = []
        objects = []
        
        # Проходим по всем типам объектов метаданных
        for obj_type_ru, obj_type_en in self.METADATA_OBJECT_TYPES.items():
            # Ищем объекты на русском
            found_objs = root.findall(f'.//{obj_type_ru}')
            
            # Ищем объекты на английском (для совместимости)
            if not found_objs:
                found_objs = root.findall(f'.//{obj_type_en}')
            
            if found_objs:
                print(f"[INFO] Найдено {obj_type_ru}: {len(found_objs)}")
                self.stats['objects'] += len(found_objs)
                
                for obj in found_objs:
                    obj_name = obj.get('name', '') or obj.get('Имя', '')
                    if not obj_name:
                        continue
                    
                    # Извлекаем модули из объекта
                    obj_modules = self.extract_object_modules(obj, obj_type_ru, obj_name, config_name, config_file)
                    modules.extend(obj_modules)
                    
                    objects.append({
                        'type': obj_type_ru,
                        'name': obj_name,
                        'modules_count': len(obj_modules)
                    })
        
        return {
            'modules': modules,
            'objects': objects
        }
    
    def extract_object_modules(
        self,
        obj: ET.Element,
        obj_type: str,
        obj_name: str,
        config_name: str,
        config_file: Path
    ) -> List[Dict[str, Any]]:
        """Извлечение всех модулей из объекта"""
        modules = []
        
        # Ищем все типы модулей
        for module_type_ru, module_type_en in self.MODULE_TYPES.items():
            # Ищем модуль на русском
            module_elem = obj.find(f'.//{module_type_ru}')
            
            # Ищем на английском
            if not module_elem:
                module_elem = obj.find(f'.//{module_type_en}')
            
            # Ищем альтернативные варианты
            if not module_elem:
                # Пробуем разные варианты написания
                alt_variants = [
                    f'Модуль{obj_type}',
                    f'{obj_type}Модуль',
                    f'{obj_type}.Модуль',
                    f'{module_type_ru}',
                    'Модуль',
                    'Module'
                ]
                
                for variant in alt_variants:
                    module_elem = obj.find(f'.//{variant}')
                    if module_elem is not None:
                        break
            
            if module_elem is not None and module_elem.text:
                module_code = module_elem.text.strip()
                
                if module_code and len(module_code) > 10:
                    # Извлекаем функции
                    functions = self.extract_functions(module_code)
                    
                    module_data = {
                        'name': f"{obj_type}.{obj_name}.{module_type_ru}",
                        'object_type': obj_type,
                        'object_name': obj_name,
                        'module_type': module_type_ru,
                        'code': module_code,
                        'functions': functions,
                        'functions_count': len(functions),
                        'source_file': str(config_file.relative_to(self.config_dir)),
                        'description': f"Модуль {module_type_ru} объекта {obj_type} {obj_name}"
                    }
                    
                    modules.append(module_data)
                    self.stats['modules'] += 1
                    self.stats['functions'] += len(functions)
        
        # Специальная обработка для форм
        forms = obj.findall('.//Форма') or obj.findall('.//Form')
        for form in forms:
            form_name = form.get('name', '') or form.get('Имя', '')
            form_module_elem = form.find('.//МодульФормы') or form.find('.//FormModule')
            
            if form_module_elem and form_module_elem.text:
                form_code = form_module_elem.text.strip()
                if form_code and len(form_code) > 10:
                    functions = self.extract_functions(form_code)
                    
                    module_data = {
                        'name': f"{obj_type}.{obj_name}.Форма.{form_name}",
                        'object_type': obj_type,
                        'object_name': obj_name,
                        'module_type': 'МодульФормы',
                        'code': form_code,
                        'functions': functions,
                        'functions_count': len(functions),
                        'source_file': str(config_file.relative_to(self.config_dir)),
                        'description': f"Модуль формы {form_name} объекта {obj_type} {obj_name}"
                    }
                    
                    modules.append(module_data)
                    self.stats['modules'] += 1
                    self.stats['functions'] += len(functions)
        
        return modules
    
    def extract_functions(self, code: str) -> List[Dict[str, Any]]:
        """Извлечение функций из BSL кода (улучшенная версия)"""
        functions = []
        
        if not code or len(code) < 10:
            return functions
        
        # Улучшенное регулярное выражение для функций и процедур
        # Учитываем различные стили написания
        patterns = [
            # Стандартный формат
            r'(?:^|\n)\s*(?:Экспорт\s+)?(Функция|Процедура)\s+([\wА-Яа-я]+)\s*\(([^)]*)\)',
            # С дефисами в именах
            r'(?:^|\n)\s*(?:Экспорт\s+)?(Функция|Процедура)\s+([\wА-Яа-я\-]+)\s*\(([^)]*)\)',
            # Без параметров
            r'(?:^|\n)\s*(?:Экспорт\s+)?(Функция|Процедура)\s+([\wА-Яа-я]+)\s*\(\)',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE):
                func_type = match.group(1).strip()
                func_name = match.group(2).strip()
                params_str = match.group(3).strip() if match.lastindex >= 3 else ""
                
                # Находим тело функции
                start_pos = match.start()
                func_code = self.extract_function_body(code, start_pos)
                
                # Парсим параметры
                params = self.parse_bsl_params(params_str)
                
                functions.append({
                    'name': func_name,
                    'type': func_type,
                    'params': params,
                    'params_count': len(params),
                    'code_snippet': func_code[:500]  # Ограничиваем длину
                })
        
        return functions
    
    def extract_function_body(self, code: str, start_pos: int) -> str:
        """Извлечение тела функции из кода"""
        # Ищем конец функции
        end_keywords = [
            'КонецФункции',
            'КонецПроцедуры',
            'EndFunction',
            'EndProcedure'
        ]
        
        code_after_start = code[start_pos:]
        min_end_pos = len(code_after_start)
        
        for end_kw in end_keywords:
            pattern = r'^\s*' + re.escape(end_kw) + r'\s*$'
            end_match = re.search(pattern, code_after_start, re.IGNORECASE | re.MULTILINE)
            if end_match:
                min_end_pos = min(min_end_pos, end_match.start())
        
        if min_end_pos < len(code_after_start):
            return code_after_start[:min_end_pos]
        else:
            return code_after_start[:1000]  # Ограничиваем длину
    
    def parse_bsl_params(self, params_str: str) -> List[str]:
        """Парсинг параметров BSL функции"""
        params = []
        
        if not params_str or not params_str.strip():
            return params
        
        # Разделяем параметры, учитывая вложенные скобки для типов
        # Пример: "Значение: Произвольный, Параметр2 = 10, Параметр3(Тип)"
        current_param = ""
        paren_depth = 0
        
        for char in params_str:
            if char == '(':
                paren_depth += 1
                current_param += char
            elif char == ')':
                paren_depth -= 1
                current_param += char
            elif char == ',' and paren_depth == 0:
                # Это разделитель параметров
                param_name = self.extract_param_name(current_param.strip())
                if param_name:
                    params.append(param_name)
                current_param = ""
            else:
                current_param += char
        
        # Последний параметр
        if current_param.strip():
            param_name = self.extract_param_name(current_param.strip())
            if param_name:
                params.append(param_name)
        
        return params
    
    def extract_param_name(self, param_str: str) -> str:
        """Извлечение имени параметра из строки параметра"""
        # Примеры: "Параметр", "Параметр: Тип", "Параметр = Значение", "Параметр(Тип)"
        # Извлекаем имя до первого двоеточия, знака равенства или скобки
        
        # Убираем пробелы
        param_str = param_str.strip()
        
        # Ищем имя параметра
        for delimiter in [':', '=', '(']:
            if delimiter in param_str:
                param_str = param_str.split(delimiter)[0].strip()
        
        return param_str.strip()
    
    def save_module_to_kb(self, module: Dict[str, Any], config_name: str):
        """Сохранение модуля в базу знаний"""
        try:
            self.kb.add_module_documentation(
                config_name=config_name.lower(),
                module_name=module['name'],
                documentation=module
            )
        except Exception as e:
            print(f"[WARN] Ошибка сохранения модуля {module['name']}: {e}")


def load_all_configurations():
    """Загрузка всех конфигураций с улучшенным парсером"""
    print("=" * 70)
    print("УЛУЧШЕННЫЙ ПАРСЕР КОНФИГУРАЦИЙ 1С")
    print("Основан на логике mcp_Метаданные")
    print("=" * 70)
    
    parser = Improved1CConfigParser()
    config_dir = Path("./1c_configurations")
    
    # Поддерживаемые конфигурации
    supported_configs = {
        "ERP": "ERP Управление предприятием 2",
        "UT": "Управление торговлей",
        "ZUP": "Зарплата и управление персоналом",
        "BUH": "Бухгалтерия предприятия",
        "HOLDING": "Управление холдингом",
        "BUHBIT": "Бухгалтерия БИТ",
        "DO": "Документооборот",
        "KA": "Комплексная автоматизация"
    }
    
    results = {}
    
    # Поиск всех config.xml файлов
    config_files = list(config_dir.rglob("config.xml"))
    
    print(f"\n[INFO] Найдено файлов конфигураций: {len(config_files)}\n")
    
    for config_file in config_files:
        # Определяем конфигурацию по имени директории
        parent_dir = config_file.parent.name
        config_name = parent_dir.upper()
        
        if config_name not in supported_configs:
            print(f"[SKIP] Неизвестная конфигурация: {config_name}")
            continue
        
        config_full_name = supported_configs[config_name]
        
        print(f"{'='*70}")
        print(f"Обработка: {config_name} ({config_full_name})")
        print(f"{'='*70}")
        
        parse_result = parser.parse_configuration(config_name, config_file)
        
        if parse_result["status"] == "success":
            modules_count = len(parse_result["modules"])
            objects_count = len(parse_result["objects"])
            functions_count = parser.stats['functions']
            
            results[config_name] = {
                "modules_found": modules_count,
                "objects_found": objects_count,
                "functions_found": functions_count,
                "status": "OK"
            }
            
            print(f"[OK] {config_name}: {modules_count} модулей, {objects_count} объектов, {functions_count} функций")
        else:
            results[config_name] = {
                "modules_found": 0,
                "objects_found": 0,
                "functions_found": 0,
                "status": f"ERROR: {parse_result.get('error', 'Unknown')}"
            }
            print(f"[ERROR] {config_name}: {parse_result.get('error', 'Unknown')}")
        
        # Сброс статистики для следующей конфигурации
        parser.stats.clear()
    
    print(f"\n{'='*70}")
    print("ИТОГИ:")
    print(f"{'='*70}")
    
    total_modules = 0
    total_objects = 0
    total_functions = 0
    
    for config, data in results.items():
        if data.get("status") == "OK":
            modules = data.get("modules_found", 0)
            objects = data.get("objects_found", 0)
            functions = data.get("functions_found", 0)
            total_modules += modules
            total_objects += objects
            total_functions += functions
            
            print(f"[OK] {config:10} | Модулей: {modules:4} | Объектов: {objects:4} | Функций: {functions:4}")
        else:
            print(f"[ERROR] {config:10} | {data.get('status', 'Unknown')}")
    
    print(f"{'='*70}")
    print(f"ВСЕГО: {total_modules} модулей, {total_objects} объектов, {total_functions} функций")
    print(f"{'='*70}")
    
    print("\n[OK] Парсинг завершен!")
    print("\nСледующие шаги:")
    print("1. Проверить базу знаний: GET /api/knowledge-base/configurations")
    print("2. Использовать данные в Code Review")
    print("3. Извлечь дополнительные паттерны")


if __name__ == "__main__":
    load_all_configurations()





