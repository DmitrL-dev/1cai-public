# 👨‍💻 Developer AI Secure Guide

**Статус:** ✅ Production  
**Файл:** `src/ai/agents/developer_agent_secure.py`

---

## 🎯 Назначение

Developer AI Secure — это ассистент для генерации и правок кода 1С/BSL с жёстким соблюдением Security Rule-of-Two:

- `[A]` обрабатывает недоверенные промпты,
- `[B]` имеет доступ к репозиторию,
- `[C]` **не** изменяет состояние без человека.

Любая генерация проходит две проверки в `AISecurityLayer` (вход/выход), фиксируется в аудите и требует ручного approve.

---

## 🔐 Rule-of-Two Workflow

1. `generate_code(prompt)`  
   - Security Layer валидирует вход.  
   - AI генерирует код (`_generate_with_ai`).  
   - Выход снова проверяется (редакция чувствительных данных).  
   - Результат содержит `token`, `safety`, `requires_approval=True`.

2. `apply_suggestion(token, approved_by_user)`  
   - Human одобряет в UI.  
   - Агент повторно анализирует код (`_analyze_code_safety`).  
   - Запись в репозиторий эмулируется `_write_to_repository()` (Git commit в проде).  
   - Событие логируется в `audit_logger`.

3. `bulk_approve_safe_suggestions(tokens)`  
   - Разрешает только предложения с `score>0.95`, иначе — отклоняет.

---

## 🧪 Тестирование

```bash
# Юнит-тесты (Rule-of-Two, токены, истечение срока)
pytest tests/unit/test_developer_agent_secure.py -v
```

Покрываем сценарии:
- генерация возвращает `requires_approval` и токен,
- успешное применение после approve,
- обработка невалидного либо просроченного токена.

---

## 🧩 Встраивание

### Использование из сервисов

```python
from src.ai.agents.developer_agent_secure import DeveloperAISecure

agent = DeveloperAISecure()

draft = agent.generate_code("Сгенерируй модуль обработки заказов")
# -> draft["token"], draft["safety"], draft["preview_url"]

apply_result = agent.apply_suggestion(
    token=draft["token"],
    approved_by_user="dev.lead"
)
```

### API слои

- REST: `POST /api/code-review/generate` → `DeveloperAISecure.generate_code`
- Review UI: отображает diff + кнопку «Approve (token)»
- `POST /api/code-review/apply` → вызывает `apply_suggestion`

---

## ✅ Checklist перед релизом

1. Пропустить промпты через `AISecurityLayer` (нет prompt injection).
2. Проверить, что `Rule-of-Two` = `[AB]` ( `config.validate()` не падает).
3. Аудит‑логи пишутся (`audit_logger.log_ai_request`).
4. Все токены очищаются после применения.
5. `tests/unit/test_developer_agent_secure.py` зелёный в CI.

---

## 📚 Связанные материалы

- `src/security/ai_security_layer.py` — общий слой безопасности.
- `docs/03-ai-agents/ALL_ASSISTANTS_IMPLEMENTATION_COMPLETE.md` — общее покрытие агентов.
- `docs/security/policy_as_code.md` — требования по audit trail.

