
"""
AI Code Reviewer - главный orchestrator
Координирует все проверки и генерирует review
"""

import os
import re
from datetime import datetime
from typing import Any, Dict, List

from src.ai.agents.code_review.bsl_parser import BSLParser
from src.utils.structured_logging import StructuredLogger

try:
    from src.ai.agents.code_review.best_practices_checker import BestPracticesChecker
except ImportError:

    class BestPracticesChecker:
        def check(self, code: str, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
            issues = []
            for item in ast.get("functions", []) + ast.get("procedures", []):
                if item.get("is_export") and not item.get("has_documentation"):
                    issues.append(
                        {
                            "severity": "LOW",
                            "category": "best_practices",
                            "issue": "Exported method lacks nearby documentation",
                            "line": item.get("start_line"),
                            "rule_id": "exported-method-doc",
                            "source": "local_fallback_scanner",
                        }
                    )
            return issues


try:
    from src.ai.agents.code_review.performance_analyzer import PerformanceAnalyzer
except ImportError:

    class PerformanceAnalyzer:
        def analyze(self, code: str, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
            issues = []
            for query in ast.get("queries", []):
                if "SELECT *" in query.get("text", "").upper() or "ВЫБРАТЬ *" in query.get("text", "").upper():
                    issues.append(
                        {
                            "severity": "MEDIUM",
                            "category": "performance",
                            "issue": "Query selects all fields",
                            "line": query.get("line"),
                            "rule_id": "select-star",
                            "source": "local_fallback_scanner",
                        }
                    )
            return issues


try:
    from src.ai.agents.code_review.security_scanner import SecurityScanner
except ImportError:

    class SecurityScanner:
        def scan(self, code: str, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
            issues = []
            if re.search(r"Запрос\.Текст\s*=.*\+", code, re.IGNORECASE | re.DOTALL):
                issues.append(
                    {
                        "severity": "CRITICAL",
                        "category": "security",
                        "issue": "Dynamic query text concatenation can lead to injection",
                        "line": self._line_of(code, "Запрос.Текст"),
                        "rule_id": "bsl-dynamic-query-concat",
                        "source": "local_fallback_scanner",
                    }
                )
            if re.search(r"\bВыполнить\s*\(", code, re.IGNORECASE):
                issues.append(
                    {
                        "severity": "HIGH",
                        "category": "security",
                        "issue": "Dynamic execution requires explicit review",
                        "line": self._line_of(code, "Выполнить"),
                        "rule_id": "bsl-dynamic-execute",
                        "source": "local_fallback_scanner",
                    }
                )
            return issues

        def _line_of(self, code: str, needle: str) -> int:
            index = code.lower().find(needle.lower())
            return code[:index].count("\n") + 1 if index >= 0 else 1

logger = StructuredLogger(__name__).logger

CODE_REVIEW_CONTRACT = "code_review_evidence_contract"


class AICodeReviewer:
    """
    AI Code Reviewer

    Автоматический review BSL кода с:
    - Security scanning
    - Performance analysis
    - Best practices checking
    - AI-powered suggestions
    """

    def __init__(self, llm_client=None):
        self.parser = BSLParser()
        self.security_scanner = SecurityScanner()
        self.performance_analyzer = PerformanceAnalyzer()
        self.best_practices_checker = BestPracticesChecker()
        self.llm_client = llm_client

        # LLM для глубокого анализа (опционально)
        self.llm_configured = False
        self.llm_available = bool(llm_client)
        try:
            self.llm_api_key = os.getenv("OPENAI_API_KEY", "")
            if self.llm_api_key:
                self.llm_configured = True
        except (OSError, Exception):
            self.llm_api_key = ""

        logger.info("AI Code Reviewer initialized")

    async def review_code(
        self, code: str, filename: str = "unknown.bsl"
    ) -> Dict[str, Any]:
        """
        Review одного файла

        Args:
            code: BSL код
            filename: Имя файла

        Returns:
            Детальный review с issues и метриками
        """
        logger.info("Reviewing file", extra={"file_name": filename})

        # 1. Parse code
        try:
            ast = self.parser.parse_file(code)
        except Exception as e:
            logger.error(
                "Parsing error",
                extra={
                    "file_name": filename,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return {"error": "Failed to parse code", "details": str(e)}

        # 2. Run all scanners
        security_issues = self.security_scanner.scan(code, ast)
        performance_issues = self.performance_analyzer.analyze(code, ast)
        bp_issues = self.best_practices_checker.check(code, ast)

        # 3. AI suggestions (if available)
        ai_suggestions = []
        if self.llm_available:
            ai_suggestions = await self._ai_deep_review(code, ast)

        # 4. Aggregate results
        all_issues = security_issues + performance_issues + bp_issues + ai_suggestions

        # 5. Calculate metrics
        metrics = self._calculate_metrics(all_issues, ast)

        # 6. Determine overall status
        overall_status = self._determine_status(all_issues)

        # 7. Generate summary
        summary = self._generate_summary(all_issues, metrics, overall_status)

        return {
            "mode": CODE_REVIEW_CONTRACT,
            "coverage": self._coverage(ai_suggestions),
            "filename": filename,
            "overall_status": overall_status,
            "summary": summary,
            "metrics": metrics,
            "issues": {
                "security": security_issues,
                "performance": performance_issues,
                "best_practices": bp_issues,
                "ai_suggestions": ai_suggestions,
            },
            "ai_review": {
                "status": "executed" if ai_suggestions else "not_configured",
                "measured": bool(ai_suggestions),
                "llm_adapter_available": self.llm_available,
                "llm_credentials_present": self.llm_configured,
                "required_evidence": []
                if self.llm_available
                else ["LLM review adapter"] if self.llm_configured else ["LLM review adapter and credentials"],
                "caveats": []
                if self.llm_available
                else [
                    "Deep LLM review is not executed without an injected adapter; deterministic scanners still run."
                ],
            },
            "total_issues": len(all_issues),
            "reviewed_at": datetime.now().isoformat(),
        }

    async def review_pull_request(
        self, files_changed: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Review целого Pull Request

        Args:
            files_changed: [
                {'filename': 'Module.bsl', 'content': '...'}
            ]

        Returns:
            Aggregated review для всего PR
        """
        logger.info("Reviewing PR", extra={"files_count": len(files_changed)})

        file_reviews = []
        all_issues = []

        # Review каждого файла
        for file_data in files_changed:
            if not file_data["filename"].endswith(".bsl"):
                continue

            review = await self.review_code(
                code=file_data["content"], filename=file_data["filename"]
            )

            if "error" not in review:
                file_reviews.append(review)
                all_issues.extend(review.get("issues", {}).get("security", []))
                all_issues.extend(review.get("issues", {}).get("performance", []))
                all_issues.extend(review.get("issues", {}).get("best_practices", []))

        # Overall metrics
        overall_metrics = {
            "files_reviewed": len(file_reviews),
            "total_issues": len(all_issues),
            "critical": sum(1 for i in all_issues if i.get("severity") == "CRITICAL"),
            "high": sum(1 for i in all_issues if i.get("severity") == "HIGH"),
            "medium": sum(1 for i in all_issues if i.get("severity") == "MEDIUM"),
            "low": sum(1 for i in all_issues if i.get("severity") == "LOW"),
        }

        # Overall status
        if overall_metrics["critical"] > 0:
            overall_status = "CHANGES_REQUESTED"
        elif overall_metrics["high"] > 3:
            overall_status = "CHANGES_REQUESTED"
        elif overall_metrics["total_issues"] > 0:
            overall_status = "COMMENTED"
        else:
            overall_status = "APPROVED"

        # Generate PR summary
        pr_summary = self._generate_pr_summary(
            file_reviews, overall_metrics, overall_status
        )

        return {
            "mode": CODE_REVIEW_CONTRACT,
            "coverage": "deterministic_bsl_scanners",
            "overall_status": overall_status,
            "summary": pr_summary,
            "file_reviews": file_reviews,
            "metrics": overall_metrics,
            "reviewed_at": datetime.now().isoformat(),
        }

    async def _ai_deep_review(self, code: str, ast: Dict) -> List[Dict]:
        """AI глубокий анализ (опционально, требует LLM)"""
        if not self.llm_client:
            return []
        if hasattr(self.llm_client, "review_code"):
            result = self.llm_client.review_code(code=code, ast=ast)
        else:
            result = self.llm_client.review(code, ast)
        if hasattr(result, "__await__"):
            result = await result
        return result if isinstance(result, list) else []

    def _coverage(self, ai_suggestions: List[Dict]) -> str:
        parts = ["deterministic_bsl_scanners"]
        if ai_suggestions:
            parts.append("llm_deep_review")
        return "+".join(parts)

    def _calculate_metrics(self, issues: List[Dict], ast: Dict) -> Dict:
        """Расчет метрик качества кода"""
        return {
            "total_issues": len(issues),
            "critical": sum(1 for i in issues if i.get("severity") == "CRITICAL"),
            "high": sum(1 for i in issues if i.get("severity") == "HIGH"),
            "medium": sum(1 for i in issues if i.get("severity") == "MEDIUM"),
            "low": sum(1 for i in issues if i.get("severity") == "LOW"),
            "complexity": ast.get("total_complexity", 0),
            "loc": ast.get("loc", 0),
            "functions_count": ast.get("functions_count", 0),
        }

    def _determine_status(self, issues: List[Dict]) -> str:
        """Определение общего статуса"""
        critical_count = sum(1 for i in issues if i.get("severity") == "CRITICAL")
        high_count = sum(1 for i in issues if i.get("severity") == "HIGH")

        if critical_count > 0:
            return "CHANGES_REQUESTED"
        elif high_count > 3:
            return "CHANGES_REQUESTED"
        elif len(issues) > 0:
            return "COMMENTED"
        else:
            return "APPROVED"

    def _generate_summary(self, issues: List[Dict], metrics: Dict, status: str) -> str:
        """Генерация summary"""

        status_emoji = {"APPROVED": "✅", "COMMENTED": "💬", "CHANGES_REQUESTED": "⚠️"}

        summary = f"""
## {status_emoji.get(status, '🔍')} AI Code Review

**Status:** {status}

### 📊 Metrics
- **Total Issues:** {metrics['total_issues']}
  - 🔴 Critical: {metrics['critical']}
  - 🟠 High: {metrics['high']}
  - 🟡 Medium: {metrics['medium']}
  - 🟢 Low: {metrics['low']}

- **Code Complexity:** {metrics['complexity']}
- **Lines of Code:** {metrics['loc']}
- **Functions:** {metrics['functions_count']}
"""

        if metrics["critical"] > 0:
            summary += """
### ⚠️ CRITICAL Issues Found!

Обнаружены критичные проблемы безопасности!
Пожалуйста, исправьте перед merge.
"""

        if metrics["total_issues"] == 0:
            summary += """
### ✨ Excellent Code Quality!

Код соответствует всем best practices! 🎉
Нет критичных замечаний.
"""

        return summary

    def _generate_pr_summary(
        self, file_reviews: List[Dict], metrics: Dict, status: str
    ) -> str:
        """Генерация summary для PR"""

        status_emoji = {"APPROVED": "✅", "COMMENTED": "💬", "CHANGES_REQUESTED": "⚠️"}

        summary = f"""
## {status_emoji.get(status, '🔍')} AI Code Review Summary

**Overall Status:** {status}

### 📊 Review Metrics
- **Files Reviewed:** {metrics['files_reviewed']}
- **Total Issues Found:** {metrics['total_issues']}

**By Severity:**
- 🔴 Critical: {metrics['critical']}
- 🟠 High: {metrics['high']}
- 🟡 Medium: {metrics['medium']}
- 🟢 Low: {metrics['low']}
"""

        if metrics["critical"] > 0:
            summary += "\n### ⚠️ Action Required\n\n"
            summary += "Найдены критичные проблемы безопасности. Merge заблокирован до исправления.\n"

        elif metrics["total_issues"] == 0:
            summary += "\n### ✨ Great Job!\n\n"
            summary += "Код отличного качества! Все проверки пройдены. 🎉\n"

        return summary
