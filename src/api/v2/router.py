"""
API v2 Main Router

Aggregates all v2 endpoints.
"""

from fastapi import APIRouter

from src.api.v2 import revolutionary

router = APIRouter()

# Include v2 sub-routers
router.include_router(revolutionary.router)
