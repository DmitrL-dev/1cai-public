"""
Poetic Form Detector

Detects poetic structure in user input to prevent adversarial poetry jailbreaks.
"""

import re
from dataclasses import dataclass
from typing import Dict, List

import logging

logger = logging.getLogger(__name__)


@dataclass
class PoeticAnalysis:
    """Result of poetic form analysis"""

    is_poetic: bool
    confidence: float  # 0-1
    features: Dict[str, float]  # Individual feature scores
    detected_patterns: List[str]  # Patterns found


class PoeticFormDetector:
    """
    Detects poetic form in text.

    Based on research showing 62% ASR with poetic jailbreaks.
    Detects:
    - Rhyme schemes
    - Meter/rhythm
    - Verse structure
    - Metaphorical language
    """

    def __init__(self, threshold: float = 0.6):
        """
        Initialize detector.

        Args:
            threshold: Confidence threshold for poetic classification
        """
        self.threshold = threshold

    async def detect_poetry(self, text: str) -> PoeticAnalysis:
        """
        Detect poetic form in text.

        Args:
            text: Input text to analyze

        Returns:
            PoeticAnalysis with detection results
        """
        if not text or len(text.strip()) < 10:
            return PoeticAnalysis(is_poetic=False, confidence=0.0, features={}, detected_patterns=[])

        # Analyze features
        rhyme_score = self._detect_rhymes(text)
        meter_score = self._detect_meter(text)
        verse_score = self._detect_verses(text)
        metaphor_score = self._detect_metaphors(text)

        # Combine scores (weighted)
        poetic_score = rhyme_score * 0.3 + meter_score * \
            0.2 + verse_score * 0.3 + metaphor_score * 0.2

        # Detect patterns
        patterns = []
        if rhyme_score > 0.5:
            patterns.append("rhyme_scheme")
        if meter_score > 0.5:
            patterns.append("rhythmic_meter")
        if verse_score > 0.5:
            patterns.append("verse_structure")
        if metaphor_score > 0.5:
            patterns.append("metaphorical_language")

        is_poetic = poetic_score > self.threshold

        if is_poetic:
            logger.warning(f"Poetic form detected (confidence: {poetic_score:.2f})", extra={
                           "patterns": patterns})

        return PoeticAnalysis(
            is_poetic=is_poetic,
            confidence=poetic_score,
            features={
                "rhyme": rhyme_score,
                "meter": meter_score,
                "verse": verse_score,
                "metaphor": metaphor_score,
            },
            detected_patterns=patterns,
        )

    def _detect_rhymes(self, text: str) -> float:
        """
        Detect rhyme schemes.

        Simple heuristic: check if line endings sound similar.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        if len(lines) < 2:
            return 0.0

        # Get last words of each line
        last_words = []
        for line in lines:
            words = line.split()
            if words:
                # Remove punctuation
                last_word = re.sub(r"[^\w\s]", "", words[-1]).lower()
                last_words.append(last_word)

        if len(last_words) < 2:
            return 0.0

        # Check for rhyming patterns (simple suffix matching)
        rhyme_count = 0
        total_pairs = 0

        for i in range(len(last_words)):
            for j in range(i + 1, min(i + 3, len(last_words))):  # Check next 2 lines
                total_pairs += 1
                word1, word2 = last_words[i], last_words[j]

                # Check if last 2-3 characters match (simple rhyme)
                if len(word1) >= 2 and len(word2) >= 2:
                    if word1[-2:] == word2[-2:] or word1[-3:] == word2[-3:]:
                        rhyme_count += 1

        if total_pairs == 0:
            return 0.0

        return min(1.0, rhyme_count / total_pairs * 2)  # Amplify signal

    def _detect_meter(self, text: str) -> float:
        """
        Detect rhythmic meter.

        Heuristic: check for consistent line lengths and syllable patterns.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        if len(lines) < 3:
            return 0.0

        # Count syllables per line (rough approximation)
        syllable_counts = []
        for line in lines:
            # Simple syllable count: vowel groups
            vowels = re.findall(r"[aeiouy]+", line.lower())
            syllable_counts.append(len(vowels))

        if not syllable_counts:
            return 0.0

        # Check for consistency
        avg_syllables = sum(syllable_counts) / len(syllable_counts)
        variance = sum((s - avg_syllables) **
                       2 for s in syllable_counts) / len(syllable_counts)

        # Low variance = consistent meter
        consistency = 1.0 / (1.0 + variance)

        return min(1.0, consistency)

    def _detect_verses(self, text: str) -> float:
        """
        Detect verse structure.

        Heuristic: check for stanza breaks and line structure.
        """
        lines = text.split("\n")

        # Count empty lines (stanza breaks)
        empty_lines = sum(1 for line in lines if not line.strip())

        # Count non-empty lines
        content_lines = sum(1 for line in lines if line.strip())

        if content_lines < 3:
            return 0.0

        # Verse indicators
        has_stanzas = empty_lines > 0
        has_multiple_lines = content_lines >= 4
        has_short_lines = sum(1 for line in lines if line.strip()
                              and len(line.strip()) < 60) > content_lines * 0.7

        score = 0.0
        if has_stanzas:
            score += 0.4
        if has_multiple_lines:
            score += 0.3
        if has_short_lines:
            score += 0.3

        return min(1.0, score)

    def _detect_metaphors(self, text: str) -> float:
        """
        Detect metaphorical language.

        Heuristic: check for poetic keywords and figurative language.
        """
        text_lower = text.lower()

        # Poetic keywords
        poetic_keywords = [
            "like",
            "as",
            "metaphor",
            "symbol",
            "represents",
            "flows",
            "whispers",
            "dances",
            "sings",
            "weeps",
            "gentle",
            "soft",
            "tender",
            "sweet",
            "bitter",
            "shadow",
            "light",
            "darkness",
            "dawn",
            "dusk",
            "heart",
            "soul",
            "spirit",
            "dream",
            "vision",
            "verse",
            "rhythm",
            "rhyme",
            "poetry",
            "stanza",
        ]

        # Count keyword occurrences
        keyword_count = sum(1 for keyword in poetic_keywords if keyword in text_lower)

        # Normalize by text length
        words = text_lower.split()
        if not words:
            return 0.0

        keyword_density = keyword_count / len(words)

        # Amplify signal
        score = min(1.0, keyword_density * 20)

        return score
