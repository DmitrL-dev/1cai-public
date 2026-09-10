import json

import test_metadata_plans as fixtures
from project_access_test_support import force_legacy_membership
from rentgen_core import cli, metadata_plans

project, scanner, captured, pytestmark = (
    fixtures.project,
    fixtures.scanner,
    fixtures.captured,
    fixtures.pytestmark,
)


def test_cli_resolves_retained_adapter_and_checks_rights_before_payload(
    captured, monkeypatch, capsys
):
    ctx, request = captured
    monkeypatch.setattr(cli, "current_windows_principal", lambda: ctx.principal)
    payload = ctx.source_root.parent / "metadata-request.json"
    payload.write_text(json.dumps(request), "utf-8")
    argv = [
        "metadata-plan",
        "--registry",
        str(ctx.source_root.parent / "registry.sqlite3"),
        "--project",
        ctx.project_id,
        "--snapshot",
        ctx.snapshot.snapshot_id,
        "--request-json",
        str(payload),
    ]
    assert cli.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["result"] == metadata_plans.create_plan(
        ctx, request
    )
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, {"project:read"})
    payload.unlink()
    assert cli.main(argv) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "PROJECT_FORBIDDEN"
