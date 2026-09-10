"""Bounded process supervision and module-loaded evidence, without running 1C."""
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.manifests import canonical_bytes
from rentgen_core.native_platform import NativePlatform
from rentgen_core import native_platform
from rentgen_core.native_process import OwnedProcess

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows process contract")


def test_successful_process_result_is_hashable(tmp_path, monkeypatch):
    class Completed:
        returncode = 0

        def poll(self):
            return 0

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

    def launch(*args, **kwargs):
        (tmp_path / "compile.log").write_text("No errors found", "utf-8")
        return Completed()

    monkeypatch.setattr(native_platform, "OwnedProcess", launch)
    platform = NativePlatform(Path("1cv8.exe"), "0" * 64)
    result = platform.invoke(
        tmp_path, "compile", ["DESIGNER"], lambda: None, time.monotonic() + 5
    )
    assert type(result["elapsed_ms"]) is int
    assert canonical_bytes(result)


def test_revocation_terminates_the_owned_native_process(tmp_path, monkeypatch):
    children, checks = [], []

    def launch(command, executable, out, err, **kwargs):
        child = OwnedProcess(
            subprocess.list2cmdline(
                [sys._base_executable, "-c", "import time;time.sleep(120)"]
            ),
            sys._base_executable,
            out,
            err,
        )
        children.append(child)
        return child

    monkeypatch.setattr(native_platform, "OwnedProcess", launch)

    def authorize():
        checks.append(True)
        if len(checks) > 1:
            raise CoreError("PROJECT_FORBIDDEN", "Revoked")

    platform = NativePlatform(Path("1cv8.exe"), "0" * 64)
    with pytest.raises(CoreError) as error:
        platform.invoke(
            tmp_path, "compile", ["DESIGNER"], authorize, time.monotonic() + 5
        )
    assert error.value.code == "PROJECT_FORBIDDEN"
    assert len(children) == 1
    assert children[0].returncode is not None
    assert children[0].job.handle is None


def test_absent_roundtrip_module_never_reaches_compiler(tmp_path, monkeypatch):
    stages = []

    def invoke(self, folder, name, args, authorize, deadline):
        stages.append(name)
        if name == "create":
            (folder / "infobase").mkdir()
            (folder / "infobase/1Cv8.1CD").write_bytes(b"fixture")
        return {"name": name, "exit_code": 0}

    monkeypatch.setattr(NativePlatform, "invoke", invoke)
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (before / "Orphan.bsl").write_bytes(
        b"Function Value() Export\nReturn 1;\nEndFunction\n"
    )
    platform = NativePlatform(Path("1cv8.exe"), "0" * 64)
    with pytest.raises(CoreError) as error:
        platform.check(before, after, "Orphan.bsl", tmp_path, lambda: None)
    assert error.value.code == "PLATFORM_TARGET_NOT_LOADED"
    assert stages == ["create", "baseline-load", "baseline-dump"]
