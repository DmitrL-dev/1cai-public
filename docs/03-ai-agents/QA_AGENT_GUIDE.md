# QA Agent — User Guide

**Version:** 1.0 | **Status:** ✅ Production Ready

## Overview
QA Engineer Agent автоматизирует тестирование, генерацию тестов, анализ качества кода.

## Features
- 🧪 Test Generation
- ✅ Test Execution
- 📊 Quality Analysis
- 🐛 Bug Detection
- 📈 Coverage Reports

## Quick Start
```python
from qa_agent import QAAgent

agent = QAAgent()

# Generate tests
tests = await agent.generate_tests(
    code="Функция ПолучитьДанные()...",
    language="bsl"
)

# Run tests
results = await agent.run_tests(test_suite="integration")

# Analyze quality
quality = await agent.analyze_quality(project_path="/path/to/1c")
```

## API
```http
POST /api/v1/qa/generate-tests
POST /api/v1/qa/run-tests
GET /api/v1/qa/quality-analysis
```

**See:** [QA Module README](../../src/modules/qa/README.md)
