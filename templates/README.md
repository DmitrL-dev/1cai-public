# Templates

> Обновлено: 10 ноября 2025  
> Основано на принципах GitHub Spec Kit (см. `docs/research/spec_kit_analysis.md`). Благодарим авторов репозитория [github/spec-kit](https://github.com/github/spec-kit) за идеи и структуру.

## Назначение

Каталог `templates/` содержит заготовки для спецификаций, планов и исследовательских записок. Используются скриптом `scripts/research/init_feature.py`, который создаёт каркас `docs/research/features/<slug>/`.

## Файлы

| Шаблон | Описание |
|--------|----------|
| `feature-plan.md` | Краткий план работы: цели, выходы, связи с продуктом. |
| `feature-spec.md` | Спецификация: контекст, ограничения, приемочные критерии, риски. |
| `feature-tasks.md` | Разбиение на задачи, зависимости, согласование с командами. |
| `feature-research.md` | Исследовательские заметки, ссылки, выводы. |

## Как использовать

1. Запустите `make feature-init FEATURE=<slug>` (или напрямую `python scripts/research/init_feature.py --slug <slug>`).  
2. Получите каталог `docs/research/features/<slug>/` с четырьмя отмеченными файлами.  
3. Заполните каждый документ по разделам; удалите подсказки `TODO`.  
4. Обновите `README.md`, `CHANGELOG.md` и другие документы проекта, ссылаясь на новые материалы.

## Благодарности

- [github/spec-kit](https://github.com/github/spec-kit) — источник вдохновения для spec-driven подхода.  
- Сообщество 1C AI Stack — за адаптацию методологии под экосистему 1С.

## Пример заполнения

- Смотрите свежий пример в `docs/research/features/marketplace-packages/` (план, спецификация, задачи и исследование по публикации пакетов Marketplace).


