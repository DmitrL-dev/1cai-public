
"""
Pytest Configuration
Общие fixtures и настройки для всех тестов
"""

import asyncio
import logging
import os
from pathlib import Path

import pytest

try:
    from alembic import command  # type: ignore
    from alembic.config import Config  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    command = None  # type: ignore
    Config = None  # type: ignore

try:
    import asyncpg
except ModuleNotFoundError:  # noqa: F401
    asyncpg = None

logger = logging.getLogger(__name__)


# Add src to path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


_migrations_applied = False


def _apply_migrations(database_url: str) -> None:
    global _migrations_applied
    if _migrations_applied:
        return

    if Config is None or command is None:
        logger.warning("Alembic is not installed; skipping migrations for tests")
        _migrations_applied = True
        return

    config_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    if not config_path.exists():
        logger.warning("alembic.ini not found; skipping migrations for tests")
        return

    alembic_cfg = Config(str(config_path))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    logger.info("Applying test migrations via Alembic")
    command.upgrade(alembic_cfg, "head")
    _migrations_applied = True


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_pool():
    """Create database connection pool for integration tests.

    Requires TEST_DATABASE_URL to be set and asyncpg installed.
    """

    if asyncpg is None:
        yield None
        return

    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        yield None
        return

    try:
        pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skipping DB-backed tests: %s", exc)
        yield None
        return

    os.environ.setdefault("DATABASE_URL", database_url)

    _apply_migrations(database_url)

    try:
        from src.database import create_pool

        await create_pool()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to initialise global DB pool: %s", exc)

    try:
        yield pool
    finally:
        await pool.close()
        try:
            from src.database import close_pool

            await close_pool()
        except Exception:
            pass


@pytest.fixture(scope="function")
async def db_conn(db_pool):
    """Get database connection for single test"""
    if db_pool:
        async with db_pool.acquire() as conn:
            # Start transaction
            async with conn.transaction():
                yield conn
                # Rollback after test
    else:
        yield None


@pytest.fixture
def sample_bsl_code():
    """Sample BSL code for testing"""
    return """
// Рассчитывает сумму заказа
//
// Параметры:
//   Заказ - ДокументСсылка.ЗаказПокупателя
//
// Возвращаемое значение:
//   Число - Сумма заказа
//
Функция РассчитатьСуммуЗаказа(Заказ) Экспорт

    Попытка
        Запрос = Новый Запрос;
        Запрос.Текст = "
        |ВЫБРАТЬ
        |    СУММА(Сумма) КАК Сумма
        |ИЗ
        |    Документ.ЗаказПокупателя.Товары
        |ГДЕ
        |    Ссылка = &Заказ";

        Запрос.УстановитьПараметр("Заказ", Заказ);

        Результат = Запрос.Выполнить();
        Выборка = Результат.Выбрать();

        Если Выборка.Следующий() Тогда
            Возврат Выборка.Сумма;
        Иначе
            Возврат 0;
        КонецЕсли;

    Исключение
        ЗаписьЖурналаРегистрации("Ошибка", УровеньЖурналаРегистрации.Ошибка);
        Возврат 0;
    КонецПопытки;

КонецФункции
"""


@pytest.fixture
def vulnerable_bsl_code():
    """Vulnerable BSL code for security testing"""
    return """
Функция ПолучитьДанныеПользователя(ИДПользователя)
    // SQL Injection vulnerability
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ГДЕ ID = '" + ИДПользователя + "'";

    // Hardcoded credentials
    Пароль = "admin123";
    APIKey = "sk_live_1234567890";

    Возврат Запрос.Выполнить();
КонецФункции
"""


@pytest.fixture
def mock_tenant_data():
    """Mock tenant data"""
    return {
        "id": "test-tenant-123",
        "name": "Test Company",
        "email": "test@example.com",
        "plan": "professional",
        "status": "active",
        "api_calls_limit": 10000,
        "storage_limit_gb": 100,
    }


@pytest.fixture
def mock_github_pr():
    """Mock GitHub PR data"""
    return {
        "number": 42,
        "repository": "test/repo",
        "title": "Add new feature",
        "author": "developer",
        "files": [
            {
                "filename": "src/test.bsl",
                "status": "added",
                "additions": 50,
                "deletions": 0,
                "patch": "+ Функция НоваяФункция()\n+ КонецФункции",
            }
        ],
    }


@pytest.fixture
def mock_stripe_event():
    """Mock Stripe webhook event"""
    return {
        "id": "evt_test_123",
        "type": "invoice.payment_succeeded",
        "created": 1234567890,
        "data": {
            "object": {
                "id": "in_test_123",
                "customer": "cus_test_123",
                "amount_paid": 29900,
                "currency": "usd",
                "status": "paid",
            }
        },
    }


@pytest.fixture
def sample_configuration_data():
    """Configuration payload used in Neo4j tests."""
    return {
        "name": "TEST",
        "full_name": "TEST CONFIGURATION",
        "version": "1.0.0",
        "metadata": {"owner": "qa"},
    }


@pytest.fixture
def sample_module_data():
    """Module payload used in persistence tests."""
    return {
        "full_name": "TEST.Module",
        "name": "Module",
        "module_type": "common",
        "line_count": 42,
        "code_hash": "abc123",
        "description": "Test module",
        "object_name": "TestObject",
        "object_type": "Catalog",
        "code": "Функция Test() \n    Возврат 1;\nКонецФункции",
        "functions": [
            {
                "name": "Test",
                "type": "Function",
                "code": "Возврат 1;",
                "exported": True,
                "params": [],
                "return_type": "Number",
                "start_line": 1,
                "end_line": 2,
            }
        ],
    }


@pytest.fixture
def mock_embedding():
    """Simple embedding vector used in Qdrant tests."""
    return [0.1] * 3


# ----- Environment preparation -------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _ensure_required_env_vars():
    """Задает обязательные переменные окружения для Settings/Pydantic."""
    defaults = {
        "OPENAI_API_KEY": "test-key",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_KEY": "test-supabase-key",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
    }

    for key, value in defaults.items():
        os.environ.setdefault(key, value)

    yield


# Markers
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "system: marks tests as system/e2e tests")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")
    config.addinivalue_line("markers", "security: marks tests as security tests")


@pytest.fixture
def sample_image_path(tmp_path):
    """Create a dummy image file for testing"""
    p = tmp_path / "test_image.png"
    # Create a minimal valid PNG file
    # 1x1 pixel black image
    content = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    p.write_bytes(content)
    return str(p)
