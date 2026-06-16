# Code Analyzers — Руководство пользователя

**Версия:** 1.0 | **Статус:** ⚠️ In Development | **API:** `/api/v1/code_analyzers` (planned)

## Обзор
**Code Analyzers** — набор анализаторов кода для различных языков. Static analysis, code quality metrics, complexity analysis.

**Возможности (planned):**
- 🔍 Static Analysis
- 📊 Quality Metrics
- 🎯 Complexity Analysis
- ⚠️ Issue Detection

## Status
⚠️ **В разработке** - базовая функциональность через Code Review API.

## Current Workaround
```python
# Используйте Code Review API для анализа
analysis = await client.post("/api/v1/code_review/submit", json={
    "code": "Функция ПолучитьДанные()...",
    "language": "bsl"
})

print(f"Quality score: {analysis.json()['quality_score']}")
print(f"Issues: {analysis.json()['issues']}")
```

## Planned Features
```python
# Dedicated analyzers (planned)
bsl_analysis = await client.post("/api/v1/code_analyzers/bsl", json={
    "code": "...",
    "rules": ["complexity", "naming", "security"]
})

js_analysis = await client.post("/api/v1/code_analyzers/javascript", json={
    "code": "...",
    "rules": ["eslint", "prettier"]
})
```

## FAQ
**Q: Когда будет готов?** A: Q2 2026  
**Q: Что использовать сейчас?** A: Code Review API

---
**Документация:** [Code Review Guide](CODE_REVIEW_GUIDE.md)
