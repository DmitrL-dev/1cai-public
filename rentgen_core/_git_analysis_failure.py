"""Bounded internal BSL failure provenance, excluded from transport errors."""

from .errors import CoreError


_BASE_REASONS = frozenset({
    "BSL_CLEANUP_FAILED",
    "BSL_COORDINATES_UNSUPPORTED",
    "BSL_COVERAGE_MISMATCH",
    "BSL_ENCODING_UNSUPPORTED",
    "BSL_INPUT_CHANGED",
    "BSL_OWNER_BUSY",
    "BSL_OWNER_QUARANTINED",
    "BSL_PLATFORM_UNSUPPORTED",
    "BSL_PROCESS_FAILED",
    "BSL_REPORT_INVALID",
    "BSL_RESOURCE_LIMIT",
    "BSL_RUNTIME_MISMATCH",
    "BSL_RUNTIME_UNAVAILABLE",
    "BSL_SOURCE_TYPE_UNSUPPORTED",
    "BSL_TIMEOUT",
})
_REASONS = _BASE_REASONS | {reason + "_CLEANUP_FAILED" for reason in _BASE_REASONS}
_MAX_REASON = max(map(len, _REASONS))


def is_known_bsl_failure_reason(value):
    return type(value) is str and len(value) <= _MAX_REASON and value in _REASONS


class GitAnalysisFailure(CoreError):
    """Validated local diagnostic; inherited to_dict deliberately omits reason."""

    def __init__(self, reason):
        if not is_known_bsl_failure_reason(reason):
            raise ValueError("Known BSL failure reason required")
        super().__init__(
            "GIT_ANALYZER_INCOMPLETE",
            "BSL-LS result is not bound to the committed blob",
        )
        self.reason = reason


def local_failure_event(error):
    event = {"status": "fatal", "code": error.code}
    if (
        type(error) is GitAnalysisFailure
        and type(error.code) is str
        and error.code == "GIT_ANALYZER_INCOMPLETE"
        and is_known_bsl_failure_reason(getattr(error, "reason", None))
    ):
        event["analysis_failure"] = {"schema": 1, "reason": error.reason}
    return event
