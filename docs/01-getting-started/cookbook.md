# 🍳 Usage Cookbook — типовые сценарии

Набор «рецептов» для быстрого использования стека без чтения всей документации.

---

## 1. Быстро проверить, что всё в порядке (Linux/macOS)

```bash
make check-runtime         # Python 3.11 + предупреждения по make/docker
make test-unit             # Юнит-тесты
make test-integration      # Интеграционные тесты
make security-audit        # Скрытые каталоги, секреты, git safety, аудит проекта
```

---

## 2. Быстрый локальный старт (Windows)

1. Пройти `docs/01-getting-started/windows_quickstart.md`.  
2. Минимальный набор:

```powershell
cd C:\1cAI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

docker-compose up -d postgres redis
python src/main.py
python -m pytest tests/unit/ -q
pwsh scripts/windows/security-audit.ps1
```

---

## 3. Проверить BA → Dev → QA поток (E2E)

```bash
python -m pytest tests/system/test_e2e_ba_dev_qa.py -q
```

Документация: `docs/08-e2e-tests/BA_DEV_QA_E2E.md`.

---

## 4. Проверить AI Orchestrator (тесты + латентность)

```bash
# Юнит-тесты оркестратора
python -m pytest tests/unit/test_ai_orchestrator_basic.py -q

# Латентностный smoke-тест (offline)
python scripts/testing/orchestrator_latency_smoke.py --requests 10
```

Подробности: `docs/06-features/AI_PERFORMANCE_GUIDE.md`.

---

## 5. Проверить Kimi/Kimi fallback (при наличии ключей)

```bash
# Бенчмарк Kimi-K2-Thinking
python scripts/testing/kimi_benchmark.py --requests 10 --concurrency 2
```

Если переменные `KIMI_API_KEY` / `KIMI_OLLAMA_URL` не заданы, скрипт просто сообщит, что бенчмарк пропущен.

---

## 5.1. Использовать российские AI провайдеры (GigaChat, YandexGPT, 1C:Напарник)

Платформа автоматически выбирает российские провайдеры для русскоязычных запросов через LLM Provider Abstraction.

### Конфигурация

**GigaChat:**
```bash
# Вариант 1: Access Token (прямой доступ)
export GIGACHAT_ACCESS_TOKEN="your-token"

# Вариант 2: Client Credentials (OAuth 2.0)
export GIGACHAT_CLIENT_ID="your-client-id"
export GIGACHAT_CLIENT_SECRET="your-client-secret"
```

**YandexGPT:**
```bash
export YANDEXGPT_API_KEY="your-api-key"
export YANDEXGPT_FOLDER_ID="your-folder-id"
```

**1C:Напарник:**
```bash
export NAPARNIK_API_KEY="your-api-key"
```

### Проверка интеграции

```bash
# E2E тесты для GigaChat/YandexGPT
python -m pytest tests/system/test_e2e_llm_provider_abstraction.py::test_e2e_gigachat_integration_with_orchestrator -v
python -m pytest tests/system/test_e2e_llm_provider_abstraction.py::test_e2e_yandexgpt_integration_with_orchestrator -v

# E2E тесты для 1C:Напарник
python -m pytest tests/system/test_e2e_llm_provider_abstraction.py::test_e2e_naparnik_integration_with_orchestrator -v
python -m pytest tests/system/test_e2e_llm_provider_abstraction.py::test_e2e_naparnik_in_llm_provider_abstraction -v

# Unit тесты для 1C:Напарник
python -m pytest tests/unit/test_naparnik_client.py -v
```

### Использование через API

```bash
# Русскоязычный запрос автоматически выберет российский провайдер
curl -X POST "http://localhost:8000/api/ai/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "Объясни, как работает механизм проведения документов в 1С", "context": {}}' | jq

# Запрос с требованием compliance (152-ФЗ)
curl -X POST "http://localhost:8000/api/ai/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "Запрос на русском", "context": {"compliance": ["152-ФЗ"]}}' | jq

# Выбор провайдера через LLM Provider Abstraction
curl -X POST "http://localhost:8000/api/llm/select-provider" \
  -H "Content-Type: application/json" \
  -d '{"query_type": "russian_text", "required_compliance": ["152-ФЗ"]}' | jq
```

### Использование через CLI

```bash
# Запрос через CLI (автоматически выберет российский провайдер для русского текста)
python scripts/cli/1cai_cli.py query "Объясни, как работает механизм проведения документов в 1С"

# Список доступных LLM провайдеров
python scripts/cli/1cai_cli.py llm-providers list

# Выбор провайдера с учетом compliance
python scripts/cli/1cai_cli.py llm-providers select --query-type russian_text --compliance 152-ФЗ
```

**Особенности:**
- Автоматическое определение русского текста в запросах
- Выбор провайдера на основе compliance требований (152-ФЗ, GDPR)
- 1C:Напарник бесплатен для пользователей 1С (cost 0.0)
- Автоматический fallback между российскими провайдерами

Подробнее: `docs/06-features/AI_PERFORMANCE_GUIDE.md` (разделы 3.1 и 1C:Напарник интеграция).

---

## 6. DR rehearsal + постмортем (staging)

```bash
# Запуск сценария DR rehearsal (например, vault)
python scripts/runbooks/dr_rehearsal_runner.py vault

# Генерация черновика постмортема
python scripts/runbooks/generate_dr_postmortem.py vault --status success
```

План: `docs/runbooks/dr_rehearsal_plan.md`, шаблон: `docs/runbooks/postmortem_template.md`.

---

## 7. Посмотреть пример сценариев Scenario Hub

После запуска backend-а (FastAPI / Orchestrator) можно получить примерные планы
BA→Dev→QA и DR rehearsal в виде JSON:

```bash
curl "http://localhost:8000/api/scenarios/examples?autonomy=A2_non_prod_changes" | jq
```

Подробнее: `docs/architecture/AI_SCENARIO_HUB_REFERENCE.md` и `docs/architecture/TOOL_REGISTRY_REFERENCE.md`.

---

## 8. Запустить YAML-плейбук Scenario Hub (dry-run)

Для локальной проверки структуры плейбука можно выполнить dry-run:

```bash
python scripts/runbooks/run_playbook.py playbooks/ba_dev_qa_example.yaml --autonomy A2_non_prod_changes
```

Аналогично для DR rehearsal:

```bash
python scripts/runbooks/run_playbook.py playbooks/dr_vault_example.yaml --autonomy A2_non_prod_changes
```

И для сценария security-audit:

```bash
python scripts/runbooks/run_playbook.py playbooks/security_audit_example.yaml --autonomy A1_safe_automation
```

Скрипт не выполняет реальные действия — только печатает отчёт по шагам
и уровню риска/автономности сценария.

---

## 9. Быстрый прогон synthetic performance-тестов

Для проверки базовой производительности AI Orchestrator и кеша:

```bash
python -m pytest tests/unit/test_ai_orchestrator_basic.py -q
```

Для более тяжёлого нагрузочного прогона (при поднятых локальных сервисах/БД):

```bash
python -m pytest tests/performance/test_load_performance.py::test_api_latency_benchmark -q
python -m pytest tests/performance/test_load_performance.py::test_concurrent_requests -q
```

---

## 10. Проверить соответствие стандартам (Scenario DSL / Policy / Graph)

Если вы используете наши сценарии/политику/граф в своём окружении или после крупных
изменений схем/примеров, полезно прогнать стандартизирующие проверки:

```bash
make validate-standards
```

Команда:

- валидирует примеры ScenarioPlan и Autonomy Policy по JSON Schema;
- проверяет пример экспорта Unified Change Graph;
- формирует JSON-отчёт о совместимости (скрипт `scripts/validation/check_conformance_report.py`).

Подробнее про стандарты и уровни совместимости:
`docs/architecture/SCENARIO_DSL_SPEC.md`, `AUTONOMY_POLICY_SPEC.md`,
`CODE_GRAPH_REFERENCE.md` и `STANDARDS_CONFORMANCE_CHECKLIST.md`.

