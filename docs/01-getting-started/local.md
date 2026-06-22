# 🚀 Quick Start - Локальный Запуск

**Полная инструкция по запуску проекта локально**

---

## 📋 Предварительные требования

### **Обязательно:**
- ✅ Python 3.11.x
- ✅ Node.js 18+
- ✅ Docker Desktop
- ✅ Git

### **Опционально:**
- PostgreSQL 15 (или через Docker)
- Redis 7 (или через Docker)

---

## 🎯 ВАРИАНТ 1: Быстрый запуск (Рекомендуется)

### **Шаг 1: Запуск инфраструктуры (Docker)**

```bash
# Клонируем репозиторий (если еще не клонирован)
cd "C:\Projects\1c-ai"

# Запускаем базы данных через Docker
docker-compose up -d postgres redis

# Однократно применяем миграции (если запускаете backend)
docker-compose run --rm migrations

# Проверяем, что запустились
docker-compose ps
```

**Должно показать:**
```
postgres  running  0.0.0.0:5432->5432/tcp
redis     running  0.0.0.0:6379->6379/tcp
```

---

### **Шаг 2: Backend (FastAPI)**

#### **2.1. Установка зависимостей:**

```bash
# Создаем виртуальное окружение (рекомендуется)
python -m venv venv

# Активируем
# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Windows CMD:
.\venv\Scripts\activate.bat

# Устанавливаем зависимости
pip install -r requirements.txt
```

#### **2.2. Настройка переменных окружения:**

Создайте файл `.env` в корне проекта:

```bash
# Копируем пример
copy .env.example .env

# Или создаем вручную
notepad .env
```

**Содержимое `.env`:**
```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/enterprise_1c_ai

# Redis
REDIS_URL=redis://localhost:6379

# OpenAI (замените на ваш ключ)
OPENAI_API_KEY=your_openai_key_here

# Supabase (если используете)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# JWT (для dev можно любой)
JWT_SECRET_KEY=dev-secret-key-change-in-production

# Environment
ENVIRONMENT=development

# CORS (для dev)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

#### **2.3. Инициализация базы данных:**

```bash
# Создаем таблицы (миграция)
python scripts/run_migrations.py

# Или запускаем SQL вручную
# psql -U postgres -d enterprise_1c_ai -f db/schema.sql
```

#### **2.4. Запуск Backend:**

```bash
# Вариант 1: Через python
python src/main.py

# Вариант 2: Через uvicorn (с hot reload)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Backend запустится на:** `http://localhost:8000`

**Проверка:**
- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- API docs: http://localhost:8000/redoc

---

### **Опционально: MinIO (локальное S3)**

```bash
docker-compose -f docker-compose.yml -f docker-compose.stage1.yml up -d minio
docker-compose -f docker-compose.yml -f docker-compose.stage1.yml run --rm minio-setup
```

- Консоль: http://localhost:9001  
- Endpoint для `.env`: `AWS_S3_ENDPOINT=http://localhost:9000`  
- Креды: `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` (по умолчанию `minioadmin`)

---

### **Шаг 3: Frontend (React Portal)**

#### **3.1. Установка зависимостей:**

```bash
# Переходим в frontend папку
cd portal

# Устанавливаем зависимости
npm install
```

#### **3.2. Настройка окружения:**

Создайте `.env` файл:

```bash
# Копируем пример
copy env.example .env

# Или создаем
notepad .env
```

**Содержимое `.env`:**
```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_ENABLE_DARK_MODE=true
VITE_ENABLE_AI_CHAT=true
```

#### **3.3. Запуск Frontend:**

```bash
npm run dev
```

**Frontend запустится на:** `http://localhost:3000`

---

### **Шаг 4: Открыть в браузере!**

1. Откройте `http://localhost:3000`
2. Увидите Login page
3. Войдите с любыми credentials (dev mode):
   - Email: `admin@test.com`
   - Password: `password123`
4. Автоматически перенаправит на dashboard!

---

## 🎯 ВАРИАНТ 2: Полный Docker Stack

### **Все сервисы через Docker:**

```bash
# Запустить ВСЕ сервисы
docker-compose -f docker-compose.yml -f docker-compose.saas.yml up -d

# Это запустит:
# - PostgreSQL
# - Redis
# - Neo4j
# - Qdrant
# - Elasticsearch
# - Backend API (3 replicas)
# - Frontend (Nginx)
# - Prometheus
# - Grafana
```

**Доступ:**
- Frontend: http://localhost:80
- Backend API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

---

## 🧪 ВАРИАНТ 3: Только тестирование

### **Запуск тестов без запуска приложения:**

```bash
# Все тесты сразу
.\scripts\run_all_tests.ps1

# Или по отдельности:

# Unit tests
python -m pytest tests/unit/ -v

# Integration tests  
python -m pytest tests/integration/ -v

# Demo test suite
python tests/run_demo_tests.py

# Code review
python -m pytest tests/test_code_review.py -v
```

---

## 🔧 Troubleshooting

### **Проблема 1: "Port 5432 already in use"**

**Решение:**
```bash
# Остановить PostgreSQL если запущен локально
# Services → PostgreSQL → Stop

# Или поменять порт в docker-compose.yml
ports:
  - "5433:5432"  # Внешний порт 5433
```

---

### **Проблема 2: "ModuleNotFoundError"**

**Решение:**
```bash
# Проверить что venv активирован
.\venv\Scripts\Activate.ps1

# Переустановить зависимости
pip install -r requirements.txt --upgrade
```

---

### **Проблема 3: "npm install fails"**

**Решение:**
```bash
# Очистить кеш
npm cache clean --force

# Удалить node_modules
rm -r node_modules
rm package-lock.json

# Переустановить
npm install
```

---

### **Проблема 4: "Database connection refused"**

**Решение:**
```bash
# Проверить что PostgreSQL запущен
docker ps | findstr postgres

# Если нет, запустить
docker-compose up -d postgres

# Проверить подключение
psql -U postgres -h localhost -p 5432
```

---

### **Проблема 5: "CORS error в браузере"**

**Решение:**

Убедитесь что в `.env` backend:
```env
CORS_ORIGINS=http://localhost:3000
```

Или в `src/main.py`:
```python
cors_origins = ["http://localhost:3000"]
```

---

## 📖 Пошаговая Проверка

### **1. Проверка Backend:**

```bash
# Запустить backend
python src/main.py

# В другом терминале:
curl http://localhost:8000/health

# Должен вернуть:
# {"status": "healthy", "version": "2.0.0"}
```

### **2. Проверка Dashboard API:**

```bash
# Executive dashboard
curl http://localhost:8000/api/dashboard/executive

# PM dashboard
curl http://localhost:8000/api/dashboard/pm

# Developer dashboard
curl http://localhost:8000/api/dashboard/developer
```

### **3. Проверка Frontend:**

1. Откройте http://localhost:3000
2. Должна загрузиться Login page
3. Войдите (любые credentials в dev mode)
4. Должны увидеть dashboard!

---

## 🎨 Что вы увидите

### **Login Page:**
```
┌────────────────────────────────┐
│                                │
│       1C AI Stack              │
│   Enterprise AI Platform       │
│                                │
│  ┌──────────────────────────┐ │
│  │ Email                    │ │
│  │ [input field]            │ │
│  │                          │ │
│  │ Password                 │ │
│  │ [input field]            │ │
│  │                          │ │
│  │ [Sign In Button]         │ │
│  │                          │ │
│  │ Or continue with:        │ │
│  │ [G] [M] [GitHub]         │ │
│  └──────────────────────────┘ │
│                                │
└────────────────────────────────┘
```

### **Executive Dashboard:**
```
┌──────────────────────────────────────┐
│ TopNav: Search | Notifications       │
├────┬─────────────────────────────────┤
│Side│ 📊 Executive Dashboard           │
│Nav │ ┌────┐ ┌────┐ ┌────┐ ┌────┐    │
│    │ │🟢  │ │💰  │ │👥  │ │📈  │    │
│📊 │ │95  │ │45K │ │1234│ │+23%│    │
│📁 │ └────┘ └────┘ └────┘ └────┘    │
│👥 │                                  │
│⚙️ │ [Revenue Chart] [Alerts]        │
│    │                                  │
│🌙 │ [Objectives Progress]            │
└────┴─────────────────────────────────┘
```

---

## ✅ Checklist для успешного запуска

### **Backend:**
- [ ] Docker Desktop запущен
- [ ] PostgreSQL container running
- [ ] Redis container running
- [ ] .env файл создан с правильными ключами
- [ ] Dependencies установлены (`pip install -r requirements.txt`)
- [ ] Database migrations выполнены
- [ ] Backend запущен (`python src/main.py`)
- [ ] http://localhost:8000/docs открывается

### **Frontend:**
- [ ] Node.js 18+ установлен
- [ ] `cd portal` выполнено
- [ ] `npm install` выполнен успешно
- [ ] `.env` файл создан
- [ ] `npm run dev` запущен
- [ ] http://localhost:3000 открывается
- [ ] Login page отображается

### **Testing:**
- [ ] Можете залогиниться
- [ ] Dashboard загружается
- [ ] KPI cards показываются
- [ ] Navigation работает

---

## 🎯 Быстрый Тест

### **5-минутный тест:**

```bash
# Terminal 1: Backend
python src/main.py

# Terminal 2: Frontend
cd portal && npm run dev

# Terminal 3: Проверка
curl http://localhost:8000/health
curl http://localhost:8000/api/dashboard/executive

# Browser: http://localhost:3000
# Login → Dashboard должен загрузиться!
```

**Если все 3 работают → SUCCESS!** ✅

---

## 📊 Что тестировать

### **1. Authentication:**
- [ ] Login page загружается
- [ ] Можно ввести email/password
- [ ] Кнопка "Sign In" работает
- [ ] После логина → redirect на dashboard

### **2. Executive Dashboard:**
- [ ] 4 KPI cards показываются
- [ ] Health indicator (🟢/🟡/🔴)
- [ ] Revenue chart placeholder
- [ ] Alerts (если есть)
- [ ] Objectives progress bars

### **3. Navigation:**
- [ ] Sidebar collapsible (toggle button)
- [ ] Navigation items clickable
- [ ] Переход между dashboards работает
- [ ] TopNav search visible
- [ ] Notifications icon visible
- [ ] User avatar + menu

### **4. PM Dashboard:**
- [ ] Project summary cards
- [ ] Timeline view
- [ ] Team workload bars
- [ ] Sprint progress

### **5. Developer Console:**
- [ ] Assigned tasks list
- [ ] Code reviews panel
- [ ] Build status
- [ ] Code quality metrics

---

## 🐛 Debug Mode

### **Включить подробное логирование:**

**Backend:**
```python
# src/main.py - добавить в начало
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Frontend:**
```typescript
// src/lib/api-client.ts - добавить
apiClient.interceptors.request.use(config => {
  console.log('API Request:', config);
  return config;
});

apiClient.interceptors.response.use(response => {
  console.log('API Response:', response);
  return response;
});
```

---

## 📱 Mobile Testing

### **В браузере:**
```
1. Откройте http://localhost:3000
2. F12 (DevTools)
3. Toggle Device Toolbar (Ctrl+Shift+M)
4. Выберите iPhone 14 Pro или другое устройство
5. Тестируйте responsive design
```

---

## 🎨 Dark Mode Testing

```
1. Login
2. Top right corner → Moon icon
3. Click to toggle dark mode
4. Проверьте что все компоненты поддерживают dark theme
```

---

## ⚡ Performance Check

### **Backend:**
```bash
# В другом терминале
curl -w "@curl-format.txt" http://localhost:8000/api/dashboard/executive

# Создайте curl-format.txt:
time_total: %{time_total}s

# Должно быть < 1s
```

### **Frontend:**
```
1. F12 → Network tab
2. Reload page
3. Проверьте:
   - Initial load < 2s
   - API calls < 500ms
   - No failed requests
```

---

## 🔍 Пример тестового сценария

### **Сценарий 1: Executive проверяет статус проекта**

```
1. Логин как Executive
   - Email: exec@test.com
   - Password: test123

2. Видит Executive Dashboard
   - ✅ Health: 🟢 Healthy (95)
   - ✅ ROI: €45.2K (+15%)
   - ✅ Users: 1,234 (+156)
   - ✅ Growth: +23%

3. Проверяет alerts
   - ⚠️ Budget at 85%
   - ✅ Sprint on track

4. Смотрит objectives
   - Launch SaaS: 80% (On Track)
   - 100 Customers: 35% (Behind)
   - €50K MRR: 10% (On Track)

5. Экспортирует отчет (кнопка)

RESULT: Executive понял статус за 2 минуты! ✅
```

---

### **Сценарий 2: PM проверяет team workload**

```
1. Логин как PM
   - Email: pm@test.com

2. Видит PM Dashboard
   - Active projects: 12
   - Completed: 45
   - At risk: 2

3. Смотрит team workload
   - Alice: 80% (normal)
   - Bob: 60% (available)
   - Carol: 100% (⚠️ overloaded)

4. Перераспределяет задачи
   - Move task from Carol to Bob

RESULT: PM оптимизировал команду! ✅
```

---

### **Сценарий 3: Developer начинает работу**

```
1. Логин как Developer
   - Email: dev@test.com

2. Видит Developer Console
   - 2 assigned tasks
   - 1 code review pending
   - Build: ✅ Success
   - Coverage: 85%

3. Кликает на task
   - Opens task details

4. Кликает "Ask AI"
   - AI chat sidebar opens

RESULT: Developer ready to code! ✅
```

---

## 📊 Expected Results

### **После запуска должно работать:**

**Backend:**
✅ Health endpoint (200 OK)  
✅ Dashboard endpoints (200 OK)  
✅ Swagger UI доступен  
✅ CORS настроен правильно  
✅ Database connection работает  

**Frontend:**
✅ App загружается (< 2s)  
✅ Login page показывается  
✅ Authentication работает  
✅ Dashboard routing работает  
✅ API calls успешны  
✅ UI responsive  
✅ Dark mode работает  

---

## 🚀 Быстрый старт (TL;DR)

```bash
# 1. Start infrastructure
docker-compose up -d postgres redis

# 2. Start backend
python src/main.py

# 3. Start frontend (new terminal)
cd portal
npm install
npm run dev

# 4. Open browser
# http://localhost:3000

# 5. Login with any email/password (dev mode)

# 6. See your dashboard!
```

**Time: ~5 минут** ⚡

---

## 📞 Need Help?

### **Check logs:**

**Backend:**
```bash
# Logs in console
# Or check: logs/api.log
```

**Frontend:**
```bash
# Browser DevTools Console (F12)
# Check for errors
```

**Docker:**
```bash
# Check service logs
docker-compose logs postgres
docker-compose logs redis
```

---

### **Common Commands:**

```bash
# Restart backend
# Ctrl+C → python src/main.py

# Restart frontend
# Ctrl+C → npm run dev

# Restart Docker services
docker-compose restart postgres redis

# Check what's running
docker-compose ps
netstat -ano | findstr ":8000"
netstat -ano | findstr ":3000"
```

---

## ✅ Success Indicators

**Вы успешно запустили если:**
- ✅ Backend отвечает на http://localhost:8000/health
- ✅ Frontend загружается на http://localhost:3000
- ✅ Login page показывается
- ✅ Можете залогиниться
- ✅ Dashboard загружается с данными
- ✅ Navigation работает
- ✅ No errors в console

**Все ✅ → Поздравляю, всё работает!** 🎉

---

## 🎯 Next Steps After Local Testing

1. ✅ Test all dashboards (Executive, PM, Developer)
2. ✅ Test all user flows
3. ✅ Check responsive (mobile, tablet)
4. ✅ Test dark mode
5. ✅ Performance check
6. ✅ Report any bugs
7. 🚀 **Deploy to staging!**

---

**Happy Testing!** 🧪✨

**Questions?** Check [docs/README.md](../README.md)


