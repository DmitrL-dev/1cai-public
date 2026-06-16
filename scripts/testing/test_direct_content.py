
#!/usr/bin/env python3
"""
Прямое тестирование получения контента через известные эндпоинты
"""

import asyncio
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))

from src.services.its_library_service import get_its_service


async def test_direct_content():
    """Прямое тестирование известных рабочих эндпоинтов"""
    import os

    its_service = get_its_service(
        username=os.getenv("ITS_USERNAME", ""), password=os.getenv("ITS_PASSWORD", "")
    )
    
    print("=" * 70)
    print("ПРЯМОЕ ТЕСТИРОВАНИЕ ИЗВЕСТНЫХ ЭНДПОИНТОВ")
    print("=" * 70)
    
    print("\n[1] Авторизация...")
    auth_result = await its_service.authenticate()
    
    if not auth_result:
        print("[ERROR] Не удалось авторизоваться")
        return
    
    print("[OK] Авторизация успешна!\n")
    
    # Известный рабочий эндпоинт
    working_url = "https://its.1c.ru/db/metod8dev/content/100010/hdoc"
    
    print(f"[2] Тестирование известного рабочего эндпоинта: {working_url}")
    response = its_service.session.get(working_url)
    
    if response.status_code == 200:
        print(f"[OK] Статус: {response.status_code}")
        print(f"[OK] Размер: {len(response.text)} bytes")
        
        # Парсим HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем структуру - может быть информация о других конфигурациях
        print("\n[3] Анализ структуры контента...")
        
        # Ищем ссылки на другие конфигурации
        links = soup.find_all('a', href=True)
        config_links = []
        
        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Ищем ссылки на конфигурации
            if '/content/' in href and any(keyword in text.lower() for keyword in [
                'erp', 'управление предприятием', 'ut', 'управление торговлей',
                'zup', 'зарплата', 'бuh', 'бухгалтерия', 'holding', 'холдинг'
            ]):
                config_links.append({
                    'href': href,
                    'text': text
                })
                print(f"  Найдена ссылка: {text[:60]} -> {href}")
        
        print(f"\n[INFO] Найдено ссылок на конфигурации: {len(config_links)}")
        
        # Сохраняем успешный ответ для анализа
        with open("its_working_content.html", "w", encoding="utf-8", errors="ignore") as f:
            f.write(response.text)
        print("\n[OK] HTML сохранен в its_working_content.html")
        
        # Пробуем извлечь ID из структуры страницы
        print("\n[4] Поиск ID конфигураций в структуре...")
        
        # Ищем скрытые данные или атрибуты с ID
        all_ids = []
        
        # Ищем data-атрибуты
        for elem in soup.find_all(attrs={'id': True, 'data-id': True}):
            elem_id = elem.get('id', '')
            data_id = elem.get('data-id', '')
            if '78' in elem_id or '78' in data_id:
                all_ids.append(f"ID: {elem_id}, Data-ID: {data_id}")
        
        # Ищем упоминания ID в тексте
        all_text = soup.get_text()
        id_patterns = [
            r'content[:\s/]+(\d+)[:\s/]+(\d+)',
            r'ID[:\s]+(\d+)',
            r'78[:\s/]+(\d+)',
        ]
        
        import re
        for pattern in id_patterns:
            matches = re.finditer(pattern, all_text, re.IGNORECASE)
            for match in matches:
                if match.lastindex:
                    id_val = '/'.join([g for g in match.groups() if g])
                    if id_val not in all_ids:
                        all_ids.append(id_val)
        
        if all_ids:
            print(f"\n[INFO] Найдено потенциальных ID: {len(all_ids)}")
            for id_val in all_ids[:10]:
                print(f"  - {id_val}")
        
        # Тестируем найденные ID
        if config_links:
            print("\n[5] Тестирование найденных ссылок...")
            
            for i, link_data in enumerate(config_links[:5], 1):
                href = link_data['href']
                text = link_data['text']
                
                # Преобразуем относительный URL в абсолютный
                if href.startswith('/'):
                    test_url = f"https://its.1c.ru{href}"
                elif href.startswith('http'):
                    test_url = href
                else:
                    continue
                
                print(f"\n[TEST {i}] {text[:50]}")
                print(f"  URL: {test_url}")
                
                try:
                    resp = its_service.session.get(test_url, timeout=5)
                    print(f"  Status: {resp.status_code}, Size: {len(resp.text)} bytes")
                    
                    if resp.status_code == 200 and len(resp.text) > 1000:
                        print(f"  [SUCCESS] Работает!")
                        
                        # Проверяем контент
                        content_lower = resp.text.lower()
                        if any(keyword in content_lower for keyword in ['модуль', 'функция', 'процедура']):
                            print(f"  [SUCCESS] Содержит код!")
                        
                        # Сохраняем
                        filename = f"its_config_{i}_{text[:20].replace(' ', '_').lower()}.html"
                        with open(filename, "w", encoding="utf-8", errors="ignore") as f:
                            f.write(resp.text)
                        print(f"  [SAVED] Сохранено в {filename}")
                
                except Exception as e:
                    print(f"  [ERROR] {e}")


if __name__ == "__main__":
    asyncio.run(test_direct_content())





