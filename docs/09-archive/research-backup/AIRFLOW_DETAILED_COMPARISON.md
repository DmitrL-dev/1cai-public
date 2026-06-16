# 🔬 Apache Airflow vs 1C AI Stack - Детальный технический анализ

**Версия:** 1.0 Extended  
**Дата:** 2024-11-05  
**Цель:** Максимально детальное сравнение с техническими спецификациями

---

## 📐 Текущая архитектура оркестрации (AS-IS)

### Компонент 1: Celery для ML Tasks

```mermaid
graph TB
    subgraph "Celery Beat (Scheduler)"
        BEAT[Celery Beat Process<br/>PID: xxx<br/>Memory: 50MB]
        
        SCHEDULE["Beat Schedule:<br/>- retrain-models-daily (2:00)<br/>- update-feature-store (hourly)<br/>- cleanup-old-experiments (1:00)<br/>- check-model-drift (every 30min)<br/>- retrain-underperforming (3:00)"]
    end
    
    subgraph "Redis Broker"
        REDIS_BROKER["Redis DB 1<br/>Port: 6379<br/>Keys:<br/>- celery-task-meta-*<br/>- _kombu.binding.*<br/>Max memory: 2GB"]
    end
    
    subgraph "Celery Workers (3 instances)"
        W1["Worker 1<br/>Concurrency: 4<br/>Pool: prefork<br/>Memory: 800MB"]
        W2["Worker 2<br/>Concurrency: 4<br/>Pool: prefork<br/>Memory: 800MB"]
        W3["Worker 3<br/>Concurrency: 4<br/>Pool: prefork<br/>Memory: 800MB"]
    end
    
    subgraph "Result Backend"
        REDIS_RESULT["Redis DB 2<br/>Result storage<br/>TTL: 24h"]
    end
    
    subgraph "Monitoring"
        FLOWER["Flower UI<br/>Port: 5555<br/>Features:<br/>- Task list<br/>- Worker status<br/>- Basic charts<br/>Memory: 100MB"]
    end

    BEAT --> REDIS_BROKER
    REDIS_BROKER --> W1
    REDIS_BROKER --> W2
    REDIS_BROKER --> W3
    
    W1 --> REDIS_RESULT
    W2 --> REDIS_RESULT
    W3 --> REDIS_RESULT
    
    W1 -.Monitor.-> FLOWER
    W2 -.Monitor.-> FLOWER
    W3 -.Monitor.-> FLOWER

    style BEAT fill:#ff6b6b
    style REDIS_BROKER fill:#dc244c
```

**Технические детали:**

```python
# Конфигурация Celery
CELERY_CONFIG = {
    'broker_url': 'redis://localhost:6379/1',
    'result_backend': 'redis://localhost:6379/2',
    'task_serializer': 'json',
    'result_serializer': 'json',
    'accept_content': ['json'],
    'timezone': 'UTC',
    'enable_utc': True,
    'task_track_started': True,
    'task_time_limit': 1800,  # 30 min
    'task_soft_time_limit': 1500,  # 25 min
    'worker_prefetch_multiplier': 1,
    'task_acks_late': True,
}

# Beat schedule
CELERYBEAT_SCHEDULE = {
    'retrain-models-daily': {
        'task': 'workers.ml_tasks.retrain_all_models',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'ml_heavy'}
    },
    # ... 4 more tasks
}
```

**Проблемы:**
```
❌ Зависимости между задачами - неочевидны
   retrain-models должен идти ПОСЛЕ update-feature-store
   но это не видно в коде
   
❌ Если retrain-models упадет в 2:05
   cleanup-old-experiments всё равно запустится в 1:00 (на след. день)
   даже если зависимые данные не готовы
   
❌ Flower UI показывает только текущие/недавние задачи
   нет истории за месяц
   нет Gantt chart
   нет SLA tracking
   
❌ Retry логика - глобальная
   нельзя настроить per-task без изменения кода
```

---

### Компонент 2: Workflow Orchestrator (TypeScript)

```mermaid
sequenceDiagram
    participant Client
    participant WF as Workflow Orchestrator
    participant DB as Supabase
    participant A1 as Architect Agent
    participant A2 as Developer Agent
    participant A3 as Consultant Agent

    Client->>WF: POST /workflow-orchestrator<br/>{user_task, demo_type}
    WF->>DB: Create demo record
    DB-->>WF: demo_id
    WF->>DB: Create 3 stages
    WF-->>Client: 202 Accepted {demo_id}
    
    Note over WF: Async processing starts
    
    WF->>DB: Update stage 1: processing
    WF->>A1: Call analyze-task
    A1-->>WF: analysis_result
    WF->>DB: Update stage 1: completed
    
    WF->>DB: Update stage 2: processing
    WF->>A2: Call develop-solution<br/>(with analysis_result)
    A2-->>WF: solution_result
    WF->>DB: Update stage 2: completed
    
    WF->>DB: Update stage 3: processing
    WF->>A3: Call provide-consultation<br/>(with solution_result)
    A3-->>WF: consultation_result
    WF->>DB: Update stage 3: completed
    
    WF->>DB: Update demo: completed<br/>progress: 100%
```

**Код:**
```typescript
async function processWorkflow(demoId, userTask, stages) {
    // Hardcoded последовательность
    analysisResult = await callAgent('analyze-task', {...});
    solutionResult = await callAgent('develop-solution', {
        analysis: analysisResult  // Передаем результат предыдущего
    });
    await callAgent('provide-consultation', {
        solution: solutionResult
    });
}
```

**Проблемы:**
```
❌ Hardcoded порядок (1→2→3)
   Невозможно: параллельное выполнение, conditional branches
   
❌ Нет retry на уровне отдельных агентов
   Если Developer Agent упал - весь workflow падает
   
❌ Нет визуализации
   Можно увидеть только через БД (demo_stages)
   
❌ Нет scheduling
   Запускается только вручную
   
❌ Масштабирование - сложное
   Все агенты в одном процессе
```

---

### Компонент 3: AI Orchestrator (Real-time Routing)

```mermaid
graph LR
    REQ[User Request] --> CLASS[Query Classifier]
    
    CLASS --> ROUTE{Route Decision}
    
    ROUTE -->|Code Gen| QWEN[Qwen3-Coder]
    ROUTE -->|Search| QDRANT[Qdrant Search]
    ROUTE -->|Graph| NEO4J[Neo4j Query]
    ROUTE -->|Analysis| GPT4[OpenAI GPT-4]
    
    QWEN --> RESP[Response]
    QDRANT --> RESP
    NEO4J --> RESP
    GPT4 --> RESP

    style CLASS fill:#00d4aa
    style ROUTE fill:#ff6b6b
```

**Это НЕ workflow orchestration** - это intelligent routing для real-time запросов.

**Airflow здесь НЕ нужен** - это синхронный процесс (<2s latency требуется).

---

### Компонент 4: Background Jobs (PostgreSQL Queue)

```mermaid
graph TB
    APP[FastAPI App] -->|Insert| QUEUE[(background_jobs table)]
    
    QUEUE -->|Poll every 5s| WORKER[Background Worker<br/>Python script]
    
    WORKER -->|Update status| QUEUE
    
    WORKER --> EXEC[Execute Job:<br/>- Export data<br/>- Send email<br/>- Generate report]
    
    EXEC -->|Success| QUEUE
    EXEC -->|Error| RETRY{Retry?}
    
    RETRY -->|Yes, retry_count < 3| QUEUE
    RETRY -->|No| FAILED[Mark as failed]

    style QUEUE fill:#336791
    style WORKER fill:#ff6b6b
```

**Код:**
```sql
-- Простая очередь в PostgreSQL
CREATE TABLE background_jobs (
    id UUID PRIMARY KEY,
    job_type VARCHAR(100),
    status VARCHAR(50) DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    ...
);

-- Worker poll
SELECT * FROM background_jobs 
WHERE status = 'pending' 
  AND (next_retry_at IS NULL OR next_retry_at < NOW())
ORDER BY created_at
LIMIT 10
FOR UPDATE SKIP LOCKED;
```

**Проблемы:**
```
❌ Polling каждые 5 секунд (неэффективно)
❌ Нет приоритетов задач
❌ Нет распределенного выполнения
❌ Ручной retry механизм
❌ Нет мониторинга задач
```

---

## 🆚 Airflow Architecture (TO-BE)

### Полная архитектура Apache Airflow

```mermaid
graph TB
    subgraph "Airflow Components"
        WEBSERVER["Airflow Webserver<br/>Port: 8080<br/>Flask app<br/>Memory: 500MB<br/>Features:<br/>- DAG visualization<br/>- Task logs<br/>- Graph view<br/>- Gantt chart<br/>- SLA monitoring"]
        
        SCHEDULER["Airflow Scheduler<br/>Process: daemon<br/>Memory: 300MB<br/>Functions:<br/>- Parse DAG files<br/>- Schedule tasks<br/>- Trigger execution<br/>- SLA checks<br/>Poll interval: 5s"]
        
        EXECUTOR{{"Executor<br/>(CeleryExecutor)"}}
        
        METADATA[(PostgreSQL<br/>Airflow Metadata DB<br/>Tables:<br/>- dag<br/>- dag_run<br/>- task_instance<br/>- task_fail<br/>- sla_miss<br/>- log<br/>- xcom<br/>~30 tables total)]
    end
    
    subgraph "Task Execution Layer"
        BROKER["Redis/RabbitMQ<br/>Task Queue<br/>Queues:<br/>- default<br/>- ml_heavy<br/>- ml_light<br/>- data_sync"]
        
        WORKER1["Celery Worker 1<br/>Queue: ml_heavy<br/>Concurrency: 2<br/>Memory: 2GB"]
        WORKER2["Celery Worker 2<br/>Queue: ml_light<br/>Concurrency: 8<br/>Memory: 1GB"]
        WORKER3["Celery Worker 3<br/>Queue: data_sync<br/>Concurrency: 4<br/>Memory: 512MB"]
    end
    
    subgraph "DAG Storage"
        DAGS["DAG Files<br/>Path: /dags/<br/>Files:<br/>- ml_training_pipeline.py<br/>- data_sync_pipeline.py<br/>- maintenance_pipeline.py<br/>Auto-discovery<br/>Scan interval: 30s"]
    end
    
    subgraph "Logs & XCom"
        LOGS["Task Logs<br/>Storage: S3/Local<br/>Retention: 30 days"]
        XCOM["XCom (data passing)<br/>Storage: Metadata DB<br/>Max size: 48KB"]
    end

    SCHEDULER --> METADATA
    SCHEDULER --> DAGS
    SCHEDULER --> EXECUTOR
    
    EXECUTOR --> BROKER
    BROKER --> WORKER1
    BROKER --> WORKER2
    BROKER --> WORKER3
    
    WORKER1 --> METADATA
    WORKER2 --> METADATA
    WORKER3 --> METADATA
    
    WORKER1 --> LOGS
    WORKER1 --> XCOM
    
    WEBSERVER --> METADATA
    WEBSERVER --> LOGS

    style SCHEDULER fill:#ff6b6b
    style WEBSERVER fill:#00d4aa
    style METADATA fill:#336791
```

**Технические детали:**

```python
# airflow.cfg
[core]
dags_folder = /opt/airflow/dags
executor = CeleryExecutor
sql_alchemy_conn = postgresql+psycopg2://airflow:***@postgres:5432/airflow
parallelism = 32  # Max parallel tasks globally
max_active_runs_per_dag = 16
load_examples = False

[scheduler]
scheduler_heartbeat_sec = 5
min_file_process_interval = 30  # Scan DAG folder
dag_dir_list_interval = 300

[celery]
broker_url = redis://redis:6379/0
result_backend = db+postgresql://airflow:***@postgres:5432/airflow
worker_concurrency = 16
worker_prefetch_multiplier = 1

[webserver]
web_server_port = 8080
workers = 4  # Gunicorn workers
worker_class = sync
expose_config = False
authenticate = True
auth_backend = airflow.contrib.auth.backends.password_auth

[logging]
base_log_folder = /opt/airflow/logs
remote_logging = True
remote_base_log_folder = s3://airflow-logs/
logging_level = INFO
```

---

## 🔄 Детальное сравнение конкретных workflow

### ML Training Pipeline

#### Текущая реализация (Celery):

```python
# src/workers/ml_tasks.py

@celery_app.task(
    name='workers.ml_tasks.retrain_all_models',
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def retrain_all_models(self):
    """Переобучить все модели"""
    try:
        # 1. Update feature store (нужно вызвать вручную или надеяться что отработал)
        # 2. Load data
        training_data = load_training_data()
        
        # 3. Train each model
        models = ['classifier_v1', 'regressor_v1', 'embeddings_v1']
        for model_name in models:
            train_single_model(model_name, training_data)
        
        # 4. Evaluate (где гарантия что training завершен успешно?)
        
        # 5. Log to MLflow
        
        return {'status': 'success', 'models_trained': len(models)}
    except Exception as e:
        self.retry(exc=e)
```

**Проблемы:**
```
❌ Все модели обучаются последовательно (медленно!)
   classifier_v1: 15 min
   regressor_v1: 20 min
   embeddings_v1: 10 min
   TOTAL: 45 минут вместо возможных 20 (если параллельно)

❌ Если одна модель упала - retry всех
   Нужно переобучать все 3 модели заново

❌ Нет visibility какая модель сейчас обучается
   Видно только "retrain_all_models: RUNNING"

❌ Зависимости неявные
   retrain_all_models зависит от update_feature_store
   но в коде это не отражено
```

---

#### Эквивалент в Airflow:

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.branch import BranchPythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

with DAG(
    'ml_training_pipeline_v2',
    default_args={
        'owner': '1c-ai-ml-team',
        'depends_on_past': True,  # Не запускать если предыдущий run не успешен
        'email': ['ml-team@1c-ai.dev'],
        'email_on_failure': True,
        'email_on_retry': False,
        'retries': 3,
        'retry_delay': timedelta(minutes=5),
        'execution_timeout': timedelta(hours=2),
    },
    description='ML Training Pipeline with parallel model training',
    schedule_interval='0 2 * * *',  # Daily at 2:00 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,  # Только один active run
    tags=['ml', 'training', 'production'],
) as dag:

    # Sensor: Wait for feature store update (if needed)
    wait_for_features = ExternalTaskSensor(
        task_id='wait_for_feature_update',
        external_dag_id='feature_store_update',
        external_task_id='update_complete',
        timeout=3600,  # 1 hour
        poke_interval=60,  # Check every minute
    )
    
    # Task: Load and prepare data
    prepare_data = PythonOperator(
        task_id='prepare_training_data',
        python_callable=load_and_prepare_data,
        pool='data_processing',  # Resource pool
    )
    
    # Task: Validate data quality
    validate_data = PythonOperator(
        task_id='validate_data_quality',
        python_callable=validate_data_quality,
    )
    
    # Branch: Choose models to train based on drift detection
    def choose_models_to_train(**context):
        drift_check = context['ti'].xcom_pull(task_ids='check_model_drift')
        if drift_check['high_drift']:
            return ['train_classifier', 'train_regressor', 'train_embeddings']
        elif drift_check['medium_drift']:
            return ['train_classifier', 'train_regressor']
        else:
            return ['skip_training']
    
    branch_training = BranchPythonOperator(
        task_id='decide_which_models',
        python_callable=choose_models_to_train,
    )
    
    # PARALLEL Training tasks (ключевое отличие!)
    train_classifier = PythonOperator(
        task_id='train_classifier',
        python_callable=train_classifier_model,
        pool='ml_training',
        pool_slots=2,  # Занимает 2 слота из pool
        execution_timeout=timedelta(minutes=30),
    )
    
    train_regressor = PythonOperator(
        task_id='train_regressor',
        python_callable=train_regressor_model,
        pool='ml_training',
        pool_slots=2,
        execution_timeout=timedelta(minutes=30),
    )
    
    train_embeddings = PythonOperator(
        task_id='train_embeddings',
        python_callable=train_embeddings_model,
        pool='ml_training',
        pool_slots=1,
        execution_timeout=timedelta(minutes=20),
    )
    
    skip_training = PythonOperator(
        task_id='skip_training',
        python_callable=lambda: print("No training needed")
    )
    
    # Evaluation tasks (после обучения)
    evaluate_all = PythonOperator(
        task_id='evaluate_all_models',
        python_callable=evaluate_models,
        trigger_rule='none_failed',  # Запустить если хотя бы одна модель обучена
    )
    
    # Model registry update
    update_registry = PythonOperator(
        task_id='update_model_registry',
        python_callable=update_mlflow_registry,
    )
    
    # Cleanup
    cleanup = PythonOperator(
        task_id='cleanup_old_experiments',
        python_callable=cleanup_experiments,
        trigger_rule='all_done',  # Всегда запускать, даже если были ошибки
    )
    
    # Send notification
    notify = PythonOperator(
        task_id='send_slack_notification',
        python_callable=send_notification,
        trigger_rule='all_done',
    )

    # DAG Dependencies (визуально видно!)
    wait_for_features >> prepare_data >> validate_data >> branch_training
    
    branch_training >> [train_classifier, train_regressor, train_embeddings, skip_training]
    
    [train_classifier, train_regressor, train_embeddings] >> evaluate_all
    skip_training >> notify
    
    evaluate_all >> update_registry >> cleanup >> notify
```

**Преимущества Airflow версии:**

```
✅ Параллельное обучение моделей
   classifier + regressor + embeddings = ОДНОВРЕМЕННО
   Время: 45 min → 20 min (экономия 55%!)

✅ Conditional execution
   Обучаем только те модели где есть drift
   
✅ Explicit dependencies
   Видно на графе что от чего зависит
   
✅ Smart retry
   Если classifier упал - retry только его
   regressor и embeddings продолжают
   
✅ Visibility в UI
   Видно какая модель сейчас обучается
   Сколько времени прошло
   Когда ожидается завершение
   
✅ Resource management
   Pools предотвращают перегрузку
   
✅ Trigger rules
   cleanup запустится ВСЕГДА
   evaluate только если хотя бы 1 модель готова
```

---

## 📊 Side-by-Side Comparison: Конкретный пример

### Сценарий: Ежедневный ML Pipeline

**Задачи:**
1. Update feature store (10 min)
2. Check model drift (5 min)
3. Train 3 models (15+20+10 = 45 min sequential, 20 min parallel)
4. Evaluate models (10 min)
5. Update registry (2 min)
6. Cleanup old experiments (5 min)

---

#### Celery (текущее):

**Время выполнения:**
```
02:00 - retrain-models-daily starts
  02:00-02:10 - update_feature_store (в другой задаче, надеемся что отработала)
  02:10-02:15 - check_model_drift (в другой задаче)
  02:15-02:30 - train classifier
  02:30-02:50 - train regressor
  02:50-03:00 - train embeddings
  03:00-03:10 - evaluate
  03:10-03:12 - update registry
  03:12-03:17 - cleanup (в отдельной задаче в 1:00, но вчерашние данные!)

TOTAL: ~1 час 17 минут
```

**Проблемы:**
- Задачи разбросаны по времени
- Зависимости неявные
- Cleanup не синхронизирован
- Если что-то упало - неясно что делать

**Мониторинг:**
```
Flower UI:
  retrain-models-daily: SUCCESS (took 1h 17m)
  
Что произошло внутри? Неизвестно без логов!
```

---

#### Airflow (предлагаемое):

**Время выполнения:**
```
02:00 - ml_training_pipeline DAG triggered

02:00-02:10 - [wait_for_features] Sensor wait
02:10-02:15 - [prepare_data] Load data
02:15-02:20 - [validate_data] Validate
02:20-02:22 - [decide_which_models] Check drift → train all 3

02:22-02:42 - PARALLEL execution:
              [train_classifier] - 20 min
              [train_regressor]  - 20 min
              [train_embeddings] - 10 min (завершился раньше)

02:42-02:52 - [evaluate_all_models] - 10 min
02:52-02:54 - [update_registry] - 2 min
02:54-02:59 - [cleanup] - 5 min
02:59-03:00 - [notify] - 1 min

TOTAL: 1 час (вместо 1h 17m)
Экономия: 17 минут (22%!)
```

**Мониторинг в UI:**
```
Airflow UI:
  DAG: ml_training_pipeline
  Run: 2024-11-05 02:00:00
  Status: SUCCESS
  Duration: 1h 0m
  
  Tasks (10):
    ✅ wait_for_features (10m)
    ✅ prepare_data (5m)
    ✅ validate_data (5m)
    ✅ decide_which_models (2m)
    ✅ train_classifier (20m) ← PARALLEL
    ✅ train_regressor (20m)  ← PARALLEL
    ✅ train_embeddings (10m) ← PARALLEL
    ✅ evaluate_all_models (10m)
    ✅ update_registry (2m)
    ✅ cleanup (5m)
    ✅ notify (1m)
  
  Gantt Chart: [визуализация когда что выполнялось]
  Graph View: [граф зависимостей с цветами]
  Logs: [клик на любой task → логи]
```

---

## 📈 Конкретные примеры DAG'ов для проекта

### DAG 1: Data Sync Pipeline (новый!)

**Проблема:** Сейчас нет автоматической синхронизации данных между БД.

**Решение с Airflow:**

```python
with DAG(
    'data_sync_1c_to_all_dbs',
    schedule_interval='0 */6 * * *',  # Every 6 hours
    start_date=datetime(2024, 1, 1),
) as dag:

    # Extract from 1C configurations
    extract_1c = PythonOperator(
        task_id='extract_1c_metadata',
        python_callable=extract_from_1c_configs,
    )
    
    # Transform
    transform = PythonOperator(
        task_id='transform_metadata',
        python_callable=transform_metadata_func,
    )
    
    # Load to PostgreSQL
    load_postgres = PostgresOperator(
        task_id='load_to_postgres',
        postgres_conn_id='postgres_1c_ai',
        sql="""
            INSERT INTO metadata (name, type, properties)
            SELECT * FROM temp_metadata
            ON CONFLICT (id) DO UPDATE SET ...
        """
    )
    
    # PARALLEL: Load to graph and vector stores
    load_neo4j = PythonOperator(
        task_id='sync_to_neo4j',
        python_callable=sync_postgres_to_neo4j,
    )
    
    vectorize_qdrant = PythonOperator(
        task_id='vectorize_to_qdrant',
        python_callable=vectorize_and_load_qdrant,
    )
    
    index_elasticsearch = PythonOperator(
        task_id='index_to_elasticsearch',
        python_callable=index_to_elasticsearch,
    )
    
    # Validation
    validate_sync = PythonOperator(
        task_id='validate_sync_integrity',
        python_callable=validate_data_integrity,
    )
    
    # Dependencies
    extract_1c >> transform >> load_postgres
    load_postgres >> [load_neo4j, vectorize_qdrant, index_elasticsearch]
    [load_neo4j, vectorize_qdrant, index_elasticsearch] >> validate_sync
```

**Визуализация в Airflow UI:**
```
extract_1c → transform → load_postgres → ┬─→ load_neo4j ────────┐
                                          ├─→ vectorize_qdrant ──┼─→ validate_sync
                                          └─→ index_elasticsearch┘
```

**Выгоды:**
- ✅ Параллельная загрузка в 3 БД (экономия времени!)
- ✅ Видно на графе весь процесс
- ✅ Если Neo4j упал - Qdrant и ES продолжают
- ✅ Validation гарантирует целостность данных

---

### DAG 2: BSL Dataset Preparation

**Проблема:** Сейчас датасет готовится вручную скриптом.

**Решение с Airflow:**

```python
with DAG(
    'bsl_dataset_preparation',
    schedule_interval='0 0 * * 0',  # Weekly on Sunday
    start_date=datetime(2024, 1, 1),
) as dag:

    # Fetch from multiple sources (PARALLEL!)
    fetch_postgres = PythonOperator(
        task_id='fetch_from_postgres',
        python_callable=fetch_bsl_from_postgres,
    )
    
    fetch_github = PythonOperator(
        task_id='fetch_from_github',
        python_callable=fetch_bsl_from_github_repos,
        execution_timeout=timedelta(hours=2),
    )
    
    fetch_its = PythonOperator(
        task_id='fetch_from_its_library',
        python_callable=fetch_bsl_from_its,
        execution_timeout=timedelta(hours=1),
    )
    
    # Merge and deduplicate
    merge_datasets = PythonOperator(
        task_id='merge_and_deduplicate',
        python_callable=merge_all_sources,
        trigger_rule='none_failed',  # Даже если GitHub упал
    )
    
    # Quality filtering
    filter_quality = PythonOperator(
        task_id='filter_low_quality',
        python_callable=filter_by_quality_score,
    )
    
    # Split train/val/test
    split_dataset = PythonOperator(
        task_id='split_dataset',
        python_callable=split_train_val_test,
    )
    
    # PARALLEL: Save in different formats
    save_jsonl = PythonOperator(
        task_id='save_as_jsonl',
        python_callable=save_jsonl_format,
    )
    
    save_parquet = PythonOperator(
        task_id='save_as_parquet',
        python_callable=save_parquet_format,
    )
    
    # Upload to dataset storage
    upload = PythonOperator(
        task_id='upload_to_huggingface',
        python_callable=upload_to_hf_hub,
    )
    
    # Validate dataset
    validate = PythonOperator(
        task_id='validate_dataset_quality',
        python_callable=validate_final_dataset,
    )
    
    # Dependencies
    [fetch_postgres, fetch_github, fetch_its] >> merge_datasets
    merge_datasets >> filter_quality >> split_dataset
    split_dataset >> [save_jsonl, save_parquet]
    [save_jsonl, save_parquet] >> upload >> validate
```

**Время выполнения:**
```
Celery (sequential):
  fetch_postgres: 30 min
  fetch_github: 120 min
  fetch_its: 60 min
  merge: 15 min
  filter: 10 min
  split: 5 min
  save: 20 min
  upload: 30 min
  TOTAL: 290 min (4.8 hours)

Airflow (parallel):
  [fetch_postgres + fetch_github + fetch_its]: 120 min (longest)
  merge: 15 min
  filter: 10 min
  split: 5 min
  [save_jsonl + save_parquet]: 20 min (parallel)
  upload: 30 min
  validate: 5 min
  TOTAL: 205 min (3.4 hours)
  
ЭКОНОМИЯ: 85 минут (29%!)
```

---

### DAG 3: System Maintenance

```python
with DAG(
    'system_maintenance',
    schedule_interval='0 1 * * *',  # Daily at 1:00 AM
    start_date=datetime(2024, 1, 1),
) as dag:

    # Database maintenance (PARALLEL для каждой БД)
    vacuum_postgres = PostgresOperator(
        task_id='vacuum_postgres',
        postgres_conn_id='postgres_1c_ai',
        sql='VACUUM ANALYZE; REINDEX DATABASE 1c_ai_stack;'
    )
    
    cleanup_neo4j = PythonOperator(
        task_id='cleanup_neo4j_orphans',
        python_callable=cleanup_neo4j_orphaned_nodes,
    )
    
    optimize_qdrant = PythonOperator(
        task_id='optimize_qdrant_collections',
        python_callable=optimize_qdrant_indexes,
    )
    
    # Cache cleanup
    cleanup_redis = PythonOperator(
        task_id='cleanup_redis_cache',
        python_callable=cleanup_old_cache_keys,
    )
    
    # Log cleanup (удаление старых логов)
    cleanup_logs = PythonOperator(
        task_id='cleanup_old_logs',
        python_callable=delete_logs_older_than_30_days,
    )
    
    # Health check после maintenance
    health_check = PythonOperator(
        task_id='system_health_check',
        python_callable=comprehensive_health_check,
        trigger_rule='all_done',
    )
    
    # Alert if health check failed
    alert_on_failure = PythonOperator(
        task_id='alert_if_unhealthy',
        python_callable=send_alert_to_oncall,
        trigger_rule='one_failed',  # Если хотя бы одна задача упала
    )
    
    # Dependencies
    [vacuum_postgres, cleanup_neo4j, optimize_qdrant, cleanup_redis, cleanup_logs] >> health_check
    health_check >> alert_on_failure
```

**Визуализация в Airflow:**
```
vacuum_postgres ────┐
cleanup_neo4j ──────┤
optimize_qdrant ────┼─→ health_check ─→ alert_on_failure
cleanup_redis ──────┤
cleanup_logs ───────┘

[Все 5 задач параллельно] → [Health check] → [Alert если нужно]
```

---

## 🎨 Airflow UI Features (чего нет в Celery)

### 1. DAG Graph View

```
┌─────────────────────────────────────────────────────┐
│ DAG: ml_training_pipeline                           │
│ Status: ✅ Success  Duration: 1h 0m  Next: Tomorrow │
├─────────────────────────────────────────────────────┤
│                                                     │
│     wait_for_features                               │
│           ↓                                         │
│     prepare_data                                    │
│           ↓                                         │
│     validate_data                                   │
│           ↓                                         │
│     decide_which_models                             │
│           ↓                                         │
│     ┌─────┴──────┬──────────┐                      │
│     ↓            ↓           ↓                      │
│  train_class  train_reg  train_emb                 │
│     └─────┬──────┴──────────┘                      │
│           ↓                                         │
│     evaluate_all                                    │
│           ↓                                         │
│     update_registry                                 │
│           ↓                                         │
│     cleanup                                         │
│           ↓                                         │
│     notify                                          │
│                                                     │
│ Colors:                                             │
│ 🟢 Success  🔴 Failed  🟡 Running  ⚪ Not started  │
└─────────────────────────────────────────────────────┘
```

### 2. Gantt Chart

```
Task                 |00:00|01:00|02:00|03:00|
---------------------|-----|-----|-----|-----|
wait_for_features    |█████|     |     |     |
prepare_data         |     |████ |     |     |
validate_data        |     | ████|     |     |
train_classifier     |     |     |█████|█████|
train_regressor      |     |     |█████|█████|
train_embeddings     |     |     |█████|     |
evaluate_all         |     |     |     |████ |
cleanup              |     |     |     | ███ |

Легко видеть:
- Где параллелизм
- Где bottleneck'и
- Сколько времени занял каждый task
```

### 3. Task Instance Details

```
┌─────────────────────────────────────────┐
│ Task: train_classifier                  │
│ Run: 2024-11-05 02:22:00               │
├─────────────────────────────────────────┤
│ Status: ✅ Success                      │
│ Duration: 19m 43s                       │
│ Try Number: 1 / 3                       │
│ Queue: ml_heavy                         │
│ Pool: ml_training (2/10 slots used)    │
│ Executor: CeleryExecutor                │
│ Hostname: celery-worker-2               │
│ PID: 42351                              │
│                                         │
│ XCom Values:                            │
│   model_path: /models/classifier_v1.pkl │
│   accuracy: 0.9234                      │
│   training_samples: 10000               │
│                                         │
│ Logs: [Full Task Log ↓]                │
│ 2024-11-05 02:22:00 - INFO - Starting  │
│ 2024-11-05 02:25:00 - INFO - Epoch 1/10│
│ ...                                     │
└─────────────────────────────────────────┘
```

Celery Flower такого НЕ показывает!

---

## 💻 Примеры кода: Миграция с Celery на Airflow

### Before (Celery):

```python
# src/workers/ml_tasks.py

@celery_app.task(bind=True, max_retries=3)
def retrain_all_models(self):
    """Переобучить все модели"""
    try:
        models = ['classifier', 'regressor', 'embeddings']
        results = []
        
        for model_name in models:
            result = train_single_model(model_name)
            results.append(result)
        
        return {'status': 'success', 'models': results}
    except Exception as e:
        self.retry(exc=e, countdown=300)

# Как это запланировано?
beat_schedule = {
    'retrain-models-daily': {
        'task': 'workers.ml_tasks.retrain_all_models',
        'schedule': crontab(hour=2, minute=0),
    }
}
```

**Проблемы:**
- Все модели тренируются последовательно
- Нет визуального представления
- Retry всех моделей если одна упала

---

### After (Airflow):

```python
# dags/ml_training_pipeline.py

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime, timedelta

# DAG definition
with DAG(
    'ml_training_pipeline',
    default_args={
        'owner': 'ml-team',
        'retries': 3,
        'retry_delay': timedelta(minutes=5),
    },
    description='ML models retraining pipeline',
    schedule_interval='0 2 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['ml', 'training'],
) as dag:

    # Task functions
    def train_classifier_func(**context):
        """Train classifier model"""
        from ml.training.trainer import ModelTrainer
        
        trainer = ModelTrainer()
        result = trainer.train('classifier_v1')
        
        # Push result to XCom (for next tasks)
        context['ti'].xcom_push(key='model_path', value=result['path'])
        context['ti'].xcom_push(key='accuracy', value=result['accuracy'])
        
        return result
    
    def train_regressor_func(**context):
        """Train regressor model"""
        # Similar logic
        pass
    
    def train_embeddings_func(**context):
        """Train embeddings model"""
        # Similar logic
        pass
    
    def evaluate_all_func(**context):
        """Evaluate all trained models"""
        # Pull results from previous tasks
        ti = context['ti']
        classifier_acc = ti.xcom_pull(task_ids='train_classifier', key='accuracy')
        regressor_acc = ti.xcom_pull(task_ids='train_regressor', key='accuracy')
        embeddings_acc = ti.xcom_pull(task_ids='train_embeddings', key='accuracy')
        
        return {
            'classifier': classifier_acc,
            'regressor': regressor_acc,
            'embeddings': embeddings_acc
        }
    
    # Define tasks
    train_classifier = PythonOperator(
        task_id='train_classifier',
        python_callable=train_classifier_func,
        pool='ml_training',
    )
    
    train_regressor = PythonOperator(
        task_id='train_regressor',
        python_callable=train_regressor_func,
        pool='ml_training',
    )
    
    train_embeddings = PythonOperator(
        task_id='train_embeddings',
        python_callable=train_embeddings_func,
        pool='ml_training',
    )
    
    evaluate = PythonOperator(
        task_id='evaluate_all_models',
        python_callable=evaluate_all_func,
        trigger_rule='none_failed',
    )
    
    # Update model registry in PostgreSQL
    update_registry = PostgresOperator(
        task_id='update_model_registry',
        postgres_conn_id='postgres_1c_ai',
        sql="""
            INSERT INTO ml.model_registry (model_name, version, accuracy, path)
            VALUES 
                ('classifier_v1', '{{ ds }}', {{ ti.xcom_pull(task_ids='train_classifier', key='accuracy') }}, '...'),
                ('regressor_v1', '{{ ds }}', {{ ti.xcom_pull(task_ids='train_regressor', key='accuracy') }}, '...'),
                ('embeddings_v1', '{{ ds }}', {{ ti.xcom_pull(task_ids='train_embeddings', key='accuracy') }}, '...')
        """
    )
    
    # Dependencies
    [train_classifier, train_regressor, train_embeddings] >> evaluate >> update_registry
```

**Преимущества:**
```
✅ Параллельное обучение: 45 min → 20 min
✅ Видно на графе что параллельно
✅ XCom передает данные между tasks
✅ Templating в SQL ({{ ti.xcom_pull(...) }})
✅ Каждая модель - отдельный task с логами
✅ Retry индивидуальный
```

---

## 📊 Resource Comparison

### Memory Usage

| Component | Celery (Current) | Airflow | Разница |
|-----------|------------------|---------|---------|
| Scheduler | 50MB (Beat) | 300MB | +250MB |
| Web UI | 100MB (Flower) | 500MB | +400MB |
| Workers (3x) | 2.4GB | 2.4GB | 0 |
| Broker | 100MB (Redis) | 100MB (Redis) | 0 |
| Metadata DB | - | 200MB (PostgreSQL) | +200MB |
| **TOTAL** | **2.65GB** | **3.5GB** | **+850MB** |

### CPU Usage

| Component | Celery | Airflow | Разница |
|-----------|--------|---------|---------|
| Scheduler | 5-10% | 10-15% | +5-10% |
| Web UI | 2-5% | 5-10% | +3-5% |
| Workers | 50-90% (when active) | 50-90% | 0 |
| **TOTAL** | **57-105%** | **65-115%** | **+8-10%** |

**Вывод:** +850MB RAM, +8-10% CPU - приемлемый overhead для функциональности.

---

## 🎯 Специфические возможности Airflow

### 1. Dynamic DAG Generation

**Сценарий:** Создать DAG для каждой 1C конфигурации автоматически

```python
# dags/dynamic_config_dags.py

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

# Читаем список конфигураций из БД
CONFIGURATIONS = [
    {'name': 'ERP', 'schedule': '0 2 * * *'},
    {'name': 'UT', 'schedule': '0 3 * * *'},
    {'name': 'ZUP', 'schedule': '0 4 * * *'},
]

# Генерируем DAG для каждой конфигурации
for config in CONFIGURATIONS:
    dag_id = f"sync_config_{config['name'].lower()}"
    
    with DAG(
        dag_id,
        schedule_interval=config['schedule'],
        start_date=datetime(2024, 1, 1),
        catchup=False,
    ) as dag:
        
        extract = PythonOperator(
            task_id='extract',
            python_callable=extract_config,
            op_kwargs={'config_name': config['name']},
        )
        
        sync = PythonOperator(
            task_id='sync_to_dbs',
            python_callable=sync_to_all_dbs,
        )
        
        extract >> sync
    
    # DAG автоматически регистрируется
    globals()[dag_id] = dag
```

**Результат:** 3 DAG'а автоматически созданы!
- sync_config_erp
- sync_config_ut
- sync_config_zup

В Celery такое сделать сложно.

---

### 2. Sub-DAGs (Композиция workflow)

```python
# Переиспользуемый sub-DAG для обучения одной модели
from airflow.utils.task_group import TaskGroup

def create_model_training_group(model_name):
    with TaskGroup(f"train_{model_name}") as group:
        
        prepare = PythonOperator(
            task_id='prepare_data',
            python_callable=prepare_data_for_model,
            op_kwargs={'model': model_name}
        )
        
        train = PythonOperator(
            task_id='train',
            python_callable=train_model,
            op_kwargs={'model': model_name}
        )
        
        evaluate = PythonOperator(
            task_id='evaluate',
            python_callable=evaluate_model,
            op_kwargs={'model': model_name}
        )
        
        prepare >> train >> evaluate
        
        return group

# Использование в основном DAG
with DAG('ml_pipeline') as dag:
    start = DummyOperator(task_id='start')
    
    # 3 параллельных sub-DAG'а
    classifier_group = create_model_training_group('classifier')
    regressor_group = create_model_training_group('regressor')
    embeddings_group = create_model_training_group('embeddings')
    
    end = DummyOperator(task_id='end')
    
    start >> [classifier_group, regressor_group, embeddings_group] >> end
```

**Визуализация:**
```
start → ┬─→ [train_classifier: prepare → train → evaluate]
        ├─→ [train_regressor: prepare → train → evaluate]
        └─→ [train_embeddings: prepare → train → evaluate]
        → end
```

---

### 3. SLA Monitoring & Alerting

```python
with DAG(
    'ml_training_pipeline',
    default_args={
        'sla': timedelta(hours=2),  # Global SLA
    },
    sla_miss_callback=send_sla_miss_alert,
) as dag:

    train_classifier = PythonOperator(
        task_id='train_classifier',
        python_callable=train_func,
        sla=timedelta(minutes=30),  # Task-specific SLA
    )
```

**Если task превышает SLA:**
```
Alert в Slack:
⚠️ SLA MISS!
DAG: ml_training_pipeline
Task: train_classifier
Expected: 30 minutes
Actual: 35 minutes
Status: Still running
Action: Investigate why training is slow
```

В Celery такого нет!

---

### 4. Backfilling Historical Data

**Сценарий:** Нужно переобработать данные за последний месяц.

**Celery:**
```python
# Придется писать скрипт руками
for date in date_range(start='2024-10-01', end='2024-11-01'):
    retrain_all_models.apply_async(
        kwargs={'execution_date': date}
    )
# Сложно отследить прогресс
```

**Airflow:**
```bash
# One command!
airflow dags backfill \
    ml_training_pipeline \
    --start-date 2024-10-01 \
    --end-date 2024-11-01 \
    --reset-dagruns

# Airflow сам:
# - Создаст 31 DAG run (по одному на день)
# - Запустит последовательно или параллельно (depends_on_past)
# - Покажет прогресс в UI
# - Сохранит все результаты
```

---

### 5. Data Lineage Tracking

```python
# Airflow автоматически отслеживает откуда данные
from airflow.lineage import AUTO

with DAG('data_pipeline') as dag:
    
    extract = PythonOperator(
        task_id='extract',
        python_callable=extract_data,
        outlets=[Dataset('s3://raw-data/metadata.json')],  # Output
    )
    
    transform = PythonOperator(
        task_id='transform',
        python_callable=transform_data,
        inlets=[Dataset('s3://raw-data/metadata.json')],  # Input
        outlets=[Dataset('postgres://metadata')],  # Output
    )
```

**В UI видно:**
```
Data Lineage:
  s3://raw-data/metadata.json → [extract] → [transform] → postgres://metadata
  
  Last updated: 2024-11-05 02:00
  Consumers: [load_to_neo4j, vectorize_to_qdrant]
```

---

## 🔧 Практический пример: Full DAG для проекта

### Комплексный Data + ML Pipeline

```python
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.task_group import TaskGroup
from datetime import datetime, timedelta

default_args = {
    'owner': '1c-ai-team',
    'depends_on_past': False,
    'email': ['alerts@1c-ai.dev'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=3),
}

with DAG(
    'complete_ml_data_pipeline',
    default_args=default_args,
    description='Complete data sync and ML training pipeline for 1C AI Stack',
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=['production', 'ml', 'data-sync'],
    sla_miss_callback=send_sla_alert,
) as dag:

    # =====================================
    # PHASE 1: DATA EXTRACTION & PREPARATION
    # =====================================
    
    with TaskGroup('data_extraction') as extraction_group:
        
        extract_1c = PythonOperator(
            task_id='extract_1c_configs',
            python_callable=extract_from_1c_configurations,
            pool='data_extraction',
            sla=timedelta(minutes=30),
        )
        
        extract_github = PythonOperator(
            task_id='extract_github_repos',
            python_callable=fetch_from_github_api,
            pool='data_extraction',
            sla=timedelta(minutes=45),
        )
        
        extract_its = PythonOperator(
            task_id='extract_its_docs',
            python_callable=scrape_its_documentation,
            pool='data_extraction',
            sla=timedelta(minutes=60),
        )
        
        # Parallel extraction
        [extract_1c, extract_github, extract_its]
    
    # =====================================
    # PHASE 2: DATA TRANSFORMATION
    # =====================================
    
    merge_data = PythonOperator(
        task_id='merge_all_sources',
        python_callable=merge_and_deduplicate,
        trigger_rule='none_failed',  # Даже если GitHub не вернул данные
    )
    
    clean_data = PythonOperator(
        task_id='clean_and_validate',
        python_callable=clean_and_validate_data,
    )
    
    # Check data quality before proceeding
    def check_data_quality_func(**context):
        ti = context['ti']
        data = ti.xcom_pull(task_ids='clean_and_validate')
        
        if data['quality_score'] > 0.8:
            return 'proceed_to_sync'
        else:
            return 'send_quality_alert'
    
    quality_check = BranchPythonOperator(
        task_id='check_data_quality',
        python_callable=check_data_quality_func,
    )
    
    send_alert = PythonOperator(
        task_id='send_quality_alert',
        python_callable=send_low_quality_alert,
    )
    
    proceed = PythonOperator(
        task_id='proceed_to_sync',
        python_callable=lambda: print("Quality OK, proceeding"),
    )
    
    # =====================================
    # PHASE 3: DATABASE SYNCHRONIZATION (PARALLEL)
    # =====================================
    
    with TaskGroup('database_sync') as sync_group:
        
        sync_postgres = PostgresOperator(
            task_id='sync_to_postgres',
            postgres_conn_id='postgres_1c_ai',
            sql='sql/sync_metadata.sql',
            pool='database_writes',
        )
        
        sync_neo4j = PythonOperator(
            task_id='sync_to_neo4j',
            python_callable=sync_graph_database,
            pool='database_writes',
        )
        
        vectorize_qdrant = PythonOperator(
            task_id='vectorize_and_sync_qdrant',
            python_callable=vectorize_and_load_qdrant,
            pool='ml_inference',  # Требует GPU
            execution_timeout=timedelta(hours=1),
        )
        
        index_elasticsearch = PythonOperator(
            task_id='index_to_elasticsearch',
            python_callable=bulk_index_to_es,
            pool='database_writes',
        )
        
        # All in parallel
        [sync_postgres, sync_neo4j, vectorize_qdrant, index_elasticsearch]
    
    # =====================================
    # PHASE 4: DATA VALIDATION
    # =====================================
    
    validate_sync = PythonOperator(
        task_id='validate_data_integrity',
        python_callable=validate_cross_db_integrity,
        trigger_rule='none_failed',
    )
    
    # =====================================
    # PHASE 5: ML MODEL TRAINING (PARALLEL)
    # =====================================
    
    with TaskGroup('ml_training') as training_group:
        
        # Model 1: Classifier
        train_classifier = PythonOperator(
            task_id='train_classifier_model',
            python_callable=train_classifier_with_new_data,
            pool='ml_training',
            pool_slots=2,  # Занимает 2 слота
            execution_timeout=timedelta(minutes=30),
        )
        
        # Model 2: Regressor
        train_regressor = PythonOperator(
            task_id='train_regressor_model',
            python_callable=train_regressor_with_new_data,
            pool='ml_training',
            pool_slots=2,
            execution_timeout=timedelta(minutes=40),
        )
        
        # Model 3: Embeddings
        fine_tune_embeddings = PythonOperator(
            task_id='finetune_embeddings_model',
            python_callable=finetune_qwen_embeddings,
            pool='ml_training',
            pool_slots=3,  # Требует больше ресурсов
            execution_timeout=timedelta(hours=2),
        )
        
        [train_classifier, train_regressor, fine_tune_embeddings]
    
    # =====================================
    # PHASE 6: MODEL EVALUATION & DEPLOYMENT
    # =====================================
    
    evaluate_models = PythonOperator(
        task_id='evaluate_all_models',
        python_callable=comprehensive_model_evaluation,
        trigger_rule='none_failed',
    )
    
    def decide_deployment(**context):
        """Решить стоит ли деплоить новые модели"""
        ti = context['ti']
        eval_results = ti.xcom_pull(task_ids='evaluate_all_models')
        
        # Если accuracy улучшилась
        if eval_results['classifier']['accuracy'] > 0.90:
            return 'deploy_to_production'
        else:
            return 'keep_current_models'
    
    deployment_decision = BranchPythonOperator(
        task_id='decide_deployment',
        python_callable=decide_deployment,
    )
    
    deploy_production = PythonOperator(
        task_id='deploy_to_production',
        python_callable=deploy_models_to_prod,
    )
    
    keep_current = PythonOperator(
        task_id='keep_current_models',
        python_callable=lambda: print("Models not good enough, keeping current"),
    )
    
    # Update model registry (always)
    update_registry = PostgresOperator(
        task_id='update_model_registry',
        postgres_conn_id='postgres_1c_ai',
        sql='sql/update_model_registry.sql',
        trigger_rule='none_failed',
    )
    
    # =====================================
    # PHASE 7: CLEANUP & NOTIFICATION
    # =====================================
    
    cleanup = PythonOperator(
        task_id='cleanup_temp_files',
        python_callable=cleanup_training_artifacts,
        trigger_rule='all_done',  # Всегда, даже при ошибках
    )
    
    notify_team = PythonOperator(
        task_id='send_summary_to_slack',
        python_callable=send_pipeline_summary,
        trigger_rule='all_done',
    )

    # =====================================
    # DAG DEPENDENCIES
    # =====================================
    
    extraction_group >> merge_data >> clean_data >> quality_check
    quality_check >> [proceed, send_alert]
    
    proceed >> sync_group >> validate_sync >> training_group
    
    training_group >> evaluate_models >> deployment_decision
    deployment_decision >> [deploy_production, keep_current]
    
    [deploy_production, keep_current] >> update_registry >> cleanup >> notify_team
```

**Визуализация в Airflow UI:**

```
[Extraction Group: parallel extract_1c, extract_github, extract_its]
    ↓
merge_data
    ↓
clean_data
    ↓
check_data_quality → [proceed | send_alert]
    ↓
[Sync Group: parallel sync_postgres, sync_neo4j, vectorize_qdrant, index_es]
    ↓
validate_sync
    ↓
[Training Group: parallel train_classifier, train_regressor, fine_tune_embeddings]
    ↓
evaluate_models
    ↓
decide_deployment → [deploy_to_production | keep_current_models]
    ↓
update_registry
    ↓
cleanup
    ↓
notify_team
```

**Это НЕВОЗМОЖНО в Celery без написания custom orchestrator!**

---

## 💰 ROI Calculation

### Costs

**One-time:**
- Разработка: 60 часов × $50/час = $3,000
- Обучение команды: 20 часов × $50/час = $1,000
- Infrastructure setup: $500
**Total one-time: $4,500**

**Recurring:**
- Infrastructure: +850MB RAM ≈ +$5/месяц (cloud)
- Maintenance: 2 часа/месяц × $50/час = $100/месяц
**Total monthly: $105**

**Annual: $1,260** (первый год: $5,760)

---

### Benefits

**Time savings:**
- ML Pipeline: 45 min → 20 min = 25 min saved daily
  - 25 min × 365 days = 152 hours/year
  - 152 hours × $50/час = $7,600/year

- Data Sync: Новый функционал, раньше не было
  - Экономия времени разработчиков: ~10 hours/week
  - 10 hours × 52 weeks × $50/час = $26,000/year

- Debugging/Troubleshooting: -30% времени
  - Сейчас: ~5 hours/week
  - Экономия: 1.5 hours/week × 52 × $50 = $3,900/year

**Total annual savings: $37,500**

**ROI:** 
- Year 1: $37,500 - $5,760 = **$31,740 profit** (550% ROI!)
- Year 2+: $37,500 - $1,260 = **$36,240 profit** (2900% ROI!)

---

## ✅ Итоговые рекомендации

### Сравнительная таблица функциональности

| Функция | Celery | Airflow | Важность для проекта |
|---------|--------|---------|----------------------|
| Task scheduling | ✅ Beat | ✅ Scheduler | 🔴 Critical |
| Async execution | ✅ | ✅ | 🔴 Critical |
| Retry logic | ✅ Basic | ✅ Advanced | 🟡 High |
| Dependencies | ❌ Manual | ✅ DAG | 🔴 Critical |
| Parallel execution | ❌ Сложно | ✅ Easy | 🔴 Critical |
| UI visualization | ⚠️ Flower (basic) | ✅ Rich UI | 🟡 High |
| Logging | ⚠️ Scattered | ✅ Centralized | 🟡 High |
| Monitoring | ⚠️ External | ✅ Built-in | 🟡 High |
| SLA tracking | ❌ | ✅ | 🟢 Medium |
| Backfilling | ❌ | ✅ | 🟢 Medium |
| Data lineage | ❌ | ✅ | 🟢 Medium |
| Conditional logic | ❌ | ✅ | 🔴 Critical |
| Resource pools | ❌ | ✅ | 🟡 High |
| XCom (data passing) | ❌ | ✅ | 🟡 High |
| Testing utilities | ⚠️ Basic | ✅ Advanced | 🟢 Medium |

**Оценка критичности:**
- 🔴 Critical (5): **Airflow wins 4/5**
- 🟡 High (6): **Airflow wins 6/6**
- 🟢 Medium (4): **Airflow wins 4/4**

**Вердикт:** Airflow значительно превосходит Celery для workflow orchestration

---

### Рекомендация: ВНЕДРЯТЬ AIRFLOW

**Почему:**
1. ✅ **Экономия времени** - параллелизм сокращает ML pipeline на 55%
2. ✅ **Видимость** - визуализация всех workflow
3. ✅ **Надежность** - лучший retry, dependencies, validation
4. ✅ **Масштабируемость** - легко добавлять новые pipeline'ы
5. ✅ **ROI** - окупается за 2 месяца

**Как внедрять:**
1. **Phase 1 (2 недели):** Setup Airflow, базовый DAG
2. **Phase 2 (3 недели):** Миграция ML pipeline с Celery
3. **Phase 3 (2 недели):** Новые DAG'и (Data Sync, Maintenance)
4. **Phase 4 (ongoing):** Оптимизация и новые pipeline'ы

**Timeline:** 2 месяца до production

**Effort:** ~80 часов разработки

**Payback period:** 2 месяца

---

### Альтернативы (если не хотим Airflow)

1. **Prefect** - современная альтернатива Airflow
   - Проще в использовании
   - Лучше для dynamic workflows
   - Меньше overhead
   - Но менее mature

2. **Temporal** - для distributed workflows
   - Очень мощный
   - Хорош для microservices
   - Более сложный

3. **Dagster** - data orchestration
   - Ориентирован на data assets
   - Хорош для ML/Data teams
   - Новый, но перспективный

4. **Оставить Celery + улучшить мониторинг**
   - Добавить custom dashboard
   - Улучшить логирование
   - Добавить dependency tracking
   - Но это фактически писать "свой Airflow"

**Вывод:** Apache Airflow - лучший выбор по соотношению зрелость/функциональность/community

---

## 📝 Финальные выводы

### Что у нас есть сейчас:

```
✅ Celery - работает, но limited
✅ Workflow Orchestrator (TS) - hardcoded, не масштабируется
✅ AI Orchestrator - хорош для real-time routing (оставить)
✅ Background Jobs - примитивная очередь
```

### Что будет с Airflow:

```
✅ Apache Airflow - единая система для batch workflows
✅ AI Orchestrator - для real-time (оставить как есть!)
✅ Celery Workers - используются внутри Airflow (CeleryExecutor)
❌ Workflow Orchestrator (TS) - заменить на Airflow DAG
❌ Background Jobs - заменить на Airflow DAG
```

### Hybrid Architecture (рекомендуется):

```
┌─────────────────────────────────────────┐
│     Apache Airflow (Batch Workflows)    │
│                                         │
│  - ML Training Pipeline                 │
│  - Data Sync Pipeline                   │
│  - Maintenance Pipeline                 │
│  - BSL Dataset Preparation              │
│                                         │
│  Uses: CeleryExecutor                   │
│     ↓                                   │
│  Celery Workers (for heavy ML tasks)    │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│   AI Orchestrator (Real-time Routing)   │
│                                         │
│  - User queries (<2s latency)           │
│  - Code generation                      │
│  - Semantic search                      │
│  - Telegram bot responses               │
│                                         │
│  Direct calls to AI services            │
└─────────────────────────────────────────┘
```

**Каждый для своей задачи!**

---

**Статус:** Аналитический документ  
**Рекомендация:** ✅ Внедрять Apache Airflow для batch workflows  
**Приоритет:** 🟡 High (не критично, но очень полезно)  
**Timeline:** 2 месяца  
**ROI:** 550% в первый год

