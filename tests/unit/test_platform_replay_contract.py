"""Portable replay classification; injected reads are not Windows acceptance."""
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from types import SimpleNamespace

import pytest

from rentgen_core import platform_runs, test_execution
from rentgen_core.errors import CoreError


OPERATION = "22222222-2222-4222-8222-222222222222"


@dataclass(frozen=True)
class Ref:
    relative_path: str = "Module.bsl"


@pytest.fixture(params=["platform", "tests"])
def replay(request, tmp_path, monkeypatch):
    proposal = SimpleNamespace(source_ref=Ref(), content_id="proposal")
    binding = {"source_ref": asdict(proposal.source_ref),
               "proposal_content_id": proposal.content_id, "profile_id": "profile"}
    folder = tmp_path / "retained"
    folder.mkdir()
    marker = folder / "request.tmp"
    marker.write_bytes(b"unfinished request")
    ctx = SimpleNamespace()

    def forbidden(*args, **kwargs):
        pytest.fail("Replay reached profile lookup, admission or execution")

    monkeypatch.setattr(test_execution, "authorized", lambda ctx: nullcontext())
    monkeypatch.setattr(test_execution, "parse_proposal", lambda *a, **kw: proposal)
    monkeypatch.setattr(test_execution, "run_path", lambda *a, **kw: folder)
    for name in ("get_profile", "reserve_run", "run_yaxunit"):
        monkeypatch.setattr(test_execution, name, forbidden)

    def invoke(saved):
        monkeypatch.setattr(platform_runs, "get_platform_run", lambda *a, **kw: saved)
        monkeypatch.setattr(test_execution, "get_platform_run", lambda *a, **kw: saved)
        try:
            if request.param == "platform":
                return platform_runs.replay_run(ctx, OPERATION, binding)
            return test_execution.check_proposal_tests(
                ctx, b"injected proposal", "profile", OPERATION, limits=None
            )
        finally:
            assert list(folder.iterdir()) == [marker]
            assert marker.read_bytes() == b"unfinished request"

    return invoke, binding


def test_missing_request_incomplete_is_not_an_input_conflict(replay):
    invoke, _ = replay
    saved = {"run_id": OPERATION, "status": "incomplete", "request": None}
    for _ in range(2):
        with pytest.raises(CoreError) as error:
            invoke(saved)
        assert error.value.code == "PLATFORM_RUN_INCOMPLETE"
        assert error.value.details == {
            "run_id": OPERATION, "status": "incomplete", "request_recorded": False,
        }


def test_legacy_completed_without_request_still_cannot_replay(replay):
    invoke, _ = replay
    with pytest.raises(CoreError) as error:
        invoke({"run_id": OPERATION, "status": "completed", "request": None,
                "report": {"legacy": True}})
    assert error.value.code == "PLATFORM_RUN_CONFLICT"


@pytest.mark.parametrize("status", ["completed", "failed", "incomplete"])
def test_bound_replay_preserves_terminal_and_nonterminal_behavior(replay, status):
    invoke, binding = replay
    report = {"retained": True}
    saved = {"run_id": OPERATION, "status": status,
             "request": {"input": binding}, "report": report}
    if status == "completed":
        assert invoke(saved) is report
    else:
        with pytest.raises(CoreError) as error:
            invoke(saved)
        assert error.value.code == "PLATFORM_RUN_INCOMPLETE"
        assert error.value.details == {"run_id": OPERATION, "status": status}


@pytest.mark.parametrize("field", ["source_ref", "proposal_content_id", "profile_id"])
def test_known_different_inputs_remain_conflicts(replay, field):
    invoke, binding = replay
    with pytest.raises(CoreError) as error:
        invoke({"run_id": OPERATION, "status": "incomplete",
                "request": {"input": {**binding, field: "different"}}})
    assert error.value.code == "PLATFORM_RUN_CONFLICT"
