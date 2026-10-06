"""Pure verifier checks; these do not invoke installed Core or native helpers."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import zipfile

import pytest


PATH = Path(__file__).resolve().parents[2] / "scripts/verification/verify_source_fact_delivery.py"
SPEC = importlib.util.spec_from_file_location("source_fact_delivery_smoke", PATH)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def test_owned_zip_is_byte_deterministic_and_explicitly_handwritten(tmp_path):
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    files, selection = smoke.owned_archive(first)
    assert smoke.owned_archive(second) == (files, selection)
    assert first.read_bytes() == second.read_bytes()
    assert files[smoke.CALLER][selection["start"]:selection["end"]] == b"DeliveryCandidate.SYNTH_DeliveryTarget"
    assert b"uuid=" not in files[smoke.METADATA]
    with zipfile.ZipFile(first) as archive:
        assert set(archive.namelist()) == set(files)
        assert all(archive.read(name) == raw for name, raw in files.items())


@pytest.mark.parametrize("expected", [None, "", "A" * 64, "0" * 63, "0" * 64])
def test_artifact_pin_is_explicit_and_must_match(tmp_path, expected):
    path = tmp_path / "owned"
    path.write_bytes(b"owned bytes")
    with pytest.raises(RuntimeError):
        smoke.pinned_bytes(path, expected)
    assert smoke.pinned_bytes(path, smoke.sha(b"owned bytes")) == b"owned bytes"


def test_fingerprint_detects_new_files_and_content_changes(tmp_path):
    path = tmp_path / "owned"
    path.mkdir()
    file = path / "one"
    file.write_bytes(b"first")
    before = smoke.fingerprint({"owned": path})
    file.write_bytes(b"second")
    assert smoke.fingerprint({"owned": path}) != before
    file.write_bytes(b"first")
    (path / "new-directory").mkdir()
    assert smoke.fingerprint({"owned": path}) != before


def test_fingerprint_rejects_symlink(tmp_path):
    (tmp_path / "link").symlink_to(tmp_path / "absent")
    with pytest.raises(RuntimeError, match="symlink"):
        smoke.fingerprint({"owned": tmp_path})


def fixed_error():
    return {"error": {"code": "SOURCE_FACTS_INPUT_REJECTED",
                      "message": "Submitted source facts could not be completed",
                      "request_id": str(uuid4()), "details": {}}}


def test_fixed_rejection_accepts_only_closed_error(tmp_path):
    value = fixed_error()
    smoke.validate_error(value, (json.dumps(value) + "\n").encode(), tmp_path)
    value["error"]["details"] = {"path": "SYNTH_PRIVATE"}
    with pytest.raises(RuntimeError):
        smoke.validate_error(value, (json.dumps(value) + "\n").encode(), tmp_path)


def test_fixed_rejection_rejects_extra_payload(tmp_path):
    value = {**fixed_error(), "result": {"source": "SYNTH_PRIVATE"}}
    with pytest.raises(RuntimeError):
        smoke.validate_error(value, (json.dumps(value) + "\n").encode(), tmp_path)


@pytest.mark.parametrize("extra", [{"source": "SYNTH_PRIVATE"}, {"extra": {}}])
def test_success_requires_closed_envelope(tmp_path, extra):
    value = {"result": {}, "request_id": str(uuid4())}
    smoke.validate_success(value, (json.dumps(value) + "\n").encode(), tmp_path)
    value.update(extra)
    with pytest.raises(RuntimeError):
        smoke.validate_success(value, (json.dumps(value) + "\n").encode(), tmp_path)


@pytest.mark.parametrize("source", ["SYNTH_PRIVATE", "/owned/private/output"])
def test_success_rejects_disclosure_canaries(source):
    value = {"result": {"unexpected": source}, "request_id": str(uuid4())}
    with pytest.raises(RuntimeError):
        smoke.validate_success(value, (json.dumps(value) + "\n").encode(), Path("/owned/private/output"))


@pytest.mark.parametrize("raw", [
    b'{"result":"SYNTH_PRIVATE","result":{}}',
    b'{"error":{"message":"SYNTH_PRIVATE","message":"fixed"}}',
    b'{"result":"SYNTH_PRIVATE","res\\u0075lt":{}}',
    b'{"result":{"details":{"path":"SYNTH_PRIVATE","path":null}}}',
])
def test_strict_parser_rejects_duplicate_keys_before_disclosure_validation(raw):
    with pytest.raises(RuntimeError, match="Duplicate JSON object key"):
        smoke.parse_json(raw)


@pytest.mark.parametrize("constant", [b"NaN", b"Infinity", b"-Infinity"])
def test_strict_parser_rejects_nonstandard_constants(constant):
    with pytest.raises(RuntimeError, match="Nonstandard JSON constant"):
        smoke.parse_json(b'{"value":' + constant + b'}')


@pytest.mark.parametrize("kind", ["success", "error"])
@pytest.mark.parametrize("canary", [b"SYNTH_PRIVATE", b"/owned/private/output"])
def test_raw_disclosure_check_does_not_trust_collapsed_parsed_value(kind, canary):
    output = Path("/owned/private/output")
    value = {"result": {}, "request_id": str(uuid4())} if kind == "success" else fixed_error()
    raw = (json.dumps(value) + "\n").encode().replace(b"{", b'{"discarded":"' + canary + b'",', 1)
    validator = smoke.validate_success if kind == "success" else smoke.validate_error
    with pytest.raises(RuntimeError, match="escaped into output"):
        validator(value, raw, output)


@pytest.mark.parametrize("escaped", [b"SYNTH_\\u0050RIVATE", b"\\u002fowned/private/output"])
def test_decoded_disclosure_check_catches_json_escapes(escaped):
    raw = b'{"value":"' + escaped + b'"}'
    with pytest.raises(RuntimeError, match="escaped into output"):
        smoke.check_disclosure(smoke.parse_json(raw), raw, Path("/owned/private/output"))


def test_bad_pin_precedes_output_creation_or_process_launch(tmp_path, monkeypatch):
    wheel = tmp_path / "owned.whl"
    wheel.write_bytes(b"owned bytes")
    output = tmp_path / "new-output"
    monkeypatch.setattr(smoke.subprocess, "Popen", lambda *a, **kw: pytest.fail("No process may start"))
    with pytest.raises(RuntimeError, match="SHA-256"):
        smoke.verify(SimpleNamespace(wheel=wheel, wheel_sha256="0" * 64, output=output))
    assert not output.exists()
