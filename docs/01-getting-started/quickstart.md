# Quick Start — 1С:Рентген

> **Что это.** Рентген конфигурации 1С: граф вызовов всей конфигурации, impact/blast-radius
> («что я сломаю»), мёртвый код и объяснимый риск-рейтинг — **token-free** (код не уходит в LLM).
> Анализ живёт в одном самодостаточном SQLite-файле (`data/rentgen.db`), отдаётся in-process.

> **Без Docker.** Никакого Docker / PostgreSQL / Neo4j / Redis / Qdrant не нужно. Всё хранилище —
> локальный SQLite. Внешние сервисы не поднимаются.

---

## 1. Требования

- **Python 3.11** — нужен системный интерпретатор (`C:\Python311\python.exe`).
  Учтите: вложенный `.venv` в репозитории сломан, поэтому скрипты вызывают `C:\Python311\python.exe`
  напрямую и выставляют `IGNORE_PY_VERSION_CHECK=1`. Если запускаете команды вручную — делайте так же.
- **Node.js 18+** — только для портала (Vite dev-сервер на :3000, проксирует `/api` на бэкенд).
- **Go-сканер** — уже собран и лежит в репозитории: `go\bsl-scan.exe`. Пересобирать не нужно
  (опционально: `cd go && go build -o bsl-scan.exe ./cmd/bsl-scan`, требует Go 1.25).

> **Данные не входят в репозиторий.** `data/rentgen.db`, граф (`data/rentgen_callgraph.ndjson`) и
> оценки (`gabriel_runs/scores.json`) — производные конкретной (часто проприетарной) конфигурации 1С,
> поэтому они в `.gitignore`. Репозиторий — это код; стенд собирается на ваших данных при первом запуске.

---

## 2. Самый быстрый путь (одна команда, Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_rentgen.ps1
```

Скрипт:

1. собирает `data/rentgen.db` при первом запуске (~30 с) из поставляемых граф/оценок, если их ещё нет;
2. поднимает бэкенд FastAPI на <http://127.0.0.1:8000>;
3. поднимает портал на <http://localhost:3000> (или ближайший свободный порт вроде :3001, если :3000 занят).

Откройте:

- **Очаги риска (risk hotspots):** <http://localhost:3000/quality>
- **Граф вызовов / impact:** <http://localhost:3000/rentgen>
- **Рабочий пульт:** <http://localhost:3000>
- **API-доки (Swagger):** <http://127.0.0.1:8000/docs>

**Вход:** на экране логина нажмите кнопку **«Dev Mode»** — она получает настоящий JWT через demo-пользователя,
а не кладёт фиктивный токен в браузер.

---

## 3. Проанализировать СВОЮ конфигурацию

Анализ строится из вашей выгрузки конфигурации 1С (распакованная конфигурация в файлах — каталог с `.bsl`).
Пайплайн из трёх шагов пересобирает **единый локальный стор** `data/rentgen.db`.

> **Honest note.** Сегодня это CLI-пайплайн, и он держит **одну конфигурацию на установку**:
> повторный прогон перезаписывает `data/rentgen.db`. UI-загрузки нескольких конфигураций пока нет.

### Вариант А — одной командой (обёртка)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\onboard.ps1 -ConfigPath C:\path\to\unpacked-1c-config
```

`onboard.ps1` прогоняет все три шага по порядку, проверяет коды возврата и останавливается на первой
ошибке, затем печатает, куда записан стор, и следующий шаг. Добавьте `-Force`, чтобы пересобрать поверх
существующего стора без вопросов.

### Вариант Б — те же три шага вручную

Все команды — из корня репозитория. Сначала: `$env:IGNORE_PY_VERSION_CHECK = "1"`.

```powershell
# 1) Граф вызовов -> data/rentgen_callgraph.ndjson  (NDJSON в stdout)
go\bsl-scan.exe -mode callgraph C:\path\to\unpacked-1c-config > data\rentgen_callgraph.ndjson

# 2) Оценки качества -> gabriel_runs/scores.json
C:\Python311\python.exe -m tools.bsl_scoring run --config-path C:\path\to\unpacked-1c-config --output gabriel_runs\scores.json

# 3) Сборка единого SQLite-стора -> data/rentgen.db  (~30 с)
C:\Python311\python.exe tools\rentgen\build_store.py
```

Шаг 3 читает ровно `data/rentgen_callgraph.ndjson` и `gabriel_runs/scores.json` и пишет `data/rentgen.db`
(существующий файл удаляется и пересоздаётся). Поэтому пути вывода в шагах 1–2 фиксированы — не меняйте их.

После пересборки перезапустите бэкенд (или просто запустите `scripts\start_rentgen.ps1` снова —
он увидит готовый стор и сразу поднимет сервисы).

---

## 4. Production

Локальный запуск работает с дев-секретом по умолчанию. Для production:

- Выставьте окружение и **сильный** `JWT_SECRET`:

  ```powershell
  $env:ENVIRONMENT = "production"
  $env:JWT_SECRET  = "<длинная случайная строка>"
  C:\Python311\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
  ```

- Приложение **отказывается стартовать**, если в production `JWT_SECRET` не задан или равен дефолту —
  это hard error на старте (см. `src/config.py`, `validate_security()`). В dev — громкий warning, стек
  всё равно поднимется.

Это всё, что требуется для запуска ядра. Бэкенд и портал — обычные процессы (uvicorn + Vite/статика),
внешних БД и брокеров нет.

---

Подробности продукта, методология и честные оговорки (что факт, что эвристика) —
[`docs/RENTGEN.md`](../RENTGEN.md). Запуск одной командой и грабли — корневой
[`README.md`](../../README.md).
