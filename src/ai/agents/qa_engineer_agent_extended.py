"""Compatibility wrapper for the legacy QAEngineerAgentExtended import path."""

from src.ai.agents.qa_engineer_agent import QAEngineerAgent


class QAEngineerAgentExtended(QAEngineerAgent):
    """Legacy extended class name backed by the current QA implementation."""


__all__ = ["QAEngineerAgentExtended"]
