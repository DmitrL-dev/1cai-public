"""Technology Journal Parser (Перформер) — performance analysis for 1C:Enterprise."""

from .parser import TJParser, TJEvent
from .analyzer import TJPerformanceAnalyzer

__all__ = ["TJParser", "TJEvent", "TJPerformanceAnalyzer"]
