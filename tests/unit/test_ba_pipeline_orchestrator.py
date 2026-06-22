import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.ba_pipeline.orchestrator import (
    available_collectors,
    instantiate_collectors,
    run_pipeline,
)


def test_available_collectors_contains_expected():
    registry = available_collectors()
    assert {
        "job_market",
        "conference_digest",
        "regulation_watcher",
        "internal_usage",
    } <= set(registry.keys())


def test_instantiate_collectors_subset():
    collectors = instantiate_collectors(["job_market", "regulation_watcher"])
    names = [collector.name for collector in collectors]
    assert names == ["job_market", "regulation_watcher"]


def test_run_pipeline_creates_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    output_dir = tmp_path / "ba_data"
    monkeypatch.setenv("BA_PIPELINE_OUTPUT_DIR", str(output_dir))

    # provide sample market sources via env
    monkeypatch.setenv(
        "BA_MARKET_SOURCES",
        json.dumps(
            [
                {
                    "platform": "hh.ru",
                    "title": "Business Analyst 1C",
                    "location": "Москва",
                    "skills": ["1C", "SQL"],
                    "level": "Senior",
                    "posted_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        ),
    )

    since = datetime.now(timezone.utc) - timedelta(days=7)
    summary = run_pipeline(output_dir=output_dir, since=since)

    assert summary["output_dir"] == str(output_dir)
    collector_payloads = {item["collector"]: item for item in summary["collectors"]}
    assert collector_payloads["job_market"]["records_count"] >= 1
    assert Path(collector_payloads["job_market"]["output_file"]).exists()
    assert Path(collector_payloads["conference_digest"]["output_file"]).exists()
    assert Path(collector_payloads["regulation_watcher"]["output_file"]).exists()
    assert Path(collector_payloads["internal_usage"]["output_file"]).exists()
