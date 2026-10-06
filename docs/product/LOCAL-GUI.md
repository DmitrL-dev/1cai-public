# Локальная графическая рабочая область

Статус: **новый экспериментальный срез из исходников, ещё не опубликованный GUI-релиз**.
Визуальный интерфейс работает в браузере, анализ ZIP использует существующий Rust input core
и Python authorization/parser. Принятый Linux binary Core dev17 подходит для этого среза.
Весь продукт, Windows/macOS GUI, живые базы и командные операции этим не квалифицируются.

## Первый рабочий сценарий

1. Запустить локальный GUI для явно выбранного проекта.
2. Открыть выданную ссылку в браузере на том же компьютере.
3. Выбрать или перетащить ZIP-выгрузку Designer XML.
4. Дождаться проверки ZIP и чтения структуры. Можно отменить передачу или анализ.
5. Исследовать объекты и модули, найти запись по имени/пути, посмотреть свойства,
   UTF-8 исходник и SHA-256. Модули около объекта определяются только по пути его папки,
   это не семантический граф зависимостей.

Приложение читает только загруженные байты. Оно не изменяет исходный архив,
живую базу, исходники проекта, registry, membership, head, snapshots или drafts.
Новый выбранный ZIP полностью принимается до анализа. Если он не проходит проверку,
предыдущий успешный результат остаётся доступным.

## Запуск из checkout

Нужны Python 3.11+, GNU/Linux x86_64 и проверенный Rust input core из
[экспериментального дополнения dev17](https://github.com/DmitrL-dev/1cai-public/releases/tag/core-v0.1.0-dev17).
Требования Linux runtime совпадают с [Rust input core](RUST-INPUT-CORE.md).
Никакие npm/framework/server dependencies не добавлены. Файлы интерфейса входят в package.

Сначала один раз явно создайте изолированные identity, registry и проект по инструкции
[переносимого ядра](PORTABLE-CORE.md). Не используйте чужую identity или production state
для ознакомительного запуска.

```sh
python -m rentgen_core.gui \
  --registry /absolute/registry.sqlite3 \
  --identity-profile /absolute/private/identity.json \
  --project <project-uuid> \
  --input-core /absolute/rentgen-input-core \
  --input-core-sha256 <verified-binary-sha256> \
  --open-browser
```

После установки новой сборки аналогичная команда называется `rentgen-gui`.
Это не означает, что GUI уже есть в опубликованном wheel dev17.
Port по умолчанию выбирается OS. При необходимости `--port 8765` задаёт фиксированный порт.
Host всегда `127.0.0.1`; произвольный listen address не принимается.

Ссылка запуска содержит временный случайный ключ сеанса в fragment.
Не пересылайте ссылку и не включайте её в журналы или скриншоты.
Интерфейс убирает ключ из адресной строки и хранит его только в памяти вкладки.
После обновления/закрытия вкладки нужно снова открыть исходную ссылку запуска.
Перезапуск процесса делает старую ссылку недействительной.
Остановка: Ctrl+C в терминале. Приложение отменяет активную операцию, дожидается
завершения дочернего процесса и удаляет собственные временные файлы.
После аварийного kill могут остаться временные файлы в закрытой OS temp-папке;
автоматическое удаление неизвестных каталогов не выполняется.

## Границы результата

- Только ZIP Stored/Deflate без пароля, ZIP64, multipart и небезопасных путей.
- Designer XML расположен прямо в корне ZIP; внешняя обёртка не угадывается.
- До 16 МиБ архив, 4096 записей, 32 МиБ распакованных данных, 4 МиБ на файл.
- До 200 объектов и 200 модулей в интерфейсе. При усечении это явно указано;
  поиск работает только в загруженной части, серверная пагинация ещё не реализована.
- Просмотр исходника ограничен 256 КиБ и UTF-8. Бинарные/неподдерживаемые кодировки
  не декодируются с потерей данных. Исходник показывается без выполнения кода.
- `metadata = bounded_root_properties_only`, `bsl = inventory_only`, UUID unverified,
  live source not verified, published snapshot false.
- Диагностика, callgraph, сравнение, изменения и командные процессы недоступны.
  UI обозначает их как будущие этапы и не генерирует фиктивные результаты.
- Frontend не требует Windows. Backend этого маршрута пока Linux-only;
  запуск `gui` на Windows/macOS явно отклоняется до обращения к проекту.

## HTTP boundary

Это локальный transport для одного OS account, не authentication service для сети.
Hostile code того же account, root и подмена trusted startup configuration вне границы.

- Новый 256-bit token на процесс, без cookie, localStorage или persistent credentials.
- API требует token header; exact Host, Origin для POST/PUT, Fetch Metadata checks.
  CORS не разрешён. CSP запрещает внешние assets/network, frames, objects и base URL.
- Registry/profile/project/helper/hash берутся только из доверенной команды запуска.
  Браузер не выбирает OS paths или права. Filename используется только как подпись.
- Проверки текущих project:read + analysis:run выполняются вокруг Rust IO и после
  сериализации успешного результата/ошибки, перед HTTP disclosure.
- Source endpoint принимает путь только как selector ранее возвращённого inventory.
  Он повторно открывает собственный upload через Rust, проверяет archive SHA и raw SHA,
  ограничивает размер и отдаёт только полностью проверенные UTF-8 bytes.
- Нет extraction ZIP, shell-команд из UI, телеметрии или отправки исходников наружу.
- Двухэтапный upload даёт ID до передачи bytes, что позволяет явную отмену.
  Резервирование истекает через 30 секунд; body deadline 30 секунд;
  максимум 8 активных HTTP handlers, 75 секунд на request и один анализ одновременно.
- Отмена cooperative на границах существующего Rust протокола. Кратковременная задержка
  возможна до завершения текущего bounded IO. Если завершение уже победило отмену,
  возвращается готовый результат. Успех не выдаётся до подтверждённого reap Rust child.

## Проверки

```sh
RENTGEN_INPUT_CORE_TEST_BINARY=/absolute/rentgen-input-core \
  python -m pytest -q tests/unit/test_local_gui.py tests/unit/test_rust_input_workflow.py
node --test tests/gui/*.test.mjs
```

Набор проверяет настоящий loopback HTTP, Rust ZIP import/source, отказ чужим Host/Origin/token,
file path и размер, сохранность project state, отмену с reap настоящего child, cleanup,
усечение source, authorization после сериализации, потерянный upload и повторный импорт.
Это целевая приёмка. Она не заменяет browser end-to-end, полный существующий Windows suite
или native-приёмку Windows/macOS.

Для визуальной проверки можно собрать **явно подписанный UI-only файл** из синтетического
JSON результата и соответствующих синтетических файлов:

```sh
python scripts/verification/build_gui_visual_fixture.py \
  --analysis-json /path/synthetic-analysis.json \
  --synthetic-source-directory /path/synthetic-export \
  --output /path/Rentgen-visual-review.html
```

Файл не обращается к backend. Он проверяет внешний вид/навигацию, а не импорт.
Не передавайте этому инструменту данные заказчиков. Label в statusbar отличает этот
просмотр от рабочего runtime. Если browser environment запрещает localhost, нельзя обходить
запрет сменой порта или публикацией backend; native browser QA остаётся отдельным gate.

Дизайн учитывает [WCAG 2.2](https://www.w3.org/TR/WCAG22/): focus-visible, клавиатуру,
адаптивный reflow и reduced motion. Это не заявление о сертификации полного соответствия.
Защита запросов следует семантике [Fetch Metadata](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Fetch_metadata).
