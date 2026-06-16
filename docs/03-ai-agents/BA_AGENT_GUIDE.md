# BA Agent — User Guide

**Version:** 1.0 | **Status:** ✅ Production Ready

## Overview
Business Analyst Agent помогает в сборе требований, анализе бизнес-процессов, создании документации.

## Features
- 📝 Requirements Gathering
- 📊 Process Modeling (BPMN)
- 🎯 KPI Calculation
- 📈 Analytics & Reporting
- 🔄 Traceability & Compliance

## Quick Start
```python
from ba_agent import BAAgent

agent = BAAgent()

# Create session
session = await agent.create_session(
    project="1C Integration",
    stakeholders=["PO", "Tech Lead"]
)

# Generate BPMN
bpmn = await agent.generate_bpmn("Order processing workflow")

# Calculate KPIs
kpis = await agent.calculate_kpis(project_id="proj_123")
```

## API
```http
POST /api/v1/ba/sessions/create
POST /api/v1/ba/bpmn/generate
GET /api/v1/ba/kpis
```

**See:** [BA Module README](../../src/modules/business_analyst/README.md)
