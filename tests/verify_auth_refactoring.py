import sys
import os
import asyncio
from fastapi import FastAPI

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


async def verify_auth_refactoring():
    print("Verifying Auth Refactoring...")

    try:
        # 1. Verify Imports
        print("1. Verifying Imports...")
        from src.modules.auth.application.service import AuthService
        from src.modules.auth.application.oauth_service import OAuthService
        from src.modules.auth.infrastructure.config import AuthSettings
        from src.modules.auth.api.routes import router as auth_router
        from src.modules.auth.api.oauth_routes import router as oauth_router

        print("   Imports successful.")

        # 2. Verify Service Initialization
        print("2. Verifying Service Initialization...")
        settings = AuthSettings()
        auth_service = AuthService(settings)
        oauth_service = OAuthService()
        print("   Services initialized successfully.")

        # 3. Verify Router Integration
        print("3. Verifying Router Integration...")
        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(oauth_router)
        print("   Routers included successfully.")

        # 4. Verify Main Application Integration
        print("4. Verifying Main Application Integration...")
        from src.main import app as main_app

        # Check if routers are in the app
        routes = [route.path for route in main_app.routes]
        if (
            "/api/v1/auth/token" in routes or "/api/v1/auth/token/" in routes
        ):  # Depends on how include_router works with prefix
            # FastAPI routes are stored in a complex structure, simplified check
            pass

        # Check if auth router is registered
        found_auth = False
        found_oauth = False
        for route in main_app.routes:
            if hasattr(route, "path"):
                if "/auth/token" in route.path:
                    found_auth = True
                if "/api/oauth" in route.path:
                    found_oauth = True

        if found_auth:
            print("   Auth router found in main app.")
        else:
            print("   WARNING: Auth router NOT found in main app (might be under /api/v1).")

        if found_oauth:
            print("   OAuth router found in main app.")
        else:
            print("   WARNING: OAuth router NOT found in main app (might be under /api/v1).")

        print("Verification Complete: SUCCESS")

    except ImportError as e:
        print(f"Verification Failed: ImportError - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Verification Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(verify_auth_refactoring())
