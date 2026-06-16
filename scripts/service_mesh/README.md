# Service Mesh Utilities

Сценарии для управления сервис-мешем (Linkerd). Для детальной инструкции откройте [`linkerd/README.md`](linkerd/README.md).

| Скрипт | Назначение |
|--------|-----------|
| `linkerd/bootstrap_certs.sh` | Генерация trust anchor и issuer сертификатов. |
| `linkerd/rotate_certs.sh` | Ротация сертификатов Linkerd. |
| `linkerd/apply_managed_identity.sh` | Настройка Azure Managed Identity для секретов. |
| `linkerd/ci_smoke.sh`, `linkerd/chaos_ci.sh` | Smoke/chaos проверки Linkerd в CI. |

## Связанные make-таргеты
- `make linkerd-install`
- `make linkerd-rotate-certs`
- `make linkerd-smoke`

Дополнительно см. [`docs/ops/service_mesh.md`](../../docs/ops/service_mesh.md).
