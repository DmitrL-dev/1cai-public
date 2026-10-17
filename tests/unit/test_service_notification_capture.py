"""Windows capture -> owner-report event -> explicit delivery -> ack recovery.

Real source/Git/Observer/scanner/lease/storage; injected BSL and HTTPS adapters.
No live endpoint, native SCM or 1C qualification is claimed.
"""
import io
import json
from threading import Event

import pytest

from rentgen_core import service_entry
from rentgen_core.notification_delivery import WebhookAdapter
from rentgen_core.notification_journal import DeliveryJournal
from rentgen_core.owner_report_store import OwnerReportStore
import test_service_composition as fixtures

configured, scanner = fixtures.configured, fixtures.scanner
project, workspace = fixtures.project, fixtures.workspace
pytestmark = fixtures.pytestmark


@pytest.mark.parametrize("schema,trusted", [(2, False), (3, False), (3, True)])
def test_service_generated_owner_event_recovers_ack_after_worker_restart(
    configured, workspace, monkeypatch, scanner, schema, trusted,
):
    if schema == 2:
        observer, source, module, snapshot, analyzer = fixtures.wire(configured, workspace, monkeypatch)
    else:
        observer, source, module, snapshot, analyzer = fixtures.autonomous(configured, workspace, monkeypatch, scanner)
    document = json.loads(configured.path.read_text())
    document.update(schema=schema, max_cycles=1, trust_registered_source=trusted)
    configured.path.write_text(json.dumps(document), encoding="utf-8")
    config = service_entry.load_config(configured.path)
    assert config.max_cycles == 1
    original = module.read_bytes()
    worker = service_entry.create_worker(config)
    sent = []
    def sender(request, *, timeout):
        sent.append(json.loads(request.data))
        result = io.BytesIO(b"")
        result.status = 204
        host.stop()
        return result
    adapter = WebhookAdapter(
        "https://hooks.example.test/events", allowed_hosts={"hooks.example.test"},
        namespace="capture-generation-a", sender=sender,
    )
    try:
        host = worker.notification_host(adapter)
        assert worker.run(Event()) == 1 and sent == []
        event = worker.outbox.peek()[0]["event"]
        assert event["status"] == "analyzed" and event["owner_report_id"]
        snapshot = observer.status()["last_snapshot"]
        store = OwnerReportStore(observer.runtime.registry.get(observer.project_id).state_root / "owner-reports")
        receipt = store.get(event["owner_report_id"], expected_project_id=observer.project_id,
                            expected_snapshot_id=snapshot, authorize=lambda: observer._context(write=True))
        assert receipt["report"]["quality"]["provenance"] == "git_source_verified"
        assert host.run() == 0 and sent[0]["event"] == event
        assert len(worker.outbox.peek()) == 1
        assert DeliveryJournal(observer.profile / "notification-delivery.json",
                               namespace="capture-generation-a").records()[0].state == "accepted"
    finally:
        worker.close()
    restarted = service_entry.create_worker(config)
    try:
        recovered = restarted.notification_host(adapter)
        assert recovered.run() == 1 and len(sent) == 1
        assert recovered.last_results[0].code == "ACK_RECOVERED"
        assert restarted.outbox.peek() == []
        assert module.read_bytes() == original and analyzer.calls
    finally:
        restarted.close()
    with observer.locked():
        pass
