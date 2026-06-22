from datetime import datetime
from typing import Any, Dict, List

from src.modules.risk.domain.models import RiskRecord
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class RiskDatabase:
    """In-memory risk database (replace with real DB in production)."""

    def __init__(self):
        self._risks: Dict[str, RiskRecord] = {}

    def create(self, risk: RiskRecord) -> None:
        self._risks[risk.id] = risk
        logger.info("Risk created", extra={"risk_id": risk.id})

    def get(self, risk_id: str) -> RiskRecord | None:
        return self._risks.get(risk_id)

    def list_all(self) -> List[RiskRecord]:
        return list(self._risks.values())

    def update_status(self, risk_id: str, status: str) -> bool:
        if risk_id in self._risks:
            self._risks[risk_id].status = status
            logger.info(
                "Risk status updated", extra={"risk_id": risk_id, "status": status}
            )
            return True
        return False

    def count(self) -> int:
        return len(self._risks)


# Global instance
_risk_db = RiskDatabase()


class RiskService:
    """Service for risk management operations."""

    def __init__(self, db: RiskDatabase = _risk_db):
        self.db = db

    async def assess_risks(
        self,
        requirements: str,
        context: Dict[str, Any] | None = None,
        architecture: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Assess project risks."""
        logger.info(
            "Assessing risks for project",
            extra={"requirements_length": len(requirements)},
        )

        # Simple risk analysis logic (replace with ML model in production)
        risk_factors = {
            "complexity_score": len(requirements.split()) / 100,
            "integration_points": (
                len(context.get("integrations", [])) if context else 0
            ),
            "data_migration": (
                context.get("data_migration", False) if context else False
            ),
            "legacy_systems": (
                len(context.get("legacy_systems", [])) if context else 0
            ),
        }

        # Calculate total risk score
        total_risk_score = (
            risk_factors["complexity_score"] * 0.4
            + risk_factors["integration_points"] * 0.2
            + (1.0 if risk_factors["data_migration"] else 0) * 0.3
            + risk_factors["legacy_systems"] * 0.1
        )

        if total_risk_score < 0.3:
            risk_level = "low"
            confidence = 0.85
        elif total_risk_score < 0.6:
            risk_level = "medium"
            confidence = 0.75
        elif total_risk_score < 0.8:
            risk_level = "high"
            confidence = 0.65
        else:
            risk_level = "critical"
            confidence = 0.55

        # Generate risk list
        risks = []
        if risk_factors["complexity_score"] > 0.5:
            risks.append(
                {
                    "category": "technical",
                    "description": "High project complexity",
                    "impact": "medium",
                    "probability": risk_factors["complexity_score"],
                }
            )

        if risk_factors["integration_points"] > 3:
            risks.append(
                {
                    "category": "technical",
                    "description": "Multiple integration points",
                    "impact": "high",
                    "probability": min(risk_factors["integration_points"] * 0.2, 1.0),
                }
            )

        if risk_factors["data_migration"]:
            risks.append(
                {
                    "category": "operational",
                    "description": "Data migration",
                    "impact": "high",
                    "probability": 0.7,
                }
            )

        if risk_factors["legacy_systems"] > 2:
            risks.append(
                {
                    "category": "technical",
                    "description": "Legacy system integration",
                    "impact": "medium",
                    "probability": 0.6,
                }
            )

        # Mitigation strategies
        mitigation_strategies = []
        if risk_level in ["high", "critical"]:
            mitigation_strategies.extend(
                [
                    "Create detailed project plan with checkpoints",
                    "Run pilot project to validate approach",
                    "Increase testing and QA time",
                    "Engage 1C experts for consultations",
                ]
            )

        if risk_factors["data_migration"]:
            mitigation_strategies.extend(
                [
                    "Create phased migration plan",
                    "Prepare rollback plan for critical errors",
                ]
            )

        if risk_factors["legacy_systems"] > 2:
            mitigation_strategies.extend(
                [
                    "Conduct compatibility audit with legacy systems",
                    "Create modernization plan for critical components",
                ]
            )

        return {
            "risk_level": risk_level,
            "risks": risks,
            "mitigation_strategies": mitigation_strategies,
            "confidence_score": confidence,
            "timestamp": datetime.now(),
        }

    async def create_risk(self, risk: RiskRecord) -> None:
        """Create new risk record."""
        self.db.create(risk)

    async def get_risk(self, risk_id: str) -> RiskRecord | None:
        """Get risk by ID."""
        return self.db.get(risk_id)

    async def list_risks(self) -> List[RiskRecord]:
        """List all risks."""
        return self.db.list_all()

    async def update_risk_status(self, risk_id: str, status: str) -> bool:
        """Update risk status."""
        return self.db.update_status(risk_id, status)

    async def get_metrics(self) -> Dict[str, Any]:
        """Get risk metrics overview."""
        risks = self.db.list_all()
        if not risks:
            return {
                "total_risks": 0,
                "by_impact": {},
                "by_status": {},
                "by_category": {},
            }

        by_category = {}
        for risk in risks:
            by_category[risk.category] = by_category.get(risk.category, 0) + 1

        by_status = {}
        for risk in risks:
            by_status[risk.status] = by_status.get(risk.status, 0) + 1

        by_impact = {}
        for risk in risks:
            by_impact[risk.impact] = by_impact.get(risk.impact, 0) + 1

        return {
            "total_risks": len(risks),
            "by_impact": by_impact,
            "by_status": by_status,
            "by_category": by_category,
            "avg_probability": sum(r.probability for r in risks) / len(risks),
        }
