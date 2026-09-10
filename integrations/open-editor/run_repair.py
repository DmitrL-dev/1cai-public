"""Create and check a model-assisted draft using an installed trusted core profile."""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import sys

import anyio

# Explicit trusted adapter directory; -I keeps ambient project/PYTHONPATH out.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from repair_model import OllamaEditor, strict_json
from repair_workflow import repair

TOOLS = [
    "rentgen_draft_start",
    "rentgen_draft_read",
    "rentgen_draft_edit",
    "rentgen_draft_check",
]


def read_file(path, limit):
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("INPUT_FILE_LIMIT")
    return raw.decode("utf-8")


async def execute(config, source_ref, instruction, model, output):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = {"PYTHONUTF8": "1"}
    if config.get("diagnostics_local_app_data"):
        env["LOCALAPPDATA"] = config["diagnostics_local_app_data"]
    args = [
        "-I",
        "-m",
        "rentgen_core.stdio_mcp",
        "--registry",
        config["registry"],
        "--project",
        config["project_id"],
    ]
    for tool in TOOLS:
        args.extend(["--allow-tool", tool])
    parameters = StdioServerParameters(
        command=config["python"], args=args, env=env, cwd=str(output)
    )
    with (output / "events.jsonl").open("x", encoding="utf-8") as journal:

        def record(event):
            journal.write(
                json.dumps(
                    {"at": datetime.now(timezone.utc).isoformat(), **event},
                    ensure_ascii=False,
                )
                + "\n"
            )
            journal.flush()
            os.fsync(journal.fileno())
            print(json.dumps({"phase": event["phase"]}), flush=True)

        try:
            with anyio.fail_after(420):
                with (output / "mcp.log").open("x", encoding="utf-8") as log:
                    async with stdio_client(parameters, errlog=log) as (reader, writer):
                        async with ClientSession(reader, writer) as session:
                            await session.initialize()

                            async def call(name, arguments):
                                if (
                                    name not in TOOLS
                                    or arguments["project_id"] != config["project_id"]
                                ):
                                    raise ValueError("REPAIR_TOOL_SCOPE")
                                with anyio.fail_after(80):
                                    result = await session.call_tool(name, arguments)
                                document = result.structuredContent
                                if (
                                    result.isError
                                    or type(document) is not dict
                                    or "error" in document
                                ):
                                    code = (document or {}).get("error", {}).get("code")
                                    raise ValueError(
                                        code
                                        if type(code) is str
                                        and re.fullmatch(r"[A-Z][A-Z0-9_]{1,80}", code)
                                        else "MCP_REPAIR_FAILED"
                                    )
                                return document["result"]

                            report = await repair(
                                call, source_ref, instruction, model, record
                            )
        except BaseException as exc:
            # Exception groups may be produced while SDK task groups shut down.
            leaf = exc
            while isinstance(leaf, BaseExceptionGroup) and leaf.exceptions:
                leaf = leaf.exceptions[0]
            code = str(leaf)
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,80}", code):
                code = (
                    "REPAIR_INTERRUPTED"
                    if isinstance(leaf, (KeyboardInterrupt, TimeoutError))
                    else "REPAIR_FAILED"
                )
            report = {
                "status": "failed",
                "error": code,
                "tests": {"status": "not_run"},
                "apply": {"status": "unavailable"},
            }
            record({"phase": "failed", "error": code})
        with (output / "result.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        return report


def validate_profile(config, installed_core, installed_mcp, executable):
    if config.get("schema") != 1 or config.get("core_version") not in {
        "0.1.0.dev7",
        "0.1.0.dev8",
    }:
        raise ValueError("Use a prepared dev7/dev8 profile")
    if installed_core != config["core_version"] or installed_mcp != "1.30.0":
        raise ValueError(
            "Installed core must match the profile exactly; MCP 1.30.0 required"
        )
    if (
        not isinstance(config.get("python"), str)
        or Path(executable).resolve() != Path(config["python"]).resolve()
    ):
        raise ValueError("Interpreter does not match the selected profile")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["profile", "source-ref", "instruction", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--think",
        action="store_true",
        help="Enable reasoning for a model that supports it",
    )
    args = parser.parse_args()
    config = strict_json(read_file(args.profile / "profile.json", 65536))
    try:
        validate_profile(
            config, version("rentgen-core"), version("mcp"), sys.executable
        )
    except ValueError as exc:
        parser.error(str(exc))
    source_ref = strict_json(read_file(args.source_ref, 32768))
    if source_ref["snapshot"]["project_id"] != config["project_id"]:
        parser.error("SourceRef must belong to the profile project")
    instruction = read_file(args.instruction, 4096)
    output = args.output.absolute()

    def capture_content(content):
        with (output / "model-proposal.json.txt").open(
            "x", encoding="utf-8", newline=""
        ) as stream:
            stream.write(content)

    model = OllamaEditor(args.model, thinking=args.think, on_content=capture_content)
    output.mkdir(parents=True, exist_ok=False)
    report = anyio.run(execute, config, source_ref, instruction, model, output)
    print(
        json.dumps({"status": report["status"], "result": str(output / "result.json")})
    )
    return 0 if report["status"] == "analysis_clean" else 1


if __name__ == "__main__":
    raise SystemExit(main())
