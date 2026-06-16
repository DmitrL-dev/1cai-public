# AI Services Monitoring Guide

## Обзор

Система мониторинга для AI сервисов включает:
- **Prometheus метрики** для Kimi-K2-Thinking и AI Orchestrator
- **Grafana дашборды** для визуализации
- **Alert правила** для критических компонентов

## Метрики

### Kimi-K2-Thinking метрики

- `kimi_queries_total` - Общее количество запросов (labels: mode, status)
- `kimi_response_duration_seconds` - Длительность ответов (histogram, mode)
- `kimi_tokens_used_total` - Использованные токены (labels: mode, token_type)
- `kimi_reasoning_steps` - Количество шагов reasoning (histogram, mode)
- `kimi_tool_calls_total` - Вызовы инструментов (labels: mode, tool_name)

### AI Orchestrator метрики

- `orchestrator_queries_total` - Запросы к orchestrator (labels: query_type, selected_service)
- `orchestrator_fallback_total` - Fallback операции (labels: from_service, to_service, reason)
- `orchestrator_cache_hits_total` - Попадания в кеш
- `orchestrator_cache_misses_total` - Промахи кеша

### Общие AI метрики

- `ai_queries_total` - Все AI запросы (labels: agent_type, status, model)
- `ai_response_duration_seconds` - Длительность ответов (histogram)
- `ai_tokens_used_total` - Использованные токены (labels: agent_type, model, token_type)
- `ai_service_available` - Доступность сервисов (gauge, labels: service, model)
- `ai_errors_total` - Ошибки (labels: service, model, error_type)

## Grafana Дашборды

### AI Services Dashboard

**Файл**: `monitoring/grafana/dashboards/ai_services.json`

**Панели**:
1. **Kimi-K2-Thinking Queries** - График запросов по режимам и статусам
2. **Kimi Response Duration** - 50th и 95th перцентили времени ответа
3. **Kimi Tokens Used** - Использование токенов по типам
4. **Kimi Error Rate** - Процент ошибок
5. **Orchestrator Query Distribution** - Распределение запросов по сервисам
6. **Orchestrator Cache Hit Rate** - Процент попаданий в кеш
7. **Orchestrator Fallbacks** - Частота fallback операций
8. **AI Service Availability** - Статус доступности сервисов
9. **AI Errors by Type** - Ошибки по типам
10. **Kimi Reasoning Steps** - Количество шагов reasoning
11. **Kimi Tool Calls** - Вызовы инструментов

**Использование**:
1. Импортируйте дашборд в Grafana
2. Убедитесь, что Prometheus datasource настроен
3. Дашборд автоматически обновляется каждые 10 секунд

## Alert Правила

### Файл: `monitoring/prometheus/alerts/ai_alerts.yml`

### Критические алерты

1. **KimiServiceDown** - Сервис Kimi недоступен более 2 минут
2. **AIServiceUnavailable** - Любой AI сервис недоступен более 3 минут

### Warning алерты

1. **KimiHighErrorRate** - Процент ошибок > 10% в течение 5 минут
2. **KimiHighResponseTime** - 95th перцентиль > 60 секунд
3. **KimiHighTokenUsage** - Использование токенов > 10000/sec
4. **OrchestratorHighFallbackRate** - Процент fallback > 20%
5. **OrchestratorLowCacheHitRate** - Процент попаданий в кеш < 50%
6. **AIServiceHighErrorRate** - Общая частота ошибок > 10/sec
7. **AIHighResponseTime** - 95th перцентиль > 30 секунд
8. **AIHighTokenUsage** - Использование токенов > 50000/sec

## Настройка

### Prometheus

Добавьте в `prometheus.yml`:
```yaml
rule_files:
  - "alerts/ai_alerts.yml"
```

### Alertmanager

Алерты автоматически маршрутизируются по severity:
- **critical** → канал `#1c-ai-critical` + email (может дублироваться в Telegram)
- **warning** → канал `#1c-ai-warnings`

Для интеграции с Telegram предусмотрен workflow `.github/workflows/telegram-alert.yaml`
и стандартная схема Alertmanager → webhook → Telegram gateway. См. подробности в
`docs/observability/telegram_alerts.md`.

## Запросы Prometheus

### Примеры полезных запросов

```promql
# Kimi успешность запросов
rate(kimi_queries_total{status="success"}[5m]) / rate(kimi_queries_total[5m]) * 100

# Среднее время ответа Kimi
histogram_quantile(0.50, rate(kimi_response_duration_seconds_bucket[5m]))

# Токены в минуту
rate(kimi_tokens_used_total[1m]) * 60

# Cache hit rate
rate(orchestrator_cache_hits_total[5m]) / (rate(orchestrator_cache_hits_total[5m]) + rate(orchestrator_cache_misses_total[5m])) * 100

# Fallback rate
rate(orchestrator_fallback_total[5m]) / rate(orchestrator_queries_total[5m]) * 100
```

## Troubleshooting

### Метрики не появляются

1. Проверьте, что Prometheus собирает метрики с `/metrics` endpoint
2. Убедитесь, что метрики экспортируются из кода (см. `src/monitoring/prometheus_metrics.py`)
3. Проверьте логи Prometheus на ошибки

### Алерты не срабатывают

1. Проверьте синтаксис правил: `promtool check rules alerts/ai_alerts.yml`
2. Убедитесь, что метрики существуют в Prometheus
3. Проверьте конфигурацию Alertmanager

### Дашборд пустой

1. Проверьте, что Prometheus datasource настроен правильно
2. Убедитесь, что метрики собираются (проверьте в Prometheus UI)
3. Проверьте временной диапазон в Grafana

## Best Practices

1. **Мониторинг в реальном времени**: Используйте Grafana для визуализации
2. **Алерты для критических проблем**: Настройте уведомления для критических алертов
3. **Регулярный review метрик**: Анализируйте тренды и оптимизируйте пороги
4. **Документирование инцидентов**: Используйте runbooks для типичных проблем

