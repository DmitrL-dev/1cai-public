# Рентген Companion 0.1.17 — модули, история и проверка запуска

Companion показывает данные установленного Core в деревьях
**«Рентген: модули»** и **«Рентген: черновики»**. Для новой пары используйте
Core **0.1.0.dev16** и отдельный доверенный профиль редактора.

**Предварительный выпуск компонентов.** Проверены пакет, установка и обычная
активация в отдельном профиле. Общая готовность продукта не заявлена.

## Что делает существующий маршрут

Можно прочитать модуль выбранного снимка, найти путь, обновить снимок,
просмотреть историю черновика и diff, открыть рабочую копию существующей
ревизии, сохранить следующую версию и прочитать квитанцию операции.

Для самого первого черновика сначала создаются предложение и сохранённый
draft через CLI/MCP. Редактор открывает уже существующую ревизию.
Просмотр и сохранение не применяют изменения к конфигурации или базе.
BSL, тесты и платформенная проверка требуют соответствующих runtime/профилей.

## Новое в Source 0.1.17

Node bridge выполняет ограниченный BOOTSTRAP/REFUSAL exchange:
запрос начала связи → явный отказ без подтверждённого владельца.
Сохраняются generation/run nonce/request_id/digest, один consumed lease,
пределы frame/bytes/counters и исходные deadlines. Отказ/cancellation
не подтверждают peer или native IO closure; повторный send не создаётся.

Явный cold mode захватывается один раз. Без admitted owner backend происходит
отказ до profile/runner/Core initializer. Marker, PID и JSON-поля не разрешают
реальный запуск. Для маршрута без cold mode сохранено прежнее поведение профиля.

Python54 application-frame — verification helper вне Core wheel.
Перед первым эффектом он закрепляет исходные policy/storage; deadlines не обновляются.
Storage и diagnostics удерживаются при pending/tombstone, освобождаются после settlement;
исходное исключение submit сохраняется. Private опыт согласовал Node BOOTSTRAP
с Python input и Python REFUSAL с Node parser; неверный request_id получил отказ.
Это fake exchange без Editor/model/native backend.

## Первое открытие проекта

1. Установите Core dev16 и создайте снимок через CLI по notes Core.
2. Подготовьте отдельный профиль по
   [инструкции адаптера](https://github.com/DmitrL-dev/1cai-public/blob/companion-v0.1.17/integrations/open-editor/README.md).
   Используйте полный checkout `companion-v0.1.17`: генератор собирает соседний
   `vscode-rentgen`. Checkout опубликованного 0.1.15 для новой пары не подходит.
3. Укажите Python установленного Core, свой registry/project_id, редактор
   и scanner. Существующий профиль сам на новую установку не переключается.
4. Следуйте `install.ps1` / `launch.ps1` подготовленного профиля.
   Установка принятого VSIX — **Extensions: Install from VSIX…**
   именно в нужном профиле. Проверьте версию расширения.
5. Предоставьте доверие своей рабочей папке. Найдите два дерева Рентгена.
6. Через **Ctrl+Shift+P** введите полное имя
   **«Рентген: обновить снимок»** или **«Рентген: обновить черновики»**.
   Для правки выберите ревизию в дереве и её действие **«Рентген: редактировать версию черновика»**.
   Затем сохраните через **«Рентген: сохранить версию черновика»**.

Launcher передаёт Python, registry и project_id; расширение проверяет профиль.
Без scanner доступны существующие снимки/черновики; новый capture требует scanner.

## Совместимость и recovery

Source поддерживает базовый профиль Core dev4–16, локальную правку dev7–16,
BSL/platform/test profiles dev8–16. Неизвестная версия в профиле вызывает отказ. После изменения установки
пересоздайте профиль с актуальными Python, registry и project_id.
Нужны доверие workspace, правильная ревизия и права Windows SID.

Завершённый результат читайте по существующей квитанции. При прерывании
сохраните идентификаторы операции и используйте recovery данного сценария;
не запускайте repair/test вслепую.

## Проверки и ограничения

Оба оригинальных CI PR54: **3164 Python / 332 Node**; 38 protected — часть Python.
Source54 controls: **RED2 старой реализации → GREEN8 полного нового набора**.

Локальные две сборки VSIX: 44 members (42 Source + 2 generated metadata).
Финальный VSIX CI нового main совпадает с обеими сборками. Он установлен
в отдельный профиль Microsoft VS Code 1.139.1 вместе с Cline 4.1.17 и Core dev16.
CLI подтвердил обе версии. Из 42 файлов расширения 41 совпал побайтно;
в package.json установщик добавил только служебное поле __metadata,
остальное содержание совпало. Два служебных файла контейнера VSIX
не считаются установленными файлами расширения.
Стенд без задания модели проверил фактическую активацию: Companion ready=true
для идентификатора нового проекта, Cline active=true, завершение процесса — 0.
Это проверка установки и активации; выбор ревизии, editor result recovery
и отказ отключённому профилю этим стендом не квалифицируются.
Private codec: одна операция/storage до fake completion и двух owned closes;
initializer/runner/Core=0, execute denied, READY=false/grants=null.
Global RSS/actual IO closure не измерены.

Actual OwnerIPC, ABI/ACL/held-role, реальный cold Editor/model, editor live apply,
типовые конфигурации и supported daily-model prerequisite остаются открытыми.
Исторический dev15/0.1.15 опыт 1С/YAxUnit относится к той прежней паре.

## Публичные файлы

| Asset | Для чего |
| --- | --- |
| `rentgen-companion-0.1.17.vsix` | Установка расширения |
| `SHA256SUMS` | SHA256 принятого VSIX |
| `release.json` | Версия, размер, SHA256 и точный commit/tag |

Notes служат телом GitHub Release. Во внутреннем workflow artifact есть
`RELEASE_NOTES.md`, но отдельного четвёртого public asset workflow не публикует.

Final VSIX: `83bdcea289b2d8195bbb7e6157ac4e166254da9d87ed2dc2d9182fd475ebc44a`,
`263885` байт.
Source records R: `указан в публичном release.json; tag companion-v0.1.17`;
tag: `companion-v0.1.17`.
`full_product_ready=false`; готовность всего рабочего места и production deployment не заявлены.
