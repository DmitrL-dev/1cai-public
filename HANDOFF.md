# HANDOFF — 1С:Рентген / 1cAI (для Codex или любого агента-преемника)

> Этот файл самодостаточен. Прочитай его + `docs/RENTGEN.md` + `progress.txt` — и можно работать
> без контекста предыдущей сессии. Цель: продолжить превращение **спины** (граф Рентгена)
> в **on-prem экосистему полного цикла разработки/доработки 1С**.

---

## 0. TL;DR

> **Current truth, 2026-06-19.** Этот handoff ниже содержит исторические записи 2026-06-15. Живой
> репозиторий сейчас на ветке `public-snapshot` (commit `6b4bc99b`), а не на старой
> `feat/rentgen-sqlite-engine`. P0 hardening начат: dev-start задает локальный JWT secret,
> `GET /health` стал быстрым liveness, deep probe переехал на `/health/deep`, Dev Mode в портале
> получает настоящий JWT через `/api/v1/auth/token`, а Change Impact/diff-review/Test Factory/Release Readiness
> протаскивают `impact_measured`, `coverage` и `coverage_caveat`, поэтому непокрытый impact больше не выглядит
> безопасным нулем. `GET /api/v1/rentgen/build` совпадает с portal `rentgenApi.build` и остается lightweight
> проверкой готовности prebuilt SQLite store. Следующий слой уже в коде: role-based Home с complete demo
> story, markdown role reports, Buyer Brief/Buyer Pulse room bridges для buyer/deal/value/trust маршрутов,
> `GET /api/v1/management/demo`, `GET /api/v1/management/role-report/{role}`,
> `POST /api/v1/management/intake/plan` и Query Surgeon правило `join-field-null-guard` для LEFT JOIN
> полей без `ЕстьNULL`/`ЕСТЬ NULL`. Platform Doctor v1 добавлен как `/platform-doctor` и
> `GET /api/v1/platform-doctor/analyze`: локальный inventory версии платформы, совместимости, СУБД,
> техжурнала, OpenMetrics, лицензий, расширений и upgrade checklist. Lock Radar v1 добавлен как
> `/lock-radar` и `POST /api/v1/lock-radar/analyze`: `TLOCK`/`TTIMEOUT`/`TDEADLOCK`, affected modules,
> test gaps, actions и runbook; Evidence Bundle может включать его как опциональный артефакт. Extension Safety v1 добавлен как
> `/extension-safety` и `POST /api/v1/extension-safety/analyze`: CFE/EDT-расширения, права,
> privileged mode, write hooks, borrowed objects, impact и test gaps; Evidence Bundle может включать его как
> опциональный артефакт. Vendor Portfolio v1 добавлен как
> `/vendor-portfolio` и `GET /api/v1/vendor-portfolio/audit`: pre-sale audit pack для клиента с
> executive risk, intake, platform readiness, work packages, caveats и markdown; `POST /api/v1/vendor-portfolio/portfolio`
> добавляет multi-client portfolio mode для франчайзи/вендора. Update War Room v1
> добавлен как `/update-war-room` и `POST /api/v1/update-war-room/plan`: план обновления с platform,
> extension safety, release impact, tests, rollback/evidence и caveats. Rights & RLS Simulator v1
> добавлен как `/rights-rls` и `GET /api/v1/rights-rls/analyze`: role/object/action matrix,
> dangerous rights, conservative RLS detection и release security gate. Value Packs Center v1 добавлен
> как `/value-packs` и `GET /api/v1/value-packs/catalog`: покупаемые role/product packs с deliverables,
> proof, route links, maturity и licensing story без обязательной токенной подписки. Business Case v1
> добавлен как `/business-case` и `POST /api/v1/business-case/build`: money map, AI subscription
> displacement, buyer committee, objections, offer stack и 30/60/90 rollout. Productization Console v1
> добавлен как `/productization`: readiness, SBOM, offline manifest/archive build and verify поверх
> `/api/v1/productization`. Evidence Bundle v1
> добавлен как `/evidence-bundle` и `POST /api/v1/evidence-bundle/build`: JSON/Markdown артефакты,
> caveats и SHA-256 manifest для approval, КП и внутреннего аудита.

- **Что это.** AI-платформа для разработки на 1С. Продуктовый фронтир — **1С:Рентген**: token-free
  «рентген» конфигурации (граф вызовов всей конфигурации + оценки качества + объяснимый риск),
  работающий **внутри закрытого контура без интернета**. Это и есть стратегический ров: туда не
  заходят 1С:Напарник/GigaCode (облако, только генерация).
- **Что уже сделано (эта сессия, коммит `6c83b2d7`, ветка `feat/rentgen-sqlite-engine`).**
  Выкинута мёртвая зависимость от Neo4j; граф+оценки живут в одном SQLite (`data/rentgen.db`),
  отдаются in-process. Готова hero-страница `/quality` (очаги риска с объяснением). Всё проверено
  на реальной 1С:ERP УХ. 10/10 тестов движка.
- **Что делать дальше.** Соединить уже построенные, но **не подключённые** пилоны (Перформер,
  ITS-RAG, whole-config review), затем собрать **change-driven workflow** (главный сценарий
  «доработки»). Подробности — §5.
- **Главное ограничение.** Машина Windows, **Docker НЕТ**, рабочий питон — `C:\Python311\python.exe`
  (встроенный `.venv` сломан). См. §2 — не переоткрывай эти грабли.

---

## 1. Где знания

| Источник | Что внутри |
|---|---|
| `docs/RENTGEN.md` | Полное описание Рентгена: что умеет, архитектура, запуск, **методология и честные оговорки** |
| `progress.txt` | Хронология; верхняя запись (2026-06-15) — про эту работу + «Learnings» |
| `C:\Users\chg\.claude\projects\C--1cAI\memory\*.md` | Память: `rentgen-product`, `1cai-runtime`, `1cai-borrow-sibling-projects` |
| `ARCHITECTURE.md`, `README.md` | Общая платформа (агенты, Micro-Swarm, MCP, Telegram) |

---

## 2. Как запускать (грабли — НЕ переоткрывай)

```powershell
# Одной командой (собирает rentgen.db при первом запуске, поднимает backend+portal):
powershell -ExecutionPolicy Bypass -File scripts\start_rentgen.ps1
```

Вручную:
```powershell
$env:IGNORE_PY_VERSION_CHECK="1"
# 1) собрать стор (если data/rentgen.db нет) — ~30с, два прохода по 503МБ NDJSON:
C:\Python311\python.exe tools\rentgen\build_store.py
# 2) backend:
C:\Python311\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
# 3) portal (Vite proxy /api -> :8000):
cd portal; npm run dev      # :3000
# 4) тесты движка:
C:\Python311\python.exe -m pytest tests/unit/test_rentgen_store.py -q
```

Грабли:
- **Питон = `C:\Python311\python.exe`** (3.11.9, все зависимости есть). `.venv` СЛОМАН (pyvenv.cfg
  указывает на несуществующий базовый интерпретатор). Всегда `IGNORE_PY_VERSION_CHECK=1`.
- **Docker/Neo4j НЕТ.** Любая фича — без внешних сервисов. Стор = SQLite (`data/rentgen.db`).
- **Baseline deps = `requirements.txt`.** OpenAI, Qdrant, sentence-transformers и Neo4j вынесены в
  `requirements-optional.txt`; PyTorch/sklearn/mlflow остаются в `requirements-ml.txt`.
- **Liveness = `GET /health`.** Глубокий probe внешних/legacy сервисов — `GET /health/deep`.
- **POST flow/impact требуют UTF-8 тела.** PowerShell 5.1 ломает кириллицу в Latin-1 → 0 результатов
  (браузер/axios — ок). В PS слать тело как `[System.Text.Encoding]::UTF8.GetBytes($json)`.
- **Bash-тул (Git Bash) ломает пути `C:\`** (exit 127) → используй PowerShell или `/c/Python311/python.exe`.
- **Portal:** реальный фронт — `portal/`, НЕ `frontend-portal/` (тот мёртвый). Dev-вход — кнопка
  «Dev Mode»; она получает настоящий JWT через demo user `admin/admin123`, а не кладет фиктивный
  токен в localStorage. `portal/.env` `VITE_API_BASE_URL` пуст → идём через прокси.
- **Первый экран продукта:** <http://localhost:3000> — role-based рабочий пульт с demo story и
  скачиваемыми markdown-отчетами. Подключение источника: <http://localhost:3000/configurations>.
  Проверка платформы: <http://localhost:3000/platform-doctor>. План обновления:
  <http://localhost:3000/update-war-room>. Права/RLS: <http://localhost:3000/rights-rls>.
  Пакеты продукта: <http://localhost:3000/value-packs>. Business Case:
  <http://localhost:3000/business-case>. Productization:
  <http://localhost:3000/productization>. Evidence export:
  <http://localhost:3000/evidence-bundle>. Портфельный audit pack:
  <http://localhost:3000/vendor-portfolio>.
- **Скриншоты preview-тула виснут** на страницах с force-graph (бесконечный rAF) — проверяй через
  `preview_snapshot` (a11y-дерево) + `preview_eval`, не через `preview_screenshot`.

---

## 3. Что построено и работает (спина)

### Движок — `tools/rentgen/`
- `build_store.py` — строит `data/rentgen.db` из:
  - `data/rentgen_callgraph.ndjson` (503МБ, **730 416** функций, граф вызовов от Go-сканера `go/bsl-scan.exe`)
  - `gabriel_runs/scores.json` (**26 748** модулей, оценки от `tools/bsl_scoring/`)
  - Порт 3-уровневого разрешения вызовов из `src/modules/graph_api/services/rentgen_pipeline.py`.
  - **`ALLOW_NAME_ONLY = False`** (точность > полнота): берём только квалифицированные `Модуль.Функция`
    (exact/alias) и локальные вызовы; отброшено ~3.37M неоднозначных рёбер (вкл. платформенные
    `Вставить/Добавить/Количество`). Итог: **1 477 681** достоверное ребро. Топ fan-in корректен
    (`ОбщегоНазначения`, `СтроковыеФункцииКлиентСервер` …).
- `store.py` — `RentgenStore` (read-only SQLite, потокобезопасен, открывает соединение на вызов):
  - quality: `get_module`, `summary`, `worst`, `search`
  - граф: `get_execution_flow`, `get_impact_analysis` (BFS, cap 600 рёбер), `dead_code`, `get_stats`, `module_neighbors`
  - **`hotspots()`** — объяснимый риск: `risk = quality_risk × blast(fan_in)`, всегда возвращает
    `reasons[]` (вклад каждого фактора). Веса прозрачны (вверху `store.py`).
- Схема БД: `subroutine`, `call_edge`, `module`, `module_edge`, `quality`, `meta`.
- **Join-ключ** между графом (модуль = `МСФО.CommandModule`) и оценками (path =
  `AccountingRegisters/МСФО/Commands/X/Ext/CommandModule.bsl`) = `(object_name, module_kind)`,
  derive через `_canon_from_callgraph` / `_canon_from_path`. Покрытие ~50% (часть нулевых fan —
  легитимна: команды/формы вызывает платформа, не BSL).

### API (отдаётся из стора, без Neo4j)
- `src/api/quality_api.py` (`/api/v1/quality`): `summary`, `worst`, `search`, `module`, `stats`,
  **`hotspots`**, `predict` (GBR, без БД), `score-config`.
- `src/api/rentgen_api.py` (`/api/v1/rentgen`): `flow`, `impact`, `dead-code`, `stats`,
  `module-neighbors`, `health`.
- `src/api/_rentgen_store.py` — общий аксессор `store_or_none()` (graceful 503, если стор не собран).
- Зарегистрированы в `src/app/routers.py` (прямой mount, строки ~111-122).

### UI — `portal/src/routes/_authenticated/quality.tsx`
KPI + таблица очагов риска с раскрытием `reasons` + панель мёртвого кода + домены.
Клиент: `portal/src/lib/api-client.ts` (`qualityApi`, `rentgenApi`). Граф-страница: `/rentgen`
(`portal/src/routes/_authenticated/rentgen.tsx`, force-graph).

### Тесты
`tests/unit/test_rentgen_store.py` — 10/10. Запуск см. §2.

---

## 4. Продукт и ров (зачем всё это)

**Цель:** экосистема для ЛЮБОГО этапа разработки/доработки ЛЮБОЙ конфигурации 1С, в т.ч. в компаниях
с замкнутым контуром. **Спина** = граф Рентгена (цифровой двойник конфигурации, token-free, on-prem).
Каждая стадия цикла подключается к спине. **Ров** = работает полностью внутри периметра без интернета —
туда не могут облачные 1С:Напарник/GigaCode.

Статус по стадиям: Онбординг ✅ (Рентген) · Требования/Разработка/Ревью ⚠️ (LLM-gated, не на графе) ·
**Производительность ⚠️ (Перформер построен, НЕ подключён)** · Тесты ❌ · CI/Git ⚠️ · Эксплуатация ⚠️.

---

## 5. Роадмап (что делать) — по убыванию ценности

### ТРЕК 1 — соединить построенное (дни). Самый дешёвый ROI.
1. **Перформер** (`src/api/performer_api.py`, prefix `/api/v1/performer`, `POST /analyze`, `GET /health`) —
   построен, но НЕ зарегистрирован. Зарегистрировать в `src/app/routers.py` (зеркалить блок
   rentgen/quality, строки ~111-122; у роутера уже полный префикс). Анализатор — в
   `src/modules/.../performer` (ТЖ-парсер, query-хотспоты, N+1, локи; см. коммит `b8ccce4e`).
   Затем **связать с графом**: новый метод стора/эндпойнт «query-хотспот → место вызова → impact».
2. **ITS-RAG** (`src/api/its_rag_api.py`, prefix `/api/v1/its`, `POST /search|context`, `GET /health`) —
   построен, НЕ зарегистрирован. Зарегистрировать. Проверить, что индекс работает офлайн (Qdrant?
   sentence-transformers?) — для закрытого контура это критично; если требует интернета — заменить
   на локальный embed (или `data/models/` micro-swarm) и зафиксировать.
3. **Whole-config review:** новый `POST /api/v1/quality/review-diff` — на вход список изменённых
   `module_path` (или unified diff), на выход по каждому: его hotspot/оценка + impact (blast radius) +
   находки Micro-Swarm/стандартов. Переиспользует `RentgenStore` + `src/micro_swarm/`.
   Критерий: 3 жёлтых блока (§4) становятся зелёными.

### ТРЕК 2 — change-driven workflow (замок свода; это и есть «доработка»).
Главный сценарий, которого нет. **`POST /api/v1/rentgen/change-impact`**, тело
`{ "changed_modules": ["<module_path>", ...] }` (или git-diff → распарсить в module_path).
Ответ по каждому модулю: blast radius (`get_impact_analysis`), задетые хотспоты (`hotspots` ∩ изменения),
перф-риски (запросы в изменённых цепочках — через Перформер), нарушения стандартов (Micro-Swarm),
покрывающие тесты (заглушка до Трека 5).
- Маппинг: `module_path` (ключ оценок) → имя модуля графа через `(object_name, module_kind)`
  (`_canon_from_path` в `build_store.py`), затем impact по функциям этого модуля.
- UI: страница `/change` (или вкладка в `/quality`): вставить diff / выбрать модули → единый отчёт
  о рисках. Критерий: «дал правку → увидел весь риск по всей конфигурации, локально».

### ТРЕК 3 — ингестия ЛЮБОЙ конфигурации (без неё это демо).
Сейчас данные — разовый снапшот одной ERP. Нужен реальный заход:
- из Git (precommit1c/EDT-XML) **или** `.cf/.dt` (`tools/v8unpack.exe`) **или** живой базы (OData/RAS,
  см. `src/integrations/onec/`); прогон `go/bsl-scan.exe -mode callgraph` + `tools/bsl_scoring` →
  пересборка `rentgen.db`. Эндпойнт `POST /quality/score-config` уже умеет extract→classify→score.
- инкрементальный пересчёт по коммиту; мульти-база (у предприятия их много) → стор на конфигурацию
  (`data/rentgen_<config>.db`) + выбор активной в API.

### ТРЕК 4 — доказанный полностью-локальный режим (ров).
Анализ уже token-free. Генеративные стадии (кодоген, BA, объяснения) должны идти на ЛОКАЛЬНОЙ LLM
(GigaChat on-prem / Ollama — клиенты есть в `src/integrations/llm/`) с НУЛЁМ внешних вызовов.
Сделать профиль `OFFLINE=1`, проверить отсутствие сетевых вызовов, описать офлайн-инсталляцию.

### ТРЕК 5 — доставка в их инструменты (MCP) + тесты.
- MCP-сервер (`src/ai/mcp/`) — отдать инструменты `rentgen.impact / hotspots / dead_code / quality`,
  чтобы Рентген работал внутри EDT/Cursor/Напарника (быть аналитическим бэкендом, не конкурентом редактору).
- YAxUnit/Vanessa + **risk-driven выбор тестов** из графа impact (какие тесты гонять для данной правки).

**Рекомендованный порядок: 1 → 2 → 3 → 4 (5 — параллельно).** Связка 1+2 даёт самый убедительный
видимый продукт.

---

## 6. Честные оговорки (не сломай доверие)
- **Риск — прозрачная формула, не чёрный ящик.** Всегда отдавать `reasons[]`.
- **Разрешение вызовов: точность > полнота.** name-only OFF. Возможны ложные отрицания (динамический
  `Выполнить()`, глобальные общие модули без квалификации), но ложные срабатывания минимизированы.
- **Мёртвый код — только общие модули** (`scope="common"`); объектные/форм-модули вызывает платформа.
  Не учитывает `Выполнить()`/рефлексию/др. конфигурации — «проверяй перед удалением».
- **GBR `code_quality` слаб** (CV R²≈−0.06) — НЕ выпячивать; ведущий сигнал — формульные оценки + риск.

## 7. Протокол проверки своей работы
1. `pytest tests/unit/test_rentgen_store.py -q` — зелёно.
2. `GET /api/v1/rentgen/health` → `{store:true, subroutines:730416, ...}`.
3. `GET /api/v1/quality/hotspots?limit=3` → 3 объекта с `risk` и непустым `reasons`.
4. POST flow/impact — слать UTF-8 тело (§2). `impact ЗначениеРеквизитаОбъекта` → ~600 callers;
   `flow ПроверитьВозможностьВыгрузки` → ~365–507 рёбер.
5. UI: `/quality` через `preview_snapshot`/`preview_eval` (не screenshot) — KPI «26 748», таблица очагов,
   клик по строке раскрывает причины.

## 8. Можно брать из соседних проектов
Пользователь разрешил переиспользовать код из своих проектов на машине (`C:\AICoach`, `AISecurity`,
`Polaris*`, …; `C:\Users\chg\.bsl-language-server` — **BSL Language Server, 180 диагностик**, главный
кандидат заменить формульные флаги реальными диагностиками в «причинах риска»). Проверяй там перед тем,
как писать с нуля; указывай источник.

## 9. Git
Текущая ветка `feat/rentgen-sqlite-engine`, последний коммит `6c83b2d7`. Большие данные
(`data/rentgen.db`, NDJSON, `scores.json`, `data/configs/`) — в `.gitignore`, НЕ коммить. Стор
воспроизводим: `python tools/rentgen/build_store.py`. Коммить осмысленными порциями (conventional commits).

---

## 10. 2026-06-15 autonomous completion note

The roadmap above is the original handoff. After the autonomous product-readiness pass, the live enterprise Copilot coverage is complete:

- `GET /api/v1/copilot-coverage` is intentionally honest: current code reports 17 tracked items, 14 ready and 3 partial, with about 92% total coverage / 89% P0 coverage.
- Track 1 is connected: Performer, ITS-RAG, whole-config review, API, MCP and UI are mounted and smoke-tested.
- Track 2 is connected: change-impact, test coverage matrix, release readiness and standards/security review form a change-driven workflow.
- Additional layers are connected: local graph-grounded generation, metadata/data governance, requirements traceability, security posture, managed-form blueprint, offline readiness, team governance, and operations incident-to-code workflow.
- Latest focused verification: extended unit suite `50 passed`, portal `npm run build` passed with only Vite chunk-size warning, live API/MCP/UI smokes passed.
- Remaining work is post-readiness hardening, not a blocker for the current coverage goal: import-ready EDT form writer, real Vanessa/YAxUnit runner, internal owner registry/approval workflow, alert ingestion/MTTR trends, packaged offline installer. External ALM/CODEOWNERS sync is customer-specific adaptation, not baseline scope.
- EDT-MCP reconnaissance from DitriXNew/EDT-MCP is now a live bridge. `src/services/edt_mcp_bridge.py` implements MCP `initialize`, `tools/list`, `tools/call`, `/health` status, SSE/plain JSON parsing and a safety gate that blocks write/execute/mixed/unknown tools unless `confirm=true`. API `src/api/edt_mcp_api.py` exposes `/status`, `/live-tools`, `/call`; MCP tools `edt_mcp_status`, `edt_mcp_live_tools`, `edt_mcp_call` are registered; UI `/edt-mcp` is built. Keep written permission/dual-license note before vendoring AGPL-3.0 Java code.
