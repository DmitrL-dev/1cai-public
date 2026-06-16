import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

async def test_postgres_async():
    """Минимальный тест PostgreSQL в async контексте"""
    print("\n🔍 Тест PostgreSQL в async контексте")
    print("=" * 70)
    
    try:
        from src.db.postgres_saver import PostgreSQLSaver
        
        print("\n1️⃣ Создание PostgreSQLSaver...")
        saver = PostgreSQLSaver(
            host="localhost",
            port=5432,
            database="knowledge_base",
            user="admin",
            password="changeme"
        )
        print("✅ PostgreSQLSaver создан")
        
        print("\n2️⃣ Подключение через asyncio.to_thread...")
        connected = await asyncio.to_thread(saver.connect)
        print(f"   Результат connect(): {connected}")
        
        if not connected:
            print("❌ Подключение провалилось")
            return False
        
        print("✅ Подключение успешно")
        
        print("\n3️⃣ Проверка is_connected...")
        is_conn = await asyncio.to_thread(saver.is_connected)
        print(f"   Результат is_connected(): {is_conn}")
        
        if not is_conn:
            print("❌ is_connected вернул False")
            await asyncio.to_thread(saver.disconnect)
            return False
        
        print("✅ is_connected = True")
        
        print("\n4️⃣ Получение статистики...")
        try:
            stats = await asyncio.to_thread(saver.get_statistics)
            print(f"✅ Статистика: {stats}")
        except Exception as e:
            print(f"⚠️ Ошибка статистики: {e}")
        
        print("\n5️⃣ Отключение...")
        await asyncio.to_thread(saver.disconnect)
        print("✅ Отключение успешно")
        
        print("\n" + "=" * 70)
        print("✅ Все тесты прошли успешно!")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_postgres_async())
    sys.exit(0 if result else 1)
