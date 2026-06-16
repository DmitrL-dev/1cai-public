"""Security regression tests for the local test-runner execution surface.

Covers the four adversarial-review findings that were remediated:

1. Test execution is gated behind the ``RENTGEN_ENABLE_TEST_EXECUTION`` kill
   switch (default OFF) — the execute path refuses and never spawns.
2. Only allow-listed runner basenames may ever be spawned.
3. Caller-supplied ``result_path`` / ``manifest_path`` are confined under the
   repo test/evidence roots (or the OS temp dir), killing arbitrary file read
   and RCE-by-manifest.
4. The EDT-MCP risky gate no longer self-authorizes privileged/destructive ops
   from a free-text reason; a validated approval record is required by default.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.rentgen import test_runners
from src.services.rentgen.test_runners import (
    ALLOWED_EXECUTABLE_BASENAMES,
    TEST_EXECUTION_FLAG,
    TestExecutionDisabled,
    _assert_executable_allowed,
    _confine_path,
    build_runner_plan,
    import_result_file,
    run_test_adapter,
)
from src.services.edt_mcp_bridge import guard_edt_mcp_tool_call


ROOT = test_runners.ROOT


# --------------------------------------------------------------------------- #
# Finding 1: kill switch (default OFF) — execution refused, never spawns.      #
# --------------------------------------------------------------------------- #
def test_execute_refused_when_flag_off(monkeypatch, tmp_path):
    monkeypatch.delenv(TEST_EXECUTION_FLAG, raising=False)
    store = tmp_path / "runs.json"
    graph = tmp_path / "graph.json"

    with pytest.raises(TestExecutionDisabled) as excinfo:
        run_test_adapter(
            "yaxunit",
            execute=True,
            allow_external=True,
            output_dir=str(tmp_path / "out"),
            path=store,
            artifact_path=graph,
        )

    assert TEST_EXECUTION_FLAG in str(excinfo.value)
    # The kill-switch error doubles as a ValueError so existing value-based
    # handlers (MCP) refuse cleanly, and as a PermissionError so the HTTP layer
    # maps it to 403.
    assert isinstance(excinfo.value, PermissionError)
    assert isinstance(excinfo.value, ValueError)


def test_execute_refused_for_falsey_flag_values(monkeypatch, tmp_path):
    for value in ("", "0", "false", "no", "off"):
        monkeypatch.setenv(TEST_EXECUTION_FLAG, value)
        with pytest.raises(TestExecutionDisabled):
            run_test_adapter(
                "yaxunit",
                execute=True,
                allow_external=True,
                output_dir=str(tmp_path / "out"),
                path=tmp_path / "runs.json",
                artifact_path=tmp_path / "graph.json",
            )


def test_dry_run_still_works_with_flag_off(monkeypatch, tmp_path):
    """Planning / dry-run must NOT spawn and must NOT be gated by the flag."""

    monkeypatch.delenv(TEST_EXECUTION_FLAG, raising=False)
    result = run_test_adapter(
        "yaxunit",
        execute=False,
        output_dir=str(tmp_path / "out"),
        path=tmp_path / "runs.json",
        artifact_path=tmp_path / "graph.json",
    )
    assert result["executed"] is False
    assert result["run"]["dry_run"] is True


# --------------------------------------------------------------------------- #
# Finding 2: executable allow-list.                                           #
# --------------------------------------------------------------------------- #
def test_assert_executable_allowed_accepts_known_runners():
    # No exception for legitimate runners (basename match, case-insensitive).
    _assert_executable_allowed(["python", "x.py"])
    _assert_executable_allowed([r"C:\Python311\python.exe", "x.py"])
    _assert_executable_allowed(["/usr/bin/oscript", "runner.os"])
    _assert_executable_allowed(["vanessa-runner", "run"])


@pytest.mark.parametrize(
    "binary",
    [
        "cmd.exe",
        "powershell.exe",
        "/bin/sh",
        "bash",
        "calc.exe",
        r"C:\Windows\System32\cmd.exe",
        "node",
        "curl",
    ],
)
def test_assert_executable_allowed_rejects_arbitrary_binaries(binary):
    with pytest.raises(ValueError):
        _assert_executable_allowed([binary, "-c", "whatever"])


def test_assert_executable_allowed_rejects_empty_command():
    with pytest.raises(ValueError):
        _assert_executable_allowed([])


def test_allow_list_contains_only_test_runners():
    # Guard against accidental widening of the allow-list to a general shell.
    forbidden = {"cmd.exe", "powershell.exe", "sh", "bash", "node", "curl", "wget"}
    assert not (forbidden & {b.casefold() for b in ALLOWED_EXECUTABLE_BASENAMES})


# --------------------------------------------------------------------------- #
# Finding 3: path confinement (arbitrary file read + RCE-by-manifest).        #
# --------------------------------------------------------------------------- #
def test_confine_path_allows_repo_tests_root():
    inside = ROOT / "tests" / "bsl" / "testplan.json"
    assert _confine_path(inside, label="manifest_path") == inside.resolve()


def test_confine_path_allows_os_temp(tmp_path):
    # pytest's tmp_path lives under the OS temp dir, an allowed scratch root.
    p = tmp_path / "report.xml"
    p.write_text("<testsuite/>", encoding="utf-8")
    assert _confine_path(p, label="result_path") == p.resolve()


@pytest.mark.parametrize(
    "bad",
    [
        str(ROOT / "artifacts" / "playwright-dev-auth.json"),  # the documented exfil target
        str(ROOT / "src" / "services" / "edt_mcp_bridge.py"),
        str(ROOT / ".sentinel_key"),
        str(ROOT / "tests" / ".." / "artifacts" / "playwright-dev-auth.json"),  # traversal
    ],
)
def test_confine_path_rejects_outside_allowed_roots(bad):
    with pytest.raises(ValueError) as excinfo:
        _confine_path(bad, label="result_path")
    assert "outside the allowed" in str(excinfo.value)


def test_import_result_file_rejects_path_outside_roots():
    """The arbitrary-file-read sink refuses the documented exfil target."""

    target = ROOT / "artifacts" / "playwright-dev-auth.json"
    with pytest.raises(ValueError):
        import_result_file(str(target))


def test_import_result_file_rejects_traversal():
    # Traversal out of an allowed root (tests/) into a sensitive sibling
    # (artifacts/) must be rejected with ValueError before any read is attempted.
    traversal = ROOT / "tests" / ".." / "artifacts" / "playwright-dev-auth.json"
    with pytest.raises(ValueError) as excinfo:
        import_result_file(str(traversal))
    assert "outside the allowed" in str(excinfo.value)


def test_build_plan_rejects_manifest_outside_roots():
    with pytest.raises(ValueError):
        build_runner_plan(
            "bsl_manifest",
            manifest_path=str(ROOT / "artifacts" / "playwright-dev-auth.json"),
        )


def test_build_plan_confines_manifest_inside_roots():
    plan = build_runner_plan(
        "bsl_manifest",
        manifest_path=str(ROOT / "tests" / "bsl" / "testplan.json"),
    )
    assert plan["adapter"] == "bsl_manifest"
    assert Path(plan["command"][0]).name.casefold() in {
        b.casefold() for b in ALLOWED_EXECUTABLE_BASENAMES
    }


# --------------------------------------------------------------------------- #
# Finding 3 (cont.): request-controlled env / cwd / extra_args are dropped.    #
# --------------------------------------------------------------------------- #
def test_plan_drops_request_env_cwd_and_extra_args():
    plan = build_runner_plan(
        "yaxunit",
        env={"EVIL": "1"},
        cwd=str(ROOT.parent),  # would also be an escape; must be ignored
        extra_args=["; rm -rf /", "--inject"],
    )
    assert plan["env"] == {}
    assert plan["cwd"] == str(ROOT)
    # The injected trailing argv must not appear in the final command.
    assert "; rm -rf /" not in plan["command"]
    assert "--inject" not in plan["command"]
    assert set(plan["dropped_request_inputs"]) == {"env", "cwd", "extra_args"}


# --------------------------------------------------------------------------- #
# Finding 4: EDT-MCP risky gate no longer self-authorizes privileged ops.     #
# --------------------------------------------------------------------------- #
def test_privileged_execute_op_rejects_free_text_reason(monkeypatch):
    """A long free-text reason must NOT authorize a destructive execute op."""

    monkeypatch.delenv("EDT_MCP_ALLOW_INLINE_PRIVILEGED", raising=False)
    monkeypatch.delenv("EDT_MCP_REQUIRE_APPROVAL_RECORD", raising=False)

    decision = guard_edt_mcp_tool_call(
        "delete_infobase",  # execute risk / destructive
        confirm=True,
        actor="attacker",
        approval_reason="please run this it is definitely fine and authorized",
    )

    assert decision["allowed"] is False
    assert decision["classification"]["risk"] == "execute"
    assert "approval_id" in decision["policy"]["missing"]
    assert decision["policy"]["requires_approval_record"] is True
    assert decision["policy"]["privileged"] is True


def test_privileged_inline_override_only_relaxes_in_dev(monkeypatch):
    monkeypatch.setenv("EDT_MCP_ALLOW_INLINE_PRIVILEGED", "1")
    monkeypatch.delenv("EDT_MCP_REQUIRE_APPROVAL_RECORD", raising=False)

    decision = guard_edt_mcp_tool_call(
        "delete_infobase",
        confirm=True,
        actor="developer",
        approval_reason="local dev teardown of throwaway infobase",
    )

    # With the explicit dev override, the inline reason is accepted again.
    assert decision["allowed"] is True
    assert decision["policy"]["approval_source"] == "inline"


def test_non_privileged_write_still_accepts_inline_reason(monkeypatch):
    """Back-compat: plain write ops keep the inline-reason path by default."""

    monkeypatch.delenv("EDT_MCP_ALLOW_INLINE_PRIVILEGED", raising=False)
    monkeypatch.delenv("EDT_MCP_REQUIRE_APPROVAL_RECORD", raising=False)

    decision = guard_edt_mcp_tool_call(
        "write_module_source",
        confirm=True,
        actor="developer",
        approval_reason="Approved for the focused unit test change.",
    )
    assert decision["allowed"] is True
    assert decision["policy"]["privileged"] is False
