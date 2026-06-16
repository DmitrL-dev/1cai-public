# Marketplace API Guide

Marketplace модуль (`src/api/marketplace.py`, `src/db/marketplace_repository.py`) позволяет загружать и модерировать плагины/ассетты. Этот документ описывает сценарии для пользователей и технические детали настройки.

---

## 1. Быстрый старт (пользователь)

| Сценарий | Команда |
| --- | --- |
| **Загрузить плагин** | `scripts/tests/run_offline_dry_run.py --upload marketplace/plugins/sample.zip` или REST-запрос `POST /api/v1/marketplace/plugins/{plugin_id}/upload`. |
| **Обновить метаданные** | `PATCH /api/v1/marketplace/plugins/{plugin_id}` с полями `version`, `description`, `categories`. |
| **Оставить жалобу** | `POST /api/v1/marketplace/plugins/{plugin_id}/complaints` (роль `user`). |
| **Ответить на жалобу / модерировать** | `POST /api/v1/marketplace/plugins/{plugin_id}/complaints/{complaint_id}/resolve` (роль `reviewer`). |

Формат payload см. в `docs/templates/offline_incident_report.md` и `tests/integration/test_marketplace_e2e.py`.

---

## 2. Пользовательские роли

| Роль | Возможности |
| --- | --- |
| `developer` | Создание/обновление плагина, загрузка артефактов. |
| `reviewer` | Просмотр жалоб, модерация, публикация. |
| `admin` | Удаление, восстановление, настройка лимитов. |

Роли выдаются через `src/api/auth.py` (см. `docs/security/policy_as_code.md`).

---

## 3. Техническая конфигурация

1. **Хранилище** — по умолчанию файлы складываются в `./output/marketplace/`. Для S3/MinIO задайте ENV `MARKETPLACE_STORAGE=s3`, `S3_BUCKET`, `S3_ENDPOINT`.
2. **Limiting** — `src/middleware/rate_limiter.py` ограничивает загрузки (`/upload`) и жалобы:
   - лимит по IP (`MARKETPLACE_UPLOAD_RPS`)
   - лимит по пользователю (`MARKETPLACE_UPLOAD_PER_USER`)
3. **Валидация** — Pydantic-модели в `src/db/marketplace_repository.py` и `src/api/marketplace.py` (параметры `PluginMetadata`, `PluginUploadRequest`).
4. **Безопасность** — каждый upload проходит через `src/services/ai_response_cache.py` (скан описания), запрещены path traversal, SQL-инъекции.

---

## 4. Тестирование и отладка

- **Unit**: `tests/unit/test_marketplace_api.py`, `tests/unit/test_marketplace_repository.py`.
- **Integration**: `tests/integration/test_marketplace_e2e.py` покрывает весь поток (submit → update → report → approve).
- **Smoke**: `scripts/tests/llm_smoke.py --scenario marketplace`.

Для локального запуска:

```bash
make docker-up
make servers
pytest tests/integration/test_marketplace_e2e.py -vv
```

---

## 5. API примеры

### Upload

```bash
curl -X POST http://localhost:6001/api/v1/marketplace/plugins/demo/upload \
     -H "Authorization: Bearer <token>" \
     -F "file=@build/demo.zip" \
     -F "metadata={\"version\":\"1.2.0\",\"summary\":\"Demo plugin\"};type=application/json"
```

### Update metadata

```bash
curl -X PATCH http://localhost:6001/api/v1/marketplace/plugins/demo \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"categories":["ai","bpmn"],"visibility":"public"}'
```

---

## 6. Поддержка

- **Логи**: `logs/marketplace.log`, structured logging (`src/utils/structured_logging.py`).
- **Мониторинг**: `marketplace_upload_duration_seconds`, `marketplace_complaints_total` (добавляются в Prometheus).
- **Инциденты**: описываются в `docs/templates/offline_incident_report.md` (раздел marketplace).

Если появляется новая роль/тип артефакта — обновите `src/db/marketplace_repository.py`, `docs/06-features/MARKETPLACE_GUIDE.md` и добавьте тесты.

