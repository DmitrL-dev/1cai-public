# Security Agent Framework

Внутренний фреймворк для автоматизированного security‑тестирования без внешних зависимостей.

## Структура

```
agent_framework/
├── ARCHITECTURE.md
├── README.md
├── requirements.txt
├── cli/
├── runtime/
├── sandbox/
├── prompts/
└── tests/
```

## Быстрый старт (MVP)

1. Установить зависимости:
   ```bash
   pip install -r security/agent_framework/requirements.txt
   ```
2. Запустить sandbox manager (заглушка):
   ```bash
   python -m security.agent_framework.sandbox.manager
   ```
3. Запустить локальную проверку (без sandbox):
   ```bash
   python -m security.agent_framework.cli run -t http://localhost --local --markdown reports/web-api.md
   python -m security.agent_framework.cli run -t ./my-repo --profile repo-static --local --format json --output reports/repo.json
   ```

По умолчанию CLI обращается к менеджеру песочниц по `http://localhost:9100`. Можно переопределить URL параметром `--manager-url`. Режим `--local` обходит менеджер и сразу запускает агентов (удобно для CI/n8n). Параметр `--submit` позволяет после локального запуска сохранить отчёт в менеджере (он попадёт в `runs/<run_id>.json`).

### Профили и модули (MVP)
- `web-api`: reachability, телеметрия, базовые security-заголовки.
- `repo-static`: поиск чувствительных файлов и потенциальных секретов.
- `n8n-workflow`: статический анализ экспортированного workflow (HTTP, сертификаты, auth).
- `bsl-1c`: простые эвристики по BSL (dangerous Выполнить(), хардкод паролей, отладочные вызовы).

Дополнительные примеры CI/n8n смотрите в `docs/CI_n8n.md`.

### Exit codes
| Код | Значение |
|-----|----------|
| 0   | Найдены только low или нет находок |
| 1   | Есть medium |
| 2   | Есть high |
| 3   | Есть critical |

### Артефакты
- `--output path.json` — сохраняет структуру результатов (для CI, Neo4j, аналитики).
- `--markdown path.md` — формирует компактное резюме в Markdown (подходит для knowledge base, отчётов, нотификаций).
- `--html path.html` — HTML-отчёт для порталов/дашбордов.
- `--submit` — отправляет JSON обратно в менеджер песочниц (хранится в `sandbox/runs/<run_id>.json` и доступен по REST `/runs/{id}/results`).
- `--knowledge-base path.jsonl` — аппендит JSON-строку в локальную базу знаний (удобно для RAG).
- `--neo4j-*` — синхронизирует найденные уязвимости в Neo4j (создаются узлы `SecurityRun`, `SecurityFinding`, `SecurityTarget`).
- `--publish-dir dir` — копирует HTML/Markdown-отчёт в каталог портала/статического хостинга и обновляет `index.html` с историей запусков.
- `--publish-url-base url` — базовый URL для опубликованных отчётов (используется в Slack-сводке).
- `--slack-webhook url` — отправляет краткое уведомление в Slack.
- `--tickets-dir dir` — создаёт JSON-файлы с задачами по критическим/высоким находкам (можно импортировать в Jira/YouTrack).
- `--ticket-prefix` — префикс в заголовках тикетов, например `SEC`.
- `--ticket-webhook url` — отправляет сформированные тикеты на внешний сервис (REST webhook).
- `--s3-*` — выгрузка отчётов в S3/MinIO (`bucket`, `prefix`, `region`, `endpoint`, `access_key`, `secret_key`).
- `--confluence-*` — публикация HTML в Confluence (`url`, `user`, `token`, `space`, `parent`).
- Портал (`publish_dir`) также создаёт `neo4j_dashboard.cypher` с базовыми запросами.
- Подробности и примеры конфигов: см. `docs/configuration.md` и `examples/basic_web_scan.yaml`.

### Preset команды
- `python -m security.agent_framework.cli preset --list` — показать список.
- `python -m security.agent_framework.cli preset web-api` — скопировать дефолтный конфиг.
- `python -m security.agent_framework.cli preset bsl-1c --show` — вывести содержимое.
- Пресеты находятся в `security/agent_framework/presets/` и поддерживают запуск через `--config`.

## План задач
- Детализировать протокол CLI ↔ sandbox (отчёты, стрим логов).
- Расширить профили (`n8n-workflow`, `bsl-1c`).
- Автоматизировать выгрузку отчётов в knowledge base / Neo4j.

