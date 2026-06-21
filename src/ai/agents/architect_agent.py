"""Compatibility wrapper for the legacy ArchitectAgent import path."""

from src.ai.agents.architect_agent_extended import ArchitectAgentExtended


class ArchitectAgent(ArchitectAgentExtended):
    """Legacy class name backed by the extended architect implementation."""


__all__ = ["ArchitectAgent"]
