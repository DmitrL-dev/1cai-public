"""
Safety Filter
-------------

Provides mechanisms to detect and block malicious inputs such as Prompt Injections
and Jailbreak attempts before they reach the core AI logic.
"""

import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)


class SafetyFilter:
    """
    Filters input text for safety violations.
    """

    # Known patterns often used in Prompt Injection
    INJECTION_PATTERNS = [
        r"ignore previous instructions",
        r"ignore all previous instructions",
        r"disregard previous instructions",
        r"forget all instructions",
        r"system override",
        r"developer mode",
    ]

    # Known patterns often used in Jailbreaks (DAN, etc.)
    JAILBREAK_PATTERNS = [
        r"do anything now",
        r"stay in character",
        r"always answer",
        r"you are not an ai",
        r"unfiltered",
        r"uncensored",
        r"pretend to be",
    ]

    def __init__(self):
        self._injection_regexes = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]
        self._jailbreak_regexes = [re.compile(p, re.IGNORECASE) for p in self.JAILBREAK_PATTERNS]

    def check_prompt_injection(self, text: str) -> float:
        """
        Calculate probability of prompt injection (0.0 to 1.0).
        """
        score = 0.0
        for regex in self._injection_regexes:
            if regex.search(text):
                score += 1.0  # High penalty for direct matches

        return min(1.0, score)

    def check_jailbreak(self, text: str) -> float:
        """
        Calculate probability of jailbreak attempt (0.0 to 1.0).
        """
        score = 0.0
        for regex in self._jailbreak_regexes:
            if regex.search(text):
                score += 1.0

        return min(1.0, score)

    def is_safe(self, text: str, threshold: float = 0.8) -> Tuple[bool, str]:
        """
        Check if the text is safe.

        Returns:
            (is_safe, reason)
        """
        injection_score = self.check_prompt_injection(text)
        if injection_score >= threshold:
            logger.warning(f"Prompt injection detected (score={injection_score}): {text[:50]}...")
            return False, "Prompt Injection Detected"

        jailbreak_score = self.check_jailbreak(text)
        if jailbreak_score >= threshold:
            logger.warning(f"Jailbreak attempt detected (score={jailbreak_score}): {text[:50]}...")
            return False, "Jailbreak Attempt Detected"

        return True, "Safe"
