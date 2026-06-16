/**
 * Вспомогательные функции для тестирования Edge Functions
 * Утилиты для создания тестовых данных, проверок и подготовительных операций
 */

// Импорты для тестирования
export interface TestContext {
  setup(): Promise<void> | void;
  teardown(): Promise<void> | void;
}

export interface TestAssertion {
  actual: any;
  expected: any;
  message?: string;
}

// ==================== УТИЛИТЫ ДЛЯ СОЗДАНИЯ ТЕСТОВЫХ ДАННЫХ ====================

/**
 * Генерация случайных тестовых данных
 */
export class TestDataGenerator {
  private static counter = 0;

  static generateId(): string {
    return `test-id-${Date.now()}-${++this.counter}`;
  }

  static generateEmail(domain: string = 'test.com'): string {
    return `test${this.counter}@${domain}`;
  }

  static generateName(): string {
    const names = ['John', 'Jane', 'Alice', 'Bob', 'Charlie', 'Diana'];
    const surnames = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones'];
    return `${names[this.counter % names.length]} ${surnames[this.counter % surnames.length]}`;
  }

  static generateText(length: number = 100): string {
    const chars = 'abcdefghijklmnopqrstuvwxyz ';
    let result = '';
    for (let i = 0; i < length; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  }

  static generateDate(start: Date = new Date(2020, 0, 1), end: Date = new Date()): Date {
    const startTime = start.getTime();
    const endTime = end.getTime();
    return new Date(startTime + Math.random() * (endTime - startTime));
  }

  static generateUser(overrides: any = {}): any {
    return {
      id: this.generateId(),
      email: this.generateEmail(),
      name: this.generateName(),
      role: 'user',
      created_at: this.generateDate().toISOString(),
      updated_at: new Date().toISOString(),
      ...overrides
    };
  }

  static generateProduct(overrides: any = {}): any {
    return {
      id: this.generateId(),
      name: `Test Product ${this.counter}`,
      description: this.generateText(50),
      price: Math.floor(Math.random() * 1000) + 1,
      category: 'test-category',
      created_at: this.generateDate().toISOString(),
      updated_at: new Date().toISOString(),
      ...overrides
    };
  }

  static generateArray<T>(generator: () => T, count: number = 5): T[] {
    return Array.from({ length: count }, generator);
  }
}

// ==================== УТИЛИТЫ ДЛЯ ПРОВЕРОК ====================

/**
 * Кастомные проверки (assertions)
 */
export class TestAssertions {
  static toBeEqual(actual: any, expected: any, message?: string) {
    const actualStr = JSON.stringify(actual);
    const expectedStr = JSON.stringify(expected);
    
    if (actualStr !== expectedStr) {
      throw new Error(message || `Expected ${expectedStr}, but got ${actualStr}`);
    }
  }

  static toBeTypeOf(actual: any, expectedType: string, message?: string) {
    const actualType = typeof actual;
    if (actualType !== expectedType) {
      throw new Error(message || `Expected type ${expectedType}, but got ${actualType}`);
    }
  }

  static toBeInstanceOf(actual: any, expectedClass: Function, message?: string) {
    if (!(actual instanceof expectedClass)) {
      throw new Error(message || `Expected instance of ${expectedClass.name}, but got ${actual?.constructor?.name}`);
    }
  }

  static toBeTruthy(actual: any, message?: string) {
    if (!actual) {
      throw new Error(message || `Expected truthy value, but got ${actual}`);
    }
  }

  static toBeFalsy(actual: any, message?: string) {
    if (actual) {
      throw new Error(message || `Expected falsy value, but got ${actual}`);
    }
  }

  static toContain(actual: any[], expected: any, message?: string) {
    if (!actual.includes(expected)) {
      throw new Error(message || `Expected array to contain ${expected}, but got ${actual}`);
    }
  }

  static toHaveProperty(actual: any, property: string, message?: string) {
    if (!(property in actual)) {
      throw new Error(message || `Expected object to have property ${property}`);
    }
  }

  static toHaveLength(actual: any, expectedLength: number, message?: string) {
    if (actual.length !== expectedLength) {
      throw new Error(message || `Expected length ${expectedLength}, but got ${actual.length}`);
    }
  }

  static toMatchPattern(actual: string, pattern: RegExp, message?: string) {
    if (!pattern.test(actual)) {
      throw new Error(message || `Expected string to match pattern ${pattern}, but got ${actual}`);
    }
  }

  static toThrowError(fn: Function, errorMessage?: string, message?: string) {
    try {
      fn();
      throw new Error(message || `Expected function to throw an error, but it didn't`);
    } catch (error) {
      if (errorMessage && error instanceof Error && !error.message.includes(errorMessage)) {
        throw new Error(message || `Expected error message to include "${errorMessage}", but got "${error.message}"`);
      }
    }
  }
}

// ==================== УТИЛИТЫ ДЛЯ ТЕСТИРОВАНИЯ EDGE FUNCTIONS ====================

/**
 * Утилиты для тестирования Deno Edge Functions
 */
export class EdgeFunctionTester {
  private static functionCache: Map<string, Function> = new Map();

  /**
   * Загрузка и кэширование Edge Function
   */
  static async loadFunction(functionName: string, functionPath: string): Promise<Function> {
    if (this.functionCache.has(functionName)) {
      return this.functionCache.get(functionName)!;
    }

    try {
      const module = await import(functionPath);
      const handler = module.default || module.handler || module.serve;
      
      if (typeof handler !== 'function') {
        throw new Error(`Handler function not found in ${functionPath}`);
      }

      this.functionCache.set(functionName, handler);
      return handler;
    } catch (error) {
      throw new Error(`Failed to load function ${functionName}: ${error.message}`);
    }
  }

  /**
   * Создание мок-запроса для тестирования
   */
  static createMockRequest(
    url: string = 'https://test.com',
    method: string = 'GET',
    headers: Record<string, string> = {},
    body?: any
  ): Request {
    const requestInit: RequestInit = {
      method,
      headers,
    };

    if (body && method !== 'GET') {
      requestInit.body = JSON.stringify(body);
      requestInit.headers = {
        'Content-Type': 'application/json',
        ...headers
      };
    }

    return new Request(url, requestInit);
  }

  /**
   * Создание мок-ответа для тестирования
   */
  static createMockResponse(data: any = null, status: number = 200, headers: Record<string, string> = {}): Response {
    const responseData = data || { success: true };
    const responseHeaders = {
      'Content-Type': 'application/json',
      ...headers
    };

    return new Response(JSON.stringify(responseData), {
      status,
      headers: responseHeaders
    });
  }

  /**
   * Выполнение Edge Function с тестовыми параметрами
   */
  static async executeFunction(
    functionPath: string,
    functionName: string,
    request: Request,
    context: any = {}
  ): Promise<Response> {
    const handler = await this.loadFunction(functionName, functionPath);
    
    // Создаем контекст выполнения
    const executionContext = {
      ...context,
      waitUntil: (promise: Promise<any>) => promise,
      passThroughOnException: () => {},
      log: (...args: any[]) => console.log('[Edge Function Log]', ...args),
      error: (...args: any[]) => console.error('[Edge Function Error]', ...args),
    };

    return await handler(request, executionContext);
  }

  /**
   * Парсинг JSON из ответа с обработкой ошибок
   */
  static async parseResponse(response: Response): Promise<any> {
    const text = await response.text();
    
    try {
      return JSON.parse(text);
    } catch (error) {
      throw new Error(`Failed to parse response as JSON: ${text}`);
    }
  }

  /**
   * Проверка статуса ответа
   */
  static expectStatus(response: Response, expectedStatus: number) {
    if (response.status !== expectedStatus) {
      throw new Error(`Expected status ${expectedStatus}, but got ${response.status}`);
    }
  }

  /**
   * Проверка заголовков ответа
   */
  static expectHeader(response: Response, headerName: string, expectedValue?: string) {
    const headerValue = response.headers.get(headerName);
    
    if (!headerValue) {
      throw new Error(`Expected header ${headerName} not found in response`);
    }
    
    if (expectedValue && headerValue !== expectedValue) {
      throw new Error(`Expected header ${headerName} to be ${expectedValue}, but got ${headerValue}`);
    }
  }
}

// ==================== УТИЛИТЫ ДЛЯ ОКРУЖЕНИЯ ТЕСТОВ ====================

/**
 * Управление тестовым окружением
 */
export class TestEnvironment {
  private static originalEnv: Record<string, string | undefined> = {};

  /**
   * Сохранение оригинальных переменных окружения
   */
  static saveOriginalEnv() {
    this.originalEnv = { ...Deno.env.toObject() };
  }

  /**
   * Восстановление оригинальных переменных окружения
   */
  static restoreOriginalEnv() {
    // Очищаем все текущие переменные
    const currentEnv = Deno.env.toObject();
    for (const key in currentEnv) {
      delete Deno.env.delete(key);
    }

    // Восстанавливаем оригинальные
    for (const [key, value] of Object.entries(this.originalEnv)) {
      if (value !== undefined) {
        Deno.env.set(key, value);
      }
    }
  }

  /**
   * Установка переменных окружения для тестов
   */
  static setEnv(env: Record<string, string>) {
    for (const [key, value] of Object.entries(env)) {
      Deno.env.set(key, value);
    }
  }

  /**
   * Очистка всех переменных окружения
   */
  static clearEnv() {
    const env = Deno.env.toObject();
    for (const key in env) {
      Deno.env.delete(key);
    }
  }

  /**
   * Создание временной директории для тестов
   */
  static async createTempDir(): Promise<string> {
    const tempDir = await Deno.makeTempDir();
    return tempDir;
  }

  /**
   * Удаление временной директории
   */
  static async removeTempDir(dirPath: string) {
    try {
      await Deno.remove(dirPath, { recursive: true });
    } catch (error) {
      console.warn(`Failed to remove temp dir ${dirPath}:`, error.message);
    }
  }

  /**
   * Создание временного файла
   */
  static async createTempFile(content: string = '', extension: string = '.txt'): Promise<string> {
    const tempDir = await Deno.makeTempDir();
    const fileName = `test-${Date.now()}${extension}`;
    const filePath = `${tempDir}/${fileName}`;
    
    await Deno.writeTextFile(filePath, content);
    
    return filePath;
  }
}

// ==================== УТИЛИТЫ ДЛЯ ПОДГОТОВКИ И ОЧИСТКИ ====================

/**
 * Базовый класс для тестовых окружений
 */
export abstract class BaseTestSuite {
  protected async setup() {
    // Переопределяется в потомках
  }

  protected async teardown() {
    // Переопределяется в потомках
  }

  async runSetup() {
    await this.setup();
  }

  async runTeardown() {
    await this.teardown();
  }
}

// ==================== МАКРОСЫ ДЛЯ ТЕСТИРОВАНИЯ ====================

/**
 * Функция для пропуска теста
 */
export function skip(reason: string) {
  console.log(`⏭️  SKIP: ${reason}`);
  return;
}

/**
 * Функция для отметки теста как TODO
 */
export function todo(description: string) {
  console.log(`📝 TODO: ${description}`);
  return;
}

/**
 * Группировка тестов
 */
export function describe(name: string, fn: () => void) {
  console.log(`📦 DESCRIBE: ${name}`);
  fn();
}

// ==================== УТИЛИТЫ ДЛЯ ПРОФИЛИРОВАНИЯ ====================

/**
 * Профилировщик производительности
 */
export class PerformanceProfiler {
  private static profiles: Map<string, number[]> = new Map();

  static start(label: string): void {
    const startTime = performance.now();
    (this as any)[label] = startTime;
  }

  static end(label: string): number {
    const startTime = (this as any)[label];
    if (startTime === undefined) {
      throw new Error(`No start time found for label: ${label}`);
    }
    
    const endTime = performance.now();
    const duration = endTime - startTime;
    
    if (!this.profiles.has(label)) {
      this.profiles.set(label, []);
    }
    
    this.profiles.get(label)!.push(duration);
    
    console.log(`⏱️  ${label}: ${duration.toFixed(2)}ms`);
    return duration;
  }

  static getAverage(label: string): number {
    const times = this.profiles.get(label);
    if (!times || times.length === 0) {
      return 0;
    }
    
    return times.reduce((sum, time) => sum + time, 0) / times.length;
  }

  static getReport(): Record<string, { average: number; min: number; max: number; count: number }> {
    const report: Record<string, { average: number; min: number; max: number; count: number }> = {};
    
    for (const [label, times] of this.profiles) {
      report[label] = {
        average: this.getAverage(label),
        min: Math.min(...times),
        max: Math.max(...times),
        count: times.length
      };
    }
    
    return report;
  }
}

// ==================== ЭКСПОРТ УТИЛИТ ====================

// Экспортируем наиболее часто используемые утилиты
export const { generateId, generateEmail, generateUser, generateProduct } = TestDataGenerator;
export const { toBeEqual, toBeTypeOf, toBeTruthy, toThrowError } = TestAssertions;
export const { createMockRequest, createMockResponse, executeFunction } = EdgeFunctionTester;
export const { setEnv, clearEnv, createTempDir } = TestEnvironment;

// Глобальные хелперы для быстрого доступа
(globalThis as any).testData = TestDataGenerator;
(globalThis as any).assertions = TestAssertions;
(globalThis as any).tester = EdgeFunctionTester;
(globalThis as any).env = TestEnvironment;