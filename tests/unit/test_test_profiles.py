"""Profile registration authorizes before input IO and stores immutable bytes."""
import hashlib

import pytest

import test_project_core_publication as fixtures
from project_access_test_support import force_legacy_membership
from rentgen_core.errors import CoreError
from rentgen_core import test_profiles as profiles

project, scanner, pytestmark = fixtures.project, fixtures.scanner, fixtures.pytestmark


@pytest.fixture
def definition(tmp_path, monkeypatch):
    files = {}
    for name in ("1cv8.exe", "ibcmd.exe", "engine.cfe", "tests.bsl"):
        file = tmp_path / name
        file.write_bytes(b"trusted fixture, not executed")
        files[name] = file
    engine_hash = hashlib.sha256(files["engine.cfe"].read_bytes()).hexdigest()
    monkeypatch.setattr(profiles, "ENGINE_SHA256", engine_hash)
    return {
        "schema": 1,
        "name": "Test profile",
        "platform": {"path": str(files["1cv8.exe"]), "sha256": engine_hash},
        "ibcmd": {"path": str(files["ibcmd.exe"]), "sha256": engine_hash},
        "engine": {"path": str(files["engine.cfe"]), "sha256": engine_hash},
        "modules": [
            {"name": "RentgenTests", "path": str(files["tests.bsl"]), "tests": ["One"]}
        ],
    }


def test_registration_is_content_addressed_and_copies_inputs(project, definition):
    ctx = project[0]
    first = profiles.register_profile(ctx, definition)
    assert profiles.register_profile(ctx, definition) == first
    assert profiles.get_profile(ctx, first["profile_id"])["definition"]["modules"][0][
        "tests"
    ] == ["One"]
    assert len(profiles.list_profiles(ctx)) == 1
    profiles.disable_profile(ctx, first["profile_id"])
    with pytest.raises(CoreError, match="disabled"):
        profiles.get_profile(ctx, first["profile_id"], active=True)
    assert profiles.list_profiles(ctx)[0]["enabled"] is False


def test_non_admin_cannot_register_before_external_files_are_read(project, definition):
    ctx = project[0]
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(
            tx, ctx.principal, {"project:read", "analysis:run", "source:edit"}
        )
    definition["engine"]["path"] = "missing"
    with pytest.raises(CoreError) as error:
        profiles.register_profile(ctx, definition)
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_tampered_or_duplicate_inputs_are_not_registered(project, definition):
    ctx = project[0]
    definition["platform"]["sha256"] = "0" * 64
    with pytest.raises(CoreError):
        profiles.register_profile(ctx, definition)
    definition["platform"]["sha256"] = definition["engine"]["sha256"]
    definition["modules"] *= 2
    with pytest.raises(CoreError):
        profiles.register_profile(ctx, definition)
