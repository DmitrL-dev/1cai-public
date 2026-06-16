"""ML module - lazy router import to avoid cascading dependency loading."""


def get_router():
    """Lazy import to avoid loading celery/heavy deps at import time."""
    from src.modules.ml.api.routes import router
    return router


__all__ = ["get_router"]
