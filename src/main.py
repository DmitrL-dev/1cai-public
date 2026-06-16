
"""
Main FastAPI Application
1C AI Stack - AI-Powered Development Platform

Refactored: модульная структура в src/app/
"""

import os
import sys

# Python version check
if os.getenv("IGNORE_PY_VERSION_CHECK") != "1" and sys.version_info[:2] != (3, 11):
    raise RuntimeError(f"Python 3.11.x is required to run 1C AI Stack (detected {sys.version.split()[0]}).")

from src.app.factory import create_app

# Create application
app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
