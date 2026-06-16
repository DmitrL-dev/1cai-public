
#!/usr/bin/env python3
"""Глубокий анализ структуры XML конфигурации 1С"""

import xml.etree.ElementTree as ET
from pathlib import Path

config_file = Path("1c_configurations/DO/config.xml")
print(f"Анализ: {config_file.name} ({config_file.stat().st_size / 1024 / 1024:.1f} MB)\n")

# Читаем файл с правильной обработкой BOM
with open(config_file, 'rb') as f:
    raw_bytes = f.read()
    if raw_bytes.startswith(b'\xef\xbb\xbf'):
        raw_bytes = raw_bytes[3:]
    content = raw_bytes.decode('utf-8')

root = ET.fromstring(content)

print(f"Root tag: {root.tag}")
print(f"Root attrib: {root.attrib}\n")

# Проверяем первые дочерние элементы
print("=" * 70)
print("Первые 10 дочерних элементов root:")
print("=" * 70)
for i, child in enumerate(list(root)[:10]):
    print(f"{i+1}. Tag: {child.tag}")
    print(f"   Attr: {child.attrib}")
    print(f"   Children: {len(list(child))}")
    
    # Ищем внутри дочерних элементов
    for subchild in list(child)[:3]:
        if subchild.text and len(subchild.text) > 100:
            print(f"   -> {subchild.tag}: текст ({len(subchild.text)} символов)")
        else:
            print(f"   -> {subchild.tag}: {len(list(subchild))} дочерних")

print("\n" + "=" * 70)
print("Поиск элементов с кодом (текст > 1000 символов):")
print("=" * 70)

elements_with_code = []
for elem in root.iter():
    if elem.text and len(elem.text.strip()) > 1000:
        # Проверяем, что это похоже на код (содержит ключевые слова BSL)
        text_sample = elem.text[:500].lower()
        if any(keyword in text_sample for keyword in ['функция', 'процедура', 'переменная', 'возврат']):
            elements_with_code.append({
                'tag': elem.tag,
                'text_length': len(elem.text),
                'parent': elem.getparent().tag if hasattr(elem, 'getparent') else 'Unknown',
                'path': self._get_path(elem, root) if hasattr(self, '_get_path') else 'N/A'
            })

print(f"Найдено элементов с кодом: {len(elements_with_code)}")
if elements_with_code:
    print("\nПримеры:")
    for i, elem_info in enumerate(elements_with_code[:5]):
        print(f"{i+1}. Tag: {elem_info['tag']}")
        print(f"   Length: {elem_info['text_length']}")
        print(f"   Parent: {elem_info['parent']}")
        print()

# Альтернативный способ - поиск по атрибутам
print("=" * 70)
print("Поиск по атрибуту 'name' с модулями:")
print("=" * 70)

elements_with_name = []
for elem in root.iter():
    name = elem.get('Имя') or elem.get('name')
    if name and 'модуль' in name.lower() or 'module' in name.lower():
        elements_with_name.append({
            'tag': elem.tag,
            'name': name,
            'has_text': bool(elem.text and len(elem.text) > 100)
        })

print(f"Найдено элементов с 'модуль' в имени: {len(elements_with_name)}")
if elements_with_name:
    for i, elem_info in enumerate(elements_with_name[:5]):
        print(f"{i+1}. {elem_info['tag']} -> {elem_info['name']} (текст: {elem_info['has_text']})")





