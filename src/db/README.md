# Database Clients

Утилиты доступа к хранилищам данных: PostgreSQL, Neo4j, Qdrant, Elasticsearch.

| Модуль | Назначение |
|--------|-----------|
| `postgres_saver.py` | Сохранение данных в PostgreSQL (используется миграциями). |
| `neo4j_client.py` | Клиент для графовой БД Neo4j. |
| `qdrant_client.py` | Работа с Qdrant (векторный поиск). |
| `elasticsearch_client.py` | Клиент к Elasticsearch (если используется исторический индекс). |
| `marketplace_repository.py` | Репозиторий marketplace (учёт интеграций, продуктов).

Связанные материалы: [docs/06-features/ML_DATASET_GENERATOR_GUIDE.md](../../docs/06-features/ML_DATASET_GENERATOR_GUIDE.md), [docs/ops/devops_platform.md](../../docs/ops/devops_platform.md).
