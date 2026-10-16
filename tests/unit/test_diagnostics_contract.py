"""ANALYZER-01: unavailable or partial analyzer output never becomes a clean check.

Constructed DTOs and report bytes only; no Java, BSL-LS process or 1C runtime.
"""
from contextlib import contextmanager
from dataclasses import asdict, replace
import hashlib
import json
from types import SimpleNamespace

import pytest

from rentgen_core import diagnostics
from rentgen_core.diagnostics import (
    BSL_CONFIG_SHA256,
    BSL_PROFILE_ID,
    BSL_RUNTIME_MANIFEST_SHA256,
    BslAnalysis,
    BslDiagnostic,
    BslPosition,
)
from rentgen_diagnostics import bsl_language_server as bsl

CANDIDATE = "Процедура Тест()\r\nКонецПроцедуры\r\n".encode()
WARNING = BslDiagnostic(
    "UnusedVariable", "Warning", "Не используется", BslPosition(0, 0), BslPosition(0, 9)
)
PERMISSIONS = {"project:read", "source:edit", "analysis:run"}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def completed(**changes):
    value = BslAnalysis(
        status="completed",
        reason=None,
        candidate_sha256=_sha(CANDIDATE),
        candidate_size_bytes=len(CANDIDATE),
        profile_id=BSL_PROFILE_ID,
        runtime_manifest_sha256=BSL_RUNTIME_MANIFEST_SHA256,
        runtime_verified=True,
        config_sha256=BSL_CONFIG_SHA256,
        scope="single_module_isolated",
        coverage="exact_one",
        diagnostics=(),
        diagnostics_complete=True,
        total_diagnostics=0,
        report_sha256="a" * 64,
        stdout_sha256="b" * 64,
        stderr_sha256="c" * 64,
        exit_code=0,
    )
    return replace(value, **changes)


def unavailable(**changes):
    value = completed(
        status="failed",
        reason="BSL_RUNTIME_UNAVAILABLE",
        runtime_verified=False,
        coverage="not_run",
        diagnostics_complete=False,
        total_diagnostics=None,
        report_sha256=None,
        stdout_sha256=None,
        stderr_sha256=None,
        exit_code=None,
    )
    return replace(value, **changes)


class Adapter:
    def __init__(self, analysis):
        self.analysis, self.calls = analysis, []

    def analyze(self, candidate_bytes, *, suffix, authorize):
        authorize()
        self.calls.append((candidate_bytes, suffix))
        return self.analysis


def diagnose(adapter, raw=CANDIDATE):
    grants = []

    class Transaction:
        def require_all(self, permissions):
            grants.append(set(permissions))

    @contextmanager
    def transaction(principal):
        assert principal == "owner"
        yield Transaction()

    ctx = SimpleNamespace(
        principal="owner", state=SimpleNamespace(transaction=transaction)
    )
    proposal = SimpleNamespace(
        replacement_bytes=raw,
        content_id="d" * 64,
        source_ref=SimpleNamespace(relative_path="CommonModules/Test/Ext/Module.bsl"),
    )
    result = diagnostics._diagnose_validated(ctx, proposal, adapter)
    assert grants and all(grant == PERMISSIONS for grant in grants)
    assert result.proposal_content_id == "d" * 64
    assert (result.tests_status, result.apply_status) == ("not_run", "unavailable")
    return result


def test_only_a_complete_verified_pinned_report_is_clean():
    adapter = Adapter(completed())
    result = diagnose(adapter)
    assert adapter.calls == [(CANDIDATE, ".bsl")]
    assert result.diagnostics_status == "clean"
    assert result.analysis is adapter.analysis
    present = diagnose(Adapter(completed(diagnostics=(WARNING,), total_diagnostics=1)))
    assert present.diagnostics_status == "diagnostics_present"
    assert present.analysis.diagnostics == (WARNING,)


@pytest.mark.parametrize(
    "analysis, status",
    [
        (unavailable(), "failed"),
        (
            unavailable(
                reason="BSL_TIMEOUT", coverage="incomplete", stdout_sha256="b" * 64
            ),
            "failed",
        ),
        (
            unavailable(status="unsupported", reason="BSL_PLATFORM_UNSUPPORTED"),
            "unsupported",
        ),
    ],
    ids=["runtime_unavailable", "timeout", "platform_unsupported"],
)
def test_unavailable_or_unsupported_analyzer_is_never_clean(analysis, status):
    result = diagnose(Adapter(analysis))
    assert result.diagnostics_status == status
    assert result.analysis is analysis
    assert result.analysis.diagnostics == ()
    assert result.analysis.diagnostics_complete is False
    assert result.analysis.total_diagnostics is None


PARTIAL_OR_UNPINNED = {
    "incomplete_rows": lambda: completed(
        diagnostics=(WARNING,), diagnostics_complete=False, total_diagnostics=200
    ),
    "incomplete_empty": lambda: completed(diagnostics_complete=False),
    "truncated_total": lambda: completed(total_diagnostics=5),
    "missing_total": lambda: completed(total_diagnostics=None),
    "coverage_incomplete": lambda: completed(coverage="incomplete"),
    "runtime_unverified": lambda: completed(runtime_verified=False),
    "nonzero_exit": lambda: completed(exit_code=1),
    "missing_exit": lambda: completed(exit_code=None),
    "missing_report_hash": lambda: completed(report_sha256=None),
    "failure_reason": lambda: completed(reason="BSL_PROCESS_FAILED"),
    "candidate_hash": lambda: completed(candidate_sha256="0" * 64),
    "missing_candidate_hash": lambda: completed(candidate_sha256=None),
    "candidate_size": lambda: completed(candidate_size_bytes=len(CANDIDATE) + 1),
    "profile": lambda: completed(profile_id="bsl-ls-0.24.2-default"),
    "missing_profile": lambda: completed(profile_id=None),
    "config": lambda: completed(config_sha256="0" * 64),
    "missing_config": lambda: completed(config_sha256=None),
    "runtime_manifest": lambda: completed(runtime_manifest_sha256="0" * 64),
    "missing_runtime_manifest": lambda: completed(runtime_manifest_sha256=None),
    "failed_with_rows": lambda: unavailable(diagnostics=(WARNING,)),
    "failed_claims_complete": lambda: unavailable(diagnostics_complete=True),
    "failed_with_total": lambda: unavailable(total_diagnostics=0),
    "failed_without_reason": lambda: unavailable(reason=None),
    "unsupported_verified": lambda: unavailable(
        status="unsupported", reason="BSL_PLATFORM_UNSUPPORTED", runtime_verified=True
    ),
    "unsupported_partial": lambda: unavailable(
        status="unsupported", reason="BSL_PLATFORM_UNSUPPORTED", coverage="incomplete"
    ),
    "not_a_dto": lambda: SimpleNamespace(**asdict(completed())),
}


@pytest.mark.parametrize("case", sorted(PARTIAL_OR_UNPINNED))
def test_partial_or_unpinned_result_becomes_an_invalid_failure(case):
    analysis = PARTIAL_OR_UNPINNED[case]()
    result = diagnose(Adapter(analysis))
    assert result.diagnostics_status == "failed"
    replaced = result.analysis
    assert replaced is not analysis
    assert replaced.status == "failed"
    assert replaced.reason == "BSL_ADAPTER_RESULT_INVALID"
    assert replaced.coverage == "incomplete"
    assert replaced.runtime_verified is False
    assert replaced.diagnostics == ()
    assert replaced.diagnostics_complete is False
    assert replaced.total_diagnostics is None
    assert (replaced.report_sha256, replaced.stdout_sha256) == (None, None)
    # Core recomputes the candidate binding from exact proposal bytes. The fixed
    # profile identity is the expected profile only, never a verification claim.
    assert replaced.candidate_sha256 == _sha(CANDIDATE)
    assert replaced.candidate_size_bytes == len(CANDIDATE)
    assert replaced.profile_id == BSL_PROFILE_ID
    assert diagnostics._analysis_valid(replaced, CANDIDATE)


def test_candidate_binding_follows_the_exact_proposal_bytes():
    other = CANDIDATE.replace("Тест".encode(), "Другой".encode())
    result = diagnose(Adapter(completed()), raw=other)
    assert result.diagnostics_status == "failed"
    assert result.analysis.candidate_sha256 == _sha(other)
    assert result.analysis.reason == "BSL_ADAPTER_RESULT_INVALID"


def _adapter(tmp_path):
    profile = bsl.BslRuntimeProfile(
        tmp_path / "missing-java", tmp_path / "missing.jar", tmp_path
    )
    return bsl.BslLanguageServerAdapter(profile)


def test_adapter_without_runtime_never_reports_clean(tmp_path):
    # Non-Windows hosts stop at the platform gate; Windows stops at the absent
    # pinned runtime. Neither path may execute Java or claim diagnostics.
    adapter = Adapter(
        _adapter(tmp_path).analyze(CANDIDATE, suffix=".bsl", authorize=lambda: None)
    )
    result = diagnose(adapter)
    assert result.analysis is adapter.analysis
    assert result.diagnostics_status in {"unsupported", "failed"}
    assert result.analysis.reason in {
        "BSL_PLATFORM_UNSUPPORTED",
        "BSL_RUNTIME_UNAVAILABLE",
    }
    assert result.analysis.coverage == "not_run"
    assert result.analysis.runtime_verified is False
    assert result.analysis.diagnostics == ()
    assert result.analysis.diagnostics_complete is False


@pytest.mark.parametrize("execution_possible", [False, True])
def test_adapter_drops_rows_from_any_unfinished_attempt(tmp_path, execution_possible):
    state = bsl._AnalysisState(0.0, execution_possible=execution_possible)
    if execution_possible:
        state.stdout_sha256 = "b" * 64
    value = _adapter(tmp_path)._result(
        CANDIDATE, state, "failed", "BSL_TIMEOUT", diagnostics=(WARNING,)
    )
    assert value.coverage == ("incomplete" if execution_possible else "not_run")
    assert value.diagnostics == ()
    assert value.diagnostics_complete is False
    assert value.total_diagnostics is None
    assert value.candidate_sha256 == _sha(CANDIDATE)
    assert (value.profile_id, value.config_sha256, value.runtime_manifest_sha256) == (
        BSL_PROFILE_ID,
        BSL_CONFIG_SHA256,
        BSL_RUNTIME_MANIFEST_SHA256,
    )
    assert diagnose(Adapter(value)).diagnostics_status == "failed"


def _report(directory, *, files=1, diagnostics=1):
    uri = (directory / "Candidate.bsl").as_uri()
    row = {
        "code": "UnusedVariable",
        "codeDescription": {
            "href": "https://1c-syntax.github.io/bsl-language-server/en/diagnostics/"
            "UnusedVariable"
        },
        "data": None,
        "message": "Не используется",
        "range": {
            "start": {"line": 0, "character": 0},
            "end": {"line": 0, "character": 9},
        },
        "relatedInformation": None,
        "severity": "Warning",
        "source": "bsl-language-server",
        "tags": [],
    }
    metrics = {
        "procedures": 1,
        "functions": 0,
        "lines": 3,
        "ncloc": 2,
        "comments": 0,
        "statements": 0,
        "cognitiveComplexity": 0,
        "cyclomaticComplexity": 1,
        "nclocData": [1, 2],
        "covlocData": None,
    }
    info = {
        "path": uri,
        "mdoRef": uri,
        "diagnostics": [row] * diagnostics,
        "metrics": metrics,
    }
    value = {
        "date": "2026-10-16 12:00:00",
        "sourceDir": str(directory),
        "fileinfos": [info] * files,
    }
    return json.dumps(value, ensure_ascii=False).encode()


@pytest.mark.parametrize(
    "files, rows, code",
    [
        (0, 1, "BSL_COVERAGE_MISMATCH"),
        (2, 1, "BSL_COVERAGE_MISMATCH"),
        (1, 129, "BSL_RESOURCE_LIMIT"),
    ],
    ids=["no_module", "extra_module", "truncated_rows"],
)
def test_report_decoder_refuses_partial_or_foreign_coverage(
    tmp_path, files, rows, code
):
    decoded = bsl.decode_report(
        _report(tmp_path), CANDIDATE, expected_directory=tmp_path, suffix=".bsl"
    )
    assert decoded == (WARNING,)
    with pytest.raises(bsl.ReportFailure) as error:
        bsl.decode_report(
            _report(tmp_path, files=files, diagnostics=rows),
            CANDIDATE,
            expected_directory=tmp_path,
            suffix=".bsl",
        )
    assert error.value.code == code
