# Code Approval — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/code_approval`

## Обзор
**Code Approval API** — автоматизация code review. Создание, управление, утверждение изменений кода.

**Возможности:** 📝 Submit for Review | 👥 Assign Reviewers | ✅ Approve/Reject | 💬 Comments | 📊 Metrics

## Quick Start
```python
# Отправить код на review
approval = await client.post("/api/v1/code_approval/submit", json={
    "code": "Функция ПолучитьДанные()...",
    "description": "Added data fetching function",
    "reviewers": ["user_123", "user_456"]
})

# Проверить статус
status = await client.get(f"/api/v1/code_approval/{approval['id']}")
print(f"Status: {status.json()['status']}")  # pending/approved/rejected

# Утвердить
await client.post(f"/api/v1/code_approval/{approval['id']}/approve", json={
    "comment": "LGTM! Good work"
})
```

## API Reference
```http
POST /api/v1/code_approval/submit
{
  "code": "...",
  "description": "Feature: User authentication",
  "reviewers": ["reviewer1", "reviewer2"],
  "priority": "high"
}

Response:
{
  "id": "approval_123",
  "status": "pending",
  "required_approvals": 2,
  "current_approvals": 0
}
```

## Workflow
1. Developer submits code
2. Auto-review checks quality
3. Assign human reviewers
4. Reviewers approve/reject
5. Merge if approved

## Integration with GitHub
```python
# Auto-create approval from PR
@app.post("/webhooks/github/pr")
async def pr_webhook(payload: dict):
    pr = payload["pull_request"]
    
    approval = await client.post("/api/v1/code_approval/submit", json={
        "code": get_pr_diff(pr),
        "description": pr["title"],
        "github_pr": pr["number"]
    })
```

## FAQ
**Q: Сколько reviewers нужно?** A: Настраивается (по умолчанию 2)  
**Q: Есть ли SLA?** A: Да, настраивается per project

---
**Документация:** [Code Approval API](../api/CODE_APPROVAL_API.md)
