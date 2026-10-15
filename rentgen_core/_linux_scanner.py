"""Internal Linux/amd64 fixed scanner process owner, not capture or a generic runner."""
from contextlib import ExitStack
from dataclasses import asdict, dataclass
import math
import os
from pathlib import Path
import platform
import re
import selectors
import struct
import subprocess
import sys
from threading import get_ident
from time import monotonic

from ._posix_source_tree import Directory, _identity
from .errors import CoreError
from .rust_input import _executable

_PROTOCOL = "rentgen-owned-scanner-linux-v1"
_CHUNK = 65536


def _error(code="GRAPH_SCANNER_FAILED"):
    return CoreError(code, "Owned Linux scanner could not complete")


def _static_image(fd):
    """Fixed CGO-disabled amd64 ELF only; the sealed hash binds all loaded code."""
    header = os.pread(fd, 64, 0)
    if len(header) != 64 or header[:7] != b"\x7fELF\x02\x01\x01" or header[7] not in (0, 3):
        raise _error("GRAPH_SCANNER_EXECUTABLE_INVALID")
    kind, machine, version = struct.unpack_from("<HHI", header, 16)
    offset = struct.unpack_from("<Q", header, 32)[0]
    header_size, entry_size, count = struct.unpack_from("<HHH", header, 52)
    if (kind != 2 or machine != 62 or version != 1 or header_size != 64
            or entry_size != 56 or not 1 <= count <= 256 or offset < 64
            or offset + count * entry_size > os.fstat(fd).st_size):
        raise _error("GRAPH_SCANNER_EXECUTABLE_INVALID")
    program = os.pread(fd, count * entry_size, offset)
    if len(program) != count * entry_size or any(
            struct.unpack_from("<I", program, index * entry_size)[0] in (2, 3)
            for index in range(count)):
        raise _error("GRAPH_SCANNER_EXECUTABLE_INVALID")


@dataclass(frozen=True)
class LinuxScannerLimits:
    # Immutable chunks, joined outputs, bounded chunk metadata and one read chunk.
    resident_byte_budget: int
    max_stdout_bytes: int = 128 * 1024**2
    max_coverage_bytes: int = 64 * 1024**2
    max_stderr_bytes: int = 65536
    max_file_bytes: int = 64 * 1024**2
    max_source_bytes: int = 1024**3
    max_files: int = 100_000
    max_entries: int = 200_000
    max_depth: int = 128
    go_memory_target_bytes: int = 512 * 1024**2
    max_transport_reads: int = 500_000
    deadline_seconds: float = 30

    def __post_init__(self):
        maxima = (1024**3, 128 * 1024**2, 64 * 1024**2, 1024**2,
                  64 * 1024**2, 1024**3, 100_000, 200_000, 128, 4 * 1024**3, 1_000_000)
        if any(type(value) is not int or not 1 <= value <= maximum
               for value, maximum in zip(list(asdict(self).values())[:-1], maxima)):
            raise _error("INVALID_QUERY_OPTIONS")
        deadline = self.deadline_seconds
        if type(deadline) not in (int, float) or not math.isfinite(deadline) or not 0.01 <= deadline <= 120:
            raise _error("INVALID_QUERY_OPTIONS")
        if (2 * (self.max_stdout_bytes + self.max_coverage_bytes + self.max_stderr_bytes)
                + 256 * self.max_transport_reads + _CHUNK + 512 > self.resident_byte_budget):
            raise _error("INVALID_QUERY_OPTIONS")


@dataclass(frozen=True)
class LinuxScannerOutput:
    ndjson: bytes
    coverage: bytes
    executable_sha256: str
    protocol: str = _PROTOCOL


def open_linux_scanner(*, executable, executable_sha256, scan_directory, limits,
                       authorize, cancelled=lambda: False):
    """Trusted fixed-image factory; caller retains its private input Directory."""
    return _LinuxScanner(executable, executable_sha256, scan_directory, limits, authorize, cancelled)


class _LinuxScanner:
    def __init__(self, executable, digest, directory, limits, authorize, cancelled):
        if (type(limits) is not LinuxScannerLimits or type(directory) is not Directory
                or not directory._private or not callable(authorize) or not callable(cancelled)
                or type(digest) is not str or re.fullmatch("[0-9a-f]{64}", digest) is None):
            raise _error("INVALID_QUERY_OPTIONS")
        self._executable, self._digest = Path(executable), digest
        if not self._executable.is_absolute() or ".." in self._executable.parts:
            raise _error("INVALID_QUERY_OPTIONS")
        self._directory, self._limits = directory, limits
        self._authorize, self._cancelled = authorize, cancelled
        self._phase, self._owner, self._busy = "new", None, False
        self._process, self._selector = None, None
        self._streams, self._buffers = {}, {}
        self._sizes, self._reads = {}, 0

    def _owner_check(self):
        if self._owner != (os.getpid(), get_ident()):
            raise _error("GRAPH_SCANNER_SESSION_INVALID")

    def _checkpoint(self):
        self._owner_check()
        if monotonic() >= self._deadline:
            raise _error("GRAPH_SCANNER_DEADLINE_EXCEEDED")
        if self._cancelled():
            raise _error("GRAPH_SCANNER_CANCELLED")
        self._authorize()
        self._directory.verify()
        if monotonic() >= self._deadline:
            raise _error("GRAPH_SCANNER_DEADLINE_EXCEEDED")

    def _register(self, stream, label):
        self._streams[label] = stream
        os.set_blocking(stream.fileno(), False)
        self._selector.register(stream, selectors.EVENT_READ, label)

    def _pipe(self, descriptors, label):
        read_fd, write_fd = os.pipe()
        descriptors.callback(os.close, write_fd)
        try:
            self._streams[label] = os.fdopen(read_fd, "rb", buffering=0)
        except BaseException:
            os.close(read_fd)
            raise
        return read_fd, write_fd

    def __enter__(self):
        if self._phase != "new":
            raise _error("GRAPH_SCANNER_SESSION_INVALID")
        self._owner, self._phase, self._busy = (os.getpid(), get_ident()), "entering", True
        self._deadline = monotonic() + self._limits.deadline_seconds
        try:
            # Refuse before executable/input IO on every unsupported runtime.
            if sys.platform != "linux" or platform.machine() not in {"x86_64", "amd64"}:
                raise _error("CAPTURE_PLATFORM_UNSUPPORTED")
            self._checkpoint()
            self._selector = selectors.DefaultSelector()
            self._buffers = {name: [] for name in ("stdout", "stderr", "coverage", "hello")}
            self._sizes = dict.fromkeys(self._buffers, 0)
            with ExitStack() as descriptors:
                try:
                    image = _executable(self._executable, self._digest, descriptors)
                    _static_image(image)
                except (CoreError, OSError) as exc:
                    raise _error("GRAPH_SCANNER_EXECUTABLE_INVALID") from exc
                # dup() shares the directory cursor. A second scanner must not
                # observe EOF left by the first or disturb the caller's cursor.
                root = os.open(".", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                               dir_fd=self._directory._fd)
                descriptors.callback(os.close, root)
                if _identity(os.fstat(root)) != _identity(os.fstat(self._directory._fd)):
                    raise _error("GRAPH_SCANNER_SESSION_INVALID")
                coverage_read, coverage_write = self._pipe(descriptors, "coverage")
                hello_read, hello_write = self._pipe(descriptors, "hello")
                inherited = (image, root, coverage_write, hello_write)
                if any(fd <= 2 for fd in (*inherited, coverage_read, hello_read)) or len(set(inherited)) != 4:
                    raise _error("GRAPH_SCANNER_SESSION_INVALID")
                self._checkpoint()
                remaining = int((self._deadline - monotonic()) * 1000)
                if remaining < 1:
                    raise _error("GRAPH_SCANNER_DEADLINE_EXCEEDED")
                args = [os.getpid(), root, coverage_write, hello_write, image, remaining,
                        self._limits.max_file_bytes, self._limits.max_source_bytes,
                        self._limits.max_files, self._limits.max_entries, self._limits.max_depth,
                        self._limits.max_stdout_bytes, self._limits.max_coverage_bytes,
                        self._limits.go_memory_target_bytes]
                self._process = subprocess.Popen(
                    [f"/proc/self/fd/{image}", "--owned-linux-v1", *map(str, args)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    bufsize=0, shell=False, close_fds=True, pass_fds=inherited,
                    env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
                )
            self._register(self._process.stdout, "stdout")
            self._register(self._process.stderr, "stderr")
            self._register(self._streams["coverage"], "coverage")
            self._register(self._streams["hello"], "hello")
            self._pump(hello=True)
            expected = f"{_PROTOCOL} {self._process.pid} {os.getpid()}\n".encode("ascii")
            if b"".join(self._buffers["hello"]) != expected:
                raise _error("GRAPH_SCANNER_PROTOCOL_INVALID")
            self._checkpoint()
            self._phase = "active"
            return self
        except BaseException:
            self._cleanup(preserve=True)
            raise
        finally:
            self._busy = False

    def _pump(self, *, hello=False):
        bounds = {"stdout": self._limits.max_stdout_bytes, "coverage": self._limits.max_coverage_bytes,
                  "stderr": self._limits.max_stderr_bytes, "hello": 512}
        raw = None
        try:
            while self._selector.get_map():
                self._checkpoint()
                for key, _ in self._selector.select(min(0.05, max(0, self._deadline - monotonic()))):
                    label = key.data
                    try:
                        raw = os.read(key.fileobj.fileno(), min(_CHUNK, bounds[label] - self._sizes[label] + 1))
                    except BlockingIOError:
                        continue
                    if not raw:
                        self._selector.unregister(key.fileobj)
                        key.fileobj.close()
                        if label == "hello" and hello:
                            return
                        continue
                    if self._sizes[label] + len(raw) > bounds[label]:
                        raise _error("GRAPH_SCANNER_OUTPUT_LIMIT_EXCEEDED")
                    if hello and label in {"stdout", "coverage"}:
                        raise _error("GRAPH_SCANNER_PROTOCOL_INVALID")
                    self._reads += 1
                    if self._reads > self._limits.max_transport_reads:
                        raise _error("GRAPH_SCANNER_OUTPUT_LIMIT_EXCEEDED")
                    self._buffers[label].append(raw)
                    self._sizes[label] += len(raw)
                    raw = None
                if self._process.poll() is not None and hello and "hello" not in [key.data for key in self._selector.get_map().values()]:
                    return
            if hello:
                raise _error("GRAPH_SCANNER_PROTOCOL_INVALID")
        finally:
            raw = None

    def scan(self):
        self._owner_check()
        if self._phase != "active" or self._busy:
            raise _error("GRAPH_SCANNER_SESSION_INVALID")
        self._busy = True
        result = None
        try:
            self._checkpoint()
            self._process.stdin.write(b"G")
            self._process.stdin.close()
            self._pump()
            while True:
                self._checkpoint()
                try:
                    status = self._process.wait(timeout=min(0.05, max(0.001, self._deadline-monotonic())))
                    break
                except subprocess.TimeoutExpired:
                    continue
            if status != 0:
                raise _error()
            self._checkpoint()
            result = LinuxScannerOutput(b"".join(self._buffers["stdout"]), b"".join(self._buffers["coverage"]), self._digest)
            self._checkpoint()
            self._buffers.clear(); self._sizes.clear()
            self._phase = "complete"
            return result
        except BaseException:
            result = None
            self._cleanup(preserve=True)
            raise
        finally:
            self._busy = False

    def _cleanup(self, *, preserve):
        failure = None
        process = self._process
        try:
            if process is not None:
                if process.poll() is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    except BaseException:
                        failure = sys.exc_info()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired as exc:
                    raise _error("GRAPH_SCANNER_CLEANUP_UNCONFIRMED") from exc
        except BaseException:
            failure = failure or sys.exc_info()
        finally:
            if self._selector is not None:
                try:
                    self._selector.close()
                except BaseException:
                    failure = failure or sys.exc_info()
            streams = list(self._streams.values())
            if process is not None:
                streams += [process.stdin, process.stdout, process.stderr]
            for stream in streams:
                if stream is not None:
                    try:
                        stream.close()
                    except BaseException:
                        failure = failure or sys.exc_info()
            self._streams.clear(); self._buffers.clear(); self._sizes.clear()
            self._directory = self._authorize = self._cancelled = self._selector = None
            self._phase = "closed"
        if failure is not None and not preserve:
            raise failure[1].with_traceback(failure[2])

    def __exit__(self, kind, value, traceback):
        self._owner_check()
        if self._busy or self._phase not in {"active", "complete", "closed"}:
            raise _error("GRAPH_SCANNER_SESSION_INVALID")
        if self._phase == "closed":
            return False
        self._busy = True
        try:
            if kind is None:
                try:
                    self._checkpoint()
                except BaseException:
                    self._cleanup(preserve=True)
                    raise
            self._cleanup(preserve=kind is not None)
            if kind is None and monotonic() >= self._deadline:
                raise _error("GRAPH_SCANNER_DEADLINE_EXCEEDED")
            return False
        finally:
            self._busy = False
