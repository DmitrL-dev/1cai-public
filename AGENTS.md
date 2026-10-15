# Работа с Рентгеном

## Сначала установить факты

- Центральные входы: `README.md`, `ROADMAP.md`, `docs/README.md` и
  `docs/product/READINESS.md`. Текущий план и реестр —
  `docs/product/FULL-FINAL-PLAN.md`: цель — полный финальный релиз со всеми
  текущими планами; компонентный prerelease не закрывает её.
  Датированные планы и evidence не являются результатами текущего HEAD.
- Проверить `git status`, remote main, открытые PR и актуальный diff перед
  изменениями. Сохранять чужие незакоммиченные правки; работать в одной ветке
  задачи или отдельном worktree при необходимости изоляции.
- Изменение поведения сопровождается узкой воспроизводимой проверкой.
  Отсутствующий runtime или неудачная проверка — ограничение, а не успех.

## Границы и проверки

- Продуктовый комплект: Windows x64 / CPython 3.11. Linux state/ZIP/GUI,
  [PR #102 source capture/graph/history](docs/product/evidence/development-ci-366db69-20261016.json)
  и отдельные [PR #103](docs/product/evidence/development-ci-c9cb31e-20261016.json) /
  [fresh main `8e7346e`](docs/product/evidence/development-ci-8e7346e-20261016.json)
  offline CLI/MCP receipts — ограниченные GNU/Linux x86_64 маршруты, без нового выпуска.
  [Linux kit](scripts/release/OWNED-LINUX-KIT.md) требует проверенной `acceptance.json`
  точных source/bytes каждой сборки; source SDK tests не заменяют installed SDK.
  [SNAP-DIFF-01](docs/product/SNAPSHOT-DIFF.md) — отдельный source-контракт:
  Linux pair имеет общий POSIX budget; Windows CLI прежний, новый MCP имеет общий
  deadline/output guard с per-session ресурсами. Public macOS закрыт.
  Старые CI `c9` / `8e` новый diff не квалифицируют; его exact-source
  [CI `c2b6cd2`](docs/product/evidence/development-ci-c2b6cd2-20261016.json) — ограниченная синтетическая приёмка. Точные границы —
  [PORTABLE-CORE](docs/product/PORTABLE-CORE.md); pure-Python wheel не означает
  поддержку всех команд или macOS.
- Python: `python -m pytest -q <relevant tests>`; полный Windows suite и
  installed-kit/SCM проверки выполняет `.github/workflows/core-ci.yml`.
- Companion: `node --test integrations/vscode-rentgen/test/*.test.cjs
  scripts/verification/companion_host/*.test.cjs`.
- Go scanner: `go -C go test ./...`. Rust input core: pinned toolchain и
  `--locked` из portable workflow. Браузерные проверки GUI: все gates из
  `.github/workflows/gui-browser-ci.yml`, настоящий helper и sandbox.
- Изменения workflow проверять `actionlint`: разбор YAML не проверяет
  допустимость GitHub expression contexts и не заменяет реальное исполнение CI.
- Полный Linux suite имеет документированный Windows baseline. Не удалять
  failure IDs и не расширять baseline ради зелёного CI; новые failures исправлять.
- Не заменять native 1С, installed-package или browser acceptance подставными
  объектами. Указывать точный source commit, ОС, команды, skips и scope.
- Source-facts PR #84 остаётся отдельным draft до полного176/whole-process gate,
  независимого source cohort и installed qualification. Обычный CI его не заменяет.

## Документация и Git

- При изменении публичного поведения синхронизировать инструкции и описание
  ограничений. Различать «есть в исходниках», «проверено» и «опубликовано».
- `output/`, окружения, бинарные сборки и приватные трассы не коммитить.
  В evidence сохранять только необходимые проверенные и безопасные квитанции.
- Объединять функциональность, её проверки и актуальные инструкции в готовый
  логический блок: законченный пользовательский сценарий в явно указанном scope.
  Мелкие промежуточные checkpoints держать локально; проверочные commits и draft
  push допустимы, когда remote HEAD нужен для Windows/Linux CI или ревью.
- Независимый готовый PR по умолчанию вливать squash одним итоговым коммитом.
  Обычный merge использовать, если нужно сохранить цепочку зависимых PR или
  человек явно запросил этот способ. Уже опубликованную историю не переписывать.
- PR описывает итоговый diff и фактически выполненные проверки. После изменения
  итогового SHA перепроверять нужные integration/release gates. Старые или
  локальные результаты не заявлять как CI новой версии.
- Удалять завершённые ветки после проверки их точных HEAD и зависимых PR.
  Невлитую уникальную работу сначала сохранить и проверить в архиве;
  не использовать force push для обхода изменившейся remote ветки.

## Выпуск

- Выпускать milestone из нескольких готовых блоков по их пользовательской
  ценности; не делать bump/tag для каждого PR. Готовность блока — завершённый
  проверенный сценарий с актуальными инструкциями и явными ограничениями.
- Core и Companion планировать как совместимый milestone. Новую версию получает
  только компонент с доставляемыми изменениями; неизменённый компонент остаётся
  на принятой версии. Совместимость выбранной пары подтверждать отдельно.
- Qualification records появляются после получения и проверки точных bytes,
  publication receipt — после публикации и проверки публичных downloads.
  Это минимальные служебные записи, не повод дробить продуктовые изменения.
  Объединять post-release evidence и актуализацию документации в один PR/коммит;
  не создавать ранние фиктивные receipts ради сокращения числа коммитов.

- Следовать `scripts/release/README.md` и `EXPERIMENTAL-LINUX.md`.
  Не перезаписывать опубликованные теги, notes или assets.
- При bump Core проверить явные allowlists Companion/adapter, installed
  verification и имена CI артефактов. Не допускать все будущие версии автоматически.
- Новая поставка требует CI точного source commit, installation/interop,
  manifests, checksums и актуальных ограничений. Core tag указывает на
  `source_commit` принятого ZIP; записи выпуска могут быть закоммичены позже.
- Перед финальным push выполнить полный поиск прежних и новых номеров версий
  по README, docs, integrations, packaging и планам, включая файлы вне текущего
  diff. Проверить все текущие publication/metadata/candidate-утверждения;
  отличать их от датированных origin/evidence и compatibility-history.
  Не переписывать accepted source/tag commits и release records; точные версии
  сохранять в install-командах, контрактах и исторических counts. Планы могут
  ссылаться на READINESS как единый источник актуальной опубликованной пары.
- После публикации скачать публичные файлы и сверить размер/SHA256, затем
  обновить опубликованную пару в README/READINESS/инструкциях/Pages.
  Компонентный prerelease не объявляет готовность полной IDE, AI или live apply.
