
"""
Admin Dashboard API (Legacy)

DEPRECATED: This module has been refactored into Clean Architecture.
Use src.modules.admin_dashboard instead.
"""
from src.modules.admin_dashboard.api.routes import router

__all__ = ["router"]
