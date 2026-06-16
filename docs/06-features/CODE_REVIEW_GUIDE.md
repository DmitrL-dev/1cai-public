# Code Review — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/code_review`

## Обзор
**Code Review Module** — автоматический code review с AI. Анализ изменений, рекомендации, best practices.

**Возможности:** 🔍 Change Analysis | 💡 Recommendations | ✅ Best Practices | 🎯 Auto-fix | 📊 Quality Score | ⚠️ Issue Detection

## API Reference

### Submit Code for Review
```http
POST /api/v1/code_review/submit
{
  "code": "Функция ПолучитьДанные()...",
  "language": "bsl",
  "context": {"file_path": "CommonModules/Работа.bsl"}
}

Response:
{
  "review_id": "rev_123",
  "quality_score": 85,
  "issues": [
    {
      "type": "warning",
      "line": 15,
      "message": "Используйте параметризованные запросы",
      "suggestion": "Запрос.УстановитьПараметр(...)"
    }
  ],
  "recommendations": [
    "Добавьте обработку ошибок",
    "Используйте structured logging"
  ]
}
```

### Auto-fix Issues
```http
POST /api/v1/code_review/{review_id}/autofix

Response:
{
  "fixed_code": "Функция ПолучитьДанные()...",
  "fixes_applied": 3
}
```

## Примеры

```python
# Проверка кода
review = await client.post("/api/v1/code_review/submit", json={
    "code": my_code,
    "language": "bsl"
})

if review.json()["quality_score"] < 80:
    # Применить auto-fix
    fixed = await client.post(f"/api/v1/code_review/{review.json()['review_id']}/autofix")
    print(fixed.json()["fixed_code"])
```

## Интеграция с GitHub

```python
# GitHub webhook для автоматического review PR
@app.post("/webhooks/github")
async def github_webhook(payload: dict):
    if payload["action"] == "opened":
        pr_code = get_pr_diff(payload["pull_request"])
        review = await client.post("/api/v1/code_review/submit", json={"code": pr_code})
        # Добавить комментарий в PR
        add_pr_comment(payload["pull_request"], review.json()["issues"])
```

## Best Practices
1. **Pre-commit hooks:** Запускайте review перед commit
2. **CI/CD integration:** Добавьте в pipeline
3. **Quality gates:** Блокируйте merge если score < 80

## FAQ
**Q: Какие языки поддерживаются?** A: BSL, JavaScript, Python, SQL  
**Q: Можно ли настроить правила?** A: Да, через `.codereview.yml`

---

**Документация:** [Code Review API](../api/CODE_REVIEW_API.md)
