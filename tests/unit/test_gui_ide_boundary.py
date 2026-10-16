"""The read-only ZIP GUI never reaches the IDE lifecycle (GUI-IDE-BOUNDARY-01).

Static guard: the transitive import closure of the GUI modules, including lazy
imports inside functions, excludes drafts, proposals, live/workspace apply,
native execution, tests, EDT execution, capture and publication. Its HTTP API
is a closed set of read-only analysis routes.
"""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "rentgen_core"
FORBIDDEN = frozenset(
    {
        "drafts", "draft_editing", "mcp_drafts", "proposals", "proposal_live_apply",
        "metadata_live_apply", "metadata_workspace", "metadata_apply",
        "metadata_native_apply", "metadata_apply_gate", "metadata_runs",
        "metadata_preview", "native_platform", "native_process", "native_resources",
        "native_scratch", "platform_check", "platform_runs", "test_execution",
        "test_profiles", "test_run_qualification", "yaxunit_runner", "edt_execution",
        "edt_command", "edt_fixture_executor", "publication", "capture", "observer",
        "git_watcher", "stdio_mcp", "cli",
    }
)
ROUTES = frozenset(
    {
        "/api/session", "/api/job", "/api/source", "/api/search", "/api/search-start",
        "/api/search-cancel", "/api/import-start", "/api/import", "/api/cancel",
        "/api/comparison-upload", "/api/comparison-source", "/api/comparison",
        "/api/comparison-current", "/api/comparison-start", "/api/comparison-cancel",
        "/api/comparison-page", "/api/comparison-line-diff", "/api/comparison-report",
        "/api/occurrences", "/api/occurrences-start", "/api/occurrences-cancel",
        "/api/threeway", "/api/threeway-current", "/api/threeway-page",
        "/api/threeway-start", "/api/threeway-cancel", "/api/threeway-upload",
        "/api/threeway-upload-start",
    }
)


def _imports(module):
    found = set()
    for node in ast.walk(ast.parse((PACKAGE / (module + ".py")).read_text("utf-8"))):
        if isinstance(node, ast.ImportFrom):
            if node.level == 1:
                found.update(
                    [node.module.split(".")[0]] if node.module else [a.name for a in node.names]
                )
            elif node.level == 0 and (node.module or "").startswith("rentgen_core."):
                found.add(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            found.update(
                a.name.split(".")[1] for a in node.names if a.name.startswith("rentgen_core.")
            )
    return {name for name in found if (PACKAGE / (name + ".py")).exists()}


def gui_modules():
    return ["gui"] + sorted(p.stem for p in PACKAGE.glob("gui_*.py"))


def test_gui_import_closure_excludes_the_ide_lifecycle():
    seen, pending = set(), gui_modules()
    while pending:
        module = pending.pop()
        if module not in seen:
            seen.add(module)
            pending.extend(_imports(module) - seen)
    assert {"gui", "submitted_export", "rust_input"} <= seen
    assert not seen & FORBIDDEN, sorted(seen & FORBIDDEN)


def test_gui_http_api_is_a_closed_read_only_route_set():
    routes = set()
    for module in gui_modules():
        text = (PACKAGE / (module + ".py")).read_text("utf-8")
        routes.update(re.findall(r"""["'](/api/[a-z0-9-]+)["']""", text))
    assert routes == ROUTES
    assert not any(
        word in route
        for route in routes
        for word in ("apply", "draft", "proposal", "live", "native", "undo", "recover")
    )
