import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def log(msg):
    print(f"[DEBUG] {time.strftime('%H:%M:%S')} - {msg}")


def debug_imports():
    log("Starting import debug...")

    try:
        log("Importing src.modules.auth.domain.models...")

        log("Success.")

        log("Importing src.modules.auth.infrastructure.config...")

        log("Success.")

        log("Importing src.modules.auth.application.service...")

        log("Success.")

        log("Importing src.modules.auth.application.oauth_service...")

        log("Success.")

        log("Importing src.modules.auth.application.roles...")

        log("Success.")

        log("Importing src.modules.auth.api.dependencies...")

        log("Success.")

        log("Importing src.modules.auth.api.routes...")

        log("Success.")

        log("Importing src.modules.auth.api.oauth_routes...")

        log("Success.")

        log("Importing src.main...")

        log("Success.")

    except Exception as e:
        log(f"FAILED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    debug_imports()
