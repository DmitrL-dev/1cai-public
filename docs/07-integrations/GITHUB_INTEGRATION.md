# GitHub Integration — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/github`

## Обзор
**GitHub Integration** — интеграция с GitHub. Webhooks, PR analysis, issue management, CI/CD integration.

**Возможности:** 🔗 Webhooks | 🔍 PR Analysis | 📝 Issue Management | 🚀 CI/CD Integration | 📊 Analytics | 🤖 Auto-review

## Quick Start

```python
# Подключить GitHub репозиторий
await client.post("/api/v1/github/repos", json={
    "owner": "mycompany",
    "repo": "1c-project",
    "access_token": "ghp_..."
})

# Настроить webhook
await client.post("/api/v1/github/webhooks", json={
    "repo": "mycompany/1c-project",
    "events": ["pull_request", "push", "issues"]
})
```

## Webhooks

```python
# Обработка PR webhook
@app.post("/webhooks/github")
async def github_webhook(payload: dict):
    if payload["action"] == "opened":
        pr = payload["pull_request"]
        
        # Автоматический code review
        diff = get_pr_diff(pr)
        review = await client.post("/api/v1/code_review/submit", json={"code": diff})
        
        # Добавить комментарий в PR
        await github.add_pr_comment(pr["number"], review.json()["issues"])
```

## PR Analysis

```http
POST /api/v1/github/pr/analyze
{
  "owner": "mycompany",
  "repo": "1c-project",
  "pr_number": 123
}

Response:
{
  "quality_score": 85,
  "files_changed": 5,
  "lines_added": 234,
  "lines_removed": 45,
  "issues": [...],
  "recommendations": [...]
}
```

## Auto-review

```yaml
# .github/workflows/auto-review.yml
name: Auto Review
on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run 1C AI Stack Review
        run: |
          curl -X POST http://1c-ai-stack:8000/api/v1/github/pr/analyze \
            -H "Authorization: Bearer ${{ secrets.AI_STACK_TOKEN }}" \
            -d '{"owner":"${{github.repository_owner}}","repo":"${{github.event.repository.name}}","pr_number":${{github.event.number}}}'
```

## Issue Management

```python
# Создать issue из bug report
await client.post("/api/v1/github/issues", json={
    "repo": "mycompany/1c-project",
    "title": "Bug: Login fails",
    "body": "Steps to reproduce...",
    "labels": ["bug", "high-priority"]
})

# Автоматическая категоризация issues
issues = await github.get_issues("mycompany/1c-project")
for issue in issues:
    category = await ai.categorize(issue["title"] + issue["body"])
    await github.add_label(issue["number"], category)
```

## FAQ
**Q: Поддерживается ли GitHub Enterprise?** A: Да  
**Q: Можно ли интегрировать с GitLab?** A: Да, см. [GitLab Integration](GITLAB_INTEGRATION.md)

---

**Документация:** [GitHub Integration API](../07-integrations/GITHUB_INTEGRATION.md)
