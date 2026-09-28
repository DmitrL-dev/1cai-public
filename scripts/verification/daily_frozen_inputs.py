"""Verify named bytes before a daily editor/model/native attempt.

The producer field is retained input data. Byte agreement does not qualify its
release claims or establish model quality. No process is launched here.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ROLES = frozenset({"python", "scanner", "platform", "ibcmd", "engine", "test_module", "profile_spec", "vsix", "editor", "core_metadata"})
DIRECTORIES = frozenset({"fixture", "diagnostics", "core", "editor_runtime"})


def _require(ok):
    if not ok:
        raise ValueError("INPUT_BINDING_MISMATCH")


def _ordinary(path, directory=False):
    value = path.lstat()
    _require(not path.is_symlink() and not (getattr(value, "st_file_attributes", 0) & 0x400))
    _require(stat.S_ISDIR(value.st_mode) if directory else stat.S_ISREG(value.st_mode))
    return value


def file_record(path):
    path = Path(path)
    _require(path.is_absolute())
    value = _ordinary(path)
    _require(value.st_size <= 512 * 1024**2)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        actual = os.fstat(stream.fileno())
        _require((actual.st_dev, actual.st_ino, actual.st_size) == (value.st_dev, value.st_ino, value.st_size))
        total = 0
        while chunk := stream.read(1024**2):
            total += len(chunk)
            _require(total <= value.st_size)
            digest.update(chunk)
    _require(total == value.st_size)
    return {"path": str(path.resolve(strict=True)), "size": total, "sha256": digest.hexdigest()}


def _walk_error(error):
    raise error


def require_separate_output(output, input_receipt):
    """Refuse canonical overlap with the input receipt before output writes."""
    output = Path(output).resolve()
    protected = [input_receipt["manifest"]["path"]]
    protected += [item["path"] for item in input_receipt["files"].values()]
    protected += [item["path"] for item in input_receipt["directories"].values()]
    for value in protected:
        path = Path(value).resolve(strict=True)
        _require(not (output.is_relative_to(path) or path.is_relative_to(output)))
    return output


def directory_inventory(root):
    root = Path(root)
    _ordinary(root, directory=True)
    result = {}
    for folder, directories, files in os.walk(root, followlinks=False, onerror=_walk_error):
        _ordinary(Path(folder), directory=True)
        for name in directories:
            _ordinary(Path(folder) / name, directory=True)
        for name in files:
            _require(len(result) < 5000)
            path = Path(folder) / name
            item = file_record(path)
            result[path.relative_to(root).as_posix()] = {k: item[k] for k in ("size", "sha256")}
    return result


def _expected_file(item):
    _require(type(item) is dict and set(item) == {"path", "size", "sha256"})
    _require(type(item["size"]) is int and 0 <= item["size"] <= 512 * 1024**2)
    _require(isinstance(item["path"], str) and Path(item["path"]).is_absolute())
    _require(isinstance(item["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is not None)
    actual = file_record(Path(item["path"]))
    _require(actual == {**item, "path": str(Path(item["path"]).resolve(strict=True))})
    return actual


def verify_frozen(path):
    path = Path(path).resolve(strict=True)
    _require(_ordinary(path).st_size <= 4 * 1024**2)
    raw = path.read_bytes()
    binding = json.loads(raw.decode("utf-8"))
    _require(type(binding) is dict and set(binding) == {"schema", "core_version", "companion_version", "profile_id", "files", "directories", "producer"})
    _require(type(binding["schema"]) is int and binding["schema"] == 1)
    _require(isinstance(binding["core_version"], str) and re.fullmatch(r"0\.1\.0\.dev[0-9]+", binding["core_version"]) is not None)
    _require(isinstance(binding["companion_version"], str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", binding["companion_version"]) is not None)
    _require(isinstance(binding["profile_id"], str) and re.fullmatch(r"[0-9a-f]{64}", binding["profile_id"]) is not None)
    _require(type(binding["producer"]) is dict)
    _require(type(binding["files"]) is dict and set(binding["files"]) == ROLES)
    files = {name: _expected_file(item) for name, item in binding["files"].items()}
    _require(type(binding["directories"]) is dict and set(binding["directories"]) == DIRECTORIES)
    directories = {}
    for name, item in binding["directories"].items():
        _require(type(item) is dict and set(item) == {"path", "exact", "files"})
        _require(isinstance(item["path"], str) and Path(item["path"]).is_absolute() and type(item["exact"]) is bool)
        _require(item["exact"] is True or name == "core")
        root = Path(item["path"])
        _ordinary(root, directory=True)
        expected = item["files"]
        _require(type(expected) is dict and 0 < len(expected) <= 5000)
        actual = {}
        for relative, pin in expected.items():
            _require(isinstance(relative, str) and relative and "\\" not in relative and not Path(relative).is_absolute() and all(p not in {"", ".", ".."} for p in relative.split("/")))
            _require(type(pin) is dict and set(pin) == {"size", "sha256"})
            target = root.joinpath(*relative.split("/"))
            _require(target.resolve(strict=True).is_relative_to(root.resolve(strict=True)))
            actual_pin = _expected_file({"path": str(target), **pin})
            actual[relative] = {k: actual_pin[k] for k in ("size", "sha256")}
        if item["exact"]:
            _require(directory_inventory(root) == expected)
        encoded = json.dumps(actual, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        directories[name] = {"path": str(root.resolve(strict=True)), "files": len(actual), "manifest_sha256": hashlib.sha256(encoded).hexdigest()}
    return binding, {"manifest": file_record(path), "files": files, "directories": directories, "producer_claim": binding["producer"], "source_ci_qualified_by_this_check": False}
