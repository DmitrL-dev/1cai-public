/**
 * Интеграционные тесты для developer-demo Edge Function
 * Тестирование полного цикла обработки запроса через Edge Function API
 */

import { describe, it, expect, beforeAll, afterAll, beforeEach, afterEach } from '@jest/globals';
import { 
  sampleDeveloperRequests, 
  expectedResponses, 
  errorResponses,
  corsTestCases 
} from '../../fixtures/sampleRequests.ts';
import { 
  mockPerformanceMetrics,
  mockStepProgressions,
  mockUserQueries
} from '../../fixtures/mockData.ts';

// Конфигурация для интеграционных тестов
const TEST_CONFIG = {
  baseUrl: process.env.EDGE_FUNCTION_URL || 'http://localhost:54321/functions/v1',
  functionName: 'developer-demo',
  timeout: 30000,
  retries: 3
};

// Вспомогательные функции для тестирования
class EdgeFunctionTester {
  private baseUrl: string;
  private functionName: string;
  private timeout: number;

  constructor(config = TEST_CONFIG) {
    this.baseUrl = config.baseUrl;
    this.functionName = config.functionName;
    this.timeout = config.timeout;
  }

  async makeRequest(
    method: string = 'POST', 
    body?: any, 
    headers: Record<string, string> = {}
  ): Promise<{ response: Response; data: any }> {
    const url = `${this.baseUrl}/${this.functionName}`;
    
    const defaultHeaders = {
      'Content-Type': 'application/json',
      ...headers
    };

    const requestOptions: RequestInit = {
      method,
      headers: defaultHeaders,
      signal: AbortSignal.timeout(this.timeout)
    };

    if (body && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
      requestOptions.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(url, requestOptions);
      const data = await response.json();
      
      return { response, data };
    } catch (error) {
      throw new Error(`Request failed: ${error.message}`);
    }
  }

  async testEndpointHealth(): Promise<boolean> {
    try {
      const { response } = await this.makeRequest('OPTIONS');
      return response.status === 200;
    } catch (error) {
      console.warn('Edge Function not available, skipping integration tests:', error.message);
      return false;
    }
  }

  getFullUrl(): string {
    return `${this.baseUrl}/${this.functionName}`;
  }
}

describe('DeveloperDemo Integration Tests', () => {
  let tester: EdgeFunctionTester;
  let isFunctionAvailable = false;

  beforeAll(async () => {
    tester = new EdgeFunctionTester();
    
    // Проверяем доступность Edge Function
    isFunctionAvailable = await tester.testEndpointHealth();
    
    if (!isFunctionAvailable) {
      console.log('⚠️ Edge Function недоступен. Интеграционные тесты будут пропущены.');
    }
  });

  afterAll(() => {
    // Очистка после всех тестов
  });

  beforeEach(() => {
    // Подготовка к каждому тесту
  });

  afterEach(() => {
    // Очистка после каждого теста
  });

  describe.skipIf(!isFunctionAvailable)('Полный цикл обработки запроса', () => {
    it('должен обрабатывать валидный POST запрос с данными справочника', async () => {
      const requestData = sampleDeveloperRequests.catalogRequest;
      
      const { response, data } = await tester.makeRequest('POST', requestData);
      
      expect(response.status).toBe(200);
      expect(response.headers.get('Content-Type')).toBe('application/json');
      
      expect(data).toHaveProperty('data');
      expect(data.data).toHaveProperty('steps');
      expect(data.data).toHaveProperty('finalResult');
      
      expect(data.data.steps).toHaveLength(5);
      expect(data.data.steps[0].progress).toBe(10);
      expect(data.data.steps[4].progress).toBe(100);
      
      expect(data.data.finalResult).toMatchObject({
        language: '1C',
        userQuery: expect.stringContaining('справочник')
      });
    }, TEST_CONFIG.timeout);

    it('должен обрабатывать запрос generate кода', async () => {
      const requestData = sampleDeveloperRequests.validGenerateRequest;
      
      const { response, data } = await tester.makeRequest('POST', requestData);
      
      expect(response.status).toBe(200);
      expect(data.data.finalResult).toMatchObject({
        code: expect.stringContaining('Справочник'),
        linesOfCode: expect.any(Number),
        functions: expect.any(Number),
        testCoverage: expect.stringContaining('%')
      });
      
      expect(data.data.steps[5].message).toContain('Код сгенерирован');
    }, TEST_CONFIG.timeout);

    it('должен обрабатывать запрос оптимизации кода', async () => {
      const requestData = sampleDeveloperRequests.validOptimizeRequest;
      
      const { response, data } = await tester.makeRequest('POST', requestData);
      
      expect(response.status).toBe(200);
      expect(data.data.finalResult).toMatchObject({
        originalQuery: expect.stringContaining('SELECT'),
        optimizedQuery: expect.stringContaining('SELECT'),
        improvements: expect.arrayContaining([expect.any(String)]),
        speedup: expect.stringContaining('x')
      });
      
      expect(data.data.finalResult.speedup).toBe('8x');
    }, TEST_CONFIG.timeout);

    it('должен обрабатывать запрос создания API интеграции', async () => {
      const requestData = sampleDeveloperRequests.validApiRequest;
      
      const { response, data } = await tester.makeRequest('POST', requestData);
      
      expect(response.status).toBe(200);
      expect(data.data.finalResult).toMatchObject({
        code: expect.stringContaining('HTTP'),
        endpoints: expect.any(Number),
        features: expect.arrayContaining([expect.any(String)]),
        testCases: expect.any(Number)
      });
      
      expect(data.data.finalResult.endpoints).toBeGreaterThan(0);
    }, TEST_CONFIG.timeout);
  });

  describe.skipIf(!isFunctionAvailable)('Тестирование через Edge Function API', () => {
    it('должен отвечать на OPTIONS запросы (CORS preflight)', async () => {
      const { response } = await tester.makeRequest('OPTIONS');
      
      expect(response.status).toBe(200);
      expect(response.headers.get('Access-Control-Allow-Origin')).toBe('*');
      expect(response.headers.get('Access-Control-Allow-Methods')).toContain('POST');
      expect(response.headers.get('Access-Control-Allow-Headers')).toContain('content-type');
    });

    it('должен обрабатывать GET запросы корректно', async () => {
      const { response, data } = await tester.makeRequest('GET');
      
      expect(response.status).toBe(200);
      expect(response.headers.get('Content-Type')).toBe('application/json');
      
      expect(data).toHaveProperty('data');
      expect(data.data).toHaveProperty('steps');
      expect(data.data).toHaveProperty('finalResult');
    });

    it('должен валидировать отсутствующий demoType', async () => {
      const requestData = sampleDeveloperRequests.missingDemoType;
      
      const { response, data } = await tester.makeRequest('POST', requestData);
      
      expect(response.status).toBe(400);
      expect(data).toHaveProperty('error');
      expect(data.error.code).toBe('VALIDATION_ERROR');
      expect(data.error.message).toContain('demoType');
    });

    it('должен валидировать пустой demoType', async () => {
      const requestData = sampleDeveloperRequests.emptyDemoType;
      
      const { response, data } = await tester.makeRequest('POST', requestData);
      
      expect(response.status).toBe(400);
      expect(data).toHaveProperty('error');
      expect(data.error.code).toBe('VALIDATION_ERROR');
    });

    it('должен валидировать неподдерживаемый HTTP метод', async () => {
      const { response, data } = await tester.makeRequest('DELETE');
      
      expect(response.status).toBe(400);
      expect(data).toHaveProperty('error');
      expect(data.error.code).toBe('VALIDATION_ERROR');
      expect(data.error.message).toContain('Unsupported method');
    });
  });

  describe.skipIf(!isFunctionAvailable)('Тестирование с реальными данными', () => {
    it('должен корректно обрабатывать различные типы запросов 1С', async () => {
      const testCases = [
        { request: sampleDeveloperRequests.catalogRequest, expectedType: 'справочник' },
        { request: sampleDeveloperRequests.documentRequest, expectedType: 'документ' },
        { request: sampleDeveloperRequests.registerRequest, expectedType: 'регистр' },
        { request: sampleDeveloperRequests.reportRequest, expectedType: 'отчет' },
        { request: sampleDeveloperRequests.processingRequest, expectedType: 'обработк' }
      ];

      for (const testCase of testCases) {
        const { response, data } = await tester.makeRequest('POST', testCase.request);
        
        expect(response.status).toBe(200);
        expect(data.data.finalResult).toHaveProperty('code');
        expect(data.data.finalResult.language).toBe('1C');
        expect(data.data.steps).toHaveLength(5);
        
        // Проверяем, что код содержит соответствующие ключевые слова
        const code = data.data.finalResult.code;
        const typeKeywords = {
          'справочник': ['Справочник', 'ПриСозданииНаСервере'],
          'документ': ['Документ', 'ОбработкаПроведения'],
          'регистр': ['Регистр', 'Функция'],
          'отчет': ['Процедура', 'СформироватьОтчет'],
          'обработк': ['Процедура', 'ВыполнитьОбработку']
        };
        
        const keywords = typeKeywords[testCase.expectedType as keyof typeof typeKeywords];
        if (keywords) {
          const hasKeyword = keywords.some(keyword => code.includes(keyword));
          expect(hasKeyword).toBe(true);
        }
      }
    }, TEST_CONFIG.timeout);

    it('должен обрабатывать пустые и граничные значения', async () => {
      const boundaryCases = [
        sampleDeveloperRequests.emptyUserQuery,
        sampleDeveloperRequests.longUserQuery,
        sampleDeveloperRequests.unicodeUserQuery
      ];

      for (const requestData of boundaryCases) {
        const { response, data } = await tester.makeRequest('POST', requestData);
        
        expect(response.status).toBe(200);
        expect(data.data).toHaveProperty('steps');
        expect(data.data).toHaveProperty('finalResult');
        expect(data.data.steps).toHaveLength(5);
        expect(data.data.finalResult).toHaveProperty('code');
        expect(data.data.finalResult.language).toBe('1C');
      }
    }, TEST_CONFIG.timeout);

    it('должен возвращать корректные метаданные сервиса', async () => {
      const requestData = sampleDeveloperRequests.validCustomRequest;
      
      const { response, data } = await tester.makeRequest('POST', requestData);
      
      expect(response.status).toBe(200);
      
      // Проверяем наличие метаданных в ответе
      if (data.data.metadata) {
        expect(data.data.metadata).toHaveProperty('service', 'developer-demo');
        expect(data.data.metadata).toHaveProperty('version');
        expect(data.data.metadata).toHaveProperty('timestamp');
        expect(data.data.metadata).toHaveProperty('supportedLanguages');
      }
    });
  });

  describe.skipIf(!isFunctionAvailable)('Тестирование производительности', () => {
    it('должен отвечать в пределах заданного времени', async () => {
      const requestData = sampleDeveloperRequests.validCustomRequest;
      const startTime = Date.now();
      
      const { response } = await tester.makeRequest('POST', requestData);
      
      const responseTime = Date.now() - startTime;
      
      expect(response.status).toBe(200);
      expect(responseTime).toBeLessThan(mockPerformanceMetrics.customProcessing.totalTime + 1000); // Дополнительная секунда на сетевые задержки
    }, TEST_CONFIG.timeout);

    it('должен обрабатывать последовательные запросы стабильно', async () => {
      const requestData = sampleDeveloperRequests.validCustomRequest;
      const results = [];
      
      for (let i = 0; i < 3; i++) {
        const startTime = Date.now();
        const { response, data } = await tester.makeRequest('POST', requestData);
        const responseTime = Date.now() - startTime;
        
        expect(response.status).toBe(200);
        expect(data.data.steps).toHaveLength(5);
        expect(responseTime).toBeLessThan(TEST_CONFIG.timeout);
        
        results.push({ responseTime, stepCount: data.data.steps.length });
      }
      
      // Проверяем, что время ответа не сильно колеблется
      const responseTimes = results.map(r => r.responseTime);
      const avgTime = responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length;
      const maxDeviation = Math.max(...responseTimes.map(t => Math.abs(t - avgTime)));
      
      expect(maxDeviation).toBeLessThan(avgTime * 0.5); // Не более 50% отклонения от среднего
    }, TEST_CONFIG.timeout * 3);

    it('должен генерировать правильную структуру прогресса', async () => {
      const requestData = sampleDeveloperRequests.validCustomRequest;
      
      const { response, data } = await tester.makeRequest('POST', requestData);
      
      expect(response.status).toBe(200);
      
      const steps = data.data.steps;
      expect(steps).toHaveLength(5);
      
      // Проверяем прогрессию
      for (let i = 0; i < steps.length; i++) {
        expect(steps[i]).toHaveProperty('progress');
        expect(steps[i]).toHaveProperty('message');
        expect(typeof steps[i].progress).toBe('number');
        expect(typeof steps[i].message).toBe('string');
        
        if (i > 0) {
          expect(steps[i].progress).toBeGreaterThan(steps[i-1].progress);
        }
      }
      
      // Проверяем финальный прогресс
      expect(steps[steps.length - 1].progress).toBe(100);
    });
  });

  describe.skipIf(!isFunctionAvailable)('Тестирование CORS', () => {
    it('должен корректно обрабатывать CORS preflight запросы', async () => {
      const { response } = await tester.makeRequest('OPTIONS');
      
      expect(response.status).toBe(200);
      expect(response.headers.get('Access-Control-Allow-Origin')).toBe('*');
      expect(response.headers.get('Access-Control-Allow-Methods')).toContain('POST');
      expect(response.headers.get('Access-Control-Allow-Methods')).toContain('GET');
      expect(response.headers.get('Access-Control-Allow-Methods')).toContain('OPTIONS');
      expect(response.headers.get('Access-Control-Allow-Headers')).toContain('authorization');
      expect(response.headers.get('Access-Control-Allow-Headers')).toContain('content-type');
    });

    it('должен возвращать CORS заголовки в POST запросах', async () => {
      const requestData = sampleDeveloperRequests.validCustomRequest;
      
      const { response } = await tester.makeRequest('POST', requestData);
      
      expect(response.headers.get('Access-Control-Allow-Origin')).toBe('*');
      expect(response.headers.get('Access-Control-Allow-Headers')).toContain('authorization');
      expect(response.headers.get('Access-Control-Allow-Methods')).toContain('POST');
      expect(response.headers.get('Access-Control-Max-Age')).toBe('86400');
    });

    it('должен работать с различными Origin заголовками', async () => {
      const origins = [
        'https://example.com',
        'https://app.company.com',
        'http://localhost:3000'
      ];
      
      const requestData = sampleDeveloperRequests.validCustomRequest;
      
      for (const origin of origins) {
        const { response } = await tester.makeRequest('POST', requestData, {
          'Origin': origin
        });
        
        expect(response.status).toBe(200);
        expect(response.headers.get('Access-Control-Allow-Origin')).toBe('*');
      }
    });
  });

  describe.skipIf(!isFunctionAvailable)('Тестирование обработки ошибок', () => {
    it('должен возвращать корректную ошибку валидации', async () => {
      const invalidRequest = { invalid: 'data' };
      
      const { response, data } = await tester.makeRequest('POST', invalidRequest);
      
      expect(response.status).toBe(400);
      expect(data).toHaveProperty('error');
      expect(data.error.code).toBe('VALIDATION_ERROR');
      expect(data.error).toHaveProperty('timestamp');
      expect(data.error).toHaveProperty('requestId');
      expect(data.error.service).toBe('developer-demo');
    });

    it('должен обрабатывать некорректный JSON', async () => {
      // Отправляем некорректный JSON через прямую отправку
      try {
        const url = tester.getFullUrl();
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: '{ invalid json }',
          signal: AbortSignal.timeout(TEST_CONFIG.timeout)
        });
        
        const data = await response.json();
        
        expect(response.status).toBe(400);
        expect(data).toHaveProperty('error');
      } catch (error) {
        // Ожидаем ошибку парсинга JSON
        expect(error.message).toContain('Request failed');
      }
    });

    it('должен возвращать структурированную информацию об ошибке', async () => {
      const { response, data } = await tester.makeRequest('POST', {
        demoType: 'invalid_type'
      });
      
      expect(response.status).toBe(400);
      expect(data.error).toMatchObject({
        code: expect.any(String),
        message: expect.any(String),
        timestamp: expect.any(String),
        requestId: expect.any(String),
        service: 'developer-demo',
        version: expect.any(String)
      });
    });
  });

  describe.skipIf(!isFunctionAvailable)('Функциональное тестирование', () => {
    it('должен корректно различать типы запросов пользователя', async () => {
      const userQueryTypes = [
        { query: 'создать справочник товаров', expectedCode: 'Справочник' },
        { query: 'создать документ продажи', expectedCode: 'Документ' },
        { query: 'создать регистр остатков', expectedCode: 'Регистр' },
        { query: 'создать отчет по продажам', expectedCode: expect.stringContaining('Процедура') }
      ];

      for (const testCase of userQueryTypes) {
        const requestData = {
          demoType: 'custom',
          userQuery: testCase.query
        };
        
        const { response, data } = await tester.makeRequest('POST', requestData);
        
        expect(response.status).toBe(200);
        expect(data.data.finalResult.code).toContain(testCase.expectedCode);
      }
    }, TEST_CONFIG.timeout);

    it('должен генерировать семантически корректный код 1С', async () => {
      const requestData = sampleDeveloperRequests.catalogRequest;
      
      const { response, data } = await tester.makeRequest('POST', requestData);
      
      expect(response.status).toBe(200);
      
      const code = data.data.finalResult.code;
      
      // Проверяем базовые элементы кода 1С
      expect(code).toContain('Процедура');
      expect(code).toContain('КонецПроцедуры');
      expect(code).toContain('(');
      expect(code).toContain(')');
      expect(code).toContain(';');
      expect(code).toContain('//');
      
      // Проверяем специфичные элементы справочника
      expect(code).toMatch(/Справочник.*Товары/);
    });
  });

  describe('Mock Integration Tests (когда Edge Function недоступен)', () => {
    it('должен корректно пропускать тесты при недоступности сервиса', async () => {
      if (isFunctionAvailable) {
        // Если функция доступна, пропускаем mock тесты
        console.log('Edge Function доступен, пропускаем mock тесты');
        return;
      }
      
      // Имитируем недоступность сервиса
      expect(isFunctionAvailable).toBe(false);
      console.log('✅ Edge Function недоступен, используем mock данные');
    });

    it('должен валидировать конфигурацию тестирования', () => {
      expect(TEST_CONFIG.baseUrl).toBeTruthy();
      expect(TEST_CONFIG.functionName).toBeTruthy();
      expect(TEST_CONFIG.timeout).toBeGreaterThan(0);
      expect(TEST_CONFIG.functionName).toBe('developer-demo');
    });
  });
});

// Утилита для пропуска тестов при недоступности сервиса
describe.skipIf = (condition: boolean) => {
  if (condition) {
    return describe.each([['Edge Function unavailable', () => {}]])('%s', () => {
      it('Edge Function недоступен, тест пропущен', () => {
        console.log('⏭️ Тест пропущен из-за недоступности Edge Function');
      });
    });
  }
  return describe;
};
