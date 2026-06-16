# Мультимедиа Генерация API - Документация

Модуль `multimediaGeneration.ts` предоставляет функции для интеграции с Audio/Video Generation API для создания демонстрационного контента.

## Основные функции

### generateDemoAudio

Генерирует аудио из текста с помощью audio_kit.

```typescript
import { generateDemoAudio } from '../utils/multimediaGeneration';

const result = await generateDemoAudio(
  'Текст для озвучивания',
  {
    voiceType: 'professional',  // тип голоса
    emotion: 'neutral',         // эмоция: happy, sad, angry, fearful, disgusted, surprised, neutral
    speed: 1.0,                // скорость речи (0.5 - 2.0)
    pitch: 0,                  // высота тона (-12 до 12)
    volume: 5.0                // громкость (0.0 - 10.0)
  }
);
```

**Параметры:**
- `text` (string, обязательный): Текст для озвучивания (максимум 1000 символов)
- `options` (AudioGenerationOptions, опциональный): Дополнительные настройки

**Возвращает:**
```typescript
{
  success: boolean;
  audioUrl?: string;
  error?: string;
}
```

### generateDemoVideo

Генерирует видео из текстового описания с помощью video_kit.

```typescript
import { generateDemoVideo } from '../utils/multimediaGeneration';

const result = await generateDemoVideo(
  'Описание видео',
  ['/path/to/image1.png', '/path/to/image2.png'],  // опциональные изображения
  {
    duration: 6,                    // продолжительность (6 или 10 секунд)
    resolution: '768P',             // разрешение: '768P' или '1080P'
    referenceType: 'first_frame'    // тип ссылки: 'first_frame' или 'subject'
  }
);
```

**Параметры:**
- `prompt` (string, обязательный): Текстовое описание видео (максимум 500 символов)
- `images` (string[], опциональный): Массив путей к изображениям
- `options` (VideoGenerationOptions, опциональный): Дополнительные настройки

**Возвращает:**
```typescript
{
  success: boolean;
  videoUrl?: string;
  error?: string;
}
```

## Ролевые демо

### generateRoleDemo

Генерирует демо-материалы для конкретной роли.

```typescript
import { generateRoleDemo } from '../utils/multimediaGeneration';

// Доступные роли: 'architect', 'developer', 'tester', 'pm', 'ba'
const architectDemo = await generateRoleDemo('architect');

console.log('Аудио для презентации:', architectDemo.audio);
console.log('Видео презентации:', architectDemo.video);
```

### generateAllRoleDemos

Пакетная генерация демо-материалов для всех ролей.

```typescript
import { generateAllRoleDemos } from '../utils/multimediaGeneration';

const allDemos = await generateAllRoleDemos();

/*
Результат:
{
  architect: { audio: '...', video: '...' },
  developer: { audio: '...', video: '...' },
  tester: { audio: '...', video: '...' },
  pm: { audio: '...', video: '...' },
  ba: { audio: '...', video: '...' }
}
*/
```

## Готовые демо-функции

### Архитектор (architect)
- **Назначение**: Презентации архитектурных решений
- **Тип контента**: Технические презентации, схемы, диаграммы
- **Особенности**: Профессиональный тон, четкая дикция

### Разработчик (developer)  
- **Назначение**: Демонстрация кода и технических решений
- **Тип контента**: Демо кода, технические объяснения
- **Особенности**: Техническая терминология, код на экране

### Тестировщик (tester)
- **Назначение**: Видео-инструкции для тестирования
- **Тип контента**: Пошаговые инструкции, тест-кейсы
- **Особенности**: Медленный темп, выделение элементов интерфейса

### PM (pm)
- **Назначение**: Видео отчеты для руководства
- **Тип контента**: Отчеты, презентации результатов
- **Особенности**: Исполнительный тон, позитивная интонация

### BA (ba)
- **Назначение**: Презентации требований
- **Тип контента**: Бизнес-требования, пользовательские истории
- **Особенности**: Бизнес-терминология, структурированная подача

## Примеры использования

### Простое аудио

```typescript
import { generateDemoAudio } from '../utils/multimediaGeneration';

const result = await generateDemoAudio(
  'Добро пожаловать в систему 1С!'
);

if (result.success) {
  console.log('Аудио создано:', result.audioUrl);
} else {
  console.error('Ошибка:', result.error);
}
```

### Видео с изображениями

```typescript
import { generateDemoVideo } from '../utils/multimediaGeneration';

const result = await generateDemoVideo(
  'Презентация нового интерфейса 1С',
  [
    '/screenshots/step1.png',
    '/screenshots/step2.png', 
    '/screenshots/step3.png'
  ],
  {
    duration: 10,
    resolution: '1080P'
  }
);
```

### React компонент

```tsx
import React, { useState } from 'react';
import { generateDemoAudio, generateDemoVideo } from '../utils/multimediaGeneration';

function MultimediaGenerator() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{audio?: string, video?: string}>({});

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const audioResult = await generateDemoAudio('Текст для озвучивания');
      const videoResult = await generateDemoVideo('Описание видео');
      
      setResult({
        audio: audioResult.audioUrl,
        video: videoResult.videoUrl
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button onClick={handleGenerate} disabled={loading}>
        {loading ? 'Генерация...' : 'Сгенерировать демо'}
      </button>
      
      {result.audio && <audio controls src={result.audio} />}
      {result.video && <video controls src={result.video} />}
    </div>
  );
}
```

## Обработка ошибок

Все функции возвращают объект с полем `success`. Всегда проверяйте результат:

```typescript
const result = await generateDemoAudio(text);

if (!result.success) {
  // Обработка ошибки
  console.error('Ошибка генерации аудио:', result.error);
  // Показать сообщение пользователю
  showErrorMessage(result.error);
  return;
}

// Успешная генерация
useGeneratedAudio(result.audioUrl);
```

## Ограничения

- **Текст для аудио**: максимум 1000 символов
- **Промпт для видео**: максимум 500 символов  
- **Изображения для видео**: поддерживаются основные форматы (PNG, JPEG)
- **Длительность видео**: 6 или 10 секунд
- **Разрешение видео**: 768P или 1080P

## Типы данных

```typescript
interface AudioGenerationOptions {
  voiceType?: string;
  emotion?: 'happy' | 'sad' | 'angry' | 'fearful' | 'disgusted' | 'surprised' | 'neutral';
  speed?: number;  // 0.5 - 2.0
  pitch?: number;  // -12 до 12
  volume?: number; // 0.0 - 10.0
}

interface VideoGenerationOptions {
  duration?: number;         // 6 или 10
  resolution?: '768P' | '1080P';
  referenceType?: 'first_frame' | 'subject';
}
```

## Интеграция с проектом

1. Импортируйте функции из модуля:
```typescript
import { 
  generateDemoAudio, 
  generateDemoVideo,
  generateRoleDemo 
} from '../utils/multimediaGeneration';
```

2. Используйте в компонентах, API роутах, или других частях приложения

3. Для пакетной генерации используйте `generateAllRoleDemos()`

4. Проверяйте результаты и обрабатывайте ошибки

## Демо-файлы

- `multimediaGeneration.ts` - основной модуль
- `multimediaDemo.ts` - примеры использования
- `index.ts` - экспорт функций

Запустите демо-файл для просмотра всех примеров в действии.
