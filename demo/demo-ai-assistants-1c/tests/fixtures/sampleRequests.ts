/**
 * Тестовые данные для запросов к Edge Functions
 */

export const sampleDeveloperRequests = {
  // Корректные запросы
  validCustomRequest: {
    demoType: 'custom',
    userQuery: 'создать справочник товаров в 1С'
  },

  validGenerateRequest: {
    demoType: 'generate',
    userQuery: 'сгенерировать модуль справочника'
  },

  validOptimizeRequest: {
    demoType: 'optimize',
    userQuery: 'оптимизировать SQL запрос'
  },

  validApiRequest: {
    demoType: 'api',
    userQuery: 'создать API для интеграции'
  },

  // Запросы с различными типами контента 1С
  catalogRequest: {
    demoType: 'custom',
    userQuery: 'создать справочник номенклатуры с кодами'
  },

  documentRequest: {
    demoType: 'custom',
    userQuery: 'создать документ приходной накладной'
  },

  registerRequest: {
    demoType: 'custom',
    userQuery: 'создать регистр накопления остатков'
  },

  reportRequest: {
    demoType: 'custom',
    userQuery: 'создать отчет по продажам'
  },

  processingRequest: {
    demoType: 'custom',
    userQuery: 'создать обработку загрузки данных'
  },

  // Некорректные запросы для тестирования валидации
  missingDemoType: {
    userQuery: 'создать справочник'
  },

  emptyDemoType: {
    demoType: '',
    userQuery: 'создать справочник'
  },

  invalidDemoType: {
    demoType: 'invalid_type',
    userQuery: 'создать справочник'
  },

  missingUserQuery: {
    demoType: 'custom'
  },

  // Специальные случаи
  longUserQuery: {
    demoType: 'custom',
    userQuery: 'создать сложный справочник товаров с иерархией, реквизитами, табличными частями, подчиненными справочниками, регистрами сведений, формами, обработчиками событий, валидацией данных, правами доступа и автоматической нумерацией'
  },

  unicodeUserQuery: {
    demoType: 'custom',
    userQuery: 'создать справочник "Товары ÜÖÄ" с кодом 123'
  },

  emptyUserQuery: {
    demoType: 'custom',
    userQuery: ''
  },

  // Запросы с неподдерживаемыми типами
  unsupportedQuery: {
    demoType: 'custom',
    userQuery: 'создать что-то непонятное для тестирования'
  }
};

export const expectedResponses = {
  customCatalogResponse: {
    message: expect.stringContaining('справочник'),
    code: expect.stringContaining('Справочник'),
    language: '1C',
    userQuery: expect.stringContaining('справочник')
  },

  customDocumentResponse: {
    message: expect.stringContaining('документ'),
    code: expect.stringContaining('Документ'),
    language: '1C'
  },

  customRegisterResponse: {
    message: expect.stringContaining('регистр'),
    code: expect.stringContaining('Регистр'),
    language: '1C'
  },

  generateResponse: {
    code: expect.stringContaining('Справочник'),
    linesOfCode: expect.any(Number),
    functions: expect.any(Number),
    testCoverage: expect.stringContaining('%'),
    complexity: expect.stringMatching(/Low|Medium|High/)
  },

  optimizeResponse: {
    originalQuery: expect.stringContaining('SELECT'),
    optimizedQuery: expect.stringContaining('SELECT'),
    improvements: expect.arrayContaining([expect.any(String)]),
    performanceBefore: expect.stringContaining('s'),
    performanceAfter: expect.stringContaining('s'),
    speedup: expect.stringContaining('x')
  },

  apiResponse: {
    code: expect.stringContaining('HTTP'),
    endpoints: expect.any(Number),
    features: expect.arrayContaining([expect.any(String)]),
    testCases: expect.any(Number)
  }
};

export const errorResponses = {
  validationError: {
    error: {
      code: 'VALIDATION_ERROR',
      message: expect.any(String),
      timestamp: expect.any(String),
      requestId: expect.any(String),
      service: 'developer-demo',
      version: expect.any(String)
    }
  },

  internalError: {
    error: {
      code: 'INTERNAL_ERROR',
      message: expect.any(String),
      timestamp: expect.any(String),
      requestId: expect.any(String),
      service: 'developer-demo',
      version: expect.any(String)
    }
  }
};

export const performanceBenchmarks = {
  maxResponseTime: 10000, // 10 секунд
  maxMemoryUsage: 100 * 1024 * 1024, // 100 MB
  concurrentRequests: 10
};

export const corsTestCases = [
  {
    name: 'OPTIONS request',
    method: 'OPTIONS',
    expectedStatus: 200,
    expectedHeaders: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
      'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type'
    }
  },
  {
    name: 'POST request with CORS',
    method: 'POST',
    headers: {
      'Origin': 'https://example.com',
      'Content-Type': 'application/json'
    },
    expectedStatus: 200,
    expectedHeaders: {
      'Access-Control-Allow-Origin': '*'
    }
  }
];
