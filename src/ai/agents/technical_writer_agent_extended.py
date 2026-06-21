"""Offline-compatible technical writer compatibility layer."""

import re
from typing import Any, Dict, List


class TechnicalWriterAgentExtended:
    """Generates bounded API documentation from supplied source text."""

    async def generate_api_docs(self, code: str, module_type: str) -> Dict[str, Any]:
        operations = self._extract_operations(code)
        openapi = {
            "openapi": "3.0.3",
            "info": {
                "title": f"{module_type} API",
                "version": "0.1.0",
            },
            "paths": {
                f"/{name}": {
                    "post": {
                        "summary": name,
                        "responses": {"200": {"description": "Successful response"}},
                    }
                }
                for name in operations
            },
        }
        return {
            "mode": "offline_api_documentation",
            "module_type": module_type,
            "openapi": openapi,
            "documentation": "\n".join(f"- {name}" for name in operations),
            "coverage": "source_code" if code.strip() else "no_source_code",
        }

    def _extract_operations(self, code: str) -> List[str]:
        matches = re.findall(
            r"\b(?:Function|Procedure|Функция|Процедура)\s+([A-Za-zА-Яа-я_][\wА-Яа-я]*)",
            code,
            flags=re.IGNORECASE,
        )
        return matches or ["operation"]


__all__ = ["TechnicalWriterAgentExtended"]
