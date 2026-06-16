# 💻 Development - Разработка

Документация для разработчиков

---

## 📚 Содержание раздела

1. **[CHANGELOG.md](./CHANGELOG.md)** - история изменений
2. **[edt-plugin/](./edt-plugin/)** - EDT plugin development
3. **[scripts/](./scripts/)** - Utility scripts

---

## 🛠️ Development Setup

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Lint
black src/
flake8 src/
```

---

## 📝 Contributing

См. [Contributing Guide](../01-getting-started/CONTRIBUTING.md)

---

## 🔍 Автоматические проверки

Перед любыми коммитами и пушами запускайте полный аудит:

```bash
python run_full_audit.py --stop-on-failure
```

Скрипт последовательно выполняет:

- Проверку всех ссылок (`check_all_links.py` → `BROKEN_LINKS_REPORT.txt`)
- Комплексный аудит структуры (`comprehensive_project_audit_final.py`)
- Security-проверку (`check_security_comprehensive.py`)
- Сверку README и кода (`check_readme_vs_code.py`)

Опционально добавьте `--include-cleanup`, чтобы удалить временные отчёты из корня.

### Правила публикации

- Раздел `README.md → Что нового` обязан быть отсортирован по убыванию даты (последние изменения сверху).
- После успешного аудита делаем push **в оба** репозитория: `origin` и `public`.
- **Обязательный порядок:** сначала пушим в приватный репозиторий для ручной проверки, затем — в публичный.

#### Private → Public workflow

1. Выполните `python run_full_audit.py --stop-on-failure`.
2. Пушим изменения в приватный репозиторий:
   ```powershell
   git push origin main
   ```
   (или используйте `git_push_safe.ps1`, если работаете в PowerShell).
3. Дождитесь ручного ревью (внутренний канал/чат). Только после одобрения продолжаем.
4. Запускаем автоматический скрипт публикации:
   ```powershell
   pwsh ./push_to_public.ps1
   ```
   Скрипт сам создаст merge-коммит, синхронизирует теги и проверит, что все отчёты свежие.
5. Убедитесь, что публичный репозиторий обновлён (`git remote show public`), и только потом закрывайте таски.

## 🗄️ Database & Storage

```bash
python scripts/run_migrations.py
```

- Использует Alembic (`alembic.ini`, `db/alembic/`)
- Учитывает `DATABASE_URL` из `.env`
- Запускайте перед стартом backend и при деплое
- Для интеграционных тестов задайте `TEST_DATABASE_URL` (например, на тестовую PostgreSQL), чтобы `pytest -m integration` мог проверить `MarketplaceRepository`

```bash
docker-compose -f docker-compose.yml -f docker-compose.stage1.yml up -d minio
```

- Запускает локальное S3-хранилище (MinIO)
- Консоль: http://localhost:9001 (креды в `.env`)
- Endpoint: `AWS_S3_ENDPOINT=http://localhost:9000`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`

### Управление ролями

```bash
python scripts/manage_roles.py grant-role user-1 admin --assigned-by=system
python scripts/manage_roles.py grant-permission user-1 marketplace:approve
```

- Скрипт использует активное подключение к БД (`DATABASE_URL`)
- Записи сохраняются в таблицах `user_roles` и `user_permissions`
- Для REST-управления используйте endpoints `/admin/users/{user_id}/roles` и `/permissions` (требуется роль `admin`)

### CI Pipeline

- Workflow `.github/workflows/comprehensive-testing.yml` выполняет `python scripts/run_migrations.py` перед интеграционными тестами (использует сервисный PostgreSQL/Redis).
- Для корректного прогона локальных интеграционных тестов задайте `TEST_DATABASE_URL` и запустите `python scripts/run_migrations.py` вручную.

CI: Do  run run migrations? Wait already there. Need to insert new note earlier near audit? we changed line but feed else. Maybe better to add new section below.

## 🔑 Аутентификация (JWT)

Используйте Bearer токены для защищённых endpoints:

```bash
# Получить токен (демо-учётки задаются через AUTH_DEMO_USERS)
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=<your_username>&password=<your_password>"

# Вызвать защищённый endpoint
curl http://localhost:8000/marketplace/plugins \
  -H "Authorization: Bearer <your_token>"

# Проверить текущего пользователя
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer <your_token>"
```

В production установите собственные значения `JWT_SECRET`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` и переопределите `AUTH_DEMO_USERS`.

[← Deployment](../04-deployment/) | 

