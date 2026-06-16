# CursorExt Guide (IDE Telemetry)

CursorExt — надстройка над IDE, собирающая действия разработчиков и агентов, фильтрующая чувствительные данные и синхронизирующая события в общее хранилище. Код: `src/cursorext/` + описание в `docs/architecture/overview.md`.

## 1. Что получает пользователь

| Возможность | Описание |
| --- | --- |
| Time-line действий | Просмотр операций (открытие файла, запуск тестов) через web-view или экспорт JSON. |
| Совместная память | События отправляются в GitHub репозиторий `memory-store`, доступны всем участникам. |
| Офлайн режим | Локальное хранилище (SQLite/LevelDB) сохраняет события без интернета. |

## 2. Установка

1. Склонировать `cursor-ext` (каталог `extension/`).
2. Собрать и установить расширение:
   ```bash
   cd extension
   npm install
   npm run build
   ```
3. В Cursor/VSCode включить developer mode и установить собранный `.vsix`.
4. Настроить endpoint (`http://localhost:6001/cursorext` по умолчанию).

## 3. Работа с данными

- **Локальное хранилище**: `~/.cursor-ext/history.db`.
- **Синхронизация**: `src/cursorext/storage.py` батчит события и вызывает `src/cursorext/events.py`.
- **Фильтрация**: секреты и приватные пути удаляются через `cursorExt.logger.apply_filters(...)`.

## 4. Технические детали

- Формат события:
  ```json
  {
    "timestamp": "...",
    "actor": "dev|agent",
    "event": "file_opened",
    "metadata": {
      "path": "src/api/graph_api.py",
      "duration_ms": 120
    }
  }
  ```
- CLI/Webhooks для CI (см. `docs/architecture/overview.md`, раздел “Интеграции с агентами/CI”).
- Headless-агенты используют `/api/v1/cursorext/events`.

## 5. Архитектура

> Диаграмма описана в `docs/architecture/overview.md` (раздел “CursorExt”). Изображение будет добавлено в `docs/architecture/images/` после обновления `make render-uml`.

---

**Проверка:**
1. `npm test` в `extension/`.
2. `pytest tests/system/test_e2e_flows.py::test_cursorext_sync`.
3. `python scripts/tests/run_offline_dry_run.py --scenario cursorext`.
# CursorExt Guide (IDE Telemetry)

CursorExt — надстройка над IDE, собирающая действия разработчиков и агентов, фильтрующая чувствительные данные и синхронизирующая события в общее хранилище. Код: `src/cursorext/` + описание в `docs/architecture/overview.md`.

## 1. Что получает пользователь

| Возможность | Описание |
| --- | --- |
| Time-line действий | Просмотр операций (открытие файла, запуск тестов) через web-view или экспорт JSON. |
| Совместная память | События отправляются в GitHub репозиторий `memory-store`, доступны всем участникам. |
| Офлайн режим | Локальное хранилище (SQLite/LevelDB) сохраняет события без интернета. |

## 2. Установка

1. Склонировать `cursor-ext` (каталог `extension/`).
2. Собрать и установить расширение:
   ```bash
   cd extension
   npm install
   npm run build
   ```
3. В Cursor/VSCode включить developer mode и установить собранный `.vsix`.
4. Настроить endpoint (`http://localhost:6001/cursorext` по умолчанию).

## 3. Работа с данными

- **Локальное хранилище**: `~/.cursor-ext/history.db`.
- **Синхронизация**: `src/cursorext/storage.py` батчит события и вызывает `src/cursorext/events.py`.
- **Фильтрация**: секреты и приватные пути удаляются через `cursorExt.logger.apply_filters(...)`.

## 4. Технические детали

- Формат события:
  ```json
  {
    "timestamp": "...",
    "actor": "dev|agent",
    "event": "file_opened",
    "metadata": {
      "path": "src/api/graph_api.py",
      "duration_ms": 120
    }
  }
  ```
- CLI/Webhooks для CI (см. `docs/architecture/overview.md`, раздел “Интеграции с агентами/CI`).
- Headless-агенты используют `/api/v1/cursorext/events`.

## 5. Архитектура

> Диаграмма описана в `docs/architecture/overview.md` (раздел “CursorExt”). Изображение будет добавлено в `docs/architecture/images/` после обновления `make render-uml`.

---

**Проверка:**
1. `npm test` в `extension/`.
2. `pytest tests/system/test_e2e_flows.py::test_cursorext_sync`.
3. `python scripts/tests/run_offline_dry_run.py --scenario cursorext`.
# CursorExt Guide (IDE Telemetry)

CursorExt — надстройка над IDE, собирающая действия разработчиков и агентов, фильтрующая чувствительные данные и синхронизирующая события в общее хранилище. Код: `src/cursorext/` + описание в `docs/architecture/overview.md`.

## 1. Что получает пользователь

| Возможность | Описание |
| --- | --- |
| Time-line действий | Просмотр операций (открытие файла, запуск тестов) через web-view или экспорт JSON. |
| Совместная память | События отправляются в GitHub репозиторий `memory-store`, доступны всем участникам. |
| Офлайн режим | Локальное хранилище (SQLite/LevelDB) сохраняет события без интернета. |

## 2. Установка

1. Склонировать `cursor-ext` (каталог `extension/`).
2. Собрать и установить расширение:
   ```bash
   cd extension
   npm install
   npm run build
   ```
3. В Cursor/VSCode включить developer mode и установить собранный `.vsix`.
4. Настроить endpoint (`http://localhost:6001/cursorext` по умолчанию).

## 3. Работа с данными

- **Локальное хранилище**: `~/.cursor-ext/history.db`.
- **Синхронизация**: `src/cursorext/storage.py` батчит события и вызывает `src/cursorext/events.py`.
- **Фильтрация**: секреты и приватные пути удаляются через `cursorExt.logger.apply_filters(...)`.

## 4. Технические детали

- Формат события:
  ```json
  {
    "timestamp": "...",
    "actor": "dev|agent",
    "event": "file_opened",
    "metadata": {
      "path": "src/api/graph_api.py",
      "duration_ms": 120
    }
  }
  ```
- CLI/Webhooks для CI (см. `docs/architecture/overview.md`, раздел “Интеграции с агентами/CI”).
- Headless-агенты используют `/api/v1/cursorext/events`.

## 5. Архитектура

> Диаграмма описана в `docs/architecture/overview.md` (раздел “CursorExt”). Изображение будет добавлено в `docs/architecture/images/` после обновления `make render-uml`.

---

**Проверка:**
1. `npm test` в `extension/`.
2. `pytest tests/system/test_e2e_flows.py::test_cursorext_sync`.
3. `python scripts/tests/run_offline_dry_run.py --scenario cursorext`.
# CursorExt Guide (IDE Telemetry)

CursorExt — надстройка над IDE, собирающая действия разработчиков и агентов, фильтрующая чувствительные данные и синхронизирующая события в общее хранилище. Код: `src/cursorext/` + `docs/architecture/overview.md`.

## 1. Что получает пользователь

| Возможность | Описание |
| --- | --- |
| Time-line действий | Просмотр операций (открытие файла, запуск тестов) через web-view или экспорт JSON. |
| Совместная память | События отправляются в GitHub репозиторий `memory-store`, доступны всем участникам. |
| Офлайн режим | Локальное хранилище (SQLite/LevelDB) сохраняет события без интернета. |

## 2. Установка

1. Склонировать `cursor-ext` (в папке `extension/` есть `package.json` и готовые скрипты).
2. В IDE (Cursor или VSCode) установить расширение через dev mode:
   ```bash
   cd extension
   npm install
   npm run build
   ```
3. В настройках указать путь к локальному API (по умолчанию `http://localhost:6001/cursorext`).

## 3. Работа с данными

- **Локальное хранилище**: файл `~/.cursor-ext/history.db`.
- **Синхронизация**: сервис `src/cursorext/storage.py` батчит события и вызывает `src/cursorext/events.py`.
- **Фильтрация**: секреты, пути и большие бинарные блоки удаляются на этапе `cursorExt.logger.apply_filters(...)`.

## 4. Технические детали

- Формат события:
  ```json
  {
    "timestamp": "...",
    "actor": "dev|agent",
    "event": "file_opened",
    "metadata": {
      "path": "src/api/graph_api.py",
      "duration_ms": 120
    }
  }
  ```
- Поддерживаются webhooks/CLI для CI (см. `docs/architecture/overview.md` раздел “Интеграции с агентами/CI”).
- Для headless-агентов есть endpoint `/api/v1/cursorext/events`.

## 5. Официальная архитектура

![CursorExt overview](../architecture/images/cursorext-overview.png) *(если изображение недоступно, см. `docs/architecture/overview.md`)*.

---

**Проверка:**  
1. `npm test` в `extension/`.  
2. `pytest tests/system/test_e2e_flows.py::test_cursorext_sync`.  
3. `python scripts/tests/run_offline_dry_run.py --scenario cursorext`.

