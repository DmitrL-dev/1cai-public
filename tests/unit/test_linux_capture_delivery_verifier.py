"""Pure artifact guards and actual unsupported-host/process controls, no fake Linux."""

import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import platform
import stat
import struct
import subprocess
import sys
import signal
import time
import zipfile

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/verification/verify_linux_capture_delivery.py"
spec = importlib.util.spec_from_file_location("linux_capture_delivery_verifier", SCRIPT)
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)
VERSION = "0.1.0.dev19"
unsupported = pytest.mark.skipif(
    sys.platform == "linux" and platform.machine() in {"x86_64", "amd64"},
    reason="Control requires an actual unsupported host")
posix = pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="Actual POSIX process/leaf controls")


@pytest.mark.parametrize("version,commit,digest", [("x", "a" * 40, "b" * 64),
    ("1.0\n", "a" * 40, "b" * 64), (VERSION, "A" * 40, "b" * 64),
    (VERSION, "a" * 39, "b" * 64), (VERSION, "a" * 40, "B" * 64),
    (VERSION, "a" * 40, True)])
def test_input_labels_refuse_ambiguous_source_or_scanner_identity(version, commit, digest):
    with pytest.raises(subject.VerificationError):
        subject.labels(version, commit, digest)


def elf():
    raw = bytearray(120)
    raw[:8] = b"\x7fELF\x02\x01\x01\x00"
    struct.pack_into("<HHI", raw, 16, 2, 62, 1)
    struct.pack_into("<Q", raw, 32, 64)
    struct.pack_into("<HHH", raw, 52, 64, 56, 1)
    struct.pack_into("<I", raw, 64, 1)
    return raw


@pytest.mark.parametrize("damage", ["dynamic", "interpreter", "wrong-arch", "shared", "short-table"])
def test_scanner_header_guard_rejects_dynamic_or_non_amd64_inputs(damage):
    # Header-only constructed inputs test parsing; none is executable qualification.
    raw = elf()
    if damage == "dynamic": struct.pack_into("<I", raw, 64, 2)
    elif damage == "interpreter": struct.pack_into("<I", raw, 64, 3)
    elif damage == "wrong-arch": struct.pack_into("<H", raw, 18, 183)
    elif damage == "shared": struct.pack_into("<H", raw, 16, 3)
    else: raw.pop()
    with pytest.raises(subject.VerificationError):
        subject.static_scanner(bytes(raw))


def wheel(expected, *, damage=None):
    payload = dict(expected)
    metadata = "rentgen_core-" + VERSION + ".dist-info/"
    payload.update({metadata + name: b"fixture" for name in ("WHEEL", "entry_points.txt", "RECORD", "licenses/LICENSE")})
    payload[metadata + "entry_points.txt"] = ("[console_scripts]\n" + "\n".join(
        name + " = " + target for name, target in subject.ENTRY_POINTS.items()) + "\n").encode()
    payload[metadata + "METADATA"] = ("Name: rentgen-core\nVersion: " + VERSION + "\n").encode()
    if damage == "stale": payload["rentgen_core/__init__.py"] = b"stale product"
    elif damage == "missing": del payload["rentgen_graph/__init__.py"]
    elif damage == "extra": payload["rentgen_core/extra.py"] = b"unexpected"
    elif damage == "pth": payload["autoload.pth"] = b"unwanted"
    elif damage == "traversal": payload["../outside"] = b"unwanted"
    elif damage == "version": payload[metadata + "METADATA"] = b"Name: rentgen-core\nVersion: 9.9\n"
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w") as archive:
        for name, raw in payload.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = ((stat.S_IFLNK if damage == "symlink" and name == "rentgen_core/__init__.py"
                                   else stat.S_IFREG) | 0o644) << 16
            archive.writestr(info, raw)
    return target.getvalue()


@pytest.mark.parametrize("damage", ["stale", "missing", "extra", "pth", "traversal", "version", "symlink"])
def test_wheel_cannot_claim_a_different_checkout_or_outside_payload(damage):
    expected = {root + "/__init__.py": (root + " bytes").encode() for root in subject.PACKAGES}
    with pytest.raises(subject.VerificationError):
        subject.wheel_product(wheel(expected, damage=damage), expected, VERSION)


def test_pure_wheel_binding_includes_every_product_byte_and_metadata_version():
    expected = {root + "/__init__.py": (root + " bytes").encode() for root in subject.PACKAGES}
    digest = subject.wheel_product(wheel(expected), expected, VERSION)
    assert len(digest) == 64
    changed = dict(expected, **{"rentgen_core/__init__.py": b"other source"})
    with pytest.raises(subject.VerificationError):
        subject.wheel_product(wheel(expected), changed, VERSION)


@pytest.mark.parametrize("name,target,section", [("../escaped-script", "rentgen_core.cli:main", "console_scripts"),
    ("/absolute-script", "rentgen_core.cli:main", "console_scripts"),
    ("rentgen", "rentgen_core.cli:unreviewed", "console_scripts"),
    ("rentgen", "rentgen_core.cli:main", "other_scripts")])
def test_wheel_entry_point_metadata_cannot_expand_installer_write_or_execution_authority(name, target, section):
    expected = {root + "/__init__.py": (root + " bytes").encode() for root in subject.PACKAGES}
    original = wheel(expected)
    changed = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(changed, "w") as destination:
        for info in source.infolist():
            raw = source.read(info)
            if info.filename.endswith("/entry_points.txt"):
                raw = ("[" + section + "]\n" + name + " = " + target + "\n").encode()
            destination.writestr(info, raw)
    with pytest.raises(subject.VerificationError):
        subject.wheel_product(changed.getvalue(), expected, VERSION)


@pytest.mark.parametrize("built", [False, True])
def test_recovery_protocol_accepts_only_exact_json_and_fixed_builder_diagnostics(built):
    recovery = dict(operation_id="11111111-1111-4111-8111-111111111111", expected_head={"revision": 0})
    raw = subject.canonical({"recovery": recovery}) + b"\n"
    if built:
        raw += b"\n".join(subject.CAPTURE_DIAGNOSTICS) + b"\n"
    subject.recovery_stderr(raw, recovery, built=built)
    for invalid in (raw + b"unexpected diagnostic\n", raw.replace(b'"revision":0', b'"revision":1')):
        with pytest.raises(subject.VerificationError):
            subject.recovery_stderr(invalid, recovery, built=built)


@pytest.mark.parametrize("path_type", [PurePosixPath, PureWindowsPath])
def test_pip_and_python_environment_cannot_redirect_install_outside_owned_venv(path_type):
    environment = subject.process_environment({"PIP_TARGET": "/outside", "PIP_PREFIX": "/outside",
        "PIP_CONFIG_FILE": "/outside/config", "PIP_USER": "1", "PYTHONPATH": "/outside",
        "PYTHONHOME": "/outside", "LD_PRELOAD": "/outside/library", "LD_AUDIT": "/outside/library",
        "DYLD_INSERT_LIBRARIES": "/outside/library", "PATH": "preserved"})
    assert {key: value for key, value in environment.items() if key.startswith("PIP_")} == {"PIP_CONFIG_FILE": os.devnull}
    assert not any(key.startswith(("LD_", "DYLD_")) for key in environment)
    assert "PYTHONPATH" not in environment and "PYTHONHOME" not in environment
    assert environment["PATH"] == "preserved"
    python, wheel = path_type("/owned/environment/bin/python"), path_type("/owned/product.whl")
    arguments = subject.install_arguments(python, wheel)
    assert arguments == [python, "-I", "-m", "pip", "--isolated",
        "--disable-pip-version-check", "--no-cache-dir", "install", "--no-index", "--no-deps", str(wheel)]


@unsupported
def test_actual_unsupported_host_refuses_before_input_io_or_output_creation(tmp_path):
    output = tmp_path / "new-output"
    with pytest.raises(subject.VerificationError, match="actual Linux/amd64"):
        subject.verify(tmp_path / "absent.whl", tmp_path / "absent-scanner", "b" * 64,
                       output, VERSION, "a" * 40)
    assert not output.exists()


@unsupported
def test_script_unsupported_host_emits_only_bounded_public_failure(tmp_path):
    output = tmp_path / "new-output"
    result = subprocess.run([sys.executable, "-I", str(SCRIPT), "--wheel", str(tmp_path / "missing.whl"),
        "--scanner", str(tmp_path / "missing-scanner"), "--scanner-sha256", "b" * 64,
        "--source-commit", "a" * 40, "--expected-version", VERSION, "--output", str(output)],
        capture_output=True, timeout=10)
    assert result.returncode == 1 and result.stdout == b""
    assert result.stderr.replace(b"\r\n", b"\n") == b"Installed Linux capture verification failed: Installed capture qualification requires actual Linux/amd64\n"
    assert not output.exists()


@posix
@pytest.mark.parametrize("mode", [0o600, 0o700])
def test_owned_artifact_copy_is_exclusive_and_independent_of_later_input_changes(tmp_path, mode):
    source = tmp_path / "input"
    source.write_bytes(b"original verified bytes")
    copied = tmp_path / "owned-copy"
    subject.copy_owned(copied, source.read_bytes(), mode)
    source.write_bytes(b"later different bytes")
    assert copied.read_bytes() == b"original verified bytes" and stat.S_IMODE(copied.stat().st_mode) == mode
    with pytest.raises(FileExistsError):
        subject.copy_owned(copied, b"replacement bytes", mode)
    assert copied.read_bytes() == b"original verified bytes"


@posix
def test_real_fifo_input_refuses_without_blocking_before_metadata_check(tmp_path):
    fifo = tmp_path / "scanner-fifo"
    os.mkfifo(fifo)
    code = '''
import importlib.util,sys
spec=importlib.util.spec_from_file_location('verifier',sys.argv[1])
subject=importlib.util.module_from_spec(spec);spec.loader.exec_module(subject)
try:
    subject.read_regular(sys.argv[2],1024)
except subject.VerificationError:
    raise SystemExit(0)
raise SystemExit(1)
'''
    result = subprocess.run([sys.executable, "-I", "-c", code, str(SCRIPT), str(fifo)],
                            capture_output=True, timeout=3)
    assert result.returncode == 0 and not result.stdout and not result.stderr
    assert stat.S_ISFIFO(fifo.stat().st_mode)


@posix
def test_actual_process_stream_bound_refuses_excess_output(tmp_path):
    with pytest.raises(subject.VerificationError, match="output exceeded"):
        subject.run([sys.executable, "-I", "-c", "import sys;sys.stdout.write('x'*100000)"],
                    cwd=tmp_path, stdout_limit=32, timeout=5)


@posix
def test_actual_process_deadline_refuses_a_hung_child(tmp_path):
    with pytest.raises(subject.VerificationError, match="deadline"):
        subject.run([sys.executable, "-I", "-c", "import time;time.sleep(10)"],
                    cwd=tmp_path, timeout=.05)


@posix
def test_deadline_reaps_owned_group_even_after_leader_has_exited(tmp_path):
    record = tmp_path / "owned-child.json"
    code = """
import json,os,pathlib,subprocess,sys
child=subprocess.Popen([sys.executable,'-I','-c','import time;time.sleep(10)'])
pathlib.Path(sys.argv[1]).write_text(json.dumps({'pid':child.pid,'group':os.getpgrp()}))
"""
    child_record = None
    try:
        with pytest.raises(subject.VerificationError, match="deadline"):
            subject.run([sys.executable, "-I", "-c", code, str(record)], cwd=tmp_path, timeout=.3)
        child_record = json.loads(record.read_text())
        deadline = time.monotonic() + 2
        while True:
            result = subprocess.run(["ps", "-o", "stat=", "-p", str(child_record["pid"])],
                                    capture_output=True, timeout=1)
            status = result.stdout.strip()
            if not status or status.startswith(b"Z"):
                break
            assert time.monotonic() < deadline, "Owned descendant survived deadline cleanup"
            time.sleep(.02)
    finally:
        if record.exists():
            child_record = json.loads(record.read_text())
            try:
                os.killpg(child_record["group"], signal.SIGKILL)
            except ProcessLookupError:
                pass
