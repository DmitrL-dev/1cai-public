# Postmortem & Retrospective Playbook

## 1. Когда проводить
- P0/P1 инциденты (см. oncall_rotations.md).
- SLA/SLO breach.
- Существенные регрессы/проблемы в релизе.

## 2. Формат
- Использовать `docs/runbooks/postmortem_template.md`.
- Обязательно указать timeline, root cause, detection, remediation, action items.

## 3. Процесс
1. Организатор (один из on-call инженеров) назначает встречу ≤48 часов после инцидента.
2. Участники: on-call, команда разработки, DevOps, Security (если нужно), Продакт.
3. Правила: blameless, focus on systems/processes.
4. Презентация фактов → обсуждение причин → список улучшений.
5. Action items добавляются в tracker (`postmortem-action`).
6. Update `docs/research/README_LOCAL.md` и `CHANGELOG.md` (если затронуты процессы).

## 4. Retro (ежеквартально)
- 1 раз в квартал собрать команду DevOps/SRE.
- Повестка: метрики (DORA, FinOps), выполненные RFC/ADR, состояние on-call, проблемы и предложения.
- Action items закрепить за владельцами.

## 5. Инструменты
- Notion/Confluence (TODO) или `docs/runbooks/postmortem/YYYY-MM-DD.md`.
- Slack канал `#postmortem` для архивирования и уведомлений.
