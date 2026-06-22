"""Offline-compatible DevOps agent compatibility layer."""

from typing import Any, Dict, List


class DevOpsAgentExtended:
    """Small deterministic DevOps advisor used when no external CI telemetry exists."""

    async def optimize_pipeline(
        self, pipeline_config: Dict[str, Any], metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        steps = list(pipeline_config.get("steps") or [])
        duration = float(
            metrics.get("avg_duration") or pipeline_config.get("duration_minutes") or 0
        )
        success_rate = metrics.get("success_rate")
        recommendations: List[str] = []

        if duration >= 30:
            recommendations.append(
                "Split slow build/test stages and cache dependencies."
            )
        if success_rate is not None and float(success_rate) < 0.95:
            recommendations.append(
                "Add flaky-test quarantine and retry only idempotent steps."
            )
        if "deploy" in steps:
            recommendations.append(
                "Gate deploy with artifact provenance and smoke checks."
            )
        if not recommendations:
            recommendations.append(
                "Keep collecting duration and failure telemetry per stage."
            )

        return {
            "mode": "offline_devops_pipeline_triage",
            "steps": steps,
            "metrics": metrics,
            "recommendations": recommendations,
            "required_evidence": [
                "per-stage timings",
                "failure reasons",
                "release gate log",
            ],
        }


__all__ = ["DevOpsAgentExtended"]
