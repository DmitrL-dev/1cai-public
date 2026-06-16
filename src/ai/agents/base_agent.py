"""
Base Agent Abstract Class

Унифицированный базовый класс для всех AI агентов в системе.
Обеспечивает единый интерфейс, мониторинг через Prometheus, и audit logging.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from prometheus_client import Counter, Gauge, Histogram

# Import Adaptive LLM Selector
try:
    from src.ai.llm import AdaptiveLLMSelector

    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


class AgentCapability(str, Enum):
    """Capabilities that an agent can have"""

    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    SECURITY_AUDIT = "security_audit"
    ARCHITECTURE_ANALYSIS = "architecture_analysis"
    REQUIREMENTS_ANALYSIS = "requirements_analysis"
    DEVOPS_AUTOMATION = "devops_automation"
    PROJECT_MANAGEMENT = "project_management"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"


class AgentStatus(str, Enum):
    """Agent execution status"""

    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_APPROVAL = "requires_approval"


# Prometheus metrics
agent_requests_total = Counter(
    "ai_agent_requests_total",
    "Total number of agent requests",
    ["agent_name", "capability", "status"],
)

agent_processing_duration = Histogram(
    "ai_agent_processing_duration_seconds",
    "Agent processing duration in seconds",
    ["agent_name", "capability"],
)

agent_active_tasks = Gauge(
    "ai_agent_active_tasks", "Number of active tasks per agent", ["agent_name"]
)


class BaseAgent(ABC):
    """
    Базовый класс для всех AI агентов.

    Обеспечивает:
    - Единый интерфейс для всех агентов
    - Мониторинг через Prometheus
    - LLM integration via AdaptiveLLMSelector
    - Audit logging
    - Error handling
    """

    def __init__(self, agent_name: str, capabilities: List[AgentCapability]):
        """
        Initialize base agent.

        Args:
            agent_name: Unique agent identifier
            capabilities: List of agent capabilities
        """
        self.agent_name = agent_name
        self.capabilities = capabilities
        self.status = AgentStatus.IDLE
        self.logger = logging.getLogger(f"agent.{agent_name}")

        # LLM Integration
        self.llm_selector = AdaptiveLLMSelector() if LLM_AVAILABLE else None

        # Statistics
        self.requests_processed = 0
        self.errors_count = 0
        self.last_request_time: Optional[datetime] = None

    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method - must be implemented by each agent.

        Args:
            input_data: Input data for processing

        Returns:
            Processing result
        """

    def get_capabilities(self) -> List[AgentCapability]:
        """Get agent capabilities"""
        return self.capabilities

    def get_status(self) -> Dict[str, Any]:
        """Get agent status and statistics"""
        return {
            "agent_name": self.agent_name,
            "status": self.status.value,
            "capabilities": [cap.value for cap in self.capabilities],
            "requests_processed": self.requests_processed,
            "errors_count": self.errors_count,
            "last_request_time": self.last_request_time.isoformat()
            if self.last_request_time
            else None,
        }

    async def execute(
        self,
        input_data: Dict[str, Any],
        capability: AgentCapability,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute agent with monitoring and error handling.

        Args:
            input_data: Input data
            capability: Capability being used
            context: Optional execution context

        Returns:
            Execution result
        """
        context = context or {}

        # Update status
        self.status = AgentStatus.PROCESSING
        self.last_request_time = datetime.utcnow()

        # Increment active tasks
        agent_active_tasks.labels(agent_name=self.agent_name).inc()

        try:
            # Start timer
            with agent_processing_duration.labels(
                agent_name=self.agent_name, capability=capability.value
            ).time():
                # Process
                result = await self.process(input_data)

            # Update metrics
            agent_requests_total.labels(
                agent_name=self.agent_name,
                capability=capability.value,
                status="success",
            ).inc()

            self.requests_processed += 1
            self.status = AgentStatus.COMPLETED

            return {
                "success": True,
                "result": result,
                "agent": self.agent_name,
                "capability": capability.value,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            # Update error metrics
            agent_requests_total.labels(
                agent_name=self.agent_name, capability=capability.value, status="error"
            ).inc()

            self.errors_count += 1
            self.status = AgentStatus.FAILED

            self.logger.error(
                f"Agent {self.agent_name} failed: {e}",
                exc_info=True,
                extra={
                    "capability": capability.value,
                    "input_data": str(input_data)[:200],
                },
            )

            return {
                "success": False,
                "error": str(e),
                "agent": self.agent_name,
                "capability": capability.value,
                "timestamp": datetime.utcnow().isoformat(),
            }

        finally:
            # Decrement active tasks
            agent_active_tasks.labels(agent_name=self.agent_name).dec()

    def _log_audit(
        self, action: str, details: Dict[str, Any], user_id: Optional[str] = None
    ) -> None:
        """
        Log audit event.

        Args:
            action: Action performed
            details: Action details
            user_id: User who triggered the action
        """
        self.logger.info(
            f"Audit: {action}",
            extra={
                "agent": self.agent_name,
                "action": action,
                "user_id": user_id,
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


__all__ = ["BaseAgent", "AgentCapability", "AgentStatus"]
