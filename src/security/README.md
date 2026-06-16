# Security Layer

Модули, отвечающие за безопасность API/AI функций: аутентификация, роли, аудит, защитный слой для AI-ответов.

| Файл | Назначение |
|------|-----------|
| `auth.py` | Аутентификация/авторизация пользователей. |
| `roles.py` | Ролевую модель и проверку прав. |
| `audit.py` | Логи безопасности и аудит действий. |
| `ai_security_layer.py` | Фильтрация/обогащение AI-ответов (PII, политики). |
| `advanced_security.py` | Дополнительные меры (rate limit, detections). |

Связанные материалы:
- [docs/security/policy_as_code.md](../../docs/security/policy_as_code.md)
- [docs/runbooks/alert_slo_runbook.md](../../docs/runbooks/alert_slo_runbook.md)
- [tests/security/test_security.py](../../tests/security/test_security.py)
