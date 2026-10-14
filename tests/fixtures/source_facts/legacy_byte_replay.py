"""Finite, public, test-only replay of the actual legacy diagnostic CLI.

No product module is imported. No expected stdout is serialized: the primary
oracle is the historical raw-byte digest already present in the public export.
This file is inert on import; execution requires independently reviewed pins.
See README.md before approving a run. Never use this adapter for hidden cases.
"""
from contextlib import ExitStack
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time

MANIFEST_SHA256 = "caa015d7a9b39aeedf3cadb8856b4f3a6529e757fb565e0eb58ac4201855490a"
JOURNAL_SHA256 = "4ad23df65b996bc181684f377f238b8927595052ff50c518bb635aa24c24fd5a"
PROTOCOL_SHA256 = "ae22acd2df04bfedb4070e3709ee1c0cd14cb80c2abb7da3084493977dad94dc"
PUBLIC_DIRECTORY = "rust/diagnostic-core/tests/observed-wire"
ADAPTER = "tests/fixtures/source_facts/legacy_byte_replay.py"
README = "tests/fixtures/source_facts/README.md"
PROTOCOL = "docs/product/SOURCE-FACTS-PROTOCOL.md"
CRATE = "rust/diagnostic-core"
PRODUCTION_SOURCE = {
    CRATE + "/Cargo.toml", CRATE + "/Cargo.lock", CRATE + "/PROTOCOL.md",
    CRATE + "/src/lib.rs", CRATE + "/src/main.rs", CRATE + "/src/catalog.rs",
    CRATE + "/src/engine.rs", CRATE + "/src/model.rs", CRATE + "/src/parse.rs",
    CRATE + "/src/bin/rentgen-source-facts.rs",
    CRATE + "/src/source_facts/mod.rs", CRATE + "/src/source_facts/model.rs",
    CRATE + "/src/source_facts/parse.rs",
}
REQUIRED_SOURCE = PRODUCTION_SOURCE | {ADAPTER, README, PROTOCOL}
UNIQUE_INPUTS, ORIGINS, SHARDS = 156, 249, 17
INPUT_CAP = 65_537  # Includes the public one-over legacy input-limit vector.
STDOUT_CAP, STDERR_CAP = 1_048_576, 65_536
IMAGE_CAP = 32 * 1024 * 1024
CASE_SECONDS, RUN_SECONDS, CLEANUP_SECONDS = 5.0, 900.0, 2.0
STOP_SIGNAL = None


class ReplayError(Exception):
    """Fixed adapter failure code; never forward candidate or OS exception text."""


class StopRequested(ReplayError):
    pass


def require(condition, code):
    # Ordinary checks, never assert: python -O cannot remove a safety gate.
    if not condition:
        raise ReplayError(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def valid_hash(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def fields(value, names, code):
    require(type(value) is dict and set(value) == set(names), code)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def reject_constant(_value):
    raise ReplayError("non_finite_json_number")


def parse_json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=reject_constant)


def same_json(left, right):
    """Exact JSON types, ordered arrays, unordered object keys (True != 1)."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(
            same_json(value, right[key]) for key, value in left.items())
    if type(left) is list:
        return len(left) == len(right) and all(
            same_json(a, b) for a, b in zip(left, right))
    return left == right


def read_bounded(path, limit):
    with open(path, "rb") as source:
        require(stat.S_ISREG(os.fstat(source.fileno()).st_mode), "non_regular_file")
        raw = source.read(limit + 1)
    require(len(raw) <= limit, "file_limit")
    return raw


def absolute_path(value):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "absolute_path_required")
    return path


def expected_json(vector):
    expected = vector["expected"]
    if expected["kind"] == "semantic_json":
        return expected["value"]
    return {"error": expected["code"]}  # Structural oracle only, never byte goldens.


def load_public(root, journal_raw):
    """Validate all 156 raw inputs and all 249 journal links BEFORE any launch."""
    public = root / PUBLIC_DIRECTORY
    manifest_raw = read_bounded(public / "manifest.json", 32_768)
    require(digest(manifest_raw) == MANIFEST_SHA256, "public_manifest_changed")
    manifest = parse_json(manifest_raw)
    require(manifest["counts"]["unique_inputs"] == UNIQUE_INPUTS
            and manifest["counts"]["source_call_occurrences"] == ORIGINS
            and manifest["counts"]["covered_call_occurrences"] == ORIGINS
            and manifest["counts"]["shards"] == SHARDS
            and len(manifest["shards"]) == SHARDS, "public_denominator_changed")
    require(manifest["source_journal_sha256"] == JOURNAL_SHA256
            and digest(journal_raw) == JOURNAL_SHA256, "journal_changed")
    journal = [parse_json(line) for line in journal_raw.splitlines()]
    require(sum(row["event"] == "request_started" for row in journal) == ORIGINS
            and sum(row["event"] == "request_finished" for row in journal) == ORIGINS,
            "journal_denominator_changed")
    require(journal[0]["event"] == "attempt_started"
            and journal[0]["kernel_sha256"] == manifest["source_executable_sha256"]
            and journal[0]["candidate_commit"] == manifest["source_commit"]
            and journal[-1]["event"] == "attempt_finished"
            and journal[-1]["passed"] is True, "historical_attempt_mismatch")
    sources = {"manifest.json": manifest_raw}
    vectors, origins, seen_inputs, seen_calls = [], [], set(), set()
    used_starts, used_finishes = set(), set()
    for number, shard in enumerate(manifest["shards"], 1):
        name = f"wire-vectors-{number:03d}.json"
        require(shard["path"] == name, "unexpected_shard_path")
        raw = read_bounded(public / name, 262_144)
        require(len(raw) == shard["bytes"] and digest(raw) == shard["sha256"],
                "public_shard_changed")
        sources[name] = raw
        payload = parse_json(raw)
        require(payload["format_version"] == 1
                and payload["kind"] == "recorded_wire_regression", "shard_schema")
        shard_origins = 0
        for vector in payload["vectors"]:
            fields(vector, {"id", "input_sha256", "input_bytes", "input_hex",
                            "expected", "recorded_stdout_sha256",
                            "recorded_stderr_sha256", "origins"}, "vector_schema")
            require(vector["id"] == f"wire-{len(vectors) + 1:04d}", "vector_order")
            encoded = vector["input_hex"]
            require(type(encoded) is str and len(encoded) <= 2 * INPUT_CAP
                    and re.fullmatch(r"(?:[0-9a-f]{2})*", encoded) is not None,
                    "input_hex_changed")
            data = bytes.fromhex(encoded)
            require(type(vector["input_bytes"]) is int
                    and len(data) == vector["input_bytes"] <= INPUT_CAP
                    and digest(data) == vector["input_sha256"]
                    and vector["input_sha256"] not in seen_inputs, "input_changed")
            seen_inputs.add(vector["input_sha256"])
            require(valid_hash(vector["recorded_stdout_sha256"])
                    and valid_hash(vector["recorded_stderr_sha256"]), "invalid_byte_oracle")
            expected = vector["expected"]
            require(expected["kind"] in {"semantic_json", "protocol_error"}, "expected_kind")
            names = {"kind", "process_exit_code", "value" if expected["kind"] == "semantic_json" else "code"}
            fields(expected, names, "expected_schema")
            require(type(expected["process_exit_code"]) is int
                    and expected["process_exit_code"] == (0 if expected["kind"] == "semantic_json" else 2),
                    "expected_status")
            require(type(vector["origins"]) is list and vector["origins"], "missing_origins")
            for origin in vector["origins"]:
                base_fields = {"call_index", "journal_tag", "request_started_line",
                               "request_finished_line", "cohort", "fixture_id"}
                require(type(origin) is dict and set(origin) in
                        (base_fields, base_fields | {"variant"}, base_fields | {"policy", "step"}),
                        "origin_schema")
                call = origin["call_index"]
                start, finish = origin["request_started_line"], origin["request_finished_line"]
                require(type(call) is int and 1 <= call <= ORIGINS and call not in seen_calls
                        and type(start) is int and type(finish) is int
                        and 1 <= start < finish <= len(journal)
                        and start not in used_starts and finish not in used_finishes, "origin_identity")
                first, last = journal[start - 1], journal[finish - 1]
                require(first["event"] == "request_started" and first["sequence"] == call
                        and first["tag"] == last["tag"] == origin["journal_tag"]
                        and first["request_bytes"] == len(data)
                        and first["request_sha256"] == vector["input_sha256"]
                        and last["event"] == "request_finished"
                        and last["return_code"] == expected["process_exit_code"]
                        and last["stdout_sha256"] == vector["recorded_stdout_sha256"]
                        and last["stderr_sha256"] == vector["recorded_stderr_sha256"]
                        and same_json(last["result"], expected_json(vector)), "origin_oracle_mismatch")
                seen_calls.add(call); used_starts.add(start); used_finishes.add(finish)
                origins.append({"vector_id": vector["id"], **origin,
                                "input_sha256": vector["input_sha256"],
                                "recorded_stdout_sha256": vector["recorded_stdout_sha256"],
                                "recorded_stderr_sha256": vector["recorded_stderr_sha256"],
                                "recorded_exit_code": expected["process_exit_code"]})
                shard_origins += 1
            vectors.append((vector, data))
        require(len(payload["vectors"]) == shard["unique_vectors"]
                and shard_origins == shard["covered_call_occurrences"], "shard_denominator")
    require(len(vectors) == UNIQUE_INPUTS and len(origins) == ORIGINS
            and seen_calls == set(range(1, ORIGINS + 1)), "incomplete_public_coverage")
    require(sum(v["expected"]["kind"] == "semantic_json" for v, _ in vectors) == 132
            and sum(v["expected"]["kind"] == "protocol_error" for v, _ in vectors) == 24
            and sum(len(v["origins"]) for v, _ in vectors if v["expected"]["kind"] == "semantic_json") == 225
            and sum(len(v["origins"]) for v, _ in vectors if v["expected"]["kind"] == "protocol_error") == 24,
            "kind_denominator_changed")
    return manifest, sources, vectors, sorted(origins, key=lambda row: row["call_index"])


def checked_inputs(args):
    require(sys.platform == "linux" and sys.flags.optimize == 0, "linux_unoptimized_python_required")
    require(hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"), "pidfd_required")
    require(valid_hash(args.pins_sha256) and valid_hash(args.image_sha256), "missing_reviewed_hash")
    root, image = absolute_path(args.root), absolute_path(args.image)
    require(Path(__file__).resolve() == (root / ADAPTER).resolve(), "wrong_adapter")
    pins_raw = read_bounded(absolute_path(args.pins), 65_536)
    require(digest(pins_raw) == args.pins_sha256, "pins_changed")
    pins = parse_json(pins_raw)
    fields(pins, {"schema", "source_commit", "source_sha256", "image", "journal",
                  "public_manifest_sha256", "expected_unique_inputs", "expected_origins"}, "pins_schema")
    require(pins["schema"] == 1 and pins["public_manifest_sha256"] == MANIFEST_SHA256
            and pins["expected_unique_inputs"] == UNIQUE_INPUTS
            and pins["expected_origins"] == ORIGINS, "pins_denominator")
    require(type(pins["source_commit"]) is str
            and re.fullmatch(r"[0-9a-f]{40}", pins["source_commit"]) is not None, "source_commit_required")
    source_hashes = pins["source_sha256"]
    require(type(source_hashes) is dict and set(source_hashes) == REQUIRED_SOURCE, "source_inventory_changed")
    actual_rs = {path.relative_to(root).as_posix() for path in (root / CRATE / "src").rglob("*") if path.is_file()}
    require(actual_rs == {path for path in PRODUCTION_SOURCE if "/src/" in path}, "crate_source_inventory_changed")
    for relative, expected in source_hashes.items():
        require(valid_hash(expected) and digest(read_bounded(root / relative, 4_194_304)) == expected,
                "reviewed_source_changed")
    require(source_hashes[PROTOCOL] == PROTOCOL_SHA256, "frozen_protocol_changed")
    info = pins["image"]
    fields(info, {"role", "path", "sha256", "build_source_commit", "build_command", "compiler_identity"}, "image_pin_schema")
    require(info["role"] == "legacy_diagnostic_cli" and info["path"] == str(image)
            and info["sha256"] == args.image_sha256
            and info["build_source_commit"] == pins["source_commit"], "current_image_pin_mismatch")
    require(type(info["build_command"]) is list and info["build_command"]
            and all(type(part) is str and part for part in info["build_command"])
            and type(info["compiler_identity"]) is str and info["compiler_identity"], "build_provenance_required")
    fields(pins["journal"], {"path", "sha256"}, "journal_pin_schema")
    require(pins["journal"]["sha256"] == JOURNAL_SHA256, "journal_pin_mismatch")
    journal_raw = read_bounded(absolute_path(pins["journal"]["path"]), 2_097_152)
    manifest, sources, vectors, origins = load_public(root, journal_raw)
    return pins, pins_raw, manifest, sources, vectors, origins, journal_raw


def checkpoint(deadline):
    if STOP_SIGNAL is not None:
        raise StopRequested("interrupted")
    if time.monotonic() >= deadline:
        raise ReplayError("deadline_exceeded")


def sealed_image(path, expected, stack, deadline):
    """Test-local exact-byte equivalent of rust_input._executable; no product import."""
    parent = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    stack.callback(os.close, parent)
    for part in path.parts[1:-1]:
        checkpoint(deadline)
        parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        stack.callback(os.close, parent)
    fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    stack.callback(os.close, fd)
    before = os.fstat(fd)
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
            and before.st_uid in (0, os.geteuid()) and not before.st_mode & 0o022
            and before.st_mode & 0o111 and 1 <= before.st_size <= IMAGE_CAP, "invalid_image")
    image = os.memfd_create("legacy-byte-replay", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    stack.callback(os.close, image)
    os.fchmod(image, 0o500)
    hasher, size, prefix = hashlib.sha256(), 0, b""
    while True:
        checkpoint(deadline)
        chunk = os.read(fd, 65_536)
        if not chunk:
            break
        if not prefix:
            prefix = chunk[:4]
        size += len(chunk)
        require(size <= IMAGE_CAP, "image_limit")
        hasher.update(chunk)
        offset = 0
        while offset < len(chunk):
            checkpoint(deadline)
            written = os.write(image, chunk[offset:])
            require(written > 0, "image_copy_stalled")
            offset += written
    after = os.fstat(fd)
    stamp = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
                         info.st_ctime_ns, info.st_mode, info.st_nlink)
    require(stamp(before) == stamp(after) and size == before.st_size
            and hasher.hexdigest() == expected and prefix == b"\x7fELF", "image_changed")
    seals = 0x01 | 0x02 | 0x04 | 0x08  # SEAL, SHRINK, GROW, WRITE.
    fcntl.fcntl(image, getattr(fcntl, "F_ADD_SEALS", 1033), seals)
    require(fcntl.fcntl(image, getattr(fcntl, "F_GET_SEALS", 1034)) & seals == seals,
            "image_not_sealed")
    return image


def stop_owned(child, pidfd):
    """One exact retained child, two-second cleanup; no PID scans or group kills."""
    errors, signalled = [], False
    deadline = time.monotonic() + CLEANUP_SECONDS
    try:
        try:
            live = child.poll() is None
        except BaseException:
            errors.append("owned_poll_failed")
            live = True
        if live:
            try:
                if pidfd is None:
                    # Only pidfd acquisition can lead here. Popen retains its own
                    # unreaped direct child, and this adapter installs no reaper.
                    child.kill()
                else:
                    signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                signalled = True
            except ProcessLookupError:
                pass
            except BaseException:
                errors.append("owned_kill_failed")
        try:
            child.wait(timeout=max(0.001, deadline - time.monotonic()))
        except BaseException:
            errors.append("owned_reap_unconfirmed")
    finally:
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream is not None:
                try:
                    stream.close()
                except BaseException:
                    errors.append("pipe_close_failed")
        if pidfd is not None:
            try:
                os.close(pidfd)
            except BaseException:
                errors.append("pidfd_close_failed")
    return errors, signalled


def replay_one(image_fd, data, run_deadline):
    """Pump all three pipes concurrently; retain raw bytes including a cap witness."""
    child = selector = pidfd = None
    stdout, stderr = bytearray(), bytearray()
    sent = 0
    stdin_closed = stdout_eof = stderr_eof = False
    failure = None
    started = time.monotonic()
    deadline = min(run_deadline, started + CASE_SECONDS)
    cleanup_errors, cleanup_signalled = [], False
    try:
        checkpoint(deadline)
        child = subprocess.Popen([f"/proc/self/fd/{image_fd}"], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 shell=False, close_fds=True, pass_fds=(image_fd,),
                                 env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "RUST_BACKTRACE": "0"})
        # The cleanup finally already owns this Popen before any setup can fail.
        pidfd = os.pidfd_open(child.pid, 0)
        selector = selectors.DefaultSelector()
        for stream, mode, label in ((child.stdin, selectors.EVENT_WRITE, "stdin"),
                                    (child.stdout, selectors.EVENT_READ, "stdout"),
                                    (child.stderr, selectors.EVENT_READ, "stderr")):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, mode, label)
        while selector.get_map() or child.poll() is None:
            checkpoint(deadline)
            for key, _events in selector.select(min(0.1, max(0.0, deadline - time.monotonic()))):
                checkpoint(deadline)
                stream, label = key.fileobj, key.data
                if label == "stdin":
                    try:
                        written = os.write(stream.fileno(), data[sent:sent + 65_536])
                    except BlockingIOError:
                        continue
                    require(written > 0, "stdin_write_stalled")
                    sent += written
                    if sent == len(data):
                        selector.unregister(stream)
                        stream.close()
                        stdin_closed = True
                else:
                    output, cap = (stdout, STDOUT_CAP) if label == "stdout" else (stderr, STDERR_CAP)
                    try:
                        chunk = os.read(stream.fileno(), min(65_536, cap + 1 - len(output)))
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(stream)
                        stream.close()
                        if label == "stdout": stdout_eof = True
                        else: stderr_eof = True
                    else:
                        output.extend(chunk)
                        require(len(output) <= cap, label + "_limit_exceeded")
        checkpoint(deadline)
        require(sent == len(data) and stdin_closed and stdout_eof and stderr_eof,
                "incomplete_transport")
    except BaseException as error:
        failure = str(error) if isinstance(error, ReplayError) else type(error).__name__
    finally:
        # Cleanup precedes all parsing, comparison, evidence writes, and reports.
        if selector is not None:
            try: selector.close()
            except BaseException: cleanup_errors.append("selector_close_failed")
        if child is not None:
            errors, cleanup_signalled = stop_owned(child, pidfd)
            cleanup_errors.extend(errors)
        elif pidfd is not None:
            os.close(pidfd)
    reaped = child is not None and child.returncode is not None
    if cleanup_errors or (child is not None and not reaped):
        failure = "cleanup_unconfirmed"
    status = {
        "launched": child is not None,
        "pid": child.pid if child is not None else None,
        "exit_code": child.returncode if child is not None else None,
        "reaped": reaped, "stdin_closed": stdin_closed,
        "stdin_bytes_written": sent, "stdout_eof": stdout_eof, "stderr_eof": stderr_eof,
        "capture_complete": stdin_closed and stdout_eof and stderr_eof,
        "failure": failure, "cleanup_errors": cleanup_errors,
        "cleanup_signalled": cleanup_signalled,
        "elapsed_seconds_including_cleanup": time.monotonic() - started,
    }
    return data[:sent], bytes(stdout), bytes(stderr), status


def save_bytes(directory, name, raw):
    with open(directory / name, "xb") as target:
        target.write(raw)
        target.flush()
        os.fsync(target.fileno())
    return {"path": name, "bytes": len(raw), "sha256": digest(raw)}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def retain_case(directory, vector, data, received):
    stdin, stdout, stderr, status = received
    try:
        structural_match = same_json(parse_json(stdout), expected_json(vector))
    except (ValueError, UnicodeError, ReplayError, RecursionError):
        structural_match = False
    checks = {
        "raw_stdout_matches_historical_sha256": digest(stdout) == vector["recorded_stdout_sha256"],
        "raw_stderr_matches_historical_sha256": digest(stderr) == vector["recorded_stderr_sha256"],
        "exact_exit_code": status["exit_code"] == vector["expected"]["process_exit_code"],
        "supplementary_structural_json": structural_match,
        "full_stdin_written_and_closed": stdin == data and status["stdin_closed"],
        "both_output_eof": status["stdout_eof"] and status["stderr_eof"],
        "confirmed_reap": status["reaped"],
        "transport_and_cleanup_completed": status["failure"] is None,
    }
    captures = {name: save_bytes(directory, name + ".bin", raw) for name, raw in
                (("request", data), ("stdin", stdin), ("stdout", stdout), ("stderr", stderr))}
    status.update({"vector_id": vector["id"], "origin_count": len(vector["origins"]),
                   "origins": vector["origins"], "checks": checks, "captures": captures,
                   "expected_exit_code": vector["expected"]["process_exit_code"],
                   "recorded_stdout_sha256": vector["recorded_stdout_sha256"],
                   "recorded_stderr_sha256": vector["recorded_stderr_sha256"],
                   "result": "passed" if all(checks.values()) else "failed"})
    receipt = save_bytes(directory, "status.json", json_bytes(status))
    return {"vector_id": vector["id"], "origin_count": len(vector["origins"]),
            "result": status["result"], "status": {**receipt, "path": vector["id"] + "/status.json"},
            "launched": status["launched"], "failure": status["failure"], "checks": checks}


def interrupted(signum, _frame):
    global STOP_SIGNAL
    STOP_SIGNAL = signum  # Never interrupt owned cleanup with a second exception.


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for option in ("root", "pins", "pins-sha256", "image", "image-sha256", "output"):
        parser.add_argument("--" + option, required=True)
    parser.add_argument("--run-reviewed-public-replay", action="store_true", required=True)
    args = parser.parse_args()
    output = absolute_path(args.output)
    # Do not accept an output locator that resolves inside the candidate/public
    # source tree: evidence is a separate, new run directory.
    root = absolute_path(args.root).resolve()
    require(not output.resolve().is_relative_to(root), "output_must_be_outside_checkout")
    pins, pins_raw, manifest, sources, vectors, origins, journal_raw = checked_inputs(args)
    # Exclusive creation forbids silent overwrite or mixing two runs' receipts.
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    old_handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    started, stop_reason = time.monotonic(), None
    rows = [{"vector_id": vector["id"], "origin_count": len(vector["origins"]),
             "result": "unrun", "launched": False} for vector, _data in vectors]
    provenance = {}
    try:
        provenance["pins"] = save_bytes(output, "reviewed-pins.json", pins_raw)
        provenance["journal"] = save_bytes(output, "historical-journal.jsonl", journal_raw)
        provenance["origins"] = save_bytes(output, "journal-origin-map.json", json_bytes(origins))
        public = output / "public-vectors"
        public.mkdir(mode=0o700)
        for name, raw in sources.items():
            item = save_bytes(public, name, raw)
            provenance["public-vectors/" + name] = {**item, "path": "public-vectors/" + name}
        with ExitStack() as stack:
            deadline = started + RUN_SECONDS
            image = sealed_image(absolute_path(args.image), args.image_sha256, stack, deadline)
            for index, (vector, data) in enumerate(vectors):
                checkpoint(deadline)
                directory = output / vector["id"]
                directory.mkdir(mode=0o700)
                received = replay_one(image, data, deadline)
                # Preserve a launched attempt in the denominator even if saving fails.
                rows[index].update({"result": "failed", "launched": received[3]["launched"],
                                    "failure": "receipt_not_retained"})
                rows[index] = retain_case(directory, vector, data, received)
                if rows[index]["failure"] == "cleanup_unconfirmed":
                    raise ReplayError("cleanup_unconfirmed")
                if STOP_SIGNAL is not None:
                    raise StopRequested("interrupted")
    except BaseException as error:
        stop_reason = str(error) if isinstance(error, ReplayError) else type(error).__name__
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
    summary = {
        "schema": 1, "kind": "public_legacy_cli_byte_regression",
        "scope": "Recorded public synthetic regression only; not source accuracy, hidden qualification, or historical ELF identity.",
        "source_commit_declared_by_reviewed_build": pins["source_commit"],
        "current_image_sha256": args.image_sha256,
        "historical_image_sha256": manifest["source_executable_sha256"],
        "reviewed_pins_sha256": args.pins_sha256, "public_manifest_sha256": MANIFEST_SHA256,
        "historical_journal_sha256": JOURNAL_SHA256,
        "expected_unique_inputs": UNIQUE_INPUTS, "expected_historical_origins": ORIGINS,
        "expected_normal_unique_inputs": 132, "expected_error_unique_inputs": 24,
        "expected_normal_origins": 225, "expected_error_origins": 24,
        "attempted_unique_inputs": sum(row["launched"] for row in rows),
        "passed_unique_inputs": sum(row["result"] == "passed" for row in rows),
        "failed_unique_inputs": sum(row["result"] == "failed" for row in rows),
        "unrun_unique_inputs": sum(row["result"] == "unrun" for row in rows),
        "passed_historical_origins": sum(row["origin_count"] for row in rows if row["result"] == "passed"),
        "failed_historical_origins": sum(row["origin_count"] for row in rows if row["result"] == "failed"),
        "unrun_historical_origins": sum(row["origin_count"] for row in rows if row["result"] == "unrun"),
        "bounds": {"case_seconds": CASE_SECONDS, "run_seconds": RUN_SECONDS,
                   "cleanup_seconds": CLEANUP_SECONDS, "stdin_bytes": INPUT_CAP,
                   "stdout_bytes": STDOUT_CAP, "stderr_bytes": STDERR_CAP},
        "stop_reason": stop_reason, "signal_received": STOP_SIGNAL,
        "elapsed_seconds": time.monotonic() - started, "provenance": provenance,
        "vectors": rows,
    }
    passed = stop_reason is None and all(row["result"] == "passed" for row in rows)
    summary["result"] = "passed" if passed else "failed"
    save_bytes(output, "summary.json", json_bytes(summary))
    # No source-bearing payload, stderr, exception text, or paths on the console.
    print("legacy_byte_replay: " + summary["result"] + "; "
          + str(summary["passed_unique_inputs"]) + "/156 unique inputs; "
          + str(summary["passed_historical_origins"]) + "/249 historical origins")
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException as error:
        if isinstance(error, SystemExit):
            raise
        print("legacy_byte_replay: failed before a complete retained summary", file=sys.stderr)
        sys.exit(2)
