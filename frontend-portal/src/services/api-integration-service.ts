// EventEmitter polyfill for browser compatibility
import { EventEmitter } from "events";

export interface APIEndpoint {
  id: string;
  name: string;
  url: string;
  method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  headers?: Record<string, string>;
  queryParams?: Record<string, any>;
  body?: any;
  timeout?: number;
  retries?: number;
  auth?: AuthConfig;
  rateLimit?: RateLimitConfig;
  cache?: CacheConfig;
  retryPolicy?: RetryPolicy;
}

export interface AuthConfig {
  type: "none" | "bearer" | "api-key" | "basic" | "oauth2";
  credentials: {
    token?: string;
    apiKey?: string;
    username?: string;
    password?: string;
    clientId?: string;
    clientSecret?: string;
  };
  refreshToken?: string;
  expiresAt?: Date;
}

export interface RateLimitConfig {
  requests: number;
  window: number; // в секундах
  queue?: boolean;
  throttleDelay?: number;
}

export interface CacheConfig {
  enabled: boolean;
  ttl: number; // в секундах
  strategy: "memory" | "localStorage" | "indexedDB";
}

export interface RetryPolicy {
  maxAttempts: number;
  backoffStrategy: "exponential" | "linear" | "fixed";
  baseDelay: number;
  maxDelay?: number;
  retryableStatusCodes?: number[];
}

export interface APIResponse<T = any> {
  data: T;
  status: number;
  headers: Record<string, string>;
  url: string;
  timing: {
    startTime: number;
    endTime: number;
    duration: number;
  };
  cached: boolean;
  error?: string;
}

export interface APIMetrics {
  totalRequests: number;
  successfulRequests: number;
  failedRequests: number;
  averageResponseTime: number;
  rateLimitHits: number;
  cacheHitRate: number;
  lastRequest?: Date;
  errorRate: number;
}

export class APIIntegrationService extends EventEmitter {
  private endpoints: Map<string, APIEndpoint> = new Map();
  private metrics: Map<string, APIMetrics> = new Map();
  private cache: Map<string, { data: any; expiresAt: number }> = new Map();
  private rateLimiters: Map<
    string,
    { requests: number; windowStart: number; queue: Function[] }
  > = new Map();

  constructor() {
    super();
    this.setupPeriodicCleanup();
  }

  /**
   * Регистрирует новый API endpoint
   */
  async registerEndpoint(endpoint: APIEndpoint): Promise<void> {
    if (this.endpoints.has(endpoint.id)) {
      throw new Error(`Endpoint with id '${endpoint.id}' already exists`);
    }

    this.endpoints.set(endpoint.id, endpoint);
    this.metrics.set(endpoint.id, {
      totalRequests: 0,
      successfulRequests: 0,
      failedRequests: 0,
      averageResponseTime: 0,
      rateLimitHits: 0,
      cacheHitRate: 0,
      errorRate: 0,
    });

    this.emit("endpoint-registered", { endpointId: endpoint.id, endpoint });
  }

  /**
   * Удаляет API endpoint
   */
  async unregisterEndpoint(endpointId: string): Promise<void> {
    if (!this.endpoints.has(endpointId)) {
      throw new Error(`Endpoint with id '${endpointId}' not found`);
    }

    this.endpoints.delete(endpointId);
    this.metrics.delete(endpointId);
    this.cache.delete(endpointId);
    this.rateLimiters.delete(endpointId);

    this.emit("endpoint-unregistered", { endpointId });
  }

  /**
   * Обновляет endpoint
   */
  async updateEndpoint(
    endpointId: string,
    updates: Partial<APIEndpoint>
  ): Promise<void> {
    const endpoint = this.endpoints.get(endpointId);
    if (!endpoint) {
      throw new Error(`Endpoint with id '${endpointId}' not found`);
    }

    const updatedEndpoint = { ...endpoint, ...updates };
    this.endpoints.set(endpointId, updatedEndpoint);

    this.emit("endpoint-updated", { endpointId, updates });
  }

  /**
   * Выполняет запрос к API
   */
  async request<T = any>(
    endpointId: string,
    options?: {
      headers?: Record<string, string>;
      queryParams?: Record<string, any>;
      body?: any;
      forceRefresh?: boolean;
    }
  ): Promise<APIResponse<T>> {
    const endpoint = this.endpoints.get(endpointId);
    if (!endpoint) {
      throw new Error(`Endpoint with id '${endpointId}' not found`);
    }

    const startTime = Date.now();

    try {
      // Проверяем rate limiting
      await this.checkRateLimit(endpointId, endpoint.rateLimit);

      // Проверяем кэш
      if (!options?.forceRefresh && endpoint.cache?.enabled) {
        const cachedResponse = this.getCachedResponse(endpointId);
        if (cachedResponse) {
          this.updateMetrics(endpointId, startTime, true);
          return cachedResponse;
        }
      }

      // Выполняем запрос
      const response = await this.executeRequest<T>(endpoint, options);

      // Кэшируем результат
      if (
        endpoint.cache?.enabled &&
        response.status >= 200 &&
        response.status < 300
      ) {
        this.cacheResponse(endpointId, response, endpoint.cache.ttl);
      }

      this.updateMetrics(endpointId, startTime, false, true);
      this.emit("request-success", { endpointId, response });

      return response;
    } catch (error) {
      this.updateMetrics(endpointId, startTime, false, false);
      this.emit("request-error", { endpointId, error: error as Error });

      // Пробуем повторный запрос согласно retry policy
      if (endpoint.retryPolicy) {
        return this.retryRequest<T>(endpointId, endpoint.retryPolicy, options);
      }

      throw error;
    }
  }

  /**
   * Выполняет множественные запросы параллельно
   */
  async batchRequest(
    requests: Array<{
      endpointId: string;
      options?: any;
    }>
  ): Promise<Map<string, APIResponse>> {
    const promises = requests.map(async ({ endpointId, options }) => {
      try {
        const response = await this.request(endpointId, options);
        return { endpointId, response, success: true };
      } catch (error) {
        return { endpointId, error: error as Error, success: false };
      }
    });

    const results = await Promise.all(promises);
    const responseMap = new Map<string, APIResponse>();

    for (const result of results) {
      if (result.success) {
        responseMap.set(result.endpointId, result.response);
      }
    }

    this.emit("batch-request-complete", {
      total: requests.length,
      successful: responseMap.size,
      failed: requests.length - responseMap.size,
    });

    return responseMap;
  }

  /**
   * Получает метрики endpoint'а
   */
  getMetrics(endpointId: string): APIMetrics | null {
    return this.metrics.get(endpointId) || null;
  }

  /**
   * Получает все метрики
   */
  getAllMetrics(): Map<string, APIMetrics> {
    return new Map(this.metrics);
  }

  /**
   * Получает список зарегистрированных endpoints
   */
  getEndpoints(): APIEndpoint[] {
    return Array.from(this.endpoints.values());
  }

  /**
   * Получает endpoint по ID
   */
  getEndpoint(endpointId: string): APIEndpoint | null {
    return this.endpoints.get(endpointId) || null;
  }

  /**
   * Проверяет состояние health check endpoint'а
   */
  async healthCheck(endpointId: string): Promise<{
    status: "healthy" | "degraded" | "unhealthy";
    responseTime: number;
    lastCheck: Date;
    error?: string;
  }> {
    const endpoint = this.endpoints.get(endpointId);
    if (!endpoint) {
      throw new Error(`Endpoint with id '${endpointId}' not found`);
    }

    const startTime = Date.now();

    try {
      const response = await this.request(endpointId, { forceRefresh: true });
      const responseTime = Date.now() - startTime;

      let status: "healthy" | "degraded" | "unhealthy";
      if (response.status >= 200 && response.status < 300) {
        status = responseTime < 1000 ? "healthy" : "degraded";
      } else {
        status = "unhealthy";
      }

      return {
        status,
        responseTime,
        lastCheck: new Date(),
      };
    } catch (error) {
      return {
        status: "unhealthy",
        responseTime: Date.now() - startTime,
        lastCheck: new Date(),
        error: (error as Error).message,
      };
    }
  }

  /**
   * Выполняет health check всех endpoints
   */
  async healthCheckAll(): Promise<
    Map<
      string,
      {
        status: "healthy" | "degraded" | "unhealthy";
        responseTime: number;
        lastCheck: Date;
        error?: string;
      }
    >
  > {
    const endpointIds = Array.from(this.endpoints.keys());
    const healthPromises = endpointIds.map(async (id) => {
      try {
        const health = await this.healthCheck(id);
        return { id, health, success: true };
      } catch (error) {
        return {
          id,
          health: {
            status: "unhealthy" as const,
            responseTime: 0,
            lastCheck: new Date(),
            error: (error as Error).message,
          },
          success: false,
        };
      }
    });

    const results = await Promise.all(healthPromises);
    const healthMap = new Map();

    for (const result of results) {
      healthMap.set(result.id, result.health);
    }

    return healthMap;
  }

  /**
   * Очищает кэш
   */
  clearCache(endpointId?: string): void {
    if (endpointId) {
      this.cache.delete(endpointId);
    } else {
      this.cache.clear();
    }
    this.emit("cache-cleared", { endpointId });
  }

  /**
   * Экспортирует конфигурацию endpoints
   */
  exportConfiguration(): string {
    const config = {
      endpoints: this.getEndpoints(),
      exportDate: new Date().toISOString(),
    };
    return JSON.stringify(config, null, 2);
  }

  /**
   * Импортирует конфигурацию endpoints
   */
  async importConfiguration(configJson: string): Promise<void> {
    try {
      const config = JSON.parse(configJson);

      if (!config.endpoints || !Array.isArray(config.endpoints)) {
        throw new Error("Invalid configuration format");
      }

      // Очищаем существующие endpoints
      this.endpoints.clear();
      this.metrics.clear();
      this.cache.clear();

      // Импортируем новые
      for (const endpoint of config.endpoints) {
        await this.registerEndpoint(endpoint);
      }

      this.emit("configuration-imported", {
        importedEndpoints: config.endpoints.length,
      });
    } catch (error) {
      throw new Error(
        `Failed to import configuration: ${(error as Error).message}`
      );
    }
  }

  // Private methods

  private async checkRateLimit(
    endpointId: string,
    rateLimit?: RateLimitConfig
  ): Promise<void> {
    if (!rateLimit) return;

    const currentTime = Date.now();
    const limiter = this.rateLimiters.get(endpointId) || {
      requests: 0,
      windowStart: currentTime,
      queue: [],
    };

    // Сбрасываем счетчик если окно истекло
    if (currentTime - limiter.windowStart >= rateLimit.window * 1000) {
      limiter.requests = 0;
      limiter.windowStart = currentTime;
    }

    if (limiter.requests >= rateLimit.requests) {
      if (rateLimit.queue && rateLimit.throttleDelay) {
        // Добавляем в очередь
        await new Promise((resolve) => {
          limiter.queue.push(resolve);
        });

        // Повторно проверяем после задержки
        await this.sleep(rateLimit.throttleDelay);
        await this.checkRateLimit(endpointId, rateLimit);
      } else {
        throw new Error("Rate limit exceeded");
      }
    }

    limiter.requests++;
    this.rateLimiters.set(endpointId, limiter);
  }

  private async executeRequest<T>(
    endpoint: APIEndpoint,
    options?: any
  ): Promise<APIResponse<T>> {
    const url = new URL(endpoint.url);

    // Добавляем query params
    if (endpoint.queryParams || options?.queryParams) {
      const params = { ...endpoint.queryParams, ...options?.queryParams };
      Object.entries(params).forEach(([key, value]) => {
        url.searchParams.append(key, String(value));
      });
    }

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...endpoint.headers,
      ...options?.headers,
    };

    // Добавляем аутентификацию
    this.addAuthHeaders(headers, endpoint.auth);

    const fetchOptions: RequestInit = {
      method: endpoint.method,
      headers,
      signal: AbortSignal.timeout(endpoint.timeout || 10000),
    };

    // Добавляем body для POST/PUT/PATCH
    if (endpoint.body || options?.body) {
      const body = options?.body || endpoint.body;
      fetchOptions.body = JSON.stringify(body);
    }

    const startTime = Date.now();

    const response = await fetch(url.toString(), fetchOptions);
    const endTime = Date.now();

    let data: T;
    const responseHeaders: Record<string, string> = {};

    // Копируем заголовки ответа
    response.headers.forEach((value, key) => {
      responseHeaders[key] = value;
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    // Парсим ответ в зависимости от content-type
    const contentType = responseHeaders["content-type"] || "";
    if (contentType.includes("application/json")) {
      data = await response.json();
    } else if (contentType.includes("text/")) {
      data = (await response.text()) as T;
    } else {
      data = (await response.arrayBuffer()) as T;
    }

    return {
      data,
      status: response.status,
      headers: responseHeaders,
      url: url.toString(),
      timing: {
        startTime,
        endTime,
        duration: endTime - startTime,
      },
      cached: false,
    };
  }

  private addAuthHeaders(
    headers: Record<string, string>,
    auth?: AuthConfig
  ): void {
    if (!auth || auth.type === "none") return;

    switch (auth.type) {
      case "bearer":
        if (auth.credentials.token) {
          headers["Authorization"] = `Bearer ${auth.credentials.token}`;
        }
        break;

      case "api-key":
        if (auth.credentials.apiKey) {
          headers["X-API-Key"] = auth.credentials.apiKey;
        }
        break;

      case "basic":
        if (auth.credentials.username && auth.credentials.password) {
          const credentials = btoa(
            `${auth.credentials.username}:${auth.credentials.password}`
          );
          headers["Authorization"] = `Basic ${credentials}`;
        }
        break;

      case "oauth2":
        if (auth.credentials.token) {
          headers["Authorization"] = `Bearer ${auth.credentials.token}`;
        }
        break;
    }
  }

  /**
   * OAuth2 Methods
   */

  /**
   * Инициировать OAuth2 flow для провайдера
   */
  async connectOAuth(provider: "github" | "gitlab" | "jira"): Promise<string> {
    try {
      const response = await fetch(`/api/oauth/${provider}/authorize`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to initiate OAuth: ${response.statusText}`);
      }

      const data = await response.json();
      return data.authorization_url;
    } catch (error) {
      this.emit("oauth-error", { provider, error: error as Error });
      throw error;
    }
  }

  /**
   * Обработать OAuth callback
   */
  async handleOAuthCallback(
    provider: "github" | "gitlab" | "jira",
    code: string,
    state: string
  ): Promise<void> {
    try {
      const response = await fetch(`/api/oauth/${provider}/callback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ code, state }),
      });

      if (!response.ok) {
        throw new Error(`OAuth callback failed: ${response.statusText}`);
      }

      const data = await response.json();
      this.emit("oauth-connected", { provider, data });
    } catch (error) {
      this.emit("oauth-error", { provider, error: error as Error });
      throw error;
    }
  }

  /**
   * Проверить статус OAuth подключения
   */
  async getOAuthStatus(provider: "github" | "gitlab" | "jira"): Promise<{
    connected: boolean;
    provider: string;
    expires_at?: string;
  }> {
    try {
      const response = await fetch(`/api/oauth/${provider}/status`);

      if (!response.ok) {
        throw new Error(`Failed to get OAuth status: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      this.emit("oauth-error", { provider, error: error as Error });
      throw error;
    }
  }

  /**
   * Отключить OAuth провайдера
   */
  async disconnectOAuth(provider: "github" | "gitlab" | "jira"): Promise<void> {
    try {
      const response = await fetch(`/api/oauth/${provider}/disconnect`, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error(`Failed to disconnect OAuth: ${response.statusText}`);
      }

      this.emit("oauth-disconnected", { provider });
    } catch (error) {
      this.emit("oauth-error", { provider, error: error as Error });
      throw error;
    }
  }

  /**
   * Получить список доступных OAuth провайдеров
   */
  async getOAuthProviders(): Promise<{
    providers: Record<
      string,
      {
        name: string;
        configured: boolean;
        scopes: string;
      }
    >;
  }> {
    try {
      const response = await fetch("/api/oauth/providers");

      if (!response.ok) {
        throw new Error(
          `Failed to get OAuth providers: ${response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      this.emit("oauth-error", { error: error as Error });
      throw error;
    }
  }

  private updateMetrics(
    endpointId: string,
    startTime: number,
    cached: boolean,
    success?: boolean
  ): void {
    const metrics = this.metrics.get(endpointId);
    if (!metrics) return;

    const duration = Date.now() - startTime;

    metrics.totalRequests++;
    metrics.lastRequest = new Date();

    if (cached) {
      // Обновляем cache hit rate
      const hitRateChange = (1 - metrics.cacheHitRate) / metrics.totalRequests;
      metrics.cacheHitRate += hitRateChange;
    }

    if (success !== undefined) {
      if (success) {
        metrics.successfulRequests++;
        // Обновляем average response time
        metrics.averageResponseTime =
          (metrics.averageResponseTime * (metrics.totalRequests - 1) +
            duration) /
          metrics.totalRequests;
      } else {
        metrics.failedRequests++;
      }

      // Обновляем error rate
      metrics.errorRate =
        (metrics.failedRequests / metrics.totalRequests) * 100;
    }
  }

  private getCachedResponse(endpointId: string): APIResponse | null {
    const cached = this.cache.get(endpointId);
    if (!cached) return null;

    if (Date.now() > cached.expiresAt) {
      this.cache.delete(endpointId);
      return null;
    }

    return { ...cached.data, cached: true };
  }

  private cacheResponse(
    endpointId: string,
    response: APIResponse,
    ttl: number
  ): void {
    const expiresAt = Date.now() + ttl * 1000;
    this.cache.set(endpointId, { data: response, expiresAt });
  }

  private async retryRequest<T>(
    endpointId: string,
    policy: RetryPolicy,
    options?: any,
    attempt: number = 1
  ): Promise<APIResponse<T>> {
    if (attempt > policy.maxAttempts) {
      throw new Error(`Max retry attempts (${policy.maxAttempts}) exceeded`);
    }

    // Вычисляем задержку
    let delay = policy.baseDelay;
    if (policy.backoffStrategy === "exponential") {
      delay = policy.baseDelay * Math.pow(2, attempt - 1);
    } else if (policy.backoffStrategy === "linear") {
      delay = policy.baseDelay * attempt;
    }

    if (policy.maxDelay && delay > policy.maxDelay) {
      delay = policy.maxDelay;
    }

    await this.sleep(delay);

    try {
      return await this.request<T>(endpointId, options);
    } catch (error) {
      const statusCode = (error as any).status;

      // Проверяем, можно ли повторить запрос для этого status code
      if (policy.retryableStatusCodes?.includes(statusCode) || !statusCode) {
        return this.retryRequest<T>(endpointId, policy, options, attempt + 1);
      }

      throw error;
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  private setupPeriodicCleanup(): void {
    // Очищаем истекший кэш каждые 5 минут
    setInterval(() => {
      const now = Date.now();
      for (const [key, cached] of this.cache.entries()) {
        if (now > cached.expiresAt) {
          this.cache.delete(key);
        }
      }
    }, 5 * 60 * 1000);

    // Сбрасываем rate limiters каждые 10 минут
    setInterval(() => {
      this.rateLimiters.clear();
    }, 10 * 60 * 1000);
  }
}

export default APIIntegrationService;
