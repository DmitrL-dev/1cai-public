# Test Generation — User Guide

**Version:** 1.0 | **Status:** ✅ Production Ready

## Overview
Test Generation автоматически генерирует unit tests, integration tests для BSL кода.

## Features
- 🧪 Unit Test Generation
- ✅ Integration Test Generation
- 📊 Coverage Analysis
- 🎯 Edge Case Detection
- 📝 Test Documentation

## Quick Start
```python
from test_generation import TestGenerator

gen = TestGenerator()

# Generate unit tests
tests = await gen.generate_unit_tests(
    code="Функция ПолучитьДанные()...",
    language="bsl"
)

# Generate integration tests
integration = await gen.generate_integration_tests(
    module="sales"
)

# Analyze coverage
coverage = await gen.analyze_coverage(project="/path/to/1c")
```

## API
```http
POST /api/v1/test-generation/unit
POST /api/v1/test-generation/integration
GET /api/v1/test-generation/coverage
```

## Examples

### Generate Unit Tests
```http
POST /api/v1/test-generation/unit
{
  "code": "Функция СуммаДокумента(Документ)\n  Возврат Документ.Сумма;\nКонецФункции",
  "language": "bsl"
}

Response:
{
  "tests": [
    {
      "name": "ТестСуммаДокумента_ПоложительноеЗначение",
      "code": "..."
    }
  ]
}
```

**See:** [QA Agent Guide](../03-ai-agents/QA_AGENT_GUIDE.md)
