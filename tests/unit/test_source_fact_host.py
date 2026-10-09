"""Public handwritten development checks, not the independent withheld cohort."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rentgen_core import capabilities, cli
from rentgen_core.errors import CoreError
from rentgen_core import source_fact_cli, submitted_source_facts
from rentgen_core.source_fact_schema import (
    equal_identifier, make_kernel_envelope, strict_json, validate_kernel,
    validate_scan, xml_observations,
)

NS = "http://v8.1c.ru/8.3/MDClasses"


def xml(properties="<Name>Candidate</Name><Server>false</Server>", *, root_attrs=""):
    return (f'<MetaDataObject xmlns="{NS}"{root_attrs}><CommonModule><Properties>'
            + properties + '</Properties></CommonModule></MetaDataObject>').encode()


@pytest.mark.parametrize("properties,reason", [
    ("<Server>true</Server>", "xml_name_missing"),
    ("<Name>A</Name><Name>A</Name><Server>true</Server>", "xml_name_duplicate"),
    ("<Name>A.B</Name><Server>true</Server>", "xml_name_invalid"),
    ("<Name x='1'>A</Name><Server>true</Server>", "xml_name_invalid"),
    ("<Name><X/></Name><Server>true</Server>", "xml_name_invalid"),
    ("<Name>A</Name>", "xml_server_missing"),
    ("<Name>A</Name><Server>true</Server><Server>true</Server>", "xml_server_duplicate"),
    ("<Name>A</Name><Server>True</Server>", "xml_server_invalid"),
    ("<Name>A</Name><Server>0</Server>", "xml_server_invalid"),
    ("<Name>A</Name><Server x='1'>true</Server>", "xml_server_invalid"),
    ("<Name>A</Name><Server><X/></Server>", "xml_server_invalid"),
    ("<Name>A</Name><Server>true</Server><Unknown/>", "xml_shape_unsupported"),
])
def test_xml_closed_failures(properties, reason):
    assert xml_observations(xml(properties))[1] == {"state": "unavailable", "reason": reason}


@pytest.mark.parametrize("value", [True, False])
def test_xml_explicit_booleans_and_case(value):
    name, result = xml_observations(xml(f"<Server> {str(value).lower()} </Server><Name> Кандидат </Name>"))
    assert name == "Кандидат"
    assert result == {"state": "observed", "value": value}


def test_xml_shape_is_not_designer_qualification():
    assert xml_observations(None)[1]["reason"] == "xml_missing"
    assert xml_observations(xml(root_attrs=' version="2.17"'))[1]["reason"] == "xml_shape_unsupported"
    assert xml_observations(b"<!DOCTYPE a [<!ENTITY x 'SYNTH_SECRET'>]><a/>")[1]["reason"] == "xml_forbidden"
    assert xml_observations(b"<a>")[1]["reason"] == "xml_invalid"
    assert xml_observations(xml().replace(b"<CommonModule>", b"<CommonModule/><CommonModule>", 1))[1]["reason"] == "xml_duplicate_container"
    assert not equal_identifier("Е", "Ё")
    assert not equal_identifier("A", "А")
    assert equal_identifier("КАНДИДАТ", "кандидат")


@pytest.mark.parametrize("raw", [
    b'{"x":-0}', b'{"x":1.0}', b'{"x":1e0}', b'{"x":NaN}',
    b'{"x":2147483648}', b'{"x":1,"\\u0078":2}', b'{"x":[]}',
    b'{"x":"\\ud800"}', b' {"x":1}', b'{"x":1}\n', b'[]',
])
def test_strict_host_json_never_coerces(raw):
    with pytest.raises(CoreError):
        strict_json(raw)


def scan_fixture(candidate_raw=b"Procedure Target() Export\nEndProcedure\n"):
    caller_raw = b"Procedure Run()\nCandidate.Target();\nEndProcedure\n"
    def entry(i, path, raw):
        return {"entry_id": i, "path": path, "size_bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest()}
    caller = entry(0, "CommonModules/Caller/Ext/Module.bsl", caller_raw)
    candidate = entry(1, "CommonModules/Candidate/Ext/Module.bsl", candidate_raw)
    start = caller_raw.index(b"Candidate.Target")
    selection = {"start": start, "end": start + len(b"Candidate.Target")}
    name = candidate_raw.index(b"Target")
    head_end = candidate_raw.index(b"\n")
    export = candidate_raw.find(b"Export", 0, head_end)
    span = lambda start, end: {"start": start, "end": end}
    record = lambda e: {**{k: e[k] for k in ("entry_id", "size_bytes", "raw_sha256")}, "admission": {"state": "admitted"}}
    result = {"protocol": "source_fact_scan_v1", "status": "ok",
              "caller": record(caller), "candidate": record(candidate),
              "selector": {"state": "observed", "entry_id": 0,
                           "routine_span": span(0, len(caller_raw) - 1),
                           "selector_span": selection, "receiver_span": span(start, start + 9),
                           "method_span": span(start + 10, start + 16)},
              "header": {"state": "observed", "entry_id": 1,
                         "routine_span": span(0, len(candidate_raw) - 1),
                         "header_span": span(0, head_end), "name_span": span(name, name + 6),
                         "export": export >= 0, "export_span": None if export < 0 else span(export, export + 6)}}
    return caller, candidate, {0: caller_raw, 1: candidate_raw}, selection, result


def validate_fixture(values):
    caller, candidate, buffers, selection, result = values
    return validate_scan(json.dumps(result, separators=(",", ":")).encode(), caller, candidate, buffers, selection)


def test_complete_header_not_clipped_or_comment_forged():
    values = scan_fixture()
    assert validate_fixture(values)[1] == "Candidate"
    clipped = copy.deepcopy(values)
    clipped[4]["header"].update(export=False, export_span=None,
                                header_span={"start": 0, "end": clipped[2][1].index(b")") + 1})
    with pytest.raises(CoreError, match="could not be completed"):
        validate_fixture(clipped)
    comment = scan_fixture(b"Procedure Target() // Export\nEndProcedure\n")
    with pytest.raises(CoreError):
        validate_fixture(comment)
    plain = scan_fixture(b"Procedure Target()\nEndProcedure\n")
    assert validate_fixture(plain)[0]["header"]["export"] is False


@pytest.mark.parametrize("mutation", ["wrong_entry", "wrong_hash", "header_role", "bad_reason", "span_bool", "wrong_method"])
def test_scanner_receipt_substitution_rejected(mutation):
    values = scan_fixture()
    result = values[4]
    if mutation == "wrong_entry": result["caller"]["entry_id"] = 2
    if mutation == "wrong_hash": result["caller"]["raw_sha256"] = "0" * 64
    if mutation == "header_role": result["header"]["entry_id"] = 0
    if mutation == "bad_reason": result["selector"] = {"state": "unavailable", "reason": {}}
    if mutation == "span_bool": result["header"]["header_span"]["start"] = False
    if mutation == "wrong_method": result["header"]["name_span"]["end"] -= 1
    with pytest.raises(CoreError): validate_fixture(values)


def test_candidate_identity_gates_without_binding_claim():
    caller, candidate, _, _, scan = scan_fixture()
    metadata = {"entry_id": 2}
    envelope = make_kernel_envelope(scan, "Candidate", "Candidate", None,
                                   {"state": "unavailable", "reason": "xml_name_invalid"},
                                   caller=caller, candidate=candidate, metadata=metadata)
    assert envelope["observations"]["export"]["reason"] == "candidate_identity_unavailable"
    assert envelope["receiver_binding"] == envelope["runtime_relation"] == "unknown"
    envelope = make_kernel_envelope(scan, "Candidate", "Candidate", "Candidate",
                                   {"state": "observed", "value": False},
                                   caller=caller, candidate=candidate, metadata=metadata)
    result = {k: v for k, v in envelope.items() if k != "receipts"}
    result["assurance"] = "source_facts_host_asserted_no_binding_no_runtime"
    validate_kernel(json.dumps(result).encode(), envelope)
    result["observations"] = copy.deepcopy(result["observations"])
    result["observations"]["server"]["value"] = 0
    with pytest.raises(CoreError): validate_kernel(json.dumps(result).encode(), envelope)


def source_argv(tmp_path):
    args = ["source-facts", "--registry", str(tmp_path / "registry"), "--project", "owned"]
    for label in ("archive", "input-core", "source-scanner", "source-kernel"):
        args += ["--" + label, str(tmp_path / label), "--" + label + "-sha256", "0" * 64]
    return args + ["--caller-entry", "Caller.bsl", "--candidate-entry", "CommonModules/Candidate/Ext/Module.bsl",
                   "--selector-start", "0", "--selector-end", "1"]


@pytest.mark.parametrize("argv", [
    ["source-facts", "--unknown", "SYNTH_SECRET"],
    ["--wrong", "SYNTH_SECRET", "source-facts"],
    ["source-facts", "--registry", "SYNTH_SECRET"],
])
def test_argument_boundary_never_echoes(argv, capsys):
    assert cli.main(argv) == 2
    out, err = capsys.readouterr()
    assert not err and "SYNTH_SECRET" not in out
    assert json.loads(out)["error"]["code"] == "SOURCE_FACTS_INVALID_ARGUMENT"


def test_final_permission_recheck_replaces_serialized_result(tmp_path, monkeypatch, capsys):
    ctx, revoked = object(), [False]
    real_dumps = json.dumps
    def execute(args, proposal_scope):
        proposal_scope.context = ctx
        return cli._ProposalCommandResult({"private": "SYNTH_SECRET"}, ctx, output_limit=65536)
    def authorize(_):
        if revoked[0]: raise CoreError("PROJECT_FORBIDDEN", "SYNTH_PRIVATE_ACCESS", details={"private": "SYNTH_SECRET"})
    def dumps(value, *args, **kwargs):
        if isinstance(value, dict) and "result" in value: revoked[0] = True
        return real_dumps(value, *args, **kwargs)
    monkeypatch.setattr(cli, "_execute", execute)
    monkeypatch.setattr(submitted_source_facts, "authorize", authorize)
    monkeypatch.setattr(source_fact_cli.json, "dumps", dumps)
    assert cli.main(source_argv(tmp_path)) == 2
    out, err = capsys.readouterr()
    assert not err and "SYNTH_SECRET" not in out and "SYNTH_PRIVATE" not in out
    assert json.loads(out)["error"]["code"] == "SOURCE_FACTS_PERMISSION_DENIED"


def test_capability_is_linux_only_and_not_mcp(monkeypatch):
    from rentgen_core.stdio_mcp import TOOL_SCHEMAS
    for platform in ("win32", "darwin", "freebsd14"):
        monkeypatch.setattr(capabilities, "_platform", platform)
        assert not capabilities.operation_supported("source-facts")
    monkeypatch.setattr(capabilities, "_platform", "linux")
    assert capabilities.operation_supported("source-facts")
    assert "rentgen_source_facts" not in TOOL_SCHEMAS
