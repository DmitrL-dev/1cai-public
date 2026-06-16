"""
Multi-Stage Validator

Combines poetic detection and intent extraction for comprehensive validation.
"""

from dataclasses import dataclass
from typing import Dict, Optional

import logging

logger = logging.getLogger(__name__)

from .intent_extractor import IntentResult, SemanticIntentExtractor
from .poetic_detector import PoeticAnalysis, PoeticFormDetector


@dataclass
class ValidationResult:
    """Result of multi-stage validation"""

    allowed: bool
    reason: str
    poetic_analysis: Optional[PoeticAnalysis] = None
    intent_result: Optional[IntentResult] = None
    stage_completed: str = ""  # Which stage completed


class MultiStageValidator:
    """
    Multi-stage validation pipeline.

    Stage 1: Poetic form detection
    Stage 2: Intent extraction (if poetic)
    Stage 3: Standard safety check
    """

    def __init__(self, orchestrator=None):
        """
        Initialize validator.

        Args:
            orchestrator: AI orchestrator for LLM access
        """
        self.poetic_detector = PoeticFormDetector(threshold=0.6)
        self.intent_extractor = SemanticIntentExtractor(orchestrator)

    async def validate(self, query: str, context: Optional[Dict] = None) -> ValidationResult:
        """
        Validate query through multi-stage pipeline.

        Args:
            query: User query
            context: Optional context

        Returns:
            ValidationResult
        """
        try:
            # Stage 1: Poetic form detection
            poetic_analysis = await self.poetic_detector.detect_poetry(query)

            if poetic_analysis.is_poetic:
                logger.warning(
                    f"Poetic form detected (confidence: {poetic_analysis.confidence:.2f})",
                    extra={"patterns": poetic_analysis.detected_patterns},
                )

                # Stage 2: Intent extraction
                intent_result = await self.intent_extractor.extract_intent(query, context)

                if not intent_result.is_safe:
                    return ValidationResult(
                        allowed=False,
                        reason="Potentially harmful intent detected in poetic form",
                        poetic_analysis=poetic_analysis,
                        intent_result=intent_result,
                        stage_completed="intent_extraction",
                    )

            # Stage 3: Standard safety check
            is_safe = await self._standard_safety_check(query)

            if not is_safe:
                return ValidationResult(
                    allowed=False,
                    reason="Failed standard safety check",
                    poetic_analysis=poetic_analysis if poetic_analysis.is_poetic else None,
                    stage_completed="safety_check",
                )

            # All checks passed
            return ValidationResult(
                allowed=True,
                reason="All validation stages passed",
                poetic_analysis=poetic_analysis if poetic_analysis.is_poetic else None,
                stage_completed="complete",
            )

        except Exception as e:
            logger.error("Validation error: %s", e)
            # Fail safe: block on error
            return ValidationResult(allowed=False, reason=f"Validation error: {str(e)}", stage_completed="error")

    async def _standard_safety_check(self, query: str) -> bool:
        """
        Standard safety check.

        Args:
            query: Query to check

        Returns:
            True if safe, False otherwise
        """
        # Simple keyword-based check
        # 1. Use SafetyFilter
        from src.security.poetic_detection.safety_filter import SafetyFilter
        safety_filter = SafetyFilter()
        is_safe, reason = safety_filter.is_safe(query)
        
        if not is_safe:
            logger.warning(f"SafetyFilter blocked request: {reason}")
            return False

        # 2. Simple keyword-based check (Legacy)

        dangerous_keywords = [
            "delete all",
            "drop database",
            "rm -rf /",
            "format c:",
            "sudo rm",
            "del /f /s /q",
        ]

        query_lower = query.lower()

        for keyword in dangerous_keywords:
            if keyword in query_lower:
                logger.warning("Dangerous keyword detected: %s", keyword)
                return False

        return True
