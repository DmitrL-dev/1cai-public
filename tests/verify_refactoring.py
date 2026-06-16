import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

print("Verifying imports...")

try:
    print("1. Importing StructuredLogger from new location...")
    from src.infrastructure.logging.structured_logging import StructuredLogger

    logger = StructuredLogger("test")
    print("✅ StructuredLogger imported successfully")

    print("2. Importing CopilotService from new location...")
    from src.modules.copilot.application.service import CopilotService

    service = CopilotService()
    print("✅ CopilotService imported and initialized successfully")

    print("3. Importing Copilot Router...")

    print("✅ Copilot Router imported successfully")

    print("4. Importing main app...")

    print("✅ Main app imported successfully")

    print("\n🎉 All verifications passed!")

except Exception as e:
    print(f"\n❌ Verification failed: {e}")
    import traceback

    traceback.print_exc()
