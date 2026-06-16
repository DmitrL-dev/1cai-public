# 🔗 Интеграция революционных компонентов с существующей системой

> **Версия:** 1.0.0  
> **Дата:** 2025-01-17

---

## 📋 Содержание

1. [Обзор интеграции](#обзор-интеграции)
2. [Интеграция с AI Orchestrator](#интеграция-с-ai-orchestrator)
3. [Интеграция с API Gateway](#интеграция-с-api-gateway)
4. [Интеграция с Data Layer](#интеграция-с-data-layer)
5. [Миграция с Celery](#миграция-с-celery)
6. [Конфигурация](#конфигурация)
7. [Мониторинг](#мониторинг)

---

## 🎯 Обзор интеграции

Революционные компоненты интегрированы с существующей системой через:

- **AdvancedAIOrchestrator** - расширенный orchestrator с продвинутыми компонентами
- **Graph API Revolutionary** - новые endpoints для революционных компонентов
- **Unified Data Layer Integration** - единый интерфейс для всех БД
- **Event-Driven Architecture** - замена Celery

---

## 🔌 Интеграция с AI Orchestrator

### Использование

```python
from src.ai.advanced_orchestrator import AdvancedAIOrchestrator

# Создание orchestrator
orchestrator = AdvancedAIOrchestrator()
await orchestrator.start()

# Обработка запроса (с автоматическим self-healing)
result = await orchestrator.process_query("Your query here")

# Запуск эволюции
evolution_result = await orchestrator.evolve()

# Координация агентов
network_result = await orchestrator.coordinate_agents(
    "Task description",
    ["developer", "qa_engineer"]
)

# Остановка
await orchestrator.stop()
```

### Автоматические возможности

1. **Self-Healing** - автоматическое исправление ошибок
2. **Event Publishing** - все операции публикуются как события
3. **Metrics Collection** - автоматический сбор метрик
4. **Agent Coordination** - координация через Distributed Network

---

## 🌐 Интеграция с API Gateway

### Новые Endpoints

#### `/api/revolutionary/evolve`
Запуск эволюции AI системы

```bash
POST /api/revolutionary/evolve
{
  "force": false
}
```

#### `/api/revolutionary/heal`
Автоматическое исправление ошибки

```bash
POST /api/revolutionary/heal
{
  "error_message": "Error description",
  "context": {
    "file_path": "src/example.py",
    "line_number": 42
  }
}
```

#### `/api/revolutionary/network/task`
Отправка задачи в Distributed Network

```bash
POST /api/revolutionary/network/task
{
  "description": "Task description",
  "agent_roles": ["developer", "qa_engineer"]
}
```

#### `/api/revolutionary/metrics`
Получение метрик всех компонентов

```bash
GET /api/revolutionary/metrics
```

#### `/api/revolutionary/analytics/report`
Получение аналитического отчета

```bash
GET /api/revolutionary/analytics/report?period_days=7&components=event_driven,self_evolving
```

#### `/api/revolutionary/config`
Управление конфигурацией

```bash
GET /api/revolutionary/config?component=event_driven
PUT /api/revolutionary/config?component=event_driven
{
  "settings": {
    "num_workers": 8
  }
}
```

---

## 💾 Интеграция с Data Layer

### Использование Unified Data Layer

```python
from src.data.unified_data_layer_integration import UnifiedDataLayerIntegration
from src.infrastructure.data_layer import DataSource

# Инициализация
data_integration = UnifiedDataLayerIntegration()

# Регистрация клиентов
data_integration.register_postgres_client(postgres_client)
data_integration.register_neo4j_client(neo4j_client)
data_integration.register_qdrant_client(qdrant_client)

# Единый интерфейс
result = await data_integration.unified_read(
    DataSource.POSTGRESQL,
    query_data
)

await data_integration.unified_write(
    DataSource.NEO4J,
    node_data
)
```

---

## 🔄 Миграция с Celery

### Автоматическая миграция

```bash
# Dry run (проверка без изменений)
python src/migration/celery_to_event_driven.py --dry-run

# Реальная миграция
python src/migration/celery_to_event_driven.py --migrate
```

### Ручная миграция

**До (Celery):**
```python
from celery import Celery

celery_app = Celery('tasks')

@celery_app.task
def train_model(model_type: str):
    # Логика обучения
    pass
```

**После (Event-Driven):**
```python
from src.infrastructure.event_bus import EventHandler, EventType

class TrainModelHandler(EventHandler):
    @property
    def event_types(self):
        return {EventType.ML_TRAINING_STARTED}
    
    async def handle(self, event: Event) -> None:
        model_type = event.payload.get("model_type")
        # Логика обучения
        pass
```

---

## ⚙️ Конфигурация

### Environment Variables

```bash
# Event-Driven
EVENT_DRIVEN_ENABLED=true
EVENT_BACKEND=nats  # или memory
EVENT_WORKERS=4
NATS_URL=nats://localhost:4222

# Self-Evolving AI
SELF_EVOLVING_ENABLED=true
SELF_EVOLVING_RL=true
SELF_EVOLVING_MULTI_OBJ=true

# Self-Healing Code
SELF_HEALING_ENABLED=true
SELF_HEALING_PATTERNS=true
SELF_HEALING_LEARN=true

# Distributed Network
DISTRIBUTED_NETWORK_ENABLED=true
CONSENSUS_PROTOCOL=raft
FAULT_TOLERANCE=1
```

### Config File

```yaml
components:
  event_driven:
    enabled: true
    settings:
      backend: nats
      num_workers: 4
      nats_url: nats://localhost:4222
  
  self_evolving:
    enabled: true
    settings:
      use_rl: true
      multi_objective: true
  
  self_healing:
    enabled: true
    settings:
      use_patterns: true
      learn_from_history: true
```

---

## 📊 Мониторинг

### Prometheus Metrics

Все компоненты экспортируют метрики в Prometheus:

- `revolutionary_events_published_total` - количество опубликованных событий
- `revolutionary_evolution_cycles_total` - циклы эволюции
- `revolutionary_errors_detected_total` - обнаруженные ошибки
- `revolutionary_fixes_applied_total` - примененные исправления
- `revolutionary_agents_total` - количество агентов
- `revolutionary_tasks_completed_total` - завершенные задачи

### Grafana Dashboards

Дашборды доступны по адресу: `http://localhost:3001`

- Revolutionary Components Overview
- Event-Driven Architecture
- Self-Evolving AI
- Self-Healing Code
- Distributed Network

---

## 🚀 Запуск

### Docker Compose

```bash
# Запуск с революционными компонентами
docker-compose --profile revolutionary up -d

# Запуск с мониторингом
docker-compose --profile revolutionary --profile monitoring up -d
```

### Проверка

```bash
# Проверка NATS
curl http://localhost:8222/healthz

# Проверка Prometheus
curl http://localhost:9090/-/healthy

# Проверка Grafana
curl http://localhost:3001/api/health
```

---

## 🐛 Troubleshooting

### NATS не запускается

```bash
# Проверка логов
docker logs 1c-ai-nats

# Проверка портов
netstat -tuln | grep 4222
```

### Prometheus не собирает метрики

1. Проверьте конфигурацию в `monitoring/prometheus/prometheus.yml`
2. Убедитесь, что приложение экспортирует метрики на `/metrics`
3. Проверьте targets в Prometheus UI

### Self-Healing не работает

1. Проверьте, что LLM провайдер настроен
2. Проверьте логи на наличие ошибок
3. Убедитесь, что `SELF_HEALING_ENABLED=true`

---

**Конец документа**



## Обзор Интеграции

TODO: Добавить содержание раздела.


## Интеграция С Ai Orchestrator

TODO: Добавить содержание раздела.


## Интеграция С Api Gateway

TODO: Добавить содержание раздела.


## Интеграция С Data Layer

TODO: Добавить содержание раздела.


## Миграция С Celery

TODO: Добавить содержание раздела.


## Конфигурация

TODO: Добавить содержание раздела.


## Мониторинг

TODO: Добавить содержание раздела.
