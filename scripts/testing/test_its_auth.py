
#!/usr/bin/env python3
"""Тестирование авторизации в ИТС"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from src.services.its_library_service import get_its_service


async def test_auth():
    """Тест авторизации"""
    print("Тестирование авторизации в ИТС...")
    its_username = os.environ.get("ITS_USERNAME", "")
    its_password = os.environ.get("ITS_PASSWORD", "")
    print(f"Username: {its_username}")
    print(f"Password: {'*' * len(its_password) if its_password else '(not set)'}")
    print("=" * 60)

    its_service = get_its_service(username=its_username, password=its_password)

    print("\nПопытка авторизации...")
    result = await its_service.authenticate()

    if result:
        print("\n[OK] Авторизация успешна!")
        print(f"Authenticated: {its_service.authenticated}")

        # Пробуем получить защищённую страницу
        print("\nПопытка получения защищённой страницы...")
        response = its_service.session.get("https://its.1c.ru/db")
        print(f"Status: {response.status_code}")
        print(f"URL: {response.url}")
        print(f"Content length: {len(response.text)}")

        # Сохраняем HTML для анализа
        with open("its_test_page.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("\n[INFO] HTML страница сохранена в its_test_page.html")

    else:
        print("\n[ERROR] Авторизация не удалась")
        print("\n[INFO] Проверьте:")
        print("  1. Правильность учётных данных")
        print("  2. Доступ к интернету")
        print("  3. Доступность сайта its.1c.ru")

        # Пробуем получить страницу без авторизации для анализа
        print("\n[INFO] Попытка получения главной страницы для анализа...")
        try:
            response = its_service.session.get("https://its.1c.ru")
            print(f"Status: {response.status_code}")
            print(f"URL: {response.url}")

            # Сохраняем для анализа
            with open("its_main_page.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print("[INFO] HTML сохранен в its_main_page.html")

            # Ищем формы входа
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")
            forms = soup.find_all("form")
            print(f"\nНайдено форм: {len(forms)}")
            for i, form in enumerate(forms[:5]):
                print(f"\nФорма {i + 1}:")
                print(f"  Action: {form.get('action', 'N/A')}")
                print(f"  Method: {form.get('method', 'N/A')}")
                inputs = form.find_all("input")
                print(f"  Inputs: {len(inputs)}")
                for inp in inputs[:5]:
                    print(f"    - {inp.get('type', 'text')}: {inp.get('name', 'N/A')}")

        except Exception as e:
            print(f"[ERROR] Ошибка получения страницы: {e}")


if __name__ == "__main__":
    asyncio.run(test_auth())
