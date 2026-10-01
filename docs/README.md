# Документация Рентгена

[Главная](../README.md) · [Скачать опубликованный выпуск](https://github.com/DmitrL-dev/1cai-public/releases)

Выберите задачу. Для первого знакомства достаточно первых трёх документов;
точные контракты нужны при настройке, автоматизации и применении изменений.

## Начать и освоиться

| Документ | Что узнаете |
| :--- | :--- |
| [Первый запуск](../GETTING_STARTED.md) | Что подготовить, как установить Core, сохранить снимок и открыть модуль |
| [Как пользоваться](USER_GUIDE.md) | Термины, действия в редакторе, черновики, проверки и восстановление результата |
| [Возможности и ограничения](CAPABILITIES.md) | Какие маршруты реализованы, где есть частичное покрытие и что подтверждено опытами |
| [Состояние поставки](product/READINESS.md) | Версии, ссылки на CI, публикацию и нативные проверки |
| [Совместимость конфигураций](product/CONFIGURATION-COMPATIBILITY.md) | Какие доказательства есть для форматов и какие не подтверждают типовые конфигурации |

## Установить и подключить инструменты

| Задача | Инструкция |
| :--- | :--- |
| Собрать выбранный Core и зарегистрировать проект | [Core installation](product/CORE-INSTALLATION.md) |
| Собрать воспроизводимый комплект с зависимостями | [Offline kit](product/CORE-OFFLINE-KIT.md) |
| Подготовить отдельный профиль VSCodium / Cline | [Open editor](../integrations/open-editor/README.md) |
| Настроить Companion и узнать его ограничения | [Расширение редактора](../integrations/vscode-rentgen/README.md) |
| Подключить локальный AI-клиент через MCP | [Core MCP](product/CORE-MCP.md) |
| Назначить или отозвать права проекта | [Project access](product/PROJECT-ACCESS.md) |
| Обновить старое состояние проекта | [State migration](product/STATE-MIGRATION.md) и [schema4](product/CORE-INSTALLATION.md#переход-существующего-проекта-на-schema4) |

## Читать исходники и работать с черновиками

| Задача | Инструкция |
| :--- | :--- |
| Найти модули по пути | [Source discovery](product/SOURCE-DISCOVERY.md) |
| Понять сохранённые метаданные | [Snapshot metadata](product/SNAPSHOT-METADATA.md) и [read sessions](product/SNAPSHOT-READ-SESSIONS.md) |
| Сравнить два снимка | [Snapshot diff](product/SNAPSHOT-DIFF.md) |
| Сохранять и открывать версии через CLI | [Draft history](product/DRAFT-HISTORY.md) |
| Управлять черновиками через MCP | [Draft MCP](product/DRAFT-MCP.md) и [большие модули](product/LARGE-DRAFT-MCP.md) |
| Исправить черновик вручную | [Manual draft edit](product/MANUAL-DRAFT-EDIT.md) |
| Подготовить управляемую локальную правку | [Local repair](product/LOCAL-REPAIR.md) |

## Проверить сохранённую версию

| Задача | Инструкция |
| :--- | :--- |
| Установить runtime и выполнить BSL-проверку из CLI | [Proposal check](product/PROPOSAL-CHECK.md) |
| Запустить BSL-проверку в редакторе | [Editor BSL check](product/EDITOR-BSL-CHECK.md) |
| Проверить предложение установленной платформой | [Proposal platform check](product/PROPOSAL-PLATFORM-CHECK.md) |
| Запустить платформенную проверку в редакторе | [Editor platform check](product/EDITOR-PLATFORM-CHECK.md) |
| Подготовить доверенный профиль тестов | [Test profiles](product/TEST-PROFILES.md) и [YAxUnit](product/YAXUNIT-PLATFORM-PROFILE.md) |
| Выполнить тесты версии из редактора | [Editor tests](product/EDITOR-TESTS.md) |

## Применить поддержанную правку

Применение — отдельная операция. Сначала проверьте поддержанный формат,
операцию, права, ожидаемую версию и сценарий восстановления.

| Задача | Инструкция |
| :--- | :--- |
| Изменить один существующий BSL-файл | [Direct BSL apply](product/PROPOSAL-LIVE-APPLY.md) |
| Переименовать реквизит Catalog в Designer XML | [Metadata live apply](product/METADATA-LIVE-APPLY.md) |
| Работать с отдельной принадлежащей копией | [Metadata workspace](product/METADATA-WORKSPACE.md) |
| Посмотреть preview переименования | [Metadata preview](product/METADATA-PREVIEW.md) |
| Подготовить apply и квалифицировать candidate | [Metadata apply](product/METADATA-APPLY.md) и [apply gate](product/METADATA-APPLY-GATE.md) |
| Настроить ограниченный native EDT маршрут | [EDT execution](product/EDT-EXECUTION.md) и [профили](product/EDT-PROFILES.md) |

## Изучить обновления и EDT

| Задача | Инструкция |
| :--- | :--- |
| Сравнить base / current / upstream | [Three-way updates](product/THREE-WAY-UPDATES.md) |
| Сопоставить Designer XML по UUID | [Metadata three-way](product/METADATA-THREE-WAY.md) |
| Узнать семантические границы BSL, форм и СКД | [Three-way semantics](product/METADATA-THREE-WAY-SEMANTICS.md) |
| Получить EDT inventory | [EDT identity inventory](product/EDT-INVENTORY-IDENTITY.md#local-cli) |
| Сравнить три EDT inventory | [EDT identity three-way](product/EDT-IDENTITY-THREE-WAY.md) |
| Разобрать вложенные реквизиты EDT Catalog | [EDT attribute three-way](product/EDT-ATTRIBUTE-THREE-WAY.md) |
| Изучить ограниченный ibcmd цикл | [EDT fixture executor](product/EDT-FIXTURE-EXECUTOR.md) |

Plan или candidate не означают, что обновление типовой конфигурации принято.
Границы покрытий приведены в [матрице совместимости](product/CONFIGURATION-COMPATIBILITY.md).

## Наблюдать за проектом и получать отчёты

| Задача | Инструкция |
| :--- | :--- |
| Следить за изменениями папки выгрузки | [Observer](product/OBSERVER.md) |
| Разбирать Git-находки | [Git watcher](product/GIT-WATCHER.md), [findings](product/GIT-FINDINGS.md), [BSL analyzer](product/GIT-BSL-ANALYZER.md) |
| Привязать Git и снимок к доказательствам | [Git/snapshot evidence](product/GIT-SNAPSHOT-EVIDENCE.md) |
| Собрать отчёт владельца | [Owner report](product/OWNER-REPORT.md) |
| Сохранить и прочитать отчёт через CLI/MCP | [Owner report store](product/OWNER-REPORT-STORE.md) |
| Подключить подтверждённые показатели | [Runtime metrics](product/RUNTIME-METRICS.md) и [экспорт регистра 1С/ERP](product/RUNTIME-SOURCE.md) |
| Отправить и принять уведомление | [Delivery](product/NOTIFICATION-DELIVERY.md) и [receiver](product/NOTIFICATION-RECEIVER.md) |
| Изучить lifecycle Windows-службы | [Service host](product/SERVICE-HOST.md), [installer](product/SERVICE-INSTALLER.md), [process inventory qualification](product/STOCK-PROCESS-INVENTORY-QUALIFICATION.md) |

## Проверить основания и участвовать

- [Архитектура](../ARCHITECTURE.md): границы компонентов и источник истины.
- [План развития](../ROADMAP.md): цели и критерии, которые ещё предстоит выполнить.
- [Daily acceptance](product/DAILY-DEVELOPMENT-ACCEPTANCE.md) и
  [platform acceptance](product/PLATFORM-ACCEPTANCE.md): отдельные критерии приёмки.
- [Аудит](product/AUDIT-20260912.md): выявленные слабые места и приоритеты.
- [Рынок и позиционирование](product/COMPETITOR-MATRIX.md): выбранное направление проекта.
- [Квалификация dev15](product/DEV15-RELEASE-QUALIFICATION-20260928.md):
  связь опубликованной поставки с нативным опытом.
- [Правила участия](../CONTRIBUTING.md): сборка, тесты и подготовка изменений.
- [Issues](https://github.com/DmitrL-dev/1cai-public/issues): вопросы и воспроизводимые проблемы.

Датированные документы и отчёты описывают свой фактический запуск.
Их версии и результаты не становятся подтверждением новой поставки
только потому, что появились более новые исходники.
