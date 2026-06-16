
#!/usr/bin/env python3
"""Тестирование API ИТС"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from src.services.its_library_service import get_its_service


async def test_api():
    """Тест API эндпоинтов ИТС"""
    its_service = get_its_service(
        username=os.environ.get("ITS_USERNAME", ""),
        password=os.environ.get("ITS_PASSWORD", ""),
    )

    print("Авторизация...")
    auth_result = await its_service.authenticate()

    if not auth_result:
        print("Не удалось авторизоваться")
        return

    print("Авторизация успешна!")
    print("\n" + "=" * 70)
    print("Тестирование API эндпоинтов")
    print("=" * 70)

    # Тест получения контента ERP
    print("\n[TEST] Получение контента ERP (content/78/1/hdoc)...")
    api_url = "https://its.1c.ru/db/metod8dev/content/78/1/hdoc?bus"
    response = its_service.session.get(api_url)

    print(f"[INFO] Status: {response.status_code}")
    print(f"[INFO] Content-Type: {response.headers.get('content-type', 'N/A')}")
    print(f"[INFO] Content length: {len(response.text)} байт")

    # Проверяем тип ответа
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type or "json" in content_type:
        print("[INFO] Ответ в формате JSON")
        try:
            import json

            data = json.loads(response.text)
            print(f"[INFO] JSON keys: {list(data.keys())[:10]}")
            print(f"[INFO] First 500 chars: {str(data)[:500]}")
        except Exception as e:
            print(f"[WARN] Ошибка парсинга JSON: {e}")
    elif "text/html" in content_type:
        print("[INFO] Ответ в формате HTML")
        print(f"[INFO] First 500 chars: {response.text[:500]}")

        # Сохраняем для анализа
        with open("its_api_response.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("[INFO] HTML сохранен в its_api_response.html")

    print("\n[OK] Тест завершен")


if __name__ == "__main__":
    asyncio.run(test_api())
