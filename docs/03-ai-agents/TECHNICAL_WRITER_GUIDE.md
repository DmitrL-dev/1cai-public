# Technical Writer Agent — User Guide

**Version:** 1.0 | **Status:** ✅ Production Ready

## Overview
Technical Writer Agent автоматизирует создание документации, API docs, user guides.

## Features
- 📚 Documentation Generation
- 📖 API Docs Creation
- 🎯 User Guide Writing
- 🔄 Doc Sync
- 📊 Diagram Generation

## Quick Start
```python
from technical_writer_agent import TechnicalWriterAgent

agent = TechnicalWriterAgent()

# Generate API docs
api_docs = await agent.generate_api_docs(
    code="/path/to/api",
    format="openapi"
)

# Create user guide
guide = await agent.create_user_guide(
    module="dashboard",
    audience="end_users"
)

# Generate diagrams
diagram = await agent.generate_diagram(type="sequence")
```

## API
```http
POST /api/v1/technical-writer/generate-api-docs
POST /api/v1/technical-writer/create-guide
POST /api/v1/technical-writer/generate-diagram
```

**See:** [Technical Writer Module README](../../src/modules/technical_writer/README.md)
