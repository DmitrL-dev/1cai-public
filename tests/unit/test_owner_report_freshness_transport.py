"""CLI/MCP read policy over real state and store; no new OS admission claim.

Windows capability routing is selected for transport-contract tests on all test
hosts. The store uses the host's actual retained IO backend, never a FakeStore.
The full Windows suite executes the Windows backend as well.
"""
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

from rentgen_core import capabilities, cli, stdio_mcp
from rentgen_core.local import LocalRuntime
from rentgen_core.owner_report import build_owner_report
from rentgen_core import owner_report_store as implementation
from rentgen_core.owner_report_store import MAX_FRESHNESS_SECONDS, OwnerReportStore
from project_access_test_support import force_legacy_membership
from test_owner_report_cli import project_fixture

SNAPSHOT = "b" * 64
PROJECT = "11111111-1111-4111-8111-111111111111"
REPORT = "33333333-3333-4333-8333-333333333333"


@pytest.fixture
def report_reads(project_fixture, monkeypatch, capsys):
    ctx, resolver = project_fixture
    runtime = LocalRuntime(resolver.registry.path)
    monkeypatch.setattr(capabilities, "_platform", "win32")
    monkeypatch.setattr(cli, "current_local_principal", lambda: ctx.principal)
    monkeypatch.setattr(cli, "_runtime", lambda args: runtime)
    store = OwnerReportStore(ctx.state.path.parent / "owner-reports")
    store.initialize()
    receipts = []
    for generated in ("2000-01-01T00:00:00+00:00", datetime.now(timezone.utc).isoformat(),
                      "2100-01-01T00:00:00+00:00"):
        report = build_owner_report(ctx.project_id, SNAPSHOT)
        report["generated_at"] = generated
        receipts.append(store.save(report, authorize=lambda: None))

    def invoke(transport, kind, *, success=True, **options):
        if kind == "get":
            options.setdefault("report_id", receipts[0]["report_id"])
        if transport == "cli":
            args = [f"owner-report-{kind}", "--registry", str(resolver.registry.path),
                    "--project", ctx.project_id, "--store", str(store.root),
                    "--snapshot", SNAPSHOT]
            for key, value in options.items():
                args.extend(["--" + key.replace("_", "-"), str(value)])
            status = cli.main(args)
            output = capsys.readouterr().out
            assert status == (0 if success else 2), output
            payload = json.loads(output)
        else:
            result = stdio_mcp._execute(
                runtime, ctx.principal, f"rentgen_owner_report_{kind}",
                {"project_id": ctx.project_id, "snapshot_id": SNAPSHOT, **options},
            )
            assert bool(result.isError) is not success, result.structuredContent
            payload = result.structuredContent
            if success:
                key = "owner_report" if kind == "get" else "owner_reports"
                payload = {"result": payload["result"][key]}
        return payload["result"] if success else payload

    return ctx, store, receipts, invoke


@pytest.mark.parametrize("transport", ["cli", "mcp"])
def test_freshness_views_preserve_receipts_and_use_host_clock(report_reads, transport):
    _, store, receipts, invoke = report_reads
    before = {p.name: p.read_bytes() for p in store.reports.iterdir()}
    start = datetime.now(timezone.utc)
    reasons = ["older_than_policy", None, "generated_after_as_of"]
    for receipt, reason in zip(receipts, reasons):
        assert invoke(transport, "get", report_id=receipt["report_id"]) == receipt
        view = invoke(transport, "get", report_id=receipt["report_id"], max_age_seconds=86400)
        freshness = view.pop("freshness")
        assert view == receipt
        assert freshness["reason"] == reason
        assert freshness["historical"] is (reason is not None)
        assert freshness["max_age_seconds"] == 86400
        assert start <= datetime.fromisoformat(freshness["as_of"]) <= datetime.now(timezone.utc)
    plain = invoke(transport, "list")
    assert all("freshness" not in item and "report" not in item for item in plain)
    views = invoke(transport, "list", max_age_seconds=86400)
    assert len(views) == 3 and len({v["freshness"]["as_of"] for v in views}) == 1
    for view, receipt in zip(views, plain):
        freshness = view.pop("freshness")
        assert view == receipt and freshness["max_age_seconds"] == 86400
    limited = invoke(transport, "list", max_age_seconds=86400, limit=1)
    assert len(limited) == 1 and limited[0]["report_id"] == plain[0]["report_id"]
    assert "freshness" in limited[0] and "report" not in limited[0]
    assert {p.name: p.read_bytes() for p in store.reports.iterdir()} == before


@pytest.mark.parametrize("transport", ["cli", "mcp"])
@pytest.mark.parametrize("kind", ["get", "list"])
def test_freshness_view_is_withheld_if_permission_changes_before_output(
    report_reads, monkeypatch, transport, kind,
):
    ctx, _, _, invoke = report_reads
    original = implementation._with_freshness
    revoked = False

    def revoke_after_view(*args):
        nonlocal revoked
        view = original(*args)
        if not revoked:
            # Deliberate invalid permission state: output must fail closed even
            # after a valid retained read and computed freshness view.
            with ctx.state.transaction(ctx.principal, write=True) as tx:
                force_legacy_membership(tx, ctx.principal, set())
            revoked = True
        return view

    monkeypatch.setattr(implementation, "_with_freshness", revoke_after_view)
    payload = invoke(transport, kind, max_age_seconds=86400, success=False)
    assert revoked and payload["error"]["code"] == "PROJECT_FORBIDDEN"
    assert "result" not in payload and "freshness" not in json.dumps(payload)


def _mcp_args(kind, **extra):
    return {"project_id": PROJECT, "snapshot_id": SNAPSHOT,
            **({"report_id": REPORT} if kind == "get" else {}), **extra}


@pytest.mark.parametrize("kind", ["get", "list"])
@pytest.mark.parametrize("value", [1, MAX_FRESHNESS_SECONDS])
def test_freshness_policy_schema_accepts_both_bounds(kind, value):
    stdio_mcp.validate_arguments(f"rentgen_owner_report_{kind}",
                                 _mcp_args(kind, max_age_seconds=value))


@pytest.mark.parametrize("kind", ["get", "list"])
@pytest.mark.parametrize("extra", [
    {"max_age_seconds": value} for value in (0, -1, MAX_FRESHNESS_SECONDS + 1,
                                            True, 1.0, "60", None)
] + [{"as_of": "2000-01-01T00:00:00+00:00"},
     {"max_age_seconds": 60, "as_of": "2000-01-01T00:00:00+00:00"}])
def test_mcp_rejects_invalid_policy_and_caller_clock_before_state_io(kind, extra):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid policy reached project state")

    result = stdio_mcp._execute(SimpleNamespace(state_context=forbidden), None,
                               f"rentgen_owner_report_{kind}", _mcp_args(kind, **extra))
    assert result.isError and result.structuredContent["error"]["code"] == "INVALID_ARGUMENT"


@pytest.mark.parametrize("kind", ["get", "list"])
@pytest.mark.parametrize("options", [
    ["--max-age-seconds", value] for value in ("0", "-1", str(MAX_FRESHNESS_SECONDS + 1),
                                              "true", "1.0")
] + [["--as-of", "2000-01-01T00:00:00+00:00"],
     ["--max-age-seconds", "60", "--max-age-seconds", "30"]])
def test_cli_rejects_invalid_policy_and_caller_clock_before_runtime(
    monkeypatch, capsys, kind, options,
):
    def forbidden(*args):
        pytest.fail("Invalid policy reached runtime")

    monkeypatch.setattr(cli, "_runtime", forbidden)
    args = [f"owner-report-{kind}", "--registry", "absent.sqlite3", "--project", PROJECT,
            "--store", "absent-store", "--snapshot", SNAPSHOT]
    if kind == "get":
        args += ["--report-id", REPORT]
    assert cli.main(args + options) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_ARGUMENT"
