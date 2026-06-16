"""
Semantic Intent Extractor

Extracts true intent from poetic/obfuscated input.
"""

from dataclasses import dataclass
from typing import Dict, Optional

import logging

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """Result of intent extraction"""

    original_text: str
    prose_intent: str
    is_safe: bool
    confidence: float
    action: str  # "allow" or "block"
    reason: Optional[str] = None


class SemanticIntentExtractor:
    """
    Extracts semantic intent from poetic/obfuscated text.

    Translates poetry to prose and validates safety.
    """

    def __init__(self, orchestrator=None):
        """
        Initialize intent extractor.

        Args:
            orchestrator: AI orchestrator for LLM access
        """
        self.orchestrator = orchestrator

    async def extract_intent(self, text: str, context: Optional[Dict] = None) -> IntentResult:
        """
        Extract intent from text.

        Args:
            text: Input text (potentially poetic)
            context: Optional context

        Returns:
            IntentResult with extracted intent and safety assessment
        """
        try:
            # Translate poetry to prose
            prose_version = await self._translate_to_prose(text)

            # Check safety of prose version
            is_safe = await self._check_safety(prose_version)

            action = "allow" if is_safe else "block"
            reason = None if is_safe else "Potentially harmful intent detected"

            if not is_safe:
                logger.warning(
                    f"Unsafe intent detected in poetic text",
                    extra={"original_length": len(
                        text), "prose_length": len(prose_version)},
                )

            return IntentResult(
                original_text=text,
                prose_intent=prose_version,
                is_safe=is_safe,
                confidence=0.8,
                action=action,
                reason=reason,
            )

        except Exception as e:
            logger.error("Error extracting intent: %s", e)
            # Fail safe: block on error
            return IntentResult(
                original_text=text,
                prose_intent="",
                is_safe=False,
                confidence=0.0,
                action="block",
                reason=f"Error during intent extraction: {str(e)}",
            )

    async def _translate_to_prose(self, text: str) -> str:
        """
        Translate poetic text to prose.

        Args:
            text: Poetic text

        Returns:
            Prose version
        """
        if not self.orchestrator:
            # Fallback: return original text
            return text

        prompt = f"""Translate the following poetic or metaphorical text into clear, direct prose.
Extract the literal meaning and intent, removing any figurative language or obfuscation.

Poetic text:
{text}

Direct prose translation:"""

        try:
            # Use orchestrator to translate
            result = await self.orchestrator.process_query(query=prompt, context={"max_tokens": 200})

            # Extract response
            if isinstance(result, dict):
                prose = result.get("response", text)
            else:
                prose = str(result)

            return prose.strip()

        except Exception as e:
            logger.error("Error translating to prose: %s", e)
            return text

    async def _check_safety(self, text: str) -> bool:
        """
        Check if text is safe.

        Args:
            text: Text to check

        Returns:
            True if safe, False if potentially harmful
        """
        # 1. Use SafetyFilter for Prompt Injection and Jailbreak detection
        from src.security.poetic_detection.safety_filter import SafetyFilter
        safety_filter = SafetyFilter()
        is_safe, reason = safety_filter.is_safe(text)
        
        if not is_safe:
            logger.warning(f"SafetyFilter blocked request: {reason}")
            return False

        # 2. Simple keyword-based safety check (Legacy/Fallback)
        harmful_keywords = [
            "delete",
            "drop",
            "truncate",
            "remove",
            "hack",
            "exploit",
            "bypass",
            "jailbreak",
            "malware",
            "virus",
            "attack",
            "breach",
            "password",
            "credential",
            "secret",
            "token",
            "inject",
            "injection",
            "xss",
            "csrf",
        ]

        text_lower = text.lower()

        # Check for harmful keywords
        for keyword in harmful_keywords:
            if keyword in text_lower:
                logger.warning("Harmful keyword detected: %s", keyword)
                return False

        # Check for suspicious patterns
        suspicious_patterns = [
            r"delete\s+from",
            r"drop\s+table",
            r"truncate\s+table",
            r"rm\s+-rf",
            r"eval\s*\(",
            r"exec\s*\(",
        ]

        import re

        for pattern in suspicious_patterns:
            if re.search(pattern, text_lower):
                logger.warning("Suspicious pattern detected: %s", pattern)
                return False

        return True
