"""Explicit values must not collide with argparse defaults; repeats still fail."""
import pytest
from rentgen_core.cli import _parser
from rentgen_core.errors import CoreError


def arguments(command, *extra):
    return [command, "--registry", "registry.sqlite3", "--project", "project", *extra]


@pytest.mark.parametrize("command", ["draft-list", "draft-history"])
def test_explicit_page_limit_replaces_default_once(command):
    extra = [] if command == "draft-list" else ["--draft-id", "draft"]
    assert _parser().parse_args(arguments(command, *extra)).limit == 20
    assert _parser().parse_args(arguments(command, *extra, "--limit", "25")).limit == 25
    with pytest.raises(CoreError, match="Repeated option: --limit"):
        _parser().parse_args(
            arguments(command, *extra, "--limit", "20", "--limit", "25")
        )


@pytest.mark.parametrize("status", ["active", "archived"])
def test_explicit_status_replaces_default_once(status):
    assert _parser().parse_args(arguments("draft-list")).status == "active"
    assert (
        _parser().parse_args(arguments("draft-list", "--status", status)).status
        == status
    )
    with pytest.raises(CoreError, match="Repeated option: --status"):
        _parser().parse_args(
            arguments("draft-list", "--status", "active", "--status", status)
        )


def test_metadata_evidence_requires_operation_and_payload():
    parsed = _parser().parse_args(
        arguments(
            "metadata-evidence",
            "--snapshot",
            "snapshot",
            "--operation-id",
            "operation",
            "--evidence-json",
            "evidence.json",
        )
    )
    assert parsed.snapshot == "snapshot"
    assert parsed.operation_id == "operation"
    assert str(parsed.evidence_json) == "evidence.json"


@pytest.mark.parametrize(
    "command",
    [
        "metadata-workspace-create",
        "metadata-workspace-apply",
        "metadata-workspace-undo",
        "metadata-workspace-status",
        "metadata-workspace-recover",
    ],
)
def test_metadata_workspace_commands_require_explicit_binding(command):
    target = ("--target", "original") if command.endswith("recover") else ()
    parsed = _parser().parse_args(
        arguments(
            command,
            "--snapshot",
            "snapshot",
            "--operation-id",
            "operation",
            "--workspace",
            "workspace",
            *target,
        )
    )
    assert parsed.snapshot == "snapshot"
    assert parsed.operation_id == "operation"
    assert str(parsed.workspace) == "workspace"


def test_metadata_workspace_recover_requires_explicit_target():
    parsed = _parser().parse_args(
        arguments(
            "metadata-workspace-recover",
            "--snapshot",
            "snapshot",
            "--operation-id",
            "operation",
            "--workspace",
            "workspace",
            "--target",
            "candidate",
        )
    )
    assert parsed.target == "candidate"
    with pytest.raises(CoreError):
        _parser().parse_args(
            arguments(
                "metadata-workspace-recover",
                "--snapshot",
                "snapshot",
                "--operation-id",
                "operation",
                "--workspace",
                "workspace",
                "--target",
                "candidate",
                "--target",
                "original",
            )
        )


def test_owner_report_commands_have_explicit_context_and_bounded_paging():
    saved = _parser().parse_args(
        arguments(
            "owner-report-save",
            "--store",
            "state/owner-reports",
            "--snapshot",
            "snapshot",
            "--report-json",
            "report.json",
        )
    )
    assert saved.store.parts[-2:] == ("state", "owner-reports")
    assert saved.report_id is None
    loaded = _parser().parse_args(
        arguments(
            "owner-report-get",
            "--store",
            "state/owner-reports",
            "--snapshot",
            "snapshot",
            "--report-id",
            "report-id",
        )
    )
    assert loaded.report_id == "report-id"
    listed = _parser().parse_args(
        arguments(
            "owner-report-list",
            "--store",
            "state/owner-reports",
            "--snapshot",
            "snapshot",
            "--limit",
            "7",
        )
    )
    assert listed.limit == 7
    with pytest.raises(CoreError, match="Repeated option: --limit"):
        _parser().parse_args(
            arguments(
                "owner-report-list",
                "--store",
                "state/owner-reports",
                "--snapshot",
                "snapshot",
                "--limit",
                "7",
                "--limit",
                "8",
            )
        )
