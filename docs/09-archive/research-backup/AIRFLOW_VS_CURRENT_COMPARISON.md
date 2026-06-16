# 🔄 Apache Airflow vs Текущая архитектура 1C AI Stack

**Дата анализа:** 2024-11-05  
**Цель:** Сравнительный анализ workflow orchestration решений

---

## 📊 Executive Summary

### Текущее состояние проекта:

**У нас есть 4 разных системы оркестрации:**
1. ✅ **Celery** - для ML задач и периодических заданий
2. ✅ **Workflow Orchestrator** - для демо-системы (TypeScript)
3. ✅ **AI Orchestrator** - для маршрутизации AI запросов
4. ✅ **Background Jobs** - простая очередь задач в PostgreSQL

**Apache Airflow мог бы:**
- 🔄 Заменить Celery для ML pipelines
- 🔄 Унифицировать все workflow в одном месте
- ➕ Добавить визуальный UI для DAGs
- ➕ Улучшить мониторинг и алертинг

---

## 🎯 Что такое Apache Airflow?

**Apache Airflow** - это платформа для программного создания, планирования и мониторинга workflow'ов (DAG - Directed Acyclic Graph).

### Ключевые концепции:

```python
# Пример DAG в Airflow
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

dag = DAG(
    'ml_pipeline',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1)
)

def train_model():
    # Training logic
    pass

def evaluate_model():
    # Evaluation logic
    pass

train_task = PythonOperator(
    task_id='train',
    python_callable=train_model,
    dag=dag
)

evaluate_task = PythonOperator(
    task_id='evaluate',
    python_callable=evaluate_model,
    dag=dag
)

train_task >> evaluate_task  # Dependency
```

---

## 🔍 Детальное сравнение

### 1. Текущая система: Celery (ML Tasks)

**Файл:** `src/workers/ml_tasks.py`

**Что есть:**
```python
celery_app = Celery(
    "ml_worker",
    broker=settings.CELERY_BROKER_URL,  # Redis
    backend=settings.CELERY_RESULT_BACKEND
)

# Периодические задачи (Celery Beat)
beat_schedule={
    'retrain-models-daily': {
        'task': 'workers.ml_tasks.retrain_all_models',
        'schedule': crontab(hour=2, minute=0),  # Ежедневно в 2:00
    },
    'update-feature-store': {
        'task': 'workers.ml_tasks.update_feature_store',
        'schedule': crontab(minute=0),  # Каждый час
    },
    'cleanup-old-experiments': {
        'task': 'workers.ml_tasks.cleanup_old_experiments',
        'schedule': crontab(hour=1, minute=0),
    },
    'check-model-drift': {
        'task': 'workers.ml_tasks.check_model_drift',
        'schedule': crontab(minute=30),  # Каждые 30 минут
    },
    'retrain-underperforming': {
        'task': 'workers.ml_tasks.retrain_underperforming_models',
        'schedule': crontab(hour=3, minute=0),
    }
}
```

**Возможности:**
- ✅ Асинхронное выполнение задач
- ✅ Периодические задания (cron-like)
- ✅ Retry логика
- ✅ Распределенное выполнение
- ✅ Мониторинг через Flower
- ❌ Нет UI для просмотра DAG
- ❌ Нет визуализации зависимостей
- ❌ Сложный мониторинг pipeline'ов
- ❌ Нет встроенного version control для задач

---

### Эквивалент в Airflow:

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime, timedelta

# DAG для ML Pipeline
with DAG(
    'ml_training_pipeline',
    default_args={
        'owner': '1c-ai-team',
        'depends_on_past': False,
        'email_on_failure': True,
        'email_on_retry': False,
        'retries': 3,
        'retry_delay': timedelta(minutes=5),
    },
    description='Daily ML model training and evaluation',
    schedule_interval='0 2 * * *',  # Ежедневно в 2:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['ml', 'training', 'production'],
) as dag:

    # Task 1: Update feature store
    update_features = PythonOperator(
        task_id='update_feature_store',
        python_callable=update_feature_store_func
    )
    
    # Task 2: Retrain models
    retrain_models = PythonOperator(
        task_id='retrain_all_models',
        python_callable=retrain_all_models_func
    )
    
    # Task 3: Check model drift
    check_drift = PythonOperator(
        task_id='check_model_drift',
        python_callable=check_model_drift_func
    )
    
    # Task 4: Cleanup old experiments
    cleanup = PythonOperator(
        task_id='cleanup_old_experiments',
        python_callable=cleanup_old_experiments_func
    )
    
    # Define dependencies (DAG)
    update_features >> retrain_models >> check_drift >> cleanup
```

**Преимущества Airflow:**
- ✅ Визуализация DAG в UI
- ✅ Мониторинг выполнения в реальном времени
- ✅ История запусков
- ✅ Логи для каждого task
- ✅ Retry/Backfill из UI
- ✅ SLA monitoring
- ✅ Task dependencies визуально
- ✅ Интеграция с 100+ сервисов (providers)

---

## 📋 Сравнительная таблица

| Критерий | Celery (текущее) | Apache Airflow |
|----------|------------------|----------------|
| **Scheduling** | ✅ Celery Beat (cron-like) | ✅ DAG scheduler (более гибкий) |
| **Task Dependencies** | ❌ Нужно писать вручную в коде | ✅ Визуально через DAG (task1 >> task2) |
| **UI/Dashboard** | ⚠️ Flower (базовый) | ✅ Rich Web UI (встроенный) |
| **Визуализация Workflow** | ❌ Нет | ✅ Граф зависимостей, Gantt chart |
| **Мониторинг** | ⚠️ Через Flower + Prometheus | ✅ Встроенный + Metrics |
| **Логи** | ⚠️ Разбросаны, нужно собирать | ✅ Централизованы для каждого task |
| **Retry логика** | ✅ Есть (в task config) | ✅ Есть (более гибкая, per-task) |
| **Backfill** | ❌ Нужно писать руками | ✅ Встроенный механизм |
| **SLA Monitoring** | ❌ Нет | ✅ Есть |
| **Alerting** | ⚠️ Нужно настраивать отдельно | ✅ Email, Slack встроенно |
| **Version Control** | ⚠️ Git для кода, но нет версий DAG | ✅ DAG as code (Git-friendly) |
| **Динамические pipeline'ы** | ❌ Сложно | ✅ Легко (Python code для DAG) |
| **Testing** | ⚠️ Стандартные pytest тесты | ✅ Встроенные утилиты для тестирования DAG |
| **Масштабирование** | ✅ Horizontal scaling workers | ✅ Horizontal scaling (Celery/K8s executor) |
| **Интеграции** | ⚠️ Нужно писать руками | ✅ 100+ providers (AWS, GCP, databases) |
| **Кривая обучения** | 🟢 Низкая | 🟡 Средняя |
| **Resource overhead** | 🟢 Низкий | 🟡 Средний (требует metadata DB) |
| **Production-ready** | ✅ Да | ✅ Да (используется в Airbnb, Uber, etc) |

---

## 🏗️ Текущая архитектура оркестрации

### 1. Celery для ML Tasks

```
┌─────────────────────────────────────────┐
│         Celery Architecture             │
├─────────────────────────────────────────┤
│                                         │
│  FastAPI App                            │
│      ↓                                  │
│  Celery Client ──────→ Redis (Broker)  │
│                           ↓             │
│                    Celery Workers       │
│                    (3-5 instances)      │
│                           ↓             │
│                    Task Execution       │
│                    - ML Training        │
│                    - Feature Update     │
│                    - Model Evaluation   │
│                                         │
│  Celery Beat ─────→ Redis              │
│  (Scheduler)           ↓                │
│                 Periodic Tasks          │
│                                         │
│  Monitoring:                            │
│  - Flower (Web UI)                      │
│  - Prometheus metrics                   │
└─────────────────────────────────────────┘
```

**Проблемы:**
- ❌ Сложно видеть зависимости между задачами
- ❌ Нет визуализации workflow
- ❌ Мониторинг разбросан (Flower + Prometheus + Logs)
- ❌ Сложно делать backfill для исторических данных
- ❌ Нет SLA мониторинга

---

### 2. Workflow Orchestrator (Demo System)

**Файл:** `supabase/functions/workflow-orchestrator/index.ts`

```typescript
// Управляет последовательным выполнением агентов
async function processWorkflow(demoId, userTask, stages) {
    // Этап 1: Анализ задачи (Architect Agent)
    analysisResult = await callAgent('analyze-task', {
        user_task: userTask,
        demo_id: demoId
    });
    
    // Этап 2: Разработка решения (Developer Agent)
    solutionResult = await callAgent('develop-solution', {
        user_task: userTask,
        analysis: analysisResult,
        demo_id: demoId
    });
    
    // Этап 3: Консультация
    await callAgent('provide-consultation', {
        user_task: userTask,
        solution: solutionResult,
        demo_id: demoId
    });
}
```

**Проблемы:**
- ❌ Hardcoded порядок выполнения
- ❌ Нет возможности параллельного выполнения
- ❌ Retry логика примитивная
- ❌ Нет визуализации workflow
- ❌ Сложно добавлять новые этапы

---

### Эквивалент в Airflow:

```python
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from datetime import datetime

with DAG(
    'ai_agents_workflow',
    schedule_interval=None,  # Triggered manually
    start_date=datetime(2024, 1, 1),
) as dag:

    # Dynamic task creation based on selected_agent
    def choose_agents(**context):
        selected = context['dag_run'].conf.get('selected_agent')
        if selected == 'analyze-task':
            return ['architect_agent']
        elif selected == 'all':
            return ['architect_agent', 'developer_agent', 'consultant_agent']
        return ['architect_agent']
    
    branch = BranchPythonOperator(
        task_id='choose_workflow',
        python_callable=choose_agents
    )
    
    architect = PythonOperator(
        task_id='architect_agent',
        python_callable=call_architect_agent
    )
    
    developer = PythonOperator(
        task_id='developer_agent',
        python_callable=call_developer_agent
    )
    
    consultant = PythonOperator(
        task_id='consultant_agent',
        python_callable=call_consultant_agent
    )
    
    # Flexible dependencies
    branch >> architect
    architect >> developer
    developer >> consultant
```

**Преимущества:**
- ✅ Визуальный граф workflow
- ✅ Гибкие зависимости
- ✅ Conditional execution (BranchPythonOperator)
- ✅ Параллельное выполнение (если нужно)
- ✅ Встроенный retry с backoff
- ✅ Логи для каждого агента отдельно

---

### 3. AI Orchestrator (Query Routing)

**Файл:** `src/ai/orchestrator.py`

```python
class AIOrchestrator:
    """Intelligent routing of queries to AI services"""
    
    async def process_query(self, query: str, context: Dict) -> Dict:
        # Classify query
        intent = self.classifier.classify(query)
        
        # Route to appropriate service
        if intent.query_type == QueryType.CODE_GENERATION:
            return await self.qwen_service.generate(query)
        elif intent.query_type == QueryType.SEMANTIC_SEARCH:
            return await self.qdrant_service.search(query)
        elif intent.query_type == QueryType.GRAPH_QUERY:
            return await self.neo4j_service.query(query)
        # ...
```

**Это НЕ workflow orchestration** - это routing/dispatching.

Airflow здесь не подходит, т.к. это синхронный real-time процесс.

---

### 4. Background Jobs (PostgreSQL)

**Таблица:** `tasks.background_jobs`

```sql
CREATE TABLE tasks.background_jobs (
    id UUID PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE,
    job_type VARCHAR(100),
    job_data JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3
);
```

**Проблемы:**
- ❌ Примитивная очередь без worker'ов
- ❌ Нет автоматического retry
- ❌ Нет приоритетов
- ❌ Нужно самим писать worker для обработки

**Airflow мог бы заменить** эту таблицу на полноценную систему задач.

---

## 💡 Что даст внедрение Apache Airflow?

### Use Case 1: ML Pipeline (замена Celery)

**До (Celery):**
```python
# 5 отдельных task'ов в beat_schedule
# Сложно видеть связи между ними
# Нет визуализации
```

**После (Airflow):**
```python
# Один DAG с визуальным графом:
# update_features → retrain_models → evaluate → check_drift → cleanup
#                                   ↓
#                              update_model_registry
```

**Выгоды:**
- ✅ Визуальная карта всего ML pipeline
- ✅ История запусков (кто, когда, результат)
- ✅ Легко добавлять новые шаги
- ✅ Параллельное выполнение где возможно
- ✅ SLA алерты если training занимает > N часов

---

### Use Case 2: Data Pipeline

**Новый workflow (сейчас нет):**
```python
with DAG('data_sync_pipeline', schedule_interval='@hourly') as dag:
    
    # Extract
    extract_1c = PythonOperator(
        task_id='extract_from_1c',
        python_callable=extract_1c_metadata
    )
    
    # Transform
    transform = PythonOperator(
        task_id='transform_data',
        python_callable=transform_metadata
    )
    
    # Load to multiple targets (parallel)
    load_postgres = PostgresOperator(
        task_id='load_to_postgres',
        sql='INSERT INTO ...'
    )
    
    load_neo4j = PythonOperator(
        task_id='load_to_neo4j',
        python_callable=load_to_neo4j
    )
    
    load_qdrant = PythonOperator(
        task_id='vectorize_and_load',
        python_callable=load_to_qdrant
    )
    
    # Dependencies
    extract_1c >> transform >> [load_postgres, load_neo4j, load_qdrant]
```

**Выгоды:**
- ✅ ETL pipeline из коробки
- ✅ Параллельная загрузка в 3 БД
- ✅ Мониторинг каждого этапа
- ✅ Автоматический retry при сбоях

---

### Use Case 3: Периодическое обслуживание

**Новые DAG'и:**
```python
# 1. Cleanup старых данных
cleanup_dag = DAG('cleanup_old_data', schedule_interval='0 1 * * *')
    - cleanup_logs (> 30 days)
    - cleanup_cache
    - vacuum_database
    - update_stats

# 2. Health checks
health_check_dag = DAG('system_health', schedule_interval='*/15 * * * *')
    - check_db_connections
    - check_redis_memory
    - check_disk_space
    - check_api_latency
    - send_alerts (if needed)

# 3. Reporting
reporting_dag = DAG('daily_reports', schedule_interval='0 9 * * *')
    - collect_metrics
    - generate_report
    - send_to_slack
```

---

## ⚖️ Когда использовать что?

### Используйте Celery если:
- ✅ Нужен lightweight task queue
- ✅ Простые задачи без сложных зависимостей
- ✅ Real-time processing (как email отправка)
- ✅ Микросервисная архитектура с event-driven паттерном

### Используйте Airflow если:
- ✅ Сложные data pipeline'ы с зависимостями
- ✅ ML pipeline'ы (training → evaluation → deployment)
- ✅ ETL процессы
- ✅ Нужна визуализация и мониторинг workflow
- ✅ Batch processing с расписанием
- ✅ Backfilling исторических данных

### Можно использовать оба:
- ✅ Airflow для orchestration DAG'ов
- ✅ Celery для выполнения отдельных task'ов внутри DAG
- ✅ Airflow использует Celery как executor! (CeleryExecutor)

---

## 🎯 Рекомендации для 1C AI Stack

### Вариант 1: Hybrid подход (Рекомендуется)

```
Apache Airflow (Orchestration)
    ↓
    ├─→ Celery Tasks (для тяжелых ML задач)
    ├─→ Python Operators (для легких задач)
    ├─→ PostgresOperator (для SQL)
    └─→ Custom Operators (для 1C интеграции)
```

**Архитектура:**
```
┌──────────────────────────────────────────────┐
│            Apache Airflow Scheduler          │
│                                              │
│  DAG 1: ML Training Pipeline                │
│  ┌────────────────────────────────────────┐ │
│  │ Extract → Transform → Train → Evaluate │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  DAG 2: Data Sync Pipeline                  │
│  ┌────────────────────────────────────────┐ │
│  │ 1C → Transform → [PG, Neo4j, Qdrant]  │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  DAG 3: Maintenance Pipeline                │
│  ┌────────────────────────────────────────┐ │
│  │ Cleanup → Vacuum → Health Check       │ │
│  └────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
                    ↓
        ┌───────────┴──────────┐
        │                      │
    Celery Workers      PostgreSQL
    (для ML задач)      Neo4j, Qdrant
```

**Что делаем:**
1. Заменяем Celery Beat на Airflow Scheduler
2. Оставляем Celery Workers для тяжелых ML задач
3. Используем Airflow UI для мониторинга
4. Пишем DAG'и для всех pipeline'ов

---

### Вариант 2: Полная миграция на Airflow

**Что убираем:**
- ❌ Celery Beat (scheduler)
- ❌ Workflow Orchestrator (TypeScript)
- ❌ Background Jobs таблица

**Что добавляем:**
- ✅ Apache Airflow (webserver + scheduler + workers)
- ✅ PostgreSQL для Airflow metadata
- ✅ Все workflow как DAG'и

**Плюсы:**
- ✅ Единая система оркестрации
- ✅ Мощный UI
- ✅ Лучший мониторинг

**Минусы:**
- ❌ Больше overhead
- ❌ Дополнительная инфраструктура
- ❌ Время на миграцию

---

### Вариант 3: Оставить как есть (Не рекомендуется)

**Проблемы которые останутся:**
- ❌ 4 разные системы оркестрации
- ❌ Сложный мониторинг
- ❌ Нет единого UI
- ❌ Дублирование функционала
- ❌ Высокая сложность поддержки

---

## 📊 Сравнение инфраструктуры

### Текущая инфраструктура:

```yaml
services:
  # Celery
  redis:          # Broker для Celery
  celery-worker:  # ML worker
  celery-beat:    # Scheduler
  flower:         # Monitoring UI (опционально)
  
  # Background jobs
  postgres:       # Для background_jobs таблицы
  
  # Основные сервисы
  api-server:
  telegram-bot:
  # ...
```

**Resource usage:**
- Redis: ~100MB
- Celery Worker: ~500MB-1GB (per worker)
- Celery Beat: ~50MB
- Flower: ~100MB

**Total: ~1GB-2GB** для оркестрации

---

### С Apache Airflow:

```yaml
services:
  # Airflow
  airflow-webserver:   # UI
  airflow-scheduler:   # DAG scheduler
  airflow-worker:      # Task executor (если CeleryExecutor)
  postgres:            # Airflow metadata DB
  redis:               # Celery broker (если CeleryExecutor)
  
  # Опционально Celery для тяжелых задач
  celery-worker:       # Для ML
  
  # Основные сервисы
  api-server:
  telegram-bot:
  # ...
```

**Resource usage:**
- Airflow Webserver: ~500MB
- Airflow Scheduler: ~300MB
- Airflow Worker: ~500MB (per worker)
- PostgreSQL (metadata): ~200MB
- Redis: ~100MB

**Total: ~1.5GB-3GB** для Airflow

**Разница:** +500MB-1GB overhead

---

## 💰 Cost-Benefit Analysis

### Costs:

**Разработка:**
- Миграция Celery tasks → Airflow DAGs: **20-40 часов**
- Настройка Airflow инфраструктуры: **8-16 часов**
- Тестирование и отладка: **16-24 часа**
- Документация: **8 часов**

**Total:** ~50-90 часов разработки

**Инфраструктура:**
- +500MB-1GB RAM
- Дополнительная PostgreSQL DB для metadata
- Возможно дополнительный pod в K8s

**Обучение команды:**
- Airflow concepts: 4-8 часов
- DAG development: 8-16 часов

---

### Benefits:

**Краткосрочные (0-3 месяца):**
- ✅ Визуализация всех workflow
- ✅ Централизованный мониторинг
- ✅ Улучшенный debugging (логи по task)
- ✅ SLA monitoring

**Среднесрочные (3-12 месяцев):**
- ✅ Быстрая разработка новых pipeline'ов
- ✅ Меньше времени на troubleshooting
- ✅ Лучший onboarding новых разработчиков
- ✅ Унификация оркестрации

**Долгосрочные (12+ месяцев):**
- ✅ Масштабируемость
- ✅ Готовые интеграции с cloud services
- ✅ Community support
- ✅ Production-proven решение

**Экономия времени:** ~20-30% на разработку и поддержку pipeline'ов

---

## 🚀 План миграции (если решим внедрять)

### Phase 1: Setup (1-2 недели)

**Week 1:**
- [ ] Установить Airflow в development
- [ ] Настроить PostgreSQL для metadata
- [ ] Настроить CeleryExecutor
- [ ] Создать базовый DAG для тестирования

**Week 2:**
- [ ] Настроить мониторинг (Prometheus + Grafana)
- [ ] Настроить алертинг (Email/Slack)
- [ ] Создать документацию для команды
- [ ] Провести обучение команды

---

### Phase 2: Миграция ML Pipeline (2-3 недели)

**Week 3:**
- [ ] Создать DAG для `retrain-models-daily`
- [ ] Портировать task'и из Celery
- [ ] Добавить зависимости между task'ами
- [ ] Тестирование в dev

**Week 4:**
- [ ] Создать DAG для остальных ML задач
- [ ] Добавить SLA monitoring
- [ ] Интеграция с MLflow
- [ ] Тестирование в staging

**Week 5:**
- [ ] Deploy в production
- [ ] Параллельный запуск (Celery + Airflow)
- [ ] Мониторинг результатов
- [ ] Отключение Celery Beat

---

### Phase 3: Новые Pipeline'ы (2-4 недели)

**Week 6-7:**
- [ ] Создать Data Sync Pipeline (1C → DBs)
- [ ] Создать Maintenance Pipeline
- [ ] Создать Reporting Pipeline

**Week 8-9:**
- [ ] Оптимизация performance
- [ ] Добавление alert'ов
- [ ] Финальное тестирование
- [ ] Production rollout

---

### Phase 4: Оптимизация (ongoing)

- [ ] Настройка auto-scaling для workers
- [ ] Оптимизация ресурсов
- [ ] Добавление новых DAG'ов
- [ ] Continuous improvement

---

## 📝 Выводы

### ✅ Плюсы внедрения Airflow:

1. **Визуализация** - видим весь workflow на графе
2. **Мониторинг** - единый UI для всех pipeline'ов
3. **Унификация** - одна система вместо 4-х разных
4. **Production-ready** - проверено в крупных компаниях
5. **Экосистема** - 100+ готовых integrations
6. **Масштабируемость** - легко добавлять новые DAG'и
7. **Developer Experience** - проще разрабатывать и поддерживать

### ❌ Минусы внедрения Airflow:

1. **Overhead** - дополнительные 500MB-1GB RAM
2. **Complexity** - еще один компонент инфраструктуры
3. **Migration cost** - 50-90 часов разработки
4. **Learning curve** - команда должна изучить Airflow
5. **Not for real-time** - не подходит для синхронных задач

### 🎯 Итоговая рекомендация:

**Да, стоит внедрять Airflow, НО постепенно:**

**Вариант: Hybrid Approach**
- ✅ Внедрить Airflow для ML pipeline'ов
- ✅ Оставить AI Orchestrator для real-time routing
- ✅ Использовать Celery Workers внутри Airflow (CeleryExecutor)
- ✅ Постепенно мигрировать остальные workflow'ы

**Приоритет:**
1. **High**: ML Training Pipeline (заменить Celery Beat)
2. **Medium**: Data Sync Pipeline (новый функционал)
3. **Low**: Maintenance tasks (можно оставить в Celery)

**Timeline:** 2-3 месяца для полной миграции

**ROI:** Положительный через 6-12 месяцев (экономия времени разработки)

---

## 🔗 Дополнительные ресурсы

**Apache Airflow:**
- Документация: https://airflow.apache.org/docs/
- Best Practices: https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html
- Providers: https://airflow.apache.org/docs/apache-airflow-providers/

**Примеры DAG'ов:**
- ML Pipeline: https://github.com/apache/airflow/tree/main/airflow/example_dags
- ETL: https://github.com/airflow-plugins/Example-Airflow-DAGs

**Мониторинг:**
- Airflow + Prometheus: https://airflow.apache.org/docs/apache-airflow/stable/logging-monitoring/metrics.html

---

**Дата создания:** 2024-11-05  
**Статус:** Аналитический документ (не коммитится в Git)  
**Действие:** Для обсуждения с командой

