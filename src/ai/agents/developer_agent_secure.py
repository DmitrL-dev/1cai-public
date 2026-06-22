"""
Secure Developer AI Agent
Based on Agents Rule of Two: [AB] Configuration

[A] Can process untrusted inputs (any code)
[B] Can access sensitive data (repository)
[C] CANNOT change state automatically (requires human approval!)
"""

import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.security.ai_security_layer import AgentRuleOfTwoConfig, AISecurityLayer

DEVELOPER_SECURE_CONTRACT = "developer_secure_evidence_contract"


class DeveloperAISecure:
    """
    Secure Developer AI - требует human approval для всех изменений
    """

    def __init__(self, ai_model=None, repository_writer=None):
        self.ai_model = ai_model
        self.repository_writer = repository_writer
        self.security = AISecurityLayer()

        # Конфигурация Rule of Two
        self.config = AgentRuleOfTwoConfig(
            can_process_untrusted=True,  # [A] - принимает любой prompt
            can_access_sensitive=True,  # [B] - видит репозиторий
            can_change_state=False,  # [C] - НЕ пишет автоматически
        )

        # Временное хранилище pending suggestions
        self._pending_suggestions = {}

    def generate_code(
        self, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Генерирует код с AI

        Returns:
            {
                'suggestion': generated code,
                'token': approval token,
                'safety': safety analysis,
                'requires_approval': True,
                'preview_url': URL для preview
            }
        """
        context = context or {}

        # Проверка входа через security layer
        input_check = self.security.validate_input(
            user_input=prompt,
            agent_id="developer_ai_secure",
            agent_config=self.config,
            context=context,
        )

        if not input_check.allowed:
            return {
                "error": input_check.reason,
                "blocked": True,
                "details": input_check.details,
            }

        # Генерация кода с AI или честный offline contract
        try:
            suggestion = self._generate_with_ai(prompt, context)
        except Exception as e:
            return {"error": f"AI generation failed: {str(e)}", "blocked": True}

        # Проверка выхода через security layer
        output_check = self.security.validate_output(
            ai_output=suggestion,
            agent_id="developer_ai_secure",
            agent_config=self.config,
            context=context,
        )

        if not output_check.allowed:
            return {"error": output_check.reason, "blocked": True}

        # Если был redacted - используем redacted версию
        final_suggestion = output_check.details.get("output", suggestion)

        # Анализ безопасности кода
        safety_analysis = self._analyze_code_safety(final_suggestion)

        # Генерация approval token
        token = str(uuid.uuid4())

        # Сохраняем для последующего approval
        self._pending_suggestions[token] = {
            "suggestion": final_suggestion,
            "created_at": datetime.now(),
            "prompt": prompt,
            "context": context,
            "safety": safety_analysis,
            "approved": False,
            "generation_mode": self._generation_mode(),
        }

        return {
            "success": True,
            "mode": DEVELOPER_SECURE_CONTRACT,
            "generation_mode": self._generation_mode(),
            "suggestion": final_suggestion,
            "token": token,
            "safety": safety_analysis,
            "requires_approval": True,
            "can_auto_apply": bool(self.ai_model) and safety_analysis["score"] > 0.95,
            "preview_url": f"/api/code-review/preview/{token}",
            "redacted": output_check.details.get("redacted", False),
            "required_evidence": self._generation_required_evidence(),
            "caveats": self._generation_caveats(),
        }

    def apply_suggestion(
        self, token: str, approved_by_user: str, changes_made: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Применяет suggestion ТОЛЬКО после human approval

        Args:
            token: Approval token от generate_code()
            approved_by_user: User ID кто одобрил
            changes_made: Опциональные изменения от пользователя

        Returns:
            Result of application
        """
        if not approved_by_user:
            raise ValueError("Human approver is required")

        # Проверка токена
        if token not in self._pending_suggestions:
            return {"error": "Invalid or expired token", "blocked": True}

        suggestion_data = self._pending_suggestions[token]

        # Проверка expiration (30 минут)
        if datetime.now() - suggestion_data["created_at"] > timedelta(minutes=30):
            del self._pending_suggestions[token]
            return {"error": "Token expired (30 min limit)", "blocked": True}

        # Получаем финальный код
        final_code = changes_made if changes_made else suggestion_data["suggestion"]

        # Повторная проверка безопасности
        safety = self._analyze_code_safety(final_code)

        if safety["score"] < 0.5:
            return {
                "error": "Code safety score too low",
                "blocked": True,
                "safety": safety,
            }

        # Audit logging
        self.security.audit_logger.log_ai_request(
            agent_id="developer_ai_secure",
            user_id=approved_by_user,
            input_hash=self.security._hash_input(suggestion_data["prompt"]),
            rule_of_two_config=self.config.get_config_code(),
            approved_by_human=True,  # ✅ КРИТИЧНО - human одобрил!
        )

        # Применяем изменения
        try:
            result = self._write_to_repository(
                code=final_code, author=approved_by_user, co_author="AI-Assistant"
            )
            if not result.get("applied", False):
                return {
                    "success": False,
                    "applied": False,
                    "blocked": True,
                    "result": result,
                    "error": result.get(
                        "reason", "Repository writer is not configured"
                    ),
                }

            # Удаляем из pending
            del self._pending_suggestions[token]

            return {
                "success": True,
                "applied": True,
                "result": result,
                "commit_sha": result.get("commit_sha"),
            }

        except Exception as e:
            return {"error": f"Failed to apply: {str(e)}", "blocked": True}

    def bulk_approve_safe_suggestions(
        self, tokens: List[str], approved_by_user: str
    ) -> Dict[str, Any]:
        """
        Bulk approval для multiple suggestions
        Применяется только к "safe" suggestions (score > 0.95)
        """
        results = {"approved": [], "rejected": [], "errors": []}

        for token in tokens:
            if token not in self._pending_suggestions:
                results["errors"].append({"token": token, "reason": "Invalid token"})
                continue

            suggestion = self._pending_suggestions[token]

            # Только безопасные можно bulk approve
            if suggestion["safety"]["score"] > 0.95:
                result = self.apply_suggestion(token, approved_by_user)
                if result.get("success"):
                    results["approved"].append(token)
                else:
                    results["rejected"].append(
                        {"token": token, "reason": result.get("error")}
                    )
            else:
                results["rejected"].append(
                    {"token": token, "reason": "Safety score too low for bulk approval"}
                )

        return results

    def _generate_with_ai(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate code with the configured model or return an offline contract."""
        if self.ai_model:
            return self.ai_model.generate(prompt, context)

        sanitized_prompt = " ".join(prompt.split())[:200]
        return "\n".join(
            [
                "# Offline developer generation contract",
                f"# Requested change: {sanitized_prompt}",
                "# No AI model is configured for code synthesis in this runtime.",
                "# Provide a model adapter or an explicit patch before repository apply.",
                "",
                "def generated_change_requires_model(*args, **kwargs):",
                "    raise RuntimeError(",
                '        "No code synthesis model is configured; review the request and provide an explicit patch."',
                "    )",
            ]
        )

    def _analyze_code_safety(self, code: str) -> Dict[str, Any]:
        """Анализ безопасности сгенерированного кода"""
        concerns = []
        score = 1.0

        # Check 1: Hardcoded credentials
        if self._contains_credentials(code):
            concerns.append(
                {
                    "severity": "CRITICAL",
                    "issue": "Hardcoded credentials detected",
                    "line": self._find_credential_lines(code),
                }
            )
            score -= 0.5

        # Check 2: SQL injection vulnerability
        if self._has_sql_injection_vuln(code):
            concerns.append(
                {
                    "severity": "HIGH",
                    "issue": "Potential SQL injection vulnerability",
                    "suggestion": "Use parameterized queries",
                }
            )
            score -= 0.3

        # Check 3: XSS vulnerability
        if self._has_xss_vuln(code):
            concerns.append(
                {
                    "severity": "HIGH",
                    "issue": "Potential XSS vulnerability",
                    "suggestion": "Sanitize user input",
                }
            )
            score -= 0.3

        # Check 4: Dangerous operations
        if self._has_dangerous_operations(code):
            concerns.append(
                {
                    "severity": "MEDIUM",
                    "issue": "Dangerous operation (eval, exec, etc.)",
                    "suggestion": "Use safer alternatives",
                }
            )
            score -= 0.2

        return {
            "score": max(0, score),
            "concerns": concerns,
            "safe": len(concerns) == 0,
            "auto_approvable": score > 0.95,
        }

    def _contains_credentials(self, code: str) -> bool:
        """Детектирует hardcoded credentials"""
        patterns = [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'api[_-]?key\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
        ]

        for pattern in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True

        return False

    def _find_credential_lines(self, code: str) -> List[int]:
        """Находит строки с credentials"""
        lines = []
        for i, line in enumerate(code.split("\n"), 1):
            if self._contains_credentials(line):
                lines.append(i)
        return lines

    def _has_sql_injection_vuln(self, code: str) -> bool:
        """Детектирует SQL injection vulnerabilities"""
        # String concatenation in SQL
        patterns = [
            r'execute\(["\'].*\+.*["\']',
            r'query\(["\'].*\+.*["\']',
            r'f["\']SELECT.*{.*}',
        ]

        for pattern in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True

        return False

    def _has_xss_vuln(self, code: str) -> bool:
        """Детектирует XSS vulnerabilities"""
        patterns = [
            r"innerHTML\s*=",
            r"dangerouslySetInnerHTML",
            r"<script>.*</script>",
        ]

        for pattern in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True

        return False

    def _has_dangerous_operations(self, code: str) -> bool:
        """Детектирует опасные операции"""
        dangerous = ["eval(", "exec(", "compile(", "__import__"]

        return any(op in code for op in dangerous)

    def _write_to_repository(
        self, code: str, author: str, co_author: str = "AI-Assistant"
    ) -> Dict[str, Any]:
        """Write to repository through an explicitly configured adapter."""
        if not self.repository_writer:
            return {
                "success": False,
                "applied": False,
                "mode": DEVELOPER_SECURE_CONTRACT,
                "reason": "repository_writer_not_configured",
                "commit_sha": None,
                "author": author,
                "co_author": co_author,
                "timestamp": datetime.now().isoformat(),
                "required_evidence": [
                    "repository writer adapter",
                    "target branch",
                    "change set",
                ],
                "caveats": [
                    "No synthetic commit SHA is produced without a repository adapter."
                ],
            }

        result = self.repository_writer.write(
            code=code, author=author, co_author=co_author
        )
        result.setdefault("success", True)
        result.setdefault("applied", True)
        result.setdefault("mode", DEVELOPER_SECURE_CONTRACT)
        return result

    def _generation_mode(self) -> str:
        return "model_generation" if self.ai_model else "offline_generation_contract"

    def _generation_required_evidence(self) -> List[str]:
        required = []
        if not self.ai_model:
            required.append("AI code synthesis model adapter")
        if not self.repository_writer:
            required.append("repository writer adapter for apply")
        return required

    def _generation_caveats(self) -> List[str]:
        caveats = [
            "Human approval is required before any repository write.",
        ]
        if not self.ai_model:
            caveats.append(
                "The returned suggestion is an offline contract, not synthesized implementation code."
            )
        if not self.repository_writer:
            caveats.append(
                "Apply will not create a commit until a repository writer adapter is configured."
            )
        return caveats
