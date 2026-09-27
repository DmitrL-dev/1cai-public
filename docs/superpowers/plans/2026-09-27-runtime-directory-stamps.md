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
- [x] Создать `tests/unit/test_runtime_pins.py`. Для timing-independent
  воспроизведения наследовать WindowsHandleOps, сохранив настоящие opens,
  stamps, final paths и closure; только directory entries enumeration выдавать
  сначала с сохранёнными значениями, затем с изменённым write/change/size.
- [x] Параметризованный тест `test_directory_cache_refresh_preserves_runtime`
  вызывает `pins.tree`, переключает cache phase, вызывает `pins.verify`, затем
  закрывает pins. Ожидание — успех и отсутствие оставшихся собственных handles.
  На старом коде ожидается `PinFailure: BSL_INPUT_CHANGED` при verify.

Команда из отдельной копии:

```powershell
$py = 'C:/Users/chg/AppData/Local/Temp/rentgen-readiness-evidence-20260927/test-env/Scripts/python.exe'
& $py -B -m pytest -q -p no:cacheprovider tests/unit/test_runtime_pins.py -k directory_cache_refresh --tb=short
```

## 2. Исправление и инварианты

- [x] В `_inventory` перед append нормализовать только directory entries:
  получить `handle = self.directory(child)`, свежий stamp через `_call`, проверить
  directory/type, identity enumeration/initial pin, attributes, creation и final
  path. При несовпадении выбросить `PinFailure("BSL_INPUT_CHANGED")`; в result
  добавить `(name, retained)`. Files добавить как прежде.
- [x] Пройти RED-тесты; добавить негативные проверки настоящих directory
  write/change/size/attributes/creation/identity/type изменений, file stamp
  изменений и неправильного final path. Для этих проверок seam меняет только
  authoritative результат нужного Win32 чтения, остальные операции настоящие.
- [x] Проверить deduplication, resource bound перед дополнительным open,
  callback failure и закрытие всех собственных handles после admission error.
- [x] Проверить настоящую `OwnedAttempt.create` → capture inventory → cleanup
  на собственном временном дереве, без изменения lifecycle implementation.
- [x] Узкая регрессия: новый файл, git_bsl_analyzer, git_watcher,
  service_composition, service_entry и service_installer. Сохранить JUnit.
- [x] Корневое ревью diff: отсутствие изменения file/hardlink guards, увеличение
  числа handles только за счёт ранее открываемых при tree/cleanup каталогов,
  отсутствие retry и корректный initial/current timestamp lifetime.

## 3. Native proof и поставка

- [x] Повторить read-only reopen на отдельном свежем дереве с исправленным кодом.
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

## Проверено в исходной ветке

33 новых контракта и узкая регрессия из 337 тестов прошли. Native repeat на
окончательных байтах исходного модуля прошёл с 9 наблюдаемыми обновлениями
кэша. [Протокол](../../product/RUNTIME-DIRECTORY-STAMPS.md) и машинная квитанция
сохраняют RED, оба исходных отказа и границы новой проверки.

## Подготовка следующего кандидата

Публикация dev12 и Companion 0.1.12 завершена. Подготовлены версии Core
`0.1.0.dev13` и Companion `0.1.13`, расширены явные списки совместимости без
удаления старых версий, обновлены пути CI и установленных verifier. Неизвестная
версия `dev999` по-прежнему отклоняется. Один новый RED-кейс подтвердил отказ
прежнего адаптера. После изменения прошли 77 Python-тестов совместимости,
поставки и live apply/recovery, а также 65 Node-контрактов.
[Квитанция](../../product/evidence/runtime-directory-stamps-compat-20260927.json).
Новый установленный комплект и полные CI ещё предстоит квалифицировать.

## Уточнение 27 сентября: native DACL и новые исходники

Локальный установленный `64197b7` прошёл runtime/service/cleanup и отрицательный
JAR-контроль; два полных CI дали 2423 passed / 1 failed. Предварительная
интерпретация Win32 creation failure исправлена после прямой диагностики:
CreateDirectoryW успешен, отказ вызван представлением RID 500 как `LA` при
строковом сравнении DACL. Диагностические ревизии `1e96838` и `cc7e7f6`
сохраняют исходные failures. Сокращённая проверка перед полной suite ускоряет
наблюдение; ни один прежний failure не переобъявляется успешным.

- [x] Получить actual SID, успешный native CreateDirectoryW и прочитанный DACL
  из обоих CI. Подтвердить alias rendering отдельным локальным Win32 опытом.
- [x] Добавить RED-контракты SY/LS/NS и отрицательные проверки различий ACL.
- [x] Сравнивать оба descriptor через одну native-репрезентацию, сохранив
  проверку всей DACL, владение buffers/handles и отказ при ошибке освобождения.
- [x] Проверить 48 локальных ACL/runtime контрактов.
- [x] Закончить регрессию 352 Git/service/ACL контрактов и записать квитанцию.
- [ ] Квалифицировать новые source push/PR CI и новый установленный wheel.
- [ ] Оформить релизные записи, final/main CI и подробную публикацию dev13.

В эту ветку не переносится отдельное исправление раннего Python -O guard
из issue #25; оно сохранено на своей локальной ветке.
