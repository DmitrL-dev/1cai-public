from __future__ import annotations

import pytest

from src.services.rentgen.lock_radar import build_lock_radar


LOCK_TJ = """12:00:02.000000-200000,TLOCK,p:1:1:1,Usr=Admin,Context='CommonModule.Sales.Module : 50 : Write()'
12:00:03.000000-0,TDEADLOCK,p:1:1:1,Usr=Admin,Context='CommonModule.Sales.Module : 60 : Post()'
12:00:04.000000-3000000,TTIMEOUT,p:1:1:1,Usr=Batch,Context='Document.Order.ObjectModule : 100 : Movements.Write()'
"""


def test_lock_radar_detects_lock_timeout_and_deadlock(tmp_path):
    log_file = tmp_path / "rphost_1" / "26022200.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_text(LOCK_TJ, encoding="utf-8")

    report = build_lock_radar(
        log_path=str(log_file.parent.parent),
        changed_modules=["CommonModule.Sales.Module"],
    )

    assert report["source"]["available"] is True
    assert report["decision"]["status"] == "critical"
    assert report["decision"]["risk_score"] > 0
    assert report["summary"]["lock_waits"] == 1
    assert report["summary"]["timeouts"] == 1
    assert report["summary"]["deadlocks"] == 1
    assert report["summary"]["modules"] == 2
    assert report["events"][0]["kind"] == "TDEADLOCK"
    assert "CommonModule.Sales.Module" in [item["module_ref"] for item in report["modules"]]
    assert any(action["kind"] == "deadlock" for action in report["recommended_actions"])
    assert "Lock Radar" in report["markdown"]


def test_lock_radar_missing_log_is_watch_with_caveat(tmp_path):
    # A missing path *inside* an allowed data root must degrade to an honest
    # no-data caveat, not a false-green zero and not a hard rejection.
    report = build_lock_radar(log_path=str(tmp_path / "missing" / "tj" / "path"))

    assert report["source"]["available"] is False
    assert report["decision"]["status"] == "watch"
    assert report["summary"]["total_events"] == 0
    assert report["caveats"]


def test_lock_radar_empty_evidence_does_not_return_false_green(tmp_path):
    log_file = tmp_path / "rphost_1" / "26022200.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_text(
        "12:00:01.000000-1000,SDBL,p:1:1:1,Usr=Admin,Context='CommonModule.Safe.Module : 10 : Query()'\n",
        encoding="utf-8",
    )

    report = build_lock_radar(log_path=str(log_file))

    assert report["source"]["available"] is True
    assert report["decision"]["status"] == "ready"
    assert report["summary"]["total_events"] == 0
    assert any("no TLOCK" in item for item in report["caveats"])


def test_lock_radar_rejects_path_outside_data_roots():
    # Path-traversal / arbitrary-file-read guard: an absolute path outside the
    # allowed data roots must be refused, not read.
    with pytest.raises(ValueError, match="outside the allowed data roots"):
        build_lock_radar(log_path=r"C:\Windows\win.ini")
