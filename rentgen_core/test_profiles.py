"""Administrator-owned immutable test inputs; never accepts model startup authority."""
from base64 import b64encode, b64decode
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
from uuid import uuid4

from ._windows_source_tree import pinned_directory, read_retained
from .errors import CoreError
from .manifests import canonical_bytes, sha256

ENGINE_SHA256 = "805a2277c997a3c24be0b0d080696479e91e4a15ed7e27aaf3991a7346522d70"
PERMISSIONS = frozenset({"project:read", "source:edit", "analysis:run"})
HASH = re.compile(r"[0-9a-f]{64}")
NAME = re.compile(r"[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё_0-9]{0,79}")


def _require(ok, message="Invalid test profile"):
    if not ok:
        raise CoreError("TEST_PROFILE_INVALID", message)


@contextmanager
def authorized(ctx, permissions=PERMISSIONS):
    def check():
        with ctx.state.transaction(ctx.principal) as tx:
            tx.require_all(permissions)

    check()
    try:
        yield
    finally:
        check()


def profile_path(ctx, profile_id):
    _require(type(profile_id) is str and HASH.fullmatch(profile_id))
    return ctx.state.path.parent / "test-profiles" / profile_id


def _json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            _require(key not in value, "Duplicate profile field")
            value[key] = item
        return value

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (ValueError, UnicodeError) as exc:
        raise CoreError("TEST_PROFILE_INVALID", "Invalid profile JSON") from exc


def _keys(value, keys):
    _require(type(value) is dict and set(value) == set(keys))


def _input(item, *, filename=None, maximum=64 * 1024**2):
    _keys(item, {"path", "sha256"})
    _require(
        type(item["path"]) is str
        and type(item["sha256"]) is str
        and HASH.fullmatch(item["sha256"])
    )
    path = Path(item["path"])
    _require(path.is_absolute() and (filename is None or path.name.lower() == filename))
    raw = read_retained(path, maximum)
    _require(sha256(raw) == item["sha256"], "Test input hash mismatch")
    return raw


def _validate(definition):
    _keys(
        definition, {"schema", "name", "platform", "ibcmd", "engine_sha256", "modules"}
    )
    _require(type(definition["schema"]) is int and definition["schema"] == 1)
    _require(
        type(definition["name"]) is str
        and 1 <= len(definition["name"]) <= 128
        and not any(ord(c) < 32 for c in definition["name"])
    )
    _require(definition["engine_sha256"] == ENGINE_SHA256)
    for key, filename in (("platform", "1cv8.exe"), ("ibcmd", "ibcmd.exe")):
        item = definition[key]
        _keys(item, {"path", "sha256"})
        _require(
            type(item["path"]) is str
            and Path(item["path"]).is_absolute()
            and Path(item["path"]).name.lower() == filename
            and type(item["sha256"]) is str
            and HASH.fullmatch(item["sha256"])
        )
    modules = definition["modules"]
    _require(type(modules) is list and 1 <= len(modules) <= 8)
    names, total = set(), 0
    for module in modules:
        _keys(module, {"name", "base64", "sha256", "tests"})
        name = module["name"]
        _require(
            type(name) is str and NAME.fullmatch(name) and name.casefold() not in names
        )
        names.add(name.casefold())
        _require(type(module["base64"]) is str and len(module["base64"]) <= 87384)
        try:
            raw = b64decode(module["base64"], validate=True)
            raw.decode("utf-8-sig")
        except (ValueError, UnicodeError) as exc:
            raise CoreError(
                "TEST_PROFILE_INVALID", "Test module must be UTF-8"
            ) from exc
        _require(
            0 < len(raw) <= 65536
            and b64encode(raw).decode() == module["base64"]
            and sha256(raw) == module["sha256"]
        )
        tests = module["tests"]
        _require(type(tests) is list and 1 <= len(tests) <= 128)
        _require(all(type(t) is str and NAME.fullmatch(t) for t in tests))
        _require(len(set(t.casefold() for t in tests)) == len(tests))
        total += len(tests)
    _require(total <= 128, "At most 128 explicitly named tests")


def _load(ctx, profile_id):
    folder = profile_path(ctx, profile_id)
    with pinned_directory(folder):
        value = _json(read_retained(folder / "profile.json", 1024 * 1024))
        _keys(
            value,
            {
                "profile_id",
                "project_id",
                "definition",
                "registered_by",
                "registered_at",
            },
        )
        _validate(value["definition"])
        _require(
            value["profile_id"] == profile_id
            and value["project_id"] == ctx.project_id
            and sha256(canonical_bytes(value["definition"])) == profile_id,
            "Profile identity mismatch",
        )
        if (folder / "disabled").exists():
            _require(
                read_retained(folder / "disabled", 1) == b"", "Invalid disable marker"
            )
            value["enabled"] = False
        else:
            value["enabled"] = True
        return value


def _summary(value):
    return {
        "profile_id": value["profile_id"],
        "name": value["definition"]["name"],
        "enabled": value["enabled"],
        "modules": [
            {"name": m["name"], "sha256": m["sha256"], "tests": m["tests"]}
            for m in value["definition"]["modules"]
        ],
    }


def register_profile(ctx, specification):
    with authorized(ctx, {"project:admin"}):
        _keys(
            specification, {"schema", "name", "platform", "ibcmd", "engine", "modules"}
        )
        _input(specification["platform"], filename="1cv8.exe")
        _input(specification["ibcmd"], filename="ibcmd.exe")
        _keys(specification["engine"], {"path", "sha256"})
        _require(specification["engine"].get("sha256") == ENGINE_SHA256)
        engine = _input(specification["engine"], maximum=8 * 1024**2)
        _require(
            type(specification["modules"]) is list
            and 1 <= len(specification["modules"]) <= 8
        )
        modules = []
        for item in specification["modules"]:
            _keys(item, {"name", "path", "tests"})
            _require(type(item["path"]) is str and Path(item["path"]).is_absolute())
            raw = read_retained(Path(item["path"]), 65536)
            modules.append(
                {
                    "name": item["name"],
                    "tests": item["tests"],
                    "base64": b64encode(raw).decode(),
                    "sha256": sha256(raw),
                }
            )
        definition = {
            k: specification[k] for k in ("schema", "name", "platform", "ibcmd")
        }
        definition.update(engine_sha256=ENGINE_SHA256, modules=modules)
        _validate(definition)
        profile_id = sha256(canonical_bytes(definition))
        target = profile_path(ctx, profile_id)
        target.parent.mkdir(exist_ok=True)
        with pinned_directory(target.parent):
            if target.exists():
                return _summary(_load(ctx, profile_id))
            with os.scandir(target.parent) as entries:
                if sum(1 for _, entry in zip(range(129), entries)) >= 128:
                    raise CoreError(
                        "TEST_PROFILE_LIMIT", "At most 128 profile directories"
                    )
            stage = target.parent / ("pending-" + str(uuid4()))
            stage.mkdir()
            record = {
                "profile_id": profile_id,
                "project_id": ctx.project_id,
                "definition": definition,
                "registered_by": asdict(ctx.principal),
                "registered_at": datetime.now(timezone.utc).isoformat(),
            }
            for name, raw in (
                ("profile.json", canonical_bytes(record)),
                ("engine.cfe", engine),
            ):
                with (stage / name).open("xb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
        # Windows no-delete directory pins must be released for publication.
        # A concurrent inventory reader may briefly hold the same parent pin.
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
        return _summary(_load(ctx, profile_id))


def get_profile(ctx, profile_id, *, active=False):
    with authorized(ctx):
        value = _load(ctx, profile_id)
        if active and not value["enabled"]:
            raise CoreError("TEST_PROFILE_DISABLED", "Test profile is disabled")
        return value


def list_profiles(ctx):
    with authorized(ctx):
        parent = ctx.state.path.parent / "test-profiles"
        if not parent.exists():
            return []
        rows = []
        with pinned_directory(parent), os.scandir(parent) as entries:
            for index, entry in enumerate(entries):
                _require(index < 256, "Profile inventory limit")
                if HASH.fullmatch(entry.name):
                    rows.append(_summary(_load(ctx, entry.name)))
        return sorted(rows, key=lambda row: row["profile_id"])


def disable_profile(ctx, profile_id):
    with authorized(ctx, {"project:admin"}):
        value = _load(ctx, profile_id)
        with pinned_directory(profile_path(ctx, profile_id)):
            try:
                with (profile_path(ctx, profile_id) / "disabled").open("xb") as stream:
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                pass
        value["enabled"] = False
        return _summary(value)


def authorize_run(ctx, profile_id):
    with authorized(ctx):
        folder = profile_path(ctx, profile_id)
        with pinned_directory(folder):
            if (folder / "disabled").exists():
                raise CoreError("TEST_PROFILE_DISABLED", "Test profile is disabled")
