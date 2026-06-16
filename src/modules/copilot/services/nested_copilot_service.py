"""
Nested Copilot Service

Multi-level code completion with Continuum Memory System.
Implements multi-time-scale predictions for better code suggestions.

Inspired by Nested Learning paradigm.
"""

import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple


if TYPE_CHECKING:
    from src.modules.copilot.services.copilot_service import CopilotService

from src.ml.continual_learning.code_memory import CodeMemory
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class NestedCopilotService:
    """
    Multi-level code completion with Nested Learning

    5-level predictions:
    - L0 (char): Next character predictions
    - L1 (token): Next token/word predictions
    - L2 (function): Function-level completions
    - L3 (project): Project-specific patterns
    - L4 (platform): 1C platform knowledge

    Key features:
    - Multi-time-scale predictions
    - Confidence scoring
    - Acceptance learning
    - Context-aware weighting

    Example:
        >>> service = NestedCopilotService(base_copilot)
        >>> completions = service.get_completions_nested(
        ...     code="Функция ",
        ...     context={"project": "MyProject"}
        ... )
        >>> service.learn_from_acceptance(completion_id, accepted=True)
    """

    def __init__(self, base_copilot: "CopilotService"):
        """
        Initialize nested copilot service

        Args:
            base_copilot: Base copilot service
        """
        self.base = base_copilot

        # Create code memory
        self.code_memory = CodeMemory()

        # Statistics
        self.stats = {
            "total_completions": 0,
            "total_acceptances": 0,
            "total_rejections": 0,
            "acceptance_rate": 0.0,
            "keystroke_savings": 0,
        }

        # Completion history for learning
        self.completion_history: Dict[str, Dict] = {}

        logger.info("Created NestedCopilotService with 5-level code memory")

    def get_completions_nested(
        self, code: str, context: Optional[Dict] = None, max_suggestions: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get multi-level code completions

        Args:
            code: Current code prefix
            context: Optional context (project, module, etc.)
            max_suggestions: Maximum number of suggestions

        Returns:
            List of completion suggestions with confidence scores
        """
        context = context or {}
        self.stats["total_completions"] += 1

        # 1. Get suggestions from all levels
        level_suggestions = self.code_memory.get_suggestions(
            code, context=context, k=max_suggestions)

        # 2. Merge and score suggestions
        merged = self._merge_suggestions(level_suggestions, code, context)

        # 3. Fallback to base copilot if needed
        if len(merged) < max_suggestions:
            try:
                base_completions = self.base.get_completions(
                    code, max_completions=max_suggestions - len(merged))

                # Add base completions with lower confidence
                for comp in base_completions:
                    merged.append(
                        {
                            "text": comp.get("text", ""),
                            "confidence": 0.3,  # Lower confidence for base
                            "source": "base",
                            "level": "fallback",
                        }
                    )
            except Exception as e:
                logger.warning("Base copilot failed: %s", e)

        # 4. Sort by confidence
        merged.sort(key=lambda x: x["confidence"], reverse=True)

        # 5. Store for learning
        completion_id = self._generate_completion_id(code)
        self.completion_history[completion_id] = {
            "code": code,
            "suggestions": merged[:max_suggestions],
            "context": context,
            "timestamp": time.time(),
        }

        logger.debug(
            "Generated nested completions",
            extra={"num_suggestions": len(merged[:max_suggestions]), "levels_used": list(
                level_suggestions.keys())},
        )

        return merged[:max_suggestions]

    def _merge_suggestions(
        self, level_suggestions: Dict[str, List[Tuple[str, float, Any]]], code: str, context: Dict
    ) -> List[Dict[str, Any]]:
        """
        Merge suggestions from multiple levels with confidence scoring

        Args:
            level_suggestions: Dict of level -> [(key, similarity, data)]
            code: Current code prefix
            context: Context

        Returns:
            List of merged suggestions
        """
        merged = []
        seen_texts = set()

        # Compute level weights
        weights = self._compute_level_weights(context)

        # Process each level
        for level_name, suggestions in level_suggestions.items():
            level_weight = weights.get(level_name, 0.2)

            for key, similarity, data in suggestions:
                if not isinstance(data, dict):
                    continue

                suggestion_code = data.get("code", "")

                # Extract completion (remove prefix)
                if suggestion_code.startswith(code):
                    completion = suggestion_code[len(code) :]
                else:
                    completion = suggestion_code

                # Skip if already seen
                if completion in seen_texts:
                    continue

                seen_texts.add(completion)

                # Compute confidence
                confidence = similarity * level_weight

                merged.append(
                    {
                        "text": completion,
                        "confidence": float(confidence),
                        "source": "nested",
                        "level": level_name,
                        "similarity": float(similarity),
                    }
                )

        return merged

    def _compute_level_weights(self, context: Dict) -> Dict[str, float]:
        """
        Compute level weights based on context

        Args:
            context: Context dictionary

        Returns:
            Dict mapping level -> weight
        """
        code_type = context.get("type", "unknown")

        if code_type == "platform":
            # Platform code: rely on platform knowledge
            return {"char": 0.1, "token": 0.1, "function": 0.2, "project": 0.1, "platform": 0.5}

        elif code_type == "new":
            # New code: rely on fast levels
            return {"char": 0.4, "token": 0.3, "function": 0.2, "project": 0.05, "platform": 0.05}

        else:
            # Default: balanced
            return {"char": 0.25, "token": 0.25, "function": 0.25, "project": 0.15, "platform": 0.1}

    def learn_from_acceptance(self, completion_id: str, accepted: bool, selected_index: Optional[int] = None):
        """
        Learn from user acceptance/rejection

        Args:
            completion_id: Completion identifier
            accepted: Whether user accepted any suggestion
            selected_index: Index of selected suggestion (if accepted)
        """
        if completion_id not in self.completion_history:
            logger.warning("Unknown completion_id: %s", completion_id)
            return

        history = self.completion_history[completion_id]
        suggestions = history["suggestions"]
        context = history["context"]

        # Update stats
        if accepted:
            self.stats["total_acceptances"] += 1

            # Track keystroke savings
            if selected_index is not None and selected_index < len(suggestions):
                saved_keystrokes = len(suggestions[selected_index]["text"])
                self.stats["keystroke_savings"] += saved_keystrokes
        else:
            self.stats["total_rejections"] += 1

        # Update acceptance rate
        total = self.stats["total_acceptances"] + self.stats["total_rejections"]
        if total > 0:
            self.stats["acceptance_rate"] = self.stats["total_acceptances"] / total

        # Learn from feedback
        if accepted and selected_index is not None and selected_index < len(suggestions):
            # Accepted suggestion
            selected = suggestions[selected_index]
            code = history["code"] + selected["text"]

            self.code_memory.learn_from_acceptance(code, True, context)

        elif not accepted:
            # All suggestions rejected
            for suggestion in suggestions:
                code = history["code"] + suggestion["text"]
                self.code_memory.learn_from_acceptance(code, False, context)

        logger.debug(
            "Learned from acceptance",
            extra={
                "completion_id": completion_id[:16] + "...",
                "accepted": accepted,
                "acceptance_rate": self.stats["acceptance_rate"],
            },
        )

    def _generate_completion_id(self, code: str) -> str:
        """Generate unique ID for completion"""
        import hashlib

        timestamp = str(time.time())
        combined = f"{code}_{timestamp}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        cms_stats = self.code_memory.get_stats()

        return {**self.stats, "code_memory": cms_stats.to_dict()}

    def health_check(self) -> Dict[str, Any]:
        """Health check"""
        return {
            "status": "healthy",
            "code_memory_levels": len(self.code_memory.levels),
            "total_completions": self.stats["total_completions"],
            "acceptance_rate": self.stats["acceptance_rate"],
            "keystroke_savings": self.stats["keystroke_savings"],
        }
