# CI и n8n интеграция (черновик)

## GitHub Actions (пример)

```yaml
name: security-scan

on:
  pull_request:
    paths:
      - "src/**"
      - "security/agent_framework/**"

jobs:
  local-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r security/agent_framework/requirements.txt
      - name: Run security agent (repo-static)
        run: |
          python -m security.agent_framework.cli run \
            --local \
            --submit \
            --profile repo-static \
            --output reports/security.json \
            --markdown reports/security.md \
            --html reports/security.html \
            --publish-dir portal/security \
            --slack-webhook ${{ secrets.SECURITY_SLACK_WEBHOOK }} \
            --publish-url-base https://security.example.com/portal \
            --s3-bucket security-artifacts \
            --s3-prefix nightly \
            --confluence-url https://confluence.example.com \
            --confluence-user ${{ secrets.CONFLUENCE_USER }} \
            --confluence-token ${{ secrets.CONFLUENCE_TOKEN }} \
            --confluence-space SEC \
            --tickets-dir reports/tickets \
            --ticket-prefix SEC \
            --ticket-webhook ${{ secrets.SECURITY_TICKET_WEBHOOK }} \
            -t .
      - name: Upload report artifact
        uses: actions/upload-artifact@v4
        with:
          name: security-report
          path: |
            reports/security.json
            reports/security.md
            reports/security.html
      - name: Fail on high severity
        run: |
          python - <<'PY'
          import json, sys
          data = json.load(open("reports/security.json", encoding="utf-8"))
          levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
          worst = max((levels.get(f["severity"].lower(), 0) for r in data["results"] for f in r["findings"]), default=0)
          if worst >= 3:
              sys.exit("High severity issue detected")
          PY
```

## n8n (workflow-идея)

1. Узел `Execute Command`: запускает PowerShell / Bash с локальным агентом.

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -m security.agent_framework.cli run `
  --local `
  --submit `
  --profile web-api `
  --format json `
  --output "$env:TEMP\security-report.json" `
  --markdown "$env:TEMP\security-report.md" `
  --html "$env:TEMP\security-report.html" `
  --publish-dir "C:\Portal\Security" `
  --slack-webhook $env:SECURITY_SLACK `
  --tickets-dir "$env:TEMP\security-tickets" `
  -t "https://staging.api.local/health"
Get-Content "$env:TEMP\security-report.json"
Get-Content "$env:TEMP\security-report.md"
Get-Content "$env:TEMP\security-report.html"
```

2. Узел `Function`: парсит JSON, формирует резюме (severity, список находок).
3. Узел `If`: проверяет `maxSeverity >= 3`. При критических находках → `Telegram`/`Email`.
4. Узел `HTTP Request`: (опционально) загружает отчёт в API knowledge base.

## Следующие шаги
- Автоматизировать загрузку Markdown/JSON отчётов в knowledge base / Neo4j.
- Подготовить готовые шаблоны workflow для `repo-static` и `web-api` профилей.
- Интегрировать публикацию отчётов (HTML/Markdown) в портал разработчиков или рассылку.

