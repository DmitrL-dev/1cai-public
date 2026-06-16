
"""
Пакет шаблонов для генерации кода 1С.

Содержит готовые шаблоны для создания различных типов объектов 1С:
- Обработки
- Отчеты
- Справочники
- Документы
"""

from .library import TemplateLibrary
from .manager import CodeTemplate, TemplateManager
from .processor import TemplateProcessor

__all__ = [
    'TemplateManager',
    'CodeTemplate',
    'TemplateLibrary',
    'TemplateProcessor'
]

__version__ = '1.0.0'