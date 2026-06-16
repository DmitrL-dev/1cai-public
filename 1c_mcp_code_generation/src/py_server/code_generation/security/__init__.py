
#!/usr/bin/env python3
"""
Security Package для 1C AI MCP Code Generation

Пакет для обеспечения безопасности генерации кода.

Версия: 1.0
Дата: 30.10.2025
"""

from .manager import SecurityAnalysisResult, SecurityManager, SecurityThreat

__version__ = "1.0.0"
__all__ = ['SecurityManager', 'SecurityThreat', 'SecurityAnalysisResult']