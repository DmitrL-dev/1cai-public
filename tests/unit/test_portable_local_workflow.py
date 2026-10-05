"""Portable adapter acceptance on real subprocesses and synthetic local state.

No live capture is simulated as accepted. Historical draft rows are explicit
state-only fixtures; source files/generations are deliberately absent on reads.
"""
import asyncio
import base64
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from uuid import uuid4

import pytest

from rentgen_core import capabilities, cli, drafts, local_identity, proposals
from rentgen_core.context import Principal, SnapshotRef
from rentgen_core.errors import CoreError
from rentgen_core.local import LocalRuntime
from rentgen_core.sources import SourceRef
from rentgen_core.stdio_mcp import TOOL_SCHEMAS, McpScope, _execute

ROOT = Path(__file__).resolve().parents[2]
linux = pytest.mark.skipif(sys.platform != "linux", reason="Actual Linux profile and subprocess acceptance")


def test_every_adapter_operation_has_explicit_capability():
    parser_commands = cli._parser()._subparsers._group_actions[0].choices
    assert set(parser_commands) <= capabilities.COMMAND_CAPABILITIES.keys()
    assert {capabilities.operation_name(tool) for tool in TOOL_SCHEMAS} <= capabilities.COMMAND_CAPABILITIES.keys()
    assert not capabilities.operation_supported("new-unreviewed-operation")


@pytest.mark.parametrize("platform", ["linux", "darwin", "freebsd14"])
def test_live_native_snapshot_unknown_capabilities_fail_closed(monkeypatch, platform):
    monkeypatch.setattr(capabilities, "_platform", platform)
    for command in ("capture", "source-read", "proposal-live-apply", "metadata-live-undo", "metadata-workspace-apply", "proposal-test", "draft-save", "new-operation"):
        with pytest.raises(CoreError) as error:
            capabilities.require_operation(command)
        assert error.value.code == "CAPABILITY_UNAVAILABLE"
        assert error.value.details["platform"] == platform


def test_windows_token_identity_remains_unchanged(monkeypatch):
    monkeypatch.setattr(local_identity, "_platform", "win32")
    existing = Principal("windows-sid:S-1-5-21-123", "local_os")
    monkeypatch.setattr(local_identity, "current_windows_principal", lambda: existing)
    assert local_identity.current_local_principal() is existing
    with pytest.raises(CoreError) as error:
        local_identity.current_local_principal(identity_profile=Path("foreign.json"))
    assert error.value.code == "INVALID_ARGUMENT"


@linux
def test_profile_is_stable_independent_of_host_boot_namespace_and_environment(tmp_path, monkeypatch):
    profile = tmp_path / "private" / "identity.json"
    owner = local_identity.initialize_local_identity(profile)
    raw = profile.read_bytes()
    assert stat.S_IMODE(profile.stat().st_mode) == 0o600
    assert stat.S_IMODE(profile.parent.stat().st_mode) == 0o700
    for key in ("HOME", "USER", "LOGNAME", "HOSTNAME", "RENTGEN_PRINCIPAL"):
        monkeypatch.setenv(key, "untrusted-new-host")
    assert local_identity.current_local_principal(identity_profile=profile) == owner
    assert profile.read_bytes() == raw
    other = local_identity.initialize_local_identity(tmp_path / "other" / "identity.json")
    assert other != owner
    with pytest.raises(CoreError):
        local_identity.initialize_local_identity(profile)
    assert profile.read_bytes() == raw
    assert list(profile.parent.iterdir()) == [profile]


@linux
def test_default_profile_uses_password_database_not_home(tmp_path, monkeypatch):
    import pwd
    from types import SimpleNamespace
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: SimpleNamespace(pw_uid=uid, pw_dir=str(tmp_path)))
    monkeypatch.setenv("HOME", "/untrusted")
    assert local_identity._default_identity_profile().is_relative_to(tmp_path)


@linux
@pytest.mark.parametrize("defect", ["symlink", "hardlink", "public_file", "public_parent", "parent_symlink", "wrong_uid", "wrong_owner", "fifo", "invalid", "duplicate", "large"])
def test_profile_rejects_unsafe_ownership_and_documents(tmp_path, defect, monkeypatch):
    profile = tmp_path / "private" / "identity.json"
    local_identity.initialize_local_identity(profile)
    if defect == "symlink":
        saved = profile.with_suffix(".saved")
        profile.rename(saved)
        profile.symlink_to(saved)
    elif defect == "hardlink":
        os.link(profile, profile.with_suffix(".linked"))
    elif defect == "public_file":
        profile.chmod(0o644)
    elif defect == "public_parent":
        profile.parent.chmod(0o755)
    elif defect == "parent_symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(profile.parent, target_is_directory=True)
        profile = alias / profile.name
    elif defect == "wrong_uid":
        value = json.loads(profile.read_bytes()); value["uid"] += 1
        profile.write_bytes(local_identity._profile_bytes(value))
    elif defect == "wrong_owner":
        monkeypatch.setattr(os, "geteuid", lambda: profile.stat().st_uid + 1)
    elif defect == "fifo":
        profile.unlink(); os.mkfifo(profile, 0o600)
    elif defect == "duplicate":
        profile.write_bytes(profile.read_bytes().replace(b'{', b'{"schema":1,', 1))
    else:
        profile.write_bytes(b"x" * (2048 if defect == "large" else 10))
    with pytest.raises(CoreError) as error:
        local_identity.current_local_principal(identity_profile=profile)
    assert error.value.code == "LOCAL_IDENTITY_UNAVAILABLE"


@linux
def test_missing_profile_read_and_failed_atomic_publish_do_not_claim_identity(tmp_path, monkeypatch):
    profile = tmp_path / "private" / "identity.json"
    with pytest.raises(CoreError):
        local_identity.current_local_principal(identity_profile=profile)
    assert not profile.parent.exists()
    monkeypatch.setattr(local_identity, "_publish_identity_profile", lambda *a, **k: (_ for _ in ()).throw(OSError("injected publication failure")))
    with pytest.raises(CoreError):
        local_identity.initialize_local_identity(profile)
    assert list(profile.parent.iterdir()) == []


def command(*args, env=None):
    result = subprocess.run(
        [sys.executable, "-m", "rentgen_core", *map(str, args)], cwd=ROOT,
        env=env, capture_output=True, text=True, timeout=20,
    )
    assert result.stderr == "", result.stderr
    return result.returncode, json.loads(result.stdout)


@pytest.fixture
def portable_project(tmp_path):
    if sys.platform != "linux":
        pytest.skip("Actual Linux CLI ownership")
    profile = tmp_path / "private" / "identity.json"
    code, identity = command("identity-init", "--identity-profile", profile)
    assert code == 0, identity
    registry = tmp_path / "registry.sqlite3"
    common = ["--registry", registry, "--identity-profile", profile]
    assert command("registry-init", *common)[0] == 0
    source = tmp_path / "source"; source.mkdir()
    sentinel = source / "foreign.bsl"; sentinel.write_bytes(b"foreign user source\n")
    state = tmp_path / "state"
    code, result = command("project-register", *common, "--source-root", source, "--state-root", state, "--name", "Portable synthetic")
    assert code == 0, result
    project = result["result"]["project_id"]
    return profile, registry, project, source, common


def seed_historical_draft(project):
    """Create test-only schema-valid history, not a portable capture/write adapter."""
    profile, registry, project_id, _, _ = project
    owner = local_identity.current_local_principal(identity_profile=profile)
    ctx = LocalRuntime(registry).state_context(owner, project_id)
    snapshot = SnapshotRef(project_id, "a" * 64, "a" * 64)
    old, candidate = b"Old();\n", "Новый();\n".encode()
    ref = SourceRef(snapshot, "base", "Module.bsl", hashlib.sha256(old).hexdigest())
    proposal = proposals.Proposal(ref, len(old), candidate, proposals.BytePolicy("utf-8", False, "lf", True, True), "")
    proposal = replace(proposal, content_id=hashlib.sha256(proposals._canonical(proposals._unsigned(proposal))).hexdigest())
    draft_id, operation = str(uuid4()), str(uuid4())
    with ctx.state.transaction(owner, write=True) as tx:
        tx._connection.execute("INSERT INTO snapshots VALUES (?,?,?,?,?,?,?,?)", (project_id, snapshot.snapshot_id, snapshot.snapshot_id, "b" * 64, "c" * 64, "generations/" + snapshot.snapshot_id, 1, "2026-10-05T00:00:00+00:00"))
        tx._connection.execute("INSERT INTO snapshot_layers VALUES (?,?,?,?,?,?,?,?)", (project_id, snapshot.snapshot_id, "base", 0, "base", None, "unresolved", "designer_xml"))
        request = drafts._request(owner, "draft.saved", draft_id, 0, title="Synthetic existing draft", content_id=proposal.content_id)
        receipt = drafts._commit(tx, request, operation, proposal, proposals._canonical(proposals._document(proposal)))
    return ctx, draft_id, operation, receipt, candidate


@linux
def test_real_cli_bootstrap_history_receipt_and_revocation(portable_project):
    profile, registry, project, source, common = portable_project
    ctx, draft_id, operation, receipt, candidate = seed_historical_draft(portable_project)
    # No source/generation access is necessary for historical draft reads.
    (source / "foreign.bsl").unlink(); source.rmdir()
    assert command("identity", "--identity-profile", profile)[1]["result"]["id"] == ctx.principal.id
    assert command("project-list", *common)[1]["result"][0]["project_id"] == project
    assert command("project-head", *common, "--project", project)[1]["result"]["revision"] == 0
    assert command("draft-list", *common, "--project", project)[0] == 0
    assert command("draft-history", *common, "--project", project, "--draft-id", draft_id)[0] == 0
    assert command("draft-receipt", *common, "--project", project, "--operation-id", operation)[1]["result"] == receipt
    code, saved = command("draft-get", *common, "--project", project, "--draft-id", draft_id)
    assert code == 0, saved
    assert base64.b64decode(saved["result"]["proposal"]["replacement"]["base64"]) == candidate
    other_profile = profile.parent.parent / "other" / "identity.json"
    assert command("identity-init", "--identity-profile", other_profile)[0] == 0
    other = ["--registry", registry, "--identity-profile", other_profile]
    assert command("project-list", *other)[1]["result"] == []
    assert command("draft-get", *other, "--project", project, "--draft-id", draft_id)[1]["error"]["code"] == "PROJECT_FORBIDDEN"
    # Explicit fixture revocation is immediately observed by a new real process.
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        tx._connection.execute("DELETE FROM membership_permissions WHERE principal_id=? AND permission='project:read'", (ctx.principal.id,))
    assert command("draft-get", *common, "--project", project, "--draft-id", draft_id)[1]["error"]["code"] == "PROJECT_FORBIDDEN"


@linux
def test_real_cli_byte_planner_is_deterministic_and_does_not_modify_state(portable_project):
    from test_metadata_three_way_materialize import PATH, xml
    profile, registry, project, source, common = portable_project
    files = []
    trees = ({PATH: xml("<Code>A</Code>")}, {PATH: xml("<Code>A</Code>", name="Local")}, {PATH: xml("<Code>B</Code>")})
    for label, tree in zip(("base", "current", "upstream"), trees):
        path = registry.parent / (label + ".json")
        path.write_text(json.dumps({"schema": 1, "encoding": "base64", "files": {key: base64.b64encode(raw).decode() for key, raw in tree.items()}}))
        files.extend(["--" + label + "-json", path])
    before = {path: path.read_bytes() for path in registry.parent.rglob("*") if path.is_file()}
    code, first = command("metadata-materialize", *common, "--project", project, *files)
    assert code == 0, first
    assert first["result"]["status"] == "ready"
    assert command("metadata-materialize", *common, "--project", project, *files)[1]["result"] == first["result"]
    assert {path: path.read_bytes() for path in before} == before


@linux
def test_unsupported_cli_and_mcp_refuse_before_project_or_payload_io(tmp_path):
    missing = tmp_path / "not-created"
    code, result = command("proposal-live-apply", "--registry", missing / "registry", "--project", str(uuid4()), "--snapshot", "a" * 64, "--operation-id", str(uuid4()), "--proposal-json", missing / "proposal", "--expected-head-json", missing / "head", "--identity-profile", missing / "identity")
    assert code == 2 and result["error"]["code"] == "CAPABILITY_UNAVAILABLE"
    assert not missing.exists()
    reply = _execute(object(), Principal("fixture", "local_os"), "rentgen_proposal_live_undo", {"project_id": str(uuid4()), "operation_id": str(uuid4())})
    assert reply.structuredContent["error"]["code"] == "CAPABILITY_UNAVAILABLE"
    assert not missing.exists()


@linux
def test_real_stdio_mcp_reads_saved_draft_and_filters_unsupported_tools(portable_project):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import anyio
    profile, registry, project, source, common = portable_project
    ctx, draft_id, operation, receipt, candidate = seed_historical_draft(portable_project)
    async def scenario():
        params = StdioServerParameters(command=sys.executable, args=["-m", "rentgen_core.stdio_mcp", "--registry", str(registry), "--identity-profile", str(profile)], cwd=str(ROOT))
        with anyio.fail_after(30):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = {tool.name for tool in (await session.list_tools()).tools}
                    assert "rentgen_capabilities" in listed
                    assert "rentgen_draft_read" in listed
                    assert "rentgen_proposal_live_apply" not in listed
                    assert "rentgen_capture" not in listed
                    caps = await session.call_tool("rentgen_capabilities", {})
                    assert caps.structuredContent["result"]["platform"] == "linux"
                    result = await session.call_tool("rentgen_draft_receipt", {"project_id": project, "operation_id": operation})
                    assert not result.isError and result.structuredContent["result"]["draft"] == receipt
                    readback = await session.call_tool("rentgen_draft_read", {"project_id": project, "draft_id": draft_id, "revision": 1, "encoding": "utf-8"})
                    assert not readback.isError, readback
                    rejected = await session.call_tool("rentgen_proposal_live_undo", {"project_id": project, "operation_id": str(uuid4())})
                    assert rejected.isError and rejected.structuredContent["error"]["code"] == "CAPABILITY_UNAVAILABLE"
    asyncio.run(scenario())


@linux
def test_identity_init_concurrent_creators_never_replace_winning_namespace(tmp_path):
    profile = tmp_path / "private" / "identity.json"
    profile.parent.mkdir(mode=0o700)
    argv = [sys.executable, "-m", "rentgen_core", "identity-init", "--identity-profile", str(profile)]
    processes = [subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
    results = [(p, p.communicate(timeout=20)) for p in processes]
    successes = [json.loads(output)["result"] for p, (output, errors) in results if p.returncode == 0]
    assert len(successes) == 1
    assert all(not errors for _, (_, errors) in results)
    assert local_identity.current_local_principal(identity_profile=profile).id == successes[0]["id"]
    assert profile.stat().st_nlink == 1
    assert list(profile.parent.iterdir()) == [profile]


@linux
def test_interruption_after_atomic_identity_publish_retains_readable_original(tmp_path, monkeypatch):
    profile = tmp_path / "private" / "identity.json"
    original = local_identity._publish_identity_profile
    def interrupt(parent, temporary, name):
        original(parent, temporary, name)
        raise KeyboardInterrupt()
    monkeypatch.setattr(local_identity, "_publish_identity_profile", interrupt)
    with pytest.raises(KeyboardInterrupt):
        local_identity.initialize_local_identity(profile)
    owner = local_identity.current_local_principal(identity_profile=profile)
    assert profile.stat().st_nlink == 1
    assert list(profile.parent.iterdir()) == [profile]
    with pytest.raises(CoreError):
        local_identity.initialize_local_identity(profile)
    assert local_identity.current_local_principal(identity_profile=profile) == owner


@linux
def test_identity_init_never_deletes_an_unowned_temporary_collision(tmp_path, monkeypatch):
    import uuid
    fixed = uuid.uuid4()
    profile = tmp_path / "private" / "identity.json"
    profile.parent.mkdir(mode=0o700)
    unrelated = profile.parent / (".rentgen-identity-" + fixed.hex + ".tmp")
    unrelated.write_bytes(b"unrelated preexisting file")
    monkeypatch.setattr(uuid, "uuid4", lambda: fixed)
    with pytest.raises(CoreError):
        local_identity.initialize_local_identity(profile)
    assert unrelated.read_bytes() == b"unrelated preexisting file"
    assert not profile.exists()
