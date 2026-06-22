"""
Deterministic BSL auto-fixes for code review findings.

The fixer only applies local, explainable rewrites. Anything that requires
semantic knowledge remains a review recommendation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

AUTO_FIXER_CONTRACT = "code_review_auto_fixer_evidence_contract"


class AutoFixer:
    """Small deterministic fixer for high-confidence BSL review findings."""

    def auto_fix_all(self, code: str, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        fixed_code = code
        applied = []
        skipped = []

        for issue in issues:
            rule_id = str(issue.get("rule_id") or "")
            issue_text = str(issue.get("issue") or "").lower()
            if rule_id == "bsl-dynamic-query-concat" or "injection" in issue_text:
                before = fixed_code
                fixed_code = self.fix_sql_injection(fixed_code, issue)
                if fixed_code != before:
                    applied.append(
                        {
                            "rule_id": rule_id or "sql-injection",
                            "strategy": "query_parameterization",
                            "confidence": "pattern_match",
                        }
                    )
                else:
                    skipped.append(
                        {
                            "rule_id": rule_id or "sql-injection",
                            "reason": "pattern_not_matched",
                        }
                    )

        return {
            "mode": AUTO_FIXER_CONTRACT,
            "fixed_code": fixed_code,
            "applied_fixes": applied,
            "skipped_fixes": skipped,
            "caveats": [
                "Only deterministic pattern fixes are applied; semantic rewrites still require developer review."
            ],
        }

    def fix_sql_injection(self, code: str, issue: Dict[str, Any]) -> str:
        pattern = re.compile(
            r"(?P<indent>^[ \t]*)(?P<target>Запрос\.Текст\s*=\s*)"
            r"\"(?P<sql>[^\"]*)\"\s*\+\s*(?P<variable>[A-Za-zА-Яа-я_][\wА-Яа-я]*)"
            r"(?:\s*\+\s*\"(?P<suffix>[^\"]*)\")?\s*;?",
            re.IGNORECASE | re.MULTILINE,
        )

        def replace(match: re.Match[str]) -> str:
            indent = match.group("indent")
            target = match.group("target")
            sql = match.group("sql")
            variable = match.group("variable")
            suffix = match.group("suffix") or ""
            parameter = self._parameter_name(variable)
            parameterized_sql = self._parameterize_sql(sql, suffix, parameter)
            return (
                f'{indent}{target}"{parameterized_sql}";\n'
                f'{indent}Запрос.УстановитьПараметр("{parameter}", {variable});'
            )

        return pattern.sub(replace, code)

    def _parameter_name(self, variable: str) -> str:
        return re.sub(r"\W+", "", variable, flags=re.UNICODE) or "Параметр"

    def _parameterize_sql(self, sql: str, suffix: str, parameter: str) -> str:
        combined = f"{sql}{suffix}"
        combined = re.sub(r"'\s*'$", "", combined).rstrip()
        if re.search(r"=\s*'?$", sql):
            return re.sub(r"=\s*'?$", f"= &{parameter}", sql).rstrip()
        if re.search(r"=\s*'?\s*$", combined):
            return re.sub(r"=\s*'?\s*$", f"= &{parameter}", combined).rstrip()
        return f"{sql.rstrip()} &{parameter}{suffix}"


__all__ = ["AUTO_FIXER_CONTRACT", "AutoFixer"]
