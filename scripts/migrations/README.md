# Data Migrations

Сценарии переноса данных между хранилищами платформы (JSON → PostgreSQL → Neo4j → Qdrant). Используются make-таргетами `make migrate`, `make migrate-pg`, `make migrate-neo4j`, `make migrate-qdrant`.

## Скрипты
| Скрипт | Назначение |
|--------|-----------|
| `migrate_json_to_postgres.py` | Загружает исходные выгрузки (JSON/CSV) в PostgreSQL. |
| `migrate_postgres_to_neo4j.py` | Формирует граф зависимостей и метаданных в Neo4j. |
| `migrate_to_qdrant.py` | Создаёт векторный индекс для поиска по знанию. |
| `run_migrations.py` (в корне `scripts/`) | Последовательный запуск всех этапов миграции. |

## Требования
- docker-compose сервисы (`make docker-up`): PostgreSQL, Neo4j, Qdrant.
- Файлы конфигураций/дампы в каталоге `data/` или `1c_configurations/`.
- Переменные окружения (см. `env.example`): строки подключения, пути к данным.

## Запуск вручную
```bash
# Полная цепочка
make migrate

# Или по шагам
make migrate-pg
make migrate-neo4j
make migrate-qdrant

# Альтернатива напрямую
python scripts/migrations/migrate_json_to_postgres.py --config config/migrations.yaml
```

Логи и промежуточные файлы сохраняются в `output/migrations/`. После миграции обновите документацию и запустите анализаторы (`make generate-docs`).
