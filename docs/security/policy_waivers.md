# Policy Waivers / Исключения для Policy-as-Code

> Цель: зафиксировать единый подход к **временным исключениям** из Conftest/Semgrep‑политик
> и GitOps‑манифестов (Argo CD), чтобы они не превращались в «вечные дыры».

---

## 1. Когда допустим waiver

Исключения допускаются только если одновременно выполняются условия:

- **Бизнес‑кейс**: есть понятная причина (legacy, vendor‑ограничения, временный workaround).
- **Срок действия**: waiver имеет дату пересмотра (`review_by`) и owner-а.
- **Низкий риск**: риск осознан и описан; для high‑risk требуется отдельное решение owner-а платформы.

Все остальные случаи должны решаться правками кода/манифестов, а не waiver-ами.

---

## 2. Формат waiver-записей

Waiver-ы хранятся в YAML/MD‑файлах рядом с политиками, например:

- `policy/kubernetes/waivers.yaml` — исключения для K8s/Argo CD манифестов.
- `policy/terraform/waivers.yaml` — исключения для Terraform планов.

Рекомендуемый формат записи (YAML):

```yaml
- id: "waiver-argo-001"
  resource: "applicationset-1cai"
  file: "infrastructure/argocd/applicationset-1cai.yaml"
  rule: "k8s_no_latest_tag"
  reason: "Временный use latest для internal image в dev-кластере"
  owner: "platform-team"
  created_at: "2025-11-16"
  review_by: "2026-02-01"
  status: "temporary"  # temporary / accepted / rejected
```

---

## 3. Как использовать вместе с Conftest

Пайплайн `scripts/security/run_policy_checks.sh` запускает Conftest для:

- Helm‑рендеров (1cai-stack, observability-stack);
- kind‑кластера;
- GitOps‑манифестов Argo CD (`infrastructure/argocd`);
- Terraform‑планов (если существуют).

Интеграция waivers может быть реализована так:

- в Rego‑политиках использовать дополнительный input (список waiver-ов);
- либо фильтровать результаты `conftest test` post‑processing-скриптом, который:
  - помечает нарушения, покрытые waivers, как `warning`/`accepted`,
  - требует пересмотра всех waiver-ов с `review_by < today`.

На данном этапе waivers задокументированы как процесс; техническая интеграция может быть добавлена позже в рамках расширения `run_policy_checks.sh` и Rego‑правил.

---

## 4. Требования Конституции

Перед релизом/PR:

- список активных waivers должен быть **просмотрен и одобрен** ответственным (owner);
- для каждого waiver-а должно быть:
  - описание impact-а,
  - план устранения (remediation plan),
  - срок пересмотра.

Любые «безымянные» или просроченные waivers считаются нарушением процесса безопасности.

*** End Patch```} ***!

