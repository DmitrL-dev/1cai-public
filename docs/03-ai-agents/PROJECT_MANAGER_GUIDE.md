# Project Manager Agent — User Guide

**Version:** 1.0 | **Status:** ⚠️ In Development

## Overview
Project Manager Agent помогает в планировании проектов, tracking, risk management.

## Features (Planned)
- 📊 Project Planning
- 🎯 Task Tracking
- 📈 Progress Monitoring
- 🔄 Risk Management
- 📝 Reporting

## Quick Start
```python
from project_manager_agent import ProjectManagerAgent

agent = ProjectManagerAgent()

# Create project plan
plan = await agent.create_plan(
    project="1C Integration",
    duration_weeks=12
)

# Track progress
progress = await agent.track_progress(project_id="proj_123")

# Analyze risks
risks = await agent.analyze_risks(project_id="proj_123")
```

## API (Planned)
```http
POST /api/v1/pm/create-plan
GET /api/v1/pm/progress
GET /api/v1/pm/risks
```

**See:** [Project Manager Module README](../../src/modules/project_manager/README.md)
