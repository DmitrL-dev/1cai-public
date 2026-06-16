
#!/usr/bin/env python3
"""
EDT Configuration Parser with Enhanced Metadata Extraction
Парсер для EDT выгрузки с расширенным извлечением метаданных

Версия: 2.0.0
Дата: 2025-11-06

Улучшения:
- Полное извлечение метаданных из XML
- Реквизиты с типами
- Табличные части с колонками
- Свойства объектов
- Enriched dataset
"""

import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Optional

# Импорт базового парсера
sys.path.insert(0, str(Path(__file__).parent))
from edt_parser import EDTConfigurationParser


class EDTParserWithMetadata(EDTConfigurationParser):
    """
    Расширенный EDT парсер с полным извлечением метаданных
    """
    
    def __init__(self, edt_root_path: Path):
        super().__init__(edt_root_path)
        
    def parse_single_catalog(self, catalog_dir: Path) -> Optional[Dict[str, Any]]:
        """
        Расширенный парсинг справочника с полными метаданными
        """
        catalog_name = catalog_dir.name
        
        # Базовые данные
        catalog_data = super().parse_single_catalog(catalog_dir)
        if not catalog_data:
            return None
        
        # Расширенное извлечение метаданных
        xml_file = catalog_dir / f"{catalog_name}.xml"
        if xml_file.exists():
            enhanced_metadata = self._parse_catalog_metadata_enhanced(xml_file)
            if enhanced_metadata:
                catalog_data['metadata'] = enhanced_metadata
        
        return catalog_data
    
    def _parse_catalog_metadata_enhanced(self, xml_file: Path) -> Optional[Dict[str, Any]]:
        """
        Полное извлечение метаданных справочника
        """
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Определяем namespace
            namespace = self._get_namespace(root)
            
            metadata = {
                'name': self._get_text(root, 'Name', namespace),
                'synonym': self._get_text(root, 'Synonym', namespace),
                'comment': self._get_text(root, 'Comment', namespace),
                'hierarchical': self._get_text(root, 'Hierarchical', namespace) == 'true',
                'hierarchy_type': self._get_text(root, 'HierarchyType', namespace),
                'code_length': self._get_text(root, 'CodeLength', namespace),
                'description_length': self._get_text(root, 'DescriptionLength', namespace),
                'attributes': [],
                'tabular_sections': [],
                'standard_attributes': []
            }
            
            # Извлекаем реквизиты
            for attr in root.findall('.//{*}Attribute'):
                attr_data = {
                    'name': attr.findtext('{*}Name', default=''),
                    'synonym': attr.findtext('{*}Synonym', default=''),
                    'comment': attr.findtext('{*}Comment', default=''),
                    'type': self._extract_type_info(attr),
                    'mandatory': attr.findtext('{*}FillChecking', default='') == 'ShowError',
                    'use': attr.findtext('{*}Use', default='') != 'DontUse'
                }
                if attr_data['name']:
                    metadata['attributes'].append(attr_data)
            
            # Извлекаем табличные части
            for tab_section in root.findall('.//{*}TabularSection'):
                section_name = tab_section.findtext('{*}Name', default='')
                if section_name:
                    section_data = {
                        'name': section_name,
                        'synonym': tab_section.findtext('{*}Synonym', default=''),
                        'columns': []
                    }
                    
                    # Извлекаем колонки табличной части
                    for attr in tab_section.findall('.//{*}Attribute'):
                        col_data = {
                            'name': attr.findtext('{*}Name', default=''),
                            'synonym': attr.findtext('{*}Synonym', default=''),
                            'type': self._extract_type_info(attr),
                            'mandatory': attr.findtext('{*}FillChecking', default='') == 'ShowError'
                        }
                        if col_data['name']:
                            section_data['columns'].append(col_data)
                    
                    metadata['tabular_sections'].append(section_data)
            
            # Стандартные реквизиты
            for std_attr in root.findall('.//{*}StandardAttribute'):
                std_name = std_attr.findtext('{*}Name', default='')
                if std_name:
                    metadata['standard_attributes'].append({
                        'name': std_name,
                        'synonym': std_attr.findtext('{*}Synonym', default=''),
                        'use': std_attr.findtext('{*}Use', default='') != 'DontUse'
                    })
            
            return metadata
            
        except Exception as e:
            self.errors.append(f"Ошибка парсинга метаданных справочника {xml_file}: {str(e)}")
            return None
    
    def parse_single_document(self, doc_dir: Path) -> Optional[Dict[str, Any]]:
        """
        Расширенный парсинг документа с полными метаданными
        """
        doc_name = doc_dir.name
        
        # Базовые данные
        doc_data = super().parse_single_document(doc_dir)
        if not doc_data:
            return None
        
        # Расширенное извлечение метаданных
        xml_file = doc_dir / f"{doc_name}.xml"
        if xml_file.exists():
            enhanced_metadata = self._parse_document_metadata_enhanced(xml_file)
            if enhanced_metadata:
                doc_data['metadata'] = enhanced_metadata
        
        return doc_data
    
    def _parse_document_metadata_enhanced(self, xml_file: Path) -> Optional[Dict[str, Any]]:
        """
        Полное извлечение метаданных документа
        """
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            namespace = self._get_namespace(root)
            
            metadata = {
                'name': self._get_text(root, 'Name', namespace),
                'synonym': self._get_text(root, 'Synonym', namespace),
                'comment': self._get_text(root, 'Comment', namespace),
                'use_standard_commands': self._get_text(root, 'UseStandardCommands', namespace) == 'true',
                'posting': self._get_text(root, 'Posting', namespace),
                'realtime_posting': self._get_text(root, 'RealTimePosting', namespace),
                'register_records_on_posting': self._get_text(root, 'RegisterRecordsOnPosting', namespace),
                'attributes': [],
                'tabular_sections': [],
                'standard_attributes': []
            }
            
            # Извлекаем реквизиты
            for attr in root.findall('.//{*}Attribute'):
                attr_data = {
                    'name': attr.findtext('{*}Name', default=''),
                    'synonym': attr.findtext('{*}Synonym', default=''),
                    'comment': attr.findtext('{*}Comment', default=''),
                    'type': self._extract_type_info(attr),
                    'mandatory': attr.findtext('{*}FillChecking', default='') == 'ShowError',
                    'use': attr.findtext('{*}Use', default='') != 'DontUse'
                }
                if attr_data['name']:
                    metadata['attributes'].append(attr_data)
            
            # Извлекаем табличные части
            for tab_section in root.findall('.//{*}TabularSection'):
                section_name = tab_section.findtext('{*}Name', default='')
                if section_name:
                    section_data = {
                        'name': section_name,
                        'synonym': tab_section.findtext('{*}Synonym', default=''),
                        'use_standard_attributes': tab_section.findtext('{*}UseStandardAttributes', default='') == 'true',
                        'columns': []
                    }
                    
                    # Извлекаем колонки табличной части
                    for attr in tab_section.findall('.//{*}Attribute'):
                        col_data = {
                            'name': attr.findtext('{*}Name', default=''),
                            'synonym': attr.findtext('{*}Synonym', default=''),
                            'type': self._extract_type_info(attr),
                            'mandatory': attr.findtext('{*}FillChecking', default='') == 'ShowError'
                        }
                        if col_data['name']:
                            section_data['columns'].append(col_data)
                    
                    metadata['tabular_sections'].append(section_data)
            
            # Стандартные реквизиты
            for std_attr in root.findall('.//{*}StandardAttribute'):
                std_name = std_attr.findtext('{*}Name', default='')
                if std_name:
                    metadata['standard_attributes'].append({
                        'name': std_name,
                        'synonym': std_attr.findtext('{*}Synonym', default=''),
                        'use': std_attr.findtext('{*}Use', default='') != 'DontUse'
                    })
            
            return metadata
            
        except Exception as e:
            self.errors.append(f"Ошибка парсинга метаданных документа {xml_file}: {str(e)}")
            return None
    
    def _extract_type_info(self, element: ET.Element) -> Dict[str, Any]:
        """
        Извлечение информации о типе данных
        """
        type_info = {
            'types': [],
            'string_qualifiers': None,
            'number_qualifiers': None,
            'date_qualifiers': None
        }
        
        # Ищем Type элемент
        type_elem = element.find('.//{*}Type')
        if type_elem is None:
            return type_info
        
        # Извлекаем типы
        for type_tag in type_elem.findall('.//{*}Type'):
            type_text = type_tag.text
            if type_text:
                type_info['types'].append(type_text)
        
        # Строковые квалификаторы
        string_qual = type_elem.find('.//{*}StringQualifiers')
        if string_qual is not None:
            type_info['string_qualifiers'] = {
                'length': string_qual.findtext('{*}Length', default=''),
                'allow_variable_length': string_qual.findtext('{*}AllowedLength', default='') == 'Variable'
            }
        
        # Числовые квалификаторы
        number_qual = type_elem.find('.//{*}NumberQualifiers')
        if number_qual is not None:
            type_info['number_qualifiers'] = {
                'precision': number_qual.findtext('{*}Digits', default=''),
                'scale': number_qual.findtext('{*}FractionDigits', default=''),
                'allow_negative': number_qual.findtext('{*}AllowedSign', default='') != 'Nonnegative'
            }
        
        # Квалификаторы даты
        date_qual = type_elem.find('.//{*}DateQualifiers')
        if date_qual is not None:
            type_info['date_qualifiers'] = {
                'date_fractions': date_qual.findtext('{*}DateFractions', default='')
            }
        
        return type_info
    
    def _get_namespace(self, root: ET.Element) -> str:
        """Получение namespace из корневого элемента"""
        if '}' in root.tag:
            return root.tag.split('}')[0][1:]
        return ''
    
    def _get_text(self, root: ET.Element, tag: str, namespace: str = '') -> str:
        """Безопасное получение текста элемента"""
        if namespace:
            elem = root.find(f'.//{{{namespace}}}{tag}')
        else:
            elem = root.find(f'.//{tag}')
        return elem.text if elem is not None and elem.text else ''


def main():
    """Запуск полного парсинга с метаданными"""
    print("=" * 80)
    print("ПОЛНЫЙ ПАРСИНГ КОНФИГУРАЦИИ С МЕТАДАННЫМИ")
    print("=" * 80)
    
    edt_path = Path("./1c_configurations/ERPCPM")
    
    if not edt_path.exists():
        print(f"[ERROR] Конфигурация не найдена: {edt_path}")
        return 1
    
    print(f"\nКонфигурация: {edt_path}")
    print("\nЭто займет ~6-10 минут. Процесс будет показывать прогресс каждые 100 объектов.\n")
    
    # Создаем парсер с метаданными
    parser = EDTParserWithMetadata(edt_path)
    
    # Запускаем полный парсинг
    start_time = time.time()
    results = parser.parse_configuration("ERPCPM")
    elapsed = time.time() - start_time
    
    # Сохраняем результаты
    output_dir = Path("./output/edt_parser")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Основной файл с результатами
    output_file = output_dir / "full_parse_with_metadata.json"
    parser.save_results(results, output_file)
    
    # Статистика
    stats_file = output_dir / "parse_statistics.json"
    stats = {
        'total_time': elapsed,
        'total_objects': (len(results.get('common_modules', [])) + 
                         len(results.get('catalogs', [])) + 
                         len(results.get('documents', []))),
        'common_modules': len(results.get('common_modules', [])),
        'catalogs': len(results.get('catalogs', [])),
        'documents': len(results.get('documents', [])),
        'total_functions': parser.stats.get('functions', 0),
        'total_procedures': parser.stats.get('procedures', 0),
        'errors': len(parser.errors),
        'rate': (len(results.get('common_modules', [])) + 
                len(results.get('catalogs', [])) + 
                len(results.get('documents', []))) / elapsed if elapsed > 0 else 0
    }
    
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 80)
    print("ПОЛНЫЙ ПАРСИНГ ЗАВЕРШЕН!")
    print("=" * 80)
    print(f"\nВремя выполнения: {elapsed/60:.2f} минут ({elapsed:.2f} секунд)")
    print(f"Всего объектов: {stats['total_objects']:,}")
    print(f"   - Общих модулей: {stats['common_modules']:,}")
    print(f"   - Справочников: {stats['catalogs']:,}")
    print(f"   - Документов: {stats['documents']:,}")
    print(f"Функций: {stats['total_functions']:,}")
    print(f"Процедур: {stats['total_procedures']:,}")
    print(f"Скорость: {stats['rate']:.2f} объектов/сек")
    print(f"Ошибок: {stats['errors']}")
    
    print(f"\nРезультаты:")
    print(f"   - Полные данные: {output_file}")
    print(f"   - Статистика: {stats_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

