# AI Agents for different roles
# Специализированные AI агенты для разных ролей
from src.ai.agents.business_analyst_agent import BusinessAnalystAgent
from src.ai.agents.qa_engineer_agent import QAEngineerAgent

try:
    from src.ai.agents.architect_agent_extended import ArchitectAgentExtended
except Exception:
    ArchitectAgentExtended = None

try:
    from src.ai.agents.onec_server_optimizer import OneCServerOptimizer
except Exception:
    OneCServerOptimizer = None

try:
    from src.ai.agents.performance_analyzer import PerformanceAnalyzer
except Exception:
    PerformanceAnalyzer = None

try:
    from src.ai.agents.security_agent import SecurityAgent
except Exception:
    SecurityAgent = None

try:
    from src.ai.agents.sql_optimizer import SQLOptimizer
except Exception:
    SQLOptimizer = None

try:
    from src.ai.agents.technology_selector import TechnologySelector
except Exception:
    TechnologySelector = None

# Optional imports (may not be installed)
try:
    from src.integrations.onec.ras_monitor import RASMonitor
except Exception:
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
