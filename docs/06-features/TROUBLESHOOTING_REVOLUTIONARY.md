# 🐛 Troubleshooting революционных компонентов

> **Версия:** 1.0.0  
> **Дата:** 2025-01-17

---

## 📋 Содержание

1. [Общие проблемы](#общие-проблемы)
2. [Event-Driven Architecture](#event-driven-architecture)
3. [Self-Evolving AI](#self-evolving-ai)
4. [Self-Healing Code](#self-healing-code)
5. [Distributed Network](#distributed-network)
6. [Monitoring](#monitoring)

---

## 🔧 Общие проблемы

### Проблема: Компоненты не инициализируются

**Симптомы:**
- Ошибка `Orchestrator not initialized`
- Компоненты не запускаются

**Решение:**
```python
# Проверьте инициализацию
from src.ai.advanced_orchestrator import AdvancedAIOrchestrator

orchestrator = AdvancedAIOrchestrator()
await orchestrator.start()  # Важно вызвать start()
```

### Проблема: Зависимости не установлены

**Симптомы:**
- `ImportError: No module named 'nats'`
- `ImportError: No module named 'hypothesis'`

**Решение:**
```bash
pip install -r requirements.txt
# Или конкретно:
pip install nats-py hypothesis psutil numpy
```

---

## 📡 Event-Driven Architecture

### Проблема: NATS не запускается

**Симптомы:**
- `Connection refused` при подключении к NATS
- NATS контейнер не стартует

**Решение:**
```bash
# Проверка статуса
docker ps | grep nats

# Проверка логов
docker logs 1c-ai-nats

# Перезапуск
docker-compose --profile revolutionary restart nats

# Проверка портов
netstat -tuln | grep 4222
```

### Проблема: События не обрабатываются

**Симптомы:**
- События публикуются, но handlers не вызываются
- События теряются

**Решение:**
```python
# Проверка подписки
event_bus = EventBus()
await event_bus.start()

# Убедитесь, что handler зарегистрирован
handler = MyHandler()
event_bus.subscribe(EventType.MY_EVENT, handler)

# Проверка истории
history = event_bus.get_event_history()
print(f"Events in history: {len(history)}")
```

---

## 🧠 Self-Evolving AI

### Проблема: Эволюция не улучшает систему

**Симптомы:**
- `improvements_applied: 0`
- Fitness не увеличивается

**Решение:**
```python
# Проверка метрик перед эволюцией
metrics = orchestrator.get_metrics_summary()
print(f"Current metrics: {metrics}")

# Принудительная эволюция
result = await orchestrator.evolve()
print(f"Evolution result: {result}")

# Проверка LLM провайдера
llm_provider = orchestrator._get_llm_provider()
if not llm_provider:
    print("LLM provider not configured")
```

### Проблема: Эволюция занимает слишком много времени

**Симптомы:**
- Эволюция выполняется > 5 минут
- Таймауты

**Решение:**
```python
# Уменьшение количества улучшений
config = config_manager.get_component_config("self_evolving")
config.settings["max_improvements"] = 5  # Вместо 10

# Использование кэша
orchestrator.cache.enabled = True
```

---

## 🔧 Self-Healing Code

### Проблема: Ошибки не исправляются автоматически

**Симптомы:**
- `fix is None` после handle_error
- Ошибки остаются

**Решение:**
```python
# Проверка конфигурации
config = config_manager.get_component_config("self_healing")
print(f"Self-healing enabled: {config.enabled}")
print(f"Use patterns: {config.settings.get('use_patterns')}")

# Проверка LLM провайдера
if not healing_code.llm_provider:
    print("LLM provider not configured")

# Проверка статистики
stats = healing_code.get_healing_stats()
print(f"Healing stats: {stats}")
```

### Проблема: Self-healing создает неправильные исправления

**Симптомы:**
- Исправления не работают
- Код становится хуже

**Решение:**
```python
# Отключение автоматического применения
config.settings["auto_apply"] = False

# Ручная проверка исправлений
fix = await healing_code.handle_error(error, context)
if fix:
    # Проверка исправления перед применением
    if fix.confidence > 0.8:
        # Применить исправление
        pass
```

---

## 🌐 Distributed Network

### Проблема: Агенты не находят друг друга

**Симптомы:**
- `No agents available`
- Консенсус не достигается

**Решение:**
```python
# Проверка регистрации агентов
stats = agent_network.get_network_stats()
print(f"Agents: {stats['agents_count']}")

# Ручная регистрация
from src.ai.distributed_agent_network import AgentNode, AgentRole

node = AgentNode(role=AgentRole.DEVELOPER)
agent = MyAgent(node, agent_network)
await agent_network.register_agent(agent)
```

### Проблема: Консенсус не достигается

**Симптомы:**
- `consensus_reached: false`
- Задачи не выполняются

**Решение:**
```python
# Проверка количества агентов
# Для Raft нужно минимум 3 узла
# Для PBFT нужно 3f+1 узлов (f - fault tolerance)

if len(agents) < 3:
    print("Not enough agents for consensus")

# Использование простого консенсуса
result = await agent_network.reach_consensus(
    initiator_id,
    question,
    options,
    algorithm=ConsensusAlgorithm.MAJORITY_VOTE  # Проще чем Raft
)
```

---

## 📊 Monitoring

### Проблема: Prometheus не собирает метрики

**Симптомы:**
- Метрики не отображаются в Prometheus
- `/metrics` endpoint возвращает пустой ответ

**Решение:**
```bash
# Проверка конфигурации Prometheus
cat monitoring/prometheus/prometheus.yml

# Проверка targets
curl http://localhost:9090/api/v1/targets

# Проверка метрик приложения
curl http://localhost:8080/metrics
```

### Проблема: Grafana не показывает данные

**Симптомы:**
- Дашборды пустые
- "No data" в графиках

**Решение:**
```bash
# Проверка подключения к Prometheus
# В Grafana: Configuration > Data Sources > Prometheus
# URL: http://prometheus:9090

# Проверка запросов
# В Grafana: Explore > Prometheus
# Запрос: revolutionary_events_published_total
```

---

## 🔍 Диагностика

### Логи

```bash
# Все логи революционных компонентов
docker logs 1c-ai-nats
docker logs 1c-ai-prometheus
docker logs 1c-ai-grafana

# Логи приложения
tail -f logs/app.log | grep revolutionary
```

### Метрики

```python
# Получение всех метрик
metrics = orchestrator.get_metrics_summary()
print(json.dumps(metrics, indent=2))

# Проверка здоровья компонентов
health = {
    "event_bus": event_bus._running,
    "evolving_ai": evolving_ai._is_evolving,
    "healing_code": healing_code._enabled,
    "agent_network": len(agent_network._agents) > 0
}
print(f"Health: {health}")
```

---

## 📞 Поддержка

Если проблема не решена:

1. Проверьте логи
2. Проверьте конфигурацию
3. Проверьте зависимости
4. Создайте issue с деталями

---

**Конец документа**



## Общие Проблемы

TODO: Добавить содержание раздела.


## Event Driven Architecture

TODO: Добавить содержание раздела.


## Self Evolving Ai

TODO: Добавить содержание раздела.


## Self Healing Code

TODO: Добавить содержание раздела.


## Distributed Network

TODO: Добавить содержание раздела.


## Monitoring

TODO: Добавить содержание раздела.
