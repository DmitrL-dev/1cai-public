import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

print("🔍 Диагностика Qdrant подключения\n")
print("=" * 70)

# Тест 1: Импорт SDK
print("\n1️⃣ Проверка импорта qdrant-client...")
try:
    print(f"✅ qdrant_client импортирован")
    from qdrant_client import QdrantClient as QdrantSDK

    print("✅ QdrantClient импортирован из SDK")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)

# Тест 2: Прямое подключение через SDK
print("\n2️⃣ Тест прямого подключения через SDK...")
try:
    client = QdrantSDK(host="localhost", port=6333)
    print("✅ SDK клиент создан")

    # Получение коллекций
    collections = client.get_collections()
    print(f"✅ Коллекций найдено: {len(collections.collections)}")

    for col in collections.collections:
        print(f"   - {col.name}")

except Exception as e:
    print(f"❌ Ошибка прямого подключения: {e}")
    import traceback

    traceback.print_exc()

# Тест 3: Наш QdrantClient wrapper
print("\n3️⃣ Тест QdrantClient wrapper...")
try:
    from src.db.qdrant_client import QdrantClient

    client = QdrantClient(host="localhost", port=6333)
    print("✅ QdrantClient wrapper инициализирован")

    if client.connect():
        print("✅ QdrantClient.connect() успешно")

        # Проверка внутреннего клиента
        if client.client:
            print("✅ Внутренний SDK клиент доступен")

            try:
                collections = client.client.get_collections()
                print(f"✅ Коллекций через wrapper: {len(collections.collections)}")
            except Exception as e:
                print(f"❌ Ошибка получения коллекций: {e}")
        else:
            print("❌ Внутренний SDK клиент = None")
    else:
        print("❌ QdrantClient.connect() провалился")

except Exception as e:
    print(f"❌ Ошибка QdrantClient wrapper: {e}")
    import traceback

    traceback.print_exc()

# Тест 4: Проверка доступности порта
print("\n4️⃣ Проверка доступности порта 6333...")
try:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex(("localhost", 6333))
    sock.close()

    if result == 0:
        print("✅ Порт 6333 доступен")
    else:
        print(f"❌ Порт 6333 недоступен (код: {result})")

except Exception as e:
    print(f"❌ Ошибка проверки порта: {e}")

print("\n" + "=" * 70)
print("✅ Диагностика Qdrant завершена")
