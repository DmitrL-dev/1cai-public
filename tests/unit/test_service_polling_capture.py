"""Windows real capture/lease/restart; injected BSL adapter, no SCM or 1C."""
from datetime import timedelta
import json

import pytest

from rentgen_core import observer as implementation, service_entry
from rentgen_core.observer import Observer
from test_observer_polling import T0
import test_service_composition as fixtures

configured, scanner = fixtures.configured, fixtures.scanner
project, workspace = fixtures.project, fixtures.workspace
pytestmark = fixtures.pytestmark


@pytest.mark.parametrize("schema,trusted", [(1, False), (3, False), (3, True)])
def test_real_service_capture_restart_records_gap_without_reanalysis(
    configured, workspace, monkeypatch, scanner, schema, trusted,
):
    observer, _, module, _, adapter = fixtures.autonomous(configured, workspace, monkeypatch, scanner)
    document = json.loads(configured.path.read_text(encoding="utf-8"))
    document.update(schema=schema, interval_seconds=60, max_cycles=1)
    if schema == 1:
        del document["diagnostics_root"]
        del document["mode"]
    else:
        document["trust_registered_source"] = trusted
    configured.path.write_text(json.dumps(document), encoding="utf-8")
    assert service_entry.load_config(configured.path).max_cycles == 1
    now = [T0]
    monkeypatch.setattr(implementation, "_utcnow", lambda: now[0])
    original = module.read_bytes()
    first = service_entry.run_console(configured.path)
    assert (first.exit_code, first.cycles) == (0, 1)
    status = observer.status()
    assert status["polling"]["interval_seconds"] == 60
    assert status["polling"]["gap_count"] == 0
    assert status["polling"]["on_schedule"] is True
    snapshot = status["last_snapshot"]
    calls = len(adapter.calls)
    now[0] += timedelta(seconds=120)
    second = service_entry.run_console(configured.path)
    assert (second.exit_code, second.cycles) == (0, 1)
    retained = Observer(observer.runtime, observer.principal, observer.project_id, observer.profile)
    status = retained.status()
    assert status["polling"]["gap_count"] == 1
    assert status["polling"]["last_gap"]["idle_seconds"] == 120
    assert status["polling"]["on_schedule"] is True
    assert status["last_snapshot"] == snapshot and len(status["jobs"]) == 1
    assert len(adapter.calls) == calls and module.read_bytes() == original
    with retained.locked():
        pass
