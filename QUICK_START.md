# 1С:Рентген — Quick Start

> **Token-free рентген конфигурации 1С.** Граф вызовов, impact/blast-radius, мёртвый код и
> объяснимый риск-рейтинг. Хранилище — один локальный SQLite-файл (`data/rentgen.db`), in-process.
> **Docker / PostgreSQL / Neo4j / Redis / Qdrant не нужны.**

Полный гайд: [`docs/01-getting-started/quickstart.md`](./docs/01-getting-started/quickstart.md).

---

## 🚀 Запустить всё одной командой (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_rentgen.ps1
```

Скрипт собирает `data/rentgen.db` при первом запуске (~30 с), поднимает бэкенд (:8000) и портал
(:3000, либо ближайший свободный порт вроде :3001).

| Что | URL |
| --- | --- |
| **Рабочий пульт** | <http://localhost:3000> |
| **Очаги риска (hotspots)** | <http://localhost:3000/quality> |
| **Граф вызовов / impact** | <http://localhost:3000/rentgen> |
| **Backend API** | <http://127.0.0.1:8000> |
| **Swagger UI** | <http://127.0.0.1:8000/docs> |

**Вход:** на экране логина кнопка **«Dev Mode»** выдаёт настоящий JWT через demo-пользователя.

---

## 🧩 Проанализировать свою конфигурацию

Распакованную конфигурацию 1С (каталог с `.bsl`) можно прогнать одной обёрткой — она пересобирает
**единый локальный стор** `data/rentgen.db` (одна конфигурация на установку сегодня):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\onboard.ps1 -ConfigPath C:\path\to\unpacked-1c-config
```

Под капотом — три шага (граф → оценки → сборка SQLite). Ручные команды и подробности:
[`docs/01-getting-started/quickstart.md`](./docs/01-getting-started/quickstart.md) §3.

---

## 📝 Разработка (ручной запуск)

Используйте системный Python 3.11 — вложенный `.venv` сломан. Выставьте `IGNORE_PY_VERSION_CHECK=1`.

### Backend

```powershell
$env:IGNORE_PY_VERSION_CHECK = "1"
C:\Python311\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

### Portal

```powershell
cd portal
npm install
npm run dev          # http://localhost:3000, проксирует /api на :8000
```

---

## 🔒 Production

```powershell
$env:ENVIRONMENT = "production"
$env:JWT_SECRET  = "<длинная случайная строка>"
C:\Python311\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Приложение **откажется стартовать**, если в production `JWT_SECRET` не задан или равен дефолту
(hard error в `src/config.py`, `validate_security()`). В dev — только warning.

---

## 🔧 Troubleshooting

### Порт занят

`start_rentgen.ps1` сам уходит на следующий свободный порт для портала. Если нужно освободить :8000 вручную:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object OwningProcess
Stop-Process -Id <PID> -Force
```

### Backend не запускается

Проверьте, что используете именно `C:\Python311\python.exe` (не вложенный `.venv`) и что выставлен
`IGNORE_PY_VERSION_CHECK=1`. Зависимости: `C:\Python311\python.exe -m pip install -r requirements.txt`.

### Portal не запускается

```powershell
cd portal
Remove-Item node_modules -Recurse -Force
npm install
```
