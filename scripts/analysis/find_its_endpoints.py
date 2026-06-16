
#!/usr/bin/env python3
"""Поиск правильных эндпоинтов ИТС"""

import asyncio
import os
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from src.services.its_library_service import get_its_service


async def find_endpoints():
    """Поиск правильных эндпоинтов"""
    its_service = get_its_service(
        username=os.environ.get("ITS_USERNAME", ""),
        password=os.environ.get("ITS_PASSWORD", ""),
    )

    print("Авторизация...")
    auth_result = await its_service.authenticate()

    if not auth_result:
        print("Не удалось авторизоваться")
        return

    print("Авторизация успешна!\n")

    # Пробуем разные варианты эндпоинтов
    endpoints = [
        # Вариант 1: Прямой URL с hash
        "https://its.1c.ru/db/metod8dev#content:78:1",
        # Вариант 2: Content API
        "https://its.1c.ru/db/metod8dev/content/78/1/hdoc",
        "https://its.1c.ru/db/metod8dev/content/78/1/hdoc?bus",
        # Вариант 3: Без bus параметра
        "https://its.1c.ru/db/metod8dev/content/78/1",
        # Вариант 4: С параметром mode
        "https://its.1c.ru/db/metod8dev/content/78/1/hdoc?bus&event[name]=mode",
        # Вариант 5: Browse
        "https://its.1c.ru/db/metod8dev/browse/78/1",
        # Вариант 6: Прямой доступ к странице
        "https://its.1c.ru/db/metod8dev",
    ]

    print("=" * 70)
    print("Тестирование эндпоинтов")
    print("=" * 70)

    for endpoint in endpoints:
        print(f"\n[TEST] {endpoint}")
        try:
            response = its_service.session.get(endpoint)
            print(f"  Status: {response.status_code}")
            print(f"  Content-Type: {response.headers.get('content-type', 'N/A')}")
            print(f"  Size: {len(response.text)} байт")

            if response.status_code == 200:
                # Проверяем содержимое
                if len(response.text) > 1000:
                    soup = BeautifulSoup(response.text, "html.parser")

                    # Ищем полезный контент
                    headers = soup.find_all(["h1", "h2", "h3"])
                    if headers:
                        print(f"  [OK] Найдено заголовков: {len(headers)}")
                        print(f"  Пример: {headers[0].get_text(strip=True)[:80]}")

                    # Ищем код
                    code_blocks = soup.find_all(["pre", "code"])
                    if code_blocks:
                        print(f"  [OK] Найдено блоков кода: {len(code_blocks)}")

                    # Ищем ссылки
                    links = soup.find_all("a", href=True)
                    useful_links = [
                        l
                        for l in links
                        if any(
                            x in l.get("href", "")
                            for x in ["module", "модуль", "config", "конфигурация"]
                        )
                    ]
                    if useful_links:
                        print(f"  [OK] Найдено полезных ссылок: {len(useful_links)}")

                    print(f"  [OK] Эндпоинт работает!")
                else:
                    print(f"  [WARN] Мало контента: {response.text[:200]}")

        except Exception as e:
            print(f"  [ERROR] {e}")

    print("\n" + "=" * 70)
    print("Поиск ссылок на документацию конфигураций")
    print("=" * 70)

    # Получаем главную страницу методики
    main_page = its_service.session.get("https://its.1c.ru/db/metod8dev")
    if main_page.status_code == 200:
        soup = BeautifulSoup(main_page.text, "html.parser")

        # Ищем ссылки на конфигурации
        config_keywords = [
            "ERP",
            "Управление торговлей",
            "Зарплата",
            "Бухгалтерия",
            "Холдинг",
        ]
        links = soup.find_all("a", href=True)

        print(f"\nНайдено ссылок: {len(links)}")
        print("\nСсылки, связанные с конфигурациями:")

        config_links = []
        for link in links:
            link_text = link.get_text(strip=True)
            link_href = link.get("href", "")

            if any(keyword in link_text for keyword in config_keywords):
                config_links.append((link_text, link_href))
                print(f"  - {link_text[:60]} -> {link_href[:80]}")

        if config_links:
            print(f"\n[OK] Найдено {len(config_links)} ссылок на конфигурации")


if __name__ == "__main__":
    asyncio.run(find_endpoints())
