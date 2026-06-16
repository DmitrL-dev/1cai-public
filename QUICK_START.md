# 1C AI Stack - Quick Start Guide

## 🚀 Быстрый запуск

### Запустить всё одной командой

```powershell
.\start-all.ps1
```

Это запустит:

```

---

## 🌐 Доступные сервисы

После запуска:

| Сервис          | URL                        | Описание         |
| --------------- | -------------------------- | ---------------- |
| **Frontend**    | http://localhost:3001      | React UI         |
| **Backend API** | http://localhost:8000      | FastAPI          |
| **Swagger UI**  | http://localhost:8000/docs | API документация |
| **PostgreSQL**  | localhost:5432             | База данных      |
| **Redis**       | localhost:6379             | Кэш              |
| **Qdrant**      | localhost:6333             | Vector DB        |
| **Neo4j**       | localhost:7687             | Graph DB         |

---

## 📝 Разработка

### Backend

```powershell
cd c:\1cAI

# Активировать venv
.\venv\Scripts\Activate.ps1

# Запустить с hot reload
python -m uvicorn src.main:app --reload
```

### Frontend

```powershell
cd c:\1cAI\frontend-portal

# Запустить dev server
npm run dev

# Сборка для production
npm run build
```

---

## 🔧 Troubleshooting

### Порт занят

Если порт 8000 или 3001 занят:

```powershell
# Найти процесс
netstat -ano | findstr :8000

# Убить процесс
taskkill /PID <PID> /F
```

### Backend не запускается

Проверьте что venv активирован и все зависимости установлены:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Frontend не запускается

Переустановите зависимости:

```powershell
cd frontend-portal
Remove-Item node_modules -Recurse -Force
npm install
```

---

## 📊 Производительность

После миграции на native host:

- ✅ npm install: **10x быстрее** (2-3 мин вместо 30 мин)
- ✅ Vite startup: **10x быстрее** (711ms вместо 5-10 сек)
- ✅ Hot reload: **5-10x быстрее** (~1 сек вместо 5-10 сек)
- ✅ VS Code: **не зависает**

---

**Последнее обновление:** 2025-11-23
