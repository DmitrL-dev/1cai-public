# SQL Optimizer Agent — User Guide

**Version:** 1.0 | **Status:** ✅ Production Ready

## Overview
SQL Optimizer Agent оптимизирует SQL запросы для 1C, анализирует планы выполнения.

## Features
- 🎯 Query Optimization
- 📊 Execution Plan Analysis
- 📈 Performance Recommendations
- 🔄 Index Suggestions
- 📝 Reports

## Quick Start
```python
from sql_optimizer_agent import SQLOptimizerAgent

agent = SQLOptimizerAgent()

# Optimize query
optimized = await agent.optimize_query(
    query="SELECT * FROM Документы WHERE Дата > '2025-01-01'"
)

# Analyze execution plan
plan = await agent.analyze_plan(query="...")

# Get index suggestions
indexes = await agent.suggest_indexes(table="Документы")
```

## API
```http
POST /api/v1/sql/optimize
POST /api/v1/sql/analyze-plan
GET /api/v1/sql/suggest-indexes
```

**See:** [SQL Optimizer Module README](../../src/modules/sql_optimizer/README.md)
