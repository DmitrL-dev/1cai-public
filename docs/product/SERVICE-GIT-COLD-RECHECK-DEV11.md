# Core dev11: повторная проверка первого полного GitAuditWorker на новом runtime

25 сентября 2026 года по местному времени проведены два дополнительных
**ограниченных локальных** прогона установленного публичного Core `0.1.0.dev11`.
В каждом официальный JDK ZIP заново распакован в отдельный каталог, публичный
`install_bsl_runtime.py` создал новый diagnostics root с 490 файлами JDK и
закреплённым BSL-LS JAR. Затем `rentgen-service --console` выполнил первый
полный цикл GitAuditWorker на отдельном новом профиле. Проверены schema 3 и
schema 2. Оба первых цикла завершились `analyzed`; повторные циклы не создали
повторного `analyzed`.

Это положительная контрпроба к непостоянному отказу из
[issue #23](https://github.com/DmitrL-dev/1cai-public/issues/23), **не** его
исправление и **не** полная приёмка холодной установки.

## Привязка входов

Использована ранее сверенная установка [Core dev11](https://github.com/DmitrL-dev/1cai-public/releases/tag/core-v0.1.0-dev11):
принятый ZIP SHA256
`9351d2b8790a358f66931a3067e8ba1823b61b7ca6b97989bb430f8fd124441a`,
wheel `74cfe4a4f00369e13ef87c084ab1b62a016ac0661217fba015d5bccc831877b6`,
`bsl-scan.exe` `8d81c1eda05d9c358385396861eb1df611d83489582f7293ad461c45017817c4`.
Скрипт установки из публичного исходного дерева имел SHA256
`398759a7aa0d6d533b7b3711523f0abe4e8dc5d06c5de43e6ad3f745cdab377d`.
Оба запуска использовали один и тот же официальный Temurin JDK ZIP SHA256
`f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e`
и BSL-LS 1.0.5 JAR SHA256
`de97f571e6474c5c151cf859294f589ee01152de3b4826b43e1a80b69ee2602a`.
Installer завершился `installed` в обоих отдельных корнях; после циклов JAR
сохранил закреплённый SHA256, в каждом установленном JDK было 490 файлов.

Использован **уже зарегистрированный** собственный синтетический Git-проект
с одним BSL-модулем. Его commit
`3b6a1eeee6ef246ab5e97a405a25f9b009837ea3`, snapshot
`b338d2b477aacfe3c3b980676595c59329ec6ccc5e3344166b16e85de13a9d6e`
и SHA256 модуля
`b057c96c16816b8fe835b62b6a6cde9ab8556653b3021676880bde3ccc59f5b9`
не изменились. Git working tree оставался чистым. Новую регистрацию проекта и
новый Git-коммит эти прогоны не проверяют.

## Наблюдаемые циклы

| Сценарий | Первый полный цикл | Повторный цикл |
| --- | --- | --- |
| Schema 3, новый runtime и новый профиль, config SHA256 `0da86491d594eaa7ef03efa2de694688278874f1af33e2045ba71d119bc939b7` | Exit 0, `cycles=1`, единственное outbox-событие `analyzed`, `git_source_verified`, полный отчёт, 0 findings | Exit 0, `cycles=1`; outbox сохранил ровно одно `analyzed`, без новой записи для `unchanged` |
| Schema 2, новый runtime и новый профиль, config SHA256 `a09780cf8f969887d24c8b508b34ad543cfce4468c53d79d9f375c892f2fd727`; snapshot заранее опубликован публичным `rentgen-observer` | Exit 0, `cycles=1`, первое событие `analyzed`, `git_source_verified`, полный отчёт, 0 findings | Exit 0, `cycles=1`; второе событие `unchanged`, повторного `analyzed` нет |

До каждого первого worker-цикла outbox соответствующего нового профиля
отсутствовал. Путь `BslGitAnalyzer` принимает результат только при
`runtime_verified=true` и `diagnostics_complete=true`; иначе полный отчёт
`analyzed` не публикуется. Для schema 2 вновь созданный owner report прочитан
публичным `rentgen owner-report-get`: качество `available`, provenance
`git_source_verified`, привязка к тому же commit/snapshot. Для schema 3
worker **переиспользовал** исторический owner report из общего project store;
новым доказательством здесь являются первый полный цикл на новом runtime,
новый профиль и его outbox, а не создание нового отчёта или snapshot.

Машинная [ограниченная квитанция](evidence/service-git-cold-recheck-dev11-20260925.json)
содержит входные SHA256, результаты обеих схем, хэши локальных config,
stdout/stderr schema 2, журналов и outbox после повторных циклов, а также
пределы проверки. Её SHA256 —
`50603896237338c0fd67cb4edb1dab89623c3825011340f53e920cc313f9d499`.
Сами локальные config и журналы остаются вне Git, поскольку содержат пути
хоста; квитанция не содержит путей хоста или SID.

## Предел доказательства

Это один Windows-хост, одна локальная учётная запись, один ранее
зарегистрированный синтетический проект и два новых runtime. Положительные
первые циклы показывают, что отказ `BSL_INPUT_CHANGED` **не возникает на каждой**
свежей установке даже для полного GitAuditWorker. Они не объясняют прежние
отказы после распаковки и пауз 5/30 секунд. [Issue #23](https://github.com/DmitrL-dev/1cai-public/issues/23)
остаётся открытым; полная детерминированная приёмка первого цикла не заявлена.

Windows SCM, отдельная service account, внешний конкурентный writer,
представительные `.cf/.cfe`, живая ИБ, публичный HTTPS/DNS и production
deployment не проверялись. Продуктовый код, бинарники, tag и вложения релиза
этой доказательной правкой не меняются.
