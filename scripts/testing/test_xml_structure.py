
#!/usr/bin/env python3
"""
Тестирование структуры XML конфигураций 1С
"""

import xml.etree.ElementTree as ET
from pathlib import Path

config_file = Path("1c_configurations/ERP/config.xml")

print(f"Анализ: {config_file.name} ({config_file.stat().st_size / 1024 / 1024:.1f} MB)\n")

# Читаем файл с правильной обработкой BOM
with open(config_file, 'rb') as f:
    raw_bytes = f.read()
    if raw_bytes.startswith(b'\xef\xbb\xbf'):
        raw_bytes = raw_bytes[3:]
    content = raw_bytes.decode('utf-8')

root = ET.fromstring(content)

print(f"Root tag: {root.tag}")
print(f"Root attrib: {dict(list(root.attrib.items())[:5])}\n")

# Определяем namespace
namespace = None
if '}' in root.tag:
    namespace = root.tag.split('}')[0][1:]

print(f"Namespace: {namespace}\n")

# Функция для создания тега с namespace
def make_tag(tag_name):
    if namespace:
        return f"{{{namespace}}}{tag_name}"
    return tag_name

# Ищем объекты разными способами
print("=" * 70)
print("ПОИСК ОБЪЕКТОВ")
print("=" * 70)

# Способ 1: Поиск всех элементов с определенными тегами
print("\nСпособ 1: Поиск всех элементов")
all_elements = list(root.iter())
print(f"Всего элементов: {len(all_elements)}")

# Собираем уникальные теги
all_tags = set([e.tag for e in all_elements])
print(f"Уникальных тегов: {len(all_tags)}")

# Фильтруем интересующие теги
interesting_tags = [t for t in all_tags if any(keyword in t for keyword in ['Document', 'Документ', 'CommonModule', 'ОбщийМодуль', 'Catalog', 'Справочник', 'Register', 'Регистр'])]
print(f"\nИнтересующие теги ({len(interesting_tags)}):")
for tag in sorted(interesting_tags)[:20]:
    count = sum(1 for e in all_elements if e.tag == tag)
    print(f"  {tag}: {count} элементов")

# Способ 2: Поиск через findall с namespace
print("\n" + "=" * 70)
print("Способ 2: Поиск с namespace")
print("=" * 70)

if namespace:
    # Пробуем разные варианты
    test_tags = ['Document', 'CommonModule', 'Catalog', 'RegisterInformation']
    for tag in test_tags:
        found = root.findall(f'.//{{{namespace}}}{tag}')
        print(f"{{{namespace}}}{tag}: {len(found)}")
        
        # Пробуем русские варианты
        ru_tags = {'Document': 'Документ', 'CommonModule': 'ОбщийМодуль', 'Catalog': 'Справочник', 'RegisterInformation': 'РегистрСведений'}
        if tag in ru_tags:
            ru_tag = ru_tags[tag]
            found_ru = root.findall(f'.//{{{namespace}}}{ru_tag}')
            print(f"{{{namespace}}}{ru_tag}: {len(found_ru)}")
            
            if found_ru:
                # Показываем первый найденный объект
                first = found_ru[0]
                print(f"  Первый элемент:")
                print(f"    Tag: {first.tag}")
                print(f"    Attrib: {dict(list(first.attrib.items())[:3])}")
                
                # Ищем имя объекта
                props = first.find(f'.//{{{namespace}}}Properties')
                if props is not None:
                    name_elem = props.find(f'.//{{{namespace}}}Name')
                    if name_elem is not None:
                        print(f"    Name: {name_elem.text}")

# Способ 3: Поиск без namespace (если namespace не работает)
print("\n" + "=" * 70)
print("Способ 3: Поиск без namespace")
print("=" * 70)

for tag in ['Document', 'Документ', 'CommonModule', 'ОбщийМодуль']:
    found = root.findall(f'.//{tag}')
    print(f"{tag}: {len(found)}")





