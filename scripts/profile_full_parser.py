
#!/usr/bin/env python3
"""
Профилирование полного парсера конфигураций
С реальными измерениями
"""

import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def create_test_config_xml():
    """Создание тестового config.xml файла"""
    
    # Минимальный но реалистичный config
    test_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Configuration xmlns="http://v8.1c.ru/8.3/MDClasses">
    <CommonModule>
        <Properties>
            <Name>ОбщийМодульТест</Name>
        </Properties>
        <Module>
Функция ПолучитьДанные() Экспорт
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Контрагенты";
    Возврат Запрос.Выполнить();
КонецФункции

Функция РассчитатьСумму(Сумма1, Сумма2) Экспорт
    Возврат Сумма1 + Сумма2;
КонецФункции
        </Module>
    </CommonModule>
</Configuration>
"""
    
    # Дублируем модули для большего размера
    modules = []
    for i in range(100):  # 100 модулей
        modules.append(f"""
    <CommonModule>
        <Properties>
            <Name>Модуль{i}</Name>
        </Properties>
        <Module>
Функция Функция{i}() Экспорт
    Запрос = Новый Запрос;
    Возврат Запрос.Выполнить();
КонецФункции
        </Module>
    </CommonModule>
""")
    
    full_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Configuration xmlns="http://v8.1c.ru/8.3/MDClasses">
    {"".join(modules)}
</Configuration>
"""
    
    return full_xml


def test_xml_parsing():
    """Тест XML парсинга"""
    
    print("=" * 70)
    print("ТЕСТ XML ПАРСИНГА")
    print("=" * 70)
    
    xml_content = create_test_config_xml()
    
    print(f"\nРазмер XML: {len(xml_content) / 1024:.1f} KB")
    print(f"Строк: {len(xml_content.split(chr(10)))}")
    
    # Тест 1: ET.fromstring (текущий подход)
    print("\n[ТЕСТ 1] xml.etree.ElementTree.fromstring()")
    
    times = []
    for i in range(3):
        start = time.time()
        root = ET.fromstring(xml_content)
        elapsed = time.time() - start
        times.append(elapsed)
        
        # Найти все модули
        modules = list(root.iter())
        print(f"  Прогон {i+1}: {elapsed:.4f} сек ({len(modules)} элементов)")
    
    avg_time = sum(times) / len(times)
    print(f"\nСреднее время ET.fromstring: {avg_time:.4f} сек")
    
    # Тест 2: Сколько времени на поиск модулей
    print("\n[ТЕСТ 2] Поиск модулей через root.iter()")
    
    root = ET.fromstring(xml_content)
    
    start = time.time()
    all_elems = list(root.iter())
    iter_time = time.time() - start
    print(f"  root.iter(): {iter_time:.4f} сек для {len(all_elems)} элементов")
    
    start = time.time()
    modules = root.findall('.//CommonModule')
    findall_time = time.time() - start
    print(f"  root.findall('.//CommonModule'): {findall_time:.4f} сек, найдено {len(modules)}")
    
    # Итог
    print("\n" + "=" * 70)
    print("РЕЗУЛЬТАТЫ XML ПАРСИНГА:")
    print("=" * 70)
    print(f"Парсинг XML: {avg_time:.4f} сек")
    print(f"Поиск через iter: {iter_time:.4f} сек")
    print(f"Поиск через findall: {findall_time:.4f} сек")
    print(f"TOTAL: {avg_time + findall_time:.4f} сек")
    
    # Сохраняем результаты
    with open('xml_parsing_results.txt', 'w', encoding='utf-8') as f:
        f.write(f"XML Parsing Results\n")
        f.write(f"===================\n")
        f.write(f"XML size: {len(xml_content) / 1024:.1f} KB\n")
        f.write(f"ET.fromstring: {avg_time:.4f} sec\n")
        f.write(f"root.iter: {iter_time:.4f} sec\n")
        f.write(f"root.findall: {findall_time:.4f} sec\n")
        f.write(f"Total: {avg_time + findall_time:.4f} sec\n")
    
    print("\nРезультаты сохранены: xml_parsing_results.txt")
    
    return avg_time, iter_time, findall_time


def test_full_pipeline():
    """Тест полного pipeline: XML + BSL parsing"""
    
    print("\n" + "=" * 70)
    print("ТЕСТ ПОЛНОГО PIPELINE")
    print("=" * 70)
    
    xml_content = create_test_config_xml()
    
    # Парсим XML
    start_total = time.time()
    
    start = time.time()
    root = ET.fromstring(xml_content)
    xml_time = time.time() - start
    
    # Находим модули
    start = time.time()
    module_elems = root.findall('.//Module')
    search_time = time.time() - start
    
    # Парсим BSL в каждом модуле
    parser = ImprovedBSLParser()
    
    total_functions = 0
    bsl_times = []
    
    start = time.time()
    for module_elem in module_elems:
        if module_elem.text:
            module_start = time.time()
            result = parser.parse(module_elem.text)
            bsl_time = time.time() - module_start
            bsl_times.append(bsl_time)
            total_functions += len(result['functions'])
    
    total_bsl_time = time.time() - start
    
    total_time = time.time() - start_total
    
    print(f"\nРезультаты:")
    print(f"  1. XML парсинг: {xml_time:.4f} сек ({xml_time/total_time*100:.1f}%)")
    print(f"  2. Поиск модулей: {search_time:.4f} сек ({search_time/total_time*100:.1f}%)")
    print(f"  3. BSL парсинг: {total_bsl_time:.4f} сек ({total_bsl_time/total_time*100:.1f}%)")
    print(f"  ---")
    print(f"  TOTAL: {total_time:.4f} сек")
    print(f"\n  Модулей обработано: {len(module_elems)}")
    print(f"  Функций извлечено: {total_functions}")
    print(f"  Среднее время на модуль: {total_bsl_time/len(module_elems)*1000:.2f} мс")
    
    # Определяем bottleneck
    print("\n" + "=" * 70)
    print("АНАЛИЗ BOTTLENECKS:")
    print("=" * 70)
    
    bottlenecks = [
        ('XML parsing', xml_time),
        ('Module search', search_time),
        ('BSL parsing', total_bsl_time)
    ]
    
    bottlenecks.sort(key=lambda x: x[1], reverse=True)
    
    print("\nГде тратится время (от большего к меньшему):")
    for i, (name, t) in enumerate(bottlenecks, 1):
        pct = t / total_time * 100
        print(f"  {i}. {name}: {t:.4f} сек ({pct:.1f}%)")
    
    print(f"\nГлавный bottleneck: {bottlenecks[0][0]}")
    
    # Сохраняем
    with open('full_pipeline_results.txt', 'w', encoding='utf-8') as f:
        f.write(f"Full Pipeline Results\n")
        f.write(f"====================\n")
        f.write(f"Total time: {total_time:.4f} sec\n")
        f.write(f"XML parsing: {xml_time:.4f} sec ({xml_time/total_time*100:.1f}%)\n")
        f.write(f"Module search: {search_time:.4f} sec ({search_time/total_time*100:.1f}%)\n")
        f.write(f"BSL parsing: {total_bsl_time:.4f} sec ({total_bsl_time/total_time*100:.1f}%)\n")
        f.write(f"\nMain bottleneck: {bottlenecks[0][0]}\n")
    
    print("\nРезультаты сохранены: full_pipeline_results.txt")


if __name__ == "__main__":
    # Тест BSL парсера
    test_parser_performance()
    
    # Тест полного pipeline
    test_full_pipeline()
    
    print("\n" + "=" * 70)
    print("ЗАВЕРШЕНО")
    print("=" * 70)
    print("\nТеперь смотрите:")
    print("  - baseline_performance.txt")
    print("  - xml_parsing_results.txt")
    print("  - full_pipeline_results.txt")
    print("\nЭто РЕАЛЬНЫЕ данные для принятия решений!")




