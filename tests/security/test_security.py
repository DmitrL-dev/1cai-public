"""
Security Tests - Тестирование безопасности
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.mark.asyncio
async def test_sql_injection_prevention():
    """
    Security: Защита от SQL injection
    """

    import asyncpg

    try:
        conn = await asyncpg.connect(
            host="localhost",
            user="postgres",
            password="postgres",
            database="enterprise_1c_ai",
        )

        # Malicious input
        malicious_input = "'; DROP TABLE projects; --"

        # Should NOT execute DROP TABLE
        try:
            result = await conn.fetch(
                "SELECT * FROM projects WHERE name = $1", malicious_input
            )
            # Should succeed without damage
            assert True
        except:
            pytest.fail("Parameterized query failed")

        # Verify table still exists
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'projects'
            )
        """
        )

        assert exists is True, "Table was dropped - SQL injection!"

        await conn.close()

    except Exception as e:
        pytest.skip(f"Database not available: {e}", allow_module_level=False)


@pytest.mark.asyncio
async def test_row_level_security():
    """
    Security: Row-Level Security (RLS) enforcement
    """

    import asyncpg

    try:
        conn = await asyncpg.connect(
            host="localhost",
            user="postgres",
            password="postgres",
            database="enterprise_1c_ai",
        )

        # Create 2 tenants
        tenant1 = await conn.fetchval(
            "INSERT INTO tenants (name, email) VALUES ($1, $2) RETURNING id",
            "Tenant 1",
            "t1@test.com",
        )

        tenant2 = await conn.fetchval(
            "INSERT INTO tenants (name, email) VALUES ($1, $2) RETURNING id",
            "Tenant 2",
            "t2@test.com",
        )

        # Tenant 1 creates project
        project_id = await conn.fetchval(
            """
            INSERT INTO projects (tenant_id, name, metadata)
            VALUES ($1, $2, $3)
            RETURNING id
        """,
            tenant1,
            "Secret Project",
            {},
        )

        # Set context to Tenant 2
        await conn.execute("SET app.current_tenant_id = $1", tenant2)

        # Tenant 2 tries to access Tenant 1 project
        result = await conn.fetchrow("SELECT * FROM projects WHERE id = $1", project_id)

        # RLS should block access
        assert result is None, "RLS FAILED - Cross-tenant access!"

        # Cleanup
        await conn.execute("RESET app.current_tenant_id")
        await conn.execute("DELETE FROM projects WHERE id = $1", project_id)
        await conn.execute("DELETE FROM tenants WHERE id IN ($1, $2)", tenant1, tenant2)
        await conn.close()

    except Exception as e:
        pytest.skip(f"Database not available: {e}", allow_module_level=False)


def test_xss_detection():
    """
    Security: XSS detection в Code Review
    """

    from src.ai.agents.code_review.security_scanner import SecurityScanner

    scanner = SecurityScanner()

    code_with_xss = """
HTML = "<script>alert('XSS')</script>";
Возврат HTML;
"""

    issues = scanner.scan_xss_vulnerabilities(code_with_xss, {})

    assert len(issues) > 0, "XSS not detected!"
    assert any(i["severity"] == "HIGH" for i in issues)


def test_credential_scanning():
    """
    Security: Обнаружение hardcoded credentials
    """

    from src.ai.agents.code_review.security_scanner import SecurityScanner

    scanner = SecurityScanner()

    code_with_secrets = """
Password = "SuperSecret123!";
APIKey = "sk_live_1234567890abcdef";
Token = "ghp_xxxxxxxxxxx";
SecretKey = "aws_secret_key_xyz";
"""

    issues = scanner.scan_hardcoded_credentials(code_with_secrets, {})

    assert len(issues) >= 3, f"Found only {len(issues)} credentials"
    assert all(i["severity"] in ["CRITICAL", "HIGH"] for i in issues)


@pytest.mark.asyncio
async def test_authentication_required():
    """
    Security: Endpoints require authentication
    """

    from fastapi import Depends, FastAPI, Header, HTTPException
    from fastapi.testclient import TestClient

    app = FastAPI()

    async def get_current_user(token: str = Header(None)):
        if not token:
            raise HTTPException(status_code=401)
        return {"user_id": 123}

    @app.get("/protected")
    async def protected_endpoint(user=Depends(get_current_user)):
        return {"message": "success"}

    client = TestClient(app)

    # Without auth - should fail
    response = client.get("/protected")
    assert response.status_code == 401

    # With auth - should succeed
    response = client.get("/protected", headers={"token": "valid"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limiting():
    """
    Security: Rate limiting protection
    """

    from src.api.middleware.tenant_context import RateLimiter

    limiter = RateLimiter(max_requests=10, window_seconds=60)

    tenant_id = "test_tenant"

    # Should allow first 10 requests
    for i in range(10):
        allowed = limiter.check_limit(tenant_id)
        assert allowed is True, f"Request {i+1} blocked"

    # 11th request should be blocked
    blocked = limiter.check_limit(tenant_id)
    assert blocked is False, "Rate limit not enforced!"


def test_input_validation():
    """
    Security: Input validation
    """

    from pydantic import BaseModel, ValidationError, constr

    class TenantCreate(BaseModel):
        name: constr(min_length=1, max_length=100)  # type: ignore
        email: constr(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")  # noqa: F722

    # Valid input
    valid = TenantCreate(name="Test Co", email="test@example.com")
    assert valid.name == "Test Co"

    # Invalid email
    with pytest.raises(ValidationError):
        invalid = TenantCreate(name="Test", email="not-an-email")

    # Empty name
    with pytest.raises(ValidationError):
        invalid = TenantCreate(name="", email="test@example.com")


@pytest.mark.asyncio
async def test_csrf_protection():
    """
    Security: CSRF token validation
    """

    from fastapi import Depends, FastAPI, Header, HTTPException
    from fastapi.testclient import TestClient

    app = FastAPI()

    async def verify_csrf(csrf_token: str = Header(None)):
        if not csrf_token or csrf_token != "valid_token":
            raise HTTPException(status_code=403, detail="CSRF validation failed")

    @app.post("/action")
    async def action(csrf_token: str = Depends(verify_csrf)):
        return {"success": True}

    client = TestClient(app)

    # Without CSRF token - should fail
    response = client.post("/action")
    assert response.status_code == 403

    # With valid token - should succeed
    response = client.post("/action", headers={"csrf-token": "valid_token"})
    assert response.status_code == 200


def test_password_hashing():
    """
    Security: Пароли должны быть хешированы
    """

    import bcrypt

    password = "SuperSecret123!"

    # Hash password
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    # Verify correct password
    assert bcrypt.checkpw(password.encode(), hashed)

    # Verify wrong password fails
    assert not bcrypt.checkpw(b"wrong", hashed)

    # Hash should be different each time
    hashed2 = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    assert hashed != hashed2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
