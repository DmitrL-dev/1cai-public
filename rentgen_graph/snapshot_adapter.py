"""Real local Go scanner adapter over retained, hash-verified captured bytes."""
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import threading
import time

from rentgen_core.errors import CoreError
from rentgen_core.graph import CapturedTree, GraphBuildReceipt
from rentgen_core.manifests import canonical_bytes

from .build_store import BuildInputs, build_snapshot_graph, _validate_callgraph_record
from .identity import SCHEMA_VERSION, IDENTITY_VERSION, source_key
from .store import RentgenStore

ADAPTER_VERSION = "rentgen-captured-go-v1"
BUILDER_VERSION = "rentgen-schema2-snapshot-v1"
SEMANTIC_SCOPE = "bounded_static_calls; preprocessing and dynamic types unresolved"
BSL_SUFFIXES = {".bsl", ".os", ".bsp"}


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _mismatch(message="Scanner output does not match captured inputs"):
    return CoreError("GRAPH_INPUT_MISMATCH", message)


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise _mismatch("Duplicate scanner JSON key")
            result[key] = value
        return result

    try:
        return json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, UnicodeError) as exc:
        raise _mismatch("Invalid scanner JSON") from exc


def _run_bounded(args, *, timeout, max_output_bytes, coverage_path=None):
    """Drain both pipes concurrently with hard retained-memory/output limits."""
    output = [bytearray(), bytearray()]
    exceeded = threading.Event()
    process = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    def drain(pipe, index, limit):
        try:
            while chunk := pipe.read(65536):
                if len(output[index]) + len(chunk) > limit:
                    exceeded.set()
                    process.kill()
                    break
                output[index].extend(chunk)
        finally:
            pipe.close()

    threads = [
        threading.Thread(target=drain, args=(process.stdout, 0, max_output_bytes)),
        threading.Thread(
            target=drain, args=(process.stderr, 1, min(max_output_bytes, 1024 * 1024))
        ),
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            if time.monotonic() >= deadline:
                raise CoreError("GRAPH_BUILD_FAILED", "Scanner timed out")
            if (
                coverage_path is not None
                and coverage_path.exists()
                and coverage_path.stat().st_size > max_output_bytes
            ):
                exceeded.set()
                break
            time.sleep(0.01)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        for thread in threads:
            thread.join()
    if exceeded.is_set():
        raise CoreError("GRAPH_BUILD_FAILED", "Scanner output limit exceeded")
    if process.returncode:
        raise CoreError("GRAPH_BUILD_FAILED", "Strict scanner failed")
    return bytes(output[0])


def _validate_outputs(ndjson: bytes, report: bytes, expected: dict, texts: dict):
    """Exact raw coverage, declaration counts and physical source span bounds."""
    document = _json(report)
    if (
        not isinstance(document, dict)
        or set(document) != {"format_version", "files"}
        or type(document["format_version"]) is not int
        or document["format_version"] != 1
        or not isinstance(document["files"], list)
    ):
        raise _mismatch()
    coverage = {}
    for item in document["files"]:
        if not isinstance(item, dict) or set(item) != {
            "source_path",
            "raw_sha256",
            "status",
            "routine_count",
        }:
            raise _mismatch()
        path = item["source_path"]
        if not isinstance(path, str) or path in coverage or path not in expected:
            raise _mismatch()
        if (
            item["raw_sha256"] != expected[path].raw_sha256
            or item["status"] != "parsed"
            or type(item["routine_count"]) is not int
            or item["routine_count"] < 0
        ):
            raise _mismatch()
        coverage[path] = item
    if set(coverage) != set(expected):
        raise _mismatch()
    counts = dict.fromkeys(expected, 0)
    records = []
    for line in ndjson.splitlines():
        if not line:
            raise _mismatch()
        record = _json(line)
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("source_path"), str)
            or record["source_path"] not in expected
        ):
            raise _mismatch()
        path = record["source_path"]
        lines = texts[path].split("\n")
        try:
            _validate_callgraph_record(
                record, Path("callgraph.ndjson"), len(records) + 1
            )
        except (ValueError, TypeError) as exc:
            raise _mismatch("Invalid scanner declaration") from exc
        start, end = record.get("line"), record.get("end_line")
        if (
            type(start) is not int
            or type(end) is not int
            or not 1 <= start <= end <= len(lines)
            or not record.get("name")
        ):
            raise _mismatch("Declaration span is outside captured source")
        if "call_sites" not in record:
            raise _mismatch("Scanner must report physical call sites")
        for site in record["call_sites"]:
            a, b = site["line"], site["end_line"]
            col, end_col = site["column"], site["end_column"]
            if (
                not start <= a <= b <= end
                or not col <= len(lines[a - 1]) + 1
                or not end_col <= len(lines[b - 1]) + 1
            ):
                raise _mismatch("Call span is outside captured source")
        for query in record.get("queries") or []:
            if (
                not isinstance(query, dict)
                or type(query.get("line")) is not int
                or not start <= query["line"] <= end
            ):
                raise _mismatch("Query span is outside captured source")
        counts[path] += 1
        records.append(record)
    if any(counts[path] != coverage[path]["routine_count"] for path in expected):
        raise _mismatch("Coverage declaration counts differ from emitted declarations")
    records.sort(
        key=lambda item: (
            item["source_path"].encode("utf-8"),
            item["line"],
            item["name"],
        )
    )
    normalized = b"".join(canonical_bytes(record) + b"\n" for record in records)
    document["files"] = [
        coverage[path] for path in sorted(coverage, key=lambda s: s.encode("utf-8"))
    ]
    return normalized, canonical_bytes(document)


class RentgenCapturedGoBuilder:
    def __init__(
        self,
        scanner_executable: Path,
        *,
        timeout_seconds: float = 120,
        max_source_bytes: int = 256 * 1024 * 1024,
        max_output_bytes: int = 128 * 1024 * 1024,
        max_files: int = 100000,
    ):
        self.scanner_executable = Path(scanner_executable).resolve()
        for value in (timeout_seconds, max_source_bytes, max_output_bytes, max_files):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError("scanner limits must be positive")
        self.timeout_seconds = timeout_seconds
        self.max_source_bytes = max_source_bytes
        self.max_output_bytes = max_output_bytes
        self.max_files = max_files

    def build(
        self, captured: CapturedTree, *, output_path: Path, work_dir: Path
    ) -> GraphBuildReceipt:
        try:
            return self._build(
                captured, output_path=Path(output_path), work_dir=Path(work_dir)
            )
        except CoreError:
            raise
        except (OSError, ValueError, sqlite3.Error) as exc:
            raise CoreError(
                "GRAPH_BUILD_FAILED", "Captured graph build failed"
            ) from exc

    def _build(self, captured, *, output_path, work_dir):
        inputs_dir = output_path.parent / "inputs"
        if output_path.exists() or (
            inputs_dir.exists()
            and (not inputs_dir.is_dir() or any(inputs_dir.iterdir()))
        ):
            raise CoreError("GRAPH_BUILD_FAILED", "Graph output must be fresh")
        executable_hash = _hash(self.scanner_executable.read_bytes())
        version = (
            _run_bounded(
                [str(self.scanner_executable), "-version"],
                timeout=self.timeout_seconds,
                max_output_bytes=4096,
            )
            .decode("ascii")
            .strip()
        )
        if version != "bsl-scan-captured-v1":
            raise CoreError("GRAPH_BUILD_FAILED", "Unsupported strict scanner version")
        expected, texts, keys = {}, {}, set()
        bindings = []
        total = 0
        with tempfile.TemporaryDirectory(
            prefix="rentgen-captured-", dir=work_dir
        ) as temp:
            private = Path(temp)
            scan_root = private / "scan"
            scan_root.mkdir()
            for entry in captured.entries:
                if Path(entry.relative_path).suffix.lower() not in BSL_SUFFIXES:
                    continue
                path = entry.layer_id + "/" + entry.relative_path
                key = source_key(path)
                if key in keys or len(path.encode("utf-8")) > 4096:
                    raise _mismatch("Duplicate or unsupported scanner path")
                keys.add(key)
                total += entry.size_bytes
                if total > self.max_source_bytes or len(keys) > self.max_files:
                    raise CoreError(
                        "GRAPH_BUILD_FAILED", "Captured scanner input limit exceeded"
                    )
                raw = captured.read_bytes(entry)
                if len(raw) != entry.size_bytes or _hash(raw) != entry.raw_sha256:
                    raise _mismatch("Captured input raw hash mismatch")
                if entry.encoding not in {"utf-8", "utf-8-sig"}:
                    raise CoreError(
                        "SOURCE_ENCODING_UNSUPPORTED",
                        "BSL requires verified UTF-8 encoding",
                    )
                try:
                    texts[path] = raw.decode("utf-8-sig")
                except UnicodeError as exc:
                    raise CoreError(
                        "SOURCE_ENCODING_UNSUPPORTED", "BSL graph inputs must be UTF-8"
                    ) from exc
                target = scan_root.joinpath(*path.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(raw)
                expected[path] = entry
                bindings.append({**asdict(entry), "graph_source_path": path})
            report_path = private / "coverage.json"
            raw_ndjson = _run_bounded(
                [
                    str(self.scanner_executable),
                    "-mode",
                    "callgraph-strict",
                    "-coverage",
                    str(report_path),
                    str(scan_root),
                ],
                timeout=self.timeout_seconds,
                max_output_bytes=self.max_output_bytes,
                coverage_path=report_path,
            )
            if report_path.stat().st_size > self.max_output_bytes:
                raise CoreError("GRAPH_BUILD_FAILED", "Scanner coverage limit exceeded")
            ndjson, report = _validate_outputs(
                raw_ndjson, report_path.read_bytes(), expected, texts
            )
        if _hash(self.scanner_executable.read_bytes()) != executable_hash:
            raise _mismatch("Scanner executable changed during build")
        bindings.sort(key=lambda item: item["graph_source_path"].encode("utf-8"))
        receipt = GraphBuildReceipt(
            SCHEMA_VERSION,
            IDENTITY_VERSION,
            captured.source_digest,
            _hash(canonical_bytes(bindings)),
            ADAPTER_VERSION,
            version + ";sha256=" + executable_hash,
            BUILDER_VERSION,
            _hash(
                canonical_bytes(
                    {
                        "mode": "callgraph-strict",
                        "coverage_version": 1,
                        "encoding": "utf-8-sig",
                        "quality": "unavailable",
                    }
                )
            ),
            SEMANTIC_SCOPE,
        )
        inputs_dir.mkdir(exist_ok=True)
        callgraph = inputs_dir / "callgraph.ndjson"
        coverage = inputs_dir / "scanner-coverage.json"
        with callgraph.open("xb") as stream:
            stream.write(ndjson)
        with coverage.open("xb") as stream:
            stream.write(report)
        return build_snapshot_graph(
            BuildInputs(callgraph, None),
            output_path,
            receipt,
            source_paths=tuple(expected),
        )


class RentgenGraphReaderFactory:
    def open(self, *, graph_path: Path, snapshot):
        return _RentgenGraphReader(graph_path)


class _RentgenGraphReader:
    """Narrow per-generation interface; each delegated read closes its connection."""

    def __init__(self, graph_path):
        self._store = RentgenStore(graph_path, immutable=True)

    def resolve_module(self, graph_source_path: str) -> dict:
        return self._store.resolve_module(graph_source_path)

    def module_impact(
        self, graph_source_path: str, *, max_depth: int, max_edges: int
    ) -> dict:
        return self._store.module_impact(
            graph_source_path, max_depth=max_depth, max_edges=max_edges
        )
