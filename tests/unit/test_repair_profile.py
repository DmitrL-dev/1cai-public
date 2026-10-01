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


@pytest.mark.parametrize(
    "core", ["0.1.0.dev7", "0.1.0.dev8", "0.1.0.dev9", "0.1.0.dev10", "0.1.0.dev11", "0.1.0.dev12", "0.1.0.dev13", "0.1.0.dev14", "0.1.0.dev15", "0.1.0.dev16"]
)
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
            {"schema": 1, "core_version": "0.1.0.dev999", "python": sys.executable},
            "0.1.0.dev999",
            "1.30.0",
            sys.executable,
        )


@pytest.mark.parametrize("context_tokens", [None, 8192, 16384, 32768])
def test_profile_context_tokens_is_resolved(adapter, context_tokens):
    config = {"schema": 1, "core_version": "0.1.0.dev16", "python": sys.executable}
    if context_tokens is not None:
        config["context_tokens"] = context_tokens
    assert adapter.validate_profile(config, "0.1.0.dev16", "1.30.0", sys.executable) == (
        32768 if context_tokens is None else context_tokens
    )


@pytest.mark.parametrize("value", [True, None, "8192", 8192.0, 12288])
def test_invalid_profile_context_is_rejected(adapter, value):
    config = {"schema": 1, "core_version": "0.1.0.dev16", "python": sys.executable,
              "context_tokens": value}
    with pytest.raises(ValueError, match="^INVALID_CONTEXT_TOKENS$"):
        adapter.validate_profile(config, "0.1.0.dev16", "1.30.0", sys.executable)


def test_cli_context_must_match_profile_before_activity(adapter):
    config = {"schema": 1, "core_version": "0.1.0.dev16", "python": sys.executable,
              "context_tokens": 8192}
    with pytest.raises(ValueError, match="^CONTEXT_TOKENS_MISMATCH$"):
        adapter.validate_profile(config, "0.1.0.dev16", "1.30.0", sys.executable,
                                 expected_context_tokens=16384)
