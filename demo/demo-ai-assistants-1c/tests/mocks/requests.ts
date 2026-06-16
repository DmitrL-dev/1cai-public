/**
 * Моки для HTTP запросов и ответов
 * Используются для тестирования API запросов без реальных сетевых вызовов
 */

export interface MockResponse {
  status: number;
  statusText: string;
  ok: boolean;
  headers: Record<string, string>;
  data?: any;
  json(): Promise<any>;
  text(): Promise<string>;
  blob(): Promise<Blob>;
}

export interface MockRequestOptions {
  method?: string;
  headers?: Record<string, string>;
  body?: any;
  signal?: AbortSignal;
}

export interface MockFetchResult {
  response: MockResponse;
  request: {
    url: string;
    method: string;
    headers: Record<string, string>;
    body?: any;
  };
}

// Класс для мока HTTP ответа
export class MockHttpResponse implements MockResponse {
  public status: number;
  public statusText: string;
  public ok: boolean;
  public headers: Record<string, string>;
  private _data: any;

  constructor(data: any, status: number = 200, statusText: string = 'OK') {
    this._data = data;
    this.status = status;
    this.statusText = statusText;
    this.ok = status >= 200 && status < 300;
    this.headers = {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    };
  }

  async json(): Promise<any> {
    return this._data;
  }

  async text(): Promise<string> {
    return typeof this._data === 'string' ? this._data : JSON.stringify(this._data);
  }

  async blob(): Promise<Blob> {
    return new Blob([JSON.stringify(this._data)], { type: 'application/json' });
  }
}

// Сервис для мока fetch
export class MockFetchService {
  private requests: MockFetchResult[] = [];
  private handlers: Map<string, (url: string, options?: MockRequestOptions) => MockResponse> = new Map();

  // Регистрация обработчика для определенного URL
  registerHandler(urlPattern: string, handler: (url: string, options?: MockRequestOptions) => MockResponse) {
    this.handlers.set(urlPattern, handler);
  }

  // Удаление обработчика
  unregisterHandler(urlPattern: string) {
    this.handlers.delete(urlPattern);
  }

  // Метод для имитации fetch
  async fetch(url: string, options: MockRequestOptions = {}): Promise<MockResponse> {
    const { method = 'GET', headers = {}, body = null, signal } = options;

    // Сохраняем запрос для тестирования
    const request: MockFetchResult = {
      response: new MockHttpResponse({ message: 'Not found' }, 404, 'Not Found'),
      request: {
        url,
        method,
        headers,
        body
      }
    };

    // Ищем подходящий обработчик
    for (const [pattern, handler] of this.handlers) {
      if (this.matchesPattern(url, pattern)) {
        try {
          const response = handler(url, options);
          request.response = response;
          break;
        } catch (error) {
          request.response = new MockHttpResponse(
            { error: error.message }, 
            500, 
            'Internal Server Error'
          );
          break;
        }
      }
    }

    this.requests.push(request);

    // Симуляция задержки сети
    await new Promise(resolve => setTimeout(resolve, Math.random() * 100));

    // Проверка сигнала отмены
    if (signal?.aborted) {
      throw new DOMException('The operation was aborted', 'AbortError');
    }

    return request.response;
  }

  // Проверка соответствия URL паттерну
  private matchesPattern(url: string, pattern: string): boolean {
    if (pattern === url) return true;
    
    // Простая проверка с wildcard *
    if (pattern.includes('*')) {
      const regex = new RegExp(pattern.replace(/\*/g, '.*'));
      return regex.test(url);
    }

    // Проверка начала URL
    if (pattern.endsWith('/')) {
      return url.startsWith(pattern);
    }

    return false;
  }

  // Получение всех запросов для проверки
  getRequests(): MockFetchResult[] {
    return [...this.requests];
  }

  // Получение запросов по URL
  getRequestsByUrl(urlPattern: string): MockFetchResult[] {
    return this.requests.filter(req => this.matchesPattern(req.request.url, urlPattern));
  }

  // Получение запросов по методу
  getRequestsByMethod(method: string): MockFetchResult[] {
    return this.requests.filter(req => req.request.method === method.toUpperCase());
  }

  // Очистка истории запросов
  clearRequests() {
    this.requests = [];
  }

  // Сброс всех обработчиков
  reset() {
    this.handlers.clear();
    this.requests = [];
  }
}

// Глобальный экземпляр мока
export const mockFetchService = new MockFetchService();

// Замена глобального fetch
export function installMockFetch() {
  globalThis.fetch = mockFetchService.fetch.bind(mockFetchService) as any;
}

// Восстановление оригинального fetch
export function restoreOriginalFetch() {
  // В тестовой среде Deno это может быть не нужно
}

// Утилиты для создания типичных ответов
export function createSuccessResponse(data: any, status: number = 200): MockResponse {
  return new MockHttpResponse({ data }, status, 'Success');
}

export function createErrorResponse(error: string, status: number = 500): MockResponse {
  return new MockHttpResponse({ error }, status, 'Error');
}

export function createValidationErrorResponse(errors: Record<string, string[]>): MockResponse {
  return new MockHttpResponse({ 
    error: 'Validation failed', 
    details: errors 
  }, 422, 'Unprocessable Entity');
}

// Обработчики для типичных API endpoints
export function setupApiHandlers(baseUrl: string = 'https://api.example.com') {
  // GET /users
  mockFetchService.registerHandler(`${baseUrl}/users`, () => {
    return createSuccessResponse([
      { id: 1, name: 'User 1', email: 'user1@example.com' },
      { id: 2, name: 'User 2', email: 'user2@example.com' }
    ]);
  });

  // GET /users/:id
  mockFetchService.registerHandler(`${baseUrl}/users/*`, (url: string) => {
    const id = url.split('/').pop();
    return createSuccessResponse({ 
      id: parseInt(id || '0'), 
      name: `User ${id}`, 
      email: `user${id}@example.com` 
    });
  });

  // POST /users
  mockFetchService.registerHandler(`${baseUrl}/users`, (url: string, options: MockRequestOptions) => {
    const body = JSON.parse(options.body || '{}');
    return createSuccessResponse({ 
      id: Date.now(), 
      ...body 
    }, 201);
  });

  // PUT /users/:id
  mockFetchService.registerHandler(`${baseUrl}/users/*`, (url: string, options: MockRequestOptions) => {
    const body = JSON.parse(options.body || '{}');
    const id = url.split('/').pop();
    return createSuccessResponse({ 
      id: parseInt(id || '0'), 
      ...body 
    });
  });

  // DELETE /users/:id
  mockFetchService.registerHandler(`${baseUrl}/users/*`, () => {
    return new MockHttpResponse(null, 204, 'No Content');
  });

  // Обработчик ошибок 404
  mockFetchService.registerHandler(`${baseUrl}/*`, () => {
    return createErrorResponse('Not found', 404);
  });
}

// Обработчики для внешних API (OpenAI, Supabase и т.д.)
export function setupExternalApiHandlers() {
  // OpenAI API
  mockFetchService.registerHandler('https://api.openai.com/*', () => {
    return createSuccessResponse({
      choices: [{
        message: {
          content: 'This is a mock response from OpenAI'
        }
      }]
    });
  });

  // Supabase API
  mockFetchService.registerHandler('https://*.supabase.co/*', () => {
    return createSuccessResponse({ message: 'Mock Supabase response' });
  });
}

// Утилиты для проверки запросов
export function expectRequest(url: string, method: string = 'GET', body?: any) {
  const requests = mockFetchService.getRequests();
  const request = requests.find(req => 
    req.request.url === url && 
    req.request.method === method &&
    (body ? JSON.stringify(req.request.body) === JSON.stringify(body) : true)
  );
  
  if (!request) {
    throw new Error(`Expected request not found: ${method} ${url}`);
  }
  
  return request;
}

export function expectNoRequest(url: string, method: string = 'GET') {
  const requests = mockFetchService.getRequests();
  const request = requests.find(req => 
    req.request.url === url && 
    req.request.method === method
  );
  
  if (request) {
    throw new Error(`Unexpected request found: ${method} ${url}`);
  }
}

export function getRequestCount(url?: string, method?: string): number {
  const requests = mockFetchService.getRequests();
  return requests.filter(req => {
    if (url && req.request.url !== url) return false;
    if (method && req.request.method !== method) return false;
    return true;
  }).length;
}