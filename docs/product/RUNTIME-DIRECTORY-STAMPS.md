# Проверка каталогов runtime: воспроизводимый ложный отказ

## Что удалось установить 27 сентября 2026

На этом Windows-хосте воспроизведён `BSL_INPUT_CHANGED` после дополнительного
открытия и закрытия каталога **только для чтения**. Файлы не изменялись.
`RuntimePins.verify` сравнивал два результата enumeration, в которых NTFS
обновила кэшированные `write`/`change` поля одной directory entry.

Один опыт сохранил точную неравную пару перед исходным сравнением. Другой
повторил отказ на неизменённом установленном Core dev12, без подмены класса
или Windows operations. В обоих случаях исходная `tree` проверка прошла,
затем дополнительный read-only open/close вызвал отказ. Все 128 файлов и
полные stamps удерживаемых каталогов сохранились.

Это конкретная воспроизводимая причина отказа. Она не устанавливает причины
всех прежних installer/worker/cleanup failures. [Issue #23](https://github.com/DmitrL-dev/1cai-public/issues/23)
остаётся открытым.

## Почему два чтения могут различаться

NTFS хранит в directory entry копию части метаданных объекта. Эта копия может
обновиться при закрытии дополнительно открытого file object, даже если исходный
handle остаётся открытым. Получение метаданных через handle читает свойства
самого объекта. Microsoft описывает этот механизм в
[статье о репликации метаданных NTFS](https://devblogs.microsoft.com/oldnewthing/20111226-00/?p=8813).
Наши наблюдения связывают механизм с directory times в используемом
[GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex).
Это локальное доказательство поведения, не обещание одинакового кэша на всех
версиях Windows или файловых системах.

## Исправление в исходной ветке

Для directory entries `_inventory` получает полный stamp через удерживаемый
no-follow handle. Identity, тип, attributes, creation и final path проверяются
при связывании с enumeration; между проверками сравниваются полные свежие
handle stamps. Реальные изменения directory write/change/size продолжают
отклоняться. В первоначальном `self.stamps` не заменяются значения: момент
захвата inventory отделён от момента первого открытия handle.

File entries, хэши, запрет hardlink/reparse, лимит 1080 handles/uncertain handles,
1024 entries и существующее владение при закрытии сохраняются. Каталоги
удерживаются при перечислении, затем повторно используются обходом дерева.
Повторных попыток после обнаруженного изменения не добавлено.

Этого изменения **нет в принятом ZIP dev12**. Оно проверено в отдельной
исходной ветке `codex/runtime-directory-stamps`. Установленный новый пакет,
штатные installer/service/cleanup и релизные CI ещё требуют отдельной приёмки.

## Проверки исходного исправления

| Проверка | Результат | Граница |
| --- | --- | --- |
| Детерминированный RED на прежнем коде | 3 expected failures: write/change/size кэша | Только enumeration seam управляема; реальные Win32 handles |
| Контракты RuntimePins | 33 passed, 0 failures/errors/skipped | Cache refresh, authoritative mutations, file stamps, membership, path, hardlinks, budget, callback, закрытие при ошибке и OwnedAttempt cleanup |
| Регрессия Git/service | 337 passed, 0 failures/errors/skipped | Шесть тестовых файлов; не весь Product checks |
| Новый native опыт на исправленных исходниках | 9 read-only reopens прошли; 9 обновлений кэша действительно наблюдались | Без подмены класса/operations; не установленный релиз |

В последнем native опыте полные удерживаемые stamps до/после совпали,
inventory размеров/SHA256 128 файлов совпал, все собственные handles закрыты.
Модуль исправленных исходников имел SHA256
`5ab0e566086aa2571bf2b2daeafd31c3942401cbe92fb23ee7d34034b94f4d72`.
Предварительный опыт до выравнивания CRLF также прошёл с шестью обновлениями
кэша; приёмочная строка выше относится к окончательным байтам исходного модуля.

[Компактная квитанция](evidence/runtime-directory-stamps-20260927.json) связывает
сырые локальные receipts, хэши модулей, RED/GREEN и регрессию. Локальные receipts
являются свидетельством исполнителя, не внешней аттестацией.

Повторить автоматические контракты в Windows из исходной ветки:

```powershell
python -m pytest -q tests/unit/test_runtime_pins.py tests/unit/test_git_bsl_analyzer.py tests/unit/test_git_watcher.py tests/unit/test_service_composition.py tests/unit/test_service_entry.py tests/unit/test_service_installer.py
```

Native опыт требует нового собственного дерева: создать 16 подкаталогов по
8 файлов, сохранить ожидаемые размеры/хэши, вызвать штатный `RuntimePins.tree`,
отдельно открыть/закрыть read-only handle каталога и вызвать `verify`. Для
положительной приёмки исправления недостаточно отсутствия ошибки: требуется
зафиксировать хотя бы одно реальное обновление кэшированного timestamp при
неизменных retained stamps и bytes. Если обновления не наблюдалось, такой опыт
не подтверждает данный сценарий.
