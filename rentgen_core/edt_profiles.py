"""Project-admin EDT toolchains; registration never executes the runtime."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
from uuid import uuid4

from ._windows_source_tree import pinned_directory, pinned_retained, read_retained
from .edt_inventory import BOOT, MAX_FILE, MAX_FILES, MAX_TOTAL, inventory
from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .platform_check import _pin_inputs
from .source_paths import validate_inventory_paths

PERMISSIONS = frozenset({"project:read", "source:edit", "analysis:run"})
HASH = re.compile(r"[0-9a-f]{64}")
PLUGIN = "plugins/com.ditrix.edt.mcp.server_2.16.1.jar"
EDT = "plugins/com._1c.g5.v8.dt.core_27.0.2.v202609041212.jar"
MAX_RECORD = 2 * 1024**2


def require(value, message="Invalid EDT profile"):
    if not value:
        raise CoreError("EDT_PROFILE_INVALID", message)


def keys(value, names):
    require(type(value) is dict and set(value) == set(names))


def parse_json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "Duplicate profile field")
            value[key] = item
        return value

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeError, ValueError) as exc:
        raise CoreError("EDT_PROFILE_INVALID", "Invalid profile JSON") from exc


@contextmanager
def authorized(ctx, permissions=PERMISSIONS):
    def check():
        with ctx.state.transaction(ctx.principal) as tx:
            tx.require_all(permissions)

    check()
    try:
        yield check
    finally:
        check()


def profile_path(ctx, identity):
    require(type(identity) is str and HASH.fullmatch(identity))
    return ctx.state.path.parent / "edt-profiles" / identity


def _path(value):
    require(type(value) is str and Path(value).is_absolute())
    require(not any(ord(c) < 32 for c in value))
    return Path(value)


def _validate(definition):
    keys(
        definition,
        {
            "schema",
            "name",
            "java",
            "java_root",
            "runtime_root",
            "java_files",
            "runtime_files",
            "launcher",
        },
    )
    require(type(definition["schema"]) is int and definition["schema"] == 1)
    require(type(definition["name"]) is str and 1 <= len(definition["name"]) <= 128)
    require(not any(ord(c) < 32 for c in definition["name"]))
    keys(definition["java"], {"path", "sha256"})
    java = _path(definition["java"]["path"])
    require(java.name.lower() == "java.exe" and java.parent.name.lower() == "bin")
    require(
        type(definition["java"]["sha256"]) is str
        and HASH.fullmatch(definition["java"]["sha256"])
    )
    require(_path(definition["java_root"]) == java.parent.parent)
    _path(definition["runtime_root"])
    for key in ("runtime_files", "java_files"):
        rows = definition[key]
        require(type(rows) is list and 1 <= len(rows) <= MAX_FILES)
        total = 0
        for row in rows:
            keys(row, {"path", "size", "sha256"})
            require(type(row["size"]) is int and 0 <= row["size"] <= MAX_FILE)
            require(type(row["sha256"]) is str and HASH.fullmatch(row["sha256"]))
            require(type(row["path"]) is str)
            if key == "runtime_files":
                require(row["path"].startswith("plugins/") or row["path"] in BOOT)
            else:
                require(
                    row["path"] == "release"
                    or row["path"].startswith(("bin/", "lib/", "conf/"))
                )
            total += row["size"]
        require(
            total <= MAX_TOTAL and rows == sorted(rows, key=lambda row: row["path"])
        )
        validate_inventory_paths(row["path"] for row in rows)
    files = {row["path"] for row in definition["runtime_files"]}
    require({PLUGIN, EDT, *BOOT} <= files, "Unsupported EDT/MCP tuple")
    launchers = [
        p
        for p in files
        if re.fullmatch(r"plugins/org\.eclipse\.equinox\.launcher_[^/]+\.jar", p)
    ]
    require(len(launchers) == 1 and definition["launcher"] == launchers[0])
    java_row = next(
        (row for row in definition["java_files"] if row["path"] == "bin/java.exe"), None
    )
    require(java_row is not None and java_row["sha256"] == definition["java"]["sha256"])


def _load(ctx, identity):
    folder = profile_path(ctx, identity)
    with pinned_directory(folder):
        record = parse_json(read_retained(folder / "profile.json", MAX_RECORD))
        keys(
            record,
            {
                "profile_id",
                "project_id",
                "definition",
                "registered_by",
                "registered_at",
            },
        )
        _validate(record["definition"])
        require(
            record["profile_id"] == identity and record["project_id"] == ctx.project_id
        )
        require(
            sha256(canonical_bytes(record["definition"])) == identity,
            "EDT profile hash mismatch",
        )
        return {**record, "enabled": not (folder / "disabled").exists()}


def _summary(record):
    definition = record["definition"]
    return {
        "profile_id": record["profile_id"],
        "name": definition["name"],
        "enabled": record["enabled"],
        "qualification": "not_run",
        "runtime_files": len(definition["runtime_files"]),
        "java_files": len(definition["java_files"]),
    }


def register_profile(ctx, specification):
    with authorized(ctx, {"project:admin"}) as check:
        keys(specification, {"schema", "name", "java", "runtime_root"})
        specification = parse_json(canonical_bytes(specification))
        require(type(specification["schema"]) is int and specification["schema"] == 1)
        require(
            type(specification["name"]) is str
            and 1 <= len(specification["name"]) <= 128
        )
        require(not any(ord(c) < 32 for c in specification["name"]))
        keys(specification["java"], {"path", "sha256"})
        runtime, java = _path(specification["runtime_root"]), _path(
            specification["java"]["path"]
        )
        require(java.name.lower() == "java.exe" and java.parent.name.lower() == "bin")
        require(
            sha256(read_retained(java, 1024**2)) == specification["java"]["sha256"],
            "Java executable hash mismatch",
        )
        definition = {
            **specification,
            "java_root": str(java.parent.parent),
            "runtime_files": inventory(runtime, authorize=check),
            "java_files": inventory(java.parent.parent, java=True, authorize=check),
        }
        launchers = [
            row["path"]
            for row in definition["runtime_files"]
            if re.fullmatch(
                r"plugins/org\.eclipse\.equinox\.launcher_[^/]+\.jar", row["path"]
            )
        ]
        require(len(launchers) == 1)
        definition["launcher"] = launchers[0]
        _validate(definition)
        identity = sha256(canonical_bytes(definition))
        target = profile_path(ctx, identity)
        target.parent.mkdir(exist_ok=True)
        with pinned_directory(target.parent):
            if target.exists():
                return _summary(_load(ctx, identity))
            with os.scandir(target.parent) as entries:
                for index, _ in enumerate(entries):
                    require(index < 63, "At most 64 EDT profile entries")
            stage = target.parent / ("pending-" + str(uuid4()))
            record = {
                "profile_id": identity,
                "project_id": ctx.project_id,
                "definition": definition,
                "registered_by": asdict(ctx.principal),
                "registered_at": datetime.now(timezone.utc).isoformat(),
            }
            raw = canonical_bytes(record)
            require(len(raw) <= MAX_RECORD, "EDT profile record exceeds limits")
            stage.mkdir()
            with (stage / "profile.json").open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        with ctx.state.transaction(ctx.principal) as tx:
            tx.require_all({"project:admin"})
            deadline = time.monotonic() + 5
            while True:
                try:
                    stage.rename(target)
                    break
                except FileExistsError:
                    break
                except OSError as exc:
                    if (
                        getattr(exc, "winerror", None) not in {32, 33}
                        or time.monotonic() >= deadline
                    ):
                        raise
                    time.sleep(0.02)
        return _summary(_load(ctx, identity))


def get_profile(ctx, identity):
    with authorized(ctx):
        return _load(ctx, identity)


def list_profiles(ctx):
    with authorized(ctx):
        parent = ctx.state.path.parent / "edt-profiles"
        if not parent.exists():
            return []
        rows = []
        with pinned_directory(parent), os.scandir(parent) as entries:
            for index, entry in enumerate(entries):
                require(index < 128, "EDT profile inventory exceeds limits")
                if HASH.fullmatch(entry.name):
                    rows.append(_summary(_load(ctx, entry.name)))
        return sorted(rows, key=lambda row: row["profile_id"])


def disable_profile(ctx, identity):
    with authorized(ctx, {"project:admin"}):
        record = _load(ctx, identity)
        with pinned_directory(profile_path(ctx, identity)):
            try:
                with (profile_path(ctx, identity) / "disabled").open("xb") as stream:
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                pass
        record["enabled"] = False
        return _summary(record)


def authorize_run(ctx, identity):
    with authorized(ctx):
        with pinned_directory(profile_path(ctx, identity)):
            if (profile_path(ctx, identity) / "disabled").exists():
                raise CoreError("EDT_PROFILE_DISABLED", "EDT profile is disabled")


@contextmanager
def pinned_runtime(ctx, identity):
    with authorized(ctx), pinned_retained(
        profile_path(ctx, identity) / "profile.json", MAX_RECORD
    ):
        record = _load(ctx, identity)
        authorize_run(ctx, identity)
        definition = record["definition"]

        def check():
            authorize_run(ctx, identity)

        for key, java in (("runtime", False), ("java", True)):
            current = inventory(
                Path(definition[key + "_root"]),
                java=java,
                authorize=check,
                hashes=False,
            )
            expected = [
                {"path": r["path"], "size": r["size"]}
                for r in definition[key + "_files"]
            ]
            require(current == expected, "Runtime file inventory changed")
        with _pin_inputs(
            Path(definition["runtime_root"]), definition["runtime_files"]
        ), _pin_inputs(Path(definition["java_root"]), definition["java_files"]):
            check()
            try:
                yield definition
            finally:
                check()
