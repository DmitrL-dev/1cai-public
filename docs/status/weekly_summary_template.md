# Weekly Status Summary Template

> Используется вместе с `dora_history.md`, SLO‑отчётами и постмортемами.

---

## 1. Период и контекст

- **Неделя:** YYYY‑WW  
- **Диапазон дат:** YYYY‑MM‑DD — YYYY‑MM‑DD  
- **Команда/продукт:** 1C AI Stack

---

## 2. DORA Metrics (за неделю)

- **Deployment Frequency:** … (деплоев в неделю)  
- **Lead Time for Changes:** … (среднее время от PR до прод)  
- **Change Failure Rate:** …%  
- **MTTR:** … (среднее время восстановления)

> Источник: `scripts/metrics/collect_dora.py` → `docs/status/dora_history.md`.

---

## 3. SLO & Incidents

- **SLO статус:** (OK / Warning / Breach)  
- **Основные SLI:** latency, availability, error rate  
- **Инциденты за неделю:**  
  - #INC‑123: краткое описание, влияние, статус  
  - #INC‑124: …

> Источники: `docs/observability/SLO.md`, `docs/runbooks/alert_slo_runbook.md`, Alertmanager.

---

## 4. Postmortems & Lessons Learned

- **Postmortems за неделю:**  
  - PM‑001: краткое название, ключевые выводы  
  - PM‑002: …

- **Key lessons / next actions:**  
  - …  
  - …

> Источник: `docs/runbooks/postmortem_template.md`, `docs/process/postmortem_playbook.md`.

---

## 5. Планы на следующую неделю

- **Engineering:** …  
- **Reliability/Observability:** …  
- **Security/Compliance:** …  
- **BA/AI Agents:** …


