"""Runtime ownership contracts across cached enumeration and retained handles."""
from dataclasses import replace
import ctypes
import hashlib
import os
import sys

import pytest

from rentgen_core._windows_source_tree import WindowsHandleOps
from rentgen_core.errors import CoreError
from rentgen_diagnostics._owned_attempt import OwnedAttempt
from rentgen_diagnostics._runtime_pins import PinFailure, RuntimePins

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows handle contract"
)


class DirectoryCacheOps(WindowsHandleOps):
    """Real Win32 IO; only cached directory time/size fields are controlled."""

    def __init__(self):
        super().__init__()
        self.paths = {}
        self.open_counts = {}
        self.cached_directories = {}
        self.refresh = None
        self.direct_changes = {}
        self.listed_changes = {}
        self.final_paths = {}
        self.reject_stamp = set()

    def open(self, path, *, directory):
        handle = super().open(path, directory=directory)
        self.paths[handle] = path
        self.open_counts[path] = self.open_counts.get(path, 0) + 1
        return handle

    def close(self, handle):
        super().close(handle)
        self.paths.pop(handle, None)

    def stamp(self, handle):
        path = self.paths.get(handle)
        if path in self.reject_stamp:
            raise CoreError("SOURCE_PATH_UNSAFE", "Controlled unsafe-object rejection")
        return replace(super().stamp(handle), **self.direct_changes.get(path, {}))

    def final_path(self, handle):
        actual = super().final_path(handle)
        return self.final_paths.get(actual, actual)

    def enumerate(self, handle):
        parent = self.paths[handle]
        for name, stamp in super().enumerate(handle):
            if stamp.directory:
                saved = self.cached_directories.setdefault(parent / name, stamp)
                stamp = replace(
                    stamp, write=saved.write, change=saved.change, size=saved.size
                )
                if self.refresh is not None:
                    stamp = replace(
                        stamp, **{self.refresh: getattr(stamp, self.refresh) + 1}
                    )
            yield name, replace(stamp, **self.listed_changes.get(parent / name, {}))


def runtime_tree(tmp_path):
    root = tmp_path / "runtime"
    directory = root / "lib"
    directory.mkdir(parents=True)
    raw = b"runtime fixture\r\n"
    (directory / "module.bin").write_bytes(raw)
    return (
        root,
        directory,
        {"lib/module.bin": (len(raw), hashlib.sha256(raw).hexdigest())},
    )


@pytest.mark.parametrize("field", ["write", "change", "size"])
def test_directory_cache_refresh_preserves_runtime(tmp_path, field):
    root, directory, expected = runtime_tree(tmp_path)
    ops = DirectoryCacheOps()
    pins = RuntimePins(operations=ops)
    try:
        pins.tree(root, expected)
        original = ops.stamp(pins.handles[directory])
        ops.refresh = field
        pins.verify()
        pins.watch_directory(root)
        assert ops.stamp(pins.handles[directory]) == original
        assert ops.open_counts[directory] == 1
    finally:
        pins.close()
    assert not ops.paths


@pytest.mark.parametrize(
    "field", ["write", "change", "size", "attributes", "creation", "identity", "type"]
)
def test_authoritative_directory_change_is_rejected(tmp_path, field):
    root, directory, expected = runtime_tree(tmp_path)
    ops = DirectoryCacheOps()
    pins = RuntimePins(operations=ops)
    try:
        pins.tree(root, expected)
        stamp = ops.stamp(pins.handles[directory])
        if field == "identity":
            changes = {field: (stamp.identity[0], stamp.identity[1] + 1)}
        elif field == "type":
            changes = {"attributes": stamp.attributes & ~0x10}
        else:
            changes = {field: getattr(stamp, field) + 1}
        ops.direct_changes[directory] = changes
        with pytest.raises(PinFailure) as error:
            pins.verify()
        assert error.value.code == "BSL_INPUT_CHANGED"
    finally:
        pins.close()
    assert not ops.paths


@pytest.mark.parametrize("field", ["attributes", "creation", "identity", "type"])
def test_directory_enumeration_binding_is_rejected(tmp_path, field):
    root, directory, expected = runtime_tree(tmp_path)
    ops = DirectoryCacheOps()
    pins = RuntimePins(operations=ops)
    try:
        pins.tree(root, expected)
        stamp = ops.cached_directories[directory]
        if field == "identity":
            changes = {field: (stamp.identity[0], stamp.identity[1] + 1)}
        elif field == "type":
            changes = {"attributes": stamp.attributes & ~0x10}
        else:
            changes = {field: getattr(stamp, field) + 1}
        ops.listed_changes[directory] = changes
        with pytest.raises(PinFailure) as error:
            pins.verify()
        assert error.value.code == "BSL_INPUT_CHANGED"
    finally:
        pins.close()
    assert not ops.paths


@pytest.mark.parametrize("source", ["direct", "enumerated"])
@pytest.mark.parametrize(
    "field", ["write", "change", "size", "attributes", "creation", "identity"]
)
def test_file_stamp_changes_remain_rejected(tmp_path, source, field):
    root, directory, expected = runtime_tree(tmp_path)
    file = directory / "module.bin"
    ops = DirectoryCacheOps()
    pins = RuntimePins(operations=ops)
    try:
        pins.tree(root, expected)
        stamp = ops.stamp(pins.handles[file])
        value = (
            (stamp.identity[0], stamp.identity[1] + 1)
            if field == "identity"
            else getattr(stamp, field) + 1
        )
        changes = ops.direct_changes if source == "direct" else ops.listed_changes
        changes[file] = {field: value}
        with pytest.raises(PinFailure) as error:
            pins.verify()
        assert error.value.code == "BSL_INPUT_CHANGED"
    finally:
        pins.close()
    assert not ops.paths


def test_directory_final_path_change_is_rejected(tmp_path):
    root, directory, expected = runtime_tree(tmp_path)
    ops = DirectoryCacheOps()
    pins = RuntimePins(operations=ops)
    try:
        pins.tree(root, expected)
        ops.final_paths[directory] = root / "other"
        with pytest.raises(PinFailure) as error:
            pins.verify()
        assert error.value.code == "BSL_INPUT_CHANGED"
    finally:
        pins.close()
    assert not ops.paths


def test_new_file_membership_is_rejected(tmp_path):
    root, _, expected = runtime_tree(tmp_path)
    pins = RuntimePins()
    try:
        pins.tree(root, expected)
        (root / "extra.bin").write_bytes(b"new input")
        with pytest.raises(PinFailure) as error:
            pins.verify()
        assert error.value.code == "BSL_INPUT_CHANGED"
    finally:
        pins.close()


def test_directory_stamp_failure_keeps_handle_owned_for_close(tmp_path):
    root, directory, _ = runtime_tree(tmp_path)
    ops = DirectoryCacheOps()
    ops.reject_stamp.add(directory)
    pins = RuntimePins(operations=ops)
    try:
        with pytest.raises(PinFailure):
            pins.watch_directory(root)
        assert directory in pins.handles
    finally:
        pins.close()
    assert not ops.paths


def test_handle_budget_prevents_additional_directory_open(tmp_path):
    root, directory, _ = runtime_tree(tmp_path)
    ops = DirectoryCacheOps()
    pins = RuntimePins(operations=ops)
    try:
        pins.directory(root)
        # Synthetic occupied-budget entries are not native handles.
        pins.uncertain.extend([None] * (1080 - len(pins.handles)))
        with pytest.raises(PinFailure) as error:
            pins.watch_directory(root)
        assert error.value.code == "BSL_RESOURCE_LIMIT"
        assert directory not in ops.open_counts
    finally:
        pins.uncertain.clear()
        pins.close()
    assert not ops.paths


def test_check_failure_prevents_additional_directory_open(tmp_path):
    root, directory, _ = runtime_tree(tmp_path)
    ops = DirectoryCacheOps()
    armed = False

    def check():
        if armed:
            raise RuntimeError("revoked")

    pins = RuntimePins(operations=ops, check=check)
    try:
        pins.directory(root)
        armed = True
        with pytest.raises(RuntimeError, match="revoked"):
            pins.watch_directory(root)
        assert directory not in ops.open_counts
    finally:
        pins.close()
    assert not ops.paths


def test_file_hardlink_alias_remains_rejected(tmp_path):
    root, directory, expected = runtime_tree(tmp_path)
    os.link(directory / "module.bin", tmp_path / "alias.bin")
    pins = RuntimePins()
    try:
        with pytest.raises(PinFailure):
            pins.tree(root, expected)
    finally:
        pins.close()


def test_owned_attempt_inventory_and_cleanup_use_retained_directories(tmp_path, monkeypatch):
    ops = DirectoryCacheOps()
    pins = RuntimePins(operations=ops)
    attempt = OwnedAttempt(tmp_path / "attempts", pins)
    create_directory = attempt.native.kernel.CreateDirectoryW
    directory_calls = []

    def observed_create_directory(path, security):
        result = create_directory(path, security)
        error = ctypes.get_last_error() if not result else None
        directory_calls.append((path, bool(result), error))
        return result

    monkeypatch.setattr(attempt.native.kernel, "CreateDirectoryW", observed_create_directory)
    try:
        try:
            attempt.create()
        except PinFailure as error:
            pytest.fail(f"OwnedAttempt.create: {error.code}; CreateDirectoryW={directory_calls!r}")
        (attempt.path / "src/Module.bsl").write_bytes(
            b"Procedure Demo()\r\nEndProcedure\r\n"
        )
        (attempt.path / "report/result.json").write_bytes(b"{}\n")
        attempt.capture_cleanup_inventory()
        ops.refresh = "write"
        attempt.cleanup()
        assert not attempt.path.exists()
        assert not attempt.native.uncertain
    finally:
        pins.close()
    assert not ops.paths
