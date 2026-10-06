"""Experimental Linux wrapper for the owned Rust submitted-byte session.

This is not a general process sandbox, snapshot reader, or live-source adapter.
No Rust message or stderr is forwarded without fixed-schema checks and current
project authorization. One context owns one child and confirms its termination.
"""
import base64
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import stat
import struct
import subprocess
import sys
import time

from .errors import CoreError

MAX_FRAME = 65536
MAX_TRANSPORT = 96 * 1024**2
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_CODES = frozenset({
    "INVALID_REQUEST", "INVALID_SEQUENCE", "INVALID_STATE", "INVALID_PATH",
    "INPUT_CHANGED", "HASH_MISMATCH", "LIMIT_EXCEEDED", "INVALID_ARCHIVE",
    "UNSUPPORTED_ARCHIVE", "IO_ERROR", "DEADLINE_EXCEEDED", "INTERNAL_ERROR",
})


def _poll_wait_timeout(deadline, iteration_started):
    """Budget checkpoint/work time and reserve half the 100 ms poll interval.

    A 50 ms iteration target leaves scheduling headroom; it is not a hard
    real-time guarantee for an arbitrarily stalled callback or operating system.
    """
    return max(0, min(deadline, iteration_started + 0.05) - time.monotonic())


def _error(code="INPUT_CORE_PROTOCOL_INVALID"):
    return CoreError(code, "Experimental input core could not complete a verified read")


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise _error()
        value[key] = item
    return value


def _hash(value):
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise _error("INPUT_CORE_INVALID_ARGUMENT")
    return value


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise _error()
    return value


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise _error()
    return value


def _executable(path, expected_hash, stack, *, checkpoint=None):
    """Exec a sealed owned image of the verified bytes, never a mutable locator."""
    import fcntl

    _hash(expected_hash)
    if checkpoint is not None:
        checkpoint()
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or len(path.parts) > 128:
        raise _error("INPUT_CORE_INVALID_ARGUMENT")
    parent = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    stack.callback(os.close, parent)
    for part in path.parts[1:-1]:
        if checkpoint is not None:
            checkpoint()
        parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        stack.callback(os.close, parent)
    fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    stack.callback(os.close, fd)
    before = os.fstat(fd)
    if (
        not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
        or before.st_uid not in (0, os.geteuid()) or before.st_mode & 0o022
        or not before.st_mode & 0o111 or not 1 <= before.st_size <= 32 * 1024**2
    ):
        raise _error("INPUT_CORE_EXECUTABLE_INVALID")
    image = os.memfd_create("rentgen-input-core", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    stack.callback(os.close, image)
    os.fchmod(image, 0o500)
    digest, size = hashlib.sha256(), 0
    while chunk := os.read(fd, 65536):
        if checkpoint is not None:
            checkpoint()
        size += len(chunk)
        if size > 32 * 1024**2:
            raise _error("INPUT_CORE_EXECUTABLE_INVALID")
        digest.update(chunk)
        offset = 0
        while offset < len(chunk):
            offset += os.write(image, chunk[offset:])
    after = os.fstat(fd)
    if checkpoint is not None:
        checkpoint()
    stamp = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_mode, info.st_nlink)
    if stamp(before) != stamp(after) or size != before.st_size or digest.hexdigest() != expected_hash:
        raise _error("INPUT_CORE_EXECUTABLE_INVALID")
    # Linux UAPI constants: some supported Python builds omit these names.
    add_seals = getattr(fcntl, "F_ADD_SEALS", 1033)
    get_seals = getattr(fcntl, "F_GET_SEALS", 1034)
    seals = 0x01 | 0x02 | 0x04 | 0x08  # SEAL, SHRINK, GROW, WRITE
    fcntl.fcntl(image, add_seals, seals)
    if fcntl.fcntl(image, get_seals) & seals != seals:
        raise _error("INPUT_CORE_EXECUTABLE_INVALID")
    return image


class RustInputSession:
    """One sequential framed connection; all returned archive bytes are owned."""

    def __init__(self, executable, executable_sha256, *, authorize, checkpoint=None):
        self.executable = executable
        self.executable_sha256 = executable_sha256
        self.authorize = authorize
        self.checkpoint = checkpoint
        self.process = None
        self.selector = None
        self.sequence = 0
        self.buffer = bytearray()
        self.transport = self.stderr_bytes = 0
        self.deadline = 0.0
        self.opened = False

    def __enter__(self):
        self.authorize()
        if sys.platform != "linux":
            raise _error("CAPABILITY_UNAVAILABLE")
        self.deadline = time.monotonic() + 60
        try:
            with ExitStack() as files:
                if self.checkpoint is None:
                    fd = _executable(self.executable, self.executable_sha256, files)
                else:
                    fd = _executable(self.executable, self.executable_sha256, files,
                                     checkpoint=self.checkpoint)
                self.authorize()
                self.process = subprocess.Popen(
                    [f"/proc/self/fd/{fd}", "--parent-pid", str(os.getpid())],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    shell=False, close_fds=True, pass_fds=(fd,),
                    env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "RUST_BACKTRACE": "0"},
                )
            self.selector = selectors.DefaultSelector()
            for stream, label in ((self.process.stdout, "stdout"), (self.process.stderr, "stderr")):
                os.set_blocking(stream.fileno(), False)
                self.selector.register(stream, selectors.EVENT_READ, label)
            os.set_blocking(self.process.stdin.fileno(), False)
            hello = self._exchange(b"", min(self.deadline, time.monotonic() + 5))
            if type(hello) is not dict or type(hello.get("protocol")) is not int or hello != {"protocol": 1, "kind": "hello", "implementation": "rentgen-input-core", "contract": "submitted-zip-v1"}:
                raise _error()
            self.authorize()
            return self
        except BaseException:
            self._terminate()
            self.authorize()
            raise

    def _exchange(self, output, deadline):
        """Pump stdin/stdout/stderr together, bounded before frame allocation."""
        sent = 0
        self.transport += len(output)
        if self.transport > MAX_TRANSPORT:
            raise _error("INPUT_CORE_OUTPUT_LIMIT")
        if output:
            self.selector.register(self.process.stdin, selectors.EVENT_WRITE, "stdin")
        try:
            while True:
                iteration_started = time.monotonic()
                if self.checkpoint is not None:
                    self.checkpoint()
                if len(self.buffer) >= 4:
                    size = struct.unpack("<I", self.buffer[:4])[0]
                    if not 1 <= size <= MAX_FRAME:
                        raise _error()
                    if len(self.buffer) >= size + 4:
                        if sent != len(output) or len(self.buffer) != size + 4:
                            raise _error()
                        raw = bytes(self.buffer[4:]); self.buffer.clear()
                        try:
                            return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=lambda _: (_ for _ in ()).throw(_error()))
                        except (ValueError, UnicodeError, RecursionError) as exc:
                            raise _error() from exc
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise _error("INPUT_CORE_TIMEOUT")
                wait = (_poll_wait_timeout(deadline, iteration_started)
                        if self.checkpoint is not None else min(remaining, 0.1))
                for key, _ in self.selector.select(wait):
                    if key.data == "stdin":
                        try:
                            count = os.write(key.fileobj.fileno(), output[sent:])
                        except BlockingIOError:
                            continue
                        sent += count
                        if sent == len(output):
                            self.selector.unregister(key.fileobj)
                    else:
                        try:
                            data = os.read(key.fileobj.fileno(), 65536)
                        except BlockingIOError:
                            continue
                        if not data:
                            self.selector.unregister(key.fileobj)
                            if key.data == "stdout":
                                raise _error("INPUT_CORE_FAILED")
                            continue
                        self.transport += len(data)
                        if self.transport > MAX_TRANSPORT:
                            raise _error("INPUT_CORE_OUTPUT_LIMIT")
                        if key.data == "stderr":
                            self.stderr_bytes += len(data)
                            if self.stderr_bytes > 65536:
                                raise _error("INPUT_CORE_OUTPUT_LIMIT")
                        else:
                            self.buffer.extend(data)
                            if len(self.buffer) > MAX_FRAME + 4:
                                raise _error()
        except (OSError, ValueError) as exc:
            raise _error("INPUT_CORE_FAILED") from exc
        finally:
            try:
                self.selector.unregister(self.process.stdin)
            except KeyError:
                pass

    def request(self, operation, **fields):
        self.authorize()
        try:
            self.sequence += 1
            raw = json.dumps({"protocol": 1, "seq": self.sequence, "op": operation, **fields}, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
            if len(raw) > MAX_FRAME:
                raise _error("INPUT_CORE_INVALID_ARGUMENT")
            result = self._exchange(struct.pack("<I", len(raw)) + raw, min(self.deadline, time.monotonic() + (10 if operation == "open_import" else 5)))
            if type(result) is not dict or result.get("protocol") != 1 or type(result.get("protocol")) is not int or result.get("seq") != self.sequence or type(result.get("seq")) is not int:
                raise _error()
            if set(result) == {"protocol", "seq", "error"}:
                error = _fields(result["error"], ("code", "message"))
                if error["code"] not in _CODES or type(error["message"]) is not str:
                    raise _error()
                raise _error("IMPORT_" + error["code"])
            _fields(result, ("protocol", "seq", "result"))
            if type(result["result"]) is not dict:
                raise _error()
            return result["result"]
        finally:
            self.authorize()

    def open_import(self, path, expected_sha256):
        _hash(expected_sha256)
        if self.opened:
            raise _error()
        result = self.request("open_import", path=str(path), expected_sha256=expected_sha256)
        _fields(result, ("input_sha256", "entries_count", "files_count", "total_bytes"))
        if result["input_sha256"] != expected_sha256:
            raise _error()
        _integer(result["entries_count"], 0, 4096)
        _integer(result["files_count"], 0, result["entries_count"])
        _integer(result["total_bytes"], 0, 32 * 1024**2)
        self.opened = True
        return result

    def entries(self, manifest):
        from .source_paths import validate_file_paths
        entries, offset, total = [], 0, 0
        while True:
            page = self.request("entries", offset=offset, limit=32)
            _fields(page, ("entries", "next_offset"))
            if type(page["entries"]) is not list or len(page["entries"]) > 32:
                raise _error()
            for entry in page["entries"]:
                _fields(entry, ("entry_id", "path", "size_bytes", "raw_sha256"))
                if _integer(entry["entry_id"], 0, 4095) != len(entries) or type(entry["path"]) is not str or len(entry["path"].encode("utf-8")) > 1024:
                    raise _error()
                total += _integer(entry["size_bytes"], 0, 4 * 1024**2)
                _hash(entry["raw_sha256"])
                entries.append(entry)
                if len(entries) > manifest["files_count"] or total > manifest["total_bytes"]:
                    raise _error()
            if page["next_offset"] is None:
                break
            offset = _integer(page["next_offset"], offset + 1, manifest["files_count"])
            if offset != len(entries):
                raise _error()
        if len(entries) != manifest["files_count"] or total != manifest["total_bytes"]:
            raise _error()
        validate_file_paths(entry["path"] for entry in entries)
        return tuple(entries)

    def read_entry(self, entry):
        chunks, offset = [], 0
        while True:
            result = self.request("read_entry", entry_id=entry["entry_id"], offset=offset, limit=32768)
            _fields(result, ("entry_id", "offset", "total_bytes", "raw_sha256", "data_base64", "next_offset"))
            if any(type(result[key]) is not int for key in ("entry_id", "offset", "total_bytes")) or result["entry_id"] != entry["entry_id"] or result["offset"] != offset or result["total_bytes"] != entry["size_bytes"] or result["raw_sha256"] != entry["raw_sha256"] or type(result["data_base64"]) is not str:
                raise _error()
            try:
                chunk = base64.b64decode(result["data_base64"], validate=True)
            except ValueError as exc:
                raise _error() from exc
            if len(chunk) > 32768 or base64.b64encode(chunk).decode("ascii") != result["data_base64"]:
                raise _error()
            offset += len(chunk); chunks.append(chunk)
            if offset > entry["size_bytes"]:
                raise _error()
            if result["next_offset"] is None:
                break
            if not chunk or type(result["next_offset"]) is not int or result["next_offset"] != offset:
                raise _error()
        raw = b"".join(chunks)
        if len(raw) != entry["size_bytes"] or hashlib.sha256(raw).hexdigest() != entry["raw_sha256"]:
            raise _error()
        return raw

    def _drain_exit(self):
        """Require EOF after the close ACK; late output cannot bypass framing."""
        deadline = min(self.deadline, time.monotonic() + 2)
        while self.selector.get_map():
            iteration_started = time.monotonic()
            if self.checkpoint is not None:
                self.checkpoint()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _error("INPUT_CORE_CLEANUP_UNCONFIRMED")
            wait = (_poll_wait_timeout(deadline, iteration_started)
                    if self.checkpoint is not None else min(remaining, 0.1))
            for key, _ in self.selector.select(wait):
                try:
                    data = os.read(key.fileobj.fileno(), 65536)
                except BlockingIOError:
                    continue
                if not data:
                    self.selector.unregister(key.fileobj)
                elif key.data == "stdout":
                    raise _error()
                else:
                    self.stderr_bytes += len(data)
                    self.transport += len(data)
                    if self.stderr_bytes > 65536 or self.transport > MAX_TRANSPORT:
                        raise _error("INPUT_CORE_OUTPUT_LIMIT")
        try:
            if self.checkpoint is None:
                status = self.process.wait(timeout=max(0.001, deadline - time.monotonic()))
            else:
                while True:
                    iteration_started = time.monotonic()
                    self.checkpoint()
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise _error("INPUT_CORE_CLEANUP_UNCONFIRMED")
                    try:
                        status = self.process.wait(timeout=_poll_wait_timeout(deadline, iteration_started))
                        break
                    except subprocess.TimeoutExpired:
                        pass
        except subprocess.TimeoutExpired as error:
            raise _error("INPUT_CORE_CLEANUP_UNCONFIRMED") from error
        if status != 0:
            raise _error("INPUT_CORE_FAILED")

    def _terminate(self):
        process = self.process
        try:
            if process is not None:
                if process.poll() is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired as exc:
                    raise _error("INPUT_CORE_CLEANUP_UNCONFIRMED") from exc
        finally:
            if self.selector is not None:
                self.selector.close()
            if process is not None:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type is None:
                closed = self.request("close")
                if set(closed) != {"closed"} or closed["closed"] is not True:
                    raise _error()
                self._drain_exit()
        finally:
            self._terminate()
            self.authorize()
