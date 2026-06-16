# Модуль интеграции с Image Generation API

Модуль для генерации изображений через AI-ассистентов в демонстрационном проекте 1C AI Assistants.

## 📋 Содержание

- [Возможности](#возможности)
- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [API Reference](#api-reference)
- [Роли ассистентов](#роли-ассистентов)
- [Примеры использования](#примеры-использования)
- [Интеграция с UI](#интеграция-с-ui)
- [Тестирование](#тестирование)

## 🚀 Возможности

- ✅ Генерация изображений для 5 ролей ассистентов
- ✅ Предопределенные промпты для каждой роли
- ✅ Поддержка пользовательских промптов
- ✅ Валидация входных данных
- ✅ Батчевая генерация изображений
- ✅ Типизация TypeScript
- ✅ Обработка ошибок
- ✅ Подробное логирование

## 🛠️ Установка

Модуль уже включен в проект и не требует дополнительной установки:

```typescript
import { generateDemoImage, AssistantRole } from '@/utils/imageGeneration';
```

## ⚡ Быстрый старт

### Базовое использование

```typescript
import { generateDemoImage, AssistantRole } from '@/utils/imageGeneration';

// Генерация изображения для архитектора
const result = await generateDemoImage(
  'Clean architecture diagram', 
  'architect'
);

if (result.success) {
  console.log('Изображение создано:', result.imageUrl);
} else {
  console.error('Ошибка:', result.error);
}
```

### Генерация примера для роли

```typescript
import { generateRoleExampleImage } from '@/utils/imageGeneration';

// Сгенерировать пример для разработчика
const developerResult = await generateRoleExampleImage('developer');
```

### Работа с несколькими ролями

```typescript
import { generateMultipleRoleImages } from '@/utils/imageGeneration';

const roles = ['architect', 'developer', 'tester'] as AssistantRole[];
const results = await generateMultipleRoleImages(roles);
```

## 📚 API Reference

### Основные функции

#### `generateDemoImage(prompt: string, role: AssistantRole): Promise<ImageGenerationResult>`

Генерирует изображение на основе промпта для конкретной роли.

**Параметры:**
- `prompt` - Текстовое описание изображения
- `role` - Роль ассистента

**Возвращает:**
```typescript
interface ImageGenerationResult {
  success: boolean;
  imageUrl?: string;
  error?: string;
  role: AssistantRole;
  prompt: string;
  timestamp: Date;
}
```

#### `generateRoleExampleImage(role: AssistantRole, exampleIndex?: number): Promise<ImageGenerationResult>`

Генерирует изображение с предопределенным примером для роли.

#### `generateMultipleRoleImages(roles: AssistantRole[]): Promise<ImageGenerationResult[]>`

Генерирует изображения для нескольких ролей одновременно.

#### `generateAllRolesPreview(): Promise<{[key in AssistantRole]: ImageGenerationResult}>`

Создает предварительный просмотр для всех ролей.

### Вспомогательные функции

#### `getAvailableRoles(): AssistantRole[]`

Возвращает список всех доступных ролей.

#### `getRoleDescription(role: AssistantRole): string`

Возвращает описание роли.

#### `getRoleExamples(role: AssistantRole): string[]`

Возвращает массив примеров промптов для роли.

#### `validatePrompt(prompt: string, role: AssistantRole): boolean`

Валидирует промпт для роли.

## 👥 Роли ассистентов

### Архитектор (`architect`)

**Описание:** Схемы и диаграммы систем

**Примеры промптов:**
- Clean architecture diagram showing layers
- Microservices architecture with API Gateway
- Event-driven architecture with message brokers
- Database schema design with entity relationships
- System integration architecture for 1C ERP

**Стиль:** Профессиональные технические диаграммы, чистые линии, синяя и серая цветовая схема

### Разработчик (`developer`)

**Описание:** Код и пользовательские интерфейсы

**Примеры промптов:**
- Modern web application dashboard
- 1C Enterprise form design
- API documentation interface
- Code editor with syntax highlighting
- Responsive mobile app wireframe

**Стиль:** Современный UI дизайн, чистый интерфейс, дружелюбные цвета для разработчиков

### Тестировщик (`tester`)

**Описание:** Тест-кейсы и сценарии тестирования

**Примеры промптов:**
- Test case flow diagram
- Quality assurance process flowchart
- Bug tracking interface
- Test automation strategy diagram
- Performance testing dashboard

**Стиль:** Структурированные диаграммы потоков, цвета рабочего процесса тестирования (зеленый, желтый, красный)

### PM (`pm`)

**Описание:** Планы проектов и аналитические дашборды

**Примеры промптов:**
- Project timeline with Gantt chart
- Business KPI dashboard
- Resource allocation chart
- Risk management matrix
- Sprint planning board

**Стиль:** Стиль бизнес-дашборда, профессиональные графики, корпоративные цвета

### BA (`ba`)

**Описание:** Бизнес-требования и прототипы процессов

**Примеры промптов:**
- Business process flowchart (AS-IS vs TO-BE)
- User story map
- Requirements traceability matrix
- Stakeholder analysis diagram
- Use case diagram

**Стиль:** Диаграммы бизнес-процессов, четкие иконки, профессиональный стиль документации

## 💡 Примеры использования

### 1. Интеграция в React компонент

```typescript
import React, { useState } from 'react';
import { generateDemoImage, AssistantRole, ImageGenerationResult } from '@/utils/imageGeneration';

const ImageGenerator: React.FC = () => {
  const [result, setResult] = useState<ImageGenerationResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleGenerate = async (role: AssistantRole, prompt: string) => {
    setLoading(true);
    try {
      const imageResult = await generateDemoImage(prompt, role);
      setResult(imageResult);
    } catch (error) {
      console.error('Ошибка генерации:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {loading && <div>Генерация изображения...</div>}
      {result && (
        <div>
          {result.success ? (
            <img src={result.imageUrl} alt="Generated" />
          ) : (
            <div>Ошибка: {result.error}</div>
          )}
        </div>
      )}
    </div>
  );
};
```

### 2. Генерация галереи изображений

```typescript
import { generateAllRolesPreview } from '@/utils/imageGeneration';

const generateGallery = async () => {
  const preview = await generateAllRolesPreview();
  
  const gallery = Object.entries(preview).map(([role, result]) => ({
    role,
    imageUrl: result.success ? result.imageUrl : null,
    error: result.error
  }));
  
  return gallery;
};
```

### 3. Кастомная генерация с валидацией

```typescript
import { validatePrompt, generateDemoImage, AssistantRole } from '@/utils/imageGeneration';

const customGenerate = async (role: AssistantRole, customPrompt: string) => {
  if (!validatePrompt(customPrompt, role)) {
    throw new Error('Некорректный промпт');
  }
  
  const result = await generateDemoImage(customPrompt, role);
  return result;
};
```

## 🎨 Интеграция с UI

### Использование в демо-страницах

```typescript
// В LiveDemoPage.tsx
import { generateRoleExampleImage, AssistantRole } from '@/utils/imageGeneration';

const LiveDemoPage: React.FC = () => {
  const generateImageForRole = async (role: AssistantRole) => {
    const result = await generateRoleExampleImage(role);
    return result.imageUrl;
  };

  // ... компонент UI
};
```

### Компонент выбора роли

```typescript
import React from 'react';
import { getAvailableRoles, getRoleDescription } from '@/utils/imageGeneration';

const RoleSelector: React.FC<{ onSelect: (role: AssistantRole) => void }> = ({ onSelect }) => {
  const roles = getAvailableRoles();

  return (
    <div className="role-selector">
      {roles.map(role => (
        <button key={role} onClick={() => onSelect(role)}>
          <h3>{role.toUpperCase()}</h3>
          <p>{getRoleDescription(role)}</p>
        </button>
      ))}
    </div>
  );
};
```

## 🧪 Тестирование

### Запуск тестов

```bash
# Тестирование всех функций модуля
npm run test:image-generation

# Интерактивная демонстрация
npm run demo:image-generation
```

### Примеры тестов

```typescript
import { testImageGenerationModule } from '@/utils/imageGenerationExamples';

// Запуск всех тестов
await testImageGenerationModule();

// Тестирование конкретной функции
import { generateDemoImage } from '@/utils/imageGeneration';

const result = await generateDemoImage('Test diagram', 'architect');
expect(result.success).toBe(true);
```

## 📝 Логирование

Модуль поддерживает подробное логирование:

```typescript
import { generateDemoImage } from '@/utils/imageGeneration';

// Логирование результата
const result = await generateDemoImage('Architecture diagram', 'architect');
console.log(`Роль: ${result.role}`);
console.log(`Статус: ${result.success ? 'Успех' : 'Ошибка'}`);
console.log(`Время: ${result.timestamp.toLocaleString()}`);
```

## ⚠️ Обработка ошибок

Модуль включает comprehensive обработку ошибок:

```typescript
try {
  const result = await generateDemoImage('Complex diagram', 'architect');
  if (!result.success) {
    // Обработка ошибки генерации
    console.error('Ошибка генерации:', result.error);
  }
} catch (error) {
  // Обработка системных ошибок
  console.error('Системная ошибка:', error);
}
```

## 🔧 Конфигурация

### Настройка стилей ролей

```typescript
// В imageGeneration.ts можно настроить стили для каждой роли
const ROLE_CONFIGS: Record<AssistantRole, RoleConfig> = {
  architect: {
    style: "professional technical diagram, clean lines, blue and gray color scheme",
    // ... другие настройки
  }
  // ... остальные роли
};
```

### Добавление новой роли

```typescript
// 1. Добавить в AssistantRole
export type AssistantRole = /* существующие роли */ | 'new_role';

// 2. Добавить конфигурацию в ROLE_CONFIGS
const ROLE_CONFIGS: Record<AssistantRole, RoleConfig> = {
  // ... существующие роли,
  new_role: {
    basePrompt: "New role description",
    examples: [
      "Example 1",
      "Example 2"
    ],
    style: "Custom style description",
    description: "Описание новой роли"
  }
};
```

## 📖 Дополнительная информация

- **Версия:** 1.0.0
- **Совместимость:** TypeScript 4.0+
- **Зависимости:** React 18+, Node.js 14+
- **Лицензия:** MIT

## 🤝 Поддержка

Для получения помощи и сообщения об ошибках создавайте issue в репозитории проекта.

## Возможности

TODO: Добавить содержание раздела.


## Установка

TODO: Добавить содержание раздела.


## Быстрый Старт

TODO: Добавить содержание раздела.


## Api Reference

TODO: Добавить содержание раздела.


## Роли Ассистентов

TODO: Добавить содержание раздела.


## Примеры Использования

TODO: Добавить содержание раздела.


## Интеграция С Ui

TODO: Добавить содержание раздела.


## Тестирование

TODO: Добавить содержание раздела.
