from datetime import datetime, timedelta

import pytest

from src.integrations.onec.ras_monitor import RASMonitor


class FailingRasClient:
    def get_clusters(self):
        raise RuntimeError("rac unavailable")


class MinimalRasClient:
    def get_clusters(self):
        return [{"cluster": "cluster-1", "name": "Prod", "port": "1541"}]

    def get_sessions(self, cluster_id):
        return [
            {
                "session-id": "s1",
                "user-name": "ivan",
                "app-id": "thin",
                "started-at": (datetime.utcnow() - timedelta(minutes=10)).isoformat(),
            }
        ]


@pytest.mark.asyncio
async def test_ras_monitor_reports_not_connected_without_mock_cluster():
    monitor = RASMonitor()
    monitor.client = FailingRasClient()

    health = await monitor.get_cluster_health()

    assert health["status"] == "not_connected"
    assert health["coverage"] == "no_ras_connection"
    assert health["connected"] is False
    assert health["health_status"] == "unknown"
    assert health["cluster_info"].cluster_id == "unavailable"
    assert "mock" not in str(health).lower()
    assert health["caveats"]


@pytest.mark.asyncio
async def test_ras_monitor_marks_basic_cluster_read_as_partial_evidence():
    monitor = RASMonitor()
    monitor.client = MinimalRasClient()

    health = await monitor.get_cluster_health()

    assert health["status"] == "success"
    assert health["coverage"] == "ras_cluster_list_partial"
    assert health["connected"] is True
    assert health["cluster_info"].cluster_id == "cluster-1"
    assert health["active_sessions"] == 1
    assert health["caveats"]
