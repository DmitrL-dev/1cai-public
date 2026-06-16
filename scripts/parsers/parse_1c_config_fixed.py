
#!/usr/bin/env python3
"""
Исправленный парсер конфигураций 1С с поддержкой namespace
Версия: 3.0.0
"""

import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

try:
    from improve_bsl_parser import ImprovedBSLParser

    from src.services.configuration_knowledge_base import get_knowledge_base
except ImportError as e:
    print(f"[ERROR] Ошибка импорта: {e}")
    sys.exit(1)


class Fixed1CConfigParser:
    """
    Исправленный парсер конфигураций 1С с поддержкой namespace
    Правильно обрабатывает структуру XML и извлекает все модули
    """
    
    # Типы объектов метаданных 1С (с namespace)
    METADATA_OBJECT_TYPES = {
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
    }
    
    # Типы модулей в объектах 1С
    MODULE_TYPES = {
        'Модуль': 'Module',
        'МодульОбъекта': 'ObjectModule',
        'МодульМенеджера': 'ManagerModule',
        'МодульФормы': 'FormModule',
        'МодульКоманды': 'CommandModule',
        'МодульНабораЗаписей': 'RecordSetModule',
    }
    
    def __init__(self):
        self.kb = get_knowledge_base()
        self.config_dir = Path("./1c_configurations")
        self.stats = defaultdict(int)
        self.bsl_parser = ImprovedBSLParser()
        self.namespace = None
    
    def parse_configuration(self, config_name: str, config_file: Path) -> Dict[str, Any]:
        """Парсинг конфигурации 1С с правильной обработкой namespace"""
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
            
            # Определяем namespace
            self.namespace = self._detect_namespace(root)
            print(f"[INFO] Namespace: {self.namespace}")
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
    
    def _detect_namespace(self, root: ET.Element) -> Optional[str]:
        """Определение namespace из корневого элемента"""
        if '}' in root.tag:
            namespace = root.tag.split('}')[0][1:]
            return namespace
        
        # Пробуем найти namespace в атрибутах
        for attr_name, attr_value in root.attrib.items():
            if 'xmlns' in attr_name:
                return attr_value
        
        return None
    
    def _make_tag(self, tag_name: str) -> str:
        """Создание тега с учетом namespace"""
        if self.namespace:
            return f"{{{self.namespace}}}{tag_name}"
        return tag_name
    
    def extract_all_metadata(self, root: ET.Element, config_name: str, config_file: Path) -> Dict[str, Any]:
        """Извлечение всех метаданных из корня XML"""
        modules = []
        objects = []
        
        # Маппинг типов объектов на префиксы в тегах XML
        object_prefixes = {
            'Документ': ['DocumentObject.', 'Document.'],
            'Справочник': ['CatalogObject.', 'Catalog.'],
            'ОбщийМодуль': ['CommonModuleObject.', 'CommonModule.'],
            'РегистрСведений': ['InformationRegisterObject.', 'RegisterInformationObject.'],
            'РегистрНакопления': ['AccumulationRegisterObject.', 'RegisterAccumulationObject.'],
            'РегистрБухгалтерии': ['AccountingRegisterObject.', 'RegisterAccountingObject.'],
            'Отчет': ['ReportObject.', 'Report.'],
            'Обработка': ['DataProcessorObject.', 'DataProcessor.'],
        }
        
        # Проходим по всем типам объектов метаданных
        for obj_type_ru, obj_type_en in self.METADATA_OBJECT_TYPES.items():
            found_objs = []
            
            # Ищем объекты с различными префиксами
            if obj_type_ru in object_prefixes:
                for prefix in object_prefixes[obj_type_ru]:
                    # Ищем с русским именем объекта после точки
                    pattern = f'{prefix}{obj_type_ru}'
                    found = [e for e in root.iter() if e.tag.startswith(pattern)]
                    if found:
                        found_objs.extend(found)
                        break
                    
                    # Пробуем английский вариант
                    pattern_en = f'{prefix}{obj_type_en}'
                    found = [e for e in root.iter() if e.tag.startswith(pattern_en)]
                    if found:
                        found_objs.extend(found)
                        break
            
            # Если не нашли через префиксы, пробуем стандартные способы
            if not found_objs:
                # Ищем объекты на русском с namespace
                found_objs = root.findall(f'.//{self._make_tag(obj_type_ru)}')
                
                # Если не нашли с namespace, пробуем без
                if not found_objs:
                    found_objs = root.findall(f'.//{obj_type_ru}')
                
                # Пробуем английские варианты
                if not found_objs:
                    found_objs = root.findall(f'.//{self._make_tag(obj_type_en)}')
                
                if not found_objs:
                    found_objs = root.findall(f'.//{obj_type_en}')
            
            # Альтернативный способ: ищем все элементы с нужным паттерном в теге
            if not found_objs:
                # Ищем по паттерну в теге (например, содержит "CatalogObject" и "Справочник")
                for elem in root.iter():
                    tag_lower = elem.tag.lower()
                    type_ru_lower = obj_type_ru.lower()
                    type_en_lower = obj_type_en.lower()
                    
                    if (type_ru_lower in tag_lower or type_en_lower in tag_lower) and \
                       any(keyword in tag_lower for keyword in ['object', 'catalog', 'document', 'commonmodule', 'register']):
                        found_objs.append(elem)
            
            if found_objs:
                print(f"[INFO] Найдено {obj_type_ru}: {len(found_objs)}")
                self.stats['objects'] += len(found_objs)
                
                for obj in found_objs:
                    obj_name = self._get_element_name(obj)
                    if not obj_name:
                        continue
                    
                    # Извлекаем модули из объекта
                    obj_modules = self.extract_object_modules(
                        obj, obj_type_ru, obj_name, config_name, config_file
                    )
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
    
    def _get_element_name(self, elem: ET.Element) -> str:
        """Извлечение имени объекта из элемента"""
        # Пробуем разные варианты
        name_attrs = ['Имя', 'name', 'Name', 'NameUuid', 'uuid', 'Uuid']
        
        for attr in name_attrs:
            if attr in elem.attrib:
                value = elem.attrib[attr]
                if value:
                    return value
        
        # Извлекаем имя из тега (например, CatalogObject.Справочник -> Справочник)
        tag = elem.tag
        if '.' in tag:
            parts = tag.split('.')
            if len(parts) > 1:
                # Возвращаем последнюю часть тега как имя объекта
                return parts[-1]
        
        # Ищем в дочерних элементах Properties
        props = elem.find('.//Properties') or elem.find('.//' + self._make_tag('Properties'))
        if props is not None:
            name_elem = props.find('.//Name') or props.find('.//' + self._make_tag('Name'))
            if name_elem is not None and name_elem.text:
                return name_elem.text.strip()
        
        # Ищем Name напрямую в элементе
        name_elem = elem.find('.//Name') or elem.find('.//' + self._make_tag('Name'))
        if name_elem is not None and name_elem.text:
            return name_elem.text.strip()
        
        # Пробуем получить имя из текста элемента или его дочерних элементов
        if elem.text and elem.text.strip():
            return elem.text.strip()[:100]  # Ограничиваем длину
        
        return ''
    
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
            # Ищем модуль с namespace
            module_elem = obj.find(f'.//{self._make_tag(module_type_ru)}')
            
            # Без namespace
            if module_elem is None:
                module_elem = obj.find(f'.//{module_type_ru}')
            
            # Английские варианты
            if module_elem is None:
                module_elem = obj.find(f'.//{self._make_tag(module_type_en)}')
            
            if module_elem is None:
                module_elem = obj.find(f'.//{module_type_en}')
            
            # Альтернативные варианты
            if module_elem is None:
                alt_variants = [
                    f'Модуль{obj_type}',
                    f'{obj_type}Модуль',
                    f'{obj_type}.Модуль',
                ]
                
                for variant in alt_variants:
                    module_elem = obj.find(f'.//{self._make_tag(variant)}') or obj.find(f'.//{variant}')
                    if module_elem is not None:
                        break
            
            if module_elem is not None:
                # Извлекаем код модуля
                module_code = self._extract_module_code(module_elem)
                
                if module_code and len(module_code) > 10:
                    # Парсим BSL код
                    bsl_result = self.bsl_parser.parse(module_code)
                    
                    module_data = {
                        'name': f"{obj_type}.{obj_name}.{module_type_ru}",
                        'object_type': obj_type,
                        'object_name': obj_name,
                        'module_type': module_type_ru,
                        'code': module_code,
                        'functions': bsl_result['functions'],
                        'procedures': bsl_result['procedures'],
                        'regions': bsl_result['regions'],
                        'api_usage': bsl_result['api_usage'],
                        'functions_count': len(bsl_result['functions']),
                        'source_file': str(config_file.relative_to(self.config_dir)),
                        'description': f"Модуль {module_type_ru} объекта {obj_type} {obj_name}"
                    }
                    
                    modules.append(module_data)
                    self.stats['modules'] += 1
                    self.stats['functions'] += len(bsl_result['functions'])
        
        # Специальная обработка для форм
        forms = obj.findall('.//' + self._make_tag('Форма')) or obj.findall('.//Form') or obj.findall('.//Форма')
        for form in forms:
            form_name = self._get_element_name(form)
            form_module_elem = form.find('.//' + self._make_tag('МодульФормы')) or form.find('.//FormModule') or form.find('.//МодульФормы')
            
            if form_module_elem is not None:
                form_code = self._extract_module_code(form_module_elem)
                if form_code and len(form_code) > 10:
                    bsl_result = self.bsl_parser.parse(form_code)
                    
                    module_data = {
                        'name': f"{obj_type}.{obj_name}.Форма.{form_name}",
                        'object_type': obj_type,
                        'object_name': obj_name,
                        'module_type': 'МодульФормы',
                        'code': form_code,
                        'functions': bsl_result['functions'],
                        'procedures': bsl_result['procedures'],
                        'regions': bsl_result['regions'],
                        'api_usage': bsl_result['api_usage'],
                        'functions_count': len(bsl_result['functions']),
                        'source_file': str(config_file.relative_to(self.config_dir)),
                        'description': f"Модуль формы {form_name} объекта {obj_type} {obj_name}"
                    }
                    
                    modules.append(module_data)
                    self.stats['modules'] += 1
                    self.stats['functions'] += len(bsl_result['functions'])
        
        return modules
    
    def _extract_module_code(self, module_elem: ET.Element) -> str:
        """Извлечение кода модуля из элемента"""
        # Код может быть в тексте элемента или в дочернем элементе
        if module_elem.text:
            return module_elem.text.strip()
        
        # Ищем в дочерних элементах
        for child in module_elem:
            if child.text:
                return child.text.strip()
        
        # Пробуем найти элемент с кодом
        code_elem = module_elem.find('.//Code') or module_elem.find('.//' + self._make_tag('Code')) or module_elem.find('.//Код')
        if code_elem is not None and code_elem.text:
            return code_elem.text.strip()
        
        return ''
    
    def save_module_to_kb(self, module: Dict[str, Any], config_name: str):
        """Сохранение модуля в базу знаний"""
        try:
            # Преобразуем функции для базы знаний
            functions_for_kb = []
            for func in module.get('functions', []):
                functions_for_kb.append({
                    'name': func['name'],
                    'type': func['type'],
                    'params': [p['name'] for p in func.get('params', [])],
                    'params_detailed': func.get('params', []),
                    'exported': func.get('exported', False),
                    'region': func.get('region'),
                    'comments': func.get('comments', '')
                })
            
            self.kb.add_module_documentation(
                config_name=config_name.lower(),
                module_name=module['name'],
                documentation={
                    'description': module.get('description', ''),
                    'code': module.get('code', ''),
                    'functions': functions_for_kb,
                    'object_type': module.get('object_type'),
                    'object_name': module.get('object_name'),
                    'module_type': module.get('module_type'),
                    'regions': module.get('regions', []),
                    'api_usage': module.get('api_usage', []),
                    'source': 'xml_parser'
                }
            )
        except Exception as e:
            print(f"[WARN] Ошибка сохранения модуля {module.get('name', 'Unknown')}: {e}")


def load_all_configurations():
    """Загрузка всех конфигураций с исправленным парсером"""
    print("=" * 70)
    print("ИСПРАВЛЕННЫЙ ПАРСЕР КОНФИГУРАЦИЙ 1С")
    print("С поддержкой namespace и улучшенным парсингом BSL")
    print("=" * 70)
    
    parser = Fixed1CConfigParser()
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
    
    # Поиск всех config.xml файлов
    config_files = list(config_dir.rglob("config.xml"))
    
    print(f"\n[INFO] Найдено файлов конфигураций: {len(config_files)}\n")
    
    results = {}
    
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

