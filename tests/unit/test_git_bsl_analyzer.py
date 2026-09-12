"""Git BSL analyzer reads exact blobs and rejects incomplete adapter output."""

import hashlib
import os
import subprocess

import pytest

from rentgen_core.diagnostics import (
    BslAnalysis,
    BslDiagnostic,
    BslPosition,
    BSL_CONFIG_SHA256,
    BSL_PROFILE_ID,
    BSL_RUNTIME_MANIFEST_SHA256,
)
from rentgen_core.errors import CoreError
from rentgen_core.git_observer import observe_git
from rentgen_diagnostics.git_bsl_analyzer import (
    BslGitAnalyzer,
    PROFILE_ID,
    SCOPE_ID,
)


pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="Git analyzer uses Windows runtime contracts"
)


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
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init", "--initial-branch=main")
    git(root, "config", "user.name", "Rentgen analyzer test")
    git(root, "config", "user.email", "analyzer@example.invalid")
    (root / "Module.bsl").write_text(
        "Процедура Тест()\nКонецПроцедуры\n", encoding="utf-8"
    )
    (root / "ignored.txt").write_text("ignored\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "baseline")
    return root


class FakeAdapter:
    def __init__(self, *, complete=True):
        self.complete = complete
        self.calls = []

    def analyze(self, candidate_bytes, *, suffix, authorize):
        authorize()
        self.calls.append((candidate_bytes, suffix))
        digest = hashlib.sha256(candidate_bytes).hexdigest()
        diagnostics = (
            BslDiagnostic(
                code="DeprecatedMessage",
                severity="Warning",
                message="Используется устаревший вызов",
                start=BslPosition(0, 0),
                end=BslPosition(0, 7),
            ),
        )
        return BslAnalysis(
            status="completed" if self.complete else "failed",
            reason=None if self.complete else "BSL_PROCESS_FAILED",
            candidate_sha256=digest,
            candidate_size_bytes=len(candidate_bytes),
            profile_id=BSL_PROFILE_ID,
            runtime_manifest_sha256=BSL_RUNTIME_MANIFEST_SHA256,
            runtime_verified=True,
            config_sha256=BSL_CONFIG_SHA256,
            scope="single_module_isolated",
            coverage="exact_one" if self.complete else "incomplete",
            diagnostics=diagnostics if self.complete else (),
            diagnostics_complete=self.complete,
            total_diagnostics=len(diagnostics) if self.complete else None,
            report_sha256="a" * 64 if self.complete else None,
            stdout_sha256="b" * 64 if self.complete else None,
            stderr_sha256="c" * 64 if self.complete else None,
            exit_code=0 if self.complete else None,
        )


def test_analyzer_reads_only_bsl_blobs_and_returns_bound_findings(repository):
    observation = observe_git(repository)
    calls = []
    analyzer = BslGitAnalyzer(
        FakeAdapter(),
        lambda: calls.append("authorized"),
    )

    report = analyzer(observation)

    assert report.observation == observation
    assert report.profile_id == PROFILE_ID
    assert report.scope_id == SCOPE_ID
    assert report.complete is True
    assert len(report.findings) == 1
    assert report.findings[0].path == "Module.bsl"
    assert report.findings[0].rule == "bsl/DeprecatedMessage"
    assert report.findings[0].line == 1
    assert calls


def test_incomplete_bsl_result_is_not_published(repository):
    observation = observe_git(repository)
    with pytest.raises(CoreError) as error:
        BslGitAnalyzer(FakeAdapter(complete=False), lambda: None)(observation)
    assert error.value.code == "GIT_ANALYZER_INCOMPLETE"


def test_dirty_repository_is_rejected_before_analysis(repository):
    observation = observe_git(repository)
    (repository / "Module.bsl").write_text("dirty\n", encoding="utf-8")
    adapter = FakeAdapter()
    with pytest.raises(CoreError) as error:
        BslGitAnalyzer(adapter, lambda: None)(observation)
    assert error.value.code == "GIT_TRACKED_DIRTY"
    assert adapter.calls == []


def test_module_limit_is_enforced(repository):
    (repository / "Second.os").write_text(
        "Процедура Тест()\nКонецПроцедуры\n", encoding="utf-8"
    )
    git(repository, "add", "Second.os")
    git(repository, "commit", "-m", "second")
    observation = observe_git(repository)
    with pytest.raises(CoreError) as error:
        BslGitAnalyzer(FakeAdapter(), lambda: None, max_files=1)(observation)
    assert error.value.code == "GIT_ANALYZER_LIMIT"
