
#!/usr/bin/env python3
"""Проверка структуры XML конфигурации 1С"""

import xml.etree.ElementTree as ET
from pathlib import Path

# Проверяем самый маленький файл
config_file = Path("1c_configurations/DO/config.xml")

print(f"Проверка структуры: {config_file}")
print(f"Размер: {config_file.stat().st_size / 1024 / 1024:.1f} MB")
print("=" * 60)

tree = ET.parse(config_file)
root = tree.getroot()

print(f"\nRoot tag: {root.tag}")
print(f"Root namespace: {root.tag.split('}')[0] if '}' in root.tag else 'None'}")

# Ищем модули разными способами
print("\n" + "=" * 60)
print("Поиск модулей:")
print("=" * 60)

# Способ 1: Поиск по тегу Module
modules = root.findall('.//Module')
print(f"1. Найдено элементов 'Module': {len(modules)}")

# Способ 2: Поиск по ObjectModule
obj_modules = root.findall('.//ObjectModule')
print(f"2. Найдено элементов 'ObjectModule': {len(obj_modules)}")

# Способ 3: Поиск по FormModule
form_modules = root.findall('.//FormModule')
print(f"3. Найдено элементов 'FormModule': {len(form_modules)}")

# Способ 4: Поиск всех элементов с 'Module' в имени
all_with_module = [elem for elem in root.iter() if 'Module' in elem.tag]
print(f"4. Найдено элементов с 'Module' в теге: {len(all_with_module)}")
if all_with_module:
    print(f"   Примеры тегов: {set([elem.tag for elem in all_with_module[:5]])}")

# Способ 5: Поиск по namespace
namespaces = {}
for elem in root.iter():
    if '}' in elem.tag:
        ns = elem.tag.split('}')[0]
        namespaces[ns] = namespaces.get(ns, 0) + 1

print(f"\n5. Найденные namespaces: {len(namespaces)}")
for ns, count in list(namespaces.items())[:5]:
    print(f"   {ns}: {count} элементов")

# Способ 6: Проверка структуры документа
print("\n" + "=" * 60)
print("Структура документа:")
print("=" * 60)

documents = root.findall('.//Document')
print(f"Documents: {len(documents)}")
if documents:
    first_doc = documents[0]
    print(f"  Первый Document name: {first_doc.get('name', 'N/A')}")
    # Проверяем дочерние элементы первого документа
    print(f"  Дочерние элементы первого Document:")
    for child in list(first_doc)[:10]:
        print(f"    - {child.tag}")

catalogs = root.findall('.//Catalog')
print(f"\nCatalogs: {len(catalogs)}")
if catalogs:
    first_cat = catalogs[0]
    print(f"  Первый Catalog name: {first_cat.get('name', 'N/A')}")

common_modules = root.findall('.//CommonModule')
print(f"\nCommonModules: {len(common_modules)}")
if common_modules:
    first_cm = common_modules[0]
    print(f"  Первый CommonModule name: {first_cm.get('name', 'N/A')}")
    # Проверяем есть ли Module внутри
    cm_module = first_cm.find('.//Module')
    if cm_module is not None:
        print(f"  Найден Module внутри, длина текста: {len(cm_module.text or '')}")
    else:
        print(f"  Module внутри не найден")
        print(f"  Дочерние элементы:")
        for child in list(first_cm)[:10]:
            print(f"    - {child.tag}")

# Попробуем найти любой модуль с текстом
print("\n" + "=" * 60)
print("Поиск модулей с кодом:")
print("=" * 60)

modules_with_code = []
for elem in root.iter():
    if 'Module' in elem.tag and elem.text and len(elem.text.strip()) > 100:
        modules_with_code.append({
            'tag': elem.tag,
            'text_length': len(elem.text),
            'parent': elem.getparent().tag if hasattr(elem, 'getparent') else 'Unknown'
        })

print(f"Найдено модулей с кодом (>100 символов): {len(modules_with_code)}")
if modules_with_code:
    print("\nПримеры:")
    for i, mod in enumerate(modules_with_code[:5]):
        print(f"  {i+1}. Tag: {mod['tag']}, Length: {mod['text_length']}, Parent: {mod.get('parent', 'N/A')}")





