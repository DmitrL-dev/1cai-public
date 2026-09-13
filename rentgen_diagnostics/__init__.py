"""Optional, isolated diagnostic adapters. Core authorization stays with callers."""

from .sarif_adapter import SarifContext, parse_sarif

__all__ = ["SarifContext", "parse_sarif"]
