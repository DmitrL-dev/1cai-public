"""Root-private prospective Main receiver SOURCE; not run/imported by author.
One original RLD and RWR storage/DLL per new disposable host, HELLO/ACK only.
Root admits exact C/H/DLL/fixtures/SID/configs and freezes all ancestors outside.
Receiver ABI 152/184 includes actual exported peer comparisons; no PID adoption.
Actual final RWR status is read only after native producer return and worker join.
Negative native mismatch keeps original first-P105/error5 and auto-stop semantics.
All native backing objects remain in _RETAIN until immediate OWN HOST exit.
"""
from __future__ import annotations
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

U16, U32, U64, I32 = C.c_uint16, C.c_uint32, C.c_uint64, C.c_int32
STATUS_SLOT, STOP_INDEX, RUN_MS, CLOSE_MS = 0xffffffff, 16, 4000, 2500
ABI = [1, 8, 65536, 8, 8368, 24, 16, 32, 152, 120, 20624, 40]
INPUT_KEYS = ("C", "header", "base_header", "dll", "node", "parent", "child")
EXPECTED = {
    "C": (75900, "fe81974981d4ab20156814d1dfae6f90610cabb8f5a0fff0cebcbd49c3a8e16e"),
    "header": (5622, "92869b7a616198fbf8f6beb83f074e9e82df3a3cf000bbd454e0868248bef280"),
    "base_header": (6141, "b14f94f5674ec55b2f8fc15900bb63e5b466ce21406042c6c204bdefae84328c"),
    "node": (91694408, "3331e1ffe19874215472217c5e94f5a0c6d8e18c4ac7111d3937aa0ad5e9b4a5"),
    "parent": (5294, "11015fc699e645f927f286b55db743cfaedf020eff60a39426b2b3ff6527118f"),
    "child": (43, "5748b8d4f8bc52c6871ccf135e0fda61670a8e69c0567ff9419afcfac3476411"),
}
_RETAIN = []
_CALLS = []
_PRIMARY = []
_ERROR_LOCK = threading.Lock()
_PAUSE = threading.Event()

class Call(C.Structure):
    _fields_ = [("entered", I32), ("done", I32), ("ok", U32), ("error", U32)]
class Clock(C.Structure):
    _fields_ = [("call", Call), ("tick_ms", U64)]
class Storage(C.Structure):
    _fields_ = [("opaque", U64 * 8192)]
class Args(C.Structure):
    _fields_ = [
        ("magic", U32), ("version", U32), ("size_bytes", U32), ("reserved0", U32),
        ("generation", U64), ("session_cookie", U64),
        ("run_until_tick_ms", U64), ("closure_until_tick_ms", U64),
        ("node_path", U16 * 1024), ("parent_fixture", U16 * 1024),
        ("child_fixture", U16 * 1024), ("working_directory", U16 * 1024),
        ("node_sha256", C.c_uint8 * 32), ("parent_sha256", C.c_uint8 * 32),
        ("child_sha256", C.c_uint8 * 32), ("reserved1", U32 * 8),
    ]
class Event(C.Structure):
    _fields_ = [
        ("sequence", U32), ("code", U32), ("pid", U32), ("tid", U32),
        ("disposition", U32), ("continued", U32), ("detail", U32),
        ("first_chance", U32), ("elapsed_ms", U64),
    ]
class Snapshot(C.Structure):
    _fields_ = [
        ("generation", U64), ("session_cookie", U64),
        ("phase", U32), ("primary_stage", U32), ("primary_error", U32),
        ("cleanup_stage", U32), ("cleanup_error", U32),
        ("candidate_count", U32), ("event_count", U32),
        ("exit_count", U32), ("owned_handles_remaining", U32),
        ("system_handles_pending", U32), ("job_empty", U32), ("cleanup_complete", U32),
        ("worker_returned", U32), ("stop_requested", U32), ("query_live", U32), ("slot", U32),
        ("birth_filetime", U64), ("birth_event_sequence", U32),
        ("image_matches_pin", U32), ("job_member", U32), ("signaled", U32),
        ("grants", U32), ("reserved", U32 * 3),
    ]
class CommandArgs(C.Structure):
    _fields_ = [
        ("op", U32), ("index", U32), ("slot", U32), ("reserved", U32),
        ("generation", U64), ("session_cookie", U64),
    ]
class CommandOut(C.Structure):
    _fields_ = [
        ("call", Call), ("submit_done", I32), ("accepted", I32),
        ("command_index", U64), ("snapshot", Snapshot),
    ]
class RunOut(C.Structure):
    _fields_ = [
        ("call", Call), ("snapshot", Snapshot),
        ("ledger_count", U32), ("reserved", U32), ("ledger", Event * 512),
    ]

def need(ok, why):
    if not ok:
        raise RuntimeError(why)

def record_failure(exc):
    with _ERROR_LOCK:
        _RETAIN.append(exc)
        if not _PRIMARY:
            _PRIMARY.append(exc)  # first object and its diagnostics are preserved

def summary_error(exc):
    return {"type": type(exc).__name__, "message": str(exc)[:1024]}

def object_pairs(pairs):
    d = {}
    for k, v in pairs:
        need(k not in d, "duplicate JSON key")
        d[k] = v
    return d

def rejected_number(value):
    raise ValueError("noninteger/nonfinite config JSON number")

def read_config(path, cap=16384):
    with path.open("rb") as f:
        raw = f.read(cap + 1)
    need(len(raw) <= cap, "config cap")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs,
                      parse_float=rejected_number, parse_constant=rejected_number)

def absolute(value):
    need(type(value) is str and value, "absolute Windows path required")
    p = Path(value)
    need(p.is_absolute() and re.fullmatch(r"[A-Za-z]:", p.drive) is not None,
         "drive-rooted path required")
    s = str(p)
    need(not s.startswith("\\\\") and len(s.encode("utf-16-le")) // 2 < 1024,
         "path length/namespace")
    return p

def uint(value, bits):
    need(type(value) is int and 0 < value < (1 << bits), "nonzero unsigned integer")
    return value

def pin(ref, expected=None, cap=128 * 1024 * 1024):
    need(type(ref) is dict and set(ref) == {"path", "size_bytes", "sha256"}, "pin fields")
    p = absolute(ref["path"])
    count = uint(ref["size_bytes"], 64)
    sha = ref["sha256"]
    need(count <= cap and type(sha) is str and re.fullmatch("[0-9a-f]{64}", sha),
         "pin size/SHA")
    if expected is not None:
        need((count, sha) == expected, "wrong approved input pin")
    need(p.stat().st_size == count, "actual file size")
    h, consumed = hashlib.sha256(), 0
    with p.open("rb") as f:
        while True:
            part = f.read(65536)
            if not part:
                break
            consumed += len(part)
            need(consumed <= count, "growing file")
            h.update(part)
    need(consumed == count and h.hexdigest() == sha, "actual file SHA")
    return p

def layout():
    need(os.name == "nt" and sys.maxsize > 2**32 and C.sizeof(C.c_void_p) == 8
         and C.sizeof(C.c_wchar) == 2 and sys.byteorder == "little",
         "Windows x64 only")
    sizes = {Storage: 65536, Args: 8368, Clock: 24, Call: 16,
             CommandArgs: 32, CommandOut: 152, Snapshot: 120, RunOut: 20624, Event: 40}
    for typ, size in sizes.items():
        need(C.sizeof(typ) == size, "ctypes size " + typ.__name__)
    for typ in (Storage, Args, Clock, CommandArgs, CommandOut, Snapshot, RunOut, Event):
        need(C.alignment(typ) == 8, "ctypes alignment " + typ.__name__)
    need(C.alignment(Call) == 4, "Call alignment")
    offsets = {
        Call: {"entered": 0, "done": 4, "ok": 8, "error": 12},
        Clock: {"call": 0, "tick_ms": 16},
        Args: {"magic": 0, "version": 4, "size_bytes": 8, "reserved0": 12,
               "generation": 16, "session_cookie": 24, "run_until_tick_ms": 32,
               "closure_until_tick_ms": 40, "node_path": 48, "parent_fixture": 2096,
               "child_fixture": 4144, "working_directory": 6192,
               "node_sha256": 8240, "parent_sha256": 8272, "child_sha256": 8304,
               "reserved1": 8336},
        Event: {"sequence": 0, "code": 4, "pid": 8, "tid": 12,
                "disposition": 16, "continued": 20, "detail": 24,
                "first_chance": 28, "elapsed_ms": 32},
        Snapshot: {"generation": 0, "session_cookie": 8, "phase": 16,
                   "primary_stage": 20, "primary_error": 24, "cleanup_stage": 28,
                   "cleanup_error": 32, "candidate_count": 36, "event_count": 40,
                   "exit_count": 44, "owned_handles_remaining": 48,
                   "system_handles_pending": 52, "job_empty": 56, "cleanup_complete": 60,
                   "worker_returned": 64, "stop_requested": 68, "query_live": 72,
                   "slot": 76, "birth_filetime": 80, "birth_event_sequence": 88,
                   "image_matches_pin": 92, "job_member": 96, "signaled": 100,
                   "grants": 104, "reserved": 108},
        CommandArgs: {"op": 0, "index": 4, "slot": 8, "reserved": 12,
                      "generation": 16, "session_cookie": 24},
        CommandOut: {"call": 0, "submit_done": 16, "accepted": 20,
                     "command_index": 24, "snapshot": 32},
        RunOut: {"call": 0, "snapshot": 16, "ledger_count": 136,
                 "reserved": 140, "ledger": 144},
    }
    for typ, fields in offsets.items():
        for field, expected in fields.items():
            need(getattr(typ, field).offset == expected, "offset " + typ.__name__ + "." + field)
    return {"ABI": ABI, "sizes": {typ.__name__: size for typ, size in sizes.items()},
            "offsets_checked": sum(map(len, offsets.values()))}

def invoke(name, fn, *buffers):
    rec = {"name": name, "producer_started": False, "producer_ended": False}
    _CALLS.append(rec)
    _RETAIN.extend((rec, fn, buffers))
    rec["producer_started"] = True
    try:
        fn(*(C.byref(x) for x in buffers))
    except BaseException as exc:
        rec["exception"] = summary_error(exc)
        record_failure(exc)
        raise
    finally:
        rec["producer_ended"] = True

def bind(dll_path):
    dll = C.WinDLL(str(dll_path), winmode=0x00000900)
    _RETAIN.append(dll)
    signatures = (
        ("rld_abi", [C.POINTER(U32)]),
        ("rld_clock", [C.POINTER(Clock)]),
        ("rld_init", [C.POINTER(Storage), C.POINTER(Args), C.POINTER(Call)]),
        ("rld_run", [C.POINTER(Storage), C.POINTER(RunOut)]),
        ("rld_submit", [C.POINTER(Storage), C.POINTER(CommandArgs), C.POINTER(CommandOut)]),
    )
    for name, types in signatures:
        fn = getattr(dll, name)
        fn.argtypes, fn.restype = types, None
        _RETAIN.append(fn)
    out = (U32 * 12)()
    _RETAIN.append(out)
    # rld_abi's parameter is a decayed uint32 array, not pointer-to-array.
    rec = {"name": "rld_abi", "producer_started": True, "producer_ended": False}
    _CALLS.append(rec)
    _RETAIN.append(rec)
    try:
        dll.rld_abi(out)
    finally:
        rec["producer_ended"] = True
    need(list(out) == ABI, "actual DLL ABI mismatch")
    return dll

def call_data(o):
    return {k: int(getattr(o, k)) for k in ("entered", "done", "ok", "error")}

def flat(o):
    return {name: int(getattr(o, name)) for name, _ in o._fields_ if name != "reserved"}

def path_field(out, name, value):
    units = str(value).encode("utf-16-le")
    need(len(units) // 2 < 1024, "path field cap")
    field = getattr(out, name)
    for i in range(0, len(units), 2):
        field[i // 2] = units[i] | units[i + 1] << 8

def wait_until(predicate, end, step=0.01):
    while not predicate():
        remaining = end - time.monotonic()
        if remaining <= 0:
            return False
        _PAUSE.wait(min(step, remaining))
    return True

RWR_ABI = [1, 8, 32768, 8, 1472, 24, 184, 152, 16, 1024, 4096, 2, 16]
class ReceiverStorage(C.Structure):
    _fields_ = [("opaque", U64 * 4096)]
class ReceiverArgs(C.Structure):
    _fields_ = [
        ("magic", U32), ("version", U32), ("size_bytes", U32), ("reserved0", U32),
        ("generation", U64), ("session_cookie", U64),
        ("run_until_tick_ms", U64), ("closure_until_tick_ms", U64),
        ("expected_slot", U32), ("hello_bytes", U32), ("sid_bytes", U32), ("pipe_access_mask", U32),
        ("expected_current_user_sid", C.c_uint8 * 68),
        ("instance", C.c_char * 33), ("nonce", C.c_char * 33), ("run", C.c_char * 129),
        ("generation_text", C.c_char * 21), ("source_copy_pin", C.c_char * 65),
        ("reserved_bytes", C.c_uint8 * 3), ("hello", C.c_uint8 * 1024), ("reserved", U32 * 8)]
class ReceiverStatus(C.Structure):
    _fields_ = [
        ("generation", U64), ("session_cookie", U64),
        ("phase", U32), ("primary_stage", U32), ("primary_error", U32),
        ("cleanup_stage", U32), ("cleanup_error", U32),
        ("expected_slot", U32), ("registered", U32), ("listen_created", U32),
        ("connected", U32), ("peer_match", U32), ("hello_completed", U32),
        ("ack_issued", U32), ("ack_completed", U32), ("authenticated", U32), ("revoked", U32),
        ("io_pending", U32), ("producer_pending", U32), ("io_terminal", U32),
        ("retired", U32), ("owned_handles_remaining", U32), ("unknown", U32),
        ("hello_wire_bytes", U32), ("ack_wire_bytes", U32), ("status_index", U32),
        ("birth_filetime", U64), ("birth_event_sequence", U32), ("grants", U32),
        ("client_pid", U32), ("expected_held_pid", U32),
        ("peer_compare_attempted", U32), ("peer_compare_match", U32),
        ("peer_bracket_before", U32), ("peer_bracket_after", U32)]
class ReceiverStatusArgs(C.Structure):
    _fields_ = [("index", U32), ("reserved", U32), ("generation", U64), ("session_cookie", U64)]
class ReceiverStatusOut(C.Structure):
    _fields_ = [("call", Call), ("submit_done", I32), ("accepted", I32),
                ("command_index", U64), ("status", ReceiverStatus)]

def receiver_layout():
    sizes = {ReceiverStorage: 32768, ReceiverArgs: 1472, ReceiverStatus: 152,
             ReceiverStatusArgs: 24, ReceiverStatusOut: 184}
    offsets = {
        ReceiverArgs: {"magic": 0, "version": 4, "size_bytes": 8, "reserved0": 12,
            "generation": 16, "session_cookie": 24, "run_until_tick_ms": 32, "closure_until_tick_ms": 40,
            "expected_slot": 48, "hello_bytes": 52, "sid_bytes": 56, "pipe_access_mask": 60,
            "expected_current_user_sid": 64, "instance": 132, "nonce": 165, "run": 198,
            "generation_text": 327, "source_copy_pin": 348, "reserved_bytes": 413,
            "hello": 416, "reserved": 1440},
        ReceiverStatus: {"generation": 0, "session_cookie": 8, "phase": 16,
            "primary_stage": 20, "primary_error": 24, "cleanup_stage": 28, "cleanup_error": 32,
            "expected_slot": 36, "registered": 40, "listen_created": 44, "connected": 48,
            "peer_match": 52, "hello_completed": 56, "ack_issued": 60, "ack_completed": 64,
            "authenticated": 68, "revoked": 72, "io_pending": 76, "producer_pending": 80,
            "io_terminal": 84, "retired": 88, "owned_handles_remaining": 92, "unknown": 96,
            "hello_wire_bytes": 100, "ack_wire_bytes": 104, "status_index": 108,
            "birth_filetime": 112, "birth_event_sequence": 120, "grants": 124,
            "client_pid": 128, "expected_held_pid": 132, "peer_compare_attempted": 136,
            "peer_compare_match": 140, "peer_bracket_before": 144, "peer_bracket_after": 148},
        ReceiverStatusArgs: {"index": 0, "reserved": 4, "generation": 8, "session_cookie": 16},
        ReceiverStatusOut: {"call": 0, "submit_done": 16, "accepted": 20,
                            "command_index": 24, "status": 32}}
    for typ, size in sizes.items():
        need(C.sizeof(typ) == size and C.alignment(typ) == 8, "receiver size/alignment " + typ.__name__)
    for typ, fields in offsets.items():
        for field, offset in fields.items():
            need(getattr(typ, field).offset == offset, "receiver offset " + typ.__name__ + "." + field)
    return {"ABI": RWR_ABI, "sizes": {typ.__name__: size for typ, size in sizes.items()},
            "offsets_checked": sum(map(len, offsets.values()))}

def bind_receiver(dll):
    signatures = (
        ("rwr_abi", [C.POINTER(U32)]),
        ("rwr_register", [C.POINTER(Storage), C.POINTER(ReceiverStorage), C.POINTER(ReceiverArgs), C.POINTER(Call)]),
        ("rwr_submit_status", [C.POINTER(Storage), C.POINTER(ReceiverStorage),
                               C.POINTER(ReceiverStatusArgs), C.POINTER(ReceiverStatusOut)]),
        ("rwr_final_status", [C.POINTER(Storage), C.POINTER(ReceiverStorage), C.POINTER(ReceiverStatusOut)]))
    for name, types in signatures:
        fn = getattr(dll, name)
        fn.argtypes, fn.restype = types, None
        _RETAIN.append(fn)
    out = (U32 * 13)()
    rec = {"name": "rwr_abi", "producer_started": True, "producer_ended": False}
    _RETAIN.extend((out, rec))
    _CALLS.append(rec)
    try:
        dll.rwr_abi(out)
    finally:
        rec["producer_ended"] = True
    need(list(out) == RWR_ABI, "actual receiver DLL ABI mismatch")

def receiver_config(cfg, admission, cli_case):
    r = cfg["receiver"]
    need(type(r) is dict and set(r) == {"expected_slot", "sid_ref", "instance", "nonce", "run", "source_copy_pin"},
         "exact receiver config")
    need(type(r["expected_slot"]) is int and r["expected_slot"] ==
         (0 if cli_case == "expected_parent_slot0" else 1), "exact original expected slot")
    for key in ("instance", "nonce"):
        need(type(r[key]) is str and re.fullmatch("[0-9a-f]{32}", r[key]), "receiver " + key)
    need(type(r["run"]) is str and re.fullmatch(r"[A-Za-z0-9._-]{1,128}", r["run"]), "receiver run token")
    need(r["source_copy_pin"] == cfg["parent"]["sha256"], "actual measured parent Source label")
    need(r["sid_ref"] in admission["additional_frozen_inputs"], "actual SID is a Root-frozen input")
    sid_path = pin(r["sid_ref"], cap=68)
    with sid_path.open("rb") as f:
        sid = f.read(69)
    need(8 <= len(sid) <= 68 and sid[0] == 1 and sid[1] <= 15 and len(sid) == 8 + 4 * sid[1],
         "bounded binary SID shape; native independently checks current token identity")
    _RETAIN.extend((r, sid))
    return r, sid

def fill_receiver_args(out, r, sid, original):
    out.magic, out.version, out.size_bytes = 0x31525752, 1, 1472
    out.generation, out.session_cookie = original.generation, original.session_cookie
    out.run_until_tick_ms, out.closure_until_tick_ms = original.run_until_tick_ms, original.closure_until_tick_ms
    out.expected_slot, out.sid_bytes, out.pipe_access_mask = r["expected_slot"], len(sid), 0x0012019f
    for i, byte in enumerate(sid):
        out.expected_current_user_sid[i] = byte
    out.instance, out.nonce, out.run = r["instance"].encode("ascii"), r["nonce"].encode("ascii"), r["run"].encode("ascii")
    out.generation_text = str(int(original.generation)).encode("ascii")
    out.source_copy_pin = r["source_copy_pin"].encode("ascii")
    hello = {"schema": "root-main-witness-control/1", "kind": "hello", "instance": r["instance"],
             "nonce": r["nonce"], "run": r["run"], "generation": str(int(original.generation)),
             "sourceCopyPin": r["source_copy_pin"]}
    raw = json.dumps(hello, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    need(0 < len(raw) <= 1024, "exact canonical HELLO cap")
    out.hello_bytes = len(raw)
    for i, byte in enumerate(raw):
        out.hello[i] = byte
    _RETAIN.extend((hello, raw))
    return {"instance": r["instance"], "nonce": r["nonce"], "run": r["run"],
            "generation_text": str(int(original.generation)), "source_copy_pin": r["source_copy_pin"],
            "expected_slot": r["expected_slot"], "sid_ref": r["sid_ref"], "hello_body_bytes": len(raw),
            "hello_body_sha256": hashlib.sha256(raw).hexdigest(), "pipe_access_mask": 0x0012019f}

def receiver_request(dll, storage, receiver, args, index, requests, end=None, worker_ended=None):
    request, out = ReceiverStatusArgs(), ReceiverStatusOut()
    request.index, request.generation, request.session_cookie = index, args.generation, args.session_cookie
    requests.append((request, out))
    _RETAIN.extend((request, out))
    invoke("rwr_submit_status", dll.rwr_submit_status, storage, receiver, request, out)
    if end is not None:
        need(wait_until(lambda: out.call.done == 1 or worker_ended.is_set(), end), "receiver status fixed deadline")
    need(out.call.done == 1, "receiver status completion unknown")
    item = {"index": index, "accepted": int(out.accepted), "submit_done": int(out.submit_done),
            "command_index": int(out.command_index), "call": call_data(out.call), "status": flat(out.status)}
    return item

def validate_receiver_observation(item, args, index):
    need(item["submit_done"] == item["accepted"] == 1 and item["command_index"] == index and
         item["call"] == {"entered": 1, "done": 1, "ok": 1, "error": 0}, "receiver status actual accepted observation")
    s = item["status"]
    need(s["generation"] == args.generation and s["session_cookie"] == args.session_cookie and
         s["status_index"] == index and s["grants"] == 0 and s["unknown"] == 0,
         "receiver original-pair observation binding")

def receiver_final_observation(dll, storage, receiver):
    out = ReceiverStatusOut()
    _RETAIN.append(out)
    invoke("rwr_final_status", dll.rwr_final_status, storage, receiver, out)
    need(out.call.done == 1, "actual receiver final-status publication")
    # Preserve the actual completed output even on refusal. Verification below
    # decides whether it qualifies this exact case; no terminal bits are added.
    return {"accepted": int(out.accepted), "submit_done": int(out.submit_done),
            "command_index": int(out.command_index), "call": call_data(out.call), "status": flat(out.status)}

def observe_receiver(dll, storage, receiver, args, requests, result, control_end, worker_ended, snapshots):
    for index in range(16):  # every status output is fresh and observed once
        need(time.monotonic() < control_end and not worker_ended.is_set(), "receiver fixed original control budget")
        item = receiver_request(dll, storage, receiver, args, index, requests, control_end, worker_ended)
        result.setdefault("receiver_status_observations", []).append(item)
        # Completed native fields are retained above BEFORE any schema, binding,
        # peer, success or cleanup assertion, including an unexpected refusal.
        validate_receiver_observation(item, args, index)
        s = item["status"]
        need(s["expected_slot"] == 0 and s["registered"] == 1,
             "receiver exact expected original slot")
        complete = s["authenticated"] == 1
        if complete:
            need(s["listen_created"] == 1 and s["connected"] == 1 and s["peer_compare_attempted"] == 1 and
                 s["peer_bracket_before"] == s["peer_bracket_after"] == 1 and
                 s["client_pid"] > 0 and s["expected_held_pid"] > 0 and
                 s["birth_filetime"] == snapshots[s["expected_slot"]]["birth_filetime"] and
                 s["birth_event_sequence"] == snapshots[s["expected_slot"]]["birth_event_sequence"],
                 "actual original held-birth peer brackets")
            need(s["primary_stage"] == s["primary_error"] == s["cleanup_stage"] == s["cleanup_error"] == 0 and
                 s["peer_match"] == s["peer_compare_match"] == 1 and s["client_pid"] == s["expected_held_pid"] and
                 s["phase"] == 6 and s["hello_completed"] == s["ack_issued"] == s["ack_completed"] == 1 and
                 s["revoked"] == 0 and s["hello_wire_bytes"] == result["receiver_binding"]["hello_body_bytes"] + 4 and
                 5 <= s["ack_wire_bytes"] <= 1028, "authenticated exact HELLO/ACK observation")
            result["receiver_live_observation"] = item
            return
        need(s["primary_stage"] == 0 and s["cleanup_stage"] == 0 and s["revoked"] == 0,
             "receiver premature failure rather than required peer case")
        remaining = control_end - time.monotonic()
        need(remaining > 0, "receiver original control end")
        _PAUSE.wait(min(0.15, remaining))
    raise RuntimeError("receiver single-use status cap exhausted; no retry")

def verify_receiver_terminal(result, snapshots):
    item = result["receiver_terminal_observation"]
    final = item["status"]
    native_final = result["final_snapshot"]
    positive = result["case"] == "expected_parent_slot0"
    expected = 0 if positive else 1
    need(item["accepted"] == item["submit_done"] == 1 and item["command_index"] == (1 << 64) - 1 and
         item["call"] == {"entered": 1, "done": 1, "ok": 1, "error": 0} and
         final["status_index"] == (1 << 32) - 1 and
         final["generation"] == result["original_binding"]["generation"] and
         final["session_cookie"] == result["original_binding"]["session_cookie"] and
         final["expected_slot"] == expected, "actual final receiver observation identity")
    need(final["phase"] == 8 and final["registered"] == final["revoked"] == 1 and
         final["authenticated"] == 0 and final["io_pending"] == final["producer_pending"] == 0 and
         final["io_terminal"] == final["retired"] == 1 and final["owned_handles_remaining"] == 0 and
         final["cleanup_stage"] == final["cleanup_error"] == final["unknown"] == final["grants"] == 0,
         "actual raw receiver terminal IO/producers/checked-handle retirement")
    need(native_final["cleanup_complete"] == 1 and native_final["worker_returned"] == 1 and
         native_final["owned_handles_remaining"] == native_final["system_handles_pending"] == 0 and
         native_final["cleanup_stage"] == native_final["cleanup_error"] == 0 and
         result["Python_worker_producer_ended"] and result["Python_worker_joined"],
         "exact native final cleanup gate includes actual receiver IO/producers/checked handles")
    need(all(call["producer_ended"] for call in _CALLS), "all original native-call producers ended")
    births = [e for e in result["ledger"] if e["code"] == 3]
    need(len(births) == 2 and births[0]["sequence"] < births[1]["sequence"] and
         final["listen_created"] == final["connected"] == final["peer_compare_attempted"] == 1 and
         final["peer_bracket_before"] == final["peer_bracket_after"] == 1 and
         final["birth_filetime"] > 0 and final["birth_event_sequence"] == births[expected]["sequence"] and
         final["client_pid"] == births[0]["pid"] and final["expected_held_pid"] == births[expected]["pid"],
         "actual parent client PID joins original debug CREATE ledger; negative expected child PID")
    if positive:
        live = result["receiver_live_observation"]["status"]
        need(final["primary_stage"] == final["primary_error"] == 0 and
             final["peer_match"] == final["peer_compare_match"] == 1 and
             final["hello_completed"] == final["ack_issued"] == final["ack_completed"] == 1 and
             len(snapshots) == 2 and final["birth_filetime"] == snapshots[0]["birth_filetime"],
             "positive retained HELLO/ACK and original live birth FILETIME")
        for key in ("client_pid", "expected_held_pid", "peer_compare_attempted", "peer_compare_match",
                    "peer_bracket_before", "peer_bracket_after", "birth_filetime", "birth_event_sequence",
                    "hello_completed", "ack_issued", "ack_completed", "hello_wire_bytes", "ack_wire_bytes"):
            need(final[key] == live[key], "actual terminal retained witness " + key)
    else:
        need(final["primary_stage"] == 105 and final["primary_error"] == 5 and
             final["peer_match"] == final["peer_compare_match"] == 0 and
             final["client_pid"] != final["expected_held_pid"] and
             final["hello_completed"] == final["ack_issued"] == final["ack_completed"] == 0 and
             final["hello_wire_bytes"] == final["ack_wire_bytes"] == 0,
             "actual terminal wrong-original-child mismatch refused without HELLO/ACK")
    result["receiver_IO_producer_handle_retirement_observed_known"] = True
    result["actual_parent_client_expected_original_slot_join_observed"] = True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=("expected_parent_slot0", "expected_child_slot1"), required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--output", required=True)
    cli = ap.parse_args()
    result_path = absolute(cli.output)
    # Root created/froze the private output directory; output is never reused.
    need(result_path.parent.is_dir() and not result_path.exists(), "exclusive new output")
    result = {
        "schema": "rentgen-Main-receiver-synthetic-DLL-ctypes-Root-case/1", "case": cli.case,
        "synthetic_case_passed": False, "cleanup_observed_known": False,
        "EditorRole": False, "OwnerIPC": False, "READY": False, "Core": False,
        "model": False, "native_1C": False, "release": False,
        "runtime_qualified": False, "production_deployment": False,
    }
    dll = storage = args = run_out = worker = stop_out = None
    worker_ended = threading.Event()
    worker_error = []
    requests = []
    init_ok = False
    positive_snapshots = []
    join_end = control_end = None
    stop_attempted = False
    first_failure = None
    receiver_storage = receiver_args = receiver_register_out = None
    receiver_registered = False
    receiver_requests = []
    try:
        result["layout"] = layout()
        result["receiver_layout"] = receiver_layout()
        need(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
             "Root launcher must use -I -S -B")
        config_path = absolute(cli.config)
        cfg = read_config(config_path)
        required = {"schema", "case", "verifier", "python", "C", "header", "base_header", "dll",
                    "node", "parent", "child", "working_directory", "generation",
                    "session_cookie", "receiver", "Root_freeze_ref", "Root_execution_admission_ref"}
        need(type(cfg) is dict and set(cfg) == required and
             cfg["schema"] == "rentgen-Root-Main-receiver-verifier-inputs/1" and
             cfg["case"] == cli.case, "config schema/case")
        need(pin(cfg["verifier"], cap=131072) == Path(__file__), "verifier file binding")
        need(pin(cfg["python"]) == Path(sys.executable), "original Python image path")
        paths = {key: pin(cfg[key], EXPECTED.get(key)) for key in INPUT_KEYS}
        pin(cfg["Root_freeze_ref"], cap=1048576)
        pin(cfg["Root_execution_admission_ref"], cap=1048576)
        admission = read_config(absolute(cfg["Root_execution_admission_ref"]["path"]), 1048576)
        need(admission["schema"] == "rentgen-Root-Main-receiver-two-hosts-execution-admission/2" and
             admission["Root_execution_admitted"] is True and admission["verifier"] == cfg["verifier"] and
             admission["python"] == cfg["python"] and admission["inputs"] == {key: cfg[key] for key in INPUT_KEYS},
             "externally pinned Root exact candidate admission before native effects")
        need(absolute(admission["owned_directory"]).parent == absolute(admission["evidence_root"]) and
             absolute(cfg["working_directory"]).parent == absolute(admission["owned_directory"]),
             "exact public evidence-root/owned-case admission binding")
        pin(admission["outer_helper"], cap=131072)
        need(admission["outer_helper"] in admission["additional_frozen_inputs"],
             "actual outer helper retained in external freeze")
        seed_ref = admission["case_seeds"][cli.case]
        pin(seed_ref, cap=16384)
        seed = read_config(absolute(seed_ref["path"]))
        need(seed["case"] == cli.case and all(seed[key] == cfg[key] for key in
             ("working_directory", "generation", "session_cookie", "receiver")), "exact admitted original case seed")
        receiver_values, receiver_sid = receiver_config(cfg, admission, cli.case)
        workdir = absolute(cfg["working_directory"])
        need(workdir.is_dir() and paths["parent"] != paths["child"] and
             str(paths["parent"]).lower().endswith(".cjs") and
             str(paths["child"]).lower().endswith(".cjs"), "fixture/CWD paths")
        result["inputs"] = {key: cfg[key] for key in INPUT_KEYS +
                            ("verifier", "python", "Root_freeze_ref", "Root_execution_admission_ref")}
        result["Root_freeze_external_only"] = True
        # A receipt/hash is not proof of currently live freeze handles.
        dll = bind(paths["dll"])
        bind_receiver(dll)
        native_clock = Clock()
        _RETAIN.append(native_clock)
        monotonic_start = time.monotonic()
        invoke("rld_clock", dll.rld_clock, native_clock)
        need(call_data(native_clock.call) == {"entered": 1, "done": 1, "ok": 1, "error": 0},
             "native clock")
        args, storage, run_out, init_out = Args(), Storage(), RunOut(), Call()
        _RETAIN.extend((args, storage, run_out, init_out))
        need(C.addressof(storage) % 8 == 0, "original storage alignment")
        args.magic, args.version, args.size_bytes = 0x314c4452, 1, 8368
        args.generation = uint(cfg["generation"], 64)
        args.session_cookie = uint(cfg["session_cookie"], 64)
        args.run_until_tick_ms = int(native_clock.tick_ms) + RUN_MS
        args.closure_until_tick_ms = int(args.run_until_tick_ms) + CLOSE_MS
        for name, value in (("node_path", paths["node"]), ("parent_fixture", paths["parent"]),
                            ("child_fixture", paths["child"]), ("working_directory", workdir)):
            path_field(args, name, value)
        for role in ("node", "parent", "child"):
            field = getattr(args, role + "_sha256")
            for i, byte in enumerate(bytes.fromhex(cfg[role]["sha256"])):
                field[i] = byte
        result["original_binding"] = {
            "generation": int(args.generation), "session_cookie": int(args.session_cookie),
            "run_until_tick_ms": int(args.run_until_tick_ms),
            "closure_until_tick_ms": int(args.closure_until_tick_ms),
            "run_ms": RUN_MS, "closure_ms": CLOSE_MS,
        }
        # These ends are set ONCE; waits/retries never renew native or host ends.
        control_end = monotonic_start + RUN_MS / 1000 - 0.10
        join_end = monotonic_start + (RUN_MS + CLOSE_MS) / 1000 + 0.30
        invoke("rld_init", dll.rld_init, storage, args, init_out)
        result["init"] = call_data(init_out)
        need(result["init"] == {"entered": 1, "done": 1, "ok": 1, "error": 0}, "init")
        init_ok = True
        receiver_storage, receiver_args, receiver_register_out = ReceiverStorage(), ReceiverArgs(), Call()
        _RETAIN.extend((receiver_storage, receiver_args, receiver_register_out, receiver_requests))
        need(C.addressof(receiver_storage) % 8 == 0 and C.addressof(receiver_storage) != C.addressof(storage),
             "separate original zeroed aligned receiver storage")
        result["receiver_binding"] = fill_receiver_args(receiver_args, receiver_values, receiver_sid, args)
        invoke("rwr_register", dll.rwr_register, storage, receiver_storage, receiver_args, receiver_register_out)
        result["receiver_register"] = call_data(receiver_register_out)
        need(result["receiver_register"] == {"entered": 1, "done": 1, "ok": 1, "error": 0}, "one original receiver registration")
        receiver_registered = True

        def debug_worker():
            try:
                invoke("rld_run", dll.rld_run, storage, run_out)
            except BaseException as exc:
                worker_error.append(exc)
                _RETAIN.append(exc)
            finally:
                worker_ended.set()  # AFTER actual native invocation return
        worker = threading.Thread(target=debug_worker, name="Root-rld-debug-worker", daemon=True)
        _RETAIN.extend((debug_worker, worker, worker_ended, worker_error, requests))
        worker.start()
        if cli.case == "expected_parent_slot0":
            index = 0
            while len(positive_snapshots) < 2:
                need(index < 16 and time.monotonic() < control_end and not worker_ended.is_set(),
                     "no live QUERY within fixed budget")
                request, out = CommandArgs(), CommandOut()
                request.op, request.index, request.slot = 1, index, len(positive_snapshots)
                request.generation, request.session_cookie = args.generation, args.session_cookie
                requests.append((request, out))
                _RETAIN.extend((request, out))
                invoke("rld_submit_QUERY", dll.rld_submit, storage, request, out)
                need(out.submit_done == 1, "submit did not return published state")
                need(wait_until(lambda: out.call.done == 1 or worker_ended.is_set(), control_end),
                     "QUERY completion unknown at control end")
                need(out.call.done == 1, "worker returned without command completion")
                item = {"index": index, "slot": int(request.slot),
                        "accepted": int(out.accepted), "call": call_data(out.call),
                        "snapshot": flat(out.snapshot)}
                result.setdefault("queries", []).append(item)
                if out.call.ok == 1:
                    s = item["snapshot"]
                    need(out.accepted == 1 and out.command_index == index and
                         s["query_live"] == 1 and s["slot"] == request.slot and
                         s["generation"] == args.generation and
                         s["session_cookie"] == args.session_cookie and s["phase"] == 3 and
                         s["candidate_count"] == 2 and s["exit_count"] == 0 and
                         s["stop_requested"] == 0 and s["image_matches_pin"] == 1 and
                         s["job_member"] == 1 and s["signaled"] == 0 and s["grants"] == 0 and
                         s["birth_filetime"] > 0 and s["birth_event_sequence"] > 0 and
                         s["primary_stage"] == 0 and s["cleanup_stage"] == 0,
                         "live QUERY binding")
                    positive_snapshots.append(s)
                else:
                    # Fresh read-only commands only; rejected/NOT_READY is not PASS.
                    need(out.call.error in (21, 995) and not worker_ended.is_set(),
                         "unexpected QUERY refusal")
                    remaining = control_end - time.monotonic()
                    need(remaining > 0, "fixed query deadline")
                    _PAUSE.wait(min(0.20, remaining))
                index += 1
            need(positive_snapshots[0]["birth_event_sequence"] !=
                 positive_snapshots[1]["birth_event_sequence"], "distinct held birth slots")
            result["both_original_live_slots_queried"] = True
            observe_receiver(dll, storage, receiver_storage, args, receiver_requests,
                             result, control_end, worker_ended, positive_snapshots)
        else:
            # Wrong-peer first-P triggers native STOP before live observations
            # can be demanded. Preserve that actual lifecycle and wait once.
            need(wait_until(worker_ended.is_set, join_end), "negative native auto-stop worker return unknown")
    except BaseException as exc:
        first_failure = exc
        record_failure(exc)
    finally:
        # Exactly one original STOP. Never close/unload/terminate by numerical PID.
        # Negative expected mismatch auto-stops natively; no caller STOP is
        # needed after its worker ended. A still-pending failure stays failed.
        if init_ok and worker is not None and worker.is_alive() and not worker_ended.is_set() and dll is not None:
            try:
                stop_attempted = True
                stop_args, stop_out = CommandArgs(), CommandOut()
                stop_args.op, stop_args.index, stop_args.slot = 2, STOP_INDEX, STATUS_SLOT
                stop_args.generation, stop_args.session_cookie = args.generation, args.session_cookie
                requests.append((stop_args, stop_out))
                _RETAIN.extend((stop_args, stop_out))
                invoke("rld_submit_STOP", dll.rld_submit, storage, stop_args, stop_out)
            except BaseException as exc:
                record_failure(exc)
                if first_failure is None:
                    first_failure = exc
        try:
            if worker is not None and join_end is not None:
                left = max(0.0, join_end - time.monotonic())
                worker.join(left)
            result["Python_worker_producer_ended"] = worker_ended.is_set()
            result["Python_worker_joined"] = worker is not None and not worker.is_alive()
            result["stop_attempted"] = stop_attempted
            if stop_out is not None and stop_out.call.done == 1:
                result["stop"] = {"accepted": int(stop_out.accepted),
                                  "submit_done": int(stop_out.submit_done),
                                  "command_index": int(stop_out.command_index),
                                  "call": call_data(stop_out.call), "snapshot": flat(stop_out.snapshot)}
            elif stop_out is not None:
                result["stop_pending_unknown"] = True
            # Never read run output before actual return AND Python worker join.
            if worker is not None and not worker.is_alive() and worker_ended.is_set() and not worker_error:
                result["run_call"] = call_data(run_out.call)
                if run_out.call.done == 1:
                    result["final_snapshot"] = flat(run_out.snapshot)
                    need(run_out.ledger_count <= 512, "bounded ledger")
                    result["ledger"] = [flat(run_out.ledger[i]) for i in range(run_out.ledger_count)]
                    result["ledger_count"] = int(run_out.ledger_count)
                    if receiver_registered:
                        result["receiver_terminal_observation"] = receiver_final_observation(
                            dll, storage, receiver_storage)
        except BaseException as exc:
            record_failure(exc)
            if first_failure is None:
                first_failure = exc
            result["harvest_failure"] = summary_error(exc)
        if _PRIMARY:
            result["first_Python_error"] = summary_error(_PRIMARY[0])
        result["native_call_producers"] = list(_CALLS)

    try:
        need(first_failure is None and not worker_error and result.get("Python_worker_producer_ended", False) and
             result.get("Python_worker_joined", False) and result.get("run_call", {}).get("done") == 1 and
             all(call["producer_ended"] for call in _CALLS),
             "driver/worker failure or pending")
        s = result["final_snapshot"]
        need(s["generation"] == args.generation and s["session_cookie"] == args.session_cookie and
             s["phase"] == 5 and s["cleanup_complete"] == 1 and
             s["owned_handles_remaining"] == 0 and s["system_handles_pending"] == 0 and
             s["cleanup_stage"] == 0 and s["cleanup_error"] == 0 and
             s["worker_returned"] == 1 and s["query_live"] == 0 and s["grants"] == 0,
             "known native terminal cleanup contract")
        result["birth_Job_cleanup_observed_known"] = True
        need(s["candidate_count"] == 2 and s["exit_count"] == 2 and s["job_empty"] == 1 and
             s["stop_requested"] == 1, "both original births and native stop/Job cleanup")
        if cli.case == "expected_parent_slot0":
            stop = result.get("stop", {})
            need(result["run_call"] == {"entered": 1, "done": 1, "ok": 1, "error": 0} and
                 s["primary_stage"] == s["primary_error"] == 0 and len(positive_snapshots) == 2 and
                 stop.get("accepted") == 1 and stop.get("submit_done") == 1 and
                 stop.get("command_index") == 16 and
                 stop.get("call") == {"entered": 1, "done": 1, "ok": 1, "error": 0},
                 "positive live admission and exact original STOP16 completion")
        else:
            need(result["run_call"] == {"entered": 1, "done": 1, "ok": 0, "error": 5} and
                 s["primary_stage"] == 105 and s["primary_error"] == 5 and
                 not stop_attempted and not positive_snapshots,
                 "negative exact first-P105/error5 and native auto-stop preserved")
            result["negative_native_first_P_preserved"] = True
            result["negative_native_auto_stop_observed"] = True
        events = result["ledger"]
        need(len(events) == s["event_count"] and
             [e["sequence"] for e in events] == list(range(1, len(events) + 1)) and
             all(e["continued"] == 1 for e in events), "all events retained/continued")
        births = [e for e in events if e["code"] == 3]
        exits = [e for e in events if e["code"] == 5]
        need(len(births) == len(exits) == 2 and len({e["pid"] for e in births}) == 2 and
             {e["pid"] for e in births} == {e["pid"] for e in exits} and
             all(e["detail"] == 125 for e in exits), "both actual birth/EXIT identities and stop codes125")
        if cli.case == "expected_parent_slot0":
            need([e["sequence"] for e in births] ==
                 [x["birth_event_sequence"] for x in positive_snapshots], "QUERY/ledger original slot binding")
        result["native_terminal_signaled_and_codes_match_contract"] = True
        result["per_held_terminal_values_not_individually_exported"] = True
        result["observed_EXIT_codes"] = [{"pid": e["pid"], "exit_event_code": e["detail"]} for e in exits]
        # Exact C terminal() waited on original held handles and compared codes;
        # their individual raw Wait/GetExitCode values are not exported or added.
        verify_receiver_terminal(result, positive_snapshots)
        result["cleanup_observed_known"] = True
        result["synthetic_case_passed"] = True
    except BaseException as exc:
        record_failure(exc)
        result["verifier_failure"] = summary_error(exc)
        if _PRIMARY:
            result["first_Python_error"] = summary_error(_PRIMARY[0])
    result["storage_DLL_all_buffers_retained_until_host_exit"] = True
    exitcode = 2
    try:
        payload = (json.dumps(result, ensure_ascii=True, indent=2) + "\n").encode("utf-8")
        need(len(payload) <= 196608, "bounded retained JSON output")
        with result_path.open("xb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        receipt = {"path": str(result_path), "size_bytes": len(payload),
                   "sha256": hashlib.sha256(payload).hexdigest()}
        line = json.dumps({"result_ref": receipt,
                           "synthetic_case_passed": result["synthetic_case_passed"],
                           "cleanup_observed_known": result["cleanup_observed_known"],
                           "runtime_qualified": False})
        need(len(line.encode("utf-8")) <= 8192, "bounded stdout JSON")
        print(line, flush=True)
        exitcode = 0 if result["synthetic_case_passed"] else 2
    except BaseException:
        # An incomplete/failed output has nonzero host rc and is never PASS.
        # Root retains stdout/stderr/unknown outcome instead of rerunning a name.
        exitcode = 2
    finally:
        # Dispose ONLY this launcher-created Python host, bypass Python teardown
        # so all original ctypes buffers/DLL remain held until process exit.
        # No Kill/Terminate/OpenProcess/FreeLibrary. On UNKNOWN this exit may
        # trigger debugger-exit fallback; it is NOT observed terminal cleanup.
        os._exit(exitcode)

if __name__ == "__main__":
    main()
