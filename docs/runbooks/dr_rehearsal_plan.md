# DR Rehearsal Plan

## 1. Цель
- Проверить способность команды восстановить сервисы (Vault, API, Linkerd, Databases) в случае полного сбоя.

## 2. Частота
- Ежеквартально (как минимум 2 раза в год). Включить в календарь on-call.

## 3. Сценарии
1. **Vault outage**: отключение Vault pod'ов, восстановление из snapshot, проверка `make vault-test`.
2. **API database**: симулируем потерю БД (использовать staging), восстановление из backup.
3. **Linkerd control plane**: удалить namespace linkerd, восстановить через ArgoCD ApplicationSet.
4. **FinOps**: проверить, что cost logs продолжают генерироваться (workflow + Grafana).

## 4. Команда
- Primary on-call (координатор восстановления).
- Secondary — сетевой/infra инженер.
- DBA/Storage.

## 5. План
- За неделю подготовить сценарии и среду (staging).
- Запустить `scripts/runbooks/dr_rehearsal_runner.py <component>` или workflow `dr-rehearsal.yml` (по расписанию / вручную).
- Во время rehearsal вести лог (использовать шаблон в `docs/process/oncall_rotations.md`).
- После завершения — постмортем + action items.

## 6. TODO
- Автоматизировать создание DR среды (Terraform).
- Собирать метрики MTTR/MTTF.
- Интегрировать Litmus сценарии (network loss) в rehearsal.
- Использовать `scripts/runbooks/generate_dr_postmortem.py` для автоматического создания черновика постмортема после `dr_rehearsal_runner.py`.
