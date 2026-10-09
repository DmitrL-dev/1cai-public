"""Pure synthetic interpretation regressions; no native or tracing execution."""
import json
import ntpath
from pathlib import Path, PurePosixPath, PureWindowsPath
import posixpath
from types import FunctionType, SimpleNamespace

import pytest
import yaml

import test_source_fact_lifecycle_completion as audit


ENOENT = "-1 ENOENT (No such file or directory)"
PRELOAD_PROBE = 'access("/etc/ld.so.preload", R_OK) = ' + ENOENT


def trace(*events):
    return "\n".join(f"{pid} 1000.{index:06d} {body}"
                     for index, (pid, body) in enumerate(events)) + "\n"


def synthetic_pipeline(*extra):
    """Enough explicit owned operations to exercise the complete interpreter."""
    config = {"state": "/synthetic/state.sqlite3", "case": {"archive": "/synthetic/input.zip"},
              "images": {role: "/synthetic/" + role for role in
                         ("input_core", "source_scanner", "source_kernel")},
              "runtime_roots": ["/synthetic/runtime"]}
    events = []
    def marker(value):
        value = "RENTGEN_P_TRACE:" + value + "\n"
        events.append((1, f"write(4<pipe:[1]>, {json.dumps(value)}, {len(value)}) = {len(value)}"))
    marker("S")
    for child, (role, path) in enumerate(config["images"].items(), 2):
        events.append((1, f'openat(AT_FDCWD</synthetic>, "{path}", O_RDONLY|O_CLOEXEC) = 5<{path}>'))
        marker("L:" + role)
        events.extend([
            (1, 'memfd_create("rentgen-input-core", MFD_CLOEXEC|MFD_ALLOW_SEALING) = 6</memfd:rentgen-input-core>(deleted)'),
            (1, f"clone(child_stack=NULL, flags=SIGCHLD) = {child}"),
            (child, 'execve("/proc/self/fd/6", ["/proc/self/fd/6"], 0x123 /* 3 vars */) = 0'),
        ])
        if role == "input_core":
            events.append((child, 'openat(AT_FDCWD</synthetic>, "/synthetic/input.zip", O_RDONLY) = 7</synthetic/input.zip>'))
            marker("A")
    events.extend(extra)
    marker("E")
    return trace(*events), config


@pytest.fixture(params=["posix", "windows"])
def path_auditor(request):
    """Exercise host path flavors without changing os or pathlib globally."""
    path_type = PureWindowsPath if request.param == "windows" else PurePosixPath
    path_module = ntpath if request.param == "windows" else posixpath
    namespace = dict(vars(audit), Path=path_type, ROOT=path_type("/synthetic/checkout"),
                     os=SimpleNamespace(path=path_module))
    for name in ("traced_path", "inspect_trace"):
        namespace[name] = FunctionType(getattr(audit, name).__code__, namespace, name)
    return SimpleNamespace(**namespace)


@pytest.mark.parametrize("name,args,expected", [
    ("open", '"/synthetic/../synthetic/input_core", O_RDONLY', "/synthetic/input_core"),
    ("openat", '3</synthetic/nested>, "../input_core", O_RDONLY', "/synthetic/input_core"),
    ("openat", 'AT_FDCWD</synthetic>, "input_core", O_RDONLY', "/synthetic/input_core"),
    ("open", '"../input_core", O_RDONLY', "/synthetic/input_core"),
    ("openat", 'AT_FDCWD, "../input_core", O_RDONLY', "/synthetic/input_core"),
    ("statx", '3</synthetic/input_core>, "", AT_EMPTY_PATH, STATX_ALL, 0x123', "/synthetic/input_core"),
    ("open", json.dumps("/synthetic/runtime\\outside.py") + ", O_RDONLY", "/synthetic/runtime\\outside.py"),
    ("openat", '3</synthetic>, ' + json.dumps("nested\\input_core") + ", O_RDONLY", "/synthetic/nested\\input_core"),
    ("openat", '3</synthetic>, "C:input_core", O_RDONLY', "/synthetic/C:input_core"),
])
def test_traced_paths_use_linux_semantics_on_either_host(path_auditor, name, args, expected):
    assert path_auditor.traced_path({"name": name, "args": args}) == expected


@pytest.mark.parametrize("path,flags,allowed", [
    ("/synthetic", "O_RDONLY|O_DIRECTORY", True),
    ("/synthetic/runtime", "O_RDONLY|O_DIRECTORY", True),
    ("/synthetic/runtime/module.py", "O_RDONLY", True),
    ("/synthetic/runtime/module.pyc", "O_RDONLY", True),
    ("/synthetic/runtime/module.so", "O_RDONLY", True),
    ("/synthetic/runtime/lib.so.6", "O_RDONLY", True),
    ("/lib/x86_64-linux-gnu/libc.so.6", "O_RDONLY", True),
    ("/synthetic", "O_RDONLY", False),
    ("/synthetic/runtime", "O_RDONLY", False),
    ("/synthetic/runtime/module.txt", "O_RDONLY", False),
    ("/synthetic/runtime_other/module.py", "O_RDONLY", False),
    ("/synthetic/RUNTIME/module.py", "O_RDONLY", False),
    ("/synthetic/runtime\\outside.py", "O_RDONLY", False),
])
def test_linux_path_authority_is_host_independent(path_auditor, path, flags, allowed):
    raw, config = synthetic_pipeline((2, f"open({json.dumps(path)}, {flags}) = 9<{path}>"))
    if not allowed:
        with pytest.raises(AssertionError, match="Outside explicit authority") as error:
            path_auditor.inspect_trace(raw, config)
        assert str(error.value).startswith(f"('Outside explicit authority', {path!r}, ")
        return
    facts = path_auditor.inspect_trace(raw, config)
    assert facts["opens"][-1]["path"] == path
    assert facts["execs"] == [{"pid": pid, "path": "/proc/self/fd/6"} for pid in (2, 3, 4)]
    assert facts["runtime_reads"] == ([] if "O_DIRECTORY" in flags else [path])


def test_absent_loader_probe_is_metadata_only_in_complete_interpretation():
    raw, config = synthetic_pipeline((2, PRELOAD_PROBE))
    facts = audit.inspect_trace(raw, config)
    assert len(facts["absent_loader_probes"]) == 1
    probe, = facts["absent_loader_probes"]
    assert (probe["pid"], probe["name"], probe["args"], probe["result"]) == (
        2, "access", '"/etc/ld.so.preload", R_OK', ENOENT)
    assert "/etc/ld.so.preload" not in facts["runtime_reads"]
    assert "/etc/ld.so.preload" not in facts["trusted_system_allowances"]
    assert all(item["path"] != "/etc/ld.so.preload" for item in facts["opens"])


def test_split_absent_loader_probe_requires_exact_completed_result():
    raw, config = synthetic_pipeline(
        (2, 'access("/etc/ld.so.preload", R_OK <unfinished ...>'),
        (1, "getpid() = 1"),
        (2, "<... access resumed>) = " + ENOENT))
    facts = audit.inspect_trace(raw, config)
    assert len(facts["absent_loader_probes"]) == 1


@pytest.mark.parametrize("body", [
    'access("/etc/ld.so.preload", R_OK) = 0',
    'access("/etc/ld.so.preload", R_OK) = -1 EACCES (Permission denied)',
    'access("/etc/ld.so.preload", R_OK) = -1 ENOTDIR (Not a directory)',
    'access("/etc/ld.so.preload", R_OK) = ?',
    'access("/etc/ld.so.preload", R_OK) = -1 ENOENT',
    'access("/etc/ld.so.preload", F_OK) = ' + ENOENT,
    'access("/etc/ld.so.preload", R_OK|W_OK) = ' + ENOENT,
    'access("/etc/../etc/ld.so.preload", R_OK) = ' + ENOENT,
    'access("/etc/ld.so.preload.extra", R_OK) = ' + ENOENT,
    'access("/etc/ld.so.conf", R_OK) = ' + ENOENT,
    'access("/unrelated/missing", R_OK) = ' + ENOENT,
    'open("/etc/ld.so.preload", O_RDONLY) = 3</etc/ld.so.preload>',
    'open("/etc/ld.so.preload", O_RDONLY) = ' + ENOENT,
    'openat(AT_FDCWD</synthetic>, "/etc/ld.so.preload", O_RDONLY) = ' + ENOENT,
    'faccessat(AT_FDCWD</synthetic>, "/etc/ld.so.preload", R_OK) = ' + ENOENT,
    'newfstatat(AT_FDCWD</synthetic>, "/etc/ld.so.preload", 0x123, 0) = ' + ENOENT,
    'readlink("/etc/ld.so.preload", 0x123, 4096) = ' + ENOENT,
])
def test_absent_loader_exception_does_not_authorize_other_operations(body):
    raw, config = synthetic_pipeline((2, body))
    with pytest.raises(AssertionError, match="Outside explicit authority"):
        audit.inspect_trace(raw, config)


def test_absent_probe_does_not_authorize_a_later_preload_open():
    raw, config = synthetic_pipeline((2, PRELOAD_PROBE),
        (2, 'open("/etc/ld.so.preload", O_RDONLY) = 3</etc/ld.so.preload>'))
    with pytest.raises(AssertionError, match="Outside explicit authority"):
        audit.inspect_trace(raw, config)


@pytest.mark.parametrize("events", [
    [(2, "???() = ?")],
    [(2, "???( <unfinished ...>"), (2, "<... ??? resumed>) = ?")],
    [(2, "<... ??? resumed>) = ?")],
    # This mirrors the retained Go sibling exit race. The exit cannot restore
    # the missing syscall identity/arguments, even with an explicit clone.
    [(2, "clone(child_stack=0x1000, flags=CLONE_VM|CLONE_SIGHAND|CLONE_THREAD) = 3"),
     (2, "exit_group(0 <unfinished ...>"), (3, "???( <unfinished ...>"),
     (3, "<... ??? resumed>) = ?"), (2, "<... exit_group resumed>) = ?"),
     (3, "+++ exited with 0 +++")],
])
def test_unknown_syscall_observations_remain_incomplete(events):
    with pytest.raises(AssertionError, match="Unresolved syscall observation"):
        audit.trace_calls(trace(*events))


@pytest.mark.parametrize("body", [
    "syscall_0x999(0, 0, 0) = -1 ENOSYS (Function not implemented)",
    'socket(AF_INET, SOCK_STREAM, 0) = -1 EACCES (Permission denied)',
    'io_uring_setup(1, 0x123) = -1 EPERM (Operation not permitted)',
])
def test_closed_syscall_inventory_still_rejects_unknown_or_forbidden(body):
    raw, config = synthetic_pipeline((2, body))
    with pytest.raises(AssertionError):
        audit.inspect_trace(raw, config)


@pytest.mark.parametrize("events", [
    [(2, 'access("/etc/ld.so.preload", R_OK <unfinished ...>')],
    [(2, 'access("/etc/ld.so.preload", R_OK <unfinished ...>'), (2, "+++ exited with 0 +++")],
    [(2, "exit_group(0 <unfinished ...>"), (2, "+++ exited with 0 +++")],
    [(2, '<... access resumed>) = ' + ENOENT)],
    [(2, 'access("/etc/ld.so.preload", R_OK <unfinished ...>'), (3, '<... access resumed>) = ' + ENOENT)],
    [(2, 'access("/etc/ld.so.preload", R_OK <unfinished ...>'), (2, '<... open resumed>) = ' + ENOENT)],
    [(2, 'access("/etc/ld.so.preload", R_OK <unfinished ...>'), (2, 'getpid( <unfinished ...>')],
])
def test_incomplete_or_mismatched_split_calls_remain_rejected(events):
    with pytest.raises(AssertionError):
        audit.trace_calls(trace(*events))


@pytest.mark.parametrize("body", [
    "open(0x7ffc609474d8, O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_DIRECTORY) = 3",
    "openat(3, 0x7ffc609474c0, O_RDONLY|O_NONBLOCK|O_NOFOLLOW|O_CLOEXEC) = 4",
    "statx(4, 0x5583c98f3962, AT_STATX_SYNC_AS_STAT|AT_EMPTY_PATH, STATX_ALL, 0x123) = 0",
])
def test_dumpability_does_not_authorize_opaque_pathnames(body):
    raw, config = synthetic_pipeline(
        (2, "prctl(PR_SET_DUMPABLE, SUID_DUMP_DISABLE) = 0"), (2, body))
    with pytest.raises(AssertionError, match="Missing decoded pathname"):
        audit.inspect_trace(raw, config)


def test_prior_owned_pipe_does_not_excuse_missing_write_descriptor():
    raw, config = synthetic_pipeline(
        (2, "dup2(20<pipe:[99]>, 1<pipe:[1]>) = 1<pipe:[99]>"),
        (2, "prctl(PR_SET_DUMPABLE, SUID_DUMP_DISABLE) = 0"),
        (2, "write(1, 0x5583eee5d500, 101) = 101"))
    with pytest.raises(AssertionError, match="Missing decoded descriptor"):
        audit.inspect_trace(raw, config)


def test_ci_retains_only_scoped_synthetic_audit_config():
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((root / ".github/workflows/source-facts-ci.yml").read_text())
    paths = [step["with"]["path"] for job in workflow["jobs"].values()
             for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")]
    config_paths = [line.strip() for block in paths for line in block.splitlines() if "config.json" in line]
    assert config_paths == ["${{ env.EVIDENCE }}/full176/tmp/pytest/**/syscall-evidence/config.json"]
    pure, = [step["run"] for job in workflow["jobs"].values() for step in job["steps"]
             if step.get("name") == "Pure host and delivery-verifier regressions"]
    assert "tests/unit/test_source_fact_syscall_audit_contract.py" in pure


def pipeline_events(raw):
    return [(int(line.split()[0]), line.split(None, 2)[2]) for line in raw.splitlines()]


@pytest.mark.parametrize("name,args,result", [
    ("openat", 'AT_FDCWD</synthetic>, "/outside/secret", O_RDONLY', "3</outside/secret>"),
    ("socket", "AF_INET, SOCK_STREAM, 0", "3<TCP:[123]>")
])
def test_syscall_entering_before_end_cannot_escape_by_completing_after_end(name, args, result):
    # Original failing negative: completion-order processing previously skipped
    # this outside-authority syscall after E and returned a successful audit.
    raw, config = synthetic_pipeline((2, f"{name}({args} <unfinished ...>"))
    events = pipeline_events(raw)
    events.append((2, f"<... {name} resumed>) = {result}"))
    with pytest.raises(AssertionError, match="Ambiguous trace boundary"):
        audit.inspect_trace(trace(*events), config)


@pytest.mark.parametrize("marker", ["S", "E", "L:input_core", "A", "L:source_scanner", "L:source_kernel"])
@pytest.mark.parametrize("name,args", [
    ("open", '"/outside/secret", O_RDONLY'),
    ("openat", 'AT_FDCWD</synthetic>, "/outside/secret", O_RDONLY'),
    ("openat2", 'AT_FDCWD</synthetic>, "/outside/secret", {flags=O_RDONLY}, 24'),
])
def test_locator_open_overlapping_each_authority_boundary_is_incomplete(marker, name, args):
    raw, config = synthetic_pipeline()
    events = pipeline_events(raw)
    index, = [index for index, (_, body) in enumerate(events) if f'"RENTGEN_P_TRACE:{marker}\\n"' in body]
    events[index:index + 1] = [(99, f"{name}({args} <unfinished ...>"), events[index],
                              (99, f"<... {name} resumed>) = 3</outside/secret>")]
    with pytest.raises(AssertionError, match="Ambiguous trace boundary"):
        audit.inspect_trace(trace(*events), config)


@pytest.mark.parametrize("marker", ["S", "E", "L:input_core", "A", "L:source_scanner", "L:source_kernel"])
def test_completed_open_inside_split_marker_is_also_incomplete(marker):
    raw, config = synthetic_pipeline()
    events = pipeline_events(raw)
    index, = [index for index, (_, body) in enumerate(events) if f'"RENTGEN_P_TRACE:{marker}\\n"' in body]
    pid, body = events[index]; head, result = body.rsplit(") = ", 1)
    events[index:index + 1] = [(pid, head + " <unfinished ...>"),
                              (99, 'open("/outside/secret", O_RDONLY) = 3</outside/secret>'),
                              (pid, "<... write resumed>) = " + result)]
    with pytest.raises(AssertionError, match="Ambiguous trace boundary"):
        audit.inspect_trace(trace(*events), config)


@pytest.mark.parametrize("args", [
    '"/lib/x86_64-linux-gnu/libc.so.6", O_RDONLY',
    '"/synthetic", O_RDONLY|O_DIRECTORY',
    '0x7ffc609474d8, O_RDONLY|O_NOFOLLOW',
])
def test_admission_overlap_rejects_all_opens_without_guessing_the_path(args):
    events = [(2, f"open({args} <unfinished ...>"),
              (1, 'write(4<pipe:[1]>, "RENTGEN_P_TRACE:A\\n", 18) = 18'),
              (2, '<... open resumed>) = 3')]
    with pytest.raises(AssertionError, match="Ambiguous trace boundary"):
        audit.check_trace_boundaries(audit.trace_calls(trace(*events)))


@pytest.mark.parametrize("marker", ["S", "E"])
def test_even_known_pipe_read_must_not_cross_operation_boundary(marker):
    events = [(2, "read(0<pipe:[99]>,  <unfinished ...>"),
              (1, f'write(4<pipe:[1]>, "RENTGEN_P_TRACE:{marker}\\n", 18) = 18'),
              (2, '<... read resumed>"", 1) = 0')]
    with pytest.raises(AssertionError, match="Ambiguous trace boundary"):
        audit.check_trace_boundaries(audit.trace_calls(trace(*events)))


@pytest.mark.parametrize("marker", ["A", "L:input_core", "L:source_scanner", "L:source_kernel"])
def test_known_pipe_read_can_span_internal_locator_admission(marker):
    raw, config = synthetic_pipeline()
    events = pipeline_events(raw)
    index, = [index for index, (_, body) in enumerate(events) if f'"RENTGEN_P_TRACE:{marker}\\n"' in body]
    events[index:index + 1] = [(99, "read(0<pipe:[99]>,  <unfinished ...>"), events[index],
                              (99, '<... read resumed>"", 1) = 0')]
    assert audit.inspect_trace(trace(*events), config)["markers"][-1] == "E"


def test_split_calls_keep_entry_and_completion_lines_without_resorting():
    calls = audit.trace_calls(trace((2, "read(0<pipe:[99]>,  <unfinished ...>"),
                                    (1, "getpid() = 1"),
                                    (2, '<... read resumed>"", 1) = 0')))
    assert [(c["name"], c["start_line"], c["line"], c["stamp"]) for c in calls] == [
        ("getpid", 2, 2, 1000.000001), ("read", 1, 3, 1000.0)]


def test_nonoverlapping_calls_outside_operation_are_still_outside_scope():
    raw, config = synthetic_pipeline()
    outside = (99, 'open("/outside/secret", O_RDONLY) = 3</outside/secret>')
    assert audit.inspect_trace(trace(outside, *pipeline_events(raw), outside), config)["markers"][-1] == "E"


def test_complete_same_pid_call_cannot_leapfrog_an_unfinished_call():
    raw = trace((2, "read(0<pipe:[99]>,  <unfinished ...>"),
                (2, "getpid() = 2"), (2, '<... read resumed>"", 1) = 0'))
    with pytest.raises(AssertionError, match="Missing syscall resume"):
        audit.trace_calls(raw)


def test_malformed_unfinished_entry_is_rejected_before_pairing():
    with pytest.raises(AssertionError, match="Malformed syscall entry"):
        audit.trace_calls(trace((2, "not a syscall <unfinished ...>")))


@pytest.mark.parametrize("name,args", [
    ("clone", "child_stack=NULL, flags=CLONE_NEWUSER|SIGCHLD"),
    ("clone3", "{flags=CLONE_NEWUSER|CLONE_VM|CLONE_SIGHAND|CLONE_THREAD}, 88"),
    ("clone", "child_stack=NULL, flags=CLONE_NEWNET|SIGCHLD"),
])
def test_namespace_creation_cannot_reacquire_authority(name, args):
    raw, config = synthetic_pipeline((2, f"{name}({args}) = 9"))
    with pytest.raises(AssertionError, match="Namespace-creating clone"):
        audit.inspect_trace(raw, config)
