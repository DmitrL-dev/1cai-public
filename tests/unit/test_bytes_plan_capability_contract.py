"""`analysis.bytes.plan` must refuse before identity, registry, payload and source IO.

docs/product/PORTABLE-CORE.md states the macOS refusal happens before those
steps. These tests pin that ordering on every OS by driving the real CLI entry
point with the capability matrix monkeypatched, and by asserting every probe
that would touch IO is never reached.
"""
import json

import pytest

from rentgen_core import capabilities, cli

from platform_support_test_support import (
    BYTES_PLAN_CAPABILITY,
    BYTES_PLAN_COMMANDS,
)

# Platforms the matrix enumerates; the ordering contract is platform-independent.
UNSUPPORTED_PLATFORMS = ("darwin", "freebsd14")
SUPPORTED_PLATFORMS = ("win32", "linux")


def _argv(command):
    """Minimal well-formed argv: values are never read before the gate."""
    return [
        command,
        "--registry",
        "registry.sqlite3",
        "--project",
        "p",
        "--base-json",
        "base.json",
        "--current-json",
        "current.json",
        "--upstream-json",
        "upstream.json",
    ]


def test_bytes_plan_commands_are_one_capability_group():
    for command in BYTES_PLAN_COMMANDS:
        assert capabilities.COMMAND_CAPABILITIES[command] == BYTES_PLAN_CAPABILITY


def test_bytes_plan_is_portable_on_windows_and_linux_only(monkeypatch):
    for platform, expected in (
        ("win32", True),
        ("linux", True),
        ("darwin", False),
        ("freebsd14", False),
    ):
        monkeypatch.setattr(capabilities, "_platform", platform)
        status = capabilities.capability_status(BYTES_PLAN_CAPABILITY)
        assert status["supported"] is expected, platform
        if not expected:
            assert status["reason"], platform


@pytest.mark.parametrize("command", BYTES_PLAN_COMMANDS)
@pytest.mark.parametrize("platform", UNSUPPORTED_PLATFORMS)
@pytest.mark.parametrize("payload", [None, b"{}", b"PRIVATE_PAYLOAD"])
def test_unsupported_platform_refuses_before_any_io(
    monkeypatch, tmp_path, capsys, command, platform, payload
):
    """A denied platform must not reach identity, registry, payload or source IO."""
    monkeypatch.setattr(capabilities, "_platform", platform)

    def forbidden(*args, **kwargs):
        pytest.fail(f"IO reached before the capability gate: {command} on {platform}")

    monkeypatch.setattr(cli, "current_local_principal", forbidden)
    monkeypatch.setattr(cli, "_runtime", forbidden)
    monkeypatch.setattr(cli, "_proposal_input", forbidden)
    monkeypatch.setattr(cli, "_metadata_tree", forbidden)
    monkeypatch.setattr(cli, "_edt_identity_inventory_json", forbidden)

    if payload is not None:
        # A real payload exists on disk; it still must not be opened.
        paths = [tmp_path / name for name in ("base.json", "current.json", "upstream.json")]
        for path in paths:
            path.write_bytes(payload)
        argv = _argv(command)
        argv[6], argv[8], argv[10] = map(str, paths)
    else:
        argv = _argv(command)

    code = cli.main(argv)
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["error"]["code"] == "CAPABILITY_UNAVAILABLE"
    assert output["error"]["details"]["platform"] == platform
    assert output["error"]["details"]["capability"] == BYTES_PLAN_CAPABILITY
    assert "result" not in output
    assert "PRIVATE_PAYLOAD" not in json.dumps(output)


@pytest.mark.parametrize("command", BYTES_PLAN_COMMANDS)
@pytest.mark.parametrize("platform", SUPPORTED_PLATFORMS)
def test_supported_platform_passes_gate_before_identity(monkeypatch, capsys, command, platform):
    """Exercise real CLI dispatch but stop at an identity sentinel, without IO."""
    monkeypatch.setattr(capabilities, "_platform", platform)
    reached = []

    def identity(*args, **kwargs):
        reached.append(True)
        raise capabilities.CoreError("TEST_IDENTITY_REACHED", "Offline identity sentinel")

    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected IO after identity sentinel")

    monkeypatch.setattr(cli, "current_local_principal", identity)
    for name in ("_runtime", "_proposal_input", "_metadata_tree", "_edt_identity_inventory_json"):
        monkeypatch.setattr(cli, name, forbidden)
    assert capabilities.require_operation(command) is None
    assert cli.main(_argv(command)) == 2
    output = capsys.readouterr()
    assert not output.err
    assert json.loads(output.out)["error"]["code"] == "TEST_IDENTITY_REACHED"
    assert reached == [True]
