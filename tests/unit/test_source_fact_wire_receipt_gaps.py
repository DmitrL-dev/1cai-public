"""Finite public W gap completion; source assertions never authenticate binding.

Run with the reviewed boundary supervisor and pinned images. This file does not
open the independent source cohort, build binaries, or generate expected labels.
"""
import base64
import copy
from contextlib import ExitStack
import hashlib
import json
import os
import selectors
import struct
import subprocess
import time

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.rust_input import _executable
from rentgen_core.source_fact_schema import make_kernel_envelope, validate_kernel
from test_source_fact_host import scan_fixture, validate_fixture
from test_source_fact_runtime_boundaries import (
    MESSAGE, ROOT, images, qualification_preflight, own_command, stop_owned,
)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def closed_failure(call, code, capsys):
    sentinel = object()
    result = sentinel
    with pytest.raises(CoreError) as caught:
        result = call()
    assert result is sentinel, "A rejected exchange returned partial observations"
    assert caught.value.code == "SOURCE_FACTS_" + code
    assert str(caught.value) == MESSAGE and caught.value.details == {}
    assert capsys.readouterr() == ("", "")


def alias_fixture():
    values = list(scan_fixture())
    caller, _, buffers, selection, scan = values
    candidate = dict(caller)
    # The caller routine is also the selected matching declaration. The observed
    # selector is Candidate.Run and the complete header has no Export marker.
    raw = buffers[0].replace(b"Candidate.Target", b"Candidate.Run")
    caller.update(size_bytes=len(raw), raw_sha256=hashlib.sha256(raw).hexdigest())
    candidate.update(caller)
    selection["end"] -= 3
    scan["caller"].update(size_bytes=len(raw), raw_sha256=caller["raw_sha256"])
    scan["candidate"] = copy.deepcopy(scan["caller"])
    scan["selector"]["routine_span"]["end"] = len(raw) - 1
    scan["selector"]["method_span"]["end"] -= 3
    scan["header"] = {"state": "observed", "entry_id": 0,
                      "routine_span": {"start": 0, "end": len(raw) - 1},
                      "header_span": {"start": 0, "end": raw.index(b"\n")},
                      "name_span": {"start": 10, "end": 13},
                      "export": False, "export_span": None}
    return caller, candidate, {0: raw}, selection, scan


def utf8_fixture():
    caller, candidate, buffers, selection, scan = scan_fixture()
    raw = buffers[0].replace(b"Candidate", "Кандидат".encode())
    delta = len("Кандидат".encode()) - len(b"Candidate")
    caller.update(size_bytes=len(raw), raw_sha256=hashlib.sha256(raw).hexdigest())
    scan["caller"].update(size_bytes=len(raw), raw_sha256=caller["raw_sha256"])
    selection["end"] += delta
    scan["selector"]["routine_span"]["end"] += delta
    scan["selector"]["receiver_span"]["end"] += delta
    for end in ("start", "end"):
        scan["selector"]["method_span"][end] += delta
    return caller, candidate, {**buffers, 0: raw}, selection, scan


SCAN_MUTATIONS = [
    ("wrong_entry", "RECEIPT_INVALID"), ("wrong_hash", "RECEIPT_INVALID"),
    ("header_role", "RECEIPT_INVALID"), ("wrong_method", "RECEIPT_INVALID"),
    ("span_bool", "PROTOCOL_INVALID"),
    ("selector_entry_role", "RECEIPT_INVALID"), ("candidate_record_role", "RECEIPT_INVALID"),
    ("selector_containment", "RECEIPT_INVALID"), ("export_token_span", "RECEIPT_INVALID"),
    ("same_file_admission_alias", "RECEIPT_INVALID"),
    ("caller_admission_dependency", "RECEIPT_INVALID"),
    ("caller_reason_dependency", "RECEIPT_INVALID"),
    ("selector_header_dependency", "RECEIPT_INVALID"),
    ("utf8_selector_boundary", "RECEIPT_INVALID"),
]


@pytest.mark.parametrize("mutation,code", SCAN_MUTATIONS)
def test_host_scan_gap_exact_closed_errors(mutation, code, capsys):
    original = (alias_fixture() if mutation == "same_file_admission_alias" else
                utf8_fixture() if mutation == "utf8_selector_boundary" else scan_fixture())
    admitted, receiver = validate_fixture(copy.deepcopy(original))
    assert admitted == original[4] and receiver == ("Кандидат" if mutation == "utf8_selector_boundary" else "Candidate")
    values = copy.deepcopy(original)
    scan = values[4]
    if mutation == "wrong_entry": scan["caller"]["entry_id"] = 2
    elif mutation == "wrong_hash": scan["caller"]["raw_sha256"] = "0" * 64
    elif mutation == "header_role": scan["header"]["entry_id"] = 0
    elif mutation == "wrong_method": scan["header"]["name_span"]["end"] -= 1
    elif mutation == "span_bool": scan["header"]["header_span"]["start"] = False
    elif mutation == "selector_entry_role": scan["selector"]["entry_id"] = 1
    elif mutation == "candidate_record_role": scan["candidate"]["entry_id"] = 0
    elif mutation == "selector_containment":
        scan["selector"]["routine_span"]["start"] = values[3]["start"] + 1
    elif mutation == "export_token_span":
        scan["header"]["export_span"] = copy.deepcopy(scan["header"]["name_span"])
    elif mutation == "same_file_admission_alias":
        scan["candidate"]["admission"] = {"state": "unavailable", "reason": "invalid_header"}
    elif mutation == "caller_admission_dependency":
        scan["caller"]["admission"] = {"state": "unavailable", "reason": "invalid_header"}
    elif mutation == "caller_reason_dependency":
        scan["selector"] = {"state": "unavailable", "reason": "caller_not_admitted"}
        scan["header"] = {"state": "unavailable", "reason": "selector_unavailable"}
    elif mutation == "selector_header_dependency":
        scan["selector"] = {"state": "unavailable", "reason": "selector_not_qualified"}
        scan["header"] = {"state": "unavailable", "reason": "declaration_unavailable"}
    elif mutation == "utf8_selector_boundary":
        # Change selection and receipt together: exact-selection equality still
        # holds; the endpoint itself splits a Cyrillic scalar in verified bytes.
        values[3]["start"] += 1
        scan["selector"]["receiver_span"]["start"] += 1
    closed_failure(lambda: validate_fixture(values), code, capsys)


def kernel_control():
    caller, candidate, _, _, scan = scan_fixture()
    return make_kernel_envelope(scan, "Candidate", "Candidate", "Candidate",
                                {"state": "observed", "value": False},
                                caller=caller, candidate=candidate, metadata={"entry_id": 2})


def kernel_expected(envelope):
    return {**{key: copy.deepcopy(value) for key, value in envelope.items() if key != "receipts"},
            "assurance": "source_facts_host_asserted_no_binding_no_runtime"}


KERNEL_MUTATIONS = ["scope", "selector_observation", "export_observation", "server_observation",
                    "selector_receipt_id", "export_receipt_id", "server_receipt_id",
                    "receiver_binding", "runtime_relation", "assurance", "extra_field"]


@pytest.mark.parametrize("mutation", KERNEL_MUTATIONS)
def test_host_kernel_gap_exact_closed_errors(mutation, capsys):
    envelope = kernel_control()
    original = kernel_expected(envelope)
    assert validate_kernel(encoded(original), envelope) == original
    result = copy.deepcopy(original)
    if mutation == "scope": result["scope"]["case_id"] += 1
    elif mutation.endswith("_observation"):
        role = mutation.removesuffix("_observation")
        result["observations"][role]["value"] = "SYNTH_FORGED_SELECTOR" if role == "selector" else not result["observations"][role]["value"]
    elif mutation.endswith("_receipt_id"):
        result["observations"][mutation.removesuffix("_receipt_id")]["receipt_id"] += 10
    elif mutation in ("receiver_binding", "runtime_relation", "assurance"): result[mutation] = "verified"
    else: result["SYNTH_EXTRA"] = "SYNTH_PRIVATE_FIELD"
    closed_failure(lambda: validate_kernel(encoded(result), envelope), "RECEIPT_INVALID", capsys)


def frame(payload):
    return struct.pack("<I", len(payload)) + payload


def actual_exchange(request, images, role, payload):
    """Actual one-shot image, bounded full-duplex I/O and confirmed direct reap.

    Reads the exact hello before writing any payload; always cleans the retained
    Popen handle. Each caller compares the entire residual stdout, not a prefix.
    """
    protocol = "source_fact_scan_v1" if role == "source_scanner" else "submitted_source_facts_v1"
    hello = frame(encoded({"protocol": protocol, "kind": "hello", "ownership": "linux_parent_death_v1"}))
    path = images[role]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == images[role + "_sha256"]
    with ExitStack() as files:
        image = _executable(path, images[role + "_sha256"], files)
        child = own_command(request, [f"/proc/self/fd/{image}", "--parent-pid", str(os.getpid())],
                            cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "GOMAXPROCS": "2"},
                            close_fds=True, pass_fds=(image,))
    output = {"stdout": bytearray(), "stderr": bytearray()}
    sent = 0
    data = frame(payload)
    deadline = time.monotonic() + (12 if role == "source_scanner" else 7)
    try:
        with selectors.DefaultSelector() as mux:
            for name in output:
                stream = getattr(child, name)
                os.set_blocking(stream.fileno(), False)
                mux.register(stream, selectors.EVENT_READ, name)
            os.set_blocking(child.stdin.fileno(), False)
            admitted_hello = False
            while mux.get_map():
                left = deadline - time.monotonic()
                if left <= 0: raise TimeoutError("Bounded framed gap exchange")
                for key, _ in mux.select(min(.1, left)):
                    if key.data == "stdin":
                        try: size = os.write(child.stdin.fileno(), data[sent:])
                        except BlockingIOError: continue
                        assert size > 0
                        sent += size
                        if sent == len(data):
                            mux.unregister(child.stdin); child.stdin.close()
                    else:
                        try: chunk = os.read(key.fileobj.fileno(), 8192)
                        except BlockingIOError: continue
                        if not chunk:
                            mux.unregister(key.fileobj)
                            continue
                        output[key.data].extend(chunk)
                        assert len(output[key.data]) <= 66056
                if not admitted_hello and len(output["stdout"]) >= len(hello):
                    assert bytes(output["stdout"][:len(hello)]) == hello
                    admitted_hello = True
                    mux.register(child.stdin, selectors.EVENT_WRITE, "stdin")
            child.wait(timeout=max(.001, deadline - time.monotonic()))
        assert admitted_hello and sent == len(data) and child.stdin.closed
        assert output["stderr"] == b""
        response = bytes(output["stdout"][len(hello):])
        assert len(response) >= 4
        size = struct.unpack("<I", response[:4])[0]
        assert 0 < size <= 65536 and len(response) == size + 4
        with pytest.raises(ChildProcessError): os.waitpid(child.pid, os.WNOHANG)
        return child.returncode, response[4:]
    finally:
        errors = stop_owned(child, time.monotonic() + 2)
        assert not errors, "Owned gap exchange cleanup unconfirmed"


def scanner_request():
    caller, candidate, buffers, selection, _ = scan_fixture()
    def record(entry):
        raw = buffers[entry["entry_id"]]
        return {**{key: entry[key] for key in ("entry_id", "size_bytes", "raw_sha256")},
                "data_base64": base64.b64encode(raw).decode()}
    return {"protocol": "source_fact_scan_v1", "caller": record(caller),
            "candidate": {"kind": "distinct_entry", "buffer": record(candidate)}, "selection": selection}


GO_VARIANTS = ["literal_1_0", "literal_1e0", "depth_13", "request_1500000", "entry_4095",
               "start_524288", "start_524289", "end_524289", "escaped_control", "ordinary_duplicate", "escaped_duplicate"]


@pytest.mark.parametrize("variant", GO_VARIANTS)
def test_actual_go_framed_gap_variants(request, images, variant):
    original = scanner_request()
    control_code, control_raw = actual_exchange(request, images, "source_scanner", encoded(original))
    assert control_code == 0
    assert json.loads(control_raw) == scan_fixture()[4]
    value = copy.deepcopy(original)
    code = None
    if variant in ("literal_1_0", "literal_1e0"):
        payload = encoded(value).replace(b'"entry_id":0', b'"entry_id":' + (b"1.0" if variant == "literal_1_0" else b"1e0"), 1)
        code = "invalid_request"
    elif variant == "depth_13":
        payload = b'{"nested":' + b'{"x":' * 12 + b'0' + b'}' * 12 + b',' + encoded(value)[1:]
        code = "invalid_request"
    elif variant == "request_1500000":
        raw = encoded(value); payload = b'{' + b' ' * (1500000 - len(raw)) + raw[1:]
        assert len(payload) == 1500000
    elif variant == "escaped_control":
        payload = encoded(value).replace(b'"protocol"', b'"\\u0070rotocol"').replace(b"source_fact_scan_v1", b"source_fact_scan_v\\u0031")
    elif variant in ("ordinary_duplicate", "escaped_duplicate"):
        key = b'"protocol"' if variant == "ordinary_duplicate" else b'"\\u0070rotocol"'
        payload = b'{' + key + b':"source_fact_scan_v1",' + encoded(value)[1:]
        code = "invalid_request"
    else:
        if variant == "entry_4095": value["caller"]["entry_id"] = 4095
        elif variant == "start_524288": value["selection"] = {"start": 524288, "end": 524288}
        elif variant == "start_524289": value["selection"]["start"] = 524289; code = "invalid_request"
        else: value["selection"]["end"] = 524289; code = "invalid_request"
        payload = encoded(value)
    status, response = actual_exchange(request, images, "source_scanner", payload)
    if code is not None:
        assert status == 2 and response == encoded({"protocol": "source_fact_scan_v1", "status": "error", "code": code})
    else:
        assert status == 0
        if variant in ("request_1500000", "escaped_control"):
            assert response == control_raw
        else:
            expected = json.loads(control_raw)
            if variant == "entry_4095":
                expected["caller"]["entry_id"] = expected["selector"]["entry_id"] = 4095
            else:
                expected["selector"] = {"state": "unavailable", "reason": "selector_span_invalid"}
                expected["header"] = {"state": "unavailable", "reason": "selector_unavailable"}
            assert json.loads(response) == expected


@pytest.mark.parametrize("variant", ["request_65536", "depth_13", "ordinary_duplicate", "xml_caller_collision", "xml_candidate_collision"])
def test_actual_rust_framed_gap_variants(request, images, variant):
    value = kernel_control()
    status, control = actual_exchange(request, images, "source_kernel", encoded(value))
    assert status == 0 and json.loads(control) == kernel_expected(value)
    if variant == "request_65536":
        raw = encoded(value); payload = b'{' + b' ' * (65536 - len(raw)) + raw[1:]
        assert len(payload) == 65536
    elif variant == "depth_13": payload = b'{"nested":' + b'{"x":' * 12 + b'0' + b'}' * 12 + b',' + encoded(value)[1:]
    elif variant == "ordinary_duplicate": payload = encoded(value).replace(b'"case_id":1', b'"case_id":1,"case_id":1', 1)
    else:
        entry = value["scope"]["caller_entry_id" if variant == "xml_caller_collision" else "candidate_entry_id"]
        value["scope"]["xml_entry_id"] = value["receipts"]["server"]["entry_id"] = entry
        payload = encoded(value)
    status, result = actual_exchange(request, images, "source_kernel", payload)
    if variant == "request_65536": assert status == 0 and result == control
    else: assert status == 2 and result == encoded({"protocol": "submitted_source_facts_v1", "status": "error", "code": "invalid_envelope"})


def test_valid_rust_assertion_does_not_authenticate_forged_go(request, images, capsys):
    values = scan_fixture()
    assert validate_fixture(copy.deepcopy(values))[0] == values[4]
    envelope = kernel_control()
    status, raw = actual_exchange(request, images, "source_kernel", encoded(envelope))
    assert status == 0 and validate_kernel(raw, envelope) == kernel_expected(envelope)
    values[4]["caller"]["raw_sha256"] = "0" * 64
    # The same well-shaped assertion still passes Rust, without authenticating
    # changed scanner provenance. The host must reject the forged Go receipt.
    status, replay = actual_exchange(request, images, "source_kernel", encoded(envelope))
    assert status == 0 and replay == raw
    closed_failure(lambda: validate_fixture(values), "RECEIPT_INVALID", capsys)
