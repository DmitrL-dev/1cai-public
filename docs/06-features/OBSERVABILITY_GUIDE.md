# Observability & Monitoring Guide

Описывает, как запустить Prometheus/Grafana/Alertmanager для 1C AI Stack, где смотреть метрики и что делать при инцидентах.

---

## 1. Быстрый старт для пользователя

| Задача | Команда |
| --- | --- |
| Запустить мониторинг локально | `make monitoring-up` или `docker-compose -f monitoring/docker-compose.yml up -d` |
| Открыть Grafana | `http://localhost:3000` (логин/пароль по умолчанию `admin/admin`) |
| Посмотреть статус сервисов | Dashboard “AI Services” → панели Kimi, Orchestrator, Marketplace |
| Проверить Prometheus | `http://localhost:9090/targets` |
| Получить алерты | Alertmanager `http://localhost:9093`, или Slack/Telegram (если настроено) |

---

## 2. Что мониторим

- **API и ассистенты**: latency, ошибка, rate limiting (`prometheus_metrics.py`).
- **LLM Gateway**: `llm_gateway_requests_total`, fallbacks, офлайн-режим (`monitoring/grafana/dashboards/ai_services.json`).
- **Marketplace**: `marketplace_upload_duration_seconds`, жалобы.
- **Graph/Hybrid Search**: `graph_query_duration_seconds`, `hybrid_search_fallback_total`.
- **BA Sessions**: отдельные панели в `monitoring/grafana/dashboards/ba_sessions.json`.

---

## 3. Настройка (DevOps)

1. **Prometheus** — конфигурация в `monitoring/prometheus/prometheus.yml`, правила алертов в `monitoring/prometheus/alerts/*.yml`.
2. **Grafana** — json-дэшборды в `monitoring/grafana/dashboards/`.
3. **Alertmanager** — см. `monitoring/prometheus/alerts/ai_alerts.yml`, настраивается через env `ALERT_WEBHOOK_URL`.
4. **OpenTelemetry** — опционально включите `src/monitoring/opentelemetry_setup.py`, задав `OTEL_EXPORTER_OTLP_ENDPOINT`.

---

## 4. Процедуры

| Ситуация | Действия |
| --- | --- |
| Высокий error rate на Kimi | Проверить `llm_gateway_fallbacks_total`, переключить провайдера (`LLM_GATEWAY_MODE`). |
| Задержки Graph API | Убедиться, что Neo4j/Qdrant живы (`/health`), посмотреть `graph_query_duration_seconds`. |
| Нет метрик из сервиса | Проверить, зарегистрирован ли `PrometheusMiddleware` в `src/main.py`, открыть `/metrics`. |
| Не приходят алерты | Проверить `alertmanager` логи, токены для Slack/Telegram. |

---

## 5. Файлы и ссылки

- `monitoring/AI_SERVICES_MONITORING.md` — описание дэшбордов.
- `docs/runbooks/dr_rehearsal_plan.md`, `docs/runbooks/alert_slo_runbook.md` — runbooks.
- `docs/templates/offline_incident_report.md` — форма отчёта.
- `scripts/monitoring/github_monitor.py` — автоматический снимок зависимостей.

---

## 6. Проверка

```bash
make monitoring-up
sleep 10
curl http://localhost:9090/metrics | grep llm_gateway
```

Если метрики появились, значит экспорт корректен. Далее проверьте Grafana и Alertmanager.

