"""Narrow deterministic JSON contracts for captured source evidence."""
from dataclasses import asdict, dataclass
import hashlib
import json

from .context import validate_project_id
from .errors import CoreError
from .source_configuration import SourceConfiguration, SourceLayerSpec
from .source_paths import validate_source_path, validate_file_paths
from .snapshots import _validate_hash


def _corrupt(message="Invalid source manifest"):
    return CoreError("SNAPSHOT_CORRUPT", message)


def _domain(value):
    if value is None or type(value) is bool:
        return
    if type(value) is int and 0 <= value < 2**63:
        return
    if isinstance(value, str):
        try:
            value.encode("utf-8")
            return
        except UnicodeError:
            pass
    elif isinstance(value, list):
        for item in value:
            _domain(item)
        return
    elif isinstance(value, dict) and all(isinstance(k, str) for k in value):
        for key, item in value.items():
            _domain(key)
            _domain(item)
        return
    raise _corrupt("Value is outside the canonical JSON domain")


def canonical_bytes(document) -> bytes:
    _domain(document)
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _corrupt("Duplicate JSON key")
        result[key] = value
    return result


def _decode(raw):
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        if canonical_bytes(document) != raw:
            raise _corrupt("Manifest is not canonical JSON")
        return document
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise _corrupt("Invalid canonical JSON") from exc


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise _corrupt("Unexpected manifest schema keys")


@dataclass(frozen=True)
class CapturedInput:
    layer_id: str
    relative_path: str
    raw_sha256: str
    size_bytes: int
    encoding: str | None

    def __post_init__(self):
        SourceLayerSpec(self.layer_id, 0, "base", ".", "unknown")
        validate_source_path(self.relative_path)
        _validate_hash(self.raw_sha256)
        if (
            type(self.size_bytes) is not int
            or not 0 <= self.size_bytes < 2**63
            or self.encoding not in (None, "utf-8", "utf-8-sig")
        ):
            raise _corrupt()


def _validate_source(document):
    _keys(document, "format_version project_id layers excluded_state_subtrees entries")
    if type(document["format_version"]) is not int or document["format_version"] != 1:
        raise CoreError(
            "SNAPSHOT_SCHEMA_MISMATCH", "Unsupported source manifest version"
        )
    validate_project_id(document["project_id"])
    if any(
        not isinstance(document[key], list)
        for key in ("layers", "entries", "excluded_state_subtrees")
    ):
        raise _corrupt("Manifest inventories must be arrays")
    layers = []
    for layer in document["layers"]:
        _keys(
            layer,
            "layer_id ordinal kind root_relative_path source_format configuration_uuid identity_status",
        )
        if (
            layer["configuration_uuid"] is not None
            or layer["identity_status"] != "unresolved"
        ):
            raise _corrupt()
        layers.append(
            SourceLayerSpec(
                **{
                    key: layer[key]
                    for key in (
                        "layer_id",
                        "ordinal",
                        "kind",
                        "root_relative_path",
                        "source_format",
                    )
                }
            )
        )
    config = SourceConfiguration(1, tuple(layers))
    order = {layer.layer_id: layer.ordinal for layer in config.layers}
    entries = []
    paths = {layer.layer_id: [] for layer in config.layers}
    for item in document["entries"]:
        _keys(item, "layer_id relative_path raw_sha256 size_bytes encoding")
        entry = CapturedInput(**item)
        if entry.layer_id not in order:
            raise _corrupt()
        entries.append(entry)
        paths[entry.layer_id].append(entry.relative_path)
    for names in paths.values():
        validate_file_paths(names)
    if entries != sorted(
        entries, key=lambda e: (order[e.layer_id], e.relative_path.encode("utf-8"))
    ):
        raise _corrupt("Unsorted source entries")
    exclusions = document["excluded_state_subtrees"]
    seen = set()
    for exclusion in exclusions:
        _keys(exclusion, "layer_id relative_path")
        layer = exclusion["layer_id"]
        path = validate_source_path(exclusion["relative_path"])
        if (
            layer not in order
            or layer in seen
            or any(name == path or name.startswith(path + "/") for name in paths[layer])
        ):
            raise _corrupt("Invalid state exclusion")
        seen.add(layer)
    if exclusions != sorted(exclusions, key=lambda e: order[e["layer_id"]]):
        raise _corrupt("Unsorted state exclusions")
    return document


def build_source_document(project_id, configuration, exclusions, entries) -> bytes:
    order = {layer.layer_id: layer.ordinal for layer in configuration.layers}
    document = {
        "format_version": 1,
        "project_id": project_id,
        "layers": [
            dict(asdict(layer), configuration_uuid=None, identity_status="unresolved")
            for layer in configuration.layers
        ],
        "excluded_state_subtrees": [
            {"layer_id": layer, "relative_path": path}
            for layer, path in sorted(exclusions, key=lambda e: order[e[0]])
        ],
        "entries": [
            asdict(entry)
            for entry in sorted(
                entries,
                key=lambda e: (order[e.layer_id], e.relative_path.encode("utf-8")),
            )
        ],
    }
    return canonical_bytes(_validate_source(document))


def parse_source_document(raw: bytes):
    try:
        return _validate_source(_decode(raw))
    except (KeyError, TypeError, ValueError) as exc:
        raise _corrupt() from exc


_CAPTURE = {
    "bytes_immutable": True,
    "method": "working_tree_verified_passes_v1",
    "temporal_atomicity": "not_proven",
}
_GRAPH_KEYS = "relative_path raw_sha256 schema_version identity_version source_digest input_binding_hash adapter_version scanner_version builder_version sqlite_version options_hash semantic_scope quality"
_DERIVED_PATHS = ["inputs/callgraph.ndjson", "inputs/scanner-coverage.json"]


def _validate_manifest(document):
    _keys(
        document,
        "format_version canonicalization project_id source source_digest capture graph derived_inputs",
    )
    if (
        type(document["format_version"]) is not int
        or document["format_version"] != 1
        or document["canonicalization"] != "rentgen-json-v1"
    ):
        raise CoreError(
            "SNAPSHOT_SCHEMA_MISMATCH", "Unsupported snapshot manifest version"
        )
    source = _validate_source(document["source"])
    if document["project_id"] != source["project_id"] or document[
        "source_digest"
    ] != sha256(canonical_bytes(source)):
        raise _corrupt("Source manifest binding mismatch")
    if (
        document["capture"] != _CAPTURE
        or type(document["capture"].get("bytes_immutable")) is not bool
    ):
        raise _corrupt("Invalid capture guarantee")
    graph = document["graph"]
    _keys(graph, _GRAPH_KEYS)
    for key in ("raw_sha256", "source_digest", "input_binding_hash", "options_hash"):
        _validate_hash(graph[key])
    if any(not isinstance(graph[key], str) or not graph[key] for key in graph):
        raise _corrupt("Graph provenance requires strings")
    for key, value in {
        "relative_path": "graph.sqlite3",
        "schema_version": "2",
        "identity_version": "source-path-v1",
        "source_digest": document["source_digest"],
        "adapter_version": "rentgen-captured-go-v1",
        "quality": "unavailable",
        "semantic_scope": "bounded_static_calls; preprocessing and dynamic types unresolved",
    }.items():
        if graph[key] != value:
            raise _corrupt("Graph binding or capability mismatch")
    derived = document["derived_inputs"]
    if not isinstance(derived, list) or len(derived) != len(_DERIVED_PATHS):
        raise _corrupt("Invalid derived input inventory")
    for entry, path in zip(derived, _DERIVED_PATHS):
        _keys(entry, "relative_path raw_sha256 size_bytes")
        _validate_hash(entry["raw_sha256"])
        if (
            entry["relative_path"] != path
            or type(entry["size_bytes"]) is not int
            or not 0 <= entry["size_bytes"] < 2**63
        ):
            raise _corrupt("Invalid derived input record")
    return document


def build_manifest(source_document: bytes, graph: dict, derived_inputs: list) -> bytes:
    source = parse_source_document(source_document)
    return canonical_bytes(
        _validate_manifest(
            {
                "format_version": 1,
                "canonicalization": "rentgen-json-v1",
                "project_id": source["project_id"],
                "source": source,
                "source_digest": sha256(source_document),
                "capture": dict(_CAPTURE),
                "graph": graph,
                "derived_inputs": derived_inputs,
            }
        )
    )


def parse_manifest(raw: bytes):
    try:
        return _validate_manifest(_decode(raw))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise _corrupt() from exc
