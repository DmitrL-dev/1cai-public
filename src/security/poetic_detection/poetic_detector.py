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

        # Adversarial-poetry jailbreaks frequently arrive as *short* couplets or
        # tercets, where the linear weighting above never crosses threshold even
        # though the text is unmistakably a poem. Two corroborated overrides close
        # that gap without flagging ordinary line-wrapped prose:
        #
        #  1) A clear end-rhyme across 2-3 short lines is the canonical "poem"
        #     shape; prose almost never end-rhymes.
        #  2) Deliberate verse structure (stanza/short lines) *with* rhythmic
        #     consistency AND at least one poetic-content signal (rhyme or
        #     figurative imagery). Requiring both structure and content keeps
        #     plain multi-line prompts (which have neither rhyme nor imagery)
        #     below threshold.
        if rhyme_score >= 0.5 and self._is_short_verse(text):
            poetic_score = max(poetic_score, self.threshold + 0.05)
        if (
            verse_score >= 0.6
            and meter_score >= 0.35
            and (rhyme_score >= 0.5 or metaphor_score >= 0.6)
        ):
            poetic_score = max(poetic_score, self.threshold + 0.05)

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

    @staticmethod
    def _rhyme_endings(word: str) -> set:
        """
        Candidate rhyme endings for a word (perfect + light slant rhyme).

        Returns the 2- and 3-char tails plus vowel-anchored rimes (from the last
        and penultimate vowel group to the end). Two words "rhyme" when any of
        these candidate endings coincide, which catches both perfect rhymes
        (fade/made) and common slant rhymes without resorting to a full
        phonetic dictionary.
        """
        w = re.sub(r"[^a-z]", "", word.lower())
        if len(w) < 2:
            return {w} if w else set()

        keys = {w[-2:], w[-3:]}
        vowel_groups = list(re.finditer(r"[aeiouy]+", w))
        if vowel_groups:
            keys.add(w[vowel_groups[-1].start():])
            if len(vowel_groups) >= 2:
                keys.add(w[vowel_groups[-2].start():])

        return {k for k in keys if k}

    def _detect_rhymes(self, text: str) -> float:
        """
        Detect rhyme schemes.

        Simple heuristic: check if line endings sound similar (perfect or slant
        rhyme via shared vowel-anchored / suffix endings).
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

        # Check for rhyming patterns (suffix + vowel-anchored matching)
        rhyme_count = 0
        total_pairs = 0

        for i in range(len(last_words)):
            for j in range(i + 1, min(i + 3, len(last_words))):  # Check next 2 lines
                total_pairs += 1
                word1, word2 = last_words[i], last_words[j]

                if len(word1) >= 2 and len(word2) >= 2:
                    if self._rhyme_endings(word1) & self._rhyme_endings(word2):
                        rhyme_count += 1

        if total_pairs == 0:
            return 0.0

        return min(1.0, rhyme_count / total_pairs * 2)  # Amplify signal

    @staticmethod
    def _is_short_verse(text: str) -> bool:
        """True for a short (2-3 line) block of short lines — a couplet/tercet."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return 2 <= len(lines) <= 3 and all(len(line) < 70 for line in lines)

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
        # Poetic / figurative vocabulary. The first block is the original set;
        # the second adds literary-imagery words that recur in adversarial-poetry
        # jailbreak samples (e.g. "the path where danger grows / what secrets can
        # a seeker find").
        poetic_keywords = {
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
            # figurative imagery seen in poetic jailbreaks
            "path",
            "danger",
            "secret",
            "secrets",
            "seeker",
            "seek",
            "silent",
            "silence",
            "whisper",
            "grace",
            "fade",
            "faded",
            "grows",
            "grow",
            "grew",
            "river",
            "stream",
            "wild",
            "trace",
            "veil",
            "echo",
            "wander",
        }

        # Tokenize on word boundaries. Substring matching (the previous approach)
        # produced false positives — e.g. "as"/"soft"/"light" match inside
        # unrelated words ("phrase", "softly"→ok, "delight") — which inflated the
        # metaphor score on ordinary prose. Whole-word matching avoids that.
        tokens = re.findall(r"[a-z']+", text.lower())
        if not tokens:
            return 0.0

        keyword_count = sum(1 for token in tokens if token in poetic_keywords)

        keyword_density = keyword_count / len(tokens)

        # Amplify signal
        score = min(1.0, keyword_density * 20)

        return score
