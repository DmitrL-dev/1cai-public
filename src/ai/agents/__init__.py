# AI Agents for different roles
# Специализированные AI агенты для разных ролей
# Phase 8: removed phantom imports for deleted agents

from src.ai.agents.architect_agent_extended import ArchitectAgentExtended
from src.ai.agents.business_analyst_agent import BusinessAnalystAgent
from src.ai.agents.onec_server_optimizer import OneCServerOptimizer
from src.ai.agents.performance_analyzer import PerformanceAnalyzer
from src.ai.agents.qa_engineer_agent import QAEngineerAgent
from src.ai.agents.security_agent import SecurityAgent
from src.ai.agents.sql_optimizer import SQLOptimizer
from src.ai.agents.technology_selector import TechnologySelector

# Optional imports (may not be installed)
try:
    from src.integrations.onec.ras_monitor import RASMonitor
except ImportError:
    RASMonitor = None

__all__ = [
    "ArchitectAgentExtended",
    "BusinessAnalystAgent",
    "OneCServerOptimizer",
    "PerformanceAnalyzer",
    "QAEngineerAgent",
    "SecurityAgent",
    "SQLOptimizer",
    "TechnologySelector",
    "RASMonitor",
]
