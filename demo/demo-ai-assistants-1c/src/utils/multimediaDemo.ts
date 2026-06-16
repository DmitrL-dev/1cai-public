/**
 * Демонстрационный файл использования модуля multimediaGeneration
 * Показывает примеры использования функций генерации аудио и видео
 */

import { 
  generateDemoAudio, 
  generateDemoVideo, 
  generateRoleDemo,
  generateAllRoleDemos,
  type AudioGenerationOptions,
  type VideoGenerationOptions
} from './multimediaGeneration';

/**
 * Пример 1: Простая генерация аудио
 */
async function simpleAudioExample() {
  console.log('=== Пример простой генерации аудио ===');
  
  const result = await generateDemoAudio(
    'Добро пожаловать в систему 1С! Это демо генерации аудио.',
    {
      voiceType: 'default',
      emotion: 'happy',
      speed: 1.0,
      volume: 7.0
    }
  );
  
  if (result.success) {
    console.log('Аудио успешно создано:', result.audioUrl);
  } else {
    console.error('Ошибка генерации аудио:', result.error);
  }
}

/**
 * Пример 2: Простая генерация видео
 */
async function simpleVideoExample() {
  console.log('=== Пример простой генерации видео ===');
  
  const result = await generateDemoVideo(
    'Интерфейс системы 1С с плавными переходами между формами',
    [],
    {
      duration: 6,
      resolution: '768P'
    }
  );
  
  if (result.success) {
    console.log('Видео успешно создано:', result.videoUrl);
  } else {
    console.error('Ошибка генерации видео:', result.error);
  }
}

/**
 * Пример 3: Генерация с изображениями
 */
async function videoWithImagesExample() {
  console.log('=== Пример генерации видео с изображениями ===');
  
  const result = await generateDemoVideo(
    'Демонстрация нового интерфейса 1С с плавными переходами',
    [
      '/images/screenshot1.png',
      '/images/screenshot2.png',
      '/images/screenshot3.png'
    ],
    {
      duration: 10,
      resolution: '1080P',
      referenceType: 'first_frame'
    }
  );
  
  if (result.success) {
    console.log('Видео с изображениями создано:', result.videoUrl);
  } else {
    console.error('Ошибка генерации видео:', result.error);
  }
}

/**
 * Пример 4: Демо для конкретной роли
 */
async function roleSpecificExample() {
  console.log('=== Пример демо для архитектора ===');
  
  try {
    const result = await generateRoleDemo('architect');
    console.log('Демо для архитектора создано:');
    console.log('  Аудио:', result.audio);
    console.log('  Видео:', result.video);
  } catch (error) {
    console.error('Ошибка создания демо:', error);
  }
}

/**
 * Пример 5: Пакетная генерация для всех ролей
 */
async function allRolesExample() {
  console.log('=== Пример генерации демо для всех ролей ===');
  
  try {
    const results = await generateAllRoleDemos();
    
    console.log('Результаты генерации для всех ролей:');
    Object.entries(results).forEach(([role, content]) => {
      console.log(`\n${role.toUpperCase()}:`);
      console.log(`  Аудио: ${content.audio || 'Ошибка'}`);
      console.log(`  Видео: ${content.video || 'Ошибка'}`);
    });
  } catch (error) {
    console.error('Ошибка пакетной генерации:', error);
  }
}

/**
 * Пример 6: Настройки для разных типов контента
 */
async function customSettingsExamples() {
  console.log('=== Примеры настроек для разных типов контента ===');
  
  // Техническая документация
  const technicalAudio = await generateDemoAudio(
    'В этом разделе рассматривается архитектура системы...',
    {
      voiceType: 'technical',
      emotion: 'neutral',
      speed: 0.9,
      pitch: -1
    }
  );
  
  // Обучающий контент
  const trainingVideo = await generateDemoVideo(
    'Пошаговое руководство по работе с модулем 1С',
    [],
    {
      duration: 10,
      resolution: '1080P'
    }
  );
  
  // Отчет для руководства
  const executiveAudio = await generateDemoAudio(
    'Уважаемые коллеги, представляю квартальный отчет...',
    {
      voiceType: 'executive',
      emotion: 'happy',
      speed: 0.85,
      volume: 8.0
    }
  );
  
  console.log('Настройки созданы для разных типов контента');
}

/**
 * Пример использования в React компоненте
 */
export function createReactDemoComponent() {
  return `
import React, { useState } from 'react';
import { generateDemoAudio, generateDemoVideo } from '../utils/multimediaGeneration';

function MultimediaDemo() {
  const [audioUrl, setAudioUrl] = useState<string>('');
  const [videoUrl, setVideoUrl] = useState<string>('');
  const [loading, setLoading] = useState(false);
  
  const handleGenerateAudio = async () => {
    setLoading(true);
    try {
      const result = await generateDemoAudio(
        'Это демо генерации аудио в React компоненте'
      );
      if (result.success) {
        setAudioUrl(result.audioUrl!);
      }
    } finally {
      setLoading(false);
    }
  };
  
  const handleGenerateVideo = async () => {
    setLoading(true);
    try {
      const result = await generateDemoVideo(
        'Демо интерфейса 1С в React компоненте'
      );
      if (result.success) {
        setVideoUrl(result.videoUrl!);
      }
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div>
      <h2>Мультимедиа демо</h2>
      <button onClick={handleGenerateAudio} disabled={loading}>
        Сгенерировать аудио
      </button>
      <button onClick={handleGenerateVideo} disabled={loading}>
        Сгенерировать видео
      </button>
      
      {audioUrl && (
        <audio controls>
          <source src={audioUrl} type="audio/mpeg" />
        </audio>
      )}
      
      {videoUrl && (
        <video controls width="400">
          <source src={videoUrl} type="video/mp4" />
        </video>
      )}
    </div>
  );
}

export default MultimediaDemo;
  `;
}

/**
 * Запуск всех примеров
 */
async function runAllExamples() {
  console.log('Запуск всех демо-примеров...');
  
  try {
    await simpleAudioExample();
    await simpleVideoExample();
    await videoWithImagesExample();
    await roleSpecificExample();
    await allRolesExample();
    await customSettingsExamples();
    
    console.log('\n=== Все примеры выполнены ===');
  } catch (error) {
    console.error('Ошибка выполнения примеров:', error);
  }
}

// Экспорт функций для использования в других модулях
export {
  simpleAudioExample,
  simpleVideoExample,
  videoWithImagesExample,
  roleSpecificExample,
  allRolesExample,
  customSettingsExamples,
  runAllExamples
};

// Автоматический запуск при импорте (только для демо)
if (typeof window !== 'undefined' && window.location.search.includes('demo=true')) {
  runAllExamples();
}
