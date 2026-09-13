"""External SARIF is bounded evidence, never an implicit successful analysis."""

from dataclasses import replace
import hashlib
import importlib
import json
import os
from pathlib import Path

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.git_observer import GitObservation


def adapter():
    return importlib.import_module("rentgen_diagnostics.sarif_adapter")


@pytest.fixture
def observation(tmp_path):
    return GitObservation(str(tmp_path), "a" * 40, "refs/heads/main")


def result(path="CommonModules/Module.bsl", line=7):
    return {
        "ruleId": "sonar/S123",
        "message": {"text": "Check the expression"},
        "level": "warning",
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": path},
                    "region": {"startLine": line},
                }
            }
        ],
    }


def document(results=None):
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{"tool": {"driver": {"name": "Sonar"}}, "results": results or []}],
    }


def encode(value):
    return json.dumps(value).encode("utf-8")


def parse(raw, observation, *, source=None, authorize=lambda: None, **changes):
    module = adapter()
    context = module.SarifContext(
        observation=observation,
        profile_id="sonar-v1",
        scope_id="repository",
        complete=True,
        report_sha256=hashlib.sha256(raw).hexdigest(),
    )
    return module.parse_sarif(
        raw if source is None else source,
        observation=observation,
        profile_id="sonar-v1",
        scope_id="repository",
        context=replace(context, **changes),
        authorize=authorize,
    )


def assert_error(raw, observation, code="SARIF_INVALID", **kwargs):
    with pytest.raises(CoreError) as error:
        parse(raw, observation, **kwargs)
    assert error.value.code == code


def test_complete_report_has_exact_context_and_stable_identity(observation):
    raw = encode(document([result()]))
    calls = []
    report = parse(raw, observation, authorize=lambda: calls.append("check"))
    assert report.observation == observation
    assert report.profile_id == "sonar-v1"
    assert report.scope_id == "repository"
    assert report.complete is True
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.rule == "sonar/S123"
    assert finding.path == "CommonModules/Module.bsl"
    assert finding.line == 7
    assert finding.message == "Check the expression"
    changed = result()
    changed["message"]["text"] = "New wording"
    changed["level"] = "error"
    assert (
        parse(encode(document([changed])), observation).findings[0].identity
        == finding.identity
    )
    assert calls == ["check"] * 3


def test_complete_empty_report_is_success(observation):
    assert parse(encode(document()), observation).findings == ()


def test_multiple_runs_are_canonical(observation):
    value = document([result("Z.bsl")])
    value["runs"].append(document([result("A.bsl")])["runs"][0])
    assert [f.path for f in parse(encode(value), observation).findings] == [
        "A.bsl",
        "Z.bsl",
    ]


@pytest.mark.parametrize("complete", [False, None, 1, "true"])
def test_incomplete_contract_cannot_resolve_findings(observation, complete):
    value = document()
    value["runs"][0]["invocations"] = [{"executionSuccessful": True, "exitCode": 0}]
    assert_error(encode(value), observation, "SARIF_INCOMPLETE", complete=complete)


@pytest.mark.parametrize(
    "field,value",
    [("profile_id", "foreign"), ("scope_id", "other"), ("report_sha256", "b" * 64)],
)
def test_foreign_contract_is_rejected(observation, field, value):
    assert_error(encode(document()), observation, "SARIF_CONTEXT", **{field: value})


@pytest.mark.parametrize(
    "field,value",
    [("commit", "b" * 40), ("repository", "C:/foreign"), ("ref", "refs/heads/other")],
)
def test_foreign_observation_is_rejected(observation, field, value):
    raw = encode(document())
    module = adapter()
    context = module.SarifContext(
        replace(observation, **{field: value}),
        "sonar-v1",
        "repository",
        True,
        hashlib.sha256(raw).hexdigest(),
    )
    with pytest.raises(CoreError) as error:
        module.parse_sarif(
            raw,
            observation=observation,
            profile_id="sonar-v1",
            scope_id="repository",
            context=context,
            authorize=lambda: None,
        )
    assert error.value.code == "SARIF_CONTEXT"


@pytest.mark.parametrize(
    "path",
    [
        "../a.bsl",
        "a/../b.bsl",
        "a\\b.bsl",
        "C:/a.bsl",
        "/a.bsl",
        "//host/a.bsl",
        "a//b.bsl",
        "./a.bsl",
        ".",
        "",
        "a\x00.bsl",
        "a\x7f.bsl",
        "a%2fb.bsl",
        "a?x",
        "a#x",
        "https://host/a",
    ],
)
def test_unsafe_uri_is_rejected(observation, path):
    assert_error(encode(document([result(path)])), observation, "SARIF_PATH_INVALID")


def test_duplicate_identity_across_runs_is_rejected(observation):
    value = document([result()])
    value["runs"].append(document([result()])["runs"][0])
    assert_error(encode(value), observation, "SARIF_DUPLICATE")


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b"[]",
        b"null",
        b"\xff",
        b'{"version":"2.1.0","version":"2.1.0","runs":[]}',
        b'{"version":NaN}',
        b"[" * 2000 + b"]" * 2000,
    ],
)
def test_malformed_json_is_typed(observation, raw):
    assert_error(raw, observation)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(version="2.0.0"),
        lambda d: d.update(runs=[]),
        lambda d: d.update(runs={}),
        lambda d: d.update(unknown=True),
        lambda d: d["runs"][0].pop("results"),
        lambda d: d["runs"][0].update(results={}),
        lambda d: d["runs"][0]["results"][0].pop("locations"),
        lambda d: d["runs"][0]["results"][0].update(locations=[]),
        lambda d: d["runs"][0]["results"][0].update(level="fatal"),
        lambda d: d["runs"][0]["results"][0].update(message={"text": ""}),
        lambda d: d["runs"][0]["results"][0].update(ruleId=123),
        lambda d: d["runs"][0]["results"][0].update(suppressions=[]),
        lambda d: d["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
            "region"
        ].update(startLine=True),
        lambda d: d["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
            "region"
        ].update(startLine=0),
        lambda d: d["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
            "artifactLocation"
        ].update(uriBaseId="ROOT"),
    ],
)
def test_unexpected_structures_are_rejected(observation, mutation):
    value = document([result()])
    mutation(value)
    assert_error(encode(value), observation)


def test_failed_invocation_overrides_complete_claim(observation):
    value = document()
    value["runs"][0]["invocations"] = [{"executionSuccessful": False, "exitCode": 1}]
    assert_error(encode(value), observation, "SARIF_INCOMPLETE")


def test_oversized_bytes_are_rejected_before_decode(observation):
    assert_error(b" " * (adapter().MAX_BYTES + 1), observation, "SARIF_LIMIT")


def test_run_limit_is_enforced(observation):
    value = document()
    value["runs"] *= adapter().MAX_RUNS + 1
    assert_error(encode(value), observation, "SARIF_LIMIT")


def test_finding_limit_is_enforced(observation):
    value = document([result(line=i + 1) for i in range(adapter().MAX_FINDINGS + 1)])
    assert_error(encode(value), observation, "SARIF_LIMIT")


@pytest.mark.parametrize("revoke_at", [1, 2, 3])
def test_authorization_revocation_never_returns_report(observation, revoke_at):
    calls = []

    def authorize():
        calls.append(1)
        if len(calls) == revoke_at:
            raise CoreError("ACCESS_REVOKED", "Revoked")

    assert_error(encode(document()), observation, "ACCESS_REVOKED", authorize=authorize)
    assert len(calls) == revoke_at


@pytest.mark.skipif(os.name != "nt", reason="Retained read uses Windows file handles")
def test_path_uses_retained_bytes(observation, tmp_path):
    raw = encode(document([result()]))
    source = tmp_path / "report.sarif"
    source.write_bytes(raw)
    assert parse(raw, observation, source=source) == parse(raw, observation)


def test_revoked_authorization_prevents_file_read(observation, tmp_path):
    def revoke():
        raise CoreError("ACCESS_REVOKED", "Revoked")

    assert_error(
        encode(document()),
        observation,
        "ACCESS_REVOKED",
        source=tmp_path / "missing.sarif",
        authorize=revoke,
    )


@pytest.mark.parametrize(
    "region",
    [
        {"startLine": 8, "endLine": 7},
        {"startLine": 7, "startColumn": 5, "endColumn": 4},
        {"startLine": 2**31},
        {"startLine": 7, "startColumn": 0},
    ],
)
def test_invalid_region_is_rejected(observation, region):
    item = result()
    item["locations"][0]["physicalLocation"]["region"] = region
    assert_error(encode(document([item])), observation)


def test_valid_end_region_and_optional_level(observation):
    item = result()
    item.pop("level")
    item["locations"][0]["physicalLocation"]["region"].update(
        startColumn=2, endLine=9, endColumn=1
    )
    assert parse(encode(document([item])), observation).findings[0].anchor == "7:2:9:1"


def test_exact_byte_limit_is_accepted(observation):
    raw = encode(document())
    raw += b" " * (adapter().MAX_BYTES - len(raw))
    assert parse(raw, observation).findings == ()


def test_finding_limit_applies_across_runs(observation):
    value = document([result(line=i + 1) for i in range(adapter().MAX_FINDINGS)])
    value["runs"].append(document([result("Other.bsl")])["runs"][0])
    assert_error(encode(value), observation, "SARIF_LIMIT")


@pytest.mark.parametrize(
    "field,value",
    [("repository", "relative"), ("commit", "bad"), ("ref", "bad\x00ref")],
)
def test_invalid_expected_observation_is_typed(observation, field, value):
    assert_error(
        encode(document()), replace(observation, **{field: value}), "SARIF_CONTEXT"
    )


@pytest.mark.parametrize("field", ["profile_id", "scope_id"])
def test_control_characters_in_context_are_rejected(observation, field):
    module = adapter()
    raw = encode(document())
    values = {"profile_id": "sonar-v1", "scope_id": "repository"}
    values[field] = "bad\x00value"
    context = module.SarifContext(
        observation,
        **values,
        complete=True,
        report_sha256=hashlib.sha256(raw).hexdigest(),
    )
    with pytest.raises(CoreError) as error:
        module.parse_sarif(
            raw,
            observation=observation,
            **values,
            context=context,
            authorize=lambda: None,
        )
    assert error.value.code == "SARIF_CONTEXT"


@pytest.mark.parametrize("value", [None, [], {}, 0, True])
def test_wrong_result_field_types_are_typed(observation, value):
    item = result()
    item["level"] = value
    assert_error(encode(document([item])), observation)


def test_relative_path_never_uses_current_directory(observation, tmp_path, monkeypatch):
    raw = encode(document())
    (tmp_path / "report.sarif").write_bytes(raw)
    monkeypatch.chdir(tmp_path)
    assert_error(raw, observation, "SARIF_PATH_INVALID", source=Path("report.sarif"))


@pytest.mark.parametrize("kind", ["empty", "parent", "nul", "unc", "drive-relative"])
def test_invalid_path_is_rejected_before_retained_read(
    observation, tmp_path, monkeypatch, kind
):
    paths = {
        "empty": Path(""),
        "parent": tmp_path / ".." / "report.sarif",
        "nul": tmp_path / "bad\x00.sarif",
        "unc": Path("//server/share/report.sarif"),
        "drive-relative": Path("C:report.sarif"),
    }

    def unexpected_read(*args):
        pytest.fail("Invalid locator reached retained read")

    monkeypatch.setattr(adapter(), "read_retained", unexpected_read)
    assert_error(
        encode(document()), observation, "SARIF_PATH_INVALID", source=paths[kind]
    )


@pytest.mark.skipif(os.name != "nt", reason="Retained read uses Windows file handles")
@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_unreadable_path_has_typed_sarif_error(observation, tmp_path, kind):
    source = tmp_path if kind == "directory" else tmp_path / "missing.sarif"
    assert_error(encode(document()), observation, "SARIF_READ_FAILED", source=source)


@pytest.mark.skipif(os.name != "nt", reason="Retained read uses Windows file handles")
@pytest.mark.parametrize("raw", [b"", b"{", b"\xff"])
def test_empty_or_malformed_file_is_typed(observation, tmp_path, raw):
    source = tmp_path / "report.sarif"
    source.write_bytes(raw)
    assert_error(raw, observation, source=source)
