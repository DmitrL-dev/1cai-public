from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_start_rentgen_sets_safe_dev_profile_and_real_login_hint():
    script = (ROOT / "scripts" / "start_rentgen.ps1").read_text(encoding="utf-8")

    assert '$env:ENVIRONMENT = "development"' in script
    assert "$env:JWT_SECRET =" in script
    assert "$env:JWT_SECRET_KEY = $env:JWT_SECRET" in script
    assert "Start-Process -FilePath $py" in script
    assert '"uvicorn", "src.main:app"' in script
    assert 'Start-Process -FilePath "npm.cmd"' in script
    assert "--strictPort" in script
    assert "FindPortalPort 3000 3010" in script
    assert "FreePort 3001" in script
    assert "Dev login" in script
    assert "real demo JWT" in script


def test_portal_dev_mode_uses_real_demo_credentials_not_fake_token():
    login_page = (ROOT / "portal" / "src" / "routes" / "login.tsx").read_text(
        encoding="utf-8"
    )

    assert 'authApi.login("admin", "admin123")' in login_page
    assert "authApi.me(data.access_token)" in login_page
    assert "setAuth(data.access_token" in login_page
    assert "dev-token" not in login_page
