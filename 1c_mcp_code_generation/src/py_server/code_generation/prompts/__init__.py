
"""
Пакет системы промптов для генерации кода 1С.

Предоставляет инструменты для создания, управления и оптимизации промптов
для генерации кода 1С с помощью LLM.
"""

from .context import ContextualPromptBuilder
from .manager import PromptManager, PromptTemplate
from .optimizer import PromptOptimizer

__all__ = [
    'PromptManager',
    'PromptTemplate', 
    'PromptOptimizer',
    'ContextualPromptBuilder'
]

__version__ = '1.0.0'