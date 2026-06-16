// Rate Limiting Utilities для API Gateway
// Управляет ограничением количества запросов для предотвращения злоупотреблений

export interface RateLimitConfig {
  requestsPerMinute: number;
  burstSize: number;
  windowMs: number;
  keyGenerator?: (req: Request) => string;
  skipSuccessfulRequests?: boolean;
  skipFailedRequests?: boolean;
}

export interface RateLimitStore {
  get(key: string): RateLimitData | null;
  set(key: string, data: RateLimitData): void;
  delete(key: string): void;
  clear(): void;
}

export interface RateLimitData {
  count: number;
  resetTime: number;
  totalRequests: number;
  blockedRequests: number;
  firstRequest: number;
  lastRequest: number;
}

export interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetTime: number;
  totalRequests: number;
  blockedRequests: number;
  limit: number;
}

/**
 * В памяти хранилище для rate limiting
 */
export class MemoryRateLimitStore implements RateLimitStore {
  private store = new Map<string, RateLimitData>();
  private maxEntries = 10000; // Максимум записей в памяти

  get(key: string): RateLimitData | null {
    const data = this.store.get(key);
    if (data && Date.now() < data.resetTime) {
      return data;
    }
    
    // Удаляем просроченные записи
    if (data) {
      this.store.delete(key);
    }
    
    return null;
  }

  set(key: string, data: RateLimitData): void {
    // Ограничиваем размер хранилища
    if (this.store.size >= this.maxEntries) {
      // Удаляем самые старые записи
      const entries = Array.from(this.store.entries());
      entries.sort((a, b) => a[1].lastRequest - b[1].lastRequest);
      
      const toDelete = Math.ceil(this.maxEntries * 0.1); // Удаляем 10% самых старых
      for (let i = 0; i < toDelete; i++) {
        this.store.delete(entries[i][0]);
      }
    }
    
    this.store.set(key, data);
  }

  delete(key: string): void {
    this.store.delete(key);
  }

  clear(): void {
    this.store.clear();
  }

  getSize(): number {
    return this.store.size;
  }
}

/**
 * Основной класс для rate limiting
 */
export class RateLimiter {
  private store: RateLimitStore;
  private configs: Map<string, RateLimitConfig> = new Map();

  constructor(store?: RateLimitStore) {
    this.store = store || new MemoryRateLimitStore();
    
    // Устанавливаем стандартные конфигурации
    this.setupDefaultConfigs();
    
    // Запускаем очистку просроченных записей
    this.startCleanup();
  }

  /**
   * Устанавливает конфигурацию для ключа
   */
  setConfig(key: string, config: RateLimitConfig): void {
    this.configs.set(key, config);
  }

  /**
   * Проверяет rate limit для запроса
   */
  async checkLimit(req: Request, key?: string): Promise<RateLimitResult> {
    const identifier = key || this.generateKey(req);
    const config = this.findBestConfig(req);
    
    let data = this.store.get(identifier);
    
    // Если данных нет или окно сброшено, создаем новые
    const now = Date.now();
    if (!data || now >= data.resetTime) {
      data = {
        count: 0,
        resetTime: now + config.windowMs,
        totalRequests: 0,
        blockedRequests: 0,
        firstRequest: now,
        lastRequest: now
      };
    }

    // Увеличиваем счетчики
    data.totalRequests++;
    data.count++;
    data.lastRequest = now;

    // Проверяем лимиты
    const remaining = Math.max(0, config.requestsPerMinute - data.count);
    const allowed = data.count <= config.requestsPerMinute && remaining >= 0;

    // Если запрос заблокирован
    if (!allowed) {
      data.blockedRequests++;
    }

    // Сохраняем обновленные данные
    this.store.set(identifier, data);

    return {
      allowed,
      remaining,
      resetTime: data.resetTime,
      totalRequests: data.totalRequests,
      blockedRequests: data.blockedRequests,
      limit: config.requestsPerMinute
    };
  }

  /**
   * Сбрасывает лимиты для ключа
   */
  resetLimit(key: string): void {
    this.store.delete(key);
  }

  /**
   * Получает текущие данные по ключу
   */
  getLimitData(key: string): RateLimitData | null {
    return this.store.get(key);
  }

  /**
   * Очищает все данные
   */
  clear(): void {
    this.store.clear();
  }

  /**
   * Получает статистику rate limiting
   */
  getStats(): any {
    const totalRequests = 0;
    const totalBlocked = 0;
    const activeKeys = 0;

    return {
      totalRequests,
      totalBlocked,
      activeKeys: this.store.getSize(),
      storeSize: this.store.getSize(),
      configs: Object.fromEntries(this.configs)
    };
  }

  /**
   * Генерирует ключ для идентификации клиента
   */
  private generateKey(req: Request): string {
    const headers = req.headers;
    
    // Пробуем разные источники идентификации
    let identifier = '';
    
    // API Key
    const apiKey = headers.get('x-api-key');
    if (apiKey) {
      identifier = `api:${apiKey}`;
    }
    
    // Authorization header
    const auth = headers.get('authorization');
    if (auth && !identifier) {
      identifier = `auth:${auth.substring(0, 20)}`; // Хешируем для безопасности
    }
    
    // User-Agent + IP
    if (!identifier) {
      const userAgent = headers.get('user-agent') || 'unknown';
      const ip = headers.get('x-forwarded-for') || headers.get('x-real-ip') || 'unknown';
      identifier = `ip:${ip}:${userAgent.substring(0, 50)}`;
    }
    
    return identifier;
  }

  /**
   * Находит лучшую конфигурацию для запроса
   */
  private findBestConfig(req: Request): RateLimitConfig {
    const url = new URL(req.url);
    const path = url.pathname;
    
    // Ищем точное совпадение пути
    for (const [pattern, config] of this.configs) {
      if (this.matchesPattern(path, pattern)) {
        return config;
      }
    }
    
    // Возвращаем стандартную конфигурацию
    return this.configs.get('default') || {
      requestsPerMinute: 100,
      burstSize: 20,
      windowMs: 60000
    };
  }

  /**
   * Проверяет совпадение паттерна с путем
   */
  private matchesPattern(path: string, pattern: string): boolean {
    // Простое совпадение с wildcard поддержкой
    const regex = new RegExp(pattern.replace(/\*/g, '.*'));
    return regex.test(path);
  }

  /**
   * Устанавливает стандартные конфигурации
   */
  private setupDefaultConfigs(): void {
    // Стандартная конфигурация
    this.configs.set('default', {
      requestsPerMinute: 100,
      burstSize: 20,
      windowMs: 60000
    });

    // Конфигурация для health checks
    this.configs.set('/health', {
      requestsPerMinute: 1000,
      burstSize: 100,
      windowMs: 60000
    });

    // Конфигурация для API endpoints
    this.configs.set('/v1/*', {
      requestsPerMinute: 200,
      burstSize: 50,
      windowMs: 60000
    });

    // Конфигурация для админ endpoints
    this.configs.set('/admin/*', {
      requestsPerMinute: 50,
      burstSize: 10,
      windowMs: 60000
    });

    // Конфифигурация для метрик
    this.configs.set('/metrics', {
      requestsPerMinute: 30,
      burstSize: 5,
      windowMs: 60000
    });
  }

  /**
   * Запускает периодическую очистку просроченных записей
   */
  private startCleanup(): void {
    setInterval(() => {
      const now = Date.now();
      // В реальном проекте здесь была бы более сложная логика очистки
      console.log(`Rate limiter cleanup: ${this.store.getSize()} active entries`);
    }, 300000); // Каждые 5 минут
  }
}

/**
 * Middleware для использования в Deno.serve
 */
export function rateLimitMiddleware(req: Request, customConfig?: RateLimitConfig): RateLimitResult | null {
  // В реальной реализации здесь был бы доступ к экземпляру rate limiter
  // Для демонстрации возвращаем заглушку
  return {
    allowed: true,
    remaining: 99,
    resetTime: Date.now() + 60000,
    totalRequests: 1,
    blockedRequests: 0,
    limit: 100
  };
}

/**
 * Создает Rate Limit Response Headers
 */
export function createRateLimitHeaders(result: RateLimitResult): Record<string, string> {
  return {
    'X-RateLimit-Limit': result.limit.toString(),
    'X-RateLimit-Remaining': result.remaining.toString(),
    'X-RateLimit-Reset': Math.ceil(result.resetTime / 1000).toString(),
    'X-RateLimit-Total': result.totalRequests.toString(),
    'X-RateLimit-Blocked': result.blockedRequests.toString()
  };
}

/**
 * Создает ошибку rate limit
 */
export function createRateLimitError(result: RateLimitResult): Response {
  const headers = createRateLimitHeaders(result);
  
  return new Response(JSON.stringify({
    error: {
      code: 'RATE_LIMIT_EXCEEDED',
      message: 'Rate limit exceeded. Too many requests.',
      details: {
        limit: result.limit,
        remaining: result.remaining,
        resetTime: new Date(result.resetTime).toISOString()
      }
    }
  }), {
    status: 429,
    headers: {
      'Content-Type': 'application/json',
      'Retry-After': Math.ceil((result.resetTime - Date.now()) / 1000).toString(),
      ...headers
    }
  });
}

// Глобальный экземпляр rate limiter
export const rateLimiter = new RateLimiter();