# Работа с Рентгеном

## Сначала установить факты

- Центральные входы: `README.md`, `ROADMAP.md`, `docs/README.md` и
  `docs/product/READINESS.md`. Ближайшая сверка —
  `docs/product/RELEASE-PLAN-20261015.md`; исторические планы и evidence не
  являются результатами текущего HEAD.
- Проверить `git status`, remote main, открытые PR и актуальный diff перед
  изменениями. Сохранять чужие незакоммиченные правки; работать в одной ветке
  задачи или отдельном worktree при необходимости изоляции.
- Изменение поведения сопровождается узкой воспроизводимой проверкой.
  Отсутствующий runtime или неудачная проверка — ограничение, а не успех.

## Границы и проверки

- Продуктовый комплект: Windows x64 / CPython 3.11. Linux state/ZIP/GUI —
  отдельный экспериментальный маршрут, принимаемый на GNU/Linux x86_64.
  Наличие pure-Python wheel не означает поддержку всех команд или macOS.
- Python: `python -m pytest -q <relevant tests>`; полный Windows suite и
  installed-kit/SCM проверки выполняет `.github/workflows/core-ci.yml`.
- Companion: `node --test integrations/vscode-rentgen/test/*.test.cjs
  scripts/verification/companion_host/*.test.cjs`.
- Go scanner: `go -C go test ./...`. Rust input core: pinned toolchain и
  `--locked` из portable workflow. Браузерные проверки GUI: все gates из
  `.github/workflows/gui-browser-ci.yml`, настоящий helper и sandbox.
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
- Пушить проверенные тематические изменения; PR описывает итоговый diff и
  фактически выполненные проверки. Не заявлять старые или локальные тесты как CI.
- Удалять завершённые ветки после проверки их точных HEAD и зависимых PR.
  Невлитую уникальную работу сначала сохранить и проверить в архиве;
  не использовать force push для обхода изменившейся remote ветки.

## Выпуск

- Следовать `scripts/release/README.md` и `EXPERIMENTAL-LINUX.md`.
  Не перезаписывать опубликованные теги, notes или assets.
- При bump Core проверить явные allowlists Companion/adapter, installed
  verification и имена CI артефактов. Не допускать все будущие версии автоматически.
- Новая поставка требует CI точного source commit, installation/interop,
  manifests, checksums и актуальных ограничений. Core tag указывает на
  `source_commit` принятого ZIP; записи выпуска могут быть закоммичены позже.
- После публикации скачать публичные файлы и сверить размер/SHA256, затем
  обновить опубликованную пару в README/READINESS/инструкциях/Pages.
  Компонентный prerelease не объявляет готовность полной IDE, AI или live apply.
