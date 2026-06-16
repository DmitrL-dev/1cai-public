/**
 * Unit тесты для developer-demo Edge Function
 * Тестирование основного класса DeveloperDemo и его методов
 */

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { BaseEdgeFunction } from '../../../supabase/shared/BaseEdgeFunction.ts';
import { BaseRequest, ProgressStep, DemoResponse } from '../../../supabase/shared/types.ts';
import { 
  sampleDeveloperRequests, 
  expectedResponses, 
  errorResponses,
  performanceBenchmarks 
} from '../../fixtures/sampleRequests.ts';
import { 
  mockPerformanceMetrics, 
  mockCodeSamples, 
  mockUserQueries,
  mockStepProgressions 
} from '../../fixtures/mockData.ts';

// Имитация Deno глобальных переменных для тестового окружения
const mockDeno = {
  serve: jest.fn(),
  crypto: {
    randomUUID: jest.fn(() => 'mock-uuid-12345')
  }
};

global.Deno = mockDeno as any;

// Класс для тестирования (рефакторенная версия DeveloperDemo)
class TestDeveloperDemo extends BaseEdgeFunction {
  constructor() {
    super('developer-demo', '1.0.0');
  }

  protected async executeDemo(request: BaseRequest): Promise<{
    steps: ProgressStep[];
    finalResult: any;
  }> {
    const steps: ProgressStep[] = [];

    if (request.demoType === 'custom') {
      // Имитация обработки пользовательского запроса
      steps.push({ progress: 10, message: 'Анализ вашего запроса...' });
      
      await new Promise(resolve => setTimeout(resolve, 100));
      steps.push({ progress: 30, message: 'Подготовка кода...' });
      
      await new Promise(resolve => setTimeout(resolve, 200));
      steps.push({ progress: 60, message: 'Генерация решения...' });
      
      await new Promise(resolve => setTimeout(resolve, 300));
      steps.push({ progress: 90, message: 'Оптимизация и форматирование...' });

      // Анализ запроса пользователя
      const queryLower = (request.userQuery || '').toLowerCase();
      let customCode = '';
      let customMessage = '';

      if (queryLower.includes('справочник') || queryLower.includes('catalog')) {
        customCode = mockCodeSamples.catalog1C;
        customMessage = 'Анализ запроса завершен. Сгенерирован модуль справочника.';
      } else if (queryLower.includes('документ') || queryLower.includes('document')) {
        customCode = mockCodeSamples.document1C;
        customMessage = 'Анализ запроса завершен. Сгенерирован модуль документа.';
      } else if (queryLower.includes('регистр') && queryLower.includes('накоплен')) {
        customCode = mockCodeSamples.register1C;
        customMessage = 'Анализ запроса завершен. Сгенерирован модуль регистра.';
      } else {
        customCode = '// Базовый обработчик\\nФункция ОбработатьДанные(Параметры)\\n    Возврат Истина;\\nКонецФункции';
        customMessage = 'Анализ запроса завершен. Сгенерирован базовый код.';
      }

      const finalResult = {
        message: customMessage,
        code: customCode,
        language: '1C',
        userQuery: request.userQuery
      };

      steps.push({ 
        progress: 100, 
        message: 'Код успешно сгенерирован!',
        result: finalResult
      });

      return { steps, finalResult };

    } else if (request.demoType === 'generate') {
      steps.push({ progress: 10, message: 'Запуск генерации кода...' });
      await new Promise(resolve => setTimeout(resolve, 100));
      steps.push({ progress: 25, message: 'Анализ требований к справочнику товаров...' });
      await new Promise(resolve => setTimeout(resolve, 200));
      steps.push({ progress: 50, message: 'Генерация структуры модуля...' });
      await new Promise(resolve => setTimeout(resolve, 300));

      const finalResult = {
        code: mockCodeSamples.catalog1C,
        linesOfCode: 245,
        functions: 8,
        testCoverage: '87%',
        complexity: 'Low'
      };

      steps.push({ 
        progress: 100, 
        message: '✅ Код сгенерирован: 245 строк, 8 функций, покрытие тестами 87%',
        result: finalResult
      });

      return { steps, finalResult };

    } else if (request.demoType === 'optimize') {
      steps.push({ progress: 10, message: 'Запуск оптимизации...' });
      await new Promise(resolve => setTimeout(resolve, 100));
      steps.push({ progress: 30, message: 'Анализ SQL запроса...' });
      await new Promise(resolve => setTimeout(resolve, 200));
      steps.push({ progress: 60, message: 'Выявление узких мест' });
      await new Promise(resolve => setTimeout(resolve, 300));
      steps.push({ progress: 85, message: 'Применение оптимизаций...' });

      const finalResult = {
        originalQuery: 'SELECT * FROM table',
        optimizedQuery: mockCodeSamples.optimizedSQL,
        improvements: ['Добавлен индекс', 'Оптимизирован JOIN'],
        performanceBefore: '3.2s',
        performanceAfter: '0.4s',
        speedup: '8x'
      };

      steps.push({ 
        progress: 100, 
        message: '✅ Производительность улучшена: с 3.2с до 0.4с (8x быстрее)',
        result: finalResult
      });

      return { steps, finalResult };

    } else if (request.demoType === 'api') {
      steps.push({ progress: 10, message: 'Запуск создания API интеграции...' });
      await new Promise(resolve => setTimeout(resolve, 100));
      steps.push({ progress: 25, message: 'Анализ спецификации API...' });
      await new Promise(resolve => setTimeout(resolve, 200));
      steps.push({ progress: 50, message: 'Генерация методов интеграции...' });
      await new Promise(resolve => setTimeout(resolve, 300));
      steps.push({ progress: 75, message: 'Добавление обработки ошибок...' });

      const finalResult = {
        code: mockCodeSamples.apiCode1C,
        endpoints: 12,
        features: ['Retry логика', 'Логирование', 'Таймауты', 'SSL/TLS'],
        testCases: 24
      };

      steps.push({ 
        progress: 100, 
        message: '✅ API интеграция готова: 12 endpoint, retry логика, логирование',
        result: finalResult
      });

      return { steps, finalResult };
    }

    throw new Error(`Неподдерживаемый тип демо: ${request.demoType}`);
  }
}

describe('DeveloperDemo Unit Tests', () => {
  let demoFunction: TestDeveloperDemo;

  beforeEach(() => {
    demoFunction = new TestDeveloperDemo();
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Класс DeveloperDemo', () => {
    it('должен корректно инициализироваться с базовыми параметрами', () => {
      expect(demoFunction).toBeInstanceOf(BaseEdgeFunction);
      expect(demoFunction.serviceName).toBe('developer-demo');
      expect(demoFunction.serviceVersion).toBe('1.0.0');
      expect(demoFunction.corsHeaders).toMatchObject({
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': expect.stringContaining('authorization'),
        'Access-Control-Allow-Methods': expect.stringContaining('POST')
      });
    });

    it('должен содержать правильные CORS заголовки', () => {
      const corsHeaders = demoFunction.corsHeaders;
      
      expect(corsHeaders['Access-Control-Allow-Origin']).toBe('*');
      expect(corsHeaders['Access-Control-Allow-Headers']).toContain('content-type');
      expect(corsHeaders['Access-Control-Allow-Methods']).toContain('POST');
      expect(corsHeaders['Access-Control-Max-Age']).toBe('86400');
      expect(corsHeaders['Access-Control-Allow-Credentials']).toBe('false');
    });
  });

  describe('Метод processRequest()', () => {
    it('должен обрабатывать валидный пользовательский запрос со справочником', async () => {
      const request: BaseRequest = sampleDeveloperRequests.validCustomRequest;
      const result = await demoFunction.executeDemo(request);

      expect(result).toHaveProperty('steps');
      expect(result).toHaveProperty('finalResult');
      expect(result.steps).toHaveLength(5);
      expect(result.steps[0].progress).toBe(10);
      expect(result.steps[4].progress).toBe(100);
      expect(result.finalResult).toMatchObject(expectedResponses.customCatalogResponse);
    });

    it('должен обрабатывать валидный пользовательский запрос с документом', async () => {
      const request: BaseRequest = sampleDeveloperRequests.documentRequest;
      const result = await demoFunction.executeDemo(request);

      expect(result.steps).toHaveLength(5);
      expect(result.finalResult.message).toContain('документ');
      expect(result.finalResult.code).toContain('Документ');
    });

    it('должен обрабатывать валидный пользовательский запрос с регистром', async () => {
      const request: BaseRequest = sampleDeveloperRequests.registerRequest;
      const result = await demoFunction.executeDemo(request);

      expect(result.steps).toHaveLength(5);
      expect(result.finalResult.message).toContain('регистр');
      expect(result.finalResult.code).toContain('Регистр');
    });

    it('должен обрабатывать запрос generate', async () => {
      const request: BaseRequest = sampleDeveloperRequests.validGenerateRequest;
      const result = await demoFunction.executeDemo(request);

      expect(result.steps).toHaveLength(6);
      expect(result.finalResult).toMatchObject(expectedResponses.generateResponse);
      expect(result.finalResult.linesOfCode).toBe(245);
      expect(result.finalResult.functions).toBe(8);
      expect(result.finalResult.testCoverage).toBe('87%');
    });

    it('должен обрабатывать запрос optimize', async () => {
      const request: BaseRequest = sampleDeveloperRequests.validOptimizeRequest;
      const result = await demoFunction.executeDemo(request);

      expect(result.steps).toHaveLength(5);
      expect(result.finalResult).toMatchObject(expectedResponses.optimizeResponse);
      expect(result.finalResult.speedup).toBe('8x');
      expect(result.finalResult.performanceBefore).toBe('3.2s');
      expect(result.finalResult.performanceAfter).toBe('0.4s');
    });

    it('должен обрабатывать запрос api', async () => {
      const request: BaseRequest = sampleDeveloperRequests.validApiRequest;
      const result = await demoFunction.executeDemo(request);

      expect(result.steps).toHaveLength(5);
      expect(result.finalResult).toMatchObject(expectedResponses.apiResponse);
      expect(result.finalResult.endpoints).toBe(12);
      expect(result.finalResult.testCases).toBe(24);
    });

    it('должен генерировать прогрессивные шаги с правильными значениями', async () => {
      const request: BaseRequest = sampleDeveloperRequests.validCustomRequest;
      const result = await demoFunction.executeDemo(request);

      const steps = result.steps;
      expect(steps[0].progress).toBe(10);
      expect(steps[1].progress).toBe(30);
      expect(steps[2].progress).toBe(60);
      expect(steps[3].progress).toBe(90);
      expect(steps[4].progress).toBe(100);

      // Проверяем, что прогресс увеличивается
      for (let i = 1; i < steps.length; i++) {
        expect(steps[i].progress).toBeGreaterThan(steps[i-1].progress);
      }
    });

    it('должен обрабатывать пустой userQuery корректно', async () => {
      const request: BaseRequest = sampleDeveloperRequests.emptyUserQuery;
      const result = await demoFunction.executeDemo(request);

      expect(result.steps).toHaveLength(5);
      expect(result.finalResult.code).toContain('ОбработатьДанные');
      expect(result.finalResult.language).toBe('1C');
    });

    it('должен обрабатывать длинный userQuery', async () => {
      const request: BaseRequest = sampleDeveloperRequests.longUserQuery;
      const result = await demoFunction.executeDemo(request);

      expect(result.steps).toHaveLength(5);
      expect(result.finalResult).toHaveProperty('code');
      expect(result.finalResult).toHaveProperty('message');
    });

    it('должен обрабатывать userQuery с Unicode символами', async () => {
      const request: BaseRequest = sampleDeveloperRequests.unicodeUserQuery;
      const result = await demoFunction.executeDemo(request);

      expect(result.steps).toHaveLength(5);
      expect(result.finalResult).toHaveProperty('code');
      expect(result.finalResult.language).toBe('1C');
    });
  });

  describe('Обработка специфичных для разработчика запросов', () => {
    it('должен распознавать и обрабатывать запросы о справочниках', () => {
      const testQueries = mockUserQueries.catalog;
      
      testQueries.forEach(query => {
        const queryLower = query.toLowerCase();
        const hasCatalog = queryLower.includes('справочник') || queryLower.includes('catalog');
        expect(hasCatalog).toBe(true);
      });
    });

    it('должен распознавать и обрабатывать запросы о документах', () => {
      const testQueries = mockUserQueries.document;
      
      testQueries.forEach(query => {
        const queryLower = query.toLowerCase();
        const hasDocument = queryLower.includes('документ') || queryLower.includes('document');
        expect(hasDocument).toBe(true);
      });
    });

    it('должен распознавать и обрабатывать запросы о регистрах', () => {
      const testQueries = mockUserQueries.register;
      
      testQueries.forEach(query => {
        const queryLower = query.toLowerCase();
        const hasRegister = queryLower.includes('регистр');
        expect(hasRegister).toBe(true);
      });
    });

    it('должен генерировать корректный код 1С для справочника', async () => {
      const request: BaseRequest = sampleDeveloperRequests.catalogRequest;
      const result = await demoFunction.executeDemo(request);

      expect(result.finalResult.code).toContain('Справочник');
      expect(result.finalResult.code).toContain('Процедура ПриСозданииНаСервере');
      expect(result.finalResult.language).toBe('1C');
    });

    it('должен генерировать корректный код 1С для документа', async () => {
      const request: BaseRequest = sampleDeveloperRequests.documentRequest;
      const result = await demoFunction.executeDemo(request);

      expect(result.finalResult.code).toContain('Документ');
      expect(result.finalResult.code).toContain('Процедура ОбработкаПроведения');
      expect(result.finalResult.language).toBe('1C');
    });

    it('должен генерировать корректный код 1С для регистра', async () => {
      const request: BaseRequest = sampleDeveloperRequests.registerRequest;
      const result = await demoFunction.executeDemo(request);

      expect(result.finalResult.code).toContain('Регистр');
      expect(result.finalResult.code).toContain('Функция ПолучитьОстаткиТоваров');
      expect(result.finalResult.language).toBe('1C');
    });
  });

  describe('Error Handling', () => {
    it('должен бросать ошибку для неподдерживаемого demoType', async () => {
      const request: BaseRequest = sampleDeveloperRequests.invalidDemoType;
      
      await expect(demoFunction.executeDemo(request))
        .rejects
        .toThrow('Неподдерживаемый тип демо');
    });

    it('должен бросать ошибку при пустом demoType', async () => {
      const request: BaseRequest = sampleDeveloperRequests.emptyDemoType;
      
      await expect(demoFunction.executeDemo(request))
        .rejects
        .toThrow('Неподдерживаемый тип демо');
    });

    it('должен обрабатывать исключения корректно', async () => {
      // Создаем mock функцию, которая бросает исключение
      const mockExecute = jest.fn().mockRejectedValue(new Error('Test error'));
      const brokenDemo = new TestDeveloperDemo() as any;
      brokenDemo.executeDemo = mockExecute;

      const request = sampleDeveloperRequests.validCustomRequest;
      
      await expect(brokenDemo.executeDemo(request))
        .rejects
        .toThrow('Test error');
    });

    it('должен валидировать входные параметры', () => {
      expect(() => {
        demoFunction.parseRequest(null);
      }).toThrow('Неверный формат данных запроса');

      expect(() => {
        demoFunction.parseRequest({});
      }).toThrow('Параметр demoType обязателен для указания');

      expect(() => {
        demoFunction.parseRequest({ demoType: '' });
      }).toThrow('Параметр demoType обязателен для указания');
    });
  });

  describe('Производительность и метрики', () => {
    it('должен выполняться в пределах заданного времени', async () => {
      const startTime = Date.now();
      const request = sampleDeveloperRequests.validCustomRequest;
      
      await demoFunction.executeDemo(request);
      
      const executionTime = Date.now() - startTime;
      expect(executionTime).toBeLessThan(performanceBenchmarks.maxResponseTime);
    }, performanceBenchmarks.maxResponseTime);

    it('должен генерировать ожидаемое количество шагов', async () => {
      const request = sampleDeveloperRequests.validCustomRequest;
      const result = await demoFunction.executeDemo(request);

      expect(result.steps).toHaveLength(5);
      expect(result.steps[result.steps.length - 1].progress).toBe(100);
    });

    it('должен создавать последовательные шаги прогресса', async () => {
      const request = sampleDeveloperRequests.validCustomRequest;
      const result = await demoFunction.executeDemo(request);

      const progresses = result.steps.map(step => step.progress);
      expect(progresses).toEqual([10, 30, 60, 90, 100]);
    });

    it('должен содержать осмысленные сообщения в шагах', async () => {
      const request = sampleDeveloperRequests.validCustomRequest;
      const result = await demoFunction.executeDemo(request);

      result.steps.forEach(step => {
        expect(step.message).toBeTruthy();
        expect(typeof step.message).toBe('string');
        expect(step.message.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Безопасность и валидация', () => {
    it('должен безопасно обрабатывать SQL инъекции в запросах', async () => {
      const maliciousRequest: BaseRequest = {
        demoType: 'custom',
        userQuery: "'; DROP TABLE users; --"
      };

      const result = await demoFunction.executeDemo(maliciousRequest);
      
      expect(result.finalResult).toHaveProperty('code');
      expect(result.finalResult.code).not.toContain('DROP TABLE');
      expect(result.finalResult.message).toContain('запроса');
    });

    it('должен безопасно обрабатывать XSS попытки', async () => {
      const xssRequest: BaseRequest = {
        demoType: 'custom',
        userQuery: '<script>alert("xss")</script>'
      };

      const result = await demoFunction.executeDemo(xssRequest);
      
      expect(result.finalResult).toHaveProperty('code');
      expect(result.finalResult.userQuery).not.toContain('<script>');
    });

    it('должен обрабатывать специальные символы', async () => {
      const specialCharRequest: BaseRequest = {
        demoType: 'custom',
        userQuery: 'тест "кавычки" \\backslash /slash |pipe'
      };

      const result = await demoFunction.executeDemo(specialCharRequest);
      
      expect(result.finalResult).toHaveProperty('code');
      expect(result.finalResult.language).toBe('1C');
    });
  });

  describe('Интеграция с базовым классом', () => {
    it('должен наследовать методы от BaseEdgeFunction', () => {
      expect(demoFunction).toHaveProperty('createSuccessResponse');
      expect(demoFunction).toHaveProperty('createErrorResponse');
      expect(demoFunction).toHaveProperty('validateRequest');
      expect(demoFunction).toHaveProperty('parseRequest');
      expect(demoFunction).toHaveProperty('createProgressSteps');
      expect(demoFunction).toHaveProperty('getMetadata');
    });

    it('должен корректно создавать success response', () => {
      const mockResult = { test: 'data' };
      const response = demoFunction.createSuccessResponse(mockResult);
      
      expect(response.status).toBe(200);
      expect(response.headers.get('Content-Type')).toBe('application/json');
      expect(response.headers.get('Access-Control-Allow-Origin')).toBe('*');
    });

    it('должен корректно создавать error response', () => {
      const response = demoFunction.createErrorResponse('TEST_ERROR', 'Test error message', 400);
      
      expect(response.status).toBe(400);
      expect(response.headers.get('Content-Type')).toBe('application/json');
      expect(response.headers.get('Access-Control-Allow-Origin')).toBe('*');
    });

    it('должен корректно валидировать HTTP методы', async () => {
      const mockRequest = {
        method: 'PUT',
        headers: new Headers(),
        json: jest.fn().mockResolvedValue({ demoType: 'custom' })
      } as any;

      const validation = await demoFunction.validateRequest(mockRequest);
      expect(validation.isValid).toBe(false);
      expect(validation.errors).toContain('Unsupported method: PUT');
    });

    it('должен корректно валидировать Content-Type', async () => {
      const mockRequest = {
        method: 'POST',
        headers: new Headers({ 'content-type': 'text/plain' }),
        json: jest.fn().mockResolvedValue({ demoType: 'custom' })
      } as any;

      const validation = await demoFunction.validateRequest(mockRequest);
      expect(validation.isValid).toBe(false);
      expect(validation.errors).toContain('Content-Type must be application/json');
    });
  });
});
