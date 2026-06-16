// Caching Utilities для API Gateway
// Управляет кэшированием запросов и ответов для повышения производительности

export interface CacheConfig {
  maxSize: number;
  defaultTTL: number;
  enableCompression: boolean;
  enableMetrics: boolean;
}

export interface CacheEntry {
  key: string;
  value: CacheValue;
  ttl: number;
  createdAt: number;
  lastAccessed: number;
  accessCount: number;
  size: number;
}

export interface CacheValue {
  status: number;
  headers: Record<string, string>;
  body: string;
  compressed?: boolean;
}

export interface CacheStats {
  hits: number;
  misses: number;
  hitRate: number;
  totalSize: number;
  entryCount: number;
  evictions: number;
  oldestEntry: number;
  newestEntry: number;
}

/**
 * Реализация кэша в памяти с LRU алгоритмом
 */
export class MemoryCache {
  private cache: Map<string, CacheEntry> = new Map();
  private accessOrder: string[] = []; // Для LRU
  private config: CacheConfig;
  private stats: CacheStats = {
    hits: 0,
    misses: 0,
    hitRate: 0,
    totalSize: 0,
    entryCount: 0,
    evictions: 0,
    oldestEntry: Date.now(),
    newestEntry: Date.now()
  };

  constructor(config: Partial<CacheConfig> = {}) {
    this.config = {
      maxSize: 1000,
      defaultTTL: 300000, // 5 минут
      enableCompression: false,
      enableMetrics: true,
      ...config
    };
  }

  /**
   * Получает значение из кэша
   */
  get(key: string): CacheValue | null {
    const entry = this.cache.get(key);
    
    if (!entry) {
      this.stats.misses++;
      this.updateHitRate();
      return null;
    }

    // Проверяем TTL
    if (Date.now() > entry.ttl) {
      this.delete(key);
      this.stats.misses++;
      this.updateHitRate();
      return null;
    }

    // Обновляем статистику доступа
    entry.lastAccessed = Date.now();
    entry.accessCount++;
    
    // Перемещаем в конец списка доступа (LRU)
    this.updateAccessOrder(key);
    
    // Возвращаем значение
    let value = entry.value;
    
    // Декомпрессия если нужно
    if (value.compressed && this.config.enableCompression) {
      value = this.decompress(value);
    }
    
    this.stats.hits++;
    this.updateHitRate();
    
    return value;
  }

  /**
   * Устанавливает значение в кэш
   */
  set(key: string, value: CacheValue, customTTL?: number): void {
    // Удаляем существующую запись
    if (this.cache.has(key)) {
      this.delete(key);
    }

    // Проверяем размер кэша
    if (this.cache.size >= this.config.maxSize) {
      this.evictLRU();
    }

    // Подготавливаем значение для хранения
    let cacheValue = value;
    
    // Компрессия если включена
    if (this.config.enableCompression) {
      cacheValue = this.compress(value);
    }

    const entry: CacheEntry = {
      key,
      value: cacheValue,
      ttl: Date.now() + (customTTL || this.config.defaultTTL),
      createdAt: Date.now(),
      lastAccessed: Date.now(),
      accessCount: 1,
      size: this.calculateSize(cacheValue)
    };

    this.cache.set(key, entry);
    this.accessOrder.push(key);
    this.updateStats();
  }

  /**
   * Удаляет запись из кэша
   */
  delete(key: string): boolean {
    const deleted = this.cache.delete(key);
    
    if (deleted) {
      const index = this.accessOrder.indexOf(key);
      if (index > -1) {
        this.accessOrder.splice(index, 1);
      }
      this.updateStats();
    }
    
    return deleted;
  }

  /**
   * Проверяет существование ключа
   */
  has(key: string): boolean {
    const entry = this.cache.get(key);
    if (!entry) return false;
    
    if (Date.now() > entry.ttl) {
      this.delete(key);
      return false;
    }
    
    return true;
  }

  /**
   * Очищает весь кэш
   */
  clear(): void {
    this.cache.clear();
    this.accessOrder = [];
    this.stats = {
      hits: 0,
      misses: 0,
      hitRate: 0,
      totalSize: 0,
      entryCount: 0,
      evictions: 0,
      oldestEntry: Date.now(),
      newestEntry: Date.now()
    };
  }

  /**
   * Получает статистику кэша
   */
  getStats(): CacheStats {
    return { ...this.stats };
  }

  /**
   * Получает все ключи в кэше
   */
  keys(): string[] {
    return Array.from(this.cache.keys());
  }

  /**
   * Получает все записи
   */
  entries(): Array<{ key: string; entry: CacheEntry }> {
    return Array.from(this.cache.entries()).map(([key, entry]) => ({ key, entry }));
  }

  /**
   * Удаляет просроченные записи
   */
  cleanup(): number {
    const now = Date.now();
    const expiredKeys: string[] = [];
    
    for (const [key, entry] of this.cache.entries()) {
      if (now > entry.ttl) {
        expiredKeys.push(key);
      }
    }
    
    for (const key of expiredKeys) {
      this.delete(key);
    }
    
    return expiredKeys.length;
  }

  /**
   * Обновляет порядок доступа для LRU
   */
  private updateAccessOrder(key: string): void {
    const index = this.accessOrder.indexOf(key);
    if (index > -1) {
      this.accessOrder.splice(index, 1);
      this.accessOrder.push(key);
    }
  }

  /**
   * Удаляет наименее используемую запись (LRU)
   */
  private evictLRU(): void {
    if (this.accessOrder.length === 0) return;
    
    const lruKey = this.accessOrder.shift();
    if (lruKey) {
      this.cache.delete(lruKey);
      this.stats.evictions++;
    }
  }

  /**
   * Вычисляет размер записи
   */
  private calculateSize(value: CacheValue): number {
    const headersSize = JSON.stringify(value.headers).length;
    const bodySize = value.body.length;
    return headersSize + bodySize + 100; // +100 для метаданных
  }

  /**
   * Обновляет статистику
   */
  private updateStats(): void {
    this.stats.entryCount = this.cache.size;
    this.stats.totalSize = Array.from(this.cache.values())
      .reduce((sum, entry) => sum + entry.size, 0);
    
    // Находим самые старые и новые записи
    const entries = Array.from(this.cache.values());
    if (entries.length > 0) {
      this.stats.oldestEntry = Math.min(...entries.map(e => e.createdAt));
      this.stats.newestEntry = Math.max(...entries.map(e => e.createdAt));
    }
  }

  /**
   * Обновляет hit rate
   */
  private updateHitRate(): void {
    const total = this.stats.hits + this.stats.misses;
    this.stats.hitRate = total > 0 ? (this.stats.hits / total) * 100 : 0;
  }

  /**
   * Сжимает значение для хранения
   */
  private compress(value: CacheValue): CacheValue {
    // Простая компрессия для демонстрации
    // В реальном проекте используйте proper compression library
    return {
      ...value,
      body: value.body, // Здесь была бы компрессия
      compressed: false // Упрощено для демонстрации
    };
  }

  /**
   * Разжимает значение при чтении
   */
  private decompress(value: CacheValue): CacheValue {
    return {
      ...value,
      compressed: false
    };
  }
}

/**
 * Генератор ключей кэша
 */
export class CacheKeyGenerator {
  /**
   * Генерирует ключ для запроса
   */
  generateRequestKey(req: Request, includeHeaders: string[] = []): string {
    const url = new URL(req.url);
    const parts = [req.method, url.pathname];
    
    // Добавляем query параметры
    if (url.search) {
      parts.push(url.search);
    }
    
    // Добавляем выбранные заголовки
    const relevantHeaders = includeHeaders
      .map(header => req.headers.get(header))
      .filter(Boolean);
    
    if (relevantHeaders.length > 0) {
      parts.push(relevantHeaders.join('|'));
    }
    
    return parts.join(':');
  }

  /**
   * Генерирует ключ для конкретного endpoint
   */
  generateEndpointKey(endpoint: string, params?: Record<string, any>): string {
    let key = endpoint;
    
    if (params) {
      const sortedParams = Object.keys(params).sort().map(k => `${k}:${params[k]}`);
      key += ':' + sortedParams.join('|');
    }
    
    return key;
  }
}

/**
 * Менеджер кэша для API Gateway
 */
export class CacheManager {
  private cache: MemoryCache;
  private keyGenerator: CacheKeyGenerator;

  constructor(config?: Partial<CacheConfig>) {
    this.cache = new MemoryCache(config);
    this.keyGenerator = new CacheKeyGenerator();
  }

  /**
   * Пытается получить кэшированный ответ
   */
  getCachedResponse(req: Request): CacheValue | null {
    const key = this.keyGenerator.generateRequestKey(req, [
      'authorization',
      'accept-language',
      'x-api-version'
    ]);
    
    return this.cache.get(key);
  }

  /**
   * Кэширует ответ
   */
  cacheResponse(req: Request, response: Response, ttl?: number): void {
    if (!this.shouldCache(req, response)) {
      return;
    }

    const key = this.keyGenerator.generateRequestKey(req, [
      'authorization',
      'accept-language',
      'x-api-version'
    ]);

    const cacheValue: CacheValue = {
      status: response.status,
      headers: Object.fromEntries(response.headers.entries()),
      body: typeof response.body === 'string' ? response.body : ''
    };

    this.cache.set(key, cacheValue, ttl);
  }

  /**
   * Проверяет, нужно ли кэшировать ответ
   */
  private shouldCache(req: Request, response: Response): boolean {
    // Кэшируем только GET запросы
    if (req.method !== 'GET') {
      return false;
    }

    // Не кэшируем ответы с ошибками
    if (response.status >= 400) {
      return false;
    }

    // Не кэшируем ответы с заголовком no-cache
    if (response.headers.get('cache-control')?.includes('no-cache')) {
      return false;
    }

    // Не кэшируем ответы с персонализированными данными
    const authHeader = req.headers.get('authorization');
    if (authHeader) {
      // Можно кэшировать для аутентифицированных пользователей, 
      // но с учетом authorization header в ключе
    }

    return true;
  }

  /**
   * Получает TTL для endpoint
   */
  getTTLForEndpoint(path: string): number {
    // Различное время жизни кэша для разных типов данных
    if (path.includes('/health') || path.includes('/status')) {
      return 60000; // 1 минута
    }
    
    if (path.includes('/docs') || path.includes('/openapi')) {
      return 300000; // 5 минут
    }
    
    if (path.includes('/static') || path.includes('/public')) {
      return 3600000; // 1 час
    }
    
    return 300000; // 5 минут по умолчанию
  }

  /**
   * Создает заголовки для кэшированного ответа
   */
  createCacheHeaders(ttl: number): Record<string, string> {
    return {
      'Cache-Control': `public, max-age=${Math.floor(ttl / 1000)}`,
      'X-Cache': 'MISS'
    };
  }

  /**
   * Создает заголовки для HIT кэша
   */
  createCacheHitHeaders(): Record<string, string> {
    return {
      'X-Cache': 'HIT',
      'Cache-Control': 'public, max-age=300'
    };
  }

  /**
   * Получает статистику кэша
   */
  getStats(): CacheStats {
    return this.cache.getStats();
  }

  /**
   * Очищает кэш
   */
  clear(): void {
    this.cache.clear();
  }

  /**
   * Удаляет просроченные записи
   */
  cleanup(): number {
    return this.cache.cleanup();
  }
}

// Глобальный экземпляр CacheManager
export const cacheManager = new CacheManager();

// Middleware для кэширования
export function cacheMiddleware(req: Request): CacheValue | null {
  return cacheManager.getCachedResponse(req);
}