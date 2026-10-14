"""Candidate admission and unchanged wire contracts, not Windows native acceptance."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from rentgen_core import cli, capabilities
from rentgen_core.stdio_mcp import TOOL_SCHEMAS
from test_core_dev16_compatibility import adapter


# These inputs were unchanged from the accepted dev17 Core 25743f7. A later
# protocol change requires explicit requalification, not a broad version range.
COMPANION_COMMANDS = (
    "project-head", "source-list", "source-read", "draft-list", "draft-history",
    "draft-get", "proposal-create", "draft-save", "proposal-check",
    "test-profile-list", "proposal-test", "proposal-test-result",
    "proposal-platform-check", "proposal-platform-result", "draft-receipt",
)
EDITOR_TOOLS = (
    "rentgen_project_head", "rentgen_source_list", "rentgen_draft_start",
    "rentgen_draft_read", "rentgen_draft_edit", "rentgen_draft_check",
    "rentgen_draft_receipt", "rentgen_draft_list", "rentgen_draft_history",
    "rentgen_proposal_live_apply", "rentgen_proposal_live_undo",
    "rentgen_proposal_live_status", "rentgen_proposal_live_recover",
)


def digest(value):
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def companion_cli_contract():
    commands = cli._parser()._subparsers._group_actions[0].choices
    return {
        name: [
            {
                "options": action.option_strings,
                "dest": action.dest,
                "required": action.required,
                "nargs": action.nargs,
                "default": action.default,
                "type": getattr(action.type, "__name__", None),
                "choices": list(action.choices) if action.choices is not None else None,
            }
            for action in commands[name]._actions
        ]
        for name in COMPANION_COMMANDS
    }


def test_existing_companion_cli_contract_remains_dev17_compatible():
    assert digest(companion_cli_contract()) == "545456e7b4303b4cc9217a4f31fd3be5f7001fadc3cf1c6d5770100282c67766"


def test_existing_editor_mcp_contract_remains_dev17_compatible():
    assert adapter("prepare.py").MCP_EDITOR_TOOLS == EDITOR_TOOLS
    assert digest({name: TOOL_SCHEMAS[name] for name in EDITOR_TOOLS}) == "131eb1e4e7c5a5961c6906ef980aca3b17eae369ba4d64311ec1ddfb9f43a227"
    assert "rentgen_source_facts" not in TOOL_SCHEMAS
    assert not any("source_fact" in name for name in TOOL_SCHEMAS)


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_source_facts_does_not_expand_live_capabilities(monkeypatch, platform):
    monkeypatch.setattr(capabilities, "_platform", platform)
    assert capabilities.operation_supported("source-facts") is (platform == "linux")
    for command in ("capture", "source-read", "draft-save", "proposal-live-apply", "proposal-live-undo", "metadata-live-apply", "proposal-test"):
        assert capabilities.operation_supported(command) is (platform == "win32")


@pytest.mark.parametrize("patch", [
    {"core": "0.1.0.dev19"}, {"core": "0.1.0.dev999"}, {"core": "0.1.0.dev18+local"},
    {"mcp": "1.31.0"}, {"mcp": "1.29.0"}, {"platform": "linux"},
    {"python": [3, 12]}, {"installed": False}, {"unexpected": True},
])
def test_dev18_editor_probe_rejects_unreviewed_runtime_before_project_read(monkeypatch, patch):
    module = adapter("prepare.py")
    identity = {"core": "0.1.0.dev18", "mcp": "1.30.0", "platform": "win32", "python": [3, 11], "installed": True}
    identity.update(patch)
    commands = []

    def execute(argv, **options):
        commands.append(argv)
        return SimpleNamespace(returncode=0, stdout=json.dumps(identity))

    monkeypatch.setattr(module.subprocess, "run", execute)
    with pytest.raises(ValueError, match="supported installed core"):
        module.probe(Path(sys.executable), Path("registry.sqlite3"), "6e461c4d-e19c-4e37-85b3-3aa0961580b7")
    assert len(commands) == 1
    assert commands[0][1] == "-I"


@pytest.mark.parametrize("installed", ["0.1.0.dev17", "0.1.0.dev19"])
def test_dev18_repair_never_silently_uses_another_installed_core(installed):
    module = adapter("run_repair.py")
    with pytest.raises(ValueError, match="match the profile exactly"):
        module.validate_profile({"schema": 1, "core_version": "0.1.0.dev18", "python": sys.executable}, installed, "1.30.0", sys.executable)
