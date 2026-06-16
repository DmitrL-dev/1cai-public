/**
 * Примеры использования модуля генерации изображений для демонстрации AI-ассистентов
 */

import { 
  generateDemoImage, 
  generateRoleExampleImage, 
  generateMultipleRoleImages,
  generateAllRolesPreview,
  getAvailableRoles,
  getRoleDescription,
  getRoleExamples,
  validatePrompt,
  AssistantRole 
} from './imageGeneration';

/**
 * Демонстрация генерации изображений для всех ролей
 */
export async function demonstrateAllRoles(): Promise<void> {
  console.log('🎨 Демонстрация генерации изображений для всех ролей AI-ассистентов\n');

  const roles = getAvailableRoles();
  console.log(`Доступные роли: ${roles.join(', ')}\n`);

  try {
    // Генерация примеров для всех ролей
    console.log('🚀 Генерация изображений для всех ролей...');
    const results = await generateMultipleRoleImages(roles);
    
    results.forEach((result, index) => {
      const role = roles[index];
      console.log(`✅ ${role}: ${result.success ? 'Успешно' : 'Ошибка'}`);
      if (!result.success) {
        console.log(`   Ошибка: ${result.error}`);
      } else {
        console.log(`   Изображение: ${result.imageUrl}`);
      }
    });

  } catch (error) {
    console.error('❌ Ошибка демонстрации:', error);
  }
}

/**
 * Демонстрация для конкретной роли
 */
export async function demonstrateRole(role: AssistantRole): Promise<void> {
  console.log(`🎯 Демонстрация для роли: ${role}`);
  console.log(`Описание: ${getRoleDescription(role)}`);
  console.log(`Примеры промптов:`);
  
  const examples = getRoleExamples(role);
  examples.forEach((example, index) => {
    console.log(`  ${index + 1}. ${example}`);
  });

  try {
    console.log('\n🔄 Генерация изображения...');
    const result = await generateRoleExampleImage(role);
    
    if (result.success) {
      console.log(`✅ Успешно сгенерировано изображение: ${result.imageUrl}`);
    } else {
      console.log(`❌ Ошибка генерации: ${result.error}`);
    }

  } catch (error) {
    console.error('❌ Ошибка:', error);
  }
}

/**
 * Демонстрация пользовательского промпта
 */
export async function demonstrateCustomPrompt(role: AssistantRole, customPrompt: string): Promise<void> {
  console.log(`🎨 Демонстрация с пользовательским промптом для роли: ${role}`);
  console.log(`Промпт: "${customPrompt}"`);

  // Валидация промпта
  if (!validatePrompt(customPrompt, role)) {
    console.log('❌ Промпт не прошел валидацию');
    return;
  }

  try {
    console.log('\n🔄 Генерация изображения...');
    const result = await generateDemoImage(customPrompt, role);
    
    if (result.success) {
      console.log(`✅ Успешно сгенерировано изображение: ${result.imageUrl}`);
      console.log(`Время генерации: ${result.timestamp.toLocaleTimeString()}`);
    } else {
      console.log(`❌ Ошибка генерации: ${result.error}`);
    }

  } catch (error) {
    console.error('❌ Ошибка:', error);
  }
}

/**
 * Создание предварительного просмотра для демонстрации
 */
export async function createDemoPreview(): Promise<void> {
  console.log('📋 Создание предварительного просмотра для демонстрации...\n');

  try {
    const preview = await generateAllRolesPreview();
    
    Object.entries(preview).forEach(([role, result]) => {
      console.log(`🎭 ${role.toUpperCase()}: ${getRoleDescription(role as AssistantRole)}`);
      console.log(`   Статус: ${result.success ? '✅ Готово' : '❌ Ошибка'}`);
      if (result.success) {
        console.log(`   Изображение: ${result.imageUrl}`);
      } else {
        console.log(`   Ошибка: ${result.error}`);
      }
      console.log('');
    });

  } catch (error) {
    console.error('❌ Ошибка создания превью:', error);
  }
}

/**
 * Интерактивная демонстрация
 */
export async function interactiveDemo(): Promise<void> {
  const readline = require('readline');
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  console.log('🎮 Интерактивная демонстрация генерации изображений\n');
  console.log('Доступные команды:');
  console.log('  all - Показать все роли');
  console.log('  [роль] - Демонстрация конкретной роли (architect, developer, tester, pm, ba)');
  console.log('  custom [роль] [промпт] - Генерация с пользовательским промптом');
  console.log('  preview - Создать превью всех ролей');
  console.log('  quit - Выход\n');

  const question = (prompt: string): Promise<string> => {
    return new Promise(resolve => rl.question(prompt, resolve));
  };

  try {
    while (true) {
      const input = await question('Введите команду: ');
      const parts = input.trim().split(' ');
      const command = parts[0].toLowerCase();

      if (command === 'quit' || command === 'exit') {
        break;
      }

      switch (command) {
        case 'all':
          await demonstrateAllRoles();
          break;
          
        case 'architect':
        case 'developer':
        case 'tester':
        case 'pm':
        case 'ba':
          await demonstrateRole(command as AssistantRole);
          break;
          
        case 'custom':
          if (parts.length >= 3) {
            const role = parts[1] as AssistantRole;
            const prompt = parts.slice(2).join(' ');
            await demonstrateCustomPrompt(role, prompt);
          } else {
            console.log('Использование: custom [роль] [промпт]');
          }
          break;
          
        case 'preview':
          await createDemoPreview();
          break;
          
        default:
          console.log('Неизвестная команда. Введите "quit" для выхода.');
      }
      
      console.log(''); // Пустая строка для разделения
    }

  } finally {
    rl.close();
  }
}

/**
 * Тестирование всех функций модуля
 */
export async function testImageGenerationModule(): Promise<void> {
  console.log('🧪 Тестирование модуля генерации изображений\n');

  // Тест 1: Получение списка ролей
  console.log('1. Тест получения списка ролей:');
  const roles = getAvailableRoles();
  console.log(`✅ Найдено ролей: ${roles.length}`);
  console.log(`   Роли: ${roles.join(', ')}\n`);

  // Тест 2: Получение описаний ролей
  console.log('2. Тест получения описаний ролей:');
  for (const role of roles) {
    const description = getRoleDescription(role);
    console.log(`✅ ${role}: ${description}`);
  }
  console.log('');

  // Тест 3: Получение примеров промптов
  console.log('3. Тест получения примеров промптов:');
  for (const role of roles) {
    const examples = getRoleExamples(role);
    console.log(`✅ ${role}: ${examples.length} примеров`);
    console.log(`   Первый пример: ${examples[0]}`);
  }
  console.log('');

  // Тест 4: Валидация промптов
  console.log('4. Тест валидации промптов:');
  const testPrompts = [
    { prompt: 'Clean architecture diagram', valid: true },
    { prompt: '', valid: false },
    { prompt: 'A'.repeat(501), valid: false }
  ];

  for (const test of testPrompts) {
    const isValid = validatePrompt(test.prompt, 'architect');
    console.log(`✅ "${test.prompt.substring(0, 30)}...": ${isValid ? 'Валидно' : 'Невалидно'}`);
  }
  console.log('');

  console.log('🎉 Тестирование завершено!');
}

// Экспорт примеров
export const examples = {
  architect: {
    prompt: 'System architecture diagram for 1C Enterprise integration with microservices',
    description: 'Архитектурная схема интеграции 1С с микросервисами'
  },
  developer: {
    prompt: 'Modern dashboard UI for inventory management system',
    description: 'Современный интерфейс панели управления складом'
  },
  tester: {
    prompt: 'Test case flow diagram with quality assurance process',
    description: 'Диаграмма потока тест-кейсов с процессом контроля качества'
  },
  pm: {
    prompt: 'Project timeline dashboard with Gantt chart and KPI metrics',
    description: 'Панель проекта с диаграммой Ганта и KPI метриками'
  },
  ba: {
    prompt: 'Business process diagram showing AS-IS and TO-BE states',
    description: 'Диаграмма бизнес-процесса с текущим и целевым состоянием'
  }
};

// Экспорт по умолчанию
export default {
  demonstrateAllRoles,
  demonstrateRole,
  demonstrateCustomPrompt,
  createDemoPreview,
  interactiveDemo,
  testImageGenerationModule,
  examples
};