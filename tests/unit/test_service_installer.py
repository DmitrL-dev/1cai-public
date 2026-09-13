"""SCM installer proof: fake executors only; never mutate host services."""

import subprocess
from dataclasses import FrozenInstanceError

import pytest

from rentgen_core.errors import CoreError


def api():
    from rentgen_core.service_installer import (
        ServiceInstallSpec,
        WindowsServiceInstaller,
    )

    return ServiceInstallSpec, WindowsServiceInstaller


@pytest.fixture
def files(tmp_path):
    binary = tmp_path / "service app.exe"
    binary.write_bytes(b"test executable placeholder")
    config = tmp_path / "settings.json"
    config.write_text("{}")
    sc = tmp_path / "sc.exe"
    sc.write_bytes(b"test SCM placeholder")
    return binary, config, sc


class Executor:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return subprocess.CompletedProcess(argv, outcome)


def setup(files, monkeypatch, outcomes):
    spec_type, installer_type = api()
    monkeypatch.setattr("rentgen_core.service_installer.sys.platform", "win32")
    executable, config, sc = files
    spec = spec_type(
        "Rentgen.Observer",
        "Rentgen Observer",
        executable,
        ("--service", "--config", str(config)),
    )
    executor = Executor(outcomes)
    installer = installer_type(executor=executor, sc_executable=sc)
    return spec, installer, executor


def verbs(executor):
    return [call[0][1] for call in executor.calls]


def test_plan_is_immutable_deterministic_and_dry_run_has_no_io(files, monkeypatch):
    spec, installer, executor = setup(files, monkeypatch, [])
    plan = installer.plan("install", spec, start=True)
    assert plan == installer.install(spec, start=True, dry_run=True)
    assert plan.operation == "install"
    assert [command[1] for command in plan.commands] == ["query", "create", "start"]
    assert plan.rollback == (str(files[2]), "delete", spec.service_name)
    assert executor.calls == []
    with pytest.raises(FrozenInstanceError):
        spec.service_name = "Other"
    create = plan.commands[1]
    assert create[create.index("binPath=") + 1] == '"' + str(
        files[0]
    ) + '" --service --config ' + subprocess.list2cmdline([str(files[1])])
    assert create[create.index("obj=") + 1] == r"NT AUTHORITY\LocalService"


def test_install_checks_absence_creates_then_starts(files, monkeypatch):
    spec, installer, executor = setup(files, monkeypatch, [1060, 0, 0])
    result = installer.install(spec, start=True)
    assert verbs(executor) == ["query", "create", "start"]
    assert result.operation == "install"
    for argv, options in executor.calls:
        assert isinstance(argv, list)
        assert options == dict(
            shell=False,
            timeout=15.0,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


@pytest.mark.parametrize(
    "outcomes, expected",
    [([0], ["query"]), ([1060, 1073], ["query", "create"]), ([5], ["query"])],
)
def test_failed_preflight_or_create_never_deletes_existing_service(
    files, monkeypatch, outcomes, expected
):
    spec, installer, executor = setup(files, monkeypatch, outcomes)
    with pytest.raises(CoreError):
        installer.install(spec, start=True)
    assert verbs(executor) == expected


@pytest.mark.parametrize(
    "failure",
    [5, subprocess.TimeoutExpired("secret password", 15), OSError("secret password")],
)
def test_partial_install_rolls_back_only_its_created_service(
    files, monkeypatch, failure
):
    spec, installer, executor = setup(files, monkeypatch, [1060, 0, failure, 0])
    with pytest.raises(CoreError) as raised:
        installer.install(spec, start=True)
    assert verbs(executor) == ["query", "create", "start", "delete"]
    assert raised.value.details["rollback"] == "delete_requested"
    assert "secret password" not in str(raised.value.to_dict("test"))
    assert raised.value.__cause__ is None


def test_failed_rollback_is_reported_without_retry(files, monkeypatch):
    spec, installer, executor = setup(files, monkeypatch, [1060, 0, 5, 5])
    with pytest.raises(CoreError) as raised:
        installer.install(spec, start=True)
    assert raised.value.details["rollback"] == "failed"
    assert verbs(executor) == ["query", "create", "start", "delete"]


@pytest.mark.parametrize(
    "operation, outcomes, expected",
    [
        ("update", [0, 0], ["query", "config"]),
        ("start", [0, 0], ["query", "start"]),
        ("stop", [0, 0], ["query", "stop"]),
        ("uninstall", [0, 0, 0], ["query", "stop", "delete"]),
        ("uninstall", [0, 1062, 0], ["query", "stop", "delete"]),
    ],
)
def test_explicit_operation_order(files, monkeypatch, operation, outcomes, expected):
    spec, installer, executor = setup(files, monkeypatch, outcomes)
    getattr(installer, operation)(spec)
    assert verbs(executor) == expected


def test_stop_failure_prevents_uninstall_delete(files, monkeypatch):
    spec, installer, executor = setup(files, monkeypatch, [0, 5])
    with pytest.raises(CoreError):
        installer.uninstall(spec)
    assert verbs(executor) == ["query", "stop"]


@pytest.mark.parametrize("operation", ["query", "status"])
@pytest.mark.parametrize("code, exists", [(0, True), (1060, False)])
def test_status_is_read_only_existence_check(
    files, monkeypatch, operation, code, exists
):
    spec, installer, executor = setup(files, monkeypatch, [code])
    result = getattr(installer, operation)(spec)
    assert result.exists is exists
    assert verbs(executor) == ["query"]


def test_non_windows_fails_before_executor_even_when_injected(files, monkeypatch):
    spec, installer, executor = setup(files, monkeypatch, [])
    monkeypatch.setattr("rentgen_core.service_installer.sys.platform", "linux")
    with pytest.raises(CoreError) as raised:
        installer.install(spec)
    assert raised.value.code == "SERVICE_PLATFORM_UNSUPPORTED"
    assert executor.calls == []


def test_scm_missing_and_deleted_target_fail_closed(files, monkeypatch):
    spec, installer, executor = setup(files, monkeypatch, [])
    files[2].unlink()
    with pytest.raises(CoreError) as raised:
        installer.query(spec)
    assert raised.value.code == "SERVICE_SCM_UNAVAILABLE"
    assert executor.calls == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("service_name", "bad\r\nname"),
        ("service_name", "a" * 81),
        ("service_name", "../other"),
        ("display_name", "a" * 121),
        ("display_name", "password=secret"),
        ("arguments", ("--token", "secret")),
        ("arguments", ("--password=secret",)),
        ("arguments", ("--service\n",)),
        ("arguments", ("--service", "opaque-secret")),
        ("arguments", "--service"),
        ("arguments", ("--service",) * 10),
        ("executable", "relative.exe"),
        ("executable", r"\\server\share\service.exe"),
        ("executable", r"C:\bad.exe:stream"),
        ("executable", "C:\\bad\r\n.exe"),
    ],
)
def test_invalid_or_secret_inputs_rejected_without_echo(files, field, value):
    spec_type, _ = api()
    inputs = dict(
        service_name="Rentgen.Observer",
        display_name="Rentgen Observer",
        executable=files[0],
        arguments=("--service",),
    )
    inputs[field] = value
    with pytest.raises(CoreError) as raised:
        spec_type(**inputs)
    assert raised.value.code == "SERVICE_SPEC_INVALID"
    assert "secret" not in str(raised.value.to_dict("test"))


def test_config_path_must_exist_and_not_contain_credential_marker(files):
    spec_type, _ = api()
    with pytest.raises(CoreError):
        spec_type(
            "Rentgen",
            "Rentgen",
            files[0],
            ("--config", str(files[1].parent / "missing.json")),
        )
    secret = files[1].parent / "password=secret.json"
    secret.write_text("{}")
    with pytest.raises(CoreError):
        spec_type("Rentgen", "Rentgen", files[0], ("--config", str(secret)))


@pytest.mark.parametrize(
    "timeout", [0, -1, 61, float("nan"), True, pytest.param(10**1000, id="huge-int")]
)
def test_timeout_must_be_finite_and_bounded(files, timeout):
    _, installer_type = api()
    with pytest.raises(CoreError) as raised:
        installer_type(sc_executable=files[2], timeout=timeout)
    assert raised.value.code == "SERVICE_SPEC_INVALID"


def test_executor_exception_and_malformed_result_are_typed_and_redacted(
    files, monkeypatch
):
    spec, installer, executor = setup(files, monkeypatch, [OSError("token=hidden")])
    with pytest.raises(CoreError) as raised:
        installer.query(spec)
    assert raised.value.code == "SERVICE_SCM_UNAVAILABLE"
    assert "hidden" not in str(raised.value.to_dict("request"))
    installer._executor = lambda *args, **kwargs: None
    with pytest.raises(CoreError) as raised:
        installer.query(spec)
    assert raised.value.code == "SERVICE_SCM_PROTOCOL"


def test_unexpected_executor_exception_is_redacted(files, monkeypatch):
    spec, installer, executor = setup(
        files, monkeypatch, [RuntimeError("password=hidden")]
    )
    with pytest.raises(CoreError) as raised:
        installer.query(spec)
    assert raised.value.code == "SERVICE_SCM_UNAVAILABLE"
    assert "hidden" not in str(raised.value.to_dict("test"))


def test_create_timeout_does_not_delete_service_of_unknown_ownership(
    files, monkeypatch
):
    spec, installer, executor = setup(
        files, monkeypatch, [1060, subprocess.TimeoutExpired("create", 15)]
    )
    with pytest.raises(CoreError) as raised:
        installer.install(spec, start=True)
    assert raised.value.code == "SERVICE_SCM_TIMEOUT"
    assert "rollback" not in raised.value.details
    assert verbs(executor) == ["query", "create"]


def test_revalidates_executable_before_mutation_but_can_query_deleted_file(
    files, monkeypatch
):
    spec, installer, executor = setup(files, monkeypatch, [0])
    files[0].unlink()
    with pytest.raises(CoreError):
        installer.install(spec)
    assert executor.calls == []
    assert installer.query(spec).exists is True


def test_config_contents_never_enter_plan_or_executor(files, monkeypatch):
    spec, installer, executor = setup(files, monkeypatch, [1060, 0])
    files[1].write_text('{"password":"highly-sensitive-value"}')
    assert "highly-sensitive-value" not in repr(installer.plan("install", spec))
    installer.install(spec)
    assert "highly-sensitive-value" not in repr(executor.calls)


@pytest.mark.parametrize(
    "operation,start",
    [("delete", False), ([], False), ("update", True), ("install", 1)],
)
def test_invalid_plan_is_typed_and_does_not_execute(
    files, monkeypatch, operation, start
):
    spec, installer, executor = setup(files, monkeypatch, [])
    with pytest.raises(CoreError):
        installer.plan(operation, spec, start=start)
    assert executor.calls == []


def test_default_executor_uses_subprocess_run_without_shell(files, monkeypatch):
    spec, _, executor = setup(files, monkeypatch, [0])
    monkeypatch.setattr("rentgen_core.service_installer.subprocess.run", executor)
    _, installer_type = api()
    assert installer_type(sc_executable=files[2]).query(spec).exists is True
    assert executor.calls[0][1]["shell"] is False


def test_missing_service_update_never_creates_or_deletes(files, monkeypatch):
    spec, installer, executor = setup(files, monkeypatch, [1060])
    with pytest.raises(CoreError):
        installer.update(spec)
    assert verbs(executor) == ["query"]


@pytest.mark.parametrize(
    "field,suffix",
    [("executable", ".exe"), ("config", ".json"), ("sc_executable", ".exe")],
)
def test_canonical_target_keeps_suffix_and_path_validation(
    files, monkeypatch, field, suffix
):
    from pathlib import Path

    spec_type, installer_type = api()
    source = files[1] if field == "config" else files[0]
    target = source.parent / ("unexpected%name" + suffix)
    target.write_text("{}")
    original = Path.resolve
    # Resolve models a followed symlink/reparse point without Windows symlink privilege.
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda self, *args, **kwargs: target
        if self == source
        else original(self, *args, **kwargs),
    )
    with pytest.raises(CoreError):
        if field == "sc_executable":
            installer_type(sc_executable=source)
        elif field == "config":
            spec_type("Rentgen", "Rentgen", files[2], ("--config", str(source)))
        else:
            spec_type("Rentgen", "Rentgen", source)


@pytest.mark.parametrize("field", ["executable", "config", "sc_executable"])
def test_allowed_reparse_target_is_canonicalized(files, monkeypatch, field):
    from pathlib import Path

    spec_type, installer_type = api()
    source = files[1] if field == "config" else files[0]
    target = source.parent / ("canonical" + source.suffix)
    target.write_text("{}")
    original = Path.resolve
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda self, *args, **kwargs: target
        if self == source
        else original(self, *args, **kwargs),
    )
    if field == "sc_executable":
        installer = installer_type(sc_executable=source)
        spec = spec_type("Rentgen", "Rentgen", files[2])
        assert installer.plan("query", spec).commands[0][0] == str(target)
    elif field == "config":
        spec = spec_type("Rentgen", "Rentgen", files[2], ("--config", str(source)))
        assert spec.arguments[-1] == str(target)
    else:
        spec = spec_type("Rentgen", "Rentgen", source)
        assert spec.executable == str(target)


def test_hardlinks_are_allowed_without_claiming_unique_ownership(files):
    spec_type, installer_type = api()
    executable = files[0].parent / "hardlink.exe"
    executable.hardlink_to(files[0])
    config = files[1].parent / "hardlink.json"
    config.hardlink_to(files[1])
    sc = files[2].parent / "hardlink-sc.exe"
    sc.hardlink_to(files[2])
    spec = spec_type("Rentgen", "Rentgen", executable, ("--config", str(config)))
    plan = installer_type(sc_executable=sc).plan("install", spec)
    assert str(executable) in plan.commands[1][plan.commands[1].index("binPath=") + 1]
    assert plan.commands[0][0] == str(sc)


PYTHON_SERVICE_ARGS = (
    "-I",
    "-m",
    "rentgen_core.service_entry",
    "--service",
    "--config",
)


@pytest.mark.parametrize("basename", ["python.exe", "pythonw.exe", "PYTHON.EXE"])
def test_direct_python_imagepath_is_exact_and_deterministic(files, basename):
    spec_type, installer_type = api()
    directory = files[0].parent / "Python runtime"
    directory.mkdir()
    interpreter = directory / basename
    interpreter.touch()
    config = files[1].with_name("observer settings.json")
    config.write_text('{"password":"private-value"}')
    spec = spec_type(
        "Rentgen.Observer",
        "Rentgen Observer",
        interpreter,
        PYTHON_SERVICE_ARGS + (str(config),),
    )
    expected_args = PYTHON_SERVICE_ARGS + (str(config.resolve()),)
    assert spec.arguments == expected_args
    assert spec.binary_path == '"' + str(
        interpreter.resolve()
    ) + '" ' + subprocess.list2cmdline(expected_args)
    executor = Executor([])
    installer = installer_type(executor=executor, sc_executable=files[2])
    for operation in ("install", "update"):
        plan = installer.plan(operation, spec)
        assert plan == getattr(installer, operation)(spec, dry_run=True)
        assert (
            plan.commands[1][plan.commands[1].index("binPath=") + 1] == spec.binary_path
        )
        assert "private-value" not in repr(plan)
    assert executor.calls == []


@pytest.mark.parametrize(
    "arguments",
    [
        (),
        ("--service",),
        ("--service", "--config", "{config}"),
        ("-m", "rentgen_core.service_entry", "--service", "--config", "{config}"),
        ("-i", "-m", "rentgen_core.service_entry", "--service", "--config", "{config}"),
        ("-I", "-m", "other.module", "--service", "--config", "{config}"),
        ("-I", "-c", "private-value", "--service", "--config", "{config}"),
        ("-I", "-m", "rentgen_core.service_entry", "--console", "--config", "{config}"),
        ("-I", "-m", "rentgen_core.service_entry", "--service", "--config={config}"),
        PYTHON_SERVICE_ARGS + ("{config}", "--service"),
        PYTHON_SERVICE_ARGS + ("{config}", "--password=private-value"),
        ("-I", "-m", "rentgen_core.service_entry", "--config", "{config}", "--service"),
    ],
)
def test_python_rejects_other_flags_modules_and_native_shortcuts(files, arguments):
    spec_type, _ = api()
    interpreter = files[0].with_name("python.exe")
    interpreter.touch()
    args = tuple(value.replace("{config}", str(files[1])) for value in arguments)
    with pytest.raises(CoreError) as raised:
        spec_type("Rentgen", "Rentgen", interpreter, args)
    assert raised.value.code == "SERVICE_SPEC_INVALID"
    assert "private-value" not in str(raised.value.to_dict("test"))


@pytest.mark.parametrize(
    "basename", ["py.exe", "python3.exe", "python-launcher.exe", "service.exe"]
)
def test_python_arguments_require_exact_interpreter_basename(files, basename):
    spec_type, _ = api()
    executable = files[0].with_name(basename)
    executable.touch()
    with pytest.raises(CoreError) as raised:
        spec_type(
            "Rentgen", "Rentgen", executable, PYTHON_SERVICE_ARGS + (str(files[1]),)
        )
    assert raised.value.code == "SERVICE_SPEC_INVALID"


@pytest.mark.parametrize(
    "operation,outcomes,expected",
    [
        ("install", [1060, 0], ["query", "create"]),
        ("update", [0, 0], ["query", "config"]),
    ],
)
def test_python_operations_keep_whole_imagepath_and_revalidate_config(
    files, monkeypatch, operation, outcomes, expected
):
    spec_type, installer_type = api()
    monkeypatch.setattr("rentgen_core.service_installer.sys.platform", "win32")
    interpreter = files[0].with_name("python.exe")
    interpreter.touch()
    spec = spec_type(
        "Rentgen", "Rentgen", interpreter, PYTHON_SERVICE_ARGS + (str(files[1]),)
    )
    executor = Executor(outcomes)
    installer = installer_type(executor=executor, sc_executable=files[2])
    getattr(installer, operation)(spec)
    assert verbs(executor) == expected
    command, options = executor.calls[-1]
    assert command[command.index("binPath=") + 1] == spec.binary_path
    assert options["shell"] is False
    files[1].unlink()
    before = len(executor.calls)
    with pytest.raises(CoreError) as raised:
        getattr(installer, operation)(spec)
    assert raised.value.code == "SERVICE_SPEC_INVALID"
    assert len(executor.calls) == before


@pytest.mark.parametrize("target_name", ["python.exe", "pythonw.exe", "other.exe"])
def test_python_canonical_target_must_also_be_an_interpreter(
    files, monkeypatch, target_name
):
    from pathlib import Path

    spec_type, _ = api()
    directory = files[0].parent / "installed"
    directory.mkdir()
    source = files[0].with_name("python.exe")
    source.touch()
    target = directory / target_name
    target.touch()
    config_target = directory / "canonical.json"
    config_target.touch()
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == source:
            return target
        if path == files[1]:
            return config_target
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    if target_name == "other.exe":
        with pytest.raises(CoreError):
            spec_type(
                "Rentgen", "Rentgen", source, PYTHON_SERVICE_ARGS + (str(files[1]),)
            )
    else:
        spec = spec_type(
            "Rentgen", "Rentgen", source, PYTHON_SERVICE_ARGS + (str(files[1]),)
        )
        assert spec.executable == str(target)
        assert spec.arguments == PYTHON_SERVICE_ARGS + (str(config_target),)


@pytest.mark.parametrize(
    "config_path",
    [
        "relative.json",
        r"\\server\share\settings.json",
        r"\\?\C:\settings.json",
        r"C:\data\..\settings.json",
        r"C:\data\settings.json:stream",
        r"C:\%APPDATA%\settings.json",
        r"C:\data\password=private-value.json",
        "C:\\data\\settings\n.json",
    ],
)
def test_python_config_uses_existing_path_and_sanitization_boundary(files, config_path):
    spec_type, _ = api()
    interpreter = files[0].with_name("python.exe")
    interpreter.touch()
    with pytest.raises(CoreError) as raised:
        spec_type(
            "Rentgen", "Rentgen", interpreter, PYTHON_SERVICE_ARGS + (config_path,)
        )
    assert raised.value.code == "SERVICE_SPEC_INVALID"
    assert "private-value" not in str(raised.value.to_dict("test"))


def test_alias_basename_cannot_enable_python_grammar(files, monkeypatch):
    from pathlib import Path

    spec_type, _ = api()
    target = files[0].with_name("python.exe")
    target.touch()
    original = Path.resolve
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda path, *args, **kwargs: target
        if path == files[0]
        else original(path, *args, **kwargs),
    )
    with pytest.raises(CoreError) as raised:
        spec_type(
            "Rentgen", "Rentgen", files[0], PYTHON_SERVICE_ARGS + (str(files[1]),)
        )
    assert raised.value.code == "SERVICE_SPEC_INVALID"
