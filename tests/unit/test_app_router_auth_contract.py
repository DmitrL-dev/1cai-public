"""Router registration auth defaults."""

from src.app.routers import _dependencies_for_module_router


def test_module_routers_require_auth_by_default() -> None:
    assert _dependencies_for_module_router("gateway")
    assert _dependencies_for_module_router("knowledge_base")
    assert _dependencies_for_module_router("marketplace")


def test_auth_and_oauth_routers_keep_public_entrypoints() -> None:
    assert _dependencies_for_module_router("auth") == []
    assert _dependencies_for_module_router("oauth") == []
