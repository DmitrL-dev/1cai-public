import json
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import (
    TOOLS,
    handle_offline_bundle_manifest,
    handle_offline_bundle_verify,
)
from src.api.productization_api import router
from src.services.offline_bundle import (
    build_offline_bundle_archive,
    build_offline_bundle_manifest,
    verify_offline_bundle_archive,
    verify_offline_bundle_manifest,
)


def test_offline_bundle_manifest_signs_verifies_and_detects_tamper(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "policy.json").write_text('{"ok": true}\n', encoding="utf-8")
    manifest_path = tmp_path / "data" / "offline_bundles" / "latest_manifest.json"

    manifest = build_offline_bundle_manifest(
        profile="production",
        include_paths=["docs/guide.md", "policy.json"],
        include_defaults=False,
        output_path=manifest_path,
        signing_key="secret",
        root=tmp_path,
    )
    verified = verify_offline_bundle_manifest(
        manifest_path=manifest_path, signing_key="secret"
    )

    (tmp_path / "policy.json").write_text('{"ok": false}\n', encoding="utf-8")
    tampered = verify_offline_bundle_manifest(
        manifest_path=manifest_path, signing_key="secret"
    )

    assert manifest["signature"]["signed"] is True
    assert manifest["summary"]["files"] == 2
    assert manifest["summary"]["missing"] == 0
    assert verified["status"] == "pass"
    assert tampered["status"] == "fail"
    assert any(
        item["code"] == "bundle-file-hash-mismatch" for item in tampered["findings"]
    )


def test_offline_bundle_rejects_paths_outside_root(tmp_path):
    try:
        build_offline_bundle_manifest(
            include_paths=["../outside.txt"],
            include_defaults=False,
            root=tmp_path,
            write=False,
        )
    except ValueError as exc:
        assert "escapes repository root" in str(exc)
    else:
        raise AssertionError("Expected escaping path to be rejected")


def test_offline_bundle_archive_verifies_and_detects_payload_tamper(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "policy.json").write_text('{"ok": true}\n', encoding="utf-8")
    archive_path = tmp_path / "data" / "offline_bundles" / "bundle.zip"

    archive = build_offline_bundle_archive(
        profile="production",
        include_paths=["docs/guide.md", "policy.json"],
        include_defaults=False,
        output_path=archive_path,
        signing_key="secret",
        root=tmp_path,
    )
    verified = verify_offline_bundle_archive(
        archive_path=archive_path, signing_key="secret"
    )
    with zipfile.ZipFile(archive_path, "r") as built:
        names = set(built.namelist())
        passport = json.loads(built.read("DELIVERY_PASSPORT.json").decode("utf-8"))

    tampered_path = tmp_path / "data" / "offline_bundles" / "tampered.zip"
    with zipfile.ZipFile(archive_path, "r") as source, zipfile.ZipFile(
        tampered_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as target:
        for name in source.namelist():
            if name == "payload/policy.json":
                target.writestr(name, b'{"ok": false}\n')
            else:
                target.writestr(name, source.read(name))
    tampered = verify_offline_bundle_archive(
        archive_path=tampered_path, signing_key="secret"
    )

    assert archive["status"] == "created"
    assert "DELIVERY_PASSPORT.json" in names
    assert "DELIVERY_PASSPORT.md" in names
    assert "VERIFY.txt" in names
    assert (
        archive["delivery_passport"]["package"]["manifest_sha256"]
        == archive["manifest"]["manifest_sha256"]
    )
    assert passport["decision"]["status"] in {"ready", "warn", "risk"}
    assert (
        verified["delivery_passport"]["package"]["manifest_sha256"]
        == archive["manifest"]["manifest_sha256"]
    )
    assert verified["status"] == "pass"
    assert tampered["status"] == "fail"
    assert any(
        item["code"] == "archive-payload-hash-mismatch" for item in tampered["findings"]
    )


def test_productization_api_builds_unsigned_bundle_manifest_without_writing():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/v1/productization/offline-bundle/manifest",
        json={
            "profile": "pilot",
            "include_defaults": False,
            "include_paths": ["docs/productization/SUPPORT_MATRIX.md"],
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["files"] == 1
    assert payload["signature"]["signed"] is False


def test_productization_api_rejects_archive_output_outside_repo():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/v1/productization/offline-bundle/archive",
        json={
            "profile": "pilot",
            "include_defaults": False,
            "include_paths": ["docs/productization/SUPPORT_MATRIX.md"],
            "output_path": "../bundle.zip",
        },
    )

    assert response.status_code == 400
    assert "escapes repository root" in response.json()["detail"]


@pytest.mark.asyncio
async def test_mcp_offline_bundle_tools_are_registered_and_work():
    names = {tool.name for tool in TOOLS}
    assert {
        "offline_bundle_manifest",
        "offline_bundle_verify",
        "offline_bundle_archive",
        "offline_bundle_archive_verify",
    } <= names

    manifest = await handle_offline_bundle_manifest(
        {
            "profile": "pilot",
            "include_defaults": False,
            "include_paths": ["docs/productization/SUPPORT_MATRIX.md"],
            "write": False,
        }
    )
    verified = await handle_offline_bundle_verify({"manifest_path": ""})

    assert manifest["summary"]["files"] == 1
    assert "error" in verified
