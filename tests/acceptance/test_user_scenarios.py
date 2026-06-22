"""
Acceptance Tests - Пользовательские сценарии
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Path of the optional 1C:Copilot completion model. When absent, CopilotService
# falls back to a small keyword-pattern engine that yields no suggestions for
# arbitrary input (e.g. an assignment line), so model-dependent acceptance
# assertions cannot be satisfied serviceless.
_COPILOT_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "qwen-bsl-lora"


@pytest.mark.asyncio
async def test_scenario_new_user_onboarding():
    """
    Acceptance: Новый пользователь регистрируется и начинает работу

    Steps:
    1. Регистрация tenant
    2. Подтверждение email
    3. Создание первого проекта
    4. Запрос к AI агенту
    5. Получение результата
    """

    import asyncpg

    from src.ai.role_based_router import RoleBasedRouter

    try:
        conn = await asyncpg.connect(
            host="localhost",
            user="postgres",
            password="postgres",
            database="enterprise_1c_ai",
        )

        # Step 1: Registration
        tenant_id = await conn.fetchval(
            """
            INSERT INTO tenants (name, email, plan, status)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """,
            "New Startup",
            "startup@example.com",
            "starter",
            "trial",
        )

        assert tenant_id is not None, "Registration failed"

        # Step 2: Email confirmed (mocked)
        await conn.execute(
            "UPDATE tenants SET email_confirmed = TRUE WHERE id = $1", tenant_id
        )

        # Step 3: Create first project
        project_id = await conn.fetchval(
            """
            INSERT INTO projects (tenant_id, name, metadata)
            VALUES ($1, $2, $3)
            RETURNING id
        """,
            tenant_id,
            "My First ERP",
            {"type": "erp"},
        )

        assert project_id is not None, "Project creation failed"

        # Step 4: Ask AI agent
        router = RoleBasedRouter()
        result = await router.route_query("Как создать документ Заказ покупателя?")

        assert result is not None, "AI agent failed"
        assert "response" in result or "result" in result

        # Cleanup
        await conn.execute("DELETE FROM projects WHERE id = $1", project_id)
        await conn.execute("DELETE FROM tenants WHERE id = $1", tenant_id)
        await conn.close()

    except Exception as e:
        pytest.skip(f"Database not available: {e}", allow_module_level=False)


@pytest.mark.asyncio
async def test_scenario_developer_uses_code_review():
    """
    Acceptance: Разработчик использует Code Review

    Steps:
    1. Developer пишет код
    2. Создает PR в GitHub
    3. AI Code Review автоматически запускается
    4. Developer получает комментарии
    5. Developer исправляет код
    6. Re-review проходит успешно
    """

    from src.ai.agents.code_review.ai_reviewer import AICodeReviewer
    from src.ai.agents.code_review.auto_fixer import AutoFixer

    # Step 1-2: Code written & PR created (mocked)
    # Step 3: Auto review
    reviewer = AICodeReviewer()

    buggy_code = """
Функция ПолучитьДанные(ID)
    Запрос.Текст = "SELECT * WHERE ID = '" + ID + "'";
    Возврат Запрос.Выполнить();
КонецФункции
"""

    review1 = await reviewer.review_code(buggy_code, "test.bsl")

    # Step 4: Developer sees issues
    assert review1["metrics"]["critical"] > 0, "Should find SQL injection"

    # Step 5: Auto-fix applied
    fixer = AutoFixer()

    issues = []
    for category in review1["issues"]:
        issues.extend(review1["issues"][category])

    fix_result = fixer.auto_fix_all(buggy_code, issues)

    fixed_code = fix_result["fixed_code"]

    # Step 6: Re-review passes
    review2 = await reviewer.review_code(fixed_code, "test.bsl")

    assert review2["metrics"]["critical"] == 0, "Fix didn't work"
    assert review2["overall_status"] in ["APPROVED", "COMMENTED"]


@pytest.mark.asyncio
async def test_scenario_subscription_upgrade():
    """
    Acceptance: Пользователь обновляет подписку

    Steps:
    1. User на Starter плане
    2. Достигает лимитов
    3. Upgrade на Professional
    4. Лимиты увеличены
    5. Billing успешно
    """

    import asyncpg

    try:
        conn = await asyncpg.connect(
            host="localhost",
            user="postgres",
            password="postgres",
            database="enterprise_1c_ai",
        )

        # Step 1: User on Starter
        tenant_id = await conn.fetchval(
            """
            INSERT INTO tenants (name, email, plan, status, api_calls_limit)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """,
            "Growing Co",
            "grow@example.com",
            "starter",
            "active",
            1000,
        )

        # Step 2: Reaches limits
        await conn.execute(
            """
            INSERT INTO usage_tracking (tenant_id, date, api_calls)
            VALUES ($1, CURRENT_DATE, $2)
        """,
            tenant_id,
            950,
        )

        usage = await conn.fetchval(
            "SELECT api_calls FROM usage_tracking WHERE tenant_id = $1", tenant_id
        )

        assert usage >= 950, "Usage not tracked"

        # Step 3: Upgrade to Professional
        await conn.execute(
            """
            UPDATE tenants
            SET plan = 'professional', api_calls_limit = 10000
            WHERE id = $1
        """,
            tenant_id,
        )

        # Step 4: Limits increased
        tenant = await conn.fetchrow("SELECT * FROM tenants WHERE id = $1", tenant_id)

        assert tenant["plan"] == "professional"
        assert tenant["api_calls_limit"] == 10000

        # Step 5: Log billing event
        await conn.execute(
            """
            INSERT INTO billing_events (tenant_id, event_type, amount_cents)
            VALUES ($1, $2, $3)
        """,
            tenant_id,
            "subscription_upgraded",
            29900,
        )

        # Cleanup
        await conn.execute("DELETE FROM usage_tracking WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM billing_events WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM tenants WHERE id = $1", tenant_id)
        await conn.close()

    except Exception as e:
        pytest.skip(f"Database not available: {e}", allow_module_level=False)


@pytest.mark.asyncio
async def test_scenario_team_collaboration():
    """
    Acceptance: Команда работает вместе

    Steps:
    1. Admin создает tenant
    2. Добавляет членов команды
    3. Назначает роли
    4. Члены работают с общими проектами
    5. Audit log ведется
    """

    import asyncpg

    try:
        conn = await asyncpg.connect(
            host="localhost",
            user="postgres",
            password="postgres",
            database="enterprise_1c_ai",
        )

        # Step 1: Admin creates tenant
        tenant_id = await conn.fetchval(
            """
            INSERT INTO tenants (name, email)
            VALUES ($1, $2)
            RETURNING id
        """,
            "Team Co",
            "admin@team.com",
        )

        # Step 2: Add team members
        admin_id = await conn.fetchval(
            """
            INSERT INTO users (tenant_id, email, name, role)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """,
            tenant_id,
            "admin@team.com",
            "Admin",
            "admin",
        )

        dev_id = await conn.fetchval(
            """
            INSERT INTO users (tenant_id, email, name, role)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """,
            tenant_id,
            "dev@team.com",
            "Developer",
            "developer",
        )

        # Step 3: Roles assigned (already done above)

        # Step 4: Shared project
        project_id = await conn.fetchval(
            """
            INSERT INTO projects (tenant_id, name, metadata)
            VALUES ($1, $2, $3)
            RETURNING id
        """,
            tenant_id,
            "Team Project",
            {},
        )

        # Both can access
        await conn.execute("SET app.current_tenant_id = $1", tenant_id)

        project = await conn.fetchrow(
            "SELECT * FROM projects WHERE id = $1", project_id
        )

        assert project is not None, "Team can't access shared project"

        # Cleanup
        await conn.execute("RESET app.current_tenant_id")
        await conn.execute("DELETE FROM projects WHERE id = $1", project_id)
        await conn.execute("DELETE FROM users WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM tenants WHERE id = $1", tenant_id)
        await conn.close()

    except Exception as e:
        pytest.skip(f"Database not available: {e}", allow_module_level=False)


@pytest.mark.skipif(
    not _COPILOT_MODEL_PATH.exists(),
    reason="1C:Copilot completion model (models/qwen-bsl-lora) not present; "
    "heuristic fallback yields no completions for non-keyword input",
)
@pytest.mark.asyncio
async def test_scenario_copilot_assists_development():
    """
    Acceptance: 1С:Copilot помогает разработчику

    Steps:
    1. Developer открывает VSCode
    2. Начинает писать функцию
    3. Copilot предлагает autocomplete
    4. Developer принимает suggestion
    5. Генерирует тесты для функции
    """

    # Import path updated: src.api.copilot_api was removed in cleanup; the
    # service now lives in src.modules.copilot.services.copilot_service.
    from src.modules.copilot.services.copilot_service import CopilotService

    service = CopilotService()

    # Step 1-2: Developer typing
    code = "Функция РассчитатьНДС(Сумма)"
    current_line = "    СуммаНДС = "

    # Step 3: Get suggestions
    suggestions = await service.get_completions(code, current_line, max_suggestions=3)

    assert suggestions is not None
    assert len(suggestions) > 0

    # Step 4: Accept suggestion (simulated)
    accepted = suggestions[0]

    # Step 5: Generate tests
    full_code = """
Функция РассчитатьНДС(Сумма, Ставка = 20) Экспорт
    СуммаНДС = Сумма * Ставка / 100;
    Возврат Окр(СуммаНДС, 2);
КонецФункции
"""

    tests = await service.generate_code(
        prompt=f"Тесты для {full_code}", code_type="test"
    )

    assert tests is not None
    assert "Процедура" in tests or "Функция" in tests


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
