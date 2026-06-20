"""Deterministic BSL performance analyzer used by the code-review pipeline."""

import re
from typing import Any, Dict, List


_SELECT_STAR_PATTERN = re.compile(r"\b(select|выбрать)\s+\*", flags=re.IGNORECASE)


class PerformanceAnalyzer:
    """Detects high-confidence local performance smells in BSL code."""

    def analyze(self, code: str, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.detect_select_star_queries(
            code, ast
        ) + self.detect_n_plus_one_queries(code, ast)

    def detect_select_star_queries(
        self, code: str, ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        issues = [
            {
                "type": "SELECT_STAR_QUERY",
                "severity": "MEDIUM",
                "category": "performance",
                "issue": "Query selects all fields; project only the fields used by the caller.",
                "line": self._line_for_index(code, match.start()),
                "rule_id": "bsl-select-star",
                "source": "deterministic_scanner",
            }
            for match in _SELECT_STAR_PATTERN.finditer(code)
        ]
        if issues:
            return issues

        for query in ast.get("queries", []) if isinstance(ast, dict) else []:
            if not isinstance(query, dict):
                continue
            text = str(query.get("text") or query.get("sql") or "")
            if _SELECT_STAR_PATTERN.search(text):
                issues.append(
                    {
                        "type": "SELECT_STAR_QUERY",
                        "severity": "MEDIUM",
                        "category": "performance",
                        "issue": "Query selects all fields; project only the fields used by the caller.",
                        "line": int(query.get("line") or query.get("start_line") or 1),
                        "rule_id": "bsl-select-star",
                        "source": "deterministic_scanner",
                    }
                )
        return issues

    def detect_n_plus_one_queries(
        self, code: str, ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        lowered = code.casefold()
        has_loop = any(marker in lowered for marker in ("цикл", "loop", "для "))
        has_query_execution = any(
            marker in lowered
            for marker in ("выполнить", "execute", "новый запрос", "new query")
        )
        if not (has_loop and has_query_execution):
            return []
        return [
            {
                "type": "N_PLUS_ONE_QUERY",
                "severity": "HIGH",
                "category": "performance",
                "issue": "Query execution appears inside a loop.",
                "line": self._line_of_first_marker(code, ("Выполнить", "execute")),
                "rule_id": "bsl-query-in-loop",
                "source": "deterministic_scanner",
            }
        ]

    def _line_of_first_marker(self, code: str, markers: tuple[str, ...]) -> int:
        lowered = code.casefold()
        indexes = [lowered.find(marker.casefold()) for marker in markers]
        indexes = [index for index in indexes if index >= 0]
        index = min(indexes) if indexes else 0
        return code[:index].count("\n") + 1

    def _line_for_index(self, code: str, index: int) -> int:
        return code[:index].count("\n") + 1


__all__ = ["PerformanceAnalyzer"]
