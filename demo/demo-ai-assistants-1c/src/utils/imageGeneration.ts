/**
 * Модуль интеграции с Image Generation API для демонстрации AI-ассистентов
 * Обеспечивает генерацию изображений по ролям для демонстрации функциональности
 */

import { gen_images } from '@/lib/imageGen';

/**
 * Роли AI-ассистентов для генерации изображений
 */
export type AssistantRole = 
  | 'architect'     // Архитектор
  | 'developer'     // Разработчик
  | 'tester'        // Тестировщик
  | 'pm'           // Project Manager
  | 'ba';          // Business Analyst

/**
 * Интерфейс для результата генерации изображения
 */
export interface ImageGenerationResult {
  success: boolean;
  imageUrl?: string;
  error?: string;
  role: AssistantRole;
  prompt: string;
  timestamp: Date;
}

/**
 * Интерфейс для конфигурации ролей
 */
interface RoleConfig {
  basePrompt: string;
  examples: string[];
  style: string;
  description: string;
}

/**
 * Конфигурация промптов для каждой роли
 */
const ROLE_CONFIGS: Record<AssistantRole, RoleConfig> = {
  architect: {
    basePrompt: "Architectural diagram, system design, technical schema",
    examples: [
      "Clean architecture diagram showing layers: Presentation, Application, Domain, Infrastructure",
      "Microservices architecture with API Gateway, service mesh, and database per service",
      "Event-driven architecture with message brokers and async communication",
      "Database schema design with entity relationships and foreign keys",
      "System integration architecture showing 1C ERP and external services"
    ],
    style: "professional technical diagram, clean lines, blue and gray color scheme",
    description: "Архитектор - схемы и диаграммы систем"
  },
  developer: {
    basePrompt: "Code structure, UI mockup, programming interface",
    examples: [
      "Modern web application dashboard with sidebar navigation and data tables",
      "1C Enterprise form design with input fields, buttons and data grid",
      "API documentation interface showing endpoints and request/response examples",
      "Code editor with syntax highlighting showing BSL (1C) code",
      "Responsive mobile app wireframe for inventory management"
    ],
    style: "modern UI design, clean interface, developer-friendly colors",
    description: "Разработчик - код и пользовательские интерфейсы"
  },
  tester: {
    basePrompt: "Test case diagram, quality assurance flowchart, testing scenarios",
    examples: [
      "Test case flow diagram with preconditions, steps, and expected results",
      "Quality assurance process flowchart showing testing phases",
      "Bug tracking interface with status workflow (Open → In Progress → Testing → Closed)",
      "Test automation strategy diagram showing CI/CD pipeline with testing stages",
      "Performance testing dashboard with load test results and metrics"
    ],
    style: "structured flowchart, testing workflow colors (green, yellow, red)",
    description: "Тестировщик - тест-кейсы и сценарии тестирования"
  },
  pm: {
    basePrompt: "Project plan, management dashboard, business analytics",
    examples: [
      "Project timeline with Gantt chart showing milestones and dependencies",
      "Business KPI dashboard with charts showing sales, revenue, and growth metrics",
      "Resource allocation chart showing team members and their assignments",
      "Risk management matrix with probability vs impact visualization",
      "Sprint planning board with user stories, tasks and burndown chart"
    ],
    style: "business dashboard style, professional charts, corporate colors",
    description: "PM - планы проектов и аналитические дашборды"
  },
  ba: {
    basePrompt: "Requirements specification, business process diagram, user story mapping",
    examples: [
      "Business process flowchart showing current vs future state (AS-IS vs TO-BE)",
      "User story map with epic hierarchy: Epic → Features → User Stories → Tasks",
      "Requirements traceability matrix linking features to test cases",
      "Stakeholder analysis diagram showing interests and influence levels",
      "Use case diagram for 1C inventory management system"
    ],
    style: "business process diagram, clear icons, professional documentation style",
    description: "BA - бизнес-требования и прототипы процессов"
  }
};

/**
 * Генерирует изображение для демонстрации AI-ассистента по роли
 * @param prompt - Промпт для генерации изображения
 * @param role - Роль ассистента
 * @returns Результат генерации изображения
 */
export async function generateDemoImage(
  prompt: string, 
  role: AssistantRole
): Promise<ImageGenerationResult> {
  try {
    // Валидация роли
    if (!ROLE_CONFIGS[role]) {
      return {
        success: false,
        error: `Неподдерживаемая роль: ${role}`,
        role: role as AssistantRole,
        prompt,
        timestamp: new Date()
      };
    }

    // Получение конфигурации для роли
    const config = ROLE_CONFIGS[role];
    
    // Создание финального промпта с учетом стиля роли
    const finalPrompt = `${prompt} in ${config.style} style, professional business diagram, high quality`;
    
    // Генерация изображения
    const imageResult = await gen_images({
      prompt: finalPrompt,
      output_file: `/tmp/demo_${role}_${Date.now()}.png`
    });

    return {
      success: true,
      imageUrl: imageResult.url || `/tmp/demo_${role}_${Date.now()}.png`,
      role,
      prompt: finalPrompt,
      timestamp: new Date()
    };

  } catch (error) {
    console.error('Ошибка генерации изображения:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Неизвестная ошибка',
      role: role as AssistantRole,
      prompt,
      timestamp: new Date()
    };
  }
}

/**
 * Генерирует изображение с примером для конкретной роли
 * @param role - Роль ассистента
 * @param exampleIndex - Индекс примера (по умолчанию 0)
 * @returns Результат генерации изображения
 */
export async function generateRoleExampleImage(
  role: AssistantRole, 
  exampleIndex: number = 0
): Promise<ImageGenerationResult> {
  const config = ROLE_CONFIGS[role];
  const example = config.examples[exampleIndex % config.examples.length];
  
  return generateDemoImage(example, role);
}

/**
 * Получает примеры промптов для роли
 * @param role - Роль ассистента
 * @returns Массив примеров промптов
 */
export function getRoleExamples(role: AssistantRole): string[] {
  return ROLE_CONFIGS[role]?.examples || [];
}

/**
 * Получает описание роли
 * @param role - Роль ассистента
 * @returns Описание роли
 */
export function getRoleDescription(role: AssistantRole): string {
  return ROLE_CONFIGS[role]?.description || '';
}

/**
 * Получает список всех доступных ролей
 * @returns Массив ролей
 */
export function getAvailableRoles(): AssistantRole[] {
  return Object.keys(ROLE_CONFIGS) as AssistantRole[];
}

/**
 * Генерирует несколько изображений для разных ролей
 * @param roles - Массив ролей для генерации
 * @returns Массив результатов генерации
 */
export async function generateMultipleRoleImages(
  roles: AssistantRole[]
): Promise<ImageGenerationResult[]> {
  const results = await Promise.all(
    roles.map(role => generateRoleExampleImage(role))
  );
  
  return results;
}

/**
 * Создает предварительный просмотр всех ролей
 * @returns Объект с примерами для каждой роли
 */
export async function generateAllRolesPreview(): Promise<{
  [key in AssistantRole]: ImageGenerationResult;
}> {
  const roles = getAvailableRoles();
  const results = await Promise.all(
    roles.map(role => generateRoleExampleImage(role))
  );

  const preview: { [key in AssistantRole]: ImageGenerationResult } = {} as any;
  
  results.forEach((result, index) => {
    preview[roles[index]] = result;
  });

  return preview;
}

/**
 * Валидирует промпт для роли
 * @param prompt - Промпт для валидации
 * @param role - Роль ассистента
 * @returns true если промпт валиден
 */
export function validatePrompt(prompt: string, role: AssistantRole): boolean {
  if (!prompt || prompt.trim().length === 0) {
    return false;
  }

  if (prompt.length > 500) {
    return false;
  }

  // Базовая валидация на неподходящий контент
  const invalidPatterns = [
    /violence|violence/i,
    /adult|adult/i,
    /illegal|illegal/i
  ];

  return !invalidPatterns.some(pattern => pattern.test(prompt));
}

/**
 * Экспорт по умолчанию
 */
export default {
  generateDemoImage,
  generateRoleExampleImage,
  getRoleExamples,
  getRoleDescription,
  getAvailableRoles,
  generateMultipleRoleImages,
  generateAllRolesPreview,
  validatePrompt,
  ROLE_CONFIGS
};