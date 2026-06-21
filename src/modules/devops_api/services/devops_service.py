"""Offline DevOps status and guarded automation compatibility service."""

from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class DevOpsService:
    """Service for offline Docker Compose infrastructure checks."""

    async def analyze_infrastructure(
        self, compose_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze Docker infrastructure by parsing a Compose file."""
        compose_path = self._resolve_compose_path(compose_file)

        import yaml

        try:
            content = compose_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content) or {}
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "static_analysis": {
                    "compose_file": str(compose_path),
                    "mode": "offline-static",
                    "error": str(exc),
                },
                "runtime_containers": [],
                "services_status": {},
                "recommendations": [
                    {
                        "severity": "high",
                        "target": str(compose_path),
                        "action": "Fix Compose syntax before deployment analysis.",
                    }
                ],
            }

        services = data.get("services") or {}
        if not isinstance(services, dict):
            services = {}

        services_status = {
            name: self._service_status(name, spec)
            for name, spec in services.items()
            if isinstance(spec, dict)
        }
        exposed_ports = {
            name: status["ports"]
            for name, status in services_status.items()
            if status["ports"]
        }
        healthcheck_count = sum(
            1 for status in services_status.values() if status["has_healthcheck"]
        )

        result = {
            "status": "success",
            "static_analysis": {
                "compose_file": str(compose_path),
                "mode": "offline-static",
                "service_count": len(services_status),
                "services": list(services_status.keys()),
                "healthcheck_count": healthcheck_count,
                "healthcheck_coverage": self._ratio(
                    healthcheck_count,
                    len(services_status),
                ),
                "exposed_ports": exposed_ports,
                "networks": sorted((data.get("networks") or {}).keys()),
                "volumes": sorted((data.get("volumes") or {}).keys()),
                "runtime_collection": "not_collected_without_docker_sdk",
            },
            "runtime_containers": [],
            "services_status": services_status,
            "recommendations": self._recommendations(services_status),
        }

        logger.info(
            "Infrastructure analysis completed",
            extra={
                "compose_file": str(compose_path),
                "services_count": len(services_status),
            },
        )
        return result

    async def get_infrastructure_status(self) -> Dict[str, Any]:
        """Return quick offline infrastructure status without Docker runtime calls."""
        try:
            result = await self.analyze_infrastructure()
        except FileNotFoundError:
            return {
                "status": "not_configured",
                "mode": "offline-static",
                "message": "No docker-compose.yml file was found in the current workspace.",
                "runtime_collection": "not_collected_without_docker_sdk",
                "next_action": "Provide compose_file to /devops/infrastructure/analyze or add a Compose file.",
            }

        static = result.get("static_analysis", {})
        recommendations = result.get("recommendations", [])
        high_count = sum(
            1 for item in recommendations if item.get("severity") == "high"
        )
        return {
            "status": "attention" if high_count else "ready",
            "mode": static.get("mode", "offline-static"),
            "compose_file": static.get("compose_file"),
            "service_count": static.get("service_count", 0),
            "healthcheck_coverage": static.get("healthcheck_coverage", 0),
            "runtime_collection": static.get("runtime_collection"),
            "recommendations": recommendations[:5],
            "next_action": "Review high-severity Compose findings before release."
            if high_count
            else "Attach Docker runtime adapter if live container status is required.",
        }

    def _resolve_compose_path(self, compose_file: Optional[str]) -> Path:
        if compose_file:
            compose_path = Path(compose_file)
            if not compose_path.exists():
                raise FileNotFoundError(f"File not found: {compose_file}")
            return compose_path

        project_root = Path.cwd()
        for name in (
            "docker-compose.yml",
            "docker-compose.mvp.yml",
            "docker-compose.yaml",
        ):
            compose_path = project_root / name
            if compose_path.exists():
                return compose_path
        raise FileNotFoundError("docker-compose.yml not found")

    def _service_status(self, name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        ports = spec.get("ports") or []
        depends_on = spec.get("depends_on") or []
        if isinstance(depends_on, dict):
            depends_on = list(depends_on.keys())
        return {
            "name": name,
            "image": spec.get("image"),
            "build": spec.get("build"),
            "ports": ports,
            "depends_on": depends_on,
            "has_healthcheck": "healthcheck" in spec,
            "restart_policy": spec.get("restart"),
            "environment_keys": sorted((spec.get("environment") or {}).keys())
            if isinstance(spec.get("environment"), dict)
            else [],
        }

    def _recommendations(
        self,
        services_status: Dict[str, Dict[str, Any]],
    ) -> list[Dict[str, Any]]:
        recommendations: list[Dict[str, Any]] = []
        if not services_status:
            recommendations.append(
                {
                    "severity": "high",
                    "target": "compose",
                    "action": "Add services to the Compose file before infrastructure analysis.",
                }
            )
            return recommendations

        for name, status in services_status.items():
            if not status["has_healthcheck"]:
                recommendations.append(
                    {
                        "severity": "medium",
                        "target": name,
                        "action": "Add a healthcheck so release gates can detect service readiness.",
                    }
                )
            if status["ports"] and not status["restart_policy"]:
                recommendations.append(
                    {
                        "severity": "medium",
                        "target": name,
                        "action": "Set an explicit restart policy for externally exposed services.",
                    }
                )
        return recommendations

    def _ratio(self, numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(numerator / denominator, 3)


class AIEvolutionService:
    """Guarded automation status for removed autonomous self-modification APIs."""

    async def evolve(self, force: bool = False) -> Dict[str, Any]:
        return {
            "status": "disabled_by_policy",
            "stage": "safety-gate",
            "metrics": {
                "force_requested": force,
                "autonomous_write_enabled": False,
                "approved_route": "/safe-autopilot",
            },
            "improvements": [],
            "message": (
                "Autonomous self-modification is disabled. Use Safe Autopilot "
                "for plan, impact, diff, tests and approval evidence."
            ),
        }

    async def get_status(self) -> Dict[str, Any]:
        return {
            "status": "disabled_by_policy",
            "stage": "safety-gate",
            "evolution_count": 0,
            "autonomous_write_enabled": False,
            "approved_route": "/safe-autopilot",
        }

    async def get_metrics(self) -> Dict[str, Any]:
        return {
            "status": "disabled_by_policy",
            "history": [],
            "metrics": {
                "evolution_count": 0,
                "autonomous_write_enabled": False,
                "approved_route": "/safe-autopilot",
            },
        }
