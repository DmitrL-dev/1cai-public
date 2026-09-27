# Runtime directory stamps: план реализации

> Исполняет основной агент без субагентов, согласно указанию владельца.
> Навыки: writing-plans, executing-plans, test-driven-development и
> verification-before-completion. Продолжение локальной реализации разрешено
> действующим поручением; production deployment требует отдельного разрешения.

**Goal:** исключить ложный отказ при обновлении кэшированных directory times,
сохранив обнаружение настоящих изменений и владение файловыми handles.

**Architecture:** полный directory stamp в inventory берётся через retained
handle; enumeration задаёт membership и проверяемую привязку. File stamps,
хэши, hardlink/reparse guards, тип ошибок и cleanup ownership сохраняются.

**Tech Stack:** Python 3.11, ctypes Win32, pytest, установленный Core dev12 для
исходной репродукции. [Спецификация](../specs/2026-09-27-runtime-directory-stamps-design.md).

## Ограничения

- Основная копия `E:/Rentgen` остаётся на main для выпуска dev12.
- Отдельная копия `E:/Rentgen-worktrees/git-audit-cold-recheck-dev11`, ветка
  `codex/runtime-directory-stamps`, основа `35361853927c13c6152aa9860146865efc10e90f`.
- 1080 handles/uncertain, 1024 inventory entries, 512 MiB bytes не увеличиваются.
- Повторные попытки, игнорирование настоящих directory mutations, изменения
  общих core Win32 primitives и перезапись dev12 assets не допускаются.

## 1. Воспроизведение и RED

- [x] Сохранить instrumented неравную пару и повтор на неизменённом установленном
  классе; проверить сохранность полных directory stamps и file inventory.
- [x] Подготовить свободную чистую копию без потери старой merged-ветки.
- [ ] Создать `tests/unit/test_runtime_pins.py`. Для timing-independent
  воспроизведения наследовать WindowsHandleOps, сохранив настоящие opens,
  stamps, final paths и closure; только directory entries enumeration выдавать
  сначала с сохранёнными значениями, затем с изменённым write/change/size.
- [ ] Параметризованный тест `test_directory_cache_refresh_preserves_runtime`
  вызывает `pins.tree`, переключает cache phase, вызывает `pins.verify`, затем
  закрывает pins. Ожидание — успех и отсутствие оставшихся собственных handles.
  На старом коде ожидается `PinFailure: BSL_INPUT_CHANGED` при verify.

Команда из отдельной копии:

```powershell
$py = 'C:/Users/chg/AppData/Local/Temp/rentgen-readiness-evidence-20260927/test-env/Scripts/python.exe'
& $py -B -m pytest -q -p no:cacheprovider tests/unit/test_runtime_pins.py -k directory_cache_refresh --tb=short
```

## 2. Исправление и инварианты

- [ ] В `_inventory` перед append нормализовать только directory entries:
  получить `handle = self.directory(child)`, свежий stamp через `_call`, проверить
  directory/type, identity enumeration/initial pin, attributes, creation и final
  path. При несовпадении выбросить `PinFailure("BSL_INPUT_CHANGED")`; в result
  добавить `(name, retained)`. Files добавить как прежде.
- [ ] Пройти RED-тесты; добавить негативные проверки настоящих directory
  write/change/size/attributes/creation/identity/type изменений, file stamp
  изменений и неправильного final path. Для этих проверок seam меняет только
  authoritative результат нужного Win32 чтения, остальные операции настоящие.
- [ ] Проверить deduplication, resource bound перед дополнительным open,
  callback failure и закрытие всех собственных handles после admission error.
- [ ] Проверить настоящую `OwnedAttempt.create` → capture inventory → cleanup
  на собственном временном дереве, без изменения lifecycle implementation.
- [ ] Узкая регрессия: новый файл, git_bsl_analyzer, git_watcher,
  service_composition, service_entry и service_installer. Сохранить JUnit.
- [ ] Корневое ревью diff: отсутствие изменения file/hardlink guards, увеличение
  числа handles только за счёт ранее открываемых при tree/cleanup каталогов,
  отсутствие retry и корректный initial/current timestamp lifetime.

## 3. Native proof и поставка

- [ ] Повторить read-only reopen на отдельном свежем дереве с исправленным кодом.
  Проверить original bytes, directory identity и закрытие handles.
- [ ] Подготовить новый кандидат и штатную native installer/service/cleanup
  проверку после завершения текущей публикации dev12. Не объявлять исправленными
  исторические случаи, для которых нет доказательства причины.
- [ ] Обновить протокол/issue #23, описав контролируемую репродукцию и область
  исправления; провести новые source/final/main CI и подробный релиз.

## Самопроверка плана

Спецификация покрыта тремя задачами. Позитивная cache-проверка и отрицательные
authoritative mutation-проверки различают источники метаданных. Cleanup и лимиты
имеют отдельные gates; они не выводятся из единственного положительного теста.
Успешный новый пакет не превращает всю платформенную матрицу в принятую.
