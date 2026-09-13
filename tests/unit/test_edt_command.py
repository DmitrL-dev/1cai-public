"""The fixture planner must not expose database mutation or a process launcher."""
from dataclasses import replace

import pytest

from rentgen_core import edt_command as api
from rentgen_core.errors import CoreError


@pytest.fixture
def profile():
    return api.IBCmdProfile(
        executable=r"C:\Program Files\1cv8\8.3.27.2342\bin\ibcmd.exe",
        version="8.3.27.2342",
        sha256="a" * 64,
    )


@pytest.fixture
def intent():
    return api.FixtureCommandRequest(
        operation_id="b5cd00b8-d2d7-4d32-bec4-ef135b676244",
        input_digest="b" * 64,
    )


def test_fixture_plan_has_only_file_import_and_export_commands(profile, intent):
    plan = api.plan_fixture_commands(profile, intent, fixture_root=r"C:\Owned fixture")
    run = r"C:\Owned fixture\ibcmd-fixtures" + "\\" + intent.operation_id
    common = (
        profile.executable,
        "config",
    )
    paths = (f"--data={run}\\data", f"--db-path={run}\\unused-infobase")
    assert plan.commands[0].argv == (
        *common,
        "import",
        *paths,
        f"--out={run}\\candidate.cf",
        run + r"\input",
    )
    assert plan.commands[1].argv == (
        *common,
        "export",
        *paths,
        f"--file={run}\\candidate.cf",
        "--threads=1",
        run + r"\roundtrip",
    )
    assert plan.execution_allowed is False
    assert plan.live_apply_allowed is False
    assert plan.input_digest == intent.input_digest
    assert plan.platform_sha256 == profile.sha256
    assert plan.commands[0].cwd == run
    assert plan.commands[1].cwd == run
    assert all(command.timeout_seconds == 120 for command in plan.commands)
    assert all(command.max_output_bytes == 2 * 1024**2 for command in plan.commands)
    assert all(command.shell is False for command in plan.commands)


@pytest.mark.parametrize(
    "root",
    [
        "relative",
        "C:",
        "C:\\",
        r"C:relative",
        r"\\server\share\fixture",
        r"\\?\C:\fixture",
        r"C:\fixture\..\user",
        r"C:\fixture\.\run",
        r"C:\fixture\NUL",
        r"C:\fixture\name.",
        r"C:\fixture\name ",
        r"C:\fixture\stream:other",
        r'C:\fixture\"quoted"',
        "C:\\fixture\nother",
        "C:\\" + "x" * 1024,
        None,
    ],
)
def test_rejects_ambiguous_or_unbounded_windows_roots(profile, intent, root):
    with pytest.raises(CoreError, match="Invalid ibcmd fixture"):
        api.plan_fixture_commands(profile, intent, fixture_root=root)


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", "8.3.26.1000"),
        ("sha256", "A" * 64),
        ("sha256", "a" * 63),
        ("sha256", None),
        ("executable", r"C:\Tools\1cv8.exe"),
        ("executable", "ibcmd.exe"),
        ("executable", r"\\server\tools\ibcmd.exe"),
    ],
)
def test_rejects_unqualified_platform_profiles(profile, intent, field, value):
    with pytest.raises(CoreError, match="Invalid ibcmd fixture"):
        api.plan_fixture_commands(
            replace(profile, **{field: value}), intent, fixture_root=r"C:\Fixture"
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("operation_id", "../user"),
        ("operation_id", "B5CD00B8-D2D7-4D32-BEC4-EF135B676244"),
        ("operation_id", None),
        ("input_digest", ""),
        ("input_digest", "b" * 65),
        ("input_digest", 1),
    ],
)
def test_rejects_invalid_intent(profile, intent, field, value):
    with pytest.raises(CoreError, match="Invalid ibcmd fixture"):
        api.plan_fixture_commands(
            profile, replace(intent, **{field: value}), fixture_root=r"C:\Fixture"
        )


class FakeExecutor:
    """A consumer that records argv, without launching or writing anything."""

    def __init__(self):
        self.commands = []

    def inspect(self, plan, profile, intent):
        validated = api.validate_fixture_commands(
            plan, profile, intent, fixture_root=r"C:\Fixture"
        )
        self.commands.extend(command.argv for command in validated.commands)


@pytest.mark.parametrize("tamper", ["argv", "grant", "digest", "timeout", "shell"])
def test_fake_executor_receives_nothing_after_plan_tampering(profile, intent, tamper):
    assert hasattr(api, "validate_fixture_commands")
    plan = api.plan_fixture_commands(profile, intent, fixture_root=r"C:\Fixture")
    if tamper == "argv":
        command = replace(
            plan.commands[0], argv=(profile.executable, "config", "apply")
        )
        plan = replace(plan, commands=(command, plan.commands[1]))
    elif tamper == "grant":
        plan = replace(plan, execution_allowed=True)
    elif tamper == "digest":
        plan = replace(plan, input_digest="c" * 64)
    elif tamper == "timeout":
        command = replace(plan.commands[0], timeout_seconds=9999)
        plan = replace(plan, commands=(command, plan.commands[1]))
    else:
        command = replace(plan.commands[0], shell=True)
        plan = replace(plan, commands=(command, plan.commands[1]))
    executor = FakeExecutor()
    with pytest.raises(CoreError, match="Invalid ibcmd fixture"):
        executor.inspect(plan, profile, intent)
    assert executor.commands == []


def test_fake_executor_can_inspect_exact_plan_without_running_processes(
    profile, intent
):
    assert hasattr(api, "validate_fixture_commands")
    plan = api.plan_fixture_commands(profile, intent, fixture_root=r"C:\Fixture")
    executor = FakeExecutor()
    executor.inspect(plan, profile, intent)
    assert executor.commands == [command.argv for command in plan.commands]
    assert plan.execution_allowed is False
