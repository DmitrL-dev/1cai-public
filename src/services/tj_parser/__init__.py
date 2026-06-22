"""Technology Journal Parser (Перформер) — performance analysis for 1C:Enterprise."""

from .analyzer import TJPerformanceAnalyzer
from .parser import TJEvent, TJParser

__all__ = ["TJParser", "TJEvent", "TJPerformanceAnalyzer"]
