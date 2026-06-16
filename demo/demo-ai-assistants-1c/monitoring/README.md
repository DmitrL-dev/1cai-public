# 🚀 Система мониторинга и логирования Demo AI Assistants

Комплексная система мониторинга, логирования и отслеживания для Demo AI Assistants проекта.

## 📊 Компоненты системы

### 🔍 Prometheus Stack
- **Prometheus**: Сбор метрик от всех сервисов
- **AlertManager**: Управление алертами и уведомлениями
- **Node Exporter**: Системные метрики хоста
- **Blackbox Exporter**: Health checks сервисов

### 📈 Grafana Dashboards
- **Overview Dashboard**: Общий мониторинг системы
- **API Gateway Metrics**: Детальная аналитика API
- **Database Metrics**: Мониторинг PostgreSQL
- **System Metrics**: Производительность и ресурсы

### 📋 ELK Stack для логирования
- **Elasticsearch**: Поиск и анализ логов
- **Logstash**: Обработка и трансформация логов
- **Kibana**: Визуализация и анализ логов
- **Filebeat**: Сбор логов контейнеров

### 🔄 Distributed Tracing
- **Jaeger**: Распределённое отслеживание
- **OpenTelemetry**: Стандарт для observability
- **Correlation IDs**: Отслеживание запросов

### 📡 Health Checks
- **Liveness Probes**: Проверка основной функциональности
- **Readiness Probes**: Готовность к приёму трафика
- **Startup Probes**: Проверка запуска приложения
- **Custom Health Endpoints**: Детальная проверка зависимостей

## 🚀 Быстрый старт

### 1. Запуск всей системы мониторинга

```bash
cd monitoring
docker-compose up -d
```

### 2. Проверка статус сервисов

```bash
# Проверка статуса всех контейнеров
docker-compose ps

# Просмотр логов
docker-compose logs -f prometheus
docker-compose logs -f grafana
docker-compose logs -f elasticsearch
```

### 3. Доступ к веб-интерфейсам

| Сервис | URL | Логин | Пароль |
|--------|-----|-------|--------|
| Grafana | http://localhost:3000 | admin | admin123 |
| Prometheus | http://localhost:9090 | - | - |
| AlertManager | http://localhost:9093 | - | - |
| Kibana | http://localhost:5601 | - | - |
| Jaeger | http://localhost:16686 | - | - |

## 📁 Структура проекта

```
monitoring/
├── prometheus/                 # Prometheus конфигурация
│   ├── prometheus.yml         # Основной конфиг
│   ├── alert_rules.yml        # Правила алертов
│   └── node_exporter.yml      # Node Exporter настройки
├── grafana/                   # Grafana конфигурация
│   ├── dashboards/            # Дашборды
│   │   ├── overview-dashboard.json
│   │   ├── api-gateway-dashboard.json
│   │   └── database-dashboard.json
│   └── provisioning/          # Автоматическая настройка
│       ├── dashboards/
│       └── datasources/
├── alertmanager/              # AlertManager конфигурация
│   ├── alertmanager.yml       # Маршрутизация алертов
│   └── templates/             # Шаблоны уведомлений
├── elk/                       # ELK Stack
│   ├── docker-compose.yml     # ELK стек
│   ├── logstash/
│   │   ├── pipeline/          # Logstash pipeline
│   │   └── config/
│   ├── filebeat/              # Filebeat конфигурация
│   └── kibana/                # Kibana настройки
├── fluentd/                   # Fluentd агрегация
│   └── fluent.conf            # Fluentd конфигурация
├── jaeger/                    # Jaeger tracing
│   ├── docker-compose.yml     # Jaeger стек
│   └── jaeger-agent.yaml      # Jaeger Agent конфиг
├── opentelemetry/             # OpenTelemetry
│   └── collector-config.yaml  # Collector конфигурация
├── kubernetes/                # K8s конфигурации
│   ├── health-checks.yaml     # K8s health checks
│   └── health-check-endpoints.ts # Пример health endpoints
├── health-check/              # Health check сервис
└── docker-compose.yml         # Основной compose файл
```

## 📊 Настройка алертов

### Критические алерты
- 🚨 **ServiceDown**: Сервис недоступен
- 🚨 **HighErrorRate**: Высокий процент ошибок (>5%)
- 🚨 **HighMemoryUsage**: Нехватка памяти (>90%)
- 🚨 **DatabaseDown**: База данных недоступна

### Предупреждения
- ⚠️ **HighLatency**: Высокая задержка API (>1s)
- ⚠️ **HighCPUUsage**: Высокое использование CPU (>80%)
- ⚠️ **DiskSpaceLow**: Мало места на диске (<15%)

### Настройка уведомлений

1. **Slack интеграция**:
   ```yaml
   slack_configs:
     - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
       channel: '#alerts'
   ```

2. **Email уведомления**:
   ```yaml
   email_configs:
     - to: 'team@company.com'
       subject: 'Alert: {{ .GroupLabels.alertname }}'
   ```

## 📝 Логирование

### Структура логов
Все логи структурированы в формате JSON с обязательными полями:
```json
{
  "timestamp": "2025-11-02T10:57:28.000Z",
  "level": "info",
  "service": "api-gateway",
  "message": "Request processed",
  "correlation_id": "req-12345",
  "user_id": "user-67890",
  "request_duration": 125
}
```

### Индексы Elasticsearch
- `demo-ai-assistants-logs-YYYY.MM.dd` - Основные логи
- `demo-ai-assistants-errors-YYYY.MM.dd` - Ошибки
- `demo-ai-assistants-critical-YYYY.MM.dd` - Критические события

## 🔍 Distributed Tracing

### Настройка correlation IDs
Все запросы должны содержать correlation ID для отслеживания:

```javascript
const correlationId = `trace-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

// Добавление в заголовки запроса
headers: {
  'X-Correlation-ID': correlationId,
  'X-Trace-ID': correlationId
}
```

### Интеграция с Jaeger
1. Все сервисы отправляют trace data в Jaeger
2. Trace связывается с логами через correlation_id
3. Метрики производительности связаны с trace ID

## 🏥 Health Checks

### Endpoints
- `GET /health/live` - Liveness probe
- `GET /health/ready` - Readiness probe  
- `GET /health/startup` - Startup probe
- `GET /health` - Детальная проверка
- `GET /metrics` - Prometheus метрики

### Kubernetes интеграция
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
```

## 📈 Добавление новых метрик

### Prometheus метрики
```typescript
// Экспорт кастомных метрик
const requestDuration = new prometheus.Histogram({
  name: 'api_request_duration_seconds',
  help: 'API request duration',
  labelNames: ['method', 'route', 'status']
});
```

### Логирование структурированных логов
```typescript
console.log(JSON.stringify({
  timestamp: new Date().toISOString(),
  level: 'info',
  service: 'api-gateway',
  message: 'Request completed',
  correlation_id: correlationId,
  user_id: userId,
  request_duration: duration,
  response_size: responseSize
}));
```

## 🔧 Troubleshooting

### Проблемы с метриками
1. Проверить доступность targets в Prometheus: http://localhost:9090/targets
2. Проверить конфигурацию scrape в prometheus.yml
3. Убедиться что сервисы запущены и expose метрики

### Проблемы с логами
1. Проверить Elasticsearch: http://localhost:9200/_cluster/health
2. Проверить Logstash pipeline: http://localhost:9600/_node/stats
3. Проверить Filebeat: docker logs filebeat

### Проблемы с алертами
1. Проверить AlertManager: http://localhost:9093/#/alerts
2. Проверить правила в Prometheus: http://localhost:9090/rules
3. Проверить webhook endpoints

## 🚀 Мониторинг производительности

### Ключевые метрики для отслеживания:
- **Response Time**: 95-й перцентиль < 1s
- **Error Rate**: < 1% для критических путей
- **Availability**: > 99.5% uptime
- **Throughput**: RPS по сервисам
- **Resource Usage**: CPU < 70%, Memory < 80%

### SLA цели:
- ✅ **Availability**: 99.5%
- ✅ **Response Time**: P95 < 1s, P99 < 2s
- ✅ **Error Rate**: < 1%
- ✅ **Uptime**: 24/7 без degradation

## 📚 Дополнительные ресурсы

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Elasticsearch Guide](https://www.elastic.co/guide/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)

## 🤝 Поддержка

При возникновении проблем:
1. Проверьте логи соответствующих сервисов
2. Убедитесь что все порты доступны
3. Проверьте сетевую связность между сервисами
4. Обратитесь к team по DevOps или SRE

---

**Система мониторинга Demo AI Assistants** - обеспечивает полную observability вашего приложения! 🚀