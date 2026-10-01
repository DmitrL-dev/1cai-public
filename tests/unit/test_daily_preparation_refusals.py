"""Constructed input refusals; no Core, editor, model or native process runs."""
import importlib.util
import inspect
import json
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest

from scripts.verification import daily_frozen_inputs as frozen
from test_daily_frozen_inputs import fixture, save


def load_prepare(monkeypatch):
    # The preparation script also supports direct execution from its directory.
    monkeypatch.setitem(__import__("sys").modules, "daily_frozen_inputs", frozen)
    path = Path(__file__).parents[2] / "scripts/verification/prepare_daily_platform.py"
    spec = importlib.util.spec_from_file_location("daily_prepare_refusal_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def preparation_inputs(tmp_path, monkeypatch, complete_fixture=False):
    binding = fixture(tmp_path)
    if complete_fixture:
        source = Path(binding["directories"]["fixture"]["path"])
        module_path = source / "CommonModules/RentgenPlatformProbe/Ext/Module.bsl"
        module_path.parent.mkdir(parents=True)
        module_path.write_text("// constructed source\n", encoding="utf-8")
        (source / "Ext").mkdir()
        (source / "Configuration.xml").write_text("<Configuration />\n", encoding="utf-8")
        binding["directories"]["fixture"]["files"] = frozen.directory_inventory(source)
    spec = {role: {key: binding["files"][role][key] for key in ("path", "sha256")}
            for role in ("platform", "ibcmd", "engine")}
    spec["modules"] = [{"name": "ЮТРентгенПроверка", "path": binding["files"]["test_module"]["path"],
                        "tests": ["ОшибкаЗаписиПередается"]}]
    profile = Path(binding["files"]["profile_spec"]["path"])
    profile.write_text(json.dumps(spec), encoding="utf-8")
    binding["files"]["profile_spec"] = frozen.file_record(profile)
    manifest = save(tmp_path, binding)
    module = load_prepare(monkeypatch)
    arguments = {role: Path(binding["files"][role]["path"]) for role in ("python", "scanner", "platform")}
    arguments.update(fixture=Path(binding["directories"]["fixture"]["path"]),
                     diagnostics_root=Path(binding["directories"]["diagnostics"]["path"]),
                     profile_spec=profile, frozen_inputs=manifest)
    return module, binding, arguments


def stub_daily_core(monkeypatch, module, binding, output):
    project_id = "constructed-project"

    def process(args, **_kwargs):
        command = args[5]
        if command == "project-register":
            result = {"project_id": project_id}
        elif command == "test-profile-register":
            registered = output / "state/test-profiles" / binding["profile_id"] / "profile.json"
            registered.parent.mkdir(parents=True)
            registered.write_text(json.dumps({"project_id": project_id}), encoding="utf-8")
            result = {
                "profile_id": binding["profile_id"],
                "enabled": True,
                "modules": [{"sha256": binding["files"]["test_module"]["sha256"]}],
            }
        elif command == "project-head":
            result = {"project_id": project_id}
        else:
            result = {}
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": result}))

    monkeypatch.setattr(module.subprocess, "run", process)


def test_context_tokens_is_an_optional_last_prepare_argument(tmp_path, monkeypatch):
    module = load_prepare(monkeypatch)
    parameters = tuple(inspect.signature(module.prepare).parameters.values())
    assert parameters[-1].name == "context_tokens"
    assert parameters[-1].default == 32768


@pytest.mark.parametrize("context_tokens", [None, 8192, 16384, 32768], ids=["default", "8192", "16384", "32768"])
def test_context_tokens_are_recorded_in_daily_profile_and_scenario(
    tmp_path, monkeypatch, context_tokens
):
    module, binding, arguments = preparation_inputs(tmp_path, monkeypatch, complete_fixture=True)
    output = tmp_path / "prepared"
    stub_daily_core(monkeypatch, module, binding, output)
    options = {} if context_tokens is None else {"context_tokens": context_tokens}
    module.prepare(**arguments, output=output, **options)
    expected = 32768 if context_tokens is None else context_tokens
    profile = json.loads((output / "profile.json").read_text("utf-8"))
    scenario = json.loads((output / "daily-scenario.json").read_text("utf-8"))
    assert type(profile["context_tokens"]) is int
    assert type(scenario["context_tokens"]) is int
    assert profile["context_tokens"] == scenario["context_tokens"] == expected


@pytest.mark.parametrize(
    "context_tokens", [True, False, None, "8192", 8192.0, 8192.5, 0, 4096, 32769]
)
def test_invalid_context_tokens_refuse_before_frozen_verification_or_output(
    tmp_path, monkeypatch, context_tokens
):
    module, _binding, arguments = preparation_inputs(tmp_path, monkeypatch)
    output = tmp_path / "never-created"

    def unexpected_activity(*_args, **_kwargs):
        raise AssertionError("Invalid context tokens reached preparation activity")

    class UnresolvedInput:
        resolve = unexpected_activity

    arguments["python"] = UnresolvedInput()
    monkeypatch.setattr(module, "verify_frozen", unexpected_activity)
    monkeypatch.setattr(module, "require_separate_output", unexpected_activity)
    monkeypatch.setattr(module.subprocess, "run", unexpected_activity)
    with pytest.raises(ValueError):
        module.prepare(**arguments, output=output, context_tokens=context_tokens)
    assert not output.exists()


@pytest.mark.parametrize("context_tokens", [8192, 16384, 32768])
def test_cli_accepts_each_context_choice_before_input_resolution(
    tmp_path, monkeypatch, context_tokens
):
    script = Path(__file__).parents[2] / "scripts/verification/prepare_daily_platform.py"
    missing = tmp_path / "missing-input"
    monkeypatch.setitem(sys.modules, "daily_frozen_inputs", frozen)
    monkeypatch.setattr(
        sys, "argv",
        [str(script)]
        + [part for name in ("python", "scanner", "fixture", "diagnostics-root", "platform", "output", "profile-spec", "frozen-inputs")
           for part in ("--" + name, str(missing))]
        + ["--context-tokens", str(context_tokens)],
    )
    with pytest.raises(FileNotFoundError):
        runpy.run_path(str(script), run_name="__main__")


def test_cli_refuses_unsupported_context_choice_before_input_resolution(tmp_path, monkeypatch, capsys):
    script = Path(__file__).parents[2] / "scripts/verification/prepare_daily_platform.py"
    missing = tmp_path / "missing-input"
    monkeypatch.setitem(sys.modules, "daily_frozen_inputs", frozen)
    monkeypatch.setattr(
        sys, "argv",
        [str(script)]
        + [part for name in ("python", "scanner", "fixture", "diagnostics-root", "platform", "output", "profile-spec", "frozen-inputs")
           for part in ("--" + name, str(missing))]
        + ["--context-tokens", "4096"],
    )
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(script), run_name="__main__")
    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    assert not missing.exists()


def test_unreadable_unlisted_subtree_refuses_incomplete_inventory(tmp_path, monkeypatch):
    root = tmp_path / "input"
    root.mkdir()
    (root / "known.txt").write_bytes(b"known")
    expected = frozen.directory_inventory(root)
    blocked = root / "unlisted-denied"
    blocked.mkdir()
    original = os.scandir

    def scandir(path):
        if Path(path) == blocked:
            raise PermissionError("constructed subtree enumeration denied")
        return original(path)

    monkeypatch.setattr(os, "scandir", scandir)
    with pytest.raises(PermissionError, match="constructed subtree"):
        frozen.directory_inventory(root)
    assert set(expected) == {"known.txt"}


def test_directory_iterator_failure_refuses_partial_inventory(tmp_path, monkeypatch):
    root = tmp_path / "input"
    root.mkdir()
    for name in ("first.txt", "second.txt"):
        (root / name).write_bytes(b"known")
    original = os.scandir

    class BrokenIterator:
        def __init__(self, path):
            self.stream = original(path)
            self.first = True

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def __iter__(self):
            return self

        def __next__(self):
            if self.first:
                self.first = False
                return next(self.stream)
            raise OSError("constructed enumeration interrupted")

    monkeypatch.setattr(os, "scandir", BrokenIterator)
    with pytest.raises(OSError, match="constructed enumeration interrupted"):
        frozen.directory_inventory(root)


@pytest.mark.parametrize("role", sorted(frozen.DIRECTORIES))
def test_frozen_directory_child_refuses_before_any_write_or_process(tmp_path, monkeypatch, role):
    module, binding, arguments = preparation_inputs(tmp_path, monkeypatch)
    output = Path(binding["directories"][role]["path"]) / "never-created"
    effects = []
    original_mkdir = Path.mkdir

    def mkdir(path, *args, **kwargs):
        if path == output:
            effects.append("mkdir")
            raise AssertionError("overlap reached output write")
        return original_mkdir(path, *args, **kwargs)

    def process(*args, **kwargs):
        effects.append("process")
        raise AssertionError("overlap reached process launch")

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(module.subprocess, "run", process)
    with pytest.raises(ValueError, match="INPUT_BINDING_MISMATCH"):
        module.prepare(**arguments, output=output)
    assert effects == [] and not output.exists()


def test_parent_segments_do_not_hide_output_overlap(tmp_path, monkeypatch):
    module, binding, arguments = preparation_inputs(tmp_path, monkeypatch)
    root = Path(binding["directories"]["diagnostics"]["path"])
    output = root / ".." / root.name / "never-created"
    with pytest.raises(ValueError, match="INPUT_BINDING_MISMATCH"):
        module.prepare(**arguments, output=output)
    assert not output.exists()


def test_separate_new_output_remains_eligible_without_launching_a_process(tmp_path, monkeypatch):
    module, binding, arguments = preparation_inputs(tmp_path, monkeypatch)
    output = tmp_path / "separate-output"
    copied = []

    def stop_copy(source, target):
        copied.append((source, target))
        raise RuntimeError("constructed stop before copying or launch")

    def process(*args, **kwargs):
        raise AssertionError("no product process is permitted in this test")

    monkeypatch.setattr(module.shutil, "copytree", stop_copy)
    monkeypatch.setattr(module.subprocess, "run", process)
    with pytest.raises(RuntimeError, match="constructed stop"):
        module.prepare(**arguments, output=output)
    assert output.is_dir() and list(output.iterdir()) == []
    assert copied == [(Path(binding["directories"]["fixture"]["path"]), output / "source")]
