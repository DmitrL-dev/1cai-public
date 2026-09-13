"""An owned retained register can produce only complete, pinned owner evidence."""

from dataclasses import FrozenInstanceError
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.owner_report_store import OwnerReportStore


PROJECT = "12345678-1234-5678-1234-567812345678"
SNAPSHOT = "b" * 64
COMMIT = "a" * 40
REGISTER = "InformationRegister.OwnerIndicators"
SOURCE = "owned-owner-indicators"
START = "2026-09-01T00:00:00Z"
END = "2026-09-07T23:59:59Z"
AS_OF = "2026-09-08T00:00:00Z"
DIGEST = "448d67f970911ba5bfb53a595730b61538a3fe0d3169031d6baab16eb164e496"
FIXTURE = (
    Path(__file__).parents[2]
    / "packaging/fixtures/runtime-register-v1/owner-indicators.json"
)


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def payload():
    return json.loads(FIXTURE.read_bytes())


def reseal(data):
    data["metrics"] = [
        {**{k: v for k, v in row.items() if k != "row_id"}, "source_id": REGISTER}
        for row in data["rows"]
    ]
    data["source_digest"] = hashlib.sha256(
        canonical(sorted(data["rows"], key=lambda row: row["row_id"]))
    ).hexdigest()


def configured(tmp_path, data=None, **overrides):
    module = importlib.import_module("rentgen_core.runtime_producer")
    path = tmp_path / "export.json"
    path.write_bytes(canonical(payload() if data is None else data))
    store = OwnerReportStore(tmp_path / "receipts")
    store.initialize()
    options = dict(
        source_id=SOURCE,
        export_path=path,
        project_id=PROJECT,
        snapshot_id=SNAPSHOT,
        commit=COMMIT,
        source_digest=DIGEST,
        register_id=REGISTER,
        source_ref="exports/owner-indicators.json",
        period_start=START,
        period_end=END,
        metric_ids=("orders_count", "revenue_amount"),
    )
    options.update(overrides)
    source = module.RetainedRegisterSource(**options)
    producer = module.RetainedRegisterProducer(source, store)
    return producer, source, store


def produce(producer, **options):
    return producer.produce(SOURCE, authorize=lambda: None, as_of=AS_OF, **options)


def test_owned_fixture_produces_canonical_immutable_owner_receipt(
    tmp_path, monkeypatch
):
    producer, source, store = configured(tmp_path)
    original = source.export_path.read_bytes()

    def prohibited(*args, **kwargs):
        pytest.fail("A retained producer must not execute processes or use sockets")

    monkeypatch.setattr("socket.socket", prohibited)
    monkeypatch.setattr("subprocess.Popen", prohibited)
    receipt = produce(producer)
    business = receipt["report"]["business_metrics"]
    assert business["status"] == "available"
    assert [metric["value"] for metric in business["metrics"]] == [42, 1250.5]
    assert business["source"]["source_digest"] == DIGEST
    assert business["source"]["commit"] == COMMIT
    assert all(metric["source_id"] == REGISTER for metric in business["metrics"])
    assert (
        receipt["receipt_id"]
        == hashlib.sha256(
            canonical({k: v for k, v in receipt.items() if k != "receipt_id"})
        ).hexdigest()
    )
    assert source.export_path.read_bytes() == original
    stored = store.get(
        receipt["report_id"],
        expected_project_id=PROJECT,
        expected_snapshot_id=SNAPSHOT,
        authorize=lambda: None,
    )
    assert stored == receipt
    changed = json.loads(json.dumps(receipt["report"]))
    changed["business_metrics"]["metrics"][0]["value"] = 999
    with pytest.raises(CoreError, match="already contains"):
        store.save(changed, report_id=receipt["report_id"], authorize=lambda: None)
    assert (
        store.get(
            receipt["report_id"],
            expected_project_id=PROJECT,
            expected_snapshot_id=SNAPSHOT,
            authorize=lambda: None,
        )
        == receipt
    )
    with pytest.raises(FrozenInstanceError):
        source.source_digest = "d" * 64


@pytest.mark.parametrize(
    "source_id", ["other", "../export.json", "https://invalid/export", SOURCE + "/x"]
)
def test_only_preconfigured_source_can_be_selected(tmp_path, monkeypatch, source_id):
    producer, _, store = configured(tmp_path)
    monkeypatch.setattr(
        "rentgen_core.runtime_source.read_retained",
        lambda *args: pytest.fail("Unapproved source must never be read"),
    )
    with pytest.raises(CoreError) as error:
        producer.produce(source_id, authorize=lambda: None, as_of=AS_OF)
    assert error.value.code == "OWNER_RUNTIME_PRODUCER_SOURCE"
    assert list(store.reports.iterdir()) == []


@pytest.mark.parametrize("kind", ["missing", "empty", "declared", "partial", "extra"])
def test_incomplete_or_wrong_indicator_inventory_never_creates_receipt(tmp_path, kind):
    data = payload()
    if kind == "missing":
        data["rows"].pop()
    elif kind == "empty":
        data["rows"] = []
    elif kind == "declared":
        data["complete"] = False
    elif kind == "partial":
        data["rows"][0]["period_start"] = "2026-09-02T00:00:00Z"
    else:
        data["rows"].append(
            {**data["rows"][0], "row_id": "extra", "metric_id": "extra"}
        )
    reseal(data)
    producer, _, store = configured(tmp_path, data, source_digest=data["source_digest"])
    with pytest.raises(CoreError) as error:
        produce(producer)
    assert error.value.code == "OWNER_RUNTIME_PRODUCER_INCOMPLETE"
    assert list(store.reports.iterdir()) == []


@pytest.mark.parametrize("self_consistent", [False, True])
def test_tampered_rows_fail_even_if_export_is_self_consistent(
    tmp_path, self_consistent
):
    data = payload()
    data["rows"][0]["value"] = 999
    data["metrics"][0]["value"] = 999
    if self_consistent:
        reseal(data)
    producer, _, store = configured(tmp_path, data)
    with pytest.raises(CoreError) as error:
        produce(producer)
    assert error.value.code == (
        "OWNER_RUNTIME_CONTEXT" if self_consistent else "OWNER_RUNTIME_SOURCE_DIGEST"
    )
    assert list(store.reports.iterdir()) == []


def test_export_with_different_complete_period_is_rejected(tmp_path):
    data = payload()
    data["period_start"] = "2026-09-02T00:00:00Z"
    for row in data["rows"]:
        row["period_start"] = data["period_start"]
    reseal(data)
    producer, _, store = configured(tmp_path, data, source_digest=data["source_digest"])
    with pytest.raises(CoreError) as error:
        produce(producer)
    assert error.value.code == "OWNER_RUNTIME_PERIOD"
    assert list(store.reports.iterdir()) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("project_id", "87654321-4321-8765-4321-876543218765"),
        ("snapshot_id", "d" * 64),
        ("commit", "d" * 40),
        ("register_id", "InformationRegister.Other"),
        ("source_ref", "exports/other.json"),
    ],
)
def test_every_trusted_context_pin_is_enforced(tmp_path, field, value):
    producer, _, store = configured(tmp_path, **{field: value})
    with pytest.raises(CoreError) as error:
        produce(producer)
    assert error.value.code == "OWNER_RUNTIME_CONTEXT"
    assert list(store.reports.iterdir()) == []


@pytest.mark.parametrize("at_call", range(1, 7))
def test_authorization_revocation_never_returns_a_receipt(tmp_path, at_call):
    producer, _, store = configured(tmp_path)
    calls = []
    denied = CoreError("ACCESS_DENIED", "Revoked")

    def authorize():
        calls.append(None)
        if len(calls) == at_call:
            raise denied

    with pytest.raises(CoreError) as error:
        producer.produce(SOURCE, authorize=authorize, as_of=AS_OF)
    assert error.value is denied
    assert len(calls) == at_call
    if at_call < 6:
        assert list(store.reports.iterdir()) == []
    else:
        # The existing store checks authorization again after its immutable write.
        # Revocation denies the returned result but does not delete stored history.
        assert len(list(store.reports.iterdir())) == 1


@pytest.mark.parametrize("at_call", [4, 5])
def test_freshness_is_rechecked_after_delayed_consumer_authorization(
    tmp_path, monkeypatch, at_call
):
    from datetime import datetime

    producer, _, store = configured(tmp_path)
    clock = [AS_OF]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(clock[0])

    monkeypatch.setattr("rentgen_core.runtime_metrics.datetime", Clock)
    calls = []

    def authorize():
        calls.append(None)
        if len(calls) == at_call:
            clock[0] = "2026-09-10T00:00:00Z"

    with pytest.raises(CoreError) as error:
        producer.produce(SOURCE, authorize=authorize)
    assert error.value.code == "OWNER_RUNTIME_STALE"
    assert list(store.reports.iterdir()) == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"metric_ids": ()},
        {"metric_ids": ("orders_count", "orders_count")},
        {"metric_ids": ["orders_count"]},
        {"period_start": None},
        {"period_end": None},
    ],
)
def test_missing_or_mutable_expected_inventory_and_period_are_rejected(
    tmp_path, overrides
):
    with pytest.raises(CoreError) as error:
        configured(tmp_path, **overrides)
    assert error.value.code == "OWNER_RUNTIME_PRODUCER_INVALID"
