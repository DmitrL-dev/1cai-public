
#!/usr/bin/env python3
"""
Парсер конфигураций 1С экспортированных из EDT
Версия: 2.0.0 - PostgreSQL Integration
"""

import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

try:
    from improve_bsl_parser import ImprovedBSLParser
except ImportError:
    print("[WARN] ImprovedBSLParser not found, using basic parsing")
    ImprovedBSLParser = None

try:
    POSTGRES_AVAILABLE = True
except ImportError:
    print("[WARN] psycopg2 not installed. Install: pip install psycopg2-binary")
    POSTGRES_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("[WARN] python-dotenv not installed. Using system environment.")


class EDTXMLParser:
    """
    Парсер конфигураций 1С экспортированных из EDT
    Обрабатывает множественные XML файлы в структуре каталогов
    Версия 2.0: Сохранение в PostgreSQL вместо JSON
    """
    
    def __init__(self, use_postgres=True):
        """
        Args:
            use_postgres: Использовать PostgreSQL (True) или JSON (False - legacy)
        """
        self.use_postgres = use_postgres and POSTGRES_AVAILABLE
        self.config_dir = Path("./1c_configurations")
        self.stats = defaultdict(int)
        
        # BSL Parser
        if ImprovedBSLParser:
            self.bsl_parser = ImprovedBSLParser()
        else:
            self.bsl_parser = None
        
        # Database connection
        if self.use_postgres:
            try:
                from src.db.postgres_saver import PostgreSQLSaver
                self.db_saver = PostgreSQLSaver()
                if self.db_saver.connect():
                    print("[INFO] PostgreSQL connection established")
                else:
                    print("[WARN] PostgreSQL connection failed, falling back to JSON")
                    self.use_postgres = False
                    self.db_saver = None
            except Exception as e:
                print(f"[WARN] Failed to initialize PostgreSQL: {e}")
                self.use_postgres = False
                self.db_saver = None
        else:
            self.db_saver = None
            print("[INFO] Using JSON storage (legacy mode)")
    
    def parse_edt_configuration(self, config_name: str, config_path: Path) -> Dict[str, Any]:
        """
        Парсинг конфигурации из EDT XML файлов
        
        Args:
            config_name: Название конфигурации
            config_path: Путь к директории с XML файлами
            
        Returns:
            Результаты парсинга
        """
        print(f"[INFO] Парсинг EDT конфигурации: {config_name}")
        print(f"[INFO] Директория: {config_path}")
        print(f"[INFO] Режим сохранения: {'PostgreSQL' if self.use_postgres else 'JSON (legacy)'}")
        
        modules = []
        objects = []
        
        # Если используем PostgreSQL, создаем конфигурацию
        config_id = None
        if self.use_postgres:
            config_id = self.db_saver.save_configuration({
                'name': config_name,
                'full_name': f'Конфигурация {config_name}',
                'source_path': str(config_path),
                'metadata': {}
            })
            
            if not config_id:
                print("[ERROR] Failed to save configuration to PostgreSQL")
                return {'status': 'error', 'error': 'Database error'}
        
        # Обрабатываем общие модули
        common_modules_path = config_path / "CommonModules"
        if common_modules_path.exists():
            print(f"[INFO] Обработка общих модулей...")
            cm_modules = self.parse_common_modules(common_modules_path, config_name)
            modules.extend(cm_modules)
            objects.extend([{'type': 'ОбщийМодуль', 'name': m['object_name'], 'modules_count': 1} for m in cm_modules])
        
        # Обрабатываем документы
        documents_path = config_path / "Documents"
        if documents_path.exists():
            print(f"[INFO] Обработка документов...")
            doc_result = self.parse_documents(documents_path, config_name)
            modules.extend(doc_result['modules'])
            objects.extend(doc_result['objects'])
        
        # Обрабатываем справочники
        catalogs_path = config_path / "Catalogs"
        if catalogs_path.exists():
            print(f"[INFO] Обработка справочников...")
            cat_result = self.parse_catalogs(catalogs_path, config_name)
            modules.extend(cat_result['modules'])
            objects.extend(cat_result['objects'])
        
        # Сохраняем в базу данных
        print(f"[INFO] Сохранение в базу данных...")
        
        if self.use_postgres and config_id:
            # Сохраняем в PostgreSQL
            for obj in objects:
                obj_id = self.db_saver.save_object(config_id, obj)
            
            for module in modules:
                # Find object_id if this module belongs to an object
                obj_id = None
                for obj in objects:
                    if obj['name'] == module.get('object_name'):
                        # Would need to query DB for object_id, skip for now
                        pass
                
                self.db_saver.save_module(config_id, module, obj_id)
        else:
            # Legacy JSON saving
            for module in modules:
                self.save_module_to_kb_json(module, config_name)
        
        # Get statistics
        if self.use_postgres:
            stats = self.db_saver.get_statistics(config_name)
            print(f"[INFO] Статистика из БД:")
            print(f"  - Объектов: {stats.get('objects', 0)}")
            print(f"  - Модулей: {stats.get('modules', 0)}")
            print(f"  - Функций: {stats.get('functions', 0)}")
            print(f"  - Строк кода: {stats.get('total_lines', 0)}")
        else:
            print(f"[INFO] Обработано: {len(modules)} модулей, {len(objects)} объектов")
        
        return {
            'status': 'success',
            'modules': modules,
            'objects': objects,
            'stats': dict(self.stats),
            'config_id': config_id
        }
    
    def parse_common_modules(self, common_modules_path: Path, config_name: str) -> List[Dict[str, Any]]:
        """Парсинг общих модулей"""
        modules = []
        
        # Ищем все XML файлы общих модулей
        for xml_file in common_modules_path.glob("*.xml"):
            try:
                # Пропускаем служебные файлы
                if xml_file.name == "Configuration.xml" or "Subsystems" in str(xml_file):
                    continue
                
                # Парсим XML для получения имени
                with open(xml_file, 'rb') as f:
                    raw_bytes = f.read()
                    if raw_bytes.startswith(b'\xef\xbb\xbf'):
                        raw_bytes = raw_bytes[3:]
                    content = raw_bytes.decode('utf-8')
                    root = ET.fromstring(content)
                
                name = self._extract_name(root)
                if not name:
                    continue
                
                # Ищем BSL файл
                bsl_file = xml_file.parent / name / "Ext" / "Module.bsl"
                if not bsl_file.exists():
                    bsl_file = xml_file.parent / "Ext" / "Module.bsl"
                if not bsl_file.exists():
                    # Пробуем найти в текущей директории
                    bsl_file = xml_file.parent / xml_file.stem / "Ext" / "Module.bsl"
                
                if bsl_file.exists():
                    try:
                        with open(bsl_file, 'r', encoding='utf-8-sig') as f:
                            module_code = f.read()
                        
                        if module_code and len(module_code.strip()) > 10:
                            bsl_result = self.bsl_parser.parse(module_code)
                            
                            modules.append({
                                'name': f"ОбщийМодуль_{name}",
                                'object_type': 'ОбщийМодуль',
                                'object_name': name,
                                'module_type': 'Модуль',
                                'code': module_code,
                                'functions': bsl_result['functions'],
                                'procedures': bsl_result['procedures'],
                                'regions': bsl_result['regions'],
                                'api_usage': bsl_result['api_usage'],
                                'functions_count': len(bsl_result['functions']),
                                'source_file': str(xml_file.relative_to(self.config_dir)),
                                'description': f"Общий модуль {name}"
                            })
                            
                            self.stats['modules'] += 1
                            self.stats['functions'] += len(bsl_result['functions'])
                    except Exception as e:
                        print(f"[WARN] Ошибка чтения BSL {bsl_file.name}: {e}")
            except Exception as e:
                print(f"[WARN] Ошибка обработки {xml_file.name}: {e}")
        
        return modules
    
    def parse_documents(self, documents_path: Path, config_name: str) -> Dict[str, Any]:
        """Парсинг документов"""
        modules = []
        objects = []
        
        # Проходим по всем поддиректориям документов
        for doc_dir in documents_path.iterdir():
            if not doc_dir.is_dir():
                continue
            
            try:
                # Ищем XML файл документа
                xml_file = doc_dir / f"{doc_dir.name}.xml"
                if not xml_file.exists():
                    # Пробуем найти любой XML файл
                    xml_files = list(doc_dir.glob("*.xml"))
                    if xml_files:
                        xml_file = xml_files[0]
                    else:
                        continue
                
                # Парсим XML для получения имени
                with open(xml_file, 'rb') as f:
                    raw_bytes = f.read()
                    if raw_bytes.startswith(b'\xef\xbb\xbf'):
                        raw_bytes = raw_bytes[3:]
                    content = raw_bytes.decode('utf-8')
                    root = ET.fromstring(content)
                
                name = self._extract_name(root) or doc_dir.name
                
                # Ищем модули документа
                doc_modules = []
                
                # Модуль объекта
                obj_module_file = doc_dir / "Ext" / "ObjectModule.bsl"
                if obj_module_file.exists():
                    try:
                        with open(obj_module_file, 'r', encoding='utf-8-sig') as f:
                            module_code = f.read()
                        if module_code and len(module_code.strip()) > 10:
                            bsl_result = self.bsl_parser.parse(module_code)
                            doc_modules.append({
                                'name': f"Документ_{name}_МодульОбъекта",
                                'object_type': 'Документ',
                                'object_name': name,
                                'module_type': 'МодульОбъекта',
                                'code': module_code,
                                'functions': bsl_result['functions'],
                                'procedures': bsl_result['procedures'],
                                'regions': bsl_result['regions'],
                                'api_usage': bsl_result['api_usage'],
                                'functions_count': len(bsl_result['functions']),
                                'source_file': str(xml_file.relative_to(self.config_dir)),
                                'description': f"Модуль объекта документа {name}"
                            })
                            self.stats['modules'] += 1
                            self.stats['functions'] += len(bsl_result['functions'])
                    except Exception as e:
                        print(f"[WARN] Ошибка чтения ObjectModule.bsl: {e}")
                
                # Модуль менеджера
                manager_module_file = doc_dir / "Ext" / "ManagerModule.bsl"
                if manager_module_file.exists():
                    try:
                        with open(manager_module_file, 'r', encoding='utf-8-sig') as f:
                            module_code = f.read()
                        if module_code and len(module_code.strip()) > 10:
                            bsl_result = self.bsl_parser.parse(module_code)
                            doc_modules.append({
                                'name': f"Документ_{name}_МодульМенеджера",
                                'object_type': 'Документ',
                                'object_name': name,
                                'module_type': 'МодульМенеджера',
                                'code': module_code,
                                'functions': bsl_result['functions'],
                                'procedures': bsl_result['procedures'],
                                'regions': bsl_result['regions'],
                                'api_usage': bsl_result['api_usage'],
                                'functions_count': len(bsl_result['functions']),
                                'source_file': str(xml_file.relative_to(self.config_dir)),
                                'description': f"Модуль менеджера документа {name}"
                            })
                            self.stats['modules'] += 1
                            self.stats['functions'] += len(bsl_result['functions'])
                    except Exception as e:
                        print(f"[WARN] Ошибка чтения ManagerModule.bsl: {e}")
                
                # Модули форм
                forms_dir = doc_dir / "Forms"
                if forms_dir.exists():
                    for form_dir in forms_dir.iterdir():
                        if not form_dir.is_dir():
                            continue
                        
                        form_module_file = form_dir / "Ext" / "Form" / "Module.bsl"
                        if form_module_file.exists():
                            try:
                                with open(form_module_file, 'r', encoding='utf-8-sig') as f:
                                    form_code = f.read()
                                if form_code and len(form_code.strip()) > 10:
                                    bsl_result = self.bsl_parser.parse(form_code)
                                    doc_modules.append({
                                        'name': f"Документ_{name}_Форма_{form_dir.name}",
                                        'object_type': 'Документ',
                                        'object_name': name,
                                        'module_type': 'МодульФормы',
                                        'code': form_code,
                                        'functions': bsl_result['functions'],
                                        'procedures': bsl_result['procedures'],
                                        'regions': bsl_result['regions'],
                                        'api_usage': bsl_result['api_usage'],
                                        'functions_count': len(bsl_result['functions']),
                                        'source_file': str(xml_file.relative_to(self.config_dir)),
                                        'description': f"Модуль формы {form_dir.name} документа {name}"
                                    })
                                    self.stats['modules'] += 1
                                    self.stats['functions'] += len(bsl_result['functions'])
                            except Exception as e:
                                print(f"[WARN] Ошибка чтения формы {form_dir.name}: {e}")
                
                if doc_modules:
                    modules.extend(doc_modules)
                    objects.append({
                        'type': 'Документ',
                        'name': name,
                        'modules_count': len(doc_modules)
                    })
            except Exception as e:
                print(f"[WARN] Ошибка обработки документа {doc_dir.name}: {e}")
        
        return {'modules': modules, 'objects': objects}
    
    def parse_catalogs(self, catalogs_path: Path, config_name: str) -> Dict[str, Any]:
        """Парсинг справочников"""
        modules = []
        objects = []
        
        # Аналогично документам, но для справочников
        for cat_dir in catalogs_path.iterdir():
            if not cat_dir.is_dir():
                continue
            
            try:
                xml_file = cat_dir / f"{cat_dir.name}.xml"
                if not xml_file.exists():
                    xml_files = list(cat_dir.glob("*.xml"))
                    if xml_files:
                        xml_file = xml_files[0]
                    else:
                        continue
                
                with open(xml_file, 'rb') as f:
                    raw_bytes = f.read()
                    if raw_bytes.startswith(b'\xef\xbb\xbf'):
                        raw_bytes = raw_bytes[3:]
                    content = raw_bytes.decode('utf-8')
                    root = ET.fromstring(content)
                
                name = self._extract_name(root) or cat_dir.name
                
                cat_modules = []
                
                # Модуль объекта
                obj_module_file = cat_dir / "Ext" / "ObjectModule.bsl"
                if obj_module_file.exists():
                    try:
                        with open(obj_module_file, 'r', encoding='utf-8-sig') as f:
                            module_code = f.read()
                        if module_code and len(module_code.strip()) > 10:
                            bsl_result = self.bsl_parser.parse(module_code)
                            cat_modules.append({
                                'name': f"Справочник_{name}_МодульОбъекта",
                                'object_type': 'Справочник',
                                'object_name': name,
                                'module_type': 'МодульОбъекта',
                                'code': module_code,
                                'functions': bsl_result['functions'],
                                'procedures': bsl_result['procedures'],
                                'regions': bsl_result['regions'],
                                'api_usage': bsl_result['api_usage'],
                                'functions_count': len(bsl_result['functions']),
                                'source_file': str(xml_file.relative_to(self.config_dir)),
                                'description': f"Модуль объекта справочника {name}"
                            })
                            self.stats['modules'] += 1
                            self.stats['functions'] += len(bsl_result['functions'])
                    except Exception as e:
                        print(f"[WARN] Ошибка чтения ObjectModule.bsl: {e}")
                
                if cat_modules:
                    modules.extend(cat_modules)
                    objects.append({
                        'type': 'Справочник',
                        'name': name,
                        'modules_count': len(cat_modules)
                    })
            except Exception as e:
                print(f"[WARN] Ошибка обработки справочника {cat_dir.name}: {e}")
        
        return {'modules': modules, 'objects': objects}
    
    def parse_single_xml_file(self, xml_file: Path, config_name: str) -> Optional[Dict[str, Any]]:
        """Парсинг одного XML файла"""
        try:
            # Пропускаем файлы форм (они обрабатываются в составе объектов)
            if 'Forms' in str(xml_file) and xml_file.name != 'Form.xml':
                return None
            
            # Читаем файл с правильной обработкой BOM
            with open(xml_file, 'rb') as f:
                raw_bytes = f.read()
                if raw_bytes.startswith(b'\xef\xbb\xbf'):
                    raw_bytes = raw_bytes[3:]
                content = raw_bytes.decode('utf-8')
            
            # Парсим XML
            root = ET.fromstring(content)
            
            # Определяем тип файла по корневому тегу
            root_tag = root.tag
            
            # Убираем namespace из тега
            if '}' in root_tag:
                root_tag = root_tag.split('}')[1]
            
            # Определяем тип объекта и извлекаем данные
            result = {
                'modules': [],
                'objects': []
            }
            
            # Общие модули
            if 'CommonModule' in root_tag or 'ОбщийМодуль' in root_tag:
                module_data = self.parse_common_module(root, xml_file, config_name)
                if module_data:
                    result['modules'].append(module_data)
                    result['objects'].append({
                        'type': 'ОбщийМодуль',
                        'name': module_data.get('object_name', 'Unknown'),
                        'modules_count': 1
                    })
            
            # Документы
            elif 'Document' in root_tag or 'Документ' in root_tag:
                doc_data = self.parse_document(root, xml_file, config_name)
                if doc_data:
                    result['modules'].extend(doc_data.get('modules', []))
                    result['objects'].append({
                        'type': 'Документ',
                        'name': doc_data.get('object_name', 'Unknown'),
                        'modules_count': len(doc_data.get('modules', []))
                    })
            
            # Справочники
            elif 'Catalog' in root_tag or 'Справочник' in root_tag:
                cat_data = self.parse_catalog(root, xml_file, config_name)
                if cat_data:
                    result['modules'].extend(cat_data.get('modules', []))
                    result['objects'].append({
                        'type': 'Справочник',
                        'name': cat_data.get('object_name', 'Unknown'),
                        'modules_count': len(cat_data.get('modules', []))
                    })
            
            # Регистры
            elif 'Register' in root_tag or 'Регистр' in root_tag:
                reg_data = self.parse_register(root, xml_file, config_name)
                if reg_data:
                    result['modules'].extend(reg_data.get('modules', []))
                    result['objects'].append({
                        'type': 'Регистр',
                        'name': reg_data.get('object_name', 'Unknown'),
                        'modules_count': len(reg_data.get('modules', []))
                    })
            
            # Отчеты
            elif 'Report' in root_tag or 'Отчет' in root_tag:
                rep_data = self.parse_report(root, xml_file, config_name)
                if rep_data:
                    result['modules'].extend(rep_data.get('modules', []))
                    result['objects'].append({
                        'type': 'Отчет',
                        'name': rep_data.get('object_name', 'Unknown'),
                        'modules_count': len(rep_data.get('modules', []))
                    })
            
            # Обработки
            elif 'DataProcessor' in root_tag or 'Обработка' in root_tag:
                proc_data = self.parse_dataprocessor(root, xml_file, config_name)
                if proc_data:
                    result['modules'].extend(proc_data.get('modules', []))
                    result['objects'].append({
                        'type': 'Обработка',
                        'name': proc_data.get('object_name', 'Unknown'),
                        'modules_count': len(proc_data.get('modules', []))
                    })
            
            return result
            
        except ET.ParseError as e:
            print(f"[WARN] Ошибка парсинга XML {xml_file.name}: {e}")
            return None
        except Exception as e:
            print(f"[WARN] Ошибка обработки {xml_file.name}: {e}")
            return None
    
    def parse_common_module(self, root: ET.Element, xml_file: Path, config_name: str) -> Optional[Dict[str, Any]]:
        """Парсинг общего модуля"""
        # Извлекаем имя модуля
        name = self._extract_name(root)
        if not name:
            return None
        
        # Ищем модуль с кодом в XML
        module_code = self._extract_module_code(root)
        
        # Если не нашли в XML, пробуем найти отдельный BSL файл
        if not module_code:
            # В EDT модули часто хранятся в отдельном файле Ext/Module.bsl
            bsl_file = xml_file.parent / "Ext" / "Module.bsl"
            if not bsl_file.exists():
                # Пробуем другие возможные пути
                bsl_file = xml_file.parent / "Module.bsl"
            
            if bsl_file.exists():
                try:
                    with open(bsl_file, 'r', encoding='utf-8-sig') as f:
                        module_code = f.read()
                except Exception as e:
                    print(f"[WARN] Ошибка чтения BSL файла {bsl_file.name}: {e}")
        
        if not module_code or len(module_code.strip()) < 10:
            return None
        
        # Парсим BSL код
        bsl_result = self.bsl_parser.parse(module_code)
        
        module_data = {
            'name': f"ОбщийМодуль_{name}",
            'object_type': 'ОбщийМодуль',
            'object_name': name,
            'module_type': 'Модуль',
            'code': module_code,
            'functions': bsl_result['functions'],
            'procedures': bsl_result['procedures'],
            'regions': bsl_result['regions'],
            'api_usage': bsl_result['api_usage'],
            'functions_count': len(bsl_result['functions']),
            'source_file': str(xml_file.relative_to(self.config_dir)),
            'description': f"Общий модуль {name}"
        }
        
        self.stats['modules'] += 1
        self.stats['functions'] += len(bsl_result['functions'])
        
        return module_data
    
    def parse_document(self, root: ET.Element, xml_file: Path, config_name: str) -> Dict[str, Any]:
        """Парсинг документа"""
        name = self._extract_name(root)
        if not name:
            return {'modules': [], 'object_name': 'Unknown'}
        
        modules = []
        
        # Модуль объекта - пробуем найти в XML и в отдельном BSL файле
        object_module = self._find_module(root, ['ObjectModule', 'МодульОбъекта', 'Object', 'Модуль'])
        module_code = None
        
        if object_module:
            module_code = self._extract_module_code_from_elem(object_module)
        
        # Если не нашли в XML, пробуем BSL файл
        if not module_code:
            bsl_file = xml_file.parent / "Ext" / "ObjectModule.bsl"
            if bsl_file.exists():
                try:
                    with open(bsl_file, 'r', encoding='utf-8-sig') as f:
                        module_code = f.read()
                except Exception as e:
                    print(f"[WARN] Ошибка чтения BSL файла {bsl_file.name}: {e}")
        
        if module_code:
                bsl_result = self.bsl_parser.parse(module_code)
                modules.append({
                    'name': f"Документ_{name}_МодульОбъекта",
                    'object_type': 'Документ',
                    'object_name': name,
                    'module_type': 'МодульОбъекта',
                    'code': module_code,
                    'functions': bsl_result['functions'],
                    'procedures': bsl_result['procedures'],
                    'regions': bsl_result['regions'],
                    'api_usage': bsl_result['api_usage'],
                    'functions_count': len(bsl_result['functions']),
                    'source_file': str(xml_file.relative_to(self.config_dir)),
                    'description': f"Модуль объекта документа {name}"
                })
                self.stats['modules'] += 1
                self.stats['functions'] += len(bsl_result['functions'])
        
        # Модуль менеджера
        manager_module = self._find_module(root, ['ManagerModule', 'МодульМенеджера', 'Manager'])
        manager_code = None
        
        if manager_module:
            manager_code = self._extract_module_code_from_elem(manager_module)
        
        # Если не нашли в XML, пробуем BSL файл
        if not manager_code:
            bsl_file = xml_file.parent / "Ext" / "ManagerModule.bsl"
            if bsl_file.exists():
                try:
                    with open(bsl_file, 'r', encoding='utf-8-sig') as f:
                        manager_code = f.read()
                except Exception as e:
                    print(f"[WARN] Ошибка чтения BSL файла {bsl_file.name}: {e}")
        
        if manager_code:
                bsl_result = self.bsl_parser.parse(manager_code)
                modules.append({
                    'name': f"Документ_{name}_МодульМенеджера",
                    'object_type': 'Документ',
                    'object_name': name,
                    'module_type': 'МодульМенеджера',
                    'code': manager_code,
                    'functions': bsl_result['functions'],
                    'procedures': bsl_result['procedures'],
                    'regions': bsl_result['regions'],
                    'api_usage': bsl_result['api_usage'],
                    'functions_count': len(bsl_result['functions']),
                    'source_file': str(xml_file.relative_to(self.config_dir)),
                    'description': f"Модуль менеджера документа {name}"
                })
                self.stats['modules'] += 1
                self.stats['functions'] += len(bsl_result['functions'])
        
        # Модули форм
        forms = self._find_all(root, ['Form', 'Форма'])
        for form in forms:
            form_name = self._extract_name(form) or 'Форма'
            form_module = self._find_module(form, ['FormModule', 'МодульФормы', 'Module'])
            form_code = None
            
            if form_module:
                form_code = self._extract_module_code_from_elem(form_module)
            
            # Если не нашли в XML, пробуем BSL файл формы
            if not form_code:
                # Форма может быть в подкаталоге Forms/ИмяФормы/Ext/Form/Module.bsl
                form_dir = xml_file.parent / "Forms" / form_name / "Ext" / "Form"
                bsl_file = form_dir / "Module.bsl"
                if not bsl_file.exists():
                    bsl_file = form_dir / "Form.bsl"
                if not bsl_file.exists():
                    bsl_file = xml_file.parent / "Forms" / form_name / "Module.bsl"
                
                if bsl_file.exists():
                    try:
                        with open(bsl_file, 'r', encoding='utf-8-sig') as f:
                            form_code = f.read()
                    except Exception as e:
                        print(f"[WARN] Ошибка чтения BSL файла формы {bsl_file.name}: {e}")
            
            if form_code:
                    bsl_result = self.bsl_parser.parse(form_code)
                    modules.append({
                        'name': f"Документ_{name}_Форма_{form_name}",
                        'object_type': 'Документ',
                        'object_name': name,
                        'module_type': 'МодульФормы',
                        'code': form_code,
                        'functions': bsl_result['functions'],
                        'procedures': bsl_result['procedures'],
                        'regions': bsl_result['regions'],
                        'api_usage': bsl_result['api_usage'],
                        'functions_count': len(bsl_result['functions']),
                        'source_file': str(xml_file.relative_to(self.config_dir)),
                        'description': f"Модуль формы {form_name} документа {name}"
                    })
                    self.stats['modules'] += 1
                    self.stats['functions'] += len(bsl_result['functions'])
        
        return {'modules': modules, 'object_name': name}
    
    def parse_catalog(self, root: ET.Element, xml_file: Path, config_name: str) -> Dict[str, Any]:
        """Парсинг справочника"""
        name = self._extract_name(root)
        if not name:
            return {'modules': [], 'object_name': 'Unknown'}
        
        modules = []
        
        # Модуль объекта
        object_module = self._find_module(root, ['ObjectModule', 'МодульОбъекта', 'Object', 'Модуль'])
        if object_module:
            module_code = self._extract_module_code_from_elem(object_module)
            if module_code:
                bsl_result = self.bsl_parser.parse(module_code)
                modules.append({
                    'name': f"Справочник_{name}_МодульОбъекта",
                    'object_type': 'Справочник',
                    'object_name': name,
                    'module_type': 'МодульОбъекта',
                    'code': module_code,
                    'functions': bsl_result['functions'],
                    'procedures': bsl_result['procedures'],
                    'regions': bsl_result['regions'],
                    'api_usage': bsl_result['api_usage'],
                    'functions_count': len(bsl_result['functions']),
                    'source_file': str(xml_file.relative_to(self.config_dir)),
                    'description': f"Модуль объекта справочника {name}"
                })
                self.stats['modules'] += 1
                self.stats['functions'] += len(bsl_result['functions'])
        
        # Модули форм
        forms = self._find_all(root, ['Form', 'Форма'])
        for form in forms:
            form_name = self._extract_name(form) or 'Форма'
            form_module = self._find_module(form, ['FormModule', 'МодульФормы', 'Module'])
            if form_module:
                module_code = self._extract_module_code_from_elem(form_module)
                if module_code:
                    bsl_result = self.bsl_parser.parse(module_code)
                    modules.append({
                        'name': f"Справочник_{name}_Форма_{form_name}",
                        'object_type': 'Справочник',
                        'object_name': name,
                        'module_type': 'МодульФормы',
                        'code': module_code,
                        'functions': bsl_result['functions'],
                        'procedures': bsl_result['procedures'],
                        'regions': bsl_result['regions'],
                        'api_usage': bsl_result['api_usage'],
                        'functions_count': len(bsl_result['functions']),
                        'source_file': str(xml_file.relative_to(self.config_dir)),
                        'description': f"Модуль формы {form_name} справочника {name}"
                    })
                    self.stats['modules'] += 1
                    self.stats['functions'] += len(bsl_result['functions'])
        
        return {'modules': modules, 'object_name': name}
    
    def parse_register(self, root: ET.Element, xml_file: Path, config_name: str) -> Dict[str, Any]:
        """Парсинг регистра"""
        name = self._extract_name(root)
        if not name:
            return {'modules': [], 'object_name': 'Unknown'}
        
        modules = []
        
        # Модуль объекта
        object_module = self._find_module(root, ['ObjectModule', 'МодульОбъекта', 'Object', 'Модуль'])
        if object_module:
            module_code = self._extract_module_code_from_elem(object_module)
            if module_code:
                bsl_result = self.bsl_parser.parse(module_code)
                modules.append({
                    'name': f"Регистр_{name}_МодульОбъекта",
                    'object_type': 'Регистр',
                    'object_name': name,
                    'module_type': 'МодульОбъекта',
                    'code': module_code,
                    'functions': bsl_result['functions'],
                    'procedures': bsl_result['procedures'],
                    'regions': bsl_result['regions'],
                    'api_usage': bsl_result['api_usage'],
                    'functions_count': len(bsl_result['functions']),
                    'source_file': str(xml_file.relative_to(self.config_dir)),
                    'description': f"Модуль объекта регистра {name}"
                })
                self.stats['modules'] += 1
                self.stats['functions'] += len(bsl_result['functions'])
        
        return {'modules': modules, 'object_name': name}
    
    def parse_report(self, root: ET.Element, xml_file: Path, config_name: str) -> Dict[str, Any]:
        """Парсинг отчета"""
        name = self._extract_name(root)
        if not name:
            return {'modules': [], 'object_name': 'Unknown'}
        
        modules = []
        
        # Модуль объекта
        object_module = self._find_module(root, ['ObjectModule', 'МодульОбъекта', 'Object', 'Модуль'])
        if object_module:
            module_code = self._extract_module_code_from_elem(object_module)
            if module_code:
                bsl_result = self.bsl_parser.parse(module_code)
                modules.append({
                    'name': f"Отчет_{name}_МодульОбъекта",
                    'object_type': 'Отчет',
                    'object_name': name,
                    'module_type': 'МодульОбъекта',
                    'code': module_code,
                    'functions': bsl_result['functions'],
                    'procedures': bsl_result['procedures'],
                    'regions': bsl_result['regions'],
                    'api_usage': bsl_result['api_usage'],
                    'functions_count': len(bsl_result['functions']),
                    'source_file': str(xml_file.relative_to(self.config_dir)),
                    'description': f"Модуль объекта отчета {name}"
                })
                self.stats['modules'] += 1
                self.stats['functions'] += len(bsl_result['functions'])
        
        return {'modules': modules, 'object_name': name}
    
    def parse_dataprocessor(self, root: ET.Element, xml_file: Path, config_name: str) -> Dict[str, Any]:
        """Парсинг обработки"""
        name = self._extract_name(root)
        if not name:
            return {'modules': [], 'object_name': 'Unknown'}
        
        modules = []
        
        # Модуль объекта
        object_module = self._find_module(root, ['ObjectModule', 'МодульОбъекта', 'Object', 'Модуль'])
        if object_module:
            module_code = self._extract_module_code_from_elem(object_module)
            if module_code:
                bsl_result = self.bsl_parser.parse(module_code)
                modules.append({
                    'name': f"Обработка_{name}_МодульОбъекта",
                    'object_type': 'Обработка',
                    'object_name': name,
                    'module_type': 'МодульОбъекта',
                    'code': module_code,
                    'functions': bsl_result['functions'],
                    'procedures': bsl_result['procedures'],
                    'regions': bsl_result['regions'],
                    'api_usage': bsl_result['api_usage'],
                    'functions_count': len(bsl_result['functions']),
                    'source_file': str(xml_file.relative_to(self.config_dir)),
                    'description': f"Модуль объекта обработки {name}"
                })
                self.stats['modules'] += 1
                self.stats['functions'] += len(bsl_result['functions'])
        
        # Модули форм
        forms = self._find_all(root, ['Form', 'Форма'])
        for form in forms:
            form_name = self._extract_name(form) or 'Форма'
            form_module = self._find_module(form, ['FormModule', 'МодульФормы', 'Module'])
            if form_module:
                module_code = self._extract_module_code_from_elem(form_module)
                if module_code:
                    bsl_result = self.bsl_parser.parse(module_code)
                    modules.append({
                        'name': f"Обработка_{name}_Форма_{form_name}",
                        'object_type': 'Обработка',
                        'object_name': name,
                        'module_type': 'МодульФормы',
                        'code': module_code,
                        'functions': bsl_result['functions'],
                        'procedures': bsl_result['procedures'],
                        'regions': bsl_result['regions'],
                        'api_usage': bsl_result['api_usage'],
                        'functions_count': len(bsl_result['functions']),
                        'source_file': str(xml_file.relative_to(self.config_dir)),
                        'description': f"Модуль формы {form_name} обработки {name}"
                    })
                    self.stats['modules'] += 1
                    self.stats['functions'] += len(bsl_result['functions'])
        
        return {'modules': modules, 'object_name': name}
    
    def _extract_name(self, elem: ET.Element) -> str:
        """Извлечение имени объекта из элемента"""
        # Пробуем разные варианты
        name_attrs = ['Имя', 'name', 'Name', 'uuid', 'Uuid']
        
        for attr in name_attrs:
            if attr in elem.attrib:
                value = elem.attrib[attr]
                if value:
                    return value
        
        # Ищем в дочерних элементах Properties/Name
        props = self._find(elem, ['Properties', 'Свойства'])
        if props is not None:
            name_elem = self._find(props, ['Name', 'Имя'])
            if name_elem is not None and name_elem.text:
                return name_elem.text.strip()
        
        # Ищем Name напрямую
        name_elem = self._find(elem, ['Name', 'Имя'])
        if name_elem is not None and name_elem.text:
            return name_elem.text.strip()
        
        return ''
    
    def _extract_module_code(self, elem: ET.Element) -> str:
        """Извлечение кода модуля из элемента"""
        # Ищем модуль
        module_elem = self._find_module(elem, ['Module', 'Модуль', 'ObjectModule', 'МодульОбъекта'])
        if module_elem:
            return self._extract_module_code_from_elem(module_elem)
        return ''
    
    def _extract_module_code_from_elem(self, module_elem: ET.Element) -> str:
        """Извлечение кода из элемента модуля"""
        # Код может быть в тексте элемента
        if module_elem.text:
            code = module_elem.text.strip()
            if code and len(code) > 10:
                return code
        
        # Ищем в дочерних элементах
        for child in module_elem:
            if child.text:
                code = child.text.strip()
                if code and len(code) > 10:
                    return code
        
        # Ищем элемент Code или Код
        code_elem = self._find(module_elem, ['Code', 'Код', 'Content', 'Содержимое'])
        if code_elem is not None and code_elem.text:
            return code_elem.text.strip()
        
        return ''
    
    def _find(self, parent: ET.Element, tag_names: List[str]) -> Optional[ET.Element]:
        """Поиск элемента по списку возможных тегов"""
        for tag in tag_names:
            # С namespace и без
            for elem in parent.iter():
                tag_clean = elem.tag.split('}')[1] if '}' in elem.tag else elem.tag
                if tag_clean == tag:
                    return elem
            
            # Прямой поиск
            found = parent.find(f'.//{tag}')
            if found is not None:
                return found
        
        return None
    
    def _find_all(self, parent: ET.Element, tag_names: List[str]) -> List[ET.Element]:
        """Поиск всех элементов по списку возможных тегов"""
        results = []
        for tag in tag_names:
            found = parent.findall(f'.//{tag}')
            if found:
                results.extend(found)
        
        return results
    
    def _find_module(self, parent: ET.Element, tag_names: List[str]) -> Optional[ET.Element]:
        """Поиск модуля по списку возможных тегов"""
        return self._find(parent, tag_names)
    
    def save_module_to_kb_json(self, module: Dict[str, Any], config_name: str):
        """Сохранение модуля в JSON базу знаний (legacy)"""
        try:
            # This is the old method for JSON storage
            # Keep for backwards compatibility
            kb_file = Path(f"./knowledge_base/{config_name.lower()}.json")
            
            # Load existing or create new
            if kb_file.exists():
                with open(kb_file, 'r', encoding='utf-8') as f:
                    kb_data = json.load(f)
            else:
                kb_data = {'modules': []}
            
            # Add module
            kb_data['modules'].append({
                'name': module['name'],
                'object_type': module.get('object_type'),
                'object_name': module.get('object_name'),
                'module_type': module.get('module_type'),
                'description': module.get('description', ''),
                'functions': module.get('functions', []),
                'procedures': module.get('procedures', []),
                'regions': module.get('regions', []),
                'api_usage': module.get('api_usage', [])
            })
            
            # Save
            kb_file.parent.mkdir(parents=True, exist_ok=True)
            with open(kb_file, 'w', encoding='utf-8') as f:
                json.dump(kb_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"[WARN] Ошибка сохранения модуля {module.get('name', 'Unknown')}: {e}")
    
    def __del__(self):
        """Cleanup on deletion"""
        if hasattr(self, 'db_saver') and self.db_saver:
            try:
                self.db_saver.disconnect()
            except:
                pass


def parse_do_configuration():
    """Парсинг конфигурации DO из EDT XML файлов"""
    import sys

    # Устанавливаем правильную кодировку для вывода
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    
    print("=" * 70)
    print("ПАРСИНГ КОНФИГУРАЦИИ DO ИЗ EDT XML ФАЙЛОВ")
    print("=" * 70)
    
    parser = EDTXMLParser()
    config_path = Path("./1c_configurations/DO")
    
    if not config_path.exists():
        print(f"[ERROR] Директория не найдена: {config_path}")
        return
    
    result = parser.parse_edt_configuration("DO", config_path)
    
    print(f"\n{'='*70}")
    print("РЕЗУЛЬТАТЫ:")
    print(f"{'='*70}")
    print(f"Модулей найдено: {len(result.get('modules', []))}")
    print(f"Объектов найдено: {len(result.get('objects', []))}")
    print(f"Функций найдено: {parser.stats['functions']}")
    
    if result.get('modules'):
        print(f"\nПервые 10 модулей:")
        for module in result['modules'][:10]:
            name = module.get('name', 'Unknown')
            func_count = module.get('functions_count', 0)
            obj_name = module.get('object_name', 'Unknown')
            print(f"  - {name} ({obj_name}): {func_count} функций")
    
    print(f"\n{'='*70}")
    print("ПАРСИНГ ЗАВЕРШЕН")
    print(f"{'='*70}")


def parse_erp_configuration():
    """Парсинг конфигурации ERP из EDT XML файлов"""
    import sys

    # Устанавливаем правильную кодировку для вывода
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    
    print("=" * 70)
    print("ПАРСИНГ КОНФИГУРАЦИИ ERP ИЗ EDT XML ФАЙЛОВ")
    print("=" * 70)
    
    parser = EDTXMLParser()
    config_path = Path("./1c_configurations/ERP")
    
    if not config_path.exists():
        print(f"[ERROR] Директория не найдена: {config_path}")
        return
    
    result = parser.parse_edt_configuration("ERP", config_path)
    
    print(f"\n{'='*70}")
    print("РЕЗУЛЬТАТЫ:")
    print(f"{'='*70}")
    print(f"Модулей найдено: {len(result.get('modules', []))}")
    print(f"Объектов найдено: {len(result.get('objects', []))}")
    print(f"Функций найдено: {parser.stats['functions']}")
    
    if result.get('modules'):
        print(f"\nПервые 10 модулей:")
        for module in result['modules'][:10]:
            name = module.get('name', 'Unknown')
            func_count = module.get('functions_count', 0)
            obj_name = module.get('object_name', 'Unknown')
            print(f"  - {name} ({obj_name}): {func_count} функций")
    
    print(f"\n{'='*70}")
    print("ПАРСИНГ ЗАВЕРШЕН")
    print(f"{'='*70}")


def parse_zup_configuration():
    """Парсинг конфигурации ZUP из EDT XML файлов"""
    import sys

    # Устанавливаем правильную кодировку для вывода
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    
    print("=" * 70)
    print("ПАРСИНГ КОНФИГУРАЦИИ ZUP ИЗ EDT XML ФАЙЛОВ")
    print("=" * 70)
    
    parser = EDTXMLParser()
    config_path = Path("./1c_configurations/ZUP")
    
    if not config_path.exists():
        print(f"[ERROR] Директория не найдена: {config_path}")
        return
    
    result = parser.parse_edt_configuration("ZUP", config_path)
    
    print(f"\n{'='*70}")
    print("РЕЗУЛЬТАТЫ:")
    print(f"{'='*70}")
    print(f"Модулей найдено: {len(result.get('modules', []))}")
    print(f"Объектов найдено: {len(result.get('objects', []))}")
    print(f"Функций найдено: {parser.stats['functions']}")
    
    if result.get('modules'):
        print(f"\nПервые 10 модулей:")
        for module in result['modules'][:10]:
            name = module.get('name', 'Unknown')
            func_count = module.get('functions_count', 0)
            obj_name = module.get('object_name', 'Unknown')
            print(f"  - {name} ({obj_name}): {func_count} функций")
    
    print(f"\n{'='*70}")
    print("ПАРСИНГ ЗАВЕРШЕН")
    print(f"{'='*70}")


def parse_buh_configuration():
    """Парсинг конфигурации BUH из EDT XML файлов"""
    import sys

    # Устанавливаем правильную кодировку для вывода
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    
    print("=" * 70)
    print("ПАРСИНГ КОНФИГУРАЦИИ BUH ИЗ EDT XML ФАЙЛОВ")
    print("=" * 70)
    
    parser = EDTXMLParser()
    config_path = Path("./1c_configurations/BUH")
    
    if not config_path.exists():
        print(f"[ERROR] Директория не найдена: {config_path}")
        return
    
    result = parser.parse_edt_configuration("BUH", config_path)
    
    print(f"\n{'='*70}")
    print("РЕЗУЛЬТАТЫ:")
    print(f"{'='*70}")
    print(f"Модулей найдено: {len(result.get('modules', []))}")
    print(f"Объектов найдено: {len(result.get('objects', []))}")
    print(f"Функций найдено: {parser.stats['functions']}")
    
    if result.get('modules'):
        print(f"\nПервые 10 модулей:")
        for module in result['modules'][:10]:
            name = module.get('name', 'Unknown')
            func_count = module.get('functions_count', 0)
            obj_name = module.get('object_name', 'Unknown')
            print(f"  - {name} ({obj_name}): {func_count} функций")
    
    print(f"\n{'='*70}")
    print("ПАРСИНГ ЗАВЕРШЕН")
    print(f"{'='*70}")


if __name__ == "__main__":
    import sys
    config_arg = sys.argv[1].upper() if len(sys.argv) > 1 else "DO"
    
    if config_arg == "ERP":
        parse_erp_configuration()
    elif config_arg == "ZUP":
        parse_zup_configuration()
    elif config_arg == "BUH":
        parse_buh_configuration()
    else:
        parse_do_configuration()

