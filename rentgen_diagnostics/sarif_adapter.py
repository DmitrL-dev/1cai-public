"""Read-only, fail-closed SARIF 2.1.0 import for exact Git finding reports.

This is a deliberately restricted SARIF profile, not a general schema validator.
The trusted caller attests provenance and completeness separately from SARIF.
"""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata
from typing import Callable

from rentgen_core._windows_source_tree import read_retained
from rentgen_core.errors import CoreError
from rentgen_core.git_observer import Finding, FindingReport, GitObservation


MAX_BYTES = 2 * 1024 * 1024
MAX_RUNS = 16
MAX_FINDINGS = 5000
MAX_TEXT = 4096
_SCHEMAS = {
    "https://json.schemastore.org/sarif-2.1.0.json",
    "https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0-rtm.5.json",
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/cos02/schemas/sarif-schema-2.1.0.json",
}


@dataclass(frozen=True)
class SarifContext:
    """Trusted producer attestation; never derive this from untrusted SARIF.

    The digest binds the attestation to the imported bytes. It is not a signature
    or independent proof that an analyzer ran against the stated observation.
    """

    observation: GitObservation
    profile_id: str
    scope_id: str
    complete: bool
    report_sha256: str


def _require(condition, code="SARIF_INVALID", message="Unsupported SARIF structure"):
    if not condition:
        raise CoreError(code, message)


def _text(value):
    _require(
        isinstance(value, str)
        and 0 < len(value) <= MAX_TEXT
        and not any(unicodedata.category(c) in {"Cs", "Cc"} for c in value)
    )
    return value


def _object(value, required, optional=()):
    _require(isinstance(value, dict))
    _require(set(required) <= value.keys() <= set(required) | set(optional))
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, message="Duplicate SARIF JSON member")
        result[key] = value
    return result


def _invalid_constant(value):
    raise CoreError("SARIF_INVALID", "Non-finite JSON number")


def _read_report(path):
    _require(
        path.is_absolute()
        and ".." not in path.parts
        and not path.drive.startswith("\\\\")
        and not str(path).startswith("//")
        and not any(unicodedata.category(c) in {"Cs", "Cc", "Cf"} for c in str(path)),
        "SARIF_PATH_INVALID",
        "SARIF report requires an absolute local path without parent traversal",
    )
    try:
        return read_retained(path, MAX_BYTES)
    except (CoreError, OSError, ValueError) as exc:
        raise CoreError(
            "SARIF_READ_FAILED", "Cannot read retained SARIF report"
        ) from exc


def _observation(value):
    _require(
        isinstance(value, GitObservation), "SARIF_CONTEXT", "Git observation required"
    )
    _require(
        isinstance(value.repository, str)
        and bool(value.repository)
        and len(value.repository) <= MAX_TEXT
        and Path(value.repository).is_absolute()
        and not any(unicodedata.category(c) in {"Cs", "Cc"} for c in value.repository)
        and isinstance(value.commit, str)
        and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value.commit) is not None
        and (
            value.ref is None
            or (
                isinstance(value.ref, str)
                and 0 < len(value.ref) <= MAX_TEXT
                and not any(unicodedata.category(c) in {"Cs", "Cc"} for c in value.ref)
            )
        ),
        "SARIF_CONTEXT",
        "Invalid Git observation",
    )


def _context(context, observation, profile_id, scope_id):
    _observation(observation)
    _require(
        isinstance(context, SarifContext),
        "SARIF_CONTEXT",
        "Trusted SARIF context required",
    )
    _require(
        context.complete is True,
        "SARIF_INCOMPLETE",
        "Complete producer attestation required",
    )
    _require(
        all(
            isinstance(v, str)
            and 0 < len(v) <= MAX_TEXT
            and not any(unicodedata.category(c) in {"Cs", "Cc"} for c in v)
            for v in (profile_id, scope_id)
        )
        and context.observation == observation
        and context.profile_id == profile_id
        and context.scope_id == scope_id
        and isinstance(context.report_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", context.report_sha256) is not None,
        "SARIF_CONTEXT",
        "SARIF context differs from the expected analysis",
    )


def _path(value):
    _require(isinstance(value, str), "SARIF_PATH_INVALID", "Unsafe SARIF artifact URI")
    path = PurePosixPath(value)
    _require(
        0 < len(value) <= MAX_TEXT
        and str(path) == value
        and value != "."
        and not path.is_absolute()
        and ".." not in path.parts
        and not any(c in value for c in "\\:%?#")
        and not any(unicodedata.category(c) in {"Cs", "Cc", "Cf"} for c in value),
        "SARIF_PATH_INVALID",
        "Unsafe SARIF artifact URI",
    )
    return value


def _finding(value):
    _object(value, {"ruleId", "message", "locations"}, {"level"})
    rule = _text(value["ruleId"])
    message = _text(_object(value["message"], {"text"})["text"])
    if "level" in value:
        _require(
            isinstance(value["level"], str)
            and value["level"] in {"none", "note", "warning", "error"}
        )
    locations = value["locations"]
    _require(isinstance(locations, list) and len(locations) == 1)
    physical = _object(
        _object(locations[0], {"physicalLocation"})["physicalLocation"],
        {"artifactLocation", "region"},
    )
    path = _path(_object(physical["artifactLocation"], {"uri"})["uri"])
    region = _object(
        physical["region"], {"startLine"}, {"startColumn", "endLine", "endColumn"}
    )
    for coordinate in region.values():
        _require(type(coordinate) is int and 1 <= coordinate <= 2**31 - 1)
    start = region["startLine"]
    end = region.get("endLine", start)
    _require(end >= start)
    if end == start and "startColumn" in region and "endColumn" in region:
        _require(region["endColumn"] >= region["startColumn"])
    anchor = (
        f"{start}:{region.get('startColumn', 0)}:{end}:{region.get('endColumn', 0)}"
    )
    return Finding(rule, path, anchor, message, start)


def _run(value):
    _object(value, {"tool", "results"}, {"invocations"})
    driver = _object(
        _object(value["tool"], {"driver"})["driver"],
        {"name"},
        {"version", "semanticVersion", "informationUri"},
    )
    for text in driver.values():
        _text(text)
    if "invocations" in value:
        invocations = value["invocations"]
        _require(isinstance(invocations, list) and 1 <= len(invocations) <= MAX_RUNS)
        for invocation in invocations:
            _object(invocation, {"executionSuccessful"}, {"exitCode"})
            _require(
                invocation["executionSuccessful"] is True,
                "SARIF_INCOMPLETE",
                "SARIF invocation failed",
            )
            if "exitCode" in invocation:
                _require(type(invocation["exitCode"]) is int)
                _require(
                    invocation["exitCode"] == 0,
                    "SARIF_INCOMPLETE",
                    "SARIF invocation failed",
                )
    results = value["results"]
    _require(isinstance(results, list))
    return results


def parse_sarif(
    source: bytes | Path,
    *,
    observation: GitObservation,
    profile_id: str,
    scope_id: str,
    context: SarifContext,
    authorize: Callable[[], None],
) -> FindingReport:
    """Import an attested report without running tools, probing Git or networking.

    ``authorize`` must raise on refusal. It runs before any read, after JSON
    parsing and immediately before returning the validated report. File inputs
    use the existing Windows retained no-follow reader, without resolving links.
    """
    _require(callable(authorize), "SARIF_CONTEXT", "Authorization callback required")
    authorize()
    _context(context, observation, profile_id, scope_id)
    if isinstance(source, Path):
        raw = _read_report(source)
    else:
        _require(type(source) is bytes, message="SARIF input must be bytes or Path")
        raw = source
    _require(len(raw) <= MAX_BYTES, "SARIF_LIMIT", "SARIF byte limit exceeded")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs,
            parse_constant=_invalid_constant,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CoreError("SARIF_INVALID", "Malformed SARIF JSON") from exc
    authorize()
    _require(
        hashlib.sha256(raw).hexdigest() == context.report_sha256,
        "SARIF_CONTEXT",
        "SARIF digest differs from producer attestation",
    )
    _object(value, {"version", "runs"}, {"$schema"})
    _require(value["version"] == "2.1.0")
    if "$schema" in value:
        _require(isinstance(value["$schema"], str) and value["$schema"] in _SCHEMAS)
    runs = value["runs"]
    _require(isinstance(runs, list) and bool(runs))
    _require(len(runs) <= MAX_RUNS, "SARIF_LIMIT", "SARIF run limit exceeded")
    findings = {}
    count = 0
    for run in runs:
        results = _run(run)
        count += len(results)
        _require(count <= MAX_FINDINGS, "SARIF_LIMIT", "SARIF finding limit exceeded")
        for result in results:
            finding = _finding(result)
            _require(
                finding.identity not in findings,
                "SARIF_DUPLICATE",
                "Duplicate SARIF finding identity",
            )
            findings[finding.identity] = finding
    report = FindingReport(
        observation,
        profile_id,
        scope_id,
        True,
        tuple(findings[key] for key in sorted(findings)),
    )
    authorize()
    return report
