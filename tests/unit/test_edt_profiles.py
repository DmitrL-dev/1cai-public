"""EDT startup authority belongs to project administrators and immutable inputs."""
import hashlib
import json
from pathlib import Path

import pytest

import test_project_core_publication as fixtures
from project_access_test_support import force_legacy_membership
from rentgen_core.errors import CoreError
from rentgen_core import edt_profiles as profiles

project, scanner, pytestmark = fixtures.project, fixtures.scanner, fixtures.pytestmark


@pytest.fixture
def specification(tmp_path):
    runtime, jdk = tmp_path / "edt", tmp_path / "jdk"
    files = {
        jdk / "bin/java.exe": b"fake Java, never executed",
        jdk / "lib/modules": b"fake Java modules",
        jdk / "conf/security/java.security": b"fake configuration",
        jdk / "release": b"test JDK",
        runtime / "plugins/org.eclipse.equinox.launcher_1.6.600.jar": b"launcher",
        runtime / "plugins/com.ditrix.edt.mcp.server_2.16.1.jar": b"mcp",
        runtime / "plugins/com._1c.g5.v8.dt.core_27.0.2.v202609041212.jar": b"edt",
        runtime / "configuration/config.ini": b"configuration",
        runtime
        / "configuration/org.eclipse.equinox.simpleconfigurator/bundles.info": b"bundles",
    }
    for path, raw in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    java = jdk / "bin/java.exe"
    return {
        "schema": 1,
        "name": "Local EDT fixture",
        "runtime_root": str(runtime),
        "java": {
            "path": str(java),
            "sha256": hashlib.sha256(java.read_bytes()).hexdigest(),
        },
    }


def test_profile_identity_includes_jdk_and_runtime_and_disable_is_final(
    project, specification
):
    ctx = project[0]
    first = profiles.register_profile(ctx, specification)
    assert first["qualification"] == "not_run"
    assert profiles.register_profile(ctx, specification) == first
    assert len(profiles.list_profiles(ctx)) == 1
    original = profiles.get_profile(ctx, first["profile_id"])
    java_modules = Path(specification["java"]["path"]).parents[1] / "lib/modules"
    java_modules.write_bytes(b"changed JDK")
    with pytest.raises(CoreError):
        with profiles.pinned_runtime(ctx, first["profile_id"]):
            pytest.fail("Changed runtime was admitted")
    second = profiles.register_profile(ctx, specification)
    assert second["profile_id"] != first["profile_id"]
    assert profiles.get_profile(ctx, first["profile_id"]) == original
    profiles.disable_profile(ctx, second["profile_id"])
    with pytest.raises(CoreError) as error:
        with profiles.pinned_runtime(ctx, second["profile_id"]):
            pytest.fail("Disabled profile was admitted")
    assert error.value.code == "EDT_PROFILE_DISABLED"


def test_admin_is_checked_before_external_io(project, specification):
    ctx = project[0]
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(
            tx, ctx.principal, {"project:read", "source:edit", "analysis:run"}
        )
    specification["runtime_root"] = "missing"
    with pytest.raises(CoreError) as error:
        profiles.register_profile(ctx, specification)
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_runtime_pins_prevent_overwrite_and_extra_file_is_refused(
    project, specification
):
    ctx = project[0]
    saved = profiles.register_profile(ctx, specification)
    module = (
        Path(specification["runtime_root"])
        / "plugins/com.ditrix.edt.mcp.server_2.16.1.jar"
    )
    with profiles.pinned_runtime(ctx, saved["profile_id"]):
        with pytest.raises(OSError):
            module.write_bytes(b"overwrite while running")
    extra = module.parent / "unregistered.jar"
    extra.write_bytes(b"unexpected startup input")
    with pytest.raises(CoreError):
        with profiles.pinned_runtime(ctx, saved["profile_id"]):
            pytest.fail("Extra runtime input was admitted")


def test_unsupported_profile_and_secret_fields_are_refused(project, specification):
    specification["url"] = "http://example.invalid/mcp"
    with pytest.raises(CoreError):
        profiles.register_profile(project[0], specification)


@pytest.mark.parametrize("revoke", [False, True])
def test_access_change_during_execution_prevents_success(
    project, specification, revoke
):
    ctx = project[0]
    saved = profiles.register_profile(ctx, specification)
    with pytest.raises(CoreError) as error:
        with profiles.pinned_runtime(ctx, saved["profile_id"]):
            if revoke:
                with ctx.state.transaction(ctx.principal, write=True) as tx:
                    force_legacy_membership(tx, ctx.principal, {"project:read"})
            else:
                profiles.disable_profile(ctx, saved["profile_id"])
    assert error.value.code == (
        "PROJECT_FORBIDDEN" if revoke else "EDT_PROFILE_DISABLED"
    )


def test_oversized_record_is_refused_before_publishing(
    project, specification, monkeypatch
):
    ctx = project[0]
    monkeypatch.setattr(profiles, "MAX_RECORD", 256)
    with pytest.raises(CoreError):
        profiles.register_profile(ctx, specification)
    assert list((ctx.state.path.parent / "edt-profiles").iterdir()) == []


def test_cli_register_list_disable_and_admin_before_read(
    project, specification, monkeypatch, capsys
):
    from rentgen_core import cli

    ctx = project[0]
    registry = ctx.state.path.parent / "unused-registry.sqlite3"

    # Keep the real context and its live access checks; isolate only CLI resolution.
    class Runtime:
        def __init__(self, *args, **kwargs):
            pass

        def state_context(self, principal, project, *, permissions):
            with ctx.state.transaction(ctx.principal) as tx:
                tx.require_all(permissions)
            return ctx

    monkeypatch.setattr(cli, "LocalRuntime", Runtime)
    monkeypatch.setattr(cli, "current_windows_principal", lambda: ctx.principal)
    specification_file = ctx.state.path.parent / "edt-specification.json"
    specification_file.write_text(json.dumps(specification), "utf-8")

    def run(command, *extra):
        code = cli.main(
            [command, "--registry", str(registry), "--project", ctx.project_id, *extra]
        )
        return code, json.loads(capsys.readouterr().out)

    code, result = run(
        "edt-profile-register", "--profile-json", str(specification_file)
    )
    assert code == 0, result
    identity = result["result"]["profile_id"]
    assert run("edt-profile-list")[1]["result"][0]["profile_id"] == identity
    assert (
        run("edt-profile-disable", "--profile-id", identity)[1]["result"]["enabled"]
        is False
    )
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, {"project:read"})
    code, result = run(
        "edt-profile-register", "--profile-json", str(specification_file / "missing")
    )
    assert code == 2
    assert result["error"]["code"] == "PROJECT_FORBIDDEN"
