import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

print("🔍 Диагностика PostgreSQL подключения\n")
print("=" * 70)

# Тест 1: Импорт модулей
print("\n1️⃣ Проверка импорта модулей...")
try:
    import psycopg2

    print(f"✅ psycopg2 версия: {psycopg2.__version__}")
    print(f"✅ psycopg2.pool доступен")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)

# Тест 2: Прямое подключение (без пула)
print("\n2️⃣ Тест прямого подключения...")
try:
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="knowledge_base",
        user="admin",
        password="changeme",
    )
    print("✅ Прямое подключение успешно")

    # Выполнение тестового запроса
    with conn.cursor() as cur:
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        print(f"✅ PostgreSQL версия: {version[:50]}...")

        cur.execute("SELECT current_database()")
        db = cur.fetchone()[0]
        print(f"✅ Текущая БД: {db}")

    conn.close()
    print("✅ Соединение закрыто")

except Exception as e:
    print(f"❌ Ошибка прямого подключения: {e}")
    import traceback

    traceback.print_exc()

# Тест 3: Подключение через пул
print("\n3️⃣ Тест подключения через ThreadedConnectionPool...")
try:
    connection_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=5,
        host="localhost",
        port=5432,
        database="knowledge_base",
        user="admin",
        password="changeme",
    )
    print("✅ Пул подключений создан")

    # Получение соединения из пула
    conn = connection_pool.getconn()
    print("✅ Соединение получено из пула")

    # Тестовый запрос
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        result = cur.fetchone()[0]
        print(f"✅ Тестовый запрос выполнен: {result}")

    # Возврат соединения в пул
    connection_pool.putconn(conn)
    print("✅ Соединение возвращено в пул")

    # Закрытие пула
    connection_pool.closeall()
    print("✅ Пул подключений закрыт")

except Exception as e:
    print(f"❌ Ошибка пула подключений: {e}")
    import traceback

    traceback.print_exc()

# Тест 4: PostgreSQLSaver
print("\n4️⃣ Тест PostgreSQLSaver...")
try:
    from src.db.postgres_saver import PostgreSQLSaver

    saver = PostgreSQLSaver(
        host="localhost",
        port=5432,
        database="knowledge_base",
        user="admin",
        password="changeme",
    )
    print("✅ PostgreSQLSaver инициализирован")

    if saver.connect():
        print("✅ PostgreSQLSaver.connect() успешно")

        if saver.is_connected():
            print("✅ PostgreSQLSaver.is_connected() = True")
        else:
            print("❌ PostgreSQLSaver.is_connected() = False")

        saver.disconnect()
        print("✅ PostgreSQLSaver.disconnect() успешно")
    else:
        print("❌ PostgreSQLSaver.connect() провалился")

except Exception as e:
    print(f"❌ Ошибка PostgreSQLSaver: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 70)
print("✅ Диагностика PostgreSQL завершена")
