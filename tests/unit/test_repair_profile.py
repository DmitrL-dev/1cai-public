"""The editor profile and installed repair runtime must agree exactly."""
import importlib.util
from pathlib import Path
import sys

import pytest


@pytest.fixture
def adapter(monkeypatch):
    folder = Path(__file__).resolve().parents[2] / "integrations/open-editor"
    monkeypatch.syspath_prepend(str(folder))
    spec = importlib.util.spec_from_file_location(
        "repair_adapter_contract", folder / "run_repair.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("core", ["0.1.0.dev7", "0.1.0.dev8"])
def test_matching_supported_runtime_is_accepted(adapter, core):
    config = {"schema": 1, "core_version": core, "python": sys.executable}
    adapter.validate_profile(config, core, "1.30.0", sys.executable)


@pytest.mark.parametrize(
    "field,value",
    [("core", "0.1.0.dev7"), ("mcp", "1.29.0"), ("python", "C:/other/python.exe")],
)
def test_different_runtime_is_not_silently_used(adapter, field, value):
    config = {"schema": 1, "core_version": "0.1.0.dev8", "python": sys.executable}
    actual = {"core": "0.1.0.dev8", "mcp": "1.30.0", "python": sys.executable}
    actual[field] = value
    with pytest.raises(ValueError):
        adapter.validate_profile(
            config, actual["core"], actual["mcp"], actual["python"]
        )


def test_unsupported_profile_is_refused(adapter):
    with pytest.raises(ValueError):
        adapter.validate_profile(
            {"schema": 1, "core_version": "0.1.0.dev9", "python": sys.executable},
            "0.1.0.dev9",
            "1.30.0",
            sys.executable,
        )
