# RFC / ADR Process

## 1. Когда нужен RFC
- Изменения архитектуры или API.
- Инфраструктурныеmigration (K8s, Vault, Linkerd) на прод.
- Вовлечение нескольких команд/подразделений.

## 2. Формат RFC
- Шаблон `templates/rfc.md` (TODO): Заголовок, контекст, варианты, риски, план внедрения.
- Создавать в `docs/rfc/YYYY/SLUG.md`. Первичная версия — Draft.

## 3. Жизненный цикл
1. Автор создаёт RFC, открывает issue (`rfc:draft`).
2. Теамлид/архитектор назначает reviewer’ов (DevOps, Security, Product).
3. Обсуждение в Slack/комментариях. Решение фиксируется в `Decision`.
4. После утверждения — создать ADR (`docs/architecture/adr/` или `docs/process/adr/`). RFC получает статус `Accepted`.
5. План внедрения → задачи в tracker (Jira/GitHub Projects). Документ `docs/research/README_LOCAL.md` обновить.

## 4. ADR
- Описывают финальное решение (см. `docs/architecture/adr/` шаблон `docs/architecture/adr/ADR_TEMPLATE.md`).
- Содержат ссылку на RFC и на PR/issue.

## 5. Инструменты
- GitHub Issues + labels `rfc:draft`, `rfc:review`, `rfc:accepted`.
- Slack канал `#rfc-review` для обсуждения.
- Автопроверка (TODO): workflow, проверяющий наличие ADR и RFC ссылок в PR.

## 6. TODO
- Создать шаблон `templates/rfc.md`.
- Автоматически генерировать changelog для принятых RFC.
