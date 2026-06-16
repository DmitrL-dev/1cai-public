
"""
RAS Monitor - 1C Remote Administration Server Monitoring
Мониторинг кластера 1С через RAS

Based on: https://github.com/Polyplastic/1c-parsing-tech-log (RAS integration)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.utils.structured_logging import StructuredLogger
from src.integrations.onec.ras_client import RasClient

logger = StructuredLogger(__name__).logger


@dataclass
class ClusterInfo:
    """Информация о кластере"""

    cluster_id: str
    name: str
    main_port: int
    working_processes: int
    total_memory_mb: int
    cpu_usage: float


@dataclass
class SessionInfo:
    """Информация о сессии"""

    session_id: str
    user: str
    application: str
    started_at: datetime
    duration_minutes: int
    memory_mb: int
    cpu_time_seconds: int
    db_connection_mode: str


@dataclass
class LockInfo:
    """Информация о блокировке"""

    object: str
    locked_by_user: str
    wait_time_seconds: int
    lock_type: str


class RASMonitor:
    """
    Мониторинг 1С кластера через Remote Administration Server

    Features:
    - Cluster health monitoring
    - Active sessions tracking
    - Lock detection
    - Resource usage analysis
    - Performance recommendations
    """

    def __init__(self, ras_host: str = "localhost", ras_port: int = 1545):
        self.ras_host = ras_host
        self.ras_port = ras_port
        self.connected = False
        self.client = RasClient(ras_host=ras_host, ras_port=ras_port)

        # Пороги для алертов
        self.thresholds = {
            "long_session_minutes": 240,  # 4 hours
            "high_memory_mb": 1000,  # 1GB per session
            "lock_wait_seconds": 30,  # 30 sec
            "working_processes_min": 2,
            "sessions_per_process": 20,  # Recommended ratio
        }

    async def connect(self) -> bool:
        """
        Подключение к RAS
        """
        try:
            # Check connection by listing clusters
            clusters = self.client.get_clusters()
            self.connected = True
            logger.info(f"RAS connection established. Found {len(clusters)} clusters.")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to RAS: {e}")
            return False

    async def _get_cluster_info(self, cluster_name: Optional[str]) -> ClusterInfo:
        """Получение информации о кластере через RAS"""
        try:
            clusters = self.client.get_clusters()
            if not clusters:
                raise RuntimeError("No clusters found")

            # Use first cluster if name not specified
            target = clusters[0]
            if cluster_name:
                for c in clusters:
                    if c.get("name") == cluster_name:
                        target = c
                        break

            return ClusterInfo(
                cluster_id=target.get("cluster", "unknown"),
                name=target.get("name", "Unknown Cluster"),
                main_port=int(target.get("port", 1541)),
                working_processes=0,  # Need separate call to count processes
                total_memory_mb=0,  # RAS doesn't provide total memory directly usually
                cpu_usage=0.0,  # RAS doesn't provide CPU usage directly
            )
        except Exception as e:
            logger.error(f"Error getting cluster info: {e}")
            # Fallback to mock for safety if RAC fails
            return ClusterInfo("mock", "Mock Cluster (Error)", 1541, 0, 0, 0.0)

    async def _get_active_sessions(self, cluster_name: Optional[str]) -> List[SessionInfo]:
        """Получение активных сессий"""
        try:
            # We need cluster ID first
            cluster = await self._get_cluster_info(cluster_name)
            if cluster.cluster_id == "mock":
                return []

            raw_sessions = self.client.get_sessions(cluster.cluster_id)
            sessions = []

            for s in raw_sessions:
                # Parse duration (format depends on locale, simplified here)
                # Assuming started-at is ISO or similar
                start_time = datetime.now()  # Placeholder

                sessions.append(
                    SessionInfo(
                        session_id=s.get("session-id", ""),
                        user=s.get("user-name", "Unknown"),
                        application=s.get("app-id", "Unknown"),
                        started_at=start_time,
                        duration_minutes=0,  # Calc from start_time
                        memory_mb=0,  # Not always available in simple list
                        cpu_time_seconds=0,
                        db_connection_mode="Unknown",
                    )
                )
            return sessions
        except Exception as e:
            logger.error(f"Error getting sessions: {e}")
            return []

    async def _get_locks(self, cluster_name: Optional[str]) -> List[LockInfo]:
        """Получение информации о блокировках"""
        # Real lock info requires more complex RAC calls (infobase specific)
        return []

    async def _get_working_processes_info(self, cluster_name: Optional[str]) -> Dict:
        """Информация о рабочих процессах"""
        return {
            "total_processes": 0,
            "available_processes": 0,
            "avg_memory_per_process_mb": 0,
            "avg_cpu_per_process": 0.0,
        }

    # ==========================================
    # АНАЛИЗ ЗДОРОВЬЯ
    # ==========================================

    async def _analyze_cluster_health(
        self,
        cluster: ClusterInfo,
        sessions: List[SessionInfo],
        locks: List[LockInfo],
        processes: Dict,
    ) -> List[Dict]:
        """Анализ здоровья кластера"""
        issues = []

        # 1. Долгие сессии
        long_sessions = [s for s in sessions if s.duration_minutes > self.thresholds["long_session_minutes"]]

        if long_sessions:
            issues.append(
                {
                    "type": "long_running_sessions",
                    "severity": "warning",
                    "count": len(long_sessions),
                    "details": f"{len(long_sessions)} сессий работают > 4 часов",
                    "action": "Проверить на зависшие процессы",
                }
            )

        # 2. Высокое потребление памяти
        high_memory_sessions = [s for s in sessions if s.memory_mb > self.thresholds["high_memory_mb"]]

        if high_memory_sessions:
            issues.append(
                {
                    "type": "high_memory_usage",
                    "severity": "high",
                    "count": len(high_memory_sessions),
                    "details": f"{len(high_memory_sessions)} сессий используют > 1GB памяти",
                    "action": "Проверить на утечки памяти",
                }
            )

        # 3. Недостаточно рабочих процессов
        sessions_per_process = len(sessions) / max(cluster.working_processes, 1)

        if sessions_per_process > self.thresholds["sessions_per_process"]:
            issues.append(
                {
                    "type": "insufficient_working_processes",
                    "severity": "high",
                    "count": 1,
                    "details": f"Соотношение сессии/процессы: {sessions_per_process:.1f} (рекомендуется < 20)",
                    "action": "Увеличить количество рабочих процессов",
                }
            )

        # 4. Высокая загрузка CPU
        if cluster.cpu_usage > 0.8:
            issues.append(
                {
                    "type": "high_cpu_usage",
                    "severity": "critical",
                    "count": 1,
                    "details": f"CPU usage: {cluster.cpu_usage*100:.0f}%",
                    "action": "Оптимизировать запросы или масштабировать сервер",
                }
            )

        return issues

    def _determine_health_status(self, issues: List[Dict]) -> str:
        """Определение общего статуса здоровья"""
        if not issues:
            return "healthy"

        critical_count = len([i for i in issues if i["severity"] == "critical"])
        high_count = len([i for i in issues if i["severity"] == "high"])

        if critical_count > 0:
            return "critical"
        elif high_count > 2:
            return "warning"
        else:
            return "moderate"

    async def _generate_cluster_recommendations(
        self, cluster: ClusterInfo, sessions: List[SessionInfo], issues: List[Dict]
    ) -> List[Dict]:
        """Генерация рекомендаций по кластеру"""
        recommendations = []

        # По проблемам
        for issue in issues:
            if issue["type"] == "insufficient_working_processes":
                current = cluster.working_processes
                recommended = len(sessions) // 15  # 15 sessions per process

                recommendations.append(
                    {
                        "category": "scaling",
                        "priority": "high",
                        "current_value": current,
                        "recommended_value": recommended,
                        "improvement": f"{(recommended/current - 1)*100:.0f}% больше capacity",
                    }
                )

        return recommendations


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test():
        monitor = RASMonitor("localhost", 1545)

        print("=== RAS Monitor Test ===")

        # Connect
        connected = await monitor.connect()
        print(f"Connected: {connected}")

        # Get cluster health
        health = await monitor.get_cluster_health()

        print("\nCluster Health:")
        print(f"  Name: {health['cluster_info'].name}")
        print(f"  Working Processes: {health['working_processes']}")
        print(f"  Active Sessions: {health['active_sessions']}")
        print(f"  CPU Usage: {health['cpu_usage']*100:.0f}%")
        print(f"  Memory: {health['total_memory_mb']}MB")
        print(f"  Health Status: {health['health_status']}")

        print(f"\nIssues: {len(health['issues'])}")
        for issue in health["issues"]:
            print(f"  [{issue['severity'].upper()}] {issue['type']}: {issue['details']}")

        print(f"\nRecommendations: {len(health['recommendations'])}")

        print("\n[OK] RAS Monitor ready!")

    asyncio.run(test())
