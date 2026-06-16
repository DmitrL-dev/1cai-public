
#!/usr/bin/env python3
"""
LLM Package для 1C AI MCP Code Generation

Пакет для интеграции с LLM провайдерами.

Версия: 1.0
Дата: 30.10.2025
"""

from .client import LLMClient, LLMRequest, LLMResponse

__version__ = "1.0.0"
__all__ = ['LLMClient', 'LLMRequest', 'LLMResponse']