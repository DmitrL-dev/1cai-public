# LLM Gateway & Offline Resiliency Guide

**Назначение:** обеспечить непрерывную работу AI-агентов при отключении интернета, блокировке отдельных LLM-провайдеров или превышении квот. Сервис `src/services/llm_gateway.py` абстрагирует работу с OpenAI/Kimi/Qwen/GigaChat и применяет политики fallback, кэширование и лимиты.

---

## 1. Сценарии для обычного пользователя

| Сценарий | Действия |
| --- | --- |
| **Переключиться на резервного провайдера** | Запустить `scripts/tests/llm_smoke.py --provider kimi` или вызвать API `/api/assistants` с заголовком `X-LLM-Provider`. Gateway автоматически переключит все запросы. |
| **Работа полностью офлайн** | Скопировать файлы моделей в локальное окружение (например, Ollama), задать `LLM_GATEWAY_MODE=offline`, применить `config/llm_gateway_simulation.yaml`, выполнить `scripts/tests/run_offline_dry_run.py`. |
| **Диагностика проблем** | Выполнить `scripts/tests/llm_smoke.py --full`, проверить метрики `http://localhost:9090/metrics` (раздел `llm_gateway_*`), открыть Grafana дашборд `AI Services`. |

Подробные подсказки выводятся в CLI-скрипте и в отчёте `output/llm_smoke_report.json`.

---

## 2. Конфигурация (тех. специалист)

1. **Основной конфиг** — `config/llm_gateway_simulation.yaml`:
   - `providers`: список доступных LLM (openai, kimi, qwen, gigachat).
   - `fallback_policy`: порядок переключения и таймауты.
   - `offline_packages`: заранее подготовленные ответы/эмбеддинги для офлайн-режима.

2. **Секреты** — задаются через ENV (`KIMI_API_KEY`, `OPENAI_API_KEY`, `QWEN_API_KEY`, `GIGACHAT_AUTH_TOKEN`). В офлайне можно оставить пустыми.

3. **Мониторинг**:
   - Prometheus экспонирует `llm_gateway_requests_total`, `llm_gateway_fallbacks_total`, `llm_gateway_offline_hits_total`.
   - Grafana JSON: `monitoring/grafana/dashboards/ai_services.json`.
   - Alertmanager правила: `monitoring/prometheus/alerts/ai_alerts.yml`.

4. **Тесты и хаос**:
   - `tests/integration/test_llm_gateway_simulation.py` — проверка fallback и деградации.
   - `tests/integration/test_llm_failover.py` — офлайн-режим.
   - `scripts/chaos/block_jira.sh`/`kill_ws_node.sh` — имитация сетевых проблем.

---

## 3. Процедуры восстановления

1. **Блокировка внешнего провайдера**  
   - Запустить `scripts/tests/run_offline_dry_run.py`.  
   - Убедиться, что `llm_gateway_offline_hits_total` > 0 и нет 5xx в `/metrics`.  
   - После возвращения связи выполнить `scripts/tests/llm_smoke.py --provider <основной>` и переключить `LLM_GATEWAY_MODE=auto`.

2. **Полное отключение интернета**  
   - Перейти в режим `offline` (env + конфиг).  
   - Использовать `analysis/llm_blocking_resilience_plan.md` как чек-лист (сбор логов, уведомления, отчёт `docs/templates/offline_incident_report.md`).  
   - После восстановления проверить синхронизацию знаний через `scripts/knowledge/build_vector_store.py`.

3. **Расхождение конфигураций**  
   - Сравнить `config/llm_providers.yaml` с фактическими секретами.  
   - Обновить значения через Vault/Kubernetes Secret.  

---

## 4. API и интеграция

- Gateway подключается внутри `src/ai/orchestrator.py` и `src/ai/agents/*`.  
- Для ручного использования есть MCP-инструмент `LLMProviderTool` (см. `docs/06-features/MCP_SERVER_GUIDE.md`).  
- REST-пример:

```bash
curl -X POST http://localhost:6001/api/assistants/generate \
     -H "X-LLM-Provider: kimi" \
     -H "Content-Type: application/json" \
     -d '{"prompt":"Сделай SQL-фильтр по продажам"}'
```

Gateway вернёт фактического провайдера, использованного для ответа (`X-LLM-Actual-Provider`).

---

## 5. Ответственность команд

| Роль | Зона ответственности |
| --- | --- |
| Product / BA | Решение, когда переходить в офлайн, какие знания подготовить заранее. |
| DevOps | Настройка конфигов, секретов, мониторинга и алертов. |
| AI Team | Обновление fallback-политик, поддержка моделей и smoke-тестов. |

---

**См. также:**  
- `analysis/llm_blocking_resilience_plan.md` — регламент.  
- `docs/templates/offline_incident_report.md` — шаблон отчёта.  
- `scripts/tests/llm_smoke.py --help` — описание CLI.

