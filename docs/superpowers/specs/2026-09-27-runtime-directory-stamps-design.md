# Runtime directory metadata: устранение воспроизводимого ложного отказа

## Цель и основание

Сохранить строгую проверку runtime и owned attempt, устранив отказ
`BSL_INPUT_CHANGED`, который воспроизводится после отдельного открытия и
закрытия каталога только для чтения. Эта работа входит в действующее поручение
по продуктовой готовности. Отдельное одобрение владельцем именно этого текста
не заявляется. Работа выполняется основным агентом без субагентов.

Основа — main `35361853927c13c6152aa9860146865efc10e90f`. Он содержит принятый
диагностический срез dev12; его текущая публикация продолжается отдельно.
Изменение pinning не входит в неизменяемые артефакты dev12.

## Доказательство дефекта

27 сентября на установленном dev12 выполнены два опыта на новых собственных
деревьях, каждое из 128 файлов в 16 каталогах. Исходная `RuntimePins.tree`
прошла. Затем дополнительный read-only handle каталога открыт и закрыт;
`RuntimePins.verify` отказал на сравнении inventories (строка 191).

- Инструментированный опыт сохранил именно возвращённый перед сравнением
  tuple: у `d01` изменились только `write` и `change`, identity, attributes,
  creation, size и состав из 16 записей совпали. SHA256 квитанции:
  `8e5c420819748fc0ce72120a3edf5c71074976cd51f2518b8927a60e88ece3f7`.
- Повтор на неизменённом установленном классе и штатных Windows operations,
  без monkeypatch, воспроизвёл отказ после `d00`. SHA256 квитанции:
  `26942b09db91696ea02dcdc2ca70421ef83ea9e02814e623473a35fb27916aed`.
- В обоих опытах полные stamps удерживаемых каталогов до/после и полный
  inventory размеров/SHA256 файлов совпали. Установленный `_runtime_pins.py`
  имеет SHA256 `3bba1041347a0aea6f806029edbe8dcdf2e425501995c94d34c910a2a7d1760f`.

Это доказательство конкретного дефекта сравнения на данном Windows-хосте.
Оно не устанавливает задним числом причину каждого старого отказа installer,
worker или cleanup в issue #23.

Microsoft описывает метаданные directory entry как копию свойств объекта,
которая может обновляться при закрытии отдельно открытого file object:
[Raymond Chen, NTFS metadata replication](https://devblogs.microsoft.com/oldnewthing/20111226-00/?p=8813).
API и классы используемых структур:
[GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex).
Применимость к наблюдаемым directory timestamps подтверждена нашими опытами;
одна эта статья не служит доказательством исторического отказа.

## Рассмотренные варианты

1. **Выбран:** для каталогов строить inventory stamp из удерживаемого
   no-follow handle. Сверять имя, identity, тип, attributes, creation и final
   path с перечислением/удерживаемым объектом. Полные authoritative stamps
   сравниваются между inventory-проверками.
2. Игнорировать directory timestamps в равенстве. Этот вариант теряет
   проверку реального изменения метаданных каталога и не выбран.
3. Повторять enumeration или предварительно открывать/закрывать всё дерево.
   Это меняет момент наблюдения, маскирует некоторые изменения и не даёт
   устойчивого контракта. Этот вариант не выбран.

## Изменение

Изменяется только `rentgen_diagnostics/_runtime_pins.py` и его проверки.
В `_inventory(path)` каждый directory entry связывается с `path / name`:

1. Существующий `directory(child)` удерживает no-follow handle и дедуплицирует
   цепочку ancestors, с прежним пределом 1080 handles/uncertain handles.
2. Свежий `ops.stamp(handle)` должен описывать каталог с тем же identity,
   что enumeration и первоначально удерживаемый объект. Enumeration attributes
   и creation должны совпадать с handle; final path должен быть ровно child.
   Несовпадение даёт `BSL_INPUT_CHANGED`, ошибки Win32 сохраняют прежний
   `PinFailure` mapping. Reparse-отказ остаётся в WindowsHandleOps.
3. В inventory сохраняется полный свежий handle stamp. Таким образом,
   write/change/size не берутся из устаревающей directory entry, но их реальные
   изменения между проверками продолжают вызывать отказ.
4. File entries сохраняются полностью, включая их исходные timestamps/size.
   Проверки file hash, hardlinks и `_retained_stamp` не меняются.

Форма tuple и порядок сортировки остаются прежними. `_inventory` начинает
удерживать встреченные каталоги раньше, чем `tree`/cleanup обходят их; один
путь по-прежнему имеет один принадлежащий `RuntimePins` handle. Новые handles
закрываются общим `close`, включая путь ошибки. Лимиты entries, bytes и глубина
cleanup не увеличиваются. Класс не получает retries или обхода отказа.

## Затронутые потребители

- `RuntimePins.tree`: runtime installer и BSL admission.
- `watch_directory` для owned BSL source.
- `OwnedAttempt.capture_cleanup_inventory` и проверка пустоты перед удалением.

Свежий stamp берётся в момент inventory, а не из старого `self.stamps`:
каталоги report/tmp законно меняются до захвата cleanup inventory. Глобальная
проверка ранее удержанного directory handle сохраняет проверку type/identity;
она не превращается в запрет всех изменений до первой watch-проверки.

## Приёмка

- Детерминированный тест реального RuntimePins с контролируемой только Win32
  enumeration seam сначала падает на старом коде при обновлении кэша directory
  write/change/size, затем проходит.
- Реальное изменение authoritative directory stamp, file stamp, identity,
  attributes, creation, final path или membership приводит к отказу.
- Дедупликация handles, предел ресурсов, check callback и владение handles при
  ошибке не ослаблены. OwnedAttempt выполняет обычную очистку.
- Повтор отдельного native read-only reopen на исправленном коде сохраняет
  bytes и проходит; отдельные native installer/service/cleanup checks нужны
  для принятия нового пакета. Старые провалы остаются в evidence.
- Версии/релизные записи готовятся после принятия исправления. Полная готовность
  продукта, Windows SCM и production deployment этим срезом не заявляются.
