"""Private directory ACL checks retain policy across native SID rendering."""

import ctypes
import sys

import pytest

from rentgen_diagnostics._owned_attempt import _PrivateFS
from rentgen_diagnostics._runtime_pins import PinFailure, RuntimePins

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows ACL contract")


@pytest.fixture
def private_directory(tmp_path, monkeypatch):
    pins = RuntimePins()
    native = _PrivateFS(pins)
    calls = []

    def create_directory(path, security):
        calls.append(path)
        return True

    # No filesystem ACL is changed for service-account test identities.
    # Both descriptor conversions still execute the real Windows API.
    monkeypatch.setattr(native.kernel, "CreateDirectoryW", create_directory)
    try:
        yield native, tmp_path / "owned", calls
    finally:
        pins.close()


@pytest.mark.parametrize(
    ("sid", "rendered"),
    [
        ("S-1-5-18", "SY"),
        ("S-1-5-19", "LS"),
        ("S-1-5-20", "NS"),
        ("S-1-5-21-111-222-333-1001", "S-1-5-21-111-222-333-1001"),
    ],
)
def test_private_directory_accepts_native_sid_spelling(
    private_directory, monkeypatch, sid, rendered
):
    native, path, calls = private_directory
    native.sid = sid
    monkeypatch.setattr(
        native, "_dacl", lambda _: f"D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;{rendered})"
    )
    native.mkdir(path)
    assert calls == ["\\\\?\\" + str(path)]
    assert native.created_paths == {path}
    assert not native.cleanup_uncertain


@pytest.mark.parametrize(
    "observed",
    [
        "D:(A;OICI;FA;;;SY)(A;OICI;FA;;;SY)",
        "D:PAI(A;OICI;FA;;;SY)(A;OICI;FA;;;SY)",
        "D:P(A;OICI;FR;;;SY)(A;OICI;FA;;;SY)",
        "D:P(A;OI;FA;;;SY)(A;OICI;FA;;;SY)",
        "D:P(A;OICI;FA;;;SY)",
        "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)",
        "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;SY)(A;OICI;FA;;;WD)",
        "D:P(D;OICI;FA;;;SY)(A;OICI;FA;;;SY)",
    ],
)
def test_private_directory_rejects_changed_acl(
    private_directory, monkeypatch, observed
):
    native, path, calls = private_directory
    native.sid = "S-1-5-18"
    monkeypatch.setattr(native, "_dacl", lambda _: observed)
    with pytest.raises(PinFailure) as error:
        native.mkdir(path)
    assert error.value.code == "BSL_PROCESS_FAILED"
    assert len(calls) == 1
    assert native.created_paths == {path}


def test_private_directory_stops_when_rendering_fails(private_directory, monkeypatch):
    native, path, calls = private_directory
    monkeypatch.setattr(
        native.security,
        "ConvertSecurityDescriptorToStringSecurityDescriptorW",
        lambda *args: False,
    )
    monkeypatch.setattr(
        native, "_dacl", lambda _: pytest.fail("No directory should be created")
    )
    with pytest.raises(PinFailure) as error:
        native.mkdir(path)
    assert error.value.code == "BSL_PROCESS_FAILED"
    assert not calls and not native.created_paths


def test_private_directory_rejects_empty_rendering(private_directory, monkeypatch):
    native, path, calls = private_directory
    monkeypatch.setattr(
        native.security,
        "ConvertSecurityDescriptorToStringSecurityDescriptorW",
        lambda *args: True,
    )
    monkeypatch.setattr(
        native, "_dacl", lambda _: pytest.fail("No directory should be created")
    )
    with pytest.raises(PinFailure) as error:
        native.mkdir(path)
    assert error.value.code == "BSL_PROCESS_FAILED"
    assert not calls and not native.created_paths


def test_private_directory_marks_failed_string_release_uncertain(
    private_directory, monkeypatch
):
    native, path, calls = private_directory
    release = native.kernel.LocalFree
    released = []

    def reported_failure(pointer):
        result = release(pointer)
        assert not result
        released.append(ctypes.cast(pointer, ctypes.c_void_p).value)
        # Release real memory, then simulate the first call's failure result.
        return released[-1] if len(released) == 1 else None

    monkeypatch.setattr(native.kernel, "LocalFree", reported_failure)
    with pytest.raises(PinFailure) as error:
        native.mkdir(path)
    assert error.value.code == "BSL_CLEANUP_FAILED"
    assert native.cleanup_uncertain
    assert len(released) == 2 and len(set(released)) == 2
    assert not calls and not native.created_paths
