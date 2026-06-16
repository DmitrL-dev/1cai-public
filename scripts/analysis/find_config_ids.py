
#!/usr/bin/env python3
"""Поиск правильных ID конфигураций в ИТС"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bs4 import BeautifulSoup

from src.services.its_library_service import get_its_service


async def find_config_ids():
    """Поиск ID конфигураций через browse и ссылки"""
    import os

    its_service = get_its_service(
        username=os.getenv("ITS_USERNAME", ""), password=os.getenv("ITS_PASSWORD", "")
    )
    
    print("=" * 70)
    print("ПОИСК ПРАВИЛЬНЫХ ID КОНФИГУРАЦИЙ")
    print("=" * 70)
    
    print("\n[1] Авторизация...")
    auth_result = await its_service.authenticate()
    
    if not auth_result:
        print("[ERROR] Не удалось авторизоваться")
        return
    
    print("[OK] Авторизация успешна!\n")
    
    print("[2] Получение страницы browse (содержание)...")
    browse_url = "https://its.1c.ru/db/metod8dev/browse/13/-1"
    response = its_service.session.get(browse_url)
    
    if response.status_code != 200:
        print(f"[ERROR] Не удалось получить страницу: {response.status_code}")
        return
    
    print(f"[OK] Страница получена ({len(response.text)} bytes)\n")
    
    print("[3] Поиск ссылок на конфигурации...")
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Ищем ссылки на конфигурации
    config_keywords = [
        'ERP', 'Управление предприятием', 'Управление торговлей', 'Зарплата',
        'Бухгалтерия', 'Холдинг', 'Документооборот', 'Комплексная автоматизация'
    ]
    
    found_links = []
    all_links = soup.find_all('a', href=True)
    
    for link in all_links:
        link_text = link.get_text(strip=True)
        link_href = link.get('href', '')
        
        # Проверяем текст ссылки
        for keyword in config_keywords:
            if keyword.lower() in link_text.lower():
                # Проверяем что это ссылка на контент
                if '/content/' in link_href or 'content:' in link_href:
                    found_links.append({
                        'text': link_text,
                        'href': link_href,
                        'keyword': keyword
                    })
                    print(f"  ✅ {keyword}: {link_text[:60]}")
                    print(f"     URL: {link_href}")
    
    print(f"\n[INFO] Найдено ссылок: {len(found_links)}")
    
    # Извлекаем ID из ссылок
    config_ids = {}
    for link in found_links:
        href = link['href']
        keyword = link['keyword']
        
        # Извлекаем ID из URL
        # Формат: /db/metod8dev/content/78/1/hdoc
        # или: #content:78:1
        id_match = None
        
        # Из URL
        url_match = re.search(r'/content/(\d+)/(\d+)', href)
        if url_match:
            id_match = f"{url_match.group(1)}/{url_match.group(2)}"
        
        # Из hash
        hash_match = re.search(r'content:(\d+):(\d+)', href)
        if hash_match:
            id_match = f"{hash_match.group(1)}/{hash_match.group(2)}"
        
        # Только число
        if not id_match:
            num_match = re.search(r'/content/(\d+)', href)
            if num_match:
                id_match = num_match.group(1)
        
        if id_match:
            config_ids[keyword] = {
                'id': id_match,
                'href': href,
                'text': link['text']
            }
            print(f"\n[OK] {keyword}: ID = {id_match}")
    
    print("\n" + "=" * 70)
    print("НАЙДЕННЫЕ ID КОНФИГУРАЦИЙ:")
    print("=" * 70)
    
    for keyword, data in config_ids.items():
        print(f"\n{keyword}:")
        print(f"  ID: {data['id']}")
        print(f"  Текст: {data['text'][:80]}")
        print(f"  Ссылка: {data['href']}")
    
    # Тестируем найденные ID
    if config_ids:
        print("\n" + "=" * 70)
        print("ТЕСТИРОВАНИЕ НАЙДЕННЫХ ID:")
        print("=" * 70)
        
        for keyword, data in list(config_ids.items())[:3]:  # Тестируем первые 3
            config_id = data['id']
            
            # Пробуем разные форматы
            test_urls = [
                f"/db/metod8dev/content/{config_id}/hdoc",
                f"/db/metod8dev/content/{config_id}/hdoc?bus",
            ]
            
            for test_url in test_urls:
                full_url = f"https://its.1c.ru{test_url}"
                print(f"\n[TEST] {keyword}: {test_url}")
                
                try:
                    resp = its_service.session.get(
                        full_url,
                        headers={"X-Requested-With": "XMLHttpRequest", "Referer": "https://its.1c.ru/db/metod8dev"},
                        timeout=5
                    )
                    
                    status = "✅" if resp.status_code == 200 else "❌"
                    print(f"  {status} Status: {resp.status_code}, Size: {len(resp.text)} bytes")
                    
                    if resp.status_code == 200 and len(resp.text) > 1000:
                        print(f"  ✅ РАБОТАЕТ!")
                        
                        # Сохраняем для анализа
                        filename = f"its_config_{keyword.lower().replace(' ', '_')}.html"
                        with open(filename, "w", encoding="utf-8", errors="ignore") as f:
                            f.write(resp.text)
                        print(f"  💾 Сохранено в {filename}")
                
                except Exception as e:
                    print(f"  [ERROR] {e}")


if __name__ == "__main__":
    import re
    asyncio.run(find_config_ids())





