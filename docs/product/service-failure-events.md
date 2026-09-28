# Диагностика отказов службы

Служба добавляет короткое событие `service_failed` в журнал Windows. Источник —
`Rentgen.Core.Service`, Event ID — 1, уровень — Error. Если источник не зарегистрирован,
Windows использует Application. Core не создаёт ключ источника в реестре.
[Поведение Windows](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-registereventsourcew).

В Properties[0] хранится JSON: schema 1, имя службы, PID, этап `stage`, тип `kind`
и причина `reason`. Максимум — 512 символов. Текст исключения, пути, аргументы
и неизвестные коды исключены. Неизвестная причина — `UNCLASSIFIED`, тип — `UNEXPECTED`.

```powershell
Get-WinEvent -LogName Application -FilterXPath "*[System[Provider[@Name='Rentgen.Core.Service'] and EventID=1]]" -MaxEvents 10 |
    ForEach-Object { $_.Properties[0].Value }
```

| Этап | Где произошёл отказ |
|---|---|
| `config` | Загрузка и проверка конфигурации службы |
| `factory` | Создание worker, получение контекста и аренды профиля |
| `interface` | Проверка методов worker |
| `ready` | Подтверждение готовности worker |
| `run` | Выполнение Git scheduler |
| `tick` / `wait` | Цикл SourceObserver или ожидание |
| `close` | Освобождение ресурсов worker |

`OBSERVER_PROFILE_MISMATCH` означает отличие привязки профиля от текущего контекста;
`PROJECT_FORBIDDEN` — недостаток прав проекта; `STATE_BUSY` — занятость SQLite;
`STATE_UNAVAILABLE` — отказ локальной транзакции. Диагностика не меняет профиль,
права или восстановление. При нескольких ошибках сохраняется первая. Ошибка
записи события не меняет общий результат службы и не отменяет освобождение аренды.
Закрытие event handle вызывается в `finally`.

Stock-сценарий читает максимум 16 событий за последние 20 минут, проверяет поля
и связывает PID с исходными наблюдениями SCM. Прочитанный код объясняет отказ;
успешность native-сценария устанавливают его прежние пять групп проверок.
Фактическая запись под LocalService ожидает нового CI. Локально проверены
инъекции Windows API и защита полей.
