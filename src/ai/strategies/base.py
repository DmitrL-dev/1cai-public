from abc import ABC, abstractmethod
from typing import Any, Dict


class AIStrategy(ABC):
    """Abstract base class for AI strategies"""

    @abstractmethod
    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the strategy"""

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return service name"""
