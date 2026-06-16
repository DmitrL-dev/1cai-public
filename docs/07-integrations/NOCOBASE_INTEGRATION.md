# NocoBase Integration — Руководство

**Версия:** 1.0 | **Статус:** ✅ Available

## Обзор

**NocoBase** — low-code платформа для создания бизнес-приложений. Интеграция с 1C AI Stack позволяет использовать AI capabilities в NocoBase приложениях.

**Возможности:**
- 📊 AI-powered dashboards в NocoBase
- 🤖 AI assistants в NocoBase UI
- 📝 Автоматическая генерация форм из 1C metadata
- 🔄 Синхронизация данных 1C ↔ NocoBase

## Quick Start

```bash
# 1. Установка NocoBase plugin
cd external/nocobase
yarn add @1c-ai-stack/nocobase-plugin

# 2. Активация plugin
npx nocobase pm enable @1c-ai-stack/nocobase-plugin

# 3. Конфигурация
cat > .env << EOF
1C_AI_STACK_URL=http://localhost:8000
1C_AI_STACK_API_KEY=your_key
EOF

# 4. Restart
npx nocobase restart
```

## Configuration

```javascript
// nocobase.config.js
module.exports = {
  plugins: [
    ['@1c-ai-stack/nocobase-plugin', {
      apiUrl: process.env.1C_AI_STACK_URL,
      apiKey: process.env.1C_AI_STACK_API_KEY,
      features: {
        aiAssistants: true,
        autoDashboards: true,
        dataSync: true
      }
    }]
  ]
};
```

## Features

### 1. AI Dashboards

```javascript
// Создание AI-powered dashboard
import { AIDashboard } from '@1c-ai-stack/nocobase-plugin';

const dashboard = new AIDashboard({
  title: 'Sales Analytics',
  dataSource: '1c_sales_data',
  aiFeatures: {
    insights: true,
    predictions: true,
    recommendations: true
  }
});
```

### 2. AI Assistants

```javascript
// Добавление AI assistant в форму
import { AIAssistant } from '@1c-ai-stack/nocobase-plugin';

<Form>
  <AIAssistant
    context="order_processing"
    suggestions={true}
    autoComplete={true}
  />
</Form>
```

### 3. Data Sync

```javascript
// Синхронизация данных
import { DataSync } from '@1c-ai-stack/nocobase-plugin';

const sync = new DataSync({
  source: '1c_database',
  target: 'nocobase_collection',
  schedule: '*/15 * * * *', // Every 15 minutes
  mapping: {
    '1c_field': 'nocobase_field'
  }
});

await sync.start();
```

## API Integration

```javascript
// Использование 1C AI Stack API из NocoBase
import { AIStackClient } from '@1c-ai-stack/nocobase-plugin';

const client = new AIStackClient({
  apiUrl: process.env.1C_AI_STACK_URL,
  apiKey: process.env.1C_AI_STACK_API_KEY
});

// Code review
const review = await client.codeReview.submit({
  code: bslCode,
  language: 'bsl'
});

// AI assistant
const response = await client.assistants.chat({
  message: 'How to optimize this query?',
  context: { code: sqlQuery }
});
```

## Examples

### Example 1: AI-powered Form

```javascript
import { Form, AIField } from '@1c-ai-stack/nocobase-plugin';

<Form>
  <AIField
    name="description"
    aiFeatures={{
      autoComplete: true,
      suggestions: true,
      validation: true
    }}
  />
</Form>
```

### Example 2: Automated Dashboard

```javascript
const dashboard = await client.analytics.createDashboard({
  dataSource: '1c_sales',
  autoGenerate: true,
  aiInsights: true
});
```

## Troubleshooting

**Проблема:** Plugin не активируется  
**Решение:** Проверьте версию NocoBase (требуется >= 0.14.0)

**Проблема:** API connection failed  
**Решение:** Проверьте 1C_AI_STACK_URL и firewall

## FAQ

**Q: Какая версия NocoBase поддерживается?**  
A: NocoBase >= 0.14.0

**Q: Нужна ли лицензия?**  
A: Нет, plugin бесплатный

---

**См. также:**
- [NocoBase Documentation](https://docs.nocobase.com)
- [1C AI Stack API](../06-features/README.md)
