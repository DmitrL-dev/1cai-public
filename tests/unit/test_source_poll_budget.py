"""Pure wait-budget arithmetic, separate from real measured polling acceptance.

The supplied clock values test calculation only. They do not simulate native
execution, qualify actual <=100 ms intervals, or relax the four live oracles.
"""
import pytest

from rentgen_core import rust_input


@pytest.mark.parametrize("started,now,deadline,expected", [
    pytest.param(200.0, 200.012, 201.0, .038, id="elapsed_work_is_subtracted"),
    pytest.param(200.0, 200.012, 200.025, .013, id="operation_deadline_caps_wait"),
    pytest.param(200.0, 200.075, 201.0, 0.0, id="iteration_overrun_is_zero"),
    pytest.param(200.0, 200.012, 200.010, 0.0, id="expired_deadline_is_not_negative"),
])
def test_source_poll_budget_arithmetic(monkeypatch, started, now, deadline, expected):
    monkeypatch.setattr(rust_input.time, "monotonic", lambda: now)
    wait = rust_input._poll_wait_timeout(deadline, started)
    assert wait == pytest.approx(expected, abs=1e-12)
    assert 0 <= wait <= .05
    assert wait <= max(0, deadline - now)
