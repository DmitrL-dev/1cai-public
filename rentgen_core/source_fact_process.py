"""Linux-only owned one-shot transport for the two fixed source-fact helpers.

This pins the main executable image, not the OS/runtime or arbitrary programs.
Only reviewed helpers are supported; it is not a general process sandbox.
"""
from contextlib import ExitStack
import json
import os
import selectors
import struct
import subprocess
import sys
import time

from .errors import CoreError
from .rust_input import _executable, _poll_wait_timeout

_ROLES = {
    "scanner": ("source_fact_scan_v1", 1_500_000, 10),
    "kernel": ("submitted_source_facts_v1", 65_536, 5),
}
_MESSAGE = "Submitted source facts could not be completed"


def failure(code):
    return CoreError("SOURCE_FACTS_" + code, _MESSAGE)


def checkpoint(authorize, cancelled, deadline):
    authorize()
    if cancelled is not None and cancelled():
        raise failure("CANCELLED")
    if time.monotonic() >= deadline:
        raise failure("TIMEOUT")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise failure("HANDSHAKE_INVALID")
        result[key] = value
    return result


def _frame_payload(buffer, limit):
    if len(buffer) < 4:
        return None
    size = struct.unpack("<I", buffer[:4])[0]
    if not 1 <= size <= limit:
        raise failure("OUTPUT_LIMIT")
    if len(buffer) > size + 4:
        raise failure("PROTOCOL_INVALID")
    return bytes(buffer[4:]) if len(buffer) == size + 4 else None


def _cleanup(process, selector, *, success, stdout_bytes, stderr_bytes):
    """Always reap our Popen child. A sent signal alone is not cleanup proof."""
    error = None
    try:
        if process is not None:
            if not success and process.poll() is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                except OSError:
                    error = failure("CLEANUP_UNCONFIRMED")
            try:
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                error = failure("CLEANUP_UNCONFIRMED")
            # Drain at most one bounded output allowance per pipe after failure.
            # No drained byte is decoded, logged or returned.
            if not success:
                for stream in (process.stdout, process.stderr):
                    if stream is None or stream.closed:
                        continue
                    try:
                        os.set_blocking(stream.fileno(), False)
                    except OSError:
                        error = failure("CLEANUP_UNCONFIRMED")
                        continue
                    left = max(0, (66_056 - stdout_bytes) if stream is process.stdout
                               else (65_536 - stderr_bytes))
                    while left:
                        try:
                            data = os.read(stream.fileno(), min(left, 8192))
                        except (BlockingIOError, OSError):
                            break
                        if not data:
                            break
                        left -= len(data)
    finally:
        if selector is not None:
            try:
                selector.close()
            except OSError:
                error = failure("CLEANUP_UNCONFIRMED")
        if process is not None:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        error = failure("CLEANUP_UNCONFIRMED")
    if error is not None:
        raise error


def run_owned_helper(executable, expected_sha256, *, role, request, authorize,
                     cancelled=None, deadline):
    """Return one raw response only after complete exchange, EOF and reap.

    Schema/receipt validation of that response belongs to the fixed-role caller.
    Source bytes are never sent before the exact parent-death hello is admitted.
    """
    checkpoint(authorize, cancelled, deadline)
    if sys.platform != "linux":
        raise failure("CAPABILITY_UNAVAILABLE")
    if role not in _ROLES or type(request) is not bytes:
        raise failure("INVALID_ARGUMENT")
    protocol, request_limit, seconds = _ROLES[role]
    if not 1 <= len(request) <= request_limit:
        raise failure("READ_LIMIT")
    process = selector = None
    success = False
    stdout_bytes = stderr_bytes = 0
    try:
        with ExitStack() as images:
            try:
                image = _executable(executable, expected_sha256, images,
                                    checkpoint=lambda: checkpoint(authorize, cancelled, deadline))
            except CoreError as error:
                if not error.code.startswith("INPUT_CORE_"):
                    raise
                raise failure("EXECUTABLE_INVALID") from None
            except (OSError, ValueError):
                raise failure("EXECUTABLE_INVALID") from None
            checkpoint(authorize, cancelled, deadline)
            launched = time.monotonic()
            try:
                process = subprocess.Popen(
                    [f"/proc/self/fd/{image}", "--parent-pid", str(os.getpid())],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, shell=False, close_fds=True,
                    pass_fds=(image,),
                    env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                         "RUST_BACKTRACE": "0", "GOMAXPROCS": "1"},
                )
            except OSError:
                raise failure("LAUNCH_FAILED") from None
        selector = selectors.DefaultSelector()
        for stream, label in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
        os.set_blocking(process.stdin.fileno(), False)
        wire = struct.pack("<I", len(request)) + request
        output = bytearray()
        sent = 0
        phase = "hello"
        closed_input = False
        eof = set()
        response = None
        while True:
            iteration_started = time.monotonic()
            stop = min(deadline, launched + (min(5, seconds) if phase == "hello" else seconds))
            checkpoint(authorize, cancelled, stop)
            payload = _frame_payload(output, 512 if phase == "hello" else 65_536)
            if phase == "hello" and payload is not None:
                try:
                    if not payload.startswith(b"{") or not payload.endswith(b"}"):
                        raise ValueError()
                    hello = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique)
                except (ValueError, UnicodeError, RecursionError):
                    raise failure("HANDSHAKE_INVALID") from None
                if hello != {"protocol": protocol, "kind": "hello", "ownership": "linux_parent_death_v1"}:
                    raise failure("HANDSHAKE_INVALID")
                checkpoint(authorize, cancelled, stop)
                output.clear()
                phase = "exchange"
                selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            elif phase == "exchange" and payload is not None:
                if sent != len(wire) or not closed_input:
                    raise failure("PROTOCOL_INVALID")
                response = payload
            if "stdout" in eof and phase == "hello":
                raise failure("CHILD_FAILED")
            if eof == {"stdout", "stderr"} and process.poll() is not None:
                if not closed_input or response is None or process.returncode != 0:
                    raise failure("CHILD_FAILED")
                process.wait(timeout=0.01)
                checkpoint(authorize, cancelled, min(deadline, launched + seconds))
                success = True
                return response
            for key, _ in selector.select(_poll_wait_timeout(stop, iteration_started)):
                if key.data == "stdin":
                    try:
                        count = os.write(key.fileobj.fileno(), wire[sent:sent + 65_536])
                    except BlockingIOError:
                        continue
                    sent += count
                    if sent == len(wire):
                        selector.unregister(key.fileobj)
                        process.stdin.close()
                        closed_input = True
                else:
                    try:
                        left = ((65_536 - stderr_bytes) if key.data == "stderr" else
                                ((516 if phase == "hello" else 65_540) - len(output)))
                        # One bounded detection byte distinguishes EOF at the
                        # exact limit from excess output. Cleanup never gets a
                        # fresh allowance for bytes already discarded here.
                        data = os.read(key.fileobj.fileno(), min(8192, max(1, left + 1)))
                    except BlockingIOError:
                        continue
                    if not data:
                        eof.add(key.data)
                        selector.unregister(key.fileobj)
                    elif key.data == "stderr":
                        stderr_bytes += len(data)
                        if stderr_bytes > 65_536:
                            raise failure("OUTPUT_LIMIT")
                    else:
                        stdout_bytes += len(data)
                        output.extend(data)
                        if len(output) > (516 if phase == "hello" else 65_540):
                            raise failure("OUTPUT_LIMIT")
    except OSError:
        raise failure("CHILD_FAILED") from None
    finally:
        _cleanup(process, selector, success=success,
                 stdout_bytes=stdout_bytes, stderr_bytes=stderr_bytes)
