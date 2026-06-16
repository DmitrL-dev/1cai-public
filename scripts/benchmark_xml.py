
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Бенчмарк XML парсинга"""

import time
import xml.etree.ElementTree as ET


def test_xml_sizes():
    """Тест парсинга XML разных размеров"""
    
    print("Бенчмарк XML парсинга")
    print("=" * 60)
    
    sizes = [1000, 10000, 100000]
    
    for size in sizes:
        # Создаем XML
        xml = '<?xml version="1.0"?><root>'
        for i in range(size):
            xml += f'<item id="{i}">content{i}</item>'
        xml += '</root>'
        
        # Измеряем
        start = time.time()
        root = ET.fromstring(xml)
        elapsed = time.time() - start
        
        size_kb = len(xml) / 1024
        
        print(f"\n{size} элементов ({size_kb:.1f} KB):")
        print(f"  Время: {elapsed:.4f} сек")
        print(f"  Скорость: {size/elapsed:.0f} элем/сек")

if __name__ == "__main__":
    test_xml_sizes()




