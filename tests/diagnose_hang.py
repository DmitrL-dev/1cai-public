import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def log(msg):
    print(f"[DIAGNOSE] {time.strftime('%H:%M:%S')} - {msg}", flush=True)


def diagnose():
    log("Starting diagnosis...")

    # 1. Test basic imports
    try:
        log("Importing os...")

        log("Importing sys...")

        log("Importing time...")
        import time

        log("Importing json...")

        log("Basic imports success.")
    except Exception as e:
        log(f"Basic imports FAILED: {e}")
        return

    # 2. Test Pydantic
    try:
        log("Importing pydantic...")
        import pydantic

        log(f"Pydantic version: {pydantic.VERSION}")

        log("Pydantic imports success.")
    except Exception as e:
        log(f"Pydantic imports FAILED: {e}")
        return

    # 3. Test python-json-logger
    try:
        log("Importing pythonjsonlogger...")

        log("pythonjsonlogger imports success.")
    except Exception as e:
        log(f"pythonjsonlogger imports FAILED: {e}")
        return

    # 4. Test StructuredLogger Import ONLY
    try:
        log("Importing src.infrastructure.logging.structured_logging (module only)...")

        log("Module import success.")
    except Exception as e:
        log(f"StructuredLogger module import FAILED: {e}")
        return

    # 5. Test StructuredLogger Class Import
    try:
        log("Importing StructuredLogger class...")
        from src.infrastructure.logging.structured_logging import StructuredLogger

        log("Class import success.")
    except Exception as e:
        log(f"StructuredLogger class import FAILED: {e}")
        return

    # 6. Test StructuredLogger Instantiation
    try:
        log("Instantiating StructuredLogger...")
        # We use a unique name to avoid conflicts
        logger = StructuredLogger(f"diagnose_logger_{int(time.time())}")
        log("Instantiation success.")

        log("Logging test message...")
        logger.info("Diagnosis test message")
        log("Logging success.")
    except Exception as e:
        log(f"StructuredLogger instantiation/usage FAILED: {e}")
        return

    log("Diagnosis COMPLETE: SUCCESS")


if __name__ == "__main__":
    diagnose()
