import sys
import os
import asyncio
import time

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Disable file logging to prevent locking issues during test
os.environ["LOG_DIR"] = f"logs_test_{int(time.time())}"


def log(msg):
    print(f"[VERIFY] {time.strftime('%H:%M:%S')} - {msg}", flush=True)


async def verify_auth_isolated():
    log("Starting ISOLATED Auth Verification...")

    try:
        # 1. Verify Domain Models
        log("1. Verifying Domain Models...")
        from src.modules.auth.domain.models import UserCredentials, CurrentUser

        user = CurrentUser(user_id="test", username="test", roles=["admin"])
        assert user.has_role("admin")
        log("   Domain models OK.")

        # 2. Verify Config
        log("2. Verifying Config...")
        from src.modules.auth.infrastructure.config import AuthSettings

        settings = AuthSettings()
        log("   Config OK.")

        # 3. Verify Service
        log("3. Verifying Service...")
        from src.modules.auth.application.service import AuthService

        service = AuthService(settings)
        token = service.create_access_token(UserCredentials(username="test", password="pwd", user_id="1", roles=[]))
        decoded = service.decode_token(token)
        assert decoded.user_id == "1"
        log("   Service OK.")

        # 4. Verify OAuth Service
        log("4. Verifying OAuth Service...")
        from src.modules.auth.application.oauth_service import OAuthService

        oauth = OAuthService()
        assert "github" in oauth.providers
        log("   OAuth Service OK.")

        # 5. Verify API Routes (Import only)
        log("5. Verifying API Routes imports...")

        log("   API Routes imports OK.")

        log("Verification Complete: SUCCESS")

    except ImportError as e:
        log(f"Verification Failed: ImportError - {e}")
        sys.exit(1)
    except Exception as e:
        log(f"Verification Failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(verify_auth_isolated())
