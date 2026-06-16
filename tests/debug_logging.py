import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def log(msg):
    print(f"[DEBUG] {time.strftime('%H:%M:%S')} - {msg}")


def debug_logging():
    log("Starting logging debug...")

    try:
        log("Importing StructuredLogger...")
        from src.infrastructure.logging.structured_logging import StructuredLogger

        log("Success.")

        log("Initializing StructuredLogger...")
        logger = StructuredLogger("test_logger")
        log("Success.")

        log("Logging a message...")
        logger.info("Test message")
        log("Success.")

    except Exception as e:
        log(f"FAILED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    debug_logging()
