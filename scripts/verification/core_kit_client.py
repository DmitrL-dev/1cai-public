"""Standalone client copied outside checkout and run with the installed SDK."""
import base64
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import rentgen_core.draft_editing
import rentgen_core.mcp_drafts
import rentgen_core.source_catalog
import rentgen_core.stdio_mcp


async def main():
    (
        cli,
        server,
        scanner,
        environment,
        forbidden,
        wheel_hash,
        expected_version,
    ) = sys.argv[1:]
    environment = Path(environment)
    assert importlib.metadata.version("rentgen-core") == expected_version
    modules = (
        rentgen_core.draft_editing,
        rentgen_core.mcp_drafts,
        rentgen_core.source_catalog,
        rentgen_core.stdio_mcp,
    )
    assert all(Path(m.__file__).is_relative_to(environment) for m in modules)
    assert all(
        not Path(p).resolve().is_relative_to(Path(forbidden))
        for p in sys.path
        if p and not Path(p).resolve().is_relative_to(environment)
    )
    assert all(importlib.util.find_spec(n) is None for n in ("src", "tools", "fastapi"))
    working = Path.cwd()
    registry = working / "registry.sqlite3"
    source = working / "source"
    source.mkdir()
    for i in range(105):
        (source / f"A{i:03}.xml").write_text("<metadata/>", encoding="utf-8")
    module = source / "Module.bsl"
    original = (
        b"\xef\xbb\xbf"
        + b"// retained line\r\n" * 4096
        + "// Сохранённый текст Я😀\r\n".encode("utf-8")
        + b"Procedure BeforePackage() Export\r\nEndProcedure\r\n"
    )
    module.write_bytes(original)

    def command(name, *args):
        result = subprocess.run(
            [cli, name, "--registry", str(registry), *map(str, args)],
            capture_output=True,
            encoding="utf-8",
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)["result"]

    command("registry-init")
    project = command(
        "project-register",
        "--source-root",
        source,
        "--state-root",
        working / "state",
        "--name",
        "Delivered draft",
    )
    selector = ("--project", project["project_id"])
    assert command("membership-list", *selector)["state_schema_version"] == 4
    captured = command("capture", *selector, "--scanner", scanner)
    pin = {
        "project_id": project["project_id"],
        "snapshot_id": captured["snapshot"]["snapshot_id"],
    }
    draft_id, operation_id = str(uuid4()), str(uuid4())
    config = StdioServerParameters(
        command=server, args=["--registry", str(registry)], cwd=str(working)
    )

    async def call(session, name, args):
        response = await session.call_tool(name, args)
        assert not response.isError, response
        payload = json.loads(response.content[0].text)
        assert payload == response.structuredContent
        return payload["result"]

    async with stdio_client(config) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = [t.name for t in (await session.list_tools()).tools]
            assert len(tools) == 21
            invalid = await session.call_tool(
                "rentgen_project_head",
                {
                    "project_id": project["project_id"],
                    "manifest_hash": "PRIVATE_VALUE_NOT_FOR_ERROR",
                },
            )
            assert invalid.isError
            details = invalid.structuredContent["error"]["details"]
            assert details["unexpected_fields"] == ["manifest_hash"]
            assert details["allowed_fields"] == ["project_id"]
            assert "PRIVATE_VALUE_NOT_FOR_ERROR" not in invalid.content[0].text
            assert json.loads(invalid.content[0].text) == invalid.structuredContent
            page = await call(
                session,
                "rentgen_source_list",
                {**pin, "kind": "module", "query": "module.bsl", "limit": 1},
            )
            assert len(page["entries"]) == 1 and page["next_cursor"] is None
            ref = page["entries"][0]["ref"]
            first = (
                await call(
                    session,
                    "rentgen_draft_start",
                    {
                        **pin,
                        "source_ref": ref,
                        "draft_id": draft_id,
                        "title": "Delivered",
                        "operation_id": str(uuid4()),
                    },
                )
            )["draft"]
            edits = {
                **pin,
                "draft_id": draft_id,
                "expected_revision": 1,
                "operation_id": operation_id,
                "edits": [
                    {
                        "old_text": "Procedure BeforePackage()",
                        "new_text": "Procedure AfterPackage()",
                    }
                ],
            }
            second = (await call(session, "rentgen_draft_edit", edits))["draft"]
            assert first["revision"] == 1 and second["revision"] == 2
            assert module.read_bytes() == original
    reopened = command("draft-get", *selector, "--draft-id", draft_id, "--revision", 2)
    expected = original.replace(b"BeforePackage", b"AfterPackage")
    assert base64.b64decode(reopened["proposal"]["replacement"]["base64"]) == expected
    assert reopened["receipt"] == second
    archived = command(
        "draft-archive",
        *selector,
        "--draft-id",
        draft_id,
        "--expected-revision",
        2,
        "--operation-id",
        str(uuid4()),
    )
    assert archived["revision"] == 3
    assert (
        command("draft-list", *selector, "--status", "active", "--limit", 1)["items"]
        == []
    )
    assert command("draft-list", *selector, "--status", "archived", "--limit", 1)[
        "items"
    ] == [archived]
    restored = command(
        "draft-restore",
        *selector,
        "--draft-id",
        draft_id,
        "--expected-revision",
        3,
        "--operation-id",
        str(uuid4()),
    )
    assert restored["revision"] == 4
    module.write_bytes(original.replace(b"BeforePackage", b"LivePackage"))
    newer = command("capture", *selector, "--scanner", scanner)
    assert newer["snapshot"] != captured["snapshot"]
    async with stdio_client(config) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            assert (
                await call(
                    session,
                    "rentgen_draft_receipt",
                    {"project_id": project["project_id"], "operation_id": operation_id},
                )
            )["draft"] == second
            chunks = bytearray()
            offset = 0
            while offset is not None:
                part = (
                    await call(
                        session,
                        "rentgen_draft_read",
                        {
                            "project_id": project["project_id"],
                            "draft_id": draft_id,
                            "revision": 2,
                            "offset": offset,
                            "limit": 65536,
                        },
                    )
                )["draft"]
                raw = base64.b64decode(part["base64"])
                assert part["chunk_sha256"] == hashlib.sha256(raw).hexdigest()
                assert part["source_ref"] == ref
                chunks.extend(raw)
                offset = part["next_offset"]
            assert bytes(chunks) == expected
            assert part["candidate_sha256"] == hashlib.sha256(chunks).hexdigest()
            text_chunks = bytearray()
            offset = 0
            while offset is not None:
                text_part = (
                    await call(
                        session,
                        "rentgen_draft_read",
                        {
                            "project_id": project["project_id"],
                            "draft_id": draft_id,
                            "revision": 2,
                            "offset": offset,
                            "limit": 65535,
                            "encoding": "utf-8",
                        },
                    )
                )["draft"]
                encoded = text_part["text"].encode("utf-8")
                assert (
                    "base64" not in text_part
                    and len(encoded) == text_part["size_bytes"]
                )
                assert text_part["chunk_sha256"] == hashlib.sha256(encoded).hexdigest()
                assert text_part["source_ref"] == ref
                text_chunks.extend(encoded)
                offset = text_part["next_offset"]
            assert bytes(text_chunks) == expected
    assert (
        len(command("draft-history", *selector, "--draft-id", draft_id)["items"]) == 4
    )
    page = command("draft-history", *selector, "--draft-id", draft_id, "--limit", 1)
    assert page["items"] == [restored] and page["next_before"] == 4
    previous = command(
        "draft-history",
        *selector,
        "--draft-id",
        draft_id,
        "--limit",
        1,
        "--before-revision",
        4,
    )
    assert previous["items"] == [archived] and previous["next_before"] == 3
    assert module.read_bytes() == original.replace(b"BeforePackage", b"LivePackage")
    scoped_tools = [
        "rentgen_project_head",
        "rentgen_draft_read",
        "rentgen_draft_receipt",
    ]
    scoped = config.model_copy(deep=True)
    scoped.args.extend(["--project", project["project_id"]])
    for name in scoped_tools:
        scoped.args.extend(["--allow-tool", name])
    async with stdio_client(scoped) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            assert {t.name for t in (await session.list_tools()).tools} == set(
                scoped_tools
            )
            for name, args, code in [
                ("rentgen_project_list", {}, "MCP_TOOL_FORBIDDEN"),
                ("rentgen_draft_edit", {}, "MCP_TOOL_FORBIDDEN"),
                (
                    "rentgen_project_head",
                    {"project_id": str(uuid4())},
                    "MCP_PROJECT_FORBIDDEN",
                ),
            ]:
                response = await session.call_tool(name, args)
                assert (
                    response.isError
                    and response.structuredContent["error"]["code"] == code
                )
                assert (
                    json.loads(response.content[0].text) == response.structuredContent
                )
            receipt = await call(
                session,
                "rentgen_draft_receipt",
                {"project_id": project["project_id"], "operation_id": operation_id},
            )
            assert receipt["draft"] == second
            retained = await call(
                session,
                "rentgen_draft_read",
                {
                    "project_id": project["project_id"],
                    "draft_id": draft_id,
                    "revision": 2,
                    "offset": 0,
                    "limit": 1024,
                    "encoding": "utf-8",
                },
            )
            assert (
                retained["draft"]["candidate_sha256"]
                == hashlib.sha256(expected).hexdigest()
            )
            assert (
                retained["draft"]["text"].encode("utf-8")
                == expected[: retained["draft"]["size_bytes"]]
            )
    print(
        json.dumps(
            {
                "wheel_sha256": wheel_hash,
                "version": expected_version,
                "argument_feedback_verified": True,
                "scoped_tools_verified": scoped_tools,
                "tools": sorted(tools),
                "source_bytes": len(original),
                "candidate_sha256": hashlib.sha256(expected).hexdigest(),
                "schema": 4,
                "revisions": 4,
                "actor": second["actor"],
                "draft_id": draft_id,
                "first_snapshot": captured["snapshot"],
                "second_snapshot": newer["snapshot"],
                "origins": {m.__name__: m.__file__ for m in modules},
            }
        )
    )


if __name__ == "__main__":
    anyio.run(main)
