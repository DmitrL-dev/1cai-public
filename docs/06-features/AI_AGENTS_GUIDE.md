# AI Agents — Overview Guide

**Version:** 1.0 | **Status:** ✅ Production Ready

## Overview
1C AI Stack включает 9 специализированных AI агентов для автоматизации разработки.

## Available Agents

### 1. DevOps Agent
- CI/CD Optimization
- Log Analysis
- Cost Management
- **Guide:** [DevOps Agent](../03-ai-agents/DEVOPS_AGENT_GUIDE.md)

### 2. Business Analyst Agent
- Requirements Gathering
- BPMN Generation
- KPI Calculation
- **Guide:** [BA Agent](../03-ai-agents/BA_AGENT_GUIDE.md)

### 3. QA Engineer Agent
- Test Generation
- Quality Analysis
- Bug Detection
- **Guide:** [QA Agent](../03-ai-agents/QA_AGENT_GUIDE.md)

### 4. Architect Agent
- Architecture Design
- Pattern Recognition
- Diagram Generation
- **Guide:** [Architect Agent](../03-ai-agents/ARCHITECT_AGENT_GUIDE.md)

### 5. Security Agent
- Security Audit
- Vulnerability Scanning
- Compliance Checking
- **Guide:** [Security Agent](../03-ai-agents/SECURITY_AGENT_GUIDE.md)

### 6. Technical Writer Agent
- Documentation Generation
- API Docs
- User Guides
- **Guide:** [Technical Writer](../03-ai-agents/TECHNICAL_WRITER_GUIDE.md)

### 7. Project Manager Agent
- Project Planning
- Progress Tracking
- Risk Management
- **Guide:** [PM Agent](../03-ai-agents/PROJECT_MANAGER_GUIDE.md)

### 8. RAS Monitor Agent
- RAS Monitoring
- Performance Analysis
- Alerts
- **Guide:** [RAS Monitor](../03-ai-agents/RAS_MONITOR_GUIDE.md)

### 9. SQL Optimizer Agent
- Query Optimization
- Execution Plan Analysis
- Index Suggestions
- **Guide:** [SQL Optimizer](../03-ai-agents/SQL_OPTIMIZER_AGENT_GUIDE.md)

## Quick Start

```python
from ai_agents import DevOpsAgent, BAAgent, QAAgent

# Initialize agents
devops = DevOpsAgent()
ba = BAAgent()
qa = QAAgent()

# Use agents
logs = await devops.analyze_logs("/var/log")
bpmn = await ba.generate_bpmn("Order processing")
tests = await qa.generate_tests(code="...")
```

## Architecture

```
┌─────────────────────────────────────┐
│        AI Agent Orchestrator        │
├─────────────────────────────────────┤
│  DevOps │ BA │ QA │ Architect │...  │
└─────────────────────────────────────┘
```

**See:** [AI Agents Directory](../03-ai-agents/)
