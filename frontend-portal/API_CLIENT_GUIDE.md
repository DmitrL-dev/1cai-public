# API Client Integration Guide

## Обзор

`api-client.ts` был рефакторирован для работы с реальным FastAPI backend вместо mock данных.

## Изменения

### До (Mock данные):

```typescript
const mockOwnerDashboard = { ... };
export const api = {
  dashboard: {
    owner: () => Promise.resolve({ data: mockOwnerDashboard }),
  },
};
```

### После (Реальный API):

```typescript
const dashboardAPI = {
  owner: async () => {
    return axiosInstance.get("/api/dashboard/owner");
  },
};
```

## Новые Возможности

### 1. Environment Configuration

```typescript
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
```

### 2. Request/Response Interceptors

- **Auth**: Автоматическое добавление Bearer token
- **Error Handling**: Обработка 401, 403, 500+ ошибок
- **Timeout**: 30 секунд

### 3. AI Services API

```typescript
api.ai.query(query, context);
api.ai.searchCode(query, language);
api.ai.getScenarios(context);
api.ai.analyzeScreenshot(imageData);
```

## Использование

### Dashboard API

```typescript
import { api } from "@/lib/api-client";

// Get owner dashboard
const response = await api.dashboard.owner();
console.log(response.data);
```

### AI Query

```typescript
// Query AI Orchestrator
const result = await api.ai.query("Как создать документ?", "1С:Предприятие");
```

### VLM Screenshot Analysis

```typescript
// Analyze screenshot
const file = new File([blob], "screenshot.jpg");
const analysis = await api.ai.analyzeScreenshot(file);
```

## Backend Endpoints Required

Для полной работы frontend требуются следующие backend endpoints:

### Dashboard

- `GET /api/dashboard/owner`
- `GET /api/dashboard/executive`
- `GET /api/dashboard/pm`
- `GET /api/dashboard/developer`

### AI Services

- `POST /api/ai/query` - AI Orchestrator
- `POST /api/ai/code/search` - Code Graph Service
- `POST /api/ai/scenarios` - Scenario Hub
- `POST /api/vlm/analyze` - VLM Server (уже работает!)

## Environment Variables

Создайте `.env` файл:

```bash
cp .env.example .env
```

Настройте переменные:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_ENABLE_AI_FEATURES=true
```

## Тестирование

### 1. Проверка VLM Server

```bash
curl http://127.0.0.1:8000/health
```

### 2. Проверка Frontend

```bash
cd frontend-portal
npm run dev
```

Откройте http://localhost:3001/ и проверьте консоль браузера на наличие ошибок API.

## Следующие Шаги

1. ✅ Создать backend endpoints для dashboard
2. ✅ Интегрировать gRPC с FastAPI
3. ✅ Протестировать все API endpoints
4. ✅ Добавить error boundaries в React компоненты
