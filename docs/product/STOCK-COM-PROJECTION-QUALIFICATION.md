# Исправление чтения COM-коллекции процессов: доказательства и следующий кандидат

## Что исправлено

Проверщик Windows-службы получает локальную WMI-коллекцию `SWbemObjectSet`.
PowerShell передавал её в конвейер одним объектом. Код пытался прочитать
`Properties_` у коллекции и завершался ошибкой до измерения первого baseline.
Теперь проверщик читает `Count` и каждый процесс через `ItemIndex`.

Запрос использует флаг16: [Count не поддерживает ForwardOnly32](https://learn.microsoft.com/en-us/windows/win32/wmisdk/swbemobjectset-count).
[ItemIndex](https://learn.microsoft.com/en-us/windows/win32/wmisdk/swbemobjectset-itemindex)
возвращает отдельный `SWbemObject`, у которого читаются свойства процесса.
Недоступный Count получает явный отказ до преобразования к числу; отрицательное
число и больше100 строк также получают отказ до обхода.

Запрос остаётся локальным и фиксированным. Область временной Debug привилегии,
исходный удержанный объект службы, SID LocalService, родитель/PID/образ/argv,
200 наблюдений,10 секунд на capture и32768 байт на поток сохраняются.
Проверка неполных образов и отказ очистки при неизвестных потомках сохраняются.

## Оба исходных CI49f

Исходник `49f8347507f3a579cc651f885f937d5e4fe0f8c2` не принят.
Оба original attempt1 завершились failure; их не перезапускали и не отменяли.

| Запуск | Event | Stock PID | Результат |
|---|---|---:|---|
| [36414749721](https://github.com/DmitrL-dev/1cai-public/actions/runs/36414749721) | pull_request |8036| Ошибка COM-проекции; cleanup не принят |
| [36414744469](https://github.com/DmitrL-dev/1cai-public/actions/runs/36414744469) | push |856| Ошибка COM-проекции; cleanup не принят |

В каждом run прошли2929 Python,71 Node и два Go package passes, без пропусков.
Все684 прежних local identities присутствуют в настоящих CI JUnit.105 собственных
файлов wheel побайтно равны Git49f. Сохранены оба комплекта из пяти artifacts;
проверены10 внешних ZIP SHA/size и отдельный checkout каждого из четырёх jobs.
PR собирался из synthetic merge53f5 с parents[c715,49f] и тем же treeb5e6.
Actual offline CI SDK receipts содержат32 full и3 scoped tools. Эти receipts
связаны с producer/source/log; повторное независимое хэширование неэкспортированных
CI site-packages этой записью не заявлено.

SourceObserver5 и Git diagnostic1 приняты каждый в своей области: их очистка
подтверждена. Full stock достиг RUNNING под LocalService, исходный удержанный
объект после STOPPED reap выполнен. Три Debug scopes восстановили точно24
исходных привилегии. Две WMI-команды вернули exit1, пустой stdout и89 байт
stderr с ошибкой обращения к null; совпадают с точным AST source49f.

Для full stock `measurement=null`, `retention=null`, `service_exists_after=true`.
Cleanup отказал в stock_process_lifetime, retention и remaining_service.
Первый baseline, Java и восстановление ACL/owners этой попыткой не приняты.
Это отдельный сбой от исторического62ef, где были неполные строки процессов
и успешная очистка. [Подробная запись обоих runs](evidence/stock-scm-com-projection-ci-failure-20260928.json).

## Проверка исправления

Новая регрессия исполняет полный PowerShell script из AST исходника над
объектом коллекции, который не перечисляется через pipeline. Она проверяет
0/1/2/100 строк, отказ101 до чтения ItemIndex, сохранение null image/argv и
ошибки query/count/index/property. Native WMI и привилегии в этих тестах не используются.

- Старый код:10 failures/1 pass из11 случаев; ошибка null воспроизведена.
- Первый индексный вариант:1 failure/43 passes; ошибка getter Count превращалась
  в null и затем в0. Добавлен явный отказ при недоступном Count.
- Итоговый узкий набор:44 passes, zero skip/error/failure; из них11 новых случаев.
- Отдельный будущий raw reader:97 pure parser passes; обязательны exact AST16,
  null Count отказ, лимит100 и ItemIndex. Исторические readers сохранены.
- Actual source collection:2940 Python cases; ожидаемый local identity union695.
  Это сбор списка тестов; полный новый CI ещё должен их выполнить.
- Реальный readonly ownPID probe на PowerShell7.6.5 прочитал PID/parent/image/argv
  из текущего исправленного исходника. Из запроса удалён только Debug-вызов,
  селектор ограничен PID самой проверки. SCM control и изменения токена отсутствуют.
  Эта проверка не квалифицирует LocalService или Java.

[Хеши и границы локальных проверок](evidence/stock-scm-com-projection-local-20260928.json).
Небольшое исправление документации также добавляет dev16 в список новых editor profiles.

## Обязательные следующие проверки

Новый exact source должен пройти оба исходных push/PR attempt1 с2940 Python,
71 Node, двумя Go packages,695 local identities и105 wheel source files.
Нужны собственные raw доказательства пяти SourceObserver lifetimes, отдельной
Git diagnostic lifetime и всех пяти full stock групп:

1. Первый холодный baseline с настоящим Java/BSL и durable публикацией.
2. CommitB только при STOPPED; второй Java/BSL и полные findings.
3. Штатный STOP неизменённой головы, reap исходного удержанного объекта,
   отсутствие потомков/lease/повторной публикации.
4. Прерывание quiet wait, отказ restart, явное recovery и неизменённая голова.
   Это не доказательство прерывания активного BSL-процесса.
5. Refusal историиA до capture, восстановлениеB, утрата прав LocalService/context
   и отказ с восстановлением исходного состояния.

Границы остаются: пять positive lifetimes,14 control receipts, два реальных Java,
три свежих отказа, чистая очистка, restoration owners/DACL/privileges и retained
SQLite/JSON. После них квалифицируются точный merged main, новая offline-установка
и неизменяемые component releases с подробным анонсом и анонимным readback.
Тег Core указывает на embedded source commitC; release records находятся в
потомкеR; tag Companion использует checkout с этими records.

## Полная продуктовая готовность

Эта правка закрывает конкретный сбой CI. Далее остаётся отдельный daily slice:
точная AI revision → тот же immutable функциональный oracle → отдельный
semantic verdict. Исторический AI candidate revision2 поглотил ошибку записи;
ручная revision3 не заменяет проверку результата модели. Private contract16
проверяет построенные отчёты и provenance, но не является native functional acceptance.
Метаданные/формы/СКД, типовая конфигурация, качество/стоимость/время моделей,
длительный pilot и остальные product requirements требуют отдельных доказательств.
Новый релиз и production deployment пока не подтверждены.
