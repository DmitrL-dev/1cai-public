
#!/usr/bin/env python3
"""
Глубокий анализ структуры EDT выгрузки 1С
Анализирует ЧТО есть в выгрузке vs ЧТО извлекает наш парсер

Цель: Evidence-based улучшения парсера
"""

import json
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict


class EDTStructureAnalyzer:
    """Анализатор структуры EDT выгрузки"""
    
    def __init__(self, edt_root_path: Path):
        self.edt_root = edt_root_path
        self.stats = defaultdict(int)
        self.samples = defaultdict(list)
        self.structure_map = {}
        
    def analyze_full_structure(self) -> Dict[str, Any]:
        """
        Полный анализ структуры EDT выгрузки
        
        Returns:
            Детальная статистика всех элементов
        """
        print("=" * 80)
        print("ГЛУБОКИЙ АНАЛИЗ СТРУКТУРЫ EDT ВЫГРУЗКИ")
        print("=" * 80)
        print(f"Путь: {self.edt_root}")
        print()
        
        start_time = time.time()
        
        # 1. Анализ верхнего уровня
        print("[*] АНАЛИЗ ВЕРХНЕГО УРОВНЯ")
        print("-" * 80)
        top_level = self.analyze_top_level()
        self.print_top_level_stats(top_level)
        
        # 2. Анализ общих модулей (CommonModules)
        print("\n[*] АНАЛИЗ ОБЩИХ МОДУЛЕЙ")
        print("-" * 80)
        common_modules_stats = self.analyze_common_modules()
        self.print_common_modules_stats(common_modules_stats)
        
        # 3. Анализ справочников (Catalogs)
        print("\n[*] АНАЛИЗ СПРАВОЧНИКОВ")
        print("-" * 80)
        catalogs_stats = self.analyze_catalogs()
        self.print_catalogs_stats(catalogs_stats)
        
        # 4. Анализ документов (Documents)
        print("\n[*] АНАЛИЗ ДОКУМЕНТОВ")
        print("-" * 80)
        documents_stats = self.analyze_documents()
        self.print_documents_stats(documents_stats)
        
        # 5. Анализ форм (Forms)
        print("\n[*] АНАЛИЗ ФОРМ")
        print("-" * 80)
        forms_stats = self.analyze_forms()
        self.print_forms_stats(forms_stats)
        
        # 6. Сводная статистика
        elapsed = time.time() - start_time
        print("\n" + "=" * 80)
        print(f"АНАЛИЗ ЗАВЕРШЕН ЗА {elapsed:.2f} СЕКУНД")
        print("=" * 80)
        
        return {
            'top_level': top_level,
            'common_modules': common_modules_stats,
            'catalogs': catalogs_stats,
            'documents': documents_stats,
            'forms': forms_stats,
            'analysis_time': elapsed
        }
    
    def analyze_top_level(self) -> Dict[str, int]:
        """Анализ структуры верхнего уровня"""
        top_level = {}
        
        for item in self.edt_root.iterdir():
            if item.is_dir():
                # Подсчет элементов в каждой папке
                count = len(list(item.iterdir()))
                top_level[item.name] = count
                self.stats[f'top_level_{item.name}'] = count
        
        return dict(sorted(top_level.items(), key=lambda x: x[1], reverse=True))
    
    def print_top_level_stats(self, stats: Dict[str, int]):
        """Вывод статистики верхнего уровня"""
        print(f"{'Тип объекта':<40} {'Количество':>10}")
        print("-" * 52)
        for name, count in stats.items():
            print(f"{name:<40} {count:>10,}")
        print("-" * 52)
        print(f"{'ВСЕГО типов объектов:':<40} {len(stats):>10}")
    
    def analyze_common_modules(self) -> Dict[str, Any]:
        """Детальный анализ общих модулей"""
        modules_path = self.edt_root / "CommonModules"
        if not modules_path.exists():
            return {}
        
        stats = {
            'total_modules': 0,
            'modules_with_code': 0,
            'modules_with_xml': 0,
            'total_code_size_mb': 0,
            'avg_code_size_kb': 0,
            'modules_by_ext': defaultdict(int),
            'sample_modules': []
        }
        
        modules = list(modules_path.iterdir())
        stats['total_modules'] = len(modules)
        
        code_sizes = []
        
        # Анализируем первые 100 модулей детально (для скорости)
        for i, module_dir in enumerate(modules[:100]):
            if not module_dir.is_dir():
                continue
            
            module_info = {
                'name': module_dir.name,
                'has_code': False,
                'has_xml': False,
                'code_size_kb': 0,
                'files': []
            }
            
            # Ищем файлы в модуле
            for file in module_dir.rglob('*'):
                if file.is_file():
                    module_info['files'].append(file.name)
                    ext = file.suffix
                    stats['modules_by_ext'][ext] += 1
                    
                    if ext == '.xml':
                        stats['modules_with_xml'] += 1
                        module_info['has_xml'] = True
                        module_info['code_size_kb'] = file.stat().st_size / 1024
                        code_sizes.append(module_info['code_size_kb'])
                    
                    if 'Module' in file.name or ext == '.bsl':
                        stats['modules_with_code'] += 1
                        module_info['has_code'] = True
            
            if i < 5:  # Сохраняем примеры первых 5 модулей
                stats['sample_modules'].append(module_info)
        
        if code_sizes:
            stats['total_code_size_mb'] = sum(code_sizes) / 1024
            stats['avg_code_size_kb'] = sum(code_sizes) / len(code_sizes)
        
        return stats
    
    def print_common_modules_stats(self, stats: Dict[str, Any]):
        """Вывод статистики общих модулей"""
        print(f"Всего общих модулей: {stats.get('total_modules', 0):,}")
        print(f"Модулей с XML: {stats.get('modules_with_xml', 0):,}")
        print(f"Модулей с кодом: {stats.get('modules_with_code', 0):,}")
        print(f"Общий размер кода: {stats.get('total_code_size_mb', 0):.2f} MB")
        print(f"Средний размер модуля: {stats.get('avg_code_size_kb', 0):.2f} KB")
        
        if stats.get('modules_by_ext'):
            print("\nРаспределение по типам файлов:")
            for ext, count in sorted(stats['modules_by_ext'].items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {ext or '(no ext)': <20} {count:>6,}")
        
        if stats.get('sample_modules'):
            print("\nПримеры модулей (первые 5):")
            for i, module in enumerate(stats['sample_modules'], 1):
                print(f"\n  {i}. {module['name']}")
                print(f"     Файлы: {', '.join(module['files'][:5])}")
                if len(module['files']) > 5:
                    print(f"     ... и ещё {len(module['files']) - 5} файлов")
                print(f"     Размер кода: {module['code_size_kb']:.2f} KB")
    
    def analyze_catalogs(self) -> Dict[str, Any]:
        """Анализ справочников"""
        catalogs_path = self.edt_root / "Catalogs"
        if not catalogs_path.exists():
            return {}
        
        catalogs = list(catalogs_path.iterdir())
        stats = {
            'total_catalogs': len(catalogs),
            'sample_catalogs': []
        }
        
        # Анализируем первые 5 справочников детально
        for catalog_dir in catalogs[:5]:
            if not catalog_dir.is_dir():
                continue
            
            catalog_info = {
                'name': catalog_dir.name,
                'has_forms': False,
                'has_commands': False,
                'has_manager_module': False,
                'has_object_module': False,
                'forms_count': 0,
                'commands_count': 0
            }
            
            # Проверяем наличие элементов
            if (catalog_dir / "Forms").exists():
                catalog_info['has_forms'] = True
                catalog_info['forms_count'] = len(list((catalog_dir / "Forms").iterdir()))
            
            if (catalog_dir / "Commands").exists():
                catalog_info['has_commands'] = True
                catalog_info['commands_count'] = len(list((catalog_dir / "Commands").iterdir()))
            
            # Ищем модули
            for file in catalog_dir.rglob('*.xml'):
                if 'ManagerModule' in file.name:
                    catalog_info['has_manager_module'] = True
                if 'ObjectModule' in file.name:
                    catalog_info['has_object_module'] = True
            
            stats['sample_catalogs'].append(catalog_info)
        
        return stats
    
    def print_catalogs_stats(self, stats: Dict[str, Any]):
        """Вывод статистики справочников"""
        print(f"Всего справочников: {stats.get('total_catalogs', 0):,}")
        
        if stats.get('sample_catalogs'):
            print("\nПримеры справочников (первые 5):")
            for i, catalog in enumerate(stats['sample_catalogs'], 1):
                print(f"\n  {i}. {catalog['name']}")
                print(f"     Формы: {catalog['forms_count']}")
                print(f"     Команды: {catalog['commands_count']}")
                print(f"     Модуль менеджера: {'+' if catalog['has_manager_module'] else '-'}")
                print(f"     Модуль объекта: {'+' if catalog['has_object_module'] else '-'}")
    
    def analyze_documents(self) -> Dict[str, Any]:
        """Анализ документов"""
        documents_path = self.edt_root / "Documents"
        if not documents_path.exists():
            return {}
        
        documents = list(documents_path.iterdir())
        stats = {
            'total_documents': len(documents),
            'sample_documents': []
        }
        
        # Анализируем первые 5 документов детально
        for doc_dir in documents[:5]:
            if not doc_dir.is_dir():
                continue
            
            doc_info = {
                'name': doc_dir.name,
                'has_forms': False,
                'has_commands': False,
                'has_manager_module': False,
                'has_object_module': False,
                'has_tabular_sections': False,
                'forms_count': 0,
                'commands_count': 0
            }
            
            if (doc_dir / "Forms").exists():
                doc_info['has_forms'] = True
                doc_info['forms_count'] = len(list((doc_dir / "Forms").iterdir()))
            
            if (doc_dir / "Commands").exists():
                doc_info['has_commands'] = True
                doc_info['commands_count'] = len(list((doc_dir / "Commands").iterdir()))
            
            # Ищем табличные части в XML
            for xml_file in doc_dir.glob('*.xml'):
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    # Ищем TabularSections
                    if root.findall('.//TabularSection') or root.findall('.//TabularSections'):
                        doc_info['has_tabular_sections'] = True
                        break
                except:
                    pass
            
            stats['sample_documents'].append(doc_info)
        
        return stats
    
    def print_documents_stats(self, stats: Dict[str, Any]):
        """Вывод статистики документов"""
        print(f"Всего документов: {stats.get('total_documents', 0):,}")
        
        if stats.get('sample_documents'):
            print("\nПримеры документов (первые 5):")
            for i, doc in enumerate(stats['sample_documents'], 1):
                print(f"\n  {i}. {doc['name']}")
                print(f"     Формы: {doc['forms_count']}")
                print(f"     Команды: {doc['commands_count']}")
                print(f"     Табличные части: {'+' if doc['has_tabular_sections'] else '-'}")
    
    def analyze_forms(self) -> Dict[str, Any]:
        """Анализ форм"""
        # Формы могут быть в CommonForms или в объектах
        common_forms_path = self.edt_root / "CommonForms"
        stats = {
            'common_forms': 0,
            'total_form_modules': 0
        }
        
        if common_forms_path.exists():
            stats['common_forms'] = len(list(common_forms_path.iterdir()))
        
        return stats
    
    def print_forms_stats(self, stats: Dict[str, Any]):
        """Вывод статистики форм"""
        print(f"Общих форм: {stats.get('common_forms', 0):,}")
    
    def save_results(self, results: Dict[str, Any], output_file: Path):
        """Сохранение результатов анализа"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n[+] Результаты сохранены: {output_file}")


def main():
    """Главная функция"""
    # Путь к EDT выгрузке
    edt_path = Path("./1c_configurations/ERPCPM")
    
    if not edt_path.exists():
        print(f"❌ Папка не найдена: {edt_path}")
        print("Убедитесь что выгрузка EDT находится в ./1c_configurations/ERPCPM/")
        return 1
    
    # Создаем анализатор
    analyzer = EDTStructureAnalyzer(edt_path)
    
    # Запускаем анализ
    results = analyzer.analyze_full_structure()
    
    # Сохраняем результаты
    output_dir = Path("./analysis")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "edt_structure_analysis.json"
    analyzer.save_results(results, output_file)
    
    print("\n" + "=" * 80)
    print("[SUCCESS] ГЛУБОКИЙ АНАЛИЗ ЗАВЕРШЕН")
    print("=" * 80)
    print(f"Результаты сохранены в: {output_file}")
    print()
    print("СЛЕДУЮЩИЙ ШАГ:")
    print("Запустить сравнение с текущим парсером для gap analysis")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

