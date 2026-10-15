"""Actual POSIX source IO; no capture dispatch, candidate writes or Win32 facade."""
from dataclasses import replace
import errno
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
from threading import Thread
from types import SimpleNamespace

import pytest

from rentgen_core import _posix_live_tree as backend
from rentgen_core import _posix_source_tree as retained
from rentgen_core.capture import _inventory, _pass
from rentgen_core.errors import CoreError
from rentgen_core.source_configuration import SourceConfiguration, SourceLayerSpec

pytestmark = pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="Actual POSIX live tree IO")
MODULE = "CommonModules/Пример/Ext/Module.bsl"


@pytest.fixture
def live(tmp_path):
    root = tmp_path.resolve()
    source, state = root / "source", root / "state"
    source.mkdir(mode=0o755); state.mkdir(mode=0o755)
    contents = {MODULE: "Функция Значение() Экспорт\r\nВозврат 1;\r\nКонецФункции\r\n".encode(),
                "binary.bin": b"\0\xff\xfe", "zero": b""}
    for name, raw in contents.items():
        leaf = source / name; leaf.parent.mkdir(parents=True, exist_ok=True)
        leaf.write_bytes(raw); leaf.chmod(0o644)
    (source / "Empty/Nested").mkdir(parents=True)
    configuration = SourceConfiguration(1, (SourceLayerSpec("base", 0, "base", ".", "unknown"),))
    return SimpleNamespace(root=root, source=source, state=state, contents=contents,
                           configuration=configuration, limits=backend.PosixLiveLimits())


def opened(live, **changes):
    return backend.PosixLiveTree(live.source, live.state, **(dict(limits=live.limits, authorize_read=lambda: None) | changes))


def inventory(tree, live):
    exclusions = tree.configure(live.configuration)
    return exclusions, tree.inventory(live.configuration, exclusions)


def leaf(items):
    return next(item for item in items if item.relative_path == MODULE)


def read(tree, item):
    with tree.read(item) as chunks: return b"".join(chunks)


def held(tree):
    caps = [*tree._directories.values(), tree._state]
    fds = {entry[0] for cap in caps for entry in cap._chain}
    streams = [row[0] for row in tree._leaves.values()]
    fds.update(stream.fileno() for stream in streams)
    return caps, fds, streams


def closed(tree, resources):
    caps, fds, streams = resources
    assert tree._phase == "closed" and not tree._directories and not tree._leaves
    assert tree._authorize is tree._baseline is tree._active_read is tree._stack is None
    assert all(cap._closed for cap in caps) and all(stream.closed for stream in streams)
    for fd in fds:
        with pytest.raises(OSError) as error: os.fstat(fd)
        assert error.value.errno == errno.EBADF


def test_real_configure_two_content_passes_final_inventory_match_existing_data_loops(live, monkeypatch):
    calls = []; pread = os.pread
    def observed(fd, size, offset):
        calls.append((fd, size, offset))
        return pread(fd, size, offset)
    monkeypatch.setattr(os, "pread", observed)
    with opened(live) as tree:
        exclusions = tree.configure(live.configuration)
        first = _inventory(tree, live.configuration, exclusions)
        assert {item.relative_path for item in first if item.stamp.directory} >= {"", "Empty", "Empty/Nested"}
        assert [item.relative_path for item in first] == sorted((item.relative_path for item in first), key=lambda path: path.encode())
        assert type(leaf(first).stamp) is backend.PosixStamp and not hasattr(leaf(first).stamp, "attributes")
        one = _pass(tree, first)
        second = _inventory(tree, live.configuration, exclusions)
        assert first == second and _pass(tree, second) == one
        assert _inventory(tree, live.configuration, exclusions) == second
        assert {entry.relative_path for entry in one} == set(live.contents)
        assert next(entry for entry in one if entry.relative_path == MODULE).encoding == "utf-8"
        assert next(entry for entry in one if entry.relative_path == "binary.bin").encoding is None
        resources = held(tree)
    assert len(calls) == 2 * len(live.contents) and all(offset == 0 for _, _, offset in calls)
    closed(tree, resources)


def test_reads_use_held_leaf_fd_and_never_reopen_content_path(live, monkeypatch):
    with opened(live) as tree:
        _, items = inventory(tree, live); item = leaf(items); resources = held(tree)
        monkeypatch.setattr(retained.Directory, "file", lambda *a, **k: pytest.fail("Content pathname reopened"))
        monkeypatch.setattr(os, "open", lambda *a, **k: pytest.fail("Content descriptor reopened"))
        assert read(tree, item) == live.contents[MODULE]
        assert read(tree, item) == live.contents[MODULE]
    closed(tree, resources)


def test_state_exclusion_is_exact_and_its_contents_are_never_read(live):
    state = live.source / "nested/.state"; state.mkdir(parents=True)
    (state / "secret").symlink_to(live.root / "absent")
    live.state = state
    with opened(live) as tree:
        exclusions, items = inventory(tree, live)
        assert exclusions == (("base", "nested/.state"),)
        assert "nested" in {item.relative_path for item in items}
        assert not any(".state" in item.relative_path for item in items)
        # Mutable excluded state may change between source passes.
        (state / "new-staging").mkdir()
        assert tree.inventory(live.configuration, exclusions) == items


def test_nonoverlapping_layers_are_bound_and_ordered_independently(live):
    for name in ("base-root", "ext-root"):
        (live.source / name).mkdir(); (live.source / name / "Module.bsl").write_bytes(name.encode())
    live.configuration = SourceConfiguration(2, (SourceLayerSpec("main", 0, "base", "base-root", "unknown"),
                                                 SourceLayerSpec("extra", 1, "extension", "ext-root", "unknown")))
    with opened(live) as tree:
        exclusions, items = inventory(tree, live)
        assert [(item.layer_id, item.relative_path) for item in items] == [("main", ""), ("main", "Module.bsl"), ("extra", ""), ("extra", "Module.bsl")]
        assert [read(tree, item) for item in items if not item.stamp.directory] == [b"base-root", b"ext-root"]
        assert not exclusions


@pytest.mark.parametrize("change", ["configuration", "missing", "invented"])
def test_inventory_cannot_change_configuration_or_exclusions(live, change):
    live.state = live.source / ".state"; live.state.mkdir()
    with opened(live) as tree:
        exclusions = tree.configure(live.configuration)
        configuration = replace(live.configuration, revision=2) if change == "configuration" else live.configuration
        if change == "missing": exclusions = ()
        elif change == "invented": exclusions = (("base", "CommonModules"),)
        with pytest.raises(CoreError) as error: tree.inventory(configuration, exclusions)
        assert error.value.code == "SOURCE_CONFIGURATION_CONFLICT" and tree._phase == "closed"


@pytest.mark.parametrize("root", ["source", "layer", "state"])
def test_root_layer_and_excluded_state_swaps_refuse_before_foreign_read(live, root):
    if root == "layer":
        (live.source / "layer").mkdir(); (live.source / "layer/Module.bsl").write_bytes(b"selected")
        live.configuration = SourceConfiguration(1, (SourceLayerSpec("base", 0, "base", "layer", "unknown"),))
    tree = opened(live)
    with pytest.raises((CoreError, OSError)):
        with tree:
            exclusions = tree.configure(live.configuration); resources = held(tree)
            target = {"source": live.source, "layer": live.source / "layer", "state": live.state}[root]
            target.rename(target.with_name(target.name + "-moved"))
            target.mkdir(); (target / "foreign").write_bytes(b"foreign")
            tree.inventory(live.configuration, exclusions)
    closed(tree, resources)


@pytest.mark.parametrize("relationship", ["equal", "source-inside-state", "layer-inside-state"])
def test_source_or_layer_inside_state_is_invalid(live, relationship):
    if relationship == "equal": live.state = live.source
    elif relationship == "source-inside-state": live.state = live.root
    else:
        live.state = live.source / "private"; live.state.mkdir()
        live.configuration = SourceConfiguration(1, (SourceLayerSpec("base", 0, "base", "private", "unknown"),))
    with pytest.raises(CoreError) as error:
        with opened(live) as tree: tree.configure(live.configuration)
    assert error.value.code == "SOURCE_LAYER_INVALID"


@pytest.mark.parametrize("alias", ["state", "layer"])
def test_native_case_alias_cannot_silently_miss_exclusion_or_layer_spelling(live, alias):
    actual = live.source / "mixed"; actual.mkdir()
    alternate = live.source / "MIXED"
    if not alternate.exists() or alternate.stat().st_ino != actual.stat().st_ino:
        pytest.skip("Actual filesystem does not provide this case alias")
    if alias == "state": live.state = alternate
    else: live.configuration = SourceConfiguration(1, (SourceLayerSpec("base", 0, "base", "MIXED", "unknown"),))
    with pytest.raises(CoreError) as error:
        with opened(live) as tree: tree.configure(live.configuration)
    assert error.value.code == "SOURCE_LAYER_INVALID"


@pytest.mark.parametrize("kind", ["symlink", "directory-link", "hardlink", "fifo", "socket", "invalid-name"])
def test_real_links_special_objects_and_nonportable_names_are_refused(live, kind, monkeypatch):
    target = live.source / "unsafe"; connection = None
    try:
        if kind == "symlink": target.symlink_to(live.source / MODULE)
        elif kind == "directory-link": target.symlink_to(live.source / "Empty", target_is_directory=True)
        elif kind == "hardlink": os.link(live.source / MODULE, target)
        elif kind == "fifo": os.mkfifo(target)
        elif kind == "socket":
            connection = socket.socket(socket.AF_UNIX)
            # sun_path is short even when pytest's native temporary path is long.
            with monkeypatch.context() as patch:
                patch.chdir(live.source)
                connection.bind(target.name)
        else: (live.source / "bad:name").write_bytes(b"invalid")
        with pytest.raises((CoreError, OSError)):
            with opened(live) as tree: inventory(tree, live)
    finally:
        if connection is not None: connection.close()


@pytest.mark.parametrize("names", [("A", "a"), ("\u00e9", "e\u0301")])
def test_native_case_and_unicode_inventory_collisions_are_rejected(live, names):
    directory = live.source / "collisions"; directory.mkdir()
    for name in names: (directory / name).write_bytes(b"data")
    if len(list(directory.iterdir())) != 2:
        pytest.skip("Actual filesystem coalesces these colliding names")
    with pytest.raises(CoreError) as error:
        with opened(live) as tree: inventory(tree, live)
    assert error.value.code == "SOURCE_PATH_COLLISION"


@pytest.mark.parametrize("change", ["content", "leaf-replace", "delete", "new-file", "empty-dir-delete", "new-empty-dir"])
def test_second_inventory_refuses_observed_changes_between_passes(live, change):
    tree = opened(live)
    with pytest.raises((CoreError, OSError)):
        with tree:
            exclusions, items = inventory(tree, live); resources = held(tree)
            assert _pass(tree, items)
            target = live.source / MODULE
            if change == "content": target.write_bytes(b"x" * target.stat().st_size)
            elif change == "leaf-replace": target.unlink(); target.write_bytes(live.contents[MODULE])
            elif change == "delete": target.unlink()
            elif change == "new-file": (live.source / "new").write_bytes(b"new")
            elif change == "empty-dir-delete": (live.source / "Empty/Nested").rmdir()
            else: (live.source / "another-empty").mkdir()
            tree.inventory(live.configuration, exclusions)
    closed(tree, resources)


def test_native_second_pass_refuses_changed_held_file_and_does_not_reopen_replacement(live, monkeypatch):
    pread = os.pread; calls = []
    def observed(fd, size, offset):
        value = pread(fd, size, offset); calls.append(value); return value
    monkeypatch.setattr(os, "pread", observed)
    tree = opened(live)
    with pytest.raises(CoreError):
        with tree:
            _, items = inventory(tree, live); item = leaf(items)
            assert read(tree, item) == live.contents[MODULE]
            (live.source / MODULE).write_bytes(b"x" * len(live.contents[MODULE]))
            assert pread(tree._leaves[item.layer_id, item.relative_path][0].fileno(), item.stamp.size, 0) != calls[0]
            read(tree, item)
    assert calls == [live.contents[MODULE]]  # Real stamp refusal precedes second copy.


def test_mutation_after_copy_before_iterator_disclosure_fails(live):
    armed = [False]
    def authorize():
        context = tree._active_read
        if armed[0] and context is not None and context._raw is not None:
            armed[0] = False
            (live.source / MODULE).write_bytes(b"x" * len(live.contents[MODULE]))
    tree = opened(live, authorize_read=authorize)
    with tree:
        _, items = inventory(tree, live); resources = held(tree); armed[0] = True
        with pytest.raises(CoreError): read(tree, leaf(items))
        closed(tree, resources)


def test_delayed_iterator_refuses_real_change_after_read_context_entry(live):
    with opened(live) as tree:
        _, items = inventory(tree, live); resources = held(tree)
        with tree.read(leaf(items)) as chunks:
            assert chunks._raw == live.contents[MODULE]
            (live.source / MODULE).write_bytes(b"x" * len(live.contents[MODULE]))
            with pytest.raises(CoreError): next(chunks)
            assert chunks._raw is None
            closed(tree, resources)


@pytest.mark.parametrize("field,value", [("max_file_bytes", 1), ("max_total_bytes", 1), ("max_entries", 1),
                                         ("max_relative_components", 1), ("max_retained_descriptors", 1)])
def test_inventory_bounds_refuse_without_leaking_partial_entry(live, field, value):
    tree = opened(live, limits=replace(live.limits, **{field: value}))
    with pytest.raises(CoreError):
        with tree: inventory(tree, live)
    assert tree._phase == "closed" and not tree._leaves and not tree._directories


@pytest.mark.parametrize("limit", ["max_reads_per_file", "max_read_bytes", "max_inventory_passes"])
def test_read_and_inventory_attempts_have_finite_lifetime_bounds(live, limit):
    value = 1 if limit != "max_read_bytes" else len(live.contents[MODULE]) - 1
    with opened(live, limits=replace(live.limits, **{limit: value})) as tree:
        exclusions, items = inventory(tree, live)
        with pytest.raises(CoreError) as error:
            if limit == "max_inventory_passes": tree.inventory(live.configuration, exclusions)
            elif limit == "max_read_bytes": read(tree, leaf(items))
            else: read(tree, leaf(items)); read(tree, leaf(items))
        assert error.value.code == "SOURCE_CAPTURE_LIMIT_EXCEEDED" and tree._phase == "closed"


@pytest.mark.parametrize("invalid", [None, "equal", "directory"])
def test_only_exact_producing_owner_item_is_read_capability(live, invalid):
    with opened(live) as tree:
        _, items = inventory(tree, live)
        item = None if invalid is None else replace(leaf(items)) if invalid == "equal" else items[0]
        with pytest.raises(CoreError) as error: read(tree, item)
        assert error.value.code == "SOURCE_REF_MISMATCH" and tree._phase == "closed"


def test_item_from_another_live_owner_is_not_a_capability(live):
    with opened(live) as first, opened(live) as second:
        _, one = inventory(first, live); _, two = inventory(second, live)
        assert one == two
        with pytest.raises(CoreError, match="exact held"): read(first, leaf(two))
        assert read(second, leaf(two)) == live.contents[MODULE]


@pytest.mark.parametrize("failure", [False, True])
def test_owner_outer_exit_closes_abandoned_read_without_masking_body_error(live, failure):
    tree = opened(live); sentinel = ValueError("body failed"); caught = False
    try:
        with tree:
            _, items = inventory(tree, live); resources = held(tree)
            context = tree.read(leaf(items)); context.__enter__()
            assert context._raw == live.contents[MODULE]
            if failure: raise sentinel
    except ValueError as error:
        caught = True
        assert failure and error is sentinel
    assert caught is failure
    assert context._raw is None and context._phase == "closed"
    closed(tree, resources)
    assert context.__exit__(None, None, None) is False


def test_foreign_thread_cannot_query_consume_read_or_close_either_context(live):
    with opened(live) as tree:
        exclusions, items = inventory(tree, live); resources = held(tree)
        with tree.read(leaf(items)) as chunks:
            errors = []
            def foreign():
                operations = [lambda: tree.inventory(live.configuration, exclusions), lambda: next(chunks),
                              lambda: chunks.__exit__(None, None, None), lambda: tree.__exit__(None, None, None)]
                for operation in operations:
                    try: operation()
                    except CoreError as error: errors.append(error.code)
            thread = Thread(target=foreign); thread.start(); thread.join(timeout=5)
            assert not thread.is_alive() and errors == ["SOURCE_READ_SESSION_INVALID"] * 4
            assert b"".join(chunks) == live.contents[MODULE]
    closed(tree, resources)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="Actual POSIX fork ownership guard")
def test_forked_child_cannot_consume_read_or_parent_context(live):
    with opened(live) as tree:
        _, items = inventory(tree, live); resources = held(tree)
        with tree.read(leaf(items)) as chunks:
            read_fd, write_fd = os.pipe(); pid = os.fork()
            if pid == 0:
                os.close(read_fd); results = []
                for operation in (lambda: next(chunks), lambda: chunks.__exit__(None, None, None), lambda: tree.__exit__(None, None, None)):
                    try: operation(); results.append("unexpected success")
                    except CoreError as error: results.append(error.code)
                os.write(write_fd, ",".join(results).encode()); os.close(write_fd); os._exit(0)
            os.close(write_fd)
            try: result = os.read(read_fd, 256)
            finally: os.close(read_fd); status = os.waitpid(pid, 0)[1]
            assert status == 0 and result == b"SOURCE_READ_SESSION_INVALID,SOURCE_READ_SESSION_INVALID,SOURCE_READ_SESSION_INVALID"
            assert b"".join(chunks) == live.contents[MODULE]
    closed(tree, resources)


@pytest.mark.parametrize("phase", ["inventory", "read-enter", "iterator", "read-exit", "tree-exit"])
def test_public_reentrant_exits_cannot_consume_contexts(live, phase):
    armed = [False]; errors = []
    def authorize():
        if armed[0]:
            operations = [lambda: tree.__exit__(None, None, None)]
            if tree._active_read is not None:
                operations.extend([lambda: tree._active_read.__exit__(None, None, None), lambda: next(tree._active_read)])
            for operation in operations:
                with pytest.raises(CoreError) as error: operation()
                assert error.value.code == "SOURCE_READ_SESSION_INVALID"
                errors.append(error.value)
    tree = opened(live, authorize_read=authorize)
    with tree:
        exclusions, items = inventory(tree, live); resources = held(tree)
        armed[0] = phase == "inventory"
        tree.inventory(live.configuration, exclusions)
        armed[0] = phase == "read-enter"
        context = tree.read(leaf(items)); context.__enter__()
        armed[0] = phase == "iterator"
        assert b"".join(context) == live.contents[MODULE]
        armed[0] = phase == "read-exit"
        context.__exit__(None, None, None)
        armed[0] = phase == "tree-exit"
    assert errors
    closed(tree, resources)


def test_outer_exit_with_idle_read_refuses_callback_reentry_before_teardown(live):
    armed = [False]; refusals = []
    def authorize():
        if armed[0]:
            for operation in (lambda: next(context), lambda: context.__exit__(None, None, None),
                              lambda: tree.inventory(live.configuration, exclusions)):
                with pytest.raises(CoreError) as error: operation()
                assert error.value.code == "SOURCE_READ_SESSION_INVALID"
                refusals.append(error.value)
    tree = opened(live, authorize_read=authorize)
    with tree:
        exclusions, items = inventory(tree, live); resources = held(tree)
        context = tree.read(leaf(items)); context.__enter__(); armed[0] = True
    assert refusals and context._raw is None
    closed(tree, resources)


@pytest.mark.parametrize("phase", ["entry", "configure", "inventory", "copy", "iterator", "exit"])
def test_cooperative_deadline_covers_entry_through_disclosure_and_exit(live, monkeypatch, phase):
    now = [100]; monkeypatch.setattr(backend, "monotonic", lambda: now[0])
    def authorize():
        if phase == "entry": now[0] += 30
    tree = opened(live, authorize_read=authorize)
    with pytest.raises(CoreError) as error:
        with tree:
            if phase == "configure": now[0] += 30
            exclusions = tree.configure(live.configuration)
            if phase == "inventory": now[0] += 30
            items = tree.inventory(live.configuration, exclusions)
            if phase == "copy": now[0] += 30
            with tree.read(leaf(items)) as chunks:
                if phase == "iterator": now[0] += 30
                b"".join(chunks)
            now[0] += 30
    assert error.value.code == "SOURCE_READ_DEADLINE_EXCEEDED" and tree._phase == "closed"


def test_original_callback_denial_and_cause_survive_namespace_cleanup_failure(live):
    armed = [False]; denial = CoreError("PROJECT_FORBIDDEN", "Trusted callback denial"); cause = ValueError("original cause")
    def authorize():
        if armed[0]:
            live.source.rename(live.root / "moved")
            raise denial from cause
    with opened(live, authorize_read=authorize) as tree:
        _, items = inventory(tree, live); resources = held(tree); armed[0] = True
        with pytest.raises(CoreError) as error: read(tree, leaf(items))
        assert error.value is denial and error.value.__cause__ is cause
        closed(tree, resources)


def test_denial_after_copy_before_iterator_disclosure_clears_owned_image(live):
    armed = [False]; denial = CoreError("PROJECT_FORBIDDEN", "Revoked before iterator disclosure")
    def authorize():
        if armed[0]: raise denial
    with opened(live, authorize_read=authorize) as tree:
        _, items = inventory(tree, live); resources = held(tree)
        with tree.read(leaf(items)) as chunks:
            assert chunks._raw == live.contents[MODULE]
            armed[0] = True
            with pytest.raises(CoreError) as error: next(chunks)
            assert error.value is denial and chunks._raw is None
            closed(tree, resources)


def test_first_inventory_rechecks_names_after_pinning_some_leaves(live):
    armed = [True]
    def authorize():
        if armed[0] and tree._leaves:
            armed[0] = False
            (live.source / "late-empty-directory").mkdir()
    tree = opened(live, authorize_read=authorize)
    with pytest.raises(CoreError, match="names changed"):
        with tree:
            inventory(tree, live)
    assert tree._phase == "closed" and not tree._leaves


def test_partial_layer_configuration_failure_closes_every_actual_opened_fd(live, monkeypatch):
    (live.source / "real-layer").mkdir()
    live.configuration = SourceConfiguration(1, (SourceLayerSpec("base", 0, "base", "real-layer", "unknown"),
                                                 SourceLayerSpec("ext", 1, "extension", "missing-layer", "unknown")))
    original = os.open; fds = []
    def tracked(*args, **kwargs):
        fd = original(*args, **kwargs); fds.append(fd); return fd
    monkeypatch.setattr(os, "open", tracked)
    with pytest.raises(CoreError, match="alias"):
        with opened(live) as tree: tree.configure(live.configuration)
    assert fds
    for fd in fds:
        with pytest.raises(OSError) as error: os.fstat(fd)
        assert error.value.errno == errno.EBADF


def test_real_close_ack_failure_cannot_report_success_or_retry_fd(live, monkeypatch):
    original = os.close; attempts = []; tree = opened(live)
    with pytest.raises(CoreError, match="cleanup"):
        with tree:
            inventory(tree, live); resources = held(tree); target = next(iter(tree._leaves.values()))[0].fileno()
            def lost(fd):
                original(fd)
                if fd == target:
                    attempts.append(fd)
                    raise OSError(errno.EIO, "lost close acknowledgement")
            monkeypatch.setattr(os, "close", lost)
    assert attempts == [target]
    closed(tree, resources)


@pytest.mark.parametrize("field,value", [("max_file_bytes", True), ("deadline_seconds", 31), ("max_reads_per_file", 3), ("max_inventory_passes", 4)])
def test_typed_limits_do_not_expand_existing_maxima(field, value):
    with pytest.raises(CoreError): replace(backend.PosixLiveLimits(), **{field: value})


@pytest.mark.skipif(sys.platform != "linux", reason="Actual Linux /proc nested-device boundary")
def test_linux_nested_device_is_refused_without_reading_proc_content(live):
    if os.stat("/proc").st_dev == os.stat("/").st_dev:
        pytest.skip("Actual /proc is not a separate device")
    tree = backend.PosixLiveTree(Path("/"), live.state, limits=live.limits, authorize_read=lambda: None)
    with pytest.raises(CoreError):
        with tree: tree._call(lambda: tree._directory("proc"))
    assert tree._phase == "closed"
