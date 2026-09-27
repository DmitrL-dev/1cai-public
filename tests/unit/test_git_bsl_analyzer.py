"""Git BSL analyzer reads exact blobs and rejects incomplete adapter output."""

import hashlib
import os
import subprocess
from dataclasses import replace

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


FAILURE_REASONS = (
    "BSL_CLEANUP_FAILED", "BSL_COORDINATES_UNSUPPORTED", "BSL_COVERAGE_MISMATCH",
    "BSL_ENCODING_UNSUPPORTED", "BSL_INPUT_CHANGED", "BSL_OWNER_BUSY",
    "BSL_OWNER_QUARANTINED", "BSL_PLATFORM_UNSUPPORTED", "BSL_PROCESS_FAILED",
    "BSL_REPORT_INVALID", "BSL_RESOURCE_LIMIT", "BSL_RUNTIME_MISMATCH",
    "BSL_RUNTIME_UNAVAILABLE", "BSL_SOURCE_TYPE_UNSUPPORTED", "BSL_TIMEOUT",
)


class FailureAdapter(FakeAdapter):
    def __init__(self, *, transform=lambda value: value, after=lambda: None):
        super().__init__(complete=False)
        self.transform, self.after = transform, after

    def analyze(self, *args, **kwargs):
        result = self.transform(super().analyze(*args, **kwargs))
        self.after()
        return result


def test_all_known_bound_failure_reasons_have_exact_internal_type(repository):
    from rentgen_core._git_analysis_failure import GitAnalysisFailure

    observation = observe_git(repository)
    for base in FAILURE_REASONS:
        for reason in (base, base + "_CLEANUP_FAILED"):
            adapter = FailureAdapter(transform=lambda value: replace(value, reason=reason))
            with pytest.raises(CoreError) as error:
                BslGitAnalyzer(adapter, lambda: None)(observation)
            assert type(error.value) is GitAnalysisFailure
            assert error.value.reason == reason
            assert error.value.details == {}
            assert error.value.to_dict("request") == {
                "error": {
                    "code": "GIT_ANALYZER_INCOMPLETE",
                    "message": "BSL-LS result is not bound to the committed blob",
                    "request_id": "request",
                    "details": {},
                }
            }


@pytest.mark.parametrize("status,reason", [
    ("failed", "BSL_INPUT_CHANGED"),
    ("unsupported", "BSL_PLATFORM_UNSUPPORTED"),
])
def test_valid_failed_and_unsupported_results_preserve_reason(repository, status, reason):
    from rentgen_core.diagnostics import _analysis_valid

    def transform(value):
        result = replace(value, status=status, reason=reason, coverage="not_run", runtime_verified=False)
        assert _analysis_valid(result, adapter.calls[-1][0])
        return result

    adapter = FailureAdapter(transform=transform)
    with pytest.raises(CoreError) as error:
        BslGitAnalyzer(adapter, lambda: None)(observe_git(repository))
    assert error.value.reason == reason


@pytest.mark.parametrize("updates", [
    {"candidate_sha256": "f" * 64}, {"candidate_size_bytes": 0},
    {"candidate_size_bytes": True}, {"profile_id": "other"},
    {"runtime_manifest_sha256": "f" * 64}, {"config_sha256": "f" * 64},
    {"runtime_verified": 1}, {"diagnostics_complete": 0}, {"diagnostics": []},
    {"status": "other"}, {"status": None}, {"coverage": "exact_one"},
    {"scope": "other"}, {"total_diagnostics": 0}, {"exit_code": True},
    {"reason": None}, {"reason": 1}, {"reason": "BSL_UNKNOWN"},
    {"reason": "C:\\secret\\runtime"}, {"reason": "BSL_TIMEOUT\nsecret"},
    {"reason": "BSL_" + "A" * 200},
    {"reason": "BSL_TIMEOUT_CLEANUP_FAILED_CLEANUP_FAILED"},
    {"status": "unsupported", "reason": "BSL_TIMEOUT"},
])
def test_unbound_or_invalid_failure_does_not_disclose_reason(repository, updates):
    adapter = FailureAdapter(transform=lambda value: replace(value, **updates))
    with pytest.raises(CoreError) as error:
        BslGitAnalyzer(adapter, lambda: None)(observe_git(repository))
    assert type(error.value) is CoreError
    assert error.value.code == "GIT_ANALYZER_INCOMPLETE"
    assert not hasattr(error.value, "reason")
    assert error.value.details == {}


@pytest.mark.parametrize("kind", ["subclass", "dictionary", "reason_subclass"])
def test_failure_dto_and_reason_require_exact_types(repository, kind):
    from dataclasses import asdict

    class SubAnalysis(BslAnalysis):
        pass

    class SubReason(str):
        pass

    def transform(value):
        if kind == "dictionary":
            return asdict(value)
        if kind == "reason_subclass":
            return replace(value, reason=SubReason("BSL_TIMEOUT"))
        return SubAnalysis(**asdict(value))

    with pytest.raises(CoreError) as error:
        BslGitAnalyzer(FailureAdapter(transform=transform), lambda: None)(observe_git(repository))
    assert type(error.value) is CoreError
    assert not hasattr(error.value, "reason")


@pytest.mark.parametrize("complete", [False, True])
def test_revocation_after_adapter_has_priority_over_analysis(repository, complete):
    revoked = False

    def authorize():
        if revoked:
            raise CoreError("PROJECT_FORBIDDEN", "revoked")

    class RevokingAdapter(FakeAdapter):
        def analyze(self, *args, **kwargs):
            nonlocal revoked
            result = super().analyze(*args, **kwargs)
            revoked = True
            return result

    with pytest.raises(CoreError) as error:
        BslGitAnalyzer(RevokingAdapter(complete=complete), authorize)(observe_git(repository))
    assert error.value.code == "PROJECT_FORBIDDEN"
    assert not hasattr(error.value, "reason")


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


def test_bound_incomplete_bsl_reason_is_preserved_internally(repository):
    observation = observe_git(repository)
    with pytest.raises(CoreError) as error:
        BslGitAnalyzer(FakeAdapter(complete=False), lambda: None)(observation)
    assert error.value.code == "GIT_ANALYZER_INCOMPLETE"
    assert getattr(error.value, "reason", None) == "BSL_PROCESS_FAILED"


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
