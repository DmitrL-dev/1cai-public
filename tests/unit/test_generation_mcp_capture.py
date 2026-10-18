"""Actual Windows/Linux capture + official SDK stdio; installed gates run separately."""
from dataclasses import asdict
import json
import sys
from uuid import uuid4

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import rentgen_core as api
from project_access_test_support import grant_membership, revoke_membership
from publication_kill_support import ROOT, backend
from test_publication_process_kill import project, scanner, native
from test_generation_delivery_probe import probe


@native
def test_native_sdk_historical_generation_damage_restore_and_revocation(project, scanner, tmp_path):
    from rentgen_core.local_identity import current_local_principal, initialize_local_identity
    ctx, registry, module = project
    extra = []
    if sys.platform == "linux":
        profile = tmp_path / "identity/profile.json"
        principal = initialize_local_identity(profile)
        extra = ["--identity-profile", str(profile)]
    else:
        principal = current_local_principal()
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        grant_membership(tx, principal, {"project:read"})
    def capture():
        return asdict(api.capture_and_publish(ctx, expected_head=api.get_project_head(ctx),
            builder=backend(*scanner), operation_id=str(uuid4())))
    first = capture()
    module.write_bytes(module.read_bytes().replace(b"Return 1", b"Return 2"))
    second = capture()
    ctx.source_root.rename(tmp_path / "removed-live-source")
    config = StdioServerParameters(command=sys.executable, args=["-m", "rentgen_core.stdio_mcp",
        "--registry", str(registry.path), "--project", ctx.project_id, *extra], cwd=str(ROOT))
    async def scenario():
        async with stdio_client(config) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                for name in ("rentgen_generation_attribution", "rentgen_generation_verify"):
                    assert tools[name].annotations.readOnlyHint and not tools[name].annotations.destructiveHint
                result = await probe.verify_mcp(session, ctx.state.path.parent, ctx.source_root, first, second)
                assert result["transport"] == "official_sdk_stdio" and result["output_scope_private"]
                assert len(result["checks"]) == 29 and all(result["outcomes"].values())
                with ctx.state.transaction(ctx.principal, write=True) as tx:
                    revoke_membership(tx, principal)
                locator = result["first"]["catalog"]["generation_relpath"]
                for name in ("rentgen_generation_attribution", "rentgen_generation_verify"):
                    denied = await session.call_tool(name, dict(project_id=ctx.project_id, generation_relpath=locator))
                    assert denied.isError and denied.structuredContent["error"]["code"] == "PROJECT_FORBIDDEN"
                    assert locator not in json.dumps(denied.model_dump())
    anyio.run(scenario)
