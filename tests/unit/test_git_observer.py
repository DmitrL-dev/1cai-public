"""Committed Git evidence and explicit complete-report finding transitions."""

from dataclasses import replace
import importlib
import subprocess

import pytest


def api():
    assert importlib.util.find_spec("rentgen_core.git_observer") is not None
    return importlib.import_module("rentgen_core.git_observer")


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "--initial-branch=main")
    git(tmp_path, "config", "user.name", "Observer test")
    git(tmp_path, "config", "user.email", "observer@example.invalid")
    (tmp_path / "Module.bsl").write_text("baseline\n", encoding="utf-8")
    git(tmp_path, "add", "Module.bsl")
    git(tmp_path, "commit", "-m", "baseline")
    return tmp_path


def test_probe_reads_commit_and_branch_without_changing_repository(repository):
    module = api()
    before = git(repository, "status", "--porcelain")
    observation = module.observe_git(repository)
    assert observation.repository == str(repository.resolve())
    assert observation.commit == git(repository, "rev-parse", "HEAD")
    assert observation.ref == "refs/heads/main"
    assert git(repository, "status", "--porcelain") == before
    assert module.observe_git(repository) == observation


def test_probe_handles_worktree_and_detached_head(repository, tmp_path):
    module = api()
    worktree = tmp_path.parent / (tmp_path.name + "-worktree")
    git(repository, "worktree", "add", "--detach", str(worktree), "HEAD")
    observed = module.observe_git(worktree)
    assert observed.repository == str(worktree.resolve())
    assert observed.ref is None
    assert observed.commit == git(repository, "rev-parse", "HEAD")


@pytest.mark.parametrize("staged", [False, True])
def test_probe_rejects_modified_tracked_files(repository, staged):
    module = api()
    (repository / "Module.bsl").write_text("changed\n", encoding="utf-8")
    if staged:
        git(repository, "add", "Module.bsl")
    with pytest.raises(module.CoreError, match="tracked"):
        module.observe_git(repository)


def test_probe_is_committed_scope_and_ignores_untracked_files(repository):
    module = api()
    (repository / "scratch.bsl").write_text("scratch", encoding="utf-8")
    assert module.observe_git(repository).commit == git(repository, "rev-parse", "HEAD")


def test_probe_sees_new_commit_and_ignores_inherited_git_directory(
    repository, monkeypatch
):
    module = api()
    first = module.observe_git(repository)
    git(repository, "commit", "--allow-empty", "-m", "next")
    monkeypatch.setenv("GIT_DIR", str(repository / "wrong.git"))
    second = module.observe_git(repository)
    assert second.commit != first.commit
    assert second.ref == first.ref


def test_probe_rejects_visible_head_race(repository, monkeypatch):
    module = api()
    real_run = subprocess.run
    reads = 0

    def changing_head(argv, **kwargs):
        nonlocal reads
        result = real_run(argv, **kwargs)
        if "HEAD^{commit}" in argv:
            reads += 1
            if reads == 2:
                result.stdout = b"b" * 40 + b"\n"
        return result

    monkeypatch.setattr(subprocess, "run", changing_head)
    with pytest.raises(module.CoreError) as error:
        module.observe_git(repository)
    assert error.value.code == "GIT_HEAD_CHANGED"


def test_probe_timeout_is_explicit(repository, monkeypatch):
    module = api()

    def timeout(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(module.CoreError) as error:
        module.observe_git(repository)
    assert error.value.code == "GIT_PROBE_FAILED"


def test_probe_rejects_non_utf8_git_output(repository, monkeypatch):
    module = api()

    class Result:
        returncode = 0
        stdout = b"\xff"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Result())
    with pytest.raises(module.CoreError) as error:
        module.observe_git(repository)
    assert error.value.code == "GIT_PROBE_FAILED"


def test_probe_rejects_unborn_head_and_non_root(tmp_path, repository):
    module = api()
    empty = tmp_path / "empty"
    empty.mkdir()
    git(empty, "init")
    with pytest.raises(module.CoreError):
        module.observe_git(empty)
    child = repository / "child"
    child.mkdir()
    with pytest.raises(module.CoreError, match="root"):
        module.observe_git(child)


def report(module, commit="a", findings=None, **changes):
    value = module.FindingReport(
        observation=module.GitObservation("repository", commit * 40, "refs/heads/main"),
        profile_id="analyzer-config-v1",
        scope_id="all-committed-bsl-v1",
        complete=True,
        findings=tuple(findings if findings is not None else [finding(module)]),
    )
    return replace(value, **changes)


def finding(module, **changes):
    return module.Finding(
        **dict(
            {
                "rule": "Rule1",
                "path": "Module.bsl",
                "anchor": "Procedure1:statement1",
                "message": "Diagnostic",
                "line": 3,
            },
            **changes,
        )
    )


def test_lifecycle_baseline_repeat_persist_resolve_and_reopen():
    module = api()
    first = module.reconcile_findings(None, report(module))
    assert first.events[0].kind == "new"
    assert first.state.records[0].first_seen == "a" * 40
    repeated = module.reconcile_findings(first.state, report(module))
    assert repeated.state == first.state
    assert repeated.events == ()
    moved = finding(module, line=7, message="Translated diagnostic")
    second = module.reconcile_findings(first.state, report(module, "b", [moved]))
    assert second.events == ()
    assert second.state.records[0].finding.line == 7
    assert second.state.records[0].last_seen == "b" * 40
    resolved = module.reconcile_findings(second.state, report(module, "c", []))
    assert resolved.events[0].kind == "resolved"
    assert resolved.state.records[0].resolved_at == "c" * 40
    reopened = module.reconcile_findings(resolved.state, report(module, "d"))
    assert reopened.events[0].kind == "reopened"
    assert reopened.state.records[0].first_seen == "a" * 40
    assert reopened.state.records[0].resolved_at is None


def test_incomplete_report_never_resolves_findings():
    module = api()
    first = module.reconcile_findings(None, report(module))
    with pytest.raises(module.CoreError, match="complete"):
        module.reconcile_findings(first.state, report(module, "b", [], complete=False))
    assert first.state.records[0].resolved_at is None


def test_resolved_findings_remain_resolved_without_repeat_events():
    module = api()
    first = module.reconcile_findings(None, report(module))
    resolved = module.reconcile_findings(first.state, report(module, "b", []))
    later = module.reconcile_findings(resolved.state, report(module, "c", []))
    assert later.events == ()
    assert later.state.records == resolved.state.records


@pytest.mark.parametrize(
    "changes",
    [
        {"rule": ""},
        {"anchor": ""},
        {"line": 0},
        {"line": True},
        {"message": "x" * 4097},
    ],
)
def test_malformed_finding_is_rejected(changes):
    module = api()
    with pytest.raises(module.CoreError, match="finding"):
        module.reconcile_findings(
            None, report(module, findings=[finding(module, **changes)])
        )


@pytest.mark.parametrize(
    "changes", [{"profile_id": ""}, {"scope_id": ""}, {"complete": "true"}]
)
def test_report_requires_explicit_complete_context(changes):
    module = api()
    with pytest.raises(module.CoreError):
        module.reconcile_findings(None, report(module, **changes))


@pytest.mark.parametrize("change", ["repository", "ref", "profile_id", "scope_id"])
def test_different_context_requires_a_separate_baseline(change):
    module = api()
    first = module.reconcile_findings(None, report(module))
    next_report = report(module, "b", [])
    if change in {"repository", "ref"}:
        next_report = replace(
            next_report,
            observation=replace(next_report.observation, **{change: "other"}),
        )
    else:
        next_report = replace(next_report, **{change: "other"})
    with pytest.raises(module.CoreError, match="baseline"):
        module.reconcile_findings(first.state, next_report)


def test_conflicting_replay_and_duplicate_identities_are_rejected():
    module = api()
    first = module.reconcile_findings(None, report(module))
    with pytest.raises(module.CoreError, match="same commit"):
        module.reconcile_findings(first.state, report(module, findings=[]))
    with pytest.raises(module.CoreError, match="Duplicate"):
        module.reconcile_findings(
            None, report(module, findings=[finding(module), finding(module, line=8)])
        )


def test_result_order_is_deterministic_and_history_is_bounded():
    module = api()
    a, b = finding(module, anchor="a"), finding(module, anchor="b")
    assert module.reconcile_findings(
        None, report(module, findings=[a, b])
    ) == module.reconcile_findings(None, report(module, findings=[b, a]))
    first = module.reconcile_findings(None, report(module, findings=[a]), max_records=1)
    with pytest.raises(module.CoreError, match="limit"):
        module.reconcile_findings(first.state, report(module, "b", [b]), max_records=1)


@pytest.mark.parametrize(
    "path",
    [
        "../Module.bsl",
        "/Module.bsl",
        "C:/Module.bsl",
        "a\\Module.bsl",
        "./Module.bsl",
        "a//Module.bsl",
    ],
)
def test_finding_paths_must_be_canonical_repository_relative_paths(path):
    module = api()
    with pytest.raises(module.CoreError, match="path"):
        module.reconcile_findings(
            None, report(module, findings=[finding(module, path=path)])
        )
