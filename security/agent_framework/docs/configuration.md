# Конфигурация CLI и интеграции

## Форматы конфигурационных файлов

CLI поддерживает загрузку настроек из YAML/JSON:

```yaml
# scan.yaml
targets:
  - http://localhost:8080/health
profile: web-api
local: true
format: json
output: reports/web.json
markdown: reports/web.md
html: reports/web.html
knowledge_base: reports/security-findings.jsonl
neo4j_url: http://localhost:7474
neo4j_user: neo4j
neo4j_password: secret
neo4j_database: neo4j
```

Запуск:

```bash
python -m security.agent_framework.cli run --config scan.yaml
```

CLI всё равно ожидает команду (`run`) в аргументах, но остальные параметры подхватываются из файла. Важно: `--config` нужно указывать **до** имени команды (`security-cli --config scan.yaml run`). Любые ключи, переданные через CLI, имеют приоритет над конфигом.

### Поддерживаемые поля

| Поле             | Назначение                                            |
|------------------|-------------------------------------------------------|
| `targets`        | Список URL/путей для сканирования                     |
| `profile`        | `web-api`, `repo-static`, `n8n-workflow`, `bsl-1c`    |
| `local`          | `true` для локального запуска без sandbox manager     |
| `format`         | `human` или `json`                                    |
| `output`         | Путь к JSON-отчёту                                    |
| `markdown`       | Путь к Markdown‑резюме                                |
| `html`           | Путь к HTML-отчёту                                    |
| `knowledge_base` | JSONL файл для накопления артефактов                  |
| `neo4j_*`        | Реквизиты подключения к Neo4j                         |
| `publish_dir`    | Каталог для публикации HTML/Markdown отчетов          |
| `publish_url_base`| Базовый URL, соответствующий publish_dir             |
| `slack_webhook`  | Webhook URL для отправки уведомления в Slack          |
| `tickets_dir`    | Каталог, куда складываются JSON файлы с тикетами     |
| `ticket_prefix`  | Префикс для заголовков тикетов (например, `SEC`)     |

## Интеграция с knowledge base

- Флаг `--knowledge-base path.jsonl` добавляет строку в JSONL файл (каждый запуск — одна запись).  
- Можно использовать в дальнейшем для RAG или аналитики (Parquet/BigQuery).
- Файл создаётся автоматически, каталоги — тоже.

Пример чтения:

```python
import json

with open("reports/security-findings.jsonl", encoding="utf-8") as fh:
    records = [json.loads(line) for line in fh]
```

## Интеграция с Neo4j

- Флаги `--neo4j-url`, `--neo4j-user`, `--neo4j-password`, `--neo4j-database` включают выгрузку в Neo4j REST (`/db/<db>/tx/commit`).  
- Создаются узлы:
  - `SecurityRun` — информация о прогоне;
  - `SecurityTarget` — сервисы/репозитории;
  - `SecurityFinding` — найденные проблемы.
- Связи: `SecurityRun` → `TARGETS` → `SecurityTarget`, `SecurityRun` → `HAS_FINDING` → `SecurityFinding`, `SecurityFinding` → `FOR_TARGET` → `SecurityTarget`.

### Подготовка Neo4j

```cypher
CREATE CONSTRAINT security_run_id IF NOT EXISTS
FOR (run:SecurityRun) REQUIRE run.run_id IS UNIQUE;

CREATE CONSTRAINT security_finding_id IF NOT EXISTS
FOR (f:SecurityFinding) REQUIRE f.finding_id IS UNIQUE;
```

## Примеры пайплайнов

- GitHub Actions: см. `docs/CI_n8n.md` — шаги с `--config`, `--submit`, `--knowledge-base`, `--publish-dir`, `--slack-webhook`.  
- n8n: узел `Execute Command` + последующая обработка JSON/Markdown и отправка в Slack/портал.

## Портал отчетов

При указании `publish_dir` CLI:
- сохраняет HTML/Markdown в `<publish_dir>/<run_id>.html/.md`; 
- обновляет `index.json` и `index.html` с историей запусков и сводкой по severity;
- добавляет ссылку на HTML в Slack-уведомлении (если задан `publish_url_base`).
- формирует `neo4j_dashboard.cypher` с базовыми запросами для графовой визуализации.

Можно раздавать каталог веб-сервером или публиковать статически (S3/MinIO/Netlify и т.д.).

## Публикация в S3/MinIO

- `--s3-bucket` — целевой бакет (обязательно)
- `--s3-prefix` — каталог внутри бакета
- `--s3-region`, `--s3-endpoint`, `--s3-access-key`, `--s3-secret-key` — для MinIO/self-hosted.

Требуется `boto3`. После загрузки можно использовать `publish_url_base`, чтобы Slack и портал вели на S3.

## Публикация в Confluence

Параметры: `--confluence-url`, `--confluence-user`, `--confluence-token`, `--confluence-space` и опционально `--confluence-parent`. CLI создаёт страницу `Security Report <run_id>` и возвращает ссылку, добавляемую в Slack.

## Webhook для тикетов

Вместе с `--tickets-dir` можно указать `--ticket-webhook` и `--ticket-prefix`. Формируются JSON-файлы и параллельно отсылаются данные на внешний сервис (Jira/YouTrack интегратор, собственный бот и т.д.).

## Файлы примеров

В каталоге `examples/` доступен базовый конфиг `basic_web_scan.yaml`, который можно адаптировать под нужды команды.

## Preset команды

Доступны готовые пресеты (`security-cli preset --list`). Например:

```bash
# скопировать пресет web-api в текущую папку
python -m security.agent_framework.cli preset web-api

# скопировать в custom путь
python -m security.agent_framework.cli preset repo-static --output ci/security-repo.yaml

# посмотреть содержимое
python -m security.agent_framework.cli preset bsl-1c --show
```

Это позволяет быстро разворачивать стандартные сценарии для CI/n8n.
