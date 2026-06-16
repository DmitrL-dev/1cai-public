# Middleware Components

Глобальные middleware FastAPI/Starlette для обеспечения безопасности, метрик и многотенантности.

| Файл | Описание |
|------|----------|
| `jwt_user_context.py` | Извлекает пользователя из JWT, прокидывает контекст. |
| `metrics_middleware.py` | Экспорт Prometheus-метрик (см. [`src/monitoring/prometheus_metrics.py`](../monitoring/prometheus_metrics.py)). |
| `rate_limiter.py`, `user_rate_limit.py` | Ограничение запросов по IP/пользователю. |
| `security_headers.py` | Добавляет HTTP security headers (CSP, X-Frame-Options, HSTS). |

Документация: [docs/ops/devops_platform.md](../../docs/ops/devops_platform.md), [docs/security/policy_as_code.md](../../docs/security/policy_as_code.md).
