import re
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest

from src.db.marketplace_repository import MarketplaceRepository


class _MockAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _MockPool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _MockAcquire(self._conn)


class _MockConn:
    def __init__(self, record):
        self._record = record

    async def fetchrow(self, *args, **kwargs):
        return self._record


class _FakeS3Client:
    def __init__(self):
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)


@pytest.mark.asyncio
async def test_store_artifact_uploads_and_updates_db():
    plugin_id = "plugin-123"
    conn = _MockConn(record={"plugin_id": plugin_id})
    pool = _MockPool(conn=conn)

    repo = MarketplaceRepository(
        pool=pool,
        cache=None,
        storage_config={
            "bucket": "bucket-name",
            "access_key": "fake-access",
            "secret_key": "fake-secret",
        },
    )

    fake_client = _FakeS3Client()
    repo._s3_client = fake_client  # type: ignore[assignment]
    repo._get_s3_client = lambda: fake_client  # type: ignore[assignment]
    repo._ensure_bucket = AsyncMock()
    repo._invalidate_caches = AsyncMock()
    repo._record_to_plugin = Mock(return_value={"id": plugin_id})  # type: ignore[assignment]

    result = await repo.store_artifact(
        plugin_id=plugin_id,
        data=b"zip-bytes",
        filename="artifact 1.0?.zip",
        content_type="application/zip",
    )

    assert result == {"id": plugin_id}
    repo._ensure_bucket.assert_awaited_once()
    repo._invalidate_caches.assert_awaited_once_with(plugin_id)
    repo._record_to_plugin.assert_called_once()

    assert fake_client.calls, "S3 client should be invoked"
    put_kwargs = fake_client.calls[0]
    assert put_kwargs["Bucket"] == "bucket-name"
    assert put_kwargs["Body"] == b"zip-bytes"
    assert put_kwargs["ContentType"] == "application/zip"
    assert put_kwargs["Key"].startswith(f"marketplace/{plugin_id}/")
    assert " " not in put_kwargs["Key"]


@pytest.mark.asyncio
async def test_store_artifact_without_storage_configuration_raises():
    repo = MarketplaceRepository(
        pool=_MockPool(_MockConn({})), cache=None, storage_config={}
    )

    with pytest.raises(RuntimeError):
        await repo.store_artifact("plugin-1", b"data", "file.zip")


def test_build_object_key_sanitizes_filename():
    repo = MarketplaceRepository(
        pool=_MockPool(_MockConn({})),
        cache=None,
        storage_config={
            "bucket": "bucket-name",
            "access_key": "fake-access",
            "secret_key": "fake-secret",
        },
    )

    key = repo._build_object_key("plugin-1", "../evil name?.zip")
    assert key.startswith("marketplace/plugin-1/")
    assert key.endswith("evil-name-.zip")
    assert re.fullmatch(r"[A-Za-z0-9._/-]+", key)


class DummyS3Client:
    def __init__(self, url: str) -> None:
        self.url = url

    def generate_presigned_url(self, *_args, **_kwargs):
        return self.url


def _create_repo(storage: Dict[str, str]) -> MarketplaceRepository:
    defaults = {
        "access_key": "key",
        "secret_key": "secret",
    }
    defaults.update(storage)
    return MarketplaceRepository(
        pool=_MockPool(_MockConn({})), cache=None, storage_config=defaults
    )


@pytest.mark.asyncio()
async def test_build_download_payload_fallback() -> None:
    repo = _create_repo({})
    plugin = {
        "plugin_id": "plugin-demo",
        "download_url": "https://cdn.example.com/plugin-demo.zip",
        "artifact_path": None,
    }

    payload = await repo.build_download_payload(plugin)

    assert payload["download_url"] == "https://cdn.example.com/plugin-demo.zip"
    assert payload["status"] == "ready"


@pytest.mark.asyncio()
async def test_build_download_payload_presigned() -> None:
    repo = _create_repo({"bucket": "test", "region": "us-test-1"})
    repo._s3_client = DummyS3Client("https://s3.example.com/presigned")  # type: ignore[assignment]

    plugin: Dict[str, Any] = {
        "plugin_id": "plugin-demo",
        "download_url": "https://legacy.example.com/plugin-demo.zip",
        "artifact_path": "artifacts/plugin-demo.zip",
    }

    payload = await repo.build_download_payload(plugin)

    assert payload["download_url"] == "https://s3.example.com/presigned"
    assert "manifest.json" in payload["files"]
