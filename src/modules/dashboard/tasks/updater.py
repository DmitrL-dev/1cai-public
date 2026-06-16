import asyncio
from src.utils.structured_logging import StructuredLogger
from src.services.real_time_service import real_time_manager
from src.database import get_pool
from src.modules.dashboard.services.ba_service import BAService
from src.modules.dashboard.services.developer_service import DeveloperService
from src.modules.dashboard.services.executive_service import ExecutiveService
from src.modules.dashboard.services.owner_service import OwnerService
from src.modules.dashboard.services.pm_service import PMService
from src.modules.dashboard.services.team_lead_service import TeamLeadService

logger = StructuredLogger(__name__).logger


async def start_dashboard_updater() -> None:
    """Фоновая задача для периодического обновления дашбордов.

    Рассылает обновления всем подключенным клиентам через WebSocket.
    """
    # Initialize services
    owner_service = OwnerService()
    executive_service = ExecutiveService()
    pm_service = PMService()
    developer_service = DeveloperService()
    team_lead_service = TeamLeadService()
    ba_service = BAService()

    while True:
        try:
            await asyncio.sleep(30)  # Update every 30 seconds

            pool = get_pool()

            # Update each dashboard type using services
            dashboards = {
                "owner": owner_service.get_dashboard,
                "executive": executive_service.get_dashboard,
                "pm": pm_service.get_dashboard,
                "developer": developer_service.get_dashboard,
                "team_lead": team_lead_service.get_dashboard,
                "ba": ba_service.get_dashboard,
            }

            for dashboard_type, service_method in dashboards.items():
                try:
                    # Call service method with pool
                    data = await service_method(pool)

                    # Broadcast update
                    await real_time_manager.broadcast_dashboard_update(dashboard_type, data)

                except Exception as e:
                    logger.error(
                        "Error updating dashboard",
                        extra={
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "dashboard_type": dashboard_type,
                        },
                        exc_info=True,
                    )

            logger.debug("Dashboard updates broadcasted")

        except Exception as e:
            logger.error(
                "Dashboard updater error",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            await asyncio.sleep(60)  # Wait longer on error
