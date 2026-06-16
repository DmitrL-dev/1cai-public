# 🪟 Windows Quickstart — локальный запуск AI-стека

**Цель:** дать 1С‑разработчику на Windows минимальный набор шагов, чтобы:

- запустить backend/AI‑контур,
- прогнать базовые тесты,
- проверить security‑аудит — без GNU Make.

---

## 1. Подготовка окружения

1. Установите:
   - Python 3.11.x
   - Docker Desktop
   - Git
2. Клонируйте репозиторий:

```powershell
cd C:\Projects
git clone https://github.com/DmitrL-dev/1cai.git
cd 1cai
```

3. Создайте виртуальное окружение и установите зависимости:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-stage1.txt
pip install -r requirements-dev.txt
```

---

## 2. Запуск инфраструктуры и backend

### 2.1. Инфраструктура (PostgreSQL + Redis)

```powershell
docker-compose up -d postgres redis
docker-compose ps
```

Убедитесь, что контейнеры `postgres` и `redis` в состоянии `running`.

### 2.2. Миграции и backend API

```powershell
# Миграции
python scripts/run_migrations.py

# Backend (в отдельном терминале, с активированным venv)
python src/main.py
```

Проверьте, что backend отвечает:

```powershell
curl http://localhost:8000/health
```

Ожидаемый ответ: JSON со статусом `healthy`.

---

## 3. Базовые тесты и e2e‑сценарии

### 3.1. Unit + system тесты агентов

```powershell
# Unit тесты по оркестратору и ключевым агентам
python -m pytest `
  tests/unit/test_developer_agent_secure.py `
  tests/unit/test_business_analyst_integrations.py `
  tests/unit/test_llm_diagnostics.py `
  tests/unit/test_sql_optimizer.py `
  tests/unit/test_sql_optimizer_secure.py `
  tests/unit/test_tech_log_analyzer.py `
  tests/unit/test_ras_monitor_complete.py `
  tests/unit/test_ai_issue_classifier.py `
  tests/unit/test_ai_issue_classifier_ml.py `
  tests/unit/test_ai_orchestrator_basic.py -q

# Сквозной BA→Dev→QA сценарий
python -m pytest tests/system/test_e2e_ba_dev_qa.py -q
```

Все тесты должны завершиться со статусом `passed`.

---

## 4. Security‑аудит (Windows)

Запустите составной security‑аудит для Windows:

```powershell
pwsh scripts/windows/security-audit.ps1
```

Сценарий последовательно выполнит:

- `scripts/audit/check_hidden_dirs.py --fail-new`
- `scripts/audit/check_secrets.py --json > analysis/secret_scan_report.json`
- `scripts/audit/check_git_safety.py`
- `scripts/audit/comprehensive_project_audit.py`

После выполнения проверьте:

- `analysis/secret_scan_report.json` — только демо/тестовые токены, без реальных ключей;
- `output/audit/comprehensive_audit.json` — общий отчёт по структуре/документации/зависимостям.

---

## 5. Куда смотреть дальше

- Общий локальный гайд: [`docs/01-getting-started/local.md`](./local.md)  
- Мониторинг AI‑сервисов: [`monitoring/AI_SERVICES_MONITORING.md`](../../monitoring/AI_SERVICES_MONITORING.md)  
- Производительность AI‑контура: [`docs/06-features/AI_PERFORMANCE_GUIDE.md`](../06-features/AI_PERFORMANCE_GUIDE.md)  
- E2E‑сценарий BA→Dev→QA: [`docs/08-e2e-tests/BA_DEV_QA_E2E.md`](../08-e2e-tests/BA_DEV_QA_E2E.md)


