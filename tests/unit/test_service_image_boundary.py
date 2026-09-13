"""SCM image validation only: never install, start or query a host service."""

from pathlib import Path
import subprocess

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.service_installer import ServiceInstallSpec, WindowsServiceInstaller


@pytest.fixture
def image_files(tmp_path):
    directory = tmp_path / "Service runtime"
    directory.mkdir()
    native = directory / "observer-service.exe"
    config = directory / "observer settings.json"
    scm = directory / "sc.exe"
    for file in (native, config, scm):
        file.write_text("private-config-content")
    return native, config, scm


@pytest.mark.parametrize("basename", ["rentgen-service.exe", "RENTGEN-SERVICE.EXE"])
@pytest.mark.parametrize("with_config", [False, True])
def test_pip_console_image_rejected_before_scm(image_files, basename, with_config):
    native, config, scm = image_files
    launcher = native.with_name(basename)
    launcher.touch()
    calls = []
    installer = WindowsServiceInstaller(executor=calls.append, sc_executable=scm)
    arguments = ("--service", "--config", str(config)) if with_config else ()

    with pytest.raises(CoreError) as raised:
        spec = ServiceInstallSpec(
            "Rentgen.Observer", "Rentgen Observer", launcher, arguments
        )
        installer.install(spec, dry_run=True)

    assert raised.value.code == "SERVICE_IMAGE_UNSUPPORTED"
    assert raised.value.details == {}
    assert str(launcher) not in str(raised.value.to_dict("test"))
    assert "private-config-content" not in str(raised.value.to_dict("test"))
    assert raised.value.__cause__ is None
    assert calls == []


@pytest.mark.parametrize(
    "source_name,target_name",
    [
        ("rentgen-service.exe", "observer-service.exe"),
        ("observer-service.exe", "rentgen-service.exe"),
        ("python.exe", "rentgen-service.exe"),
    ],
)
def test_pip_image_rejected_on_either_side_of_canonicalization(
    image_files, monkeypatch, source_name, target_name
):
    native, config, _ = image_files
    source = native.with_name(source_name)
    target_dir = native.parent / "canonical"
    target_dir.mkdir()
    target = target_dir / target_name
    source.touch()
    target.touch()
    original = Path.resolve
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda path, *args, **kwargs: target
        if path == source
        else original(path, *args, **kwargs),
    )
    arguments = ("--service", "--config", str(config))
    if source_name == "python.exe":
        arguments = ("-I", "-m", "rentgen_core.service_entry") + arguments

    with pytest.raises(CoreError) as raised:
        ServiceInstallSpec("Rentgen.Observer", "Rentgen Observer", source, arguments)

    assert raised.value.code == "SERVICE_IMAGE_UNSUPPORTED"


@pytest.mark.parametrize("operation", ["install", "update"])
def test_revalidation_rejects_new_pip_target_before_first_scm_call(
    image_files, monkeypatch, operation
):
    native, config, scm = image_files
    spec = ServiceInstallSpec(
        "Rentgen.Observer",
        "Rentgen Observer",
        native,
        ("--service", "--config", str(config)),
    )
    launcher = native.with_name("rentgen-service.exe")
    launcher.touch()
    calls = []

    def executor(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0)

    installer = WindowsServiceInstaller(executor=executor, sc_executable=scm)
    original = Path.resolve
    monkeypatch.setattr("rentgen_core.service_installer.sys.platform", "win32")
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda path, *args, **kwargs: launcher
        if path == native
        else original(path, *args, **kwargs),
    )

    with pytest.raises(CoreError) as raised:
        getattr(installer, operation)(spec)

    assert raised.value.code == "SERVICE_IMAGE_UNSUPPORTED"
    assert calls == []


@pytest.mark.parametrize("basename", ["python.exe", "pythonw.exe"])
def test_supported_direct_interpreter_retains_exact_quoted_imagepath(
    image_files, basename
):
    native, config, scm = image_files
    interpreter = native.with_name(basename)
    interpreter.touch()
    arguments = (
        "-I",
        "-m",
        "rentgen_core.service_entry",
        "--service",
        "--config",
        str(config),
    )
    spec = ServiceInstallSpec(
        "Rentgen.Observer", "Rentgen Observer", interpreter, arguments
    )
    calls = []
    plan = WindowsServiceInstaller(executor=calls.append, sc_executable=scm).install(
        spec, dry_run=True
    )

    assert spec.binary_path == f'"{interpreter.resolve()}" ' + subprocess.list2cmdline(
        arguments
    )
    create = plan.commands[1]
    assert create[create.index("binPath=") + 1] == spec.binary_path
    assert "private-config-content" not in repr(plan)
    assert calls == []
