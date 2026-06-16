
#!/usr/bin/env python3
"""Анализ структуры страниц ИТС после авторизации"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bs4 import BeautifulSoup

from src.services.its_library_service import get_its_service


async def analyze_its_structure():
    """Анализ структуры страниц ИТС"""
    # Security: Use environment variables for credentials
    username = os.getenv("ITS_USERNAME", "")
    password = os.getenv("ITS_PASSWORD", "")
    
    if not username or not password:
        print("[ERROR] Credentials not found in environment variables")
        print("Please set: ITS_USERNAME and ITS_PASSWORD")
        return
    
    its_service = get_its_service(username=username, password=password)
    
    print("Авторизация...")
    auth_result = await its_service.authenticate()
    
    if not auth_result:
        print("Не удалось авторизоваться")
        return
    
    print("Авторизация успешна!")
    print("\n" + "="*70)
    print("Анализ структуры страниц ИТС")
    print("="*70)
    
    # Получаем страницу документации ERP
    print("\n[INFO] Получение страницы ERP...")
    response = its_service.session.get("https://its.1c.ru/db/metod8dev#content:78:1")
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        print(f"\n[INFO] Статус: {response.status_code}")
        print(f"[INFO] URL: {response.url}")
        print(f"[INFO] Размер страницы: {len(response.text)} байт")
        
        # Анализируем структуру
        print("\n" + "="*70)
        print("Структура страницы:")
        print("="*70)
        
        # Ищем заголовки
        headers = soup.find_all(['h1', 'h2', 'h3', 'h4'])
        print(f"\nЗаголовки: {len(headers)}")
        for i, header in enumerate(headers[:10]):
            print(f"  {i+1}. {header.get_text(strip=True)[:100]}")
        
        # Ищем блоки с кодом
        code_blocks = soup.find_all(['pre', 'code'])
        print(f"\nБлоки кода: {len(code_blocks)}")
        for i, code in enumerate(code_blocks[:5]):
            text = code.get_text(strip=True)
            print(f"  {i+1}. Длина: {len(text)}, Начало: {text[:50]}")
        
        # Ищем ссылки на модули
        links = soup.find_all('a', href=True)
        module_links = [link for link in links if 'module' in link.get('href', '').lower() or 'модуль' in link.get_text().lower()]
        print(f"\nСсылки на модули: {len(module_links)}")
        for i, link in enumerate(module_links[:10]):
            print(f"  {i+1}. {link.get_text(strip=True)} -> {link.get('href')}")
        
        # Ищем таблицы
        tables = soup.find_all('table')
        print(f"\nТаблицы: {len(tables)}")
        
        # Сохраняем страницу для анализа
        with open("its_erp_page.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("\n[INFO] HTML сохранен в its_erp_page.html")
        
        # Анализируем классы элементов
        print("\n" + "="*70)
        print("Классы элементов:")
        print("="*70)
        
        divs_with_classes = soup.find_all('div', class_=True)
        classes = set()
        for div in divs_with_classes[:50]:
            div_classes = div.get('class', [])
            if isinstance(div_classes, list):
                classes.update(div_classes)
        
        print(f"\nНайдено уникальных классов: {len(classes)}")
        print("Примеры:")
        for cls in list(classes)[:20]:
            print(f"  - {cls}")
        
    else:
        print(f"[ERROR] Не удалось получить страницу: {response.status_code}")
        print(f"[INFO] URL: {response.url}")
        print(f"[INFO] Ответ: {response.text[:500]}")

if __name__ == "__main__":
    asyncio.run(analyze_its_structure())





