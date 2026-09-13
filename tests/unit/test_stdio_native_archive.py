import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from rentgen_core import stdio_mcp
from rentgen_core.errors import CoreError


PROJECT = "11111111-1111-4111-8111-111111111111"
SNAPSHOT = "a" * 64
OPERATION = "22222222-2222-4222-8222-222222222222"
PROFILE = "b" * 64


class _Tx:
    def __init__(self, runtime):
        self.runtime = runtime

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def require_all(self, permissions):
        self.runtime.checked_permissions.append(frozenset(permissions))
        if self.runtime.revoked:
            raise CoreError("PROJECT_FORBIDDEN", "Project access denied")


@dataclass
class _Context:
    project_id: str
    principal: object
    state: object


@dataclass
class _Runtime:
    graph_reader_factory: object = field(default_factory=object)
    revoked: bool = False
    checked_permissions: list = field(default_factory=list)
    context_calls: list = field(default_factory=list)
    resolve_calls: list = field(default_factory=list)

    def state_context(self, principal, project, permissions=()):
        self.context_calls.append((principal, project, frozenset(permissions)))
        if self.revoked:
            raise CoreError("PROJECT_FORBIDDEN", "Project access denied")
        return _Context(
            project,
            principal,
            SimpleNamespace(
                path=Path("C:/Rentgen/state.sqlite3"),
                transaction=lambda _: _Tx(self),
            ),
        )

    def resolve(self, principal, project, snapshot):
        self.resolve_calls.append((principal, project, snapshot))
        return _Context(
            project,
            principal,
            SimpleNamespace(
                path=Path("C:/Rentgen/state.sqlite3"),
                transaction=lambda _: _Tx(self),
            ),
        )


def _args(**overrides):
    value = {
        "project_id": PROJECT,
        "snapshot_id": SNAPSHOT,
        "operation_id": OPERATION,
        "namespace": "metadata-runs",
        "profile_id": PROFILE,
    }
    value.update(overrides)
    return value


def test_native_archive_schema_requires_explicit_binding():
    schema = stdio_mcp.TOOL_SCHEMAS["rentgen_native_archive"]
    assert schema["required"] == [
        "project_id",
        "snapshot_id",
        "operation_id",
        "namespace",
    ]
    stdio_mcp.validate_arguments("rentgen_native_archive", _args())
    platform_args = _args(namespace="platform-checks")
    platform_args.pop("profile_id")
    stdio_mcp.validate_arguments("rentgen_native_archive", platform_args)
    with pytest.raises(CoreError):
        stdio_mcp.validate_arguments(
            "rentgen_native_archive", _args(namespace="unknown")
        )
    with pytest.raises(CoreError):
        stdio_mcp.validate_arguments("rentgen_native_archive", _args(profile_id=None))


def test_native_archive_dispatch_is_admin_scoped_and_returns_receipt(monkeypatch):
    runtime = _Runtime()
    principal = SimpleNamespace(id="tester", authority="local_os")
    calls = []

    def fake_archive(ctx, operation_id, *, namespace, profile_id=None):
        calls.append((ctx, operation_id, namespace, profile_id))
        return {
            "schema": 1,
            "status": "archived",
            "released_logical_bytes": 0,
            "manifest_sha256": "c" * 64,
        }

    monkeypatch.setattr(
        "rentgen_core.native_resources.archive_native_run", fake_archive
    )
    result = stdio_mcp._execute(
        runtime,
        principal,
        "rentgen_native_archive",
        _args(),
        protocol_request_id=7,
        scope=stdio_mcp.McpScope(
            project_id=PROJECT, allowed_tools={"rentgen_native_archive"}
        ),
    )

    assert result.isError is False
    assert result.structuredContent["result"]["archive"]["status"] == "archived"
    assert result.meta["rentgenOutputScope"]["permissions"] == [
        "project:admin",
        "project:read",
    ]
    assert runtime.context_calls == [
        (principal, PROJECT, frozenset({"project:read", "project:admin"}))
    ]
    assert runtime.resolve_calls == [(principal, PROJECT, SNAPSHOT)]
    assert calls[0][1:] == (OPERATION, "metadata-runs", PROFILE)

    stream = io.BytesIO()
    guarded = stdio_mcp._GuardedOutput(stream, runtime, principal)
    document = {
        "jsonrpc": "2.0",
        "id": 7,
        "result": result.model_dump(by_alias=True, mode="json", exclude_none=True),
    }
    guarded._write(json.dumps(document, separators=(",", ":")))
    emitted = json.loads(stream.getvalue())
    assert emitted["result"]["structuredContent"]["result"]["archive"]["status"] == (
        "archived"
    )
    assert "_meta" not in emitted["result"]

    runtime.revoked = True
    revoked_stream = io.BytesIO()
    revoked_result = result.model_dump(by_alias=True, mode="json", exclude_none=True)
    revoked_result.pop("structuredContent")
    stdio_mcp._GuardedOutput(revoked_stream, runtime, principal)._write(
        json.dumps(
            {"jsonrpc": "2.0", "id": 7, "result": revoked_result},
            separators=(",", ":"),
        )
    )
    revoked = json.loads(revoked_stream.getvalue())
    assert revoked["result"]["structuredContent"]["error"]["code"] == (
        "PROJECT_FORBIDDEN"
    )

    tampered_stream = io.BytesIO()
    tampered_result = result.model_dump(by_alias=True, mode="json", exclude_none=True)
    tampered_result["_meta"]["rentgenOutputScope"]["permissions"] = [
        "project:read",
        "source:edit",
    ]
    stdio_mcp._GuardedOutput(tampered_stream, _Runtime(), principal)._write(
        json.dumps(
            {"jsonrpc": "2.0", "id": 7, "result": tampered_result},
            separators=(",", ":"),
        )
    )
    tampered = json.loads(tampered_stream.getvalue())
    assert tampered["result"]["structuredContent"]["error"]["code"] == (
        "PROJECT_ACCESS_UNAVAILABLE"
    )


def test_native_archive_error_is_redacted_after_revoke(monkeypatch):
    runtime = _Runtime()
    principal = SimpleNamespace(id="tester", authority="local_os")

    def fail_resolve(*_args):
        runtime.revoked = True
        raise CoreError("SENSITIVE_SNAPSHOT_ERROR", "should not leak")

    monkeypatch.setattr(runtime, "resolve", fail_resolve)
    result = stdio_mcp._execute(
        runtime,
        principal,
        "rentgen_native_archive",
        _args(),
        scope=stdio_mcp.McpScope(allowed_tools={"rentgen_native_archive"}),
    )

    assert result.isError is True
    assert result.structuredContent["error"]["code"] == "PROJECT_FORBIDDEN"
    assert "should not leak" not in result.structuredContent["error"]["message"]


def test_owner_report_tools_are_snapshot_bound_and_reauthorized(monkeypatch):
    runtime = _Runtime()
    principal = SimpleNamespace(id="tester", authority="local_os")
    report_id = "33333333-3333-4333-8333-333333333333"
    calls = []

    class FakeStore:
        def __init__(self, root):
            calls.append(("init", root))

        def get(
            self, selected, *, expected_project_id, expected_snapshot_id, authorize
        ):
            calls.append(("get", selected, expected_project_id, expected_snapshot_id))
            authorize()
            return {
                "schema": 1,
                "report_id": selected,
                "project_id": expected_project_id,
                "snapshot_id": expected_snapshot_id,
                "status": "stored",
                "created_at": "2026-09-14T00:00:00+00:00",
                "report": {"business_metrics": {"status": "not_available"}},
                "receipt_id": "d" * 64,
            }

        def list(self, *, expected_project_id, expected_snapshot_id, authorize, limit):
            calls.append(("list", expected_project_id, expected_snapshot_id, limit))
            authorize()
            return [
                {
                    "schema": 1,
                    "report_id": report_id,
                    "project_id": expected_project_id,
                    "snapshot_id": expected_snapshot_id,
                    "status": "stored",
                    "created_at": "2026-09-14T00:00:00+00:00",
                    "receipt_id": "e" * 64,
                }
            ]

    monkeypatch.setattr("rentgen_core.owner_report_store.OwnerReportStore", FakeStore)
    scope = stdio_mcp.McpScope(
        project_id=PROJECT,
        allowed_tools={"rentgen_owner_report_get", "rentgen_owner_report_list"},
    )
    result = stdio_mcp._execute(
        runtime,
        principal,
        "rentgen_owner_report_get",
        {"project_id": PROJECT, "snapshot_id": SNAPSHOT, "report_id": report_id},
        scope=scope,
    )
    assert result.isError is False
    assert result.structuredContent["result"]["owner_report"]["report_id"] == report_id
    assert result.meta["rentgenOutputScope"]["permissions"] == ["project:read"]
    assert result.meta["rentgenOutputScope"]["family"] == "report"
    assert calls[0] == ("init", Path("C:/Rentgen/owner-reports"))
    assert calls[1] == ("get", report_id, PROJECT, SNAPSHOT)

    report_stream = io.BytesIO()
    report_document = {
        "jsonrpc": "2.0",
        "id": 8,
        "result": result.model_dump(by_alias=True, mode="json", exclude_none=True),
    }
    stdio_mcp._GuardedOutput(report_stream, runtime, principal)._write(
        json.dumps(report_document, separators=(",", ":"))
    )
    report_emitted = json.loads(report_stream.getvalue())
    assert (
        report_emitted["result"]["structuredContent"]["result"]["owner_report"][
            "report_id"
        ]
        == report_id
    )
    assert "_meta" not in report_emitted["result"]

    runtime.revoked = True
    report_revoked_stream = io.BytesIO()
    report_revoked_result = result.model_dump(
        by_alias=True, mode="json", exclude_none=True
    )
    report_revoked_result.pop("structuredContent")
    stdio_mcp._GuardedOutput(report_revoked_stream, runtime, principal)._write(
        json.dumps(
            {"jsonrpc": "2.0", "id": 8, "result": report_revoked_result},
            separators=(",", ":"),
        )
    )
    report_revoked = json.loads(report_revoked_stream.getvalue())
    assert report_revoked["result"]["structuredContent"]["error"]["code"] == (
        "PROJECT_FORBIDDEN"
    )
    runtime.revoked = False

    listed = stdio_mcp._execute(
        runtime,
        principal,
        "rentgen_owner_report_list",
        {"project_id": PROJECT, "snapshot_id": SNAPSHOT, "limit": 7},
        scope=scope,
    )
    assert listed.isError is False
    assert (
        listed.structuredContent["result"]["owner_reports"][0]["report_id"] == report_id
    )
    assert calls[-1] == ("list", PROJECT, SNAPSHOT, 7)


def test_owner_report_tools_reject_unknown_fields_and_bad_ids():
    with pytest.raises(CoreError):
        stdio_mcp.validate_arguments(
            "rentgen_owner_report_get",
            {
                "project_id": PROJECT,
                "snapshot_id": SNAPSHOT,
                "report_id": "not-a-uuid",
            },
        )
    with pytest.raises(CoreError):
        stdio_mcp.validate_arguments(
            "rentgen_owner_report_list",
            {"project_id": PROJECT, "snapshot_id": SNAPSHOT, "limit": 0},
        )
