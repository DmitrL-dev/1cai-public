"""Test-only Linux containment and reviewed-pins qualification entry point.

This module is never imported by production. It signals only retained Popen
handles, the unreaped session leader it created, or kernel-listed direct children
of its own isolated subreaper. No system settings, external process, or process
name is used. No command from the pins manifest is executed.
"""
import argparse
import ast
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import socket
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

# Never let -O remove qualification or driver gates. This check is not assert.
if sys.flags.optimize != 0:
    raise RuntimeError("Optimized Python is forbidden for qualification")

PROTOCOL_HASH = "ae22acd2df04bfedb4070e3709ee1c0cd14cb80c2abb7da3084493977dad94dc"
ROLES = {"input_core", "source_scanner", "source_kernel"}
HARNESS = {"tests/fixtures/source_facts/boundary_supervisor.py",
           "tests/fixtures/source_facts/qualification_journal.py",
           "tests/fixtures/source_facts/owned_transport_probe.c",
           "tests/unit/test_source_fact_runtime_boundaries.py",
           "tests/unit/test_source_fact_lifecycle_completion.py",
           "tests/unit/test_source_fact_wire_receipt_gaps.py"}
SOURCE = Path(__file__).with_name("owned_transport_probe.c")
_CLEANUP_OWNER = None

# A reviewed harness wall allowance, never a product operation deadline. The
# former 240-second hosted attempts remain incomplete first-run evidence.
FULL_BUDGET_VERSION = "source-facts-176-v2"
FULL_WALL_SECONDS = 600
POLLING_BUDGET_VERSION = "source-facts-polling-v1"
POLLING_WALL_SECONDS = 240
FULL_COST_INVENTORY = {
    "deliberate_wait_seconds": {"transport_timeouts": 70, "whole_operation": 60,
                               "cleanup_confirmation": 9},
    "fresh_cli_bootstrap_processes": 171,
    "syscall_audit_controls": {"count": 2, "outer_seconds_each": 34},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_pins(path, expected, root):
    """The caller supplies the separately reviewed manifest's independent hash."""
    assert re.fullmatch(r"[0-9a-f]{64}", expected or ""), "Missing reviewed pins hash"
    raw_pins = Path(path).read_bytes()
    assert hashlib.sha256(raw_pins).hexdigest() == expected, "Pins manifest changed"
    pins = json.loads(raw_pins)
    assert Path(__file__).resolve() == (root / "tests/fixtures/source_facts/boundary_supervisor.py").resolve(), "Wrong executing supervisor"
    assert pins["schema"] == 1 and pins["protocol_sha256"] == PROTOCOL_HASH
    assert sha(root / "docs/product/SOURCE-FACTS-PROTOCOL.md") == PROTOCOL_HASH
    git = ["/usr/bin/git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false"]
    git_env = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_OPTIONAL_LOCKS": "0"}
    commit = subprocess.check_output([*git, "rev-parse", "HEAD"], cwd=root, env=git_env, timeout=3, text=True).strip()
    assert commit == pins["source_commit"], "Unreviewed candidate commit"
    status = subprocess.check_output([*git, "status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching"],
                                     cwd=root, env=git_env, timeout=3, text=True)
    assert not status, "Qualification requires a completely clean reviewed checkout"
    assert set(pins["images"]) == ROLES
    for label, item in {**pins["images"], "probe": pins["probe"]}.items():
        assert Path(item["path"]).is_absolute(), label
        assert re.fullmatch(r"[0-9a-f]{64}", item["sha256"]), label
        assert sha(item["path"]) == item["sha256"], "Unreviewed image: " + label
        assert isinstance(item["build_command"], list) and item["build_command"]
        assert all(isinstance(v, str) and v for v in item["build_command"])
        assert isinstance(item["compiler_identity"], str) and item["compiler_identity"]
    assert pins["probe"]["source_sha256"] == sha(SOURCE), "Unreviewed probe source"
    assert set(pins["harness_sha256"]) == HARNESS
    for relative, expected_hash in pins["harness_sha256"].items():
        assert sha(root / relative) == expected_hash, "Unreviewed harness source"
    assert pins["expected_variants"] == 176, "Required denominator changed"
    if "trace_launcher" in pins:
        launcher = pins["trace_launcher"]
        assert launcher["contract"] == "owned_trace_cap_sys_ptrace_v1"
        assert Path(launcher["path"]).is_absolute()
        assert re.fullmatch(r"[0-9a-f]{64}", launcher["sha256"])
        assert sha(launcher["path"]) == launcher["sha256"], "Unreviewed trace capability launcher"
        assert launcher["source_sha256"] == sha(root / "tests/fixtures/source_facts/owned_trace_launcher.c")
    assert pins["strace"]["path"] == "/usr/bin/strace"
    assert re.fullmatch(r"[0-9a-f]{64}", pins["strace"]["sha256"])
    assert sha(pins["strace"]["path"]) == pins["strace"]["sha256"], "Unreviewed trace tool"
    return pins


def close_streams(child):
    errors = []
    for stream in (child.stdin, child.stdout, child.stderr):
        if stream is not None:
            try:
                stream.close()
            except BaseException as error:
                errors.append(type(error).__name__)
    return errors


def stop_owned(child, deadline):
    """Independent safety cleanup, never proof that production cleaned up."""
    errors = []; live = False
    try:
        try: live = child.poll() is None
        except BaseException as error: errors.append(type(error).__name__)
        if live:
            try: signal_owned(child.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            except BaseException as error: errors.append(type(error).__name__)
        try: child.wait(timeout=max(0.001, deadline - time.monotonic()))
        except BaseException as error: errors.append(type(error).__name__)
    finally:
        errors.extend(close_streams(child))
    return errors


def proc_identity(path):
    """Parse only kernel PID, PPID and start-time fields; never use comm as identity."""
    raw = Path(path).read_bytes()
    prefix, delimiter, suffix = raw.rpartition(b")")
    values = suffix.split()
    if not delimiter or b" (" not in prefix or len(values) <= 19:
        raise RuntimeError("Malformed procfs process identity")
    return int(prefix.split(b" ", 1)[0]), int(values[1]), int(values[19])


def verify_proc_namespace():
    pid = os.getpid()
    self_identity = proc_identity("/proc/self/stat")
    numeric_identity = proc_identity(f"/proc/{pid}/stat")
    status = {}
    for line in Path("/proc/self/status").read_bytes().splitlines():
        key, separator, value = line.partition(b":")
        if separator and key in {b"Pid", b"PPid"}: status[key] = int(value.strip())
    if (self_identity != numeric_identity or self_identity[0] != pid
            or status.get(b"Pid") != pid or status.get(b"PPid") != os.getppid()
            or self_identity[1] != os.getppid()):
        raise RuntimeError("Procfs and kernel PID namespaces do not match")
    return pid


def kernel_empty_children():
    """Only ECHILD proves empty. None means live children, not an empty set."""
    verify_proc_namespace()
    try:
        os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except ChildProcessError as error:
        if error.errno == errno.ECHILD: return True
        raise
    return False


def require_empty_baseline():
    if not kernel_empty_children():
        # No signal or reap has occurred. Preexisting children are never adopted
        # as this harness's cleanup authority merely because they are visible.
        raise RuntimeError("Preexisting children: refusing cleanup authority")


def owned_status(pid):
    """Exact unreaped-child authority, checked non-destructively before signalling."""
    verify_proc_namespace()
    return os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)


def signal_owned(pid, sig, *, start_time=None):
    if start_time is not None:
        identity = proc_identity(f"/proc/{pid}/stat")
        if identity != (pid, os.getpid(), start_time):
            raise RuntimeError("Owned child identity changed before signal")
    if owned_status(pid) is not None:
        return False  # Exited but deliberately unreaped; no signal is needed.
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        return False
    return True


def own_children():
    # The executor omits /proc/*/task/*/children. Kernel PPID/start fields are
    # the discovery mechanism; discovery alone NEVER proves an empty child set.
    parent = verify_proc_namespace(); result = {}
    for entry in Path("/proc").iterdir():
        if re.fullmatch(r"[0-9]+", entry.name) is None: continue
        try:
            pid, ppid, start = proc_identity(entry / "stat")
        except (FileNotFoundError, ProcessLookupError):
            continue  # A process can disappear during a read-only scan.
        if pid != int(entry.name):
            raise RuntimeError("Numeric procfs PID identity mismatch")
        if ppid == parent: result[pid] = start
    return result


def cleanup_adopted(deadline):
    """No children may be signalled/reaped without the empty-baseline authority."""
    if _CLEANUP_OWNER != os.getpid():
        raise RuntimeError("Cleanup ownership was never established")
    observed, statuses = set(), {}
    while time.monotonic() < deadline:
        children = own_children()
        if kernel_empty_children():
            return observed, statuses, []
        observed.update(children)
        for pid, start in children.items():
            try:
                identity = proc_identity(f"/proc/{pid}/stat")
                if identity != (pid, os.getpid(), start):
                    continue
                exited = owned_status(pid)
                if exited is not None:
                    found, status = os.waitpid(pid, os.WNOHANG)
                    if found: statuses[pid] = status
                else:
                    signal_owned(pid, signal.SIGKILL, start_time=start)
            except (ChildProcessError, FileNotFoundError, ProcessLookupError):
                pass
        time.sleep(.01)
    if kernel_empty_children():
        return observed, statuses, []
    remaining = sorted(own_children())
    return observed, statuses, remaining or ["kernel-child-not-enumerated"]


def subreaper():
    global _CLEANUP_OWNER
    _CLEANUP_OWNER = None
    require_empty_baseline()
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Test subreaper unavailable")
    _CLEANUP_OWNER = os.getpid()


def read_exact(fd, size, deadline):
    os.set_blocking(fd, False)
    output = bytearray()
    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_READ)
        while len(output) < size:
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError("Bounded test read expired")
            if not selector.select(min(.1, left)):
                continue
            try:
                chunk = os.read(fd, size - len(output))
            except BlockingIOError:
                continue
            if not chunk:
                raise EOFError("Incomplete test frame")
            output.extend(chunk)
    return bytes(output)


def read_to_eof(fd, deadline, cap=65536):
    os.set_blocking(fd, False)
    output = bytearray()
    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_READ)
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError("Bounded test drain expired")
            if not selector.select(min(.1, left)):
                continue
            try:
                chunk = os.read(fd, min(8192, cap + 1 - len(output)))
            except BlockingIOError:
                continue
            if not chunk:
                return bytes(output)
            output.extend(chunk)
            if len(output) > cap:
                raise ValueError("Test output cap exceeded")


def parent_owner(binary, channel_fd):
    channel = child = None
    errors = []
    try:
        channel = socket.socket(fileno=int(channel_fd)); channel.settimeout(30)
        child = subprocess.Popen([binary, "--parent-pid", str(os.getpid())],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Identity and all three pipes are transferred BEFORE any hello read.
        socket.send_fds(channel, [str(child.pid).encode()],
                        [child.stdin.fileno(), child.stdout.fileno(), child.stderr.fileno()])
        channel.recv(1)
    finally:
        try:
            if child is not None: errors = stop_owned(child, time.monotonic() + 2)
        finally:
            if channel is not None: channel.close()
    if errors:
        raise RuntimeError("Owner cleanup unconfirmed")


def parent_death(binary, protocol):
    subreaper()
    channel = peer = parent = None
    held = []; child = None; tested_reap = False; errors = []
    result = None
    try:
        channel, peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        channel.settimeout(5)
        parent = subprocess.Popen([sys.executable, __file__, "owner", binary, str(peer.fileno())],
                                  pass_fds=(peer.fileno(),), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        peer.close(); peer = None
        data, held, flags, _ = socket.recv_fds(channel, 128, 3)
        assert len(held) == 3 and not flags
        child = int(data)
        # Verify registration using kernel parentage, not just the message value.
        status = Path(f"/proc/{child}/status").read_text()
        assert f"PPid:\t{parent.pid}\n" in status
        end = time.monotonic() + 5
        size = struct.unpack("<I", read_exact(held[1], 4, end))[0]
        assert 1 <= size <= 512
        hello = json.loads(read_exact(held[1], size, end))
        assert hello == {"protocol": protocol, "kind": "hello", "ownership": "linux_parent_death_v1"}
        limits = Path(f"/proc/{child}/limits").read_text().splitlines()
        assert any(line.startswith("Max core file size") and line.split()[4:6] == ["0", "0"] for line in limits)
        signal_owned(parent.pid, signal.SIGKILL)
        parent.wait(timeout=2)
        assert parent.returncode == -signal.SIGKILL
        end = time.monotonic() + 2
        while time.monotonic() < end:
            found, child_status = os.waitpid(child, os.WNOHANG)
            if found:
                tested_reap = True
                assert os.WIFSIGNALED(child_status) and os.WTERMSIG(child_status) == signal.SIGKILL
                break
            time.sleep(.01)
        assert tested_reap, "Parent-death SIGKILL/reap was not observed"
        # The held stdin writer remains open throughout the tested death/reap.
        assert read_to_eof(held[1], time.monotonic() + 1) == b""
        assert read_to_eof(held[2], time.monotonic() + 1) == b""
        result = {"hello": True, "core_limit_zero": True, "retained_stdin": True,
                  "owned_child_reaped": True, "signal": "SIGKILL"}
    finally:
        try:
            try:
                if parent is not None: errors.extend(stop_owned(parent, time.monotonic() + 2))
            finally:
                # Covers failure between spawn and identity registration, too.
                observed, _, remaining = cleanup_adopted(time.monotonic() + 2)
                errors.extend(remaining)
                if result is not None and observed:
                    errors.append("unexpected-descendant-after-tested-reap")
        finally:
            for fd in held:
                try: os.close(fd)
                except OSError: errors.append("fd-close")
            for item in (peer, channel):
                if item is not None:
                    try: item.close()
                    except OSError: errors.append("socket-close")
        if errors:
            raise RuntimeError("Driver cleanup unconfirmed")
    print(json.dumps(result), flush=True)


def qualify(root, pins_path, pins_hash, output, cancelled, *, polling_correction_only=False):
    """Own a fresh process group until all cleanup is complete, including success."""
    required_run_variants = 4 if polling_correction_only else 176
    wall_budget = POLLING_WALL_SECONDS if polling_correction_only else FULL_WALL_SECONDS
    budget_version = POLLING_BUDGET_VERSION if polling_correction_only else FULL_BUDGET_VERSION
    if not sys.flags.isolated or not sys.dont_write_bytecode:
        raise RuntimeError("Start qualification with the venv Python -I -B")
    root = root.absolute(); output = output.absolute(); pins_path = pins_path.absolute()
    if output.is_relative_to(root):
        raise ValueError("Qualification evidence must be outside the clean checkout")
    # Check before even trusted Git preflight subprocesses can be spawned.
    require_empty_baseline()
    checked_pins(pins_path, pins_hash, root)
    output.mkdir(parents=True, exist_ok=False)
    (output / "tmp").mkdir()
    subreaper()
    child = selector = None; logs = {}; errors = []; statuses = {}; leftover = set()
    timed_out = False; returncode = None; began = time.monotonic()
    try:
        for name in ("stdout", "stderr"):
            logs[name] = (output / (name + ".log")).open("wb")
        # No inherited PYTHON*, PYTEST_PLUGINS, PYTEST_ADDOPTS, import/config,
        # loader, Git, or user-profile override is passed to qualification.
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
               "TMPDIR": str(output / "tmp"), "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONNOUSERSITE": "1", "PYTEST_ADDOPTS": "",
               "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "NO_COLOR": "1",
               "RENTGEN_SOURCE_TEST_PINS": str(pins_path),
               "RENTGEN_SOURCE_TEST_PINS_SHA256": pins_hash,
               "RENTGEN_SOURCE_SUPERVISOR_PID": str(os.getpid())}
        if cancelled(): raise RuntimeError("Interrupted before qualification launch")
        # -I keeps the intended venv but excludes user-site/environment imports.
        # Only the exact clean reviewed checkout is deliberately added to sys.path.
        bootstrap = ("import sys;root=sys.argv.pop(1);"
                     "sys.path[:0]=[root,root+'/tests/fixtures/source_facts'];"
                     "from qualification_journal import run_pytest;"
                     "raise SystemExit(run_pytest(sys.argv.pop(1),sys.argv[1:]))")
        # A single fixed regression scope, not a caller-supplied test selector.
        # It never executes the locally denied ptrace/strace gate cases.
        test_paths = (["tests/unit/test_source_fact_lifecycle_completion.py::test_completion_observed_authorization_poll_intervals"]
                      if polling_correction_only else [
                          "tests/unit/test_source_fact_runtime_boundaries.py",
                          "tests/unit/test_source_fact_lifecycle_completion.py",
                          "tests/unit/test_source_fact_wire_receipt_gaps.py"])
        child = subprocess.Popen([sys.executable, "-I", "-B", "-c", bootstrap, str(root),
                                  str(output / "progress.jsonl"),
                                  "-q", "-ra", "-p", "no:cacheprovider", "-c", str(root / "pyproject.toml"),
                                  "--confcutdir=" + str(root),
                                  "--basetemp=" + str(output / "tmp/pytest"),
                                  *test_paths,
                                  "--junitxml=" + str(output / "results.xml")],
                                 cwd=root, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, start_new_session=True)
        assert os.getpgid(child.pid) == child.pid
        # Do not poll/wait/communicate and release the ownership anchor early.
        selector = selectors.DefaultSelector(); counts = {"stdout": 0, "stderr": 0}
        for name in counts:
            stream = getattr(child, name); os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        end = began + wall_budget
        while True:
            if cancelled(): break
            if time.monotonic() >= end:
                timed_out = True; break
            for key, _ in selector.select(.1):
                try: data = os.read(key.fileobj.fileno(), 8192)
                except BlockingIOError: continue
                if not data:
                    selector.unregister(key.fileobj); continue
                counts[key.data] += len(data)
                if counts[key.data] > 4 * 1024 * 1024:
                    raise RuntimeError("Qualification log bound exceeded")
                logs[key.data].write(data)
            exit_info = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            if exit_info is not None and not selector.get_map():
                break
    except BaseException as error:
        errors.append("supervisor-" + type(error).__name__)
    finally:
        # Signal handlers only store a flag throughout launch AND this entire
        # teardown. Repeated SIGINT/SIGTERM cannot raise or reenter cleanup.
        try:
            if child is not None:
                # Exactly one group signal while the unreaped root anchors its ID.
                try:
                    owned_status(child.pid)  # Retain live OR zombie group anchor.
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                except OSError as error: errors.append(type(error).__name__)
        finally:
            try:
                # Always sweep, including interruption/failure before Popen assigns
                # a handle. Without an anchor, never infer or signal a group ID.
                observed, statuses, remaining = cleanup_adopted(time.monotonic() + 3)
                leftover = observed - ({child.pid} if child is not None else set())
                errors.extend(remaining)
                if child is not None:
                    if child.pid in statuses:
                        child.returncode = returncode = os.waitstatus_to_exitcode(statuses[child.pid])
                    else:
                        errors.append("root-reap-unconfirmed")
            except BaseException as error:
                errors.append("adopted-cleanup-unconfirmed-" + type(error).__name__)
            finally:
                if child is not None: errors.extend(close_streams(child))
                if selector is not None:
                    try: selector.close()
                    except BaseException as error: errors.append(type(error).__name__)
                for stream in logs.values():
                    try: stream.close()
                    except BaseException as error: errors.append(type(error).__name__)
    counts = {"passed": 0, "failed": 0, "skipped": 0, "unrun": required_run_variants}
    report = output / "results.xml"
    if report.is_file():
        try:
            tree = ast.parse((root / "tests/unit/test_source_fact_runtime_boundaries.py").read_text())
            completion_tree = ast.parse((root / "tests/unit/test_source_fact_lifecycle_completion.py").read_text())
            wire_tree = ast.parse((root / "tests/unit/test_source_fact_wire_receipt_gaps.py").read_text())
            names = ({"test_completion_observed_authorization_poll_intervals"} if polling_correction_only else
                     {n.name for n in [*tree.body, *completion_tree.body, *wire_tree.body]
                      if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")})
            all_cases = ET.parse(report).findall(".//testcase")
            cases = [c for c in all_cases if c.get("name", "").split("[", 1)[0] in names]
            if len(cases) != len(all_cases): errors.append("non-variant-junit-error")
            if len({c.get("name") for c in cases}) != len(cases): errors.append("duplicate-junit-variant")
            if polling_correction_only and {c.get("name") for c in cases} != {
                "test_completion_observed_authorization_poll_intervals[cancel-scanner]",
                "test_completion_observed_authorization_poll_intervals[cancel-kernel]",
                "test_completion_observed_authorization_poll_intervals[revoke-scanner]",
                "test_completion_observed_authorization_poll_intervals[revoke-kernel]",
            }: errors.append("polling-correction-variant-set")
            counts["failed"] = sum(c.find("failure") is not None or c.find("error") is not None for c in cases)
            counts["skipped"] = sum(c.find("skipped") is not None for c in cases)
            counts["passed"] = len(cases) - counts["failed"] - counts["skipped"]
            counts["unrun"] = max(0, required_run_variants - len(cases))
        except (OSError, ValueError, SyntaxError, ET.ParseError) as error:
            errors.append("report-" + type(error).__name__)
    passed = returncode == 0 and not cancelled() and not timed_out and not errors and not leftover and counts == {"passed": required_run_variants, "failed": 0, "skipped": 0, "unrun": 0}
    full_counts = dict(counts)
    if polling_correction_only: full_counts["unrun"] += 172
    summary = {"status": ("polling_correction_passed" if polling_correction_only else "passed") if passed else "not_passed",
               "scope": "polling_correction" if polling_correction_only else "full_source_boundaries",
               "required_run_variants": required_run_variants,
               "full_required_variants": 176, "full176_qualified": passed and not polling_correction_only,
               "counts": full_counts, "run_counts": counts,
               "pytest_exit": returncode, "wall_seconds": time.monotonic() - began,
               "harness_budget_version": budget_version, "harness_wall_seconds": wall_budget,
               "predeclared_cost_inventory": None if polling_correction_only else FULL_COST_INVENTORY,
               "timeout": timed_out, "interrupted": cancelled(), "cleanup_unconfirmed": errors,
               "residual_owned_descendants": sorted(leftover), "pins_sha256": pins_hash}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0 if passed else 2


def main():
    # These handlers are installed before any child launch. They never raise,
    # including during registration, cleanup, logging, or repeated delivery.
    interrupted = False
    def mark_interrupt(*_):
        nonlocal interrupted
        interrupted = True
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        for sig in previous: signal.signal(sig, mark_interrupt)
        if sys.argv[1:2] == ["owner"]:
            parent_owner(*sys.argv[2:]); return 2 if interrupted else 0
        if sys.argv[1:2] == ["parent-death"]:
            parent_death(*sys.argv[2:]); return 2 if interrupted else 0
        parser = argparse.ArgumentParser()
        parser.add_argument("--root", type=Path, required=True)
        parser.add_argument("--pins", type=Path, required=True)
        parser.add_argument("--pins-sha256", required=True)
        parser.add_argument("--output", type=Path, required=True)
        parser.add_argument("--polling-correction-only", action="store_true")
        args = parser.parse_args()
        status = qualify(args.root, args.pins, args.pins_sha256, args.output, lambda: interrupted,
                         polling_correction_only=args.polling_correction_only)
        return 2 if interrupted else status
    finally:
        # Restore only after the kernel confirms no retained/adopted child remains.
        # On unconfirmed cleanup, keep non-raising handlers until process exit.
        try: discharged = kernel_empty_children()
        except BaseException: discharged = False
        if discharged:
            for sig, handler in previous.items(): signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
