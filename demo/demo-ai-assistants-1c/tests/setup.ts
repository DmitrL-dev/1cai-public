/**
 * Настройка тестового окружения для Edge Functions
 */

import '@jest/globals';

// Глобальные настройки перед каждым тестом
beforeAll(() => {
  // Устанавливаем таймауты для тестов
  jest.setTimeout(30000);
  
  // Очищаем все моки перед началом тестов
  jest.clearAllMocks();
});

afterAll(() => {
  // Очистка после всех тестов
  jest.restoreAllMocks();
});

beforeEach(() => {
  // Настройка перед каждым тестом
  jest.clearAllTimers();
});

// Глобальные моки для Deno
global.fetch = jest.fn();
global.Request = jest.fn();
global.Response = jest.fn();
global.Headers = jest.fn();
global.AbortController = jest.fn();
global.AbortSignal = jest.fn();

// Мок для crypto.randomUUID
global.crypto = {
  randomUUID: jest.fn(() => 'mock-uuid-12345')
};

// Настройка для console в тестах
global.console = {
  ...console,
  log: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
  info: jest.fn(),
  debug: jest.fn()
};

// Глобальные переменные окружения для тестов
process.env.NODE_ENV = 'test';
process.env.EDGE_FUNCTION_URL = 'http://localhost:54321/functions/v1';
process.env.SUPABASE_URL = 'http://localhost:54321';
process.env.SUPABASE_ANON_KEY = 'test-anon-key';
process.env.SUPABASE_SERVICE_ROLE_KEY = 'test-service-role-key';

// Утилиты для тестирования
global.testUtils = {
  waitFor: (condition: () => boolean, timeout = 5000) => {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      
      const check = () => {
        if (condition()) {
          resolve(true);
        } else if (Date.now() - startTime > timeout) {
          reject(new Error(`Condition not met within ${timeout}ms`));
        } else {
          setTimeout(check, 100);
        }
      };
      
      check();
    });
  },
  
  delay: (ms: number) => {
    return new Promise(resolve => setTimeout(resolve, ms));
  },
  
  createMockRequest: (options: any = {}) => {
    return {
      method: options.method || 'POST',
      headers: new Headers(options.headers || {}),
      json: jest.fn().mockResolvedValue(options.body || {}),
      text: jest.fn().mockResolvedValue(JSON.stringify(options.body || {})),
      ...options
    };
  },
  
  createMockResponse: () => {
    const mockResponse = {
      status: 200,
      headers: new Headers(),
      json: jest.fn(),
      text: jest.fn(),
      ok: true
    };
    
    mockResponse.json.mockReturnValue(Promise.resolve({ data: {} }));
    mockResponse.text.mockReturnValue(Promise.resolve('{}'));
    
    return mockResponse;
  }
};

// Расширение expect для дополнительных проверок
expect.extend({
  toBeWithinRange(received: number, floor: number, ceiling: number) {
    const pass = received >= floor && received <= ceiling;
    if (pass) {
      return {
        message: () =>
          `expected ${received} not to be within range ${floor} - ${ceiling}`,
        pass: true,
      };
    } else {
      return {
        message: () =>
          `expected ${received} to be within range ${floor} - ${ceiling}`,
        pass: false,
      };
    }
  },
  
  toHaveValidCorsHeaders(received: Headers) {
    const pass = 
      received.get('Access-Control-Allow-Origin') === '*' &&
      received.get('Access-Control-Allow-Methods')?.includes('POST') &&
      received.get('Access-Control-Allow-Headers')?.includes('content-type');
    
    return {
      message: () => 'Expected response to have valid CORS headers',
      pass
    };
  },
  
  toBeValidProgressSteps(received: any[]) {
    const pass = Array.isArray(received) && received.length > 0 && 
      received.every(step => 
        typeof step.progress === 'number' && 
        typeof step.message === 'string' &&
        step.progress >= 0 && step.progress <= 100
      ) &&
      received[received.length - 1].progress === 100;
    
    return {
      message: () => 'Expected array of valid progress steps with final step having progress 100',
      pass
    };
  }
});

// Типы для TypeScript
declare global {
  var testUtils: {
    waitFor: (condition: () => boolean, timeout?: number) => Promise<boolean>;
    delay: (ms: number) => Promise<void>;
    createMockRequest: (options?: any) => any;
    createMockResponse: () => any;
  };

  namespace jest {
    interface Matchers<R> {
      toBeWithinRange(floor: number, ceiling: number): R;
      toHaveValidCorsHeaders(): R;
      toBeValidProgressSteps(): R;
    }
  }
}

export {};
