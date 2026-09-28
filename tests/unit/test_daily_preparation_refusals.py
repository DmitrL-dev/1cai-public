"""Constructed input refusals; no Core, editor, model or native process runs."""
import importlib.util
import json
import os
from pathlib import Path

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


def preparation_inputs(tmp_path, monkeypatch):
    binding = fixture(tmp_path)
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
