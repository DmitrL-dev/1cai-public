# ⚙️ AI Performance & Observability Guide

**Фокус:** Orchestrator + Kimi-K2-Thinking + Qwen Coder + GigaChat + YandexGPT + 1C:Напарник  
**Цель:** понимать, как мерить производительность и где смотреть, если «AI медленный».

---

## 1. Какие метрики уже есть

Реализация в `src/monitoring/prometheus_metrics.py`, обзор — в `monitoring/AI_SERVICES_MONITORING.md`.

- **Orchestrator**
  - `orchestrator_queries_total{query_type,selected_service}`
  - `orchestrator_cache_hits_total`, `orchestrator_cache_misses_total`
  - `orchestrator_fallback_total{from_service,to_service,reason}`
- **Scenario Hub / Scenario API**
  - `scenario_requests_total{endpoint,autonomy_provided}`
- **Kimi‑K2‑Thinking**
  - `kimi_queries_total{mode,status}`
  - `kimi_response_duration_seconds_bucket{mode}` (гистограмма)
  - `kimi_tokens_used_total{mode,token_type}`
- **LLM Provider Abstraction**
  - `llm_provider_selections_total{provider_id,query_type,reason}` - количество выборов провайдера
  - `llm_provider_selection_duration_seconds{provider_id}` - время выбора провайдера
  - `llm_provider_cost_estimate{provider_id}` - оценка стоимости запроса
- **GigaChat / YandexGPT**
  - Метрики интегрированы через общие AI метрики (`ai_queries_total`, `ai_response_duration_seconds_bucket`)
  - Автоматический выбор провайдера через LLM Provider Abstraction для русскоязычных запросов
- **1C:Напарник**
  - Метрики интегрированы через общие AI метрики
  - Автоматический выбор для 1C-специфичных запросов через LLM Provider Abstraction
  - Бесплатный провайдер для пользователей 1С
- **Общие AI метрики**
  - `ai_queries_total{agent_type,status,model}`
  - `ai_response_duration_seconds_bucket{agent_type,model}`
  - `ai_errors_total{service,model,error_type}`

Эти метрики уже используются в Grafana‑дашборде `monitoring/grafana/dashboards/ai_services.json`.

---

## 2. Минимальные synthetic‑тесты производительности

Для локальной проверки базовой работы кеша и оркестратора:

```bash
python -m pytest tests/unit/test_ai_orchestrator_basic.py -q
```

Тест `test_process_query_uses_cache_on_second_call`:

- вызывает `AIOrchestrator.process_query` дважды с одинаковыми аргументами;
- проверяет, что:
  - ответ берётся из `orchestrator.cache`,
  - счётчик `orchestrator_cache_hits_total` увеличился.

Тест `test_process_query_unknown_uses_multi_service_stub` дополнительно проверяет увеличение `orchestrator_cache_misses_total`.

Для более тяжёлого synthetic‑нагруза предусмотрен набор тестов `tests/performance/test_load_performance.py`
(RoleBasedRouter, MultiLayerCache, PostgreSQL), которые можно запускать точечно:

```bash
python -m pytest tests/performance/test_load_performance.py::test_api_latency_benchmark -q
python -m pytest tests/performance/test_load_performance.py::test_concurrent_requests -q
```

Эти тесты предполагают поднятые локальные зависимости (PostgreSQL и сервисы),
поэтому их рекомендуется использовать как периодический benchmark, а не как часть быстрого feedback‑цикла.

---

## 3. Kimi-K2-Thinking benchmark script

Для точечного замера латентности Kimi используется скрипт `scripts/testing/kimi_benchmark.py`:

```bash
python scripts/testing/kimi_benchmark.py --requests 10 --concurrency 2
```

Он:

- использует тот же `KimiClient/KimiConfig`, что и оркестратор;
- выполняет N запросов с заданной конкуррентностью;
- печатает min/avg/p50/p95/max latency и распределение ошибок.

Если `KIMI_API_KEY` / `KIMI_OLLAMA_URL` не заданы, скрипт аккуратно сообщает, что бенчмарк пропущен.

---

## 3.1. GigaChat и YandexGPT интеграция

Платформа автоматически интегрирует российские LLM провайдеры (GigaChat и YandexGPT) для обработки русскоязычных запросов через **LLM Provider Abstraction**.

### Автоматический выбор провайдера

Orchestrator автоматически определяет язык запроса и выбирает подходящий провайдер:

```python
# Пример: русскоязычный запрос автоматически направляется в GigaChat/YandexGPT
query = "Объясни, как работает механизм проведения документов в 1С"
response = await orchestrator.process_query(query)
# → автоматически выбран GigaChat или YandexGPT через LLM Provider Abstraction
```

### Конфигурация

**GigaChat:**
```bash
# Вариант 1: Access Token (прямой доступ)
export GIGACHAT_ACCESS_TOKEN="your-token"

# Вариант 2: Client Credentials (OAuth 2.0)
export GIGACHAT_CLIENT_ID="your-client-id"
export GIGACHAT_CLIENT_SECRET="your-client-secret"
export GIGACHAT_TOKEN_URL="https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
```

**YandexGPT:**
```bash
export YANDEXGPT_API_KEY="your-api-key"
export YANDEXGPT_FOLDER_ID="your-folder-id"
export YANDEXGPT_MODEL="yandexgpt/latest"  # опционально
```

### Compliance и выбор провайдера

LLM Provider Abstraction учитывает требования compliance:

```python
# Запрос с требованием 152-ФЗ автоматически выберет российский провайдер
context = {"compliance": ["152-ФЗ"]}
response = await orchestrator.process_query("Запрос на русском", context)
# → автоматически выбран GigaChat или YandexGPT
```

### Проверка интеграции

Для проверки работы интеграции запустите E2E тесты:

```bash
python -m pytest tests/system/test_e2e_llm_provider_abstraction.py::test_e2e_gigachat_integration_with_orchestrator -v
python -m pytest tests/system/test_e2e_llm_provider_abstraction.py::test_e2e_yandexgpt_integration_with_orchestrator -v
python -m pytest tests/system/test_e2e_llm_provider_abstraction.py::test_e2e_russian_text_query_provider_selection -v
```

### Производительность

- **GigaChat**: средняя latency ~1800ms, поддержка streaming, compliance: 152-ФЗ, GDPR
- **YandexGPT**: средняя latency ~1600ms, поддержка streaming, compliance: 152-ФЗ, GDPR
- Автоматический fallback между российскими провайдерами при недоступности одного из них

### 1C:Напарник интеграция

**1C:Напарник** - специализированный AI-помощник для разработчиков 1С:Enterprise, интегрированный в платформу через LLM Provider Abstraction.

#### Автоматический выбор провайдера

Orchestrator автоматически выбирает 1C:Напарник для 1C-специфичных запросов:

```python
# Пример: запрос о конфигурации 1С автоматически направляется в 1C:Напарник
query = "Как работает механизм проведения документов в типовой конфигурации УТ 11"
response = await orchestrator.process_query(query)
# → автоматически выбран 1C:Напарник через LLM Provider Abstraction
```

#### Конфигурация

```bash
export NAPARNIK_API_KEY="your-api-key"
export NAPARNIK_MODEL="naparnik-pro"  # опционально, по умолчанию naparnik-pro
export NAPARNIK_API_URL="https://naparnik.platform.1c.ru/api/v1"  # опционально
```

#### Особенности

- **Бесплатный**: стоимость 0.0 за 1k токенов для пользователей 1С
- **Специализация**: оптимизирован для работы с конфигурациями и метаданными 1С:Enterprise
- **Compliance**: поддерживает 152-ФЗ и GDPR
- **Производительность**: средняя latency ~2000ms

#### Проверка интеграции

Для проверки работы интеграции запустите E2E тесты:

```bash
python -m pytest tests/system/test_e2e_llm_provider_abstraction.py::test_e2e_naparnik_integration_with_orchestrator -v
python -m pytest tests/system/test_e2e_llm_provider_abstraction.py::test_e2e_naparnik_in_llm_provider_abstraction -v
python -m pytest tests/unit/test_naparnik_client.py -v
```

---

## 4. Orchestrator latency smoke-тест (offline)

Для быстрой проверки латентности Orchestrator в offline‑режиме (без Kimi/Qwen) есть скрипт `scripts/testing/orchestrator_latency_smoke.py`:

```bash
python scripts/testing/orchestrator_latency_smoke.py --requests 10
```

Он:

- несколько раз вызывает `AIOrchestrator.process_query` с отключёнными внешними клиентами,
- выводит время обработки каждого запроса и среднее значение.

Скрипт не делает жёстких assert'ов, а служит как быстрая ручная проверка и источник чисел для сравнения между ветками/коммитами.

---

## 5. Как смотреть latency и cache hit rate в Prometheus

Примеры промкьюэл‑запросов (также приведены в `monitoring/AI_SERVICES_MONITORING.md`):

```promql
# Cache hit rate оркестратора
rate(orchestrator_cache_hits_total[5m])
/
(rate(orchestrator_cache_hits_total[5m]) + rate(orchestrator_cache_misses_total[5m]))
* 100

# Среднее время ответа Kimi (p50)
histogram_quantile(
  0.50,
  rate(kimi_response_duration_seconds_bucket[5m])
)

# Среднее время ответа AI агентов (p95)
histogram_quantile(
  0.95,
  rate(ai_response_duration_seconds_bucket[5m])
)

# Частота использования Scenario Hub c разбивкой по уровню автономии
sum(rate(scenario_requests_total[5m])) by (endpoint, autonomy_provided)

# Выборы LLM провайдера по типу запроса
sum(rate(llm_provider_selections_total[5m])) by (provider_id, query_type)

# Средняя стоимость запросов по провайдерам
avg(llm_provider_cost_estimate) by (provider_id)
```

Рекомендуемые целевые ориентиры:

- cache hit rate оркестратора: **≥ 60–70%** для повторяющихся запросов;
- p95 latency для Kimi/Qwen: в пределах **≤ 60s** под нагрузкой (см. alert‑правила);
- p95 latency для GigaChat/YandexGPT: в пределах **≤ 5s** для русскоязычных запросов;
- LLM provider selection latency: **< 1ms** (выбор провайдера не должен влиять на общую latency).

---

## 6. Быстрая диагностика «AI тормозит»

1. **Проверить `/metrics`**  
   Убедиться, что endpoint жив и метрики отдаются (см. `metrics_endpoint` в `prometheus_metrics.py`).

2. **Открыть Grafana AI Services Dashboard**  
   - панели `Kimi Response Duration`, `AIHighResponseTime`, `Orchestrator Fallbacks`.

3. **Смотреть на:**
   - всплески `kimi_response_duration_seconds` или `ai_response_duration_seconds`,
   - рост `orchestrator_fallback_total` (переходы Kimi→Qwen и т.п.),
   - падение cache hit rate.

4. **Локально прогнать smoke‑тесты:**

```bash
python -m pytest tests/system/test_e2e_ba_dev_qa.py tests/system/test_e2e_flows.py -q
```

Если e2e проходят нормально, а latency высока только в прод‑кластерe — проблема, скорее всего, в окружении/сетях, а не в коде агентов.

---

## 7. Что наращивать дальше

- Добавить k6/Locust‑сценарии для Orchestrator (нагрузка на `/api/ai/query` с разными типами запросов).  
- Ввести перцентильные SLO для AI ответов (например, `p95 <= 60s` для Kimi и `p95 <= 15s` для Qwen) и подключить к существующей системе SLO/Alertmanager.


