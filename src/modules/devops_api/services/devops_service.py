"""DevOps Service — Phase 7 rewrite.

Replaced phantom DevOpsAgentExtended and SelfEvolvingAI
with real SecurityAgent for infrastructure analysis.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class DevOpsService:
    """Service for DevOps operations — simplified after Phase 7 cleanup."""

    async def analyze_infrastructure(
        self, compose_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze Docker infrastructure by parsing compose file."""
        if not compose_file:
            project_root = Path.cwd()
            for name in (
                "docker-compose.yml",
                "docker-compose.mvp.yml",
                "docker-compose.yaml",
            ):
                path = project_root / name
                if path.exists():
                    compose_file = str(path)
                    break
            if not compose_file:
                raise FileNotFoundError("docker-compose.yml not found")

        compose_path = Path(compose_file)
        if not compose_path.exists():
            raise FileNotFoundError(f"File not found: {compose_file}")

        # Basic compose analysis without phantom agent
        import yaml

        try:
            content = compose_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
        except Exception as e:
            return {"status": "error", "message": str(e)}

        services = data.get("services", {})
        result = {
            "status": "success",
            "compose_file": compose_file,
            "service_count": len(services),
            "services": list(services.keys()),
            "has_healthchecks": sum(1 for s in services.values() if "healthcheck" in s),
            "exposed_ports": {
                name: svc.get("ports", [])
                for name, svc in services.items()
                if svc.get("ports")
            },
        }

        logger.info(
            "Infrastructure analysis completed",
            extra={
                "compose_file": compose_file,
                "services_count": result["service_count"],
            },
        )
        return result

    async def get_infrastructure_status(self) -> Dict[str, Any]:
        """Get quick infrastructure status — placeholder."""
        return {
            "status": "success",
            "message": "Runtime status requires Docker SDK (not installed)",
        }


class AIEvolutionService:
    """Stub — SelfEvolvingAI was a phantom module. Kept for API compat."""

    async def evolve(self, force: bool = False) -> Dict[str, Any]:
        return {
            "status": "not_available",
            "message": "Self-evolving AI removed in Phase 7 (was phantom module)",
        }

    async def get_status(self) -> Dict[str, Any]:
        return {"status": "not_available", "evolution_count": 0}
