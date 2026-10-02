"""READY intent is unavailable until an authoritative Root owner exists."""
from types import SimpleNamespace

import pytest

from scripts.verification import run_daily_semantic_editor_host as host


@pytest.mark.parametrize("claim", [None, {"accepted": True}, {"pid": 42, "nonce": "warm", "handle": 123}])
def test_ready_intent_denies_before_input_read_or_legacy_launch(monkeypatch, claim):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("READY intent must refuse before filesystem or process work")

    monkeypatch.setattr(host, "verify_frozen", forbidden)
    monkeypatch.setattr(host, "extract", forbidden)
    monkeypatch.setattr(host.subprocess, "Popen", forbidden)
    # Incomplete paths are deliberate: the owner refusal must precede their use.
    args = SimpleNamespace(mode="ready-intent-only", prior=None, frozen_inputs=None,
                           editor_owner=claim)
    with pytest.raises(ValueError, match="^DAILY_ROOT_EDITOR_OWNER_REQUIRED$"):
        host.run(args)
    assert calls == []


def test_unknown_mode_denies_before_input_read(monkeypatch):
    def forbidden(*_):
        raise AssertionError("Unknown mode reached frozen-input work")

    monkeypatch.setattr(host, "verify_frozen", forbidden)
    with pytest.raises(ValueError, match="^DAILY_MODE_INVALID$"):
        host.run(SimpleNamespace(mode="typo", prior=None, frozen_inputs=None))
