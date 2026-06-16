// EventEmitter polyfill for browser compatibility
import { EventEmitter } from "events";
import APIIntegrationService from "./api-integration-service";

export interface GatewayRoute {
  id: string;
  name: string;
  path: string;
  methods: string[];
  target: RouteTarget;
  authentication?: AuthenticationRule;
  rateLimit?: RateLimitRule;
  cache?: CacheRule;
  transformation?: TransformationRule;
  monitoring?: MonitoringRule;
  priority: number;
  enabled: boolean;
}

export interface RouteTarget {
  type: "api-endpoint" | "static-content" | "proxy" | "function";
  config: {
    endpointId?: string;
    url?: string;
    headers?: Record<string, string>;
    method?: string;
    functionName?: string;
  };
}

export interface AuthenticationRule {
  required: boolean;
  type: "oauth2" | "api-key" | "jwt" | "custom";
  scopes?: string[];
  roles?: string[];
  customValidator?: string;
}

export interface RateLimitRule {
  requests: number;
  window: number; // в секундах
  scope: "global" | "ip" | "user" | "route";
  whitelist?: string[];
  blacklist?: string[];
}

export interface CacheRule {
  enabled: boolean;
  ttl: number;
  varyByHeaders?: string[];
  varyByQuery?: string[];
  invalidateOn?: string[];
}

export interface TransformationRule {
  request?: {
    headers?: Record<string, string>;
    body?: string; // JavaScript function
    query?: Record<string, any>;
  };
  response?: {
    headers?: Record<string, string>;
    body?: string; // JavaScript function
    status?: number;
  };
}

export interface MonitoringRule {
  enabled: boolean;
  metrics: string[];
  alerts?: AlertRule[];
}

export interface AlertRule {
  condition: string; // JavaScript expression
  threshold: number;
  duration: number;
  action: "email" | "webhook" | "log";
}

export interface GatewayMetrics {
  totalRequests: number;
  successfulRequests: number;
  failedRequests: number;
  averageResponseTime: number;
  routeMetrics: Map<string, RouteMetrics>;
  rateLimitHits: number;
  cacheHitRate: number;
  authFailures: number;
  lastRequest?: Date;
}

export interface RouteMetrics {
  routeId: string;
  requests: number;
  successes: number;
  failures: number;
  averageResponseTime: number;
  lastRequest?: Date;
  rateLimitHits: number;
  cacheHits: number;
}

export interface JWTPayload {
  sub: string; // userId
  roles?: string[];
  scopes?: string[];
  exp: number;
  iat: number;
  [key: string]: any;
}

export interface AuthResult {
  success: boolean;
  userId?: string;
  userRoles?: string[];
  scopes?: string[];
  error?: string;
}

export interface GatewayRequest {
  method: string;
  path: string;
  headers: Record<string, string>;
  query: Record<string, string>;
  body?: any;
  userId?: string;
  userRoles?: string[];
  scopes?: string[];
  ip: string;
  userAgent: string;
}

export interface GatewayResponse {
  status: number;
  headers: Record<string, string>;
  body: any;
  cached: boolean;
  routeId?: string;
}

export class APIGatewayService extends EventEmitter {
  private routes: Map<string, GatewayRoute> = new Map();
  private routeIndex: Map<string, GatewayRoute> = new Map(); // path -> route
  private metrics: GatewayMetrics;
  private rateLimiters: Map<string, RateLimiter> = new Map();
  private cache: Map<string, CacheEntry> = new Map();
  private apiService: APIIntegrationService;

  constructor(apiService?: APIIntegrationService) {
    super();
    this.apiService = apiService || new APIIntegrationService();
    this.metrics = this.initializeMetrics();
    this.loadDefaultRoutes();
  }

  /**
   * Регистрирует новый маршрут
   */
  async registerRoute(route: GatewayRoute): Promise<void> {
    if (this.routes.has(route.id)) {
      throw new Error(`Route with id '${route.id}' already exists`);
    }

    // Проверяем уникальность пути для методов
    for (const method of route.methods) {
      const routeKey = `${method}:${route.path}`;
      if (this.routeIndex.has(routeKey)) {
        throw new Error(`Route for ${method} ${route.path} already exists`);
      }
      this.routeIndex.set(routeKey, route);
    }

    this.routes.set(route.id, route);
    this.initializeRouteMetrics(route.id);

    this.emit("route-registered", { routeId: route.id, route });
  }

  /**
   * Удаляет маршрут
   */
  async unregisterRoute(routeId: string): Promise<void> {
    const route = this.routes.get(routeId);
    if (!route) {
      throw new Error(`Route with id '${routeId}' not found`);
    }

    // Удаляем из индексов
    for (const method of route.methods) {
      const routeKey = `${method}:${route.path}`;
      this.routeIndex.delete(routeKey);
    }

    this.routes.delete(routeId);
    this.metrics.routeMetrics.delete(routeId);

    this.emit("route-unregistered", { routeId });
  }

  /**
   * Обновляет маршрут
   */
  async updateRoute(
    routeId: string,
    updates: Partial<GatewayRoute>
  ): Promise<void> {
    const route = this.routes.get(routeId);
    if (!route) {
      throw new Error(`Route with id '${routeId}' not found`);
    }

    // Сохраняем старые данные для сравнения
    const oldPath = route.path;
    const oldMethods = [...route.methods];

    // Применяем обновления
    const updatedRoute = { ...route, ...updates };
    this.routes.set(routeId, updatedRoute);

    // Обновляем индексы если изменились путь или методы
    if (updates.path !== undefined || updates.methods !== undefined) {
      // Удаляем старые индексы
      for (const method of oldMethods) {
        const routeKey = `${method}:${oldPath}`;
        this.routeIndex.delete(routeKey);
      }

      // Добавляем новые индексы
      for (const method of updatedRoute.methods) {
        const routeKey = `${method}:${updatedRoute.path}`;
        this.routeIndex.set(routeKey, updatedRoute);
      }
    }

    this.emit("route-updated", { routeId, updates });
  }

  /**
   * Обрабатывает входящий запрос
   */
  async handleRequest(request: GatewayRequest): Promise<GatewayResponse> {
    const startTime = Date.now();

    try {
      // Находим подходящий маршрут
      const route = this.findRoute(request.method, request.path);
      if (!route) {
        return this.createErrorResponse(404, "Route not found");
      }

      if (!route.enabled) {
        return this.createErrorResponse(503, "Route disabled");
      }

      // Проверяем аутентификацию
      if (route.authentication?.required) {
        const authResult = await this.authenticate(
          request,
          route.authentication
        );
        if (!authResult.success) {
          this.metrics.authFailures++;
          return this.createErrorResponse(
            401,
            authResult.error || "Authentication failed"
          );
        }
        request.userId = authResult.userId;
        request.userRoles = authResult.userRoles;
      }

      // Проверяем rate limiting
      await this.checkRateLimit(request, route);

      // Проверяем кэш
      const cacheKey = this.generateCacheKey(request, route);
      if (route.cache?.enabled) {
        const cachedResponse = this.getCachedResponse(cacheKey);
        if (cachedResponse) {
          this.updateMetrics(route.id, startTime, true, true);
          return cachedResponse;
        }
      }

      // Применяем трансформацию запроса
      const transformedRequest = await this.transformRequest(
        request,
        route.transformation?.request
      );

      // Выполняем маршрутизацию
      const targetResponse = await this.routeToTarget(
        transformedRequest,
        route
      );

      // Применяем трансформацию ответа
      const transformedResponse = await this.transformResponse(
        targetResponse,
        route.transformation?.response
      );

      // Кэшируем ответ если нужно
      if (
        route.cache?.enabled &&
        transformedResponse.status >= 200 &&
        transformedResponse.status < 300
      ) {
        this.cacheResponse(cacheKey, transformedResponse, route.cache.ttl);
      }

      // Добавляем информацию о маршруте
      transformedResponse.routeId = route.id;

      this.updateMetrics(route.id, startTime, false, true);
      this.emit("request-success", {
        routeId: route.id,
        responseTime: Date.now() - startTime,
      });

      return transformedResponse;
    } catch (error) {
      this.updateMetrics("unknown", startTime, false, false);
      this.emit("request-error", { error: error as Error, request });

      return this.createErrorResponse(
        500,
        error instanceof Error ? error.message : "Internal server error"
      );
    }
  }

  /**
   * Получает метрики gateway'а
   */
  getMetrics(): GatewayMetrics {
    return { ...this.metrics };
  }

  /**
   * Получает метрики маршрута
   */
  getRouteMetrics(routeId: string): RouteMetrics | null {
    return this.metrics.routeMetrics.get(routeId) || null;
  }

  /**
   * Получает все маршруты
   */
  getRoutes(): GatewayRoute[] {
    return Array.from(this.routes.values());
  }

  /**
   * Получает маршрут по ID
   */
  getRoute(routeId: string): GatewayRoute | null {
    return this.routes.get(routeId) || null;
  }

  /**
   * Очищает кэш
   */
  clearCache(routeId?: string): void {
    if (routeId) {
      // Удаляем кэш для конкретного маршрута
      for (const [key, entry] of this.cache.entries()) {
        if (entry.routeId === routeId) {
          this.cache.delete(key);
        }
      }
    } else {
      this.cache.clear();
    }
    this.emit("cache-cleared", { routeId });
  }

  /**
   * Получает статус health check
   */
  async healthCheck(): Promise<{
    status: "healthy" | "degraded" | "unhealthy";
    routes: Map<string, { status: string; responseTime: number }>;
    metrics: GatewayMetrics;
  }> {
    const routeStatuses = new Map();
    let totalResponseTime = 0;
    let healthyRoutes = 0;

    for (const route of this.routes.values()) {
      if (!route.enabled) {
        routeStatuses.set(route.id, { status: "disabled", responseTime: 0 });
        continue;
      }

      try {
        const testResponse = await this.healthCheckRoute(route);
        routeStatuses.set(route.id, testResponse);

        if (testResponse.status === "healthy") {
          healthyRoutes++;
          totalResponseTime += testResponse.responseTime;
        }
      } catch (error) {
        routeStatuses.set(route.id, {
          status: "unhealthy" as const,
          responseTime: 0,
        });
      }
    }

    const averageResponseTime =
      healthyRoutes > 0 ? totalResponseTime / healthyRoutes : 0;
    let overallStatus: "healthy" | "degraded" | "unhealthy";

    if (healthyRoutes === 0) {
      overallStatus = "unhealthy";
    } else if (healthyRoutes === this.routes.size) {
      overallStatus = averageResponseTime < 1000 ? "healthy" : "degraded";
    } else {
      overallStatus = "degraded";
    }

    return {
      status: overallStatus,
      routes: routeStatuses,
      metrics: this.metrics,
    };
  }

  /**
   * Экспортирует конфигурацию маршрутов
   */
  exportRoutes(): string {
    const config = {
      routes: this.getRoutes(),
      exportDate: new Date().toISOString(),
    };
    return JSON.stringify(config, null, 2);
  }

  /**
   * Импортирует конфигурацию маршрутов
   */
  async importRoutes(configJson: string): Promise<void> {
    try {
      const config = JSON.parse(configJson);

      if (!config.routes || !Array.isArray(config.routes)) {
        throw new Error("Invalid routes configuration format");
      }

      // Очищаем существующие маршруты
      this.routes.clear();
      this.routeIndex.clear();
      this.metrics.routeMetrics.clear();

      // Импортируем новые
      for (const route of config.routes) {
        await this.registerRoute(route);
      }

      this.emit("routes-imported", {
        importedRoutes: config.routes.length,
      });
    } catch (error) {
      throw new Error(
        `Failed to import routes configuration: ${(error as Error).message}`
      );
    }
  }

  // Private methods

  private findRoute(method: string, path: string): GatewayRoute | null {
    // Ищем точное совпадение
    let route = this.routeIndex.get(`${method}:${path}`);
    if (route) return route;

    // Ищем по паттерну с wildcards
    for (const candidateRoute of this.routes.values()) {
      if (
        candidateRoute.methods.includes(method) &&
        this.matchPath(path, candidateRoute.path)
      ) {
        return candidateRoute;
      }
    }

    return null;
  }

  private matchPath(path: string, pattern: string): boolean {
    // Простая реализация wildcard matching
    // TODO: Использовать более продвинутый path-to-regexp
    const regex = new RegExp(
      "^" + pattern.replace(/\*/g, ".*").replace(/\?/g, ".") + "$"
    );
    return regex.test(path);
  }

  private async authenticate(
    request: GatewayRequest,
    rule: AuthenticationRule
  ): Promise<AuthResult> {
    const authHeader = request.headers["authorization"];

    if (!authHeader) {
      return { success: false, error: "No authorization header" };
    }

    let authResult: AuthResult;

    // Выбираем метод аутентификации
    switch (rule.type) {
      case "jwt":
        authResult = await this.validateJWT(authHeader);
        break;

      case "oauth2":
        authResult = await this.validateOAuth2(authHeader, rule.scopes);
        break;

      case "api-key":
        authResult = await this.validateAPIKey(authHeader);
        break;

      case "custom":
        authResult = await this.validateCustom(
          request,
          rule.customValidator || ""
        );
        break;

      default:
        return {
          success: false,
          error: `Unknown authentication type: ${rule.type}`,
        };
    }

    if (!authResult.success) {
      return authResult;
    }

    // Проверяем роли если нужно
    if (rule.roles && rule.roles.length > 0) {
      const hasRole = rule.roles.some((role) =>
        authResult.userRoles?.includes(role)
      );
      if (!hasRole) {
        return {
          success: false,
          error: "Insufficient permissions - missing required role",
        };
      }
    }

    // Проверяем scopes для OAuth2
    if (rule.scopes && rule.scopes.length > 0) {
      const hasScope = rule.scopes.every((scope) =>
        authResult.scopes?.includes(scope)
      );
      if (!hasScope) {
        return {
          success: false,
          error: "Insufficient permissions - missing required scope",
        };
      }
    }

    return authResult;
  }

  /**
   * Валидация JWT токена
   */
  private async validateJWT(authHeader: string): Promise<AuthResult> {
    try {
      // Извлекаем токен из заголовка
      const token = authHeader.replace(/^Bearer\s+/i, "");

      if (!token) {
        return { success: false, error: "Invalid authorization header format" };
      }

      // Простая валидация JWT (без проверки подписи для frontend)
      // В production должна быть проверка через backend
      const parts = token.split(".");
      if (parts.length !== 3) {
        return { success: false, error: "Invalid JWT format" };
      }

      // Декодируем payload
      const payload = JSON.parse(atob(parts[1])) as JWTPayload;

      // Проверяем expiration
      if (payload.exp && payload.exp < Date.now() / 1000) {
        return { success: false, error: "Token expired" };
      }

      return {
        success: true,
        userId: payload.sub,
        userRoles: payload.roles || [],
        scopes: payload.scopes || [],
      };
    } catch (error) {
      return {
        success: false,
        error: `JWT validation failed: ${(error as Error).message}`,
      };
    }
  }

  /**
   * Валидация OAuth2 токена
   */
  private async validateOAuth2(
    authHeader: string,
    requiredScopes?: string[]
  ): Promise<AuthResult> {
    try {
      const token = authHeader.replace(/^Bearer\s+/i, "");

      if (!token) {
        return { success: false, error: "Invalid authorization header format" };
      }

      // Проверяем токен через backend API
      // В production это должен быть вызов к OAuth introspection endpoint
      const response = await fetch("/api/oauth/introspect", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ token }),
      });

      if (!response.ok) {
        return { success: false, error: "OAuth token validation failed" };
      }

      const data = await response.json();

      if (!data.active) {
        return { success: false, error: "Token is not active" };
      }

      return {
        success: true,
        userId: data.sub || data.user_id,
        userRoles: data.roles || [],
        scopes: data.scope ? data.scope.split(" ") : [],
      };
    } catch (error) {
      return {
        success: false,
        error: `OAuth2 validation failed: ${(error as Error).message}`,
      };
    }
  }

  /**
   * Валидация API ключа
   */
  private async validateAPIKey(authHeader: string): Promise<AuthResult> {
    try {
      // Извлекаем API ключ из заголовка
      const apiKey = authHeader
        .replace(/^ApiKey\s+/i, "")
        .replace(/^Bearer\s+/i, "");

      if (!apiKey) {
        return { success: false, error: "Invalid API key format" };
      }

      // Проверяем ключ через backend
      const response = await fetch("/api/auth/validate-api-key", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ apiKey }),
      });

      if (!response.ok) {
        return { success: false, error: "API key validation failed" };
      }

      const data = await response.json();

      if (!data.valid) {
        return { success: false, error: "Invalid API key" };
      }

      return {
        success: true,
        userId: data.userId,
        userRoles: data.roles || [],
        scopes: data.scopes || [],
      };
    } catch (error) {
      return {
        success: false,
        error: `API key validation failed: ${(error as Error).message}`,
      };
    }
  }

  /**
   * Кастомная валидация
   */
  private async validateCustom(
    request: GatewayRequest,
    validator: string
  ): Promise<AuthResult> {
    try {
      // Выполняем кастомную функцию валидации
      // ВНИМАНИЕ: Это потенциально небезопасно, использовать только для доверенного кода
      const validatorFunction = new Function("request", validator);
      const result = await validatorFunction(request);

      if (typeof result === "object" && result.success !== undefined) {
        return result as AuthResult;
      }

      return {
        success: false,
        error: "Custom validator returned invalid result",
      };
    } catch (error) {
      return {
        success: false,
        error: `Custom validation failed: ${(error as Error).message}`,
      };
    }
  }

  private async checkRateLimit(
    request: GatewayRequest,
    route: GatewayRoute
  ): Promise<void> {
    if (!route.rateLimit) return;

    const limiterKey = this.generateRateLimitKey(request, route.rateLimit);
    const limiter =
      this.rateLimiters.get(limiterKey) ||
      this.createRateLimiter(route.rateLimit);

    const now = Date.now();

    if (now - limiter.windowStart >= route.rateLimit.window * 1000) {
      // Сброс окна
      limiter.requests = 0;
      limiter.windowStart = now;
    }

    if (limiter.requests >= route.rateLimit.requests) {
      this.metrics.rateLimitHits++;
      this.emit("rate-limit-hit", { routeId: route.id, request });
      throw new Error("Rate limit exceeded");
    }

    limiter.requests++;
    this.rateLimiters.set(limiterKey, limiter);
  }

  private async transformRequest(
    request: GatewayRequest,
    transformation?: TransformationRule["request"]
  ): Promise<GatewayRequest> {
    if (!transformation) return request;

    const transformed = { ...request };

    // Трансформируем заголовки
    if (transformation.headers) {
      transformed.headers = {
        ...transformed.headers,
        ...transformation.headers,
      };
    }

    // Трансформируем query params
    if (transformation.query) {
      transformed.query = { ...transformed.query, ...transformation.query };
    }

    // Трансформируем body через функцию
    if (transformation.body) {
      try {
        const transformFunction = new Function("request", transformation.body);
        transformed.body = transformFunction(transformed);
      } catch (error) {
        console.error("Request transformation failed:", error);
      }
    }

    return transformed;
  }

  private async transformResponse(
    response: GatewayResponse,
    transformation?: TransformationRule["response"]
  ): Promise<GatewayResponse> {
    if (!transformation) return response;

    const transformed = { ...response };

    // Трансформируем заголовки
    if (transformation.headers) {
      transformed.headers = {
        ...transformed.headers,
        ...transformation.headers,
      };
    }

    // Трансформируем статус
    if (transformation.status) {
      transformed.status = transformation.status;
    }

    // Трансформируем body через функцию
    if (transformation.body) {
      try {
        const transformFunction = new Function("response", transformation.body);
        transformed.body = transformFunction(transformed);
      } catch (error) {
        console.error("Response transformation failed:", error);
      }
    }

    return transformed;
  }

  private async routeToTarget(
    request: GatewayRequest,
    route: GatewayRoute
  ): Promise<GatewayResponse> {
    const target = route.target;

    switch (target.type) {
      case "api-endpoint":
        if (!target.config.endpointId) {
          throw new Error("API endpoint ID not specified");
        }
        return this.routeToAPIEndpoint(request, target.config.endpointId);

      case "static-content":
        return this.routeToStaticContent(request, target.config.url || "");

      case "proxy":
        return this.routeToProxy(request, target.config.url || "");

      case "function":
        return this.routeToFunction(request, target.config.functionName || "");

      default:
        throw new Error(`Unknown target type: ${target.type}`);
    }
  }

  private async routeToAPIEndpoint(
    request: GatewayRequest,
    endpointId: string
  ): Promise<GatewayResponse> {
    try {
      const response = await this.apiService.request(endpointId, {
        headers: request.headers,
        queryParams: request.query,
        body: request.body,
      });

      return {
        status: response.status,
        headers: response.headers || {},
        body: response.data,
        cached: response.cached || false,
      };
    } catch (error) {
      throw new Error(
        `API endpoint request failed: ${(error as Error).message}`
      );
    }
  }

  private async routeToStaticContent(
    request: GatewayRequest,
    url: string
  ): Promise<GatewayResponse> {
    // Простая реализация статического контента
    return {
      status: 200,
      headers: { "Content-Type": "text/html" },
      body: `<h1>Static Content</h1><p>URL: ${url}</p>`,
      cached: false,
    };
  }

  private async routeToProxy(
    request: GatewayRequest,
    url: string
  ): Promise<GatewayResponse> {
    try {
      const proxyUrl = new URL(url);
      const proxyRequest = new Request(proxyUrl.toString(), {
        method: request.method,
        headers: request.headers,
        body: request.body ? JSON.stringify(request.body) : undefined,
      });

      const response = await fetch(proxyRequest);
      const responseText = await response.text();

      return {
        status: response.status,
        headers: Object.fromEntries(response.headers.entries()),
        body: responseText,
        cached: false,
      };
    } catch (error) {
      throw new Error(`Proxy request failed: ${(error as Error).message}`);
    }
  }

  private async routeToFunction(
    request: GatewayRequest,
    functionName: string
  ): Promise<GatewayResponse> {
    // TODO: Реализовать выполнение serverless функций
    return {
      status: 200,
      headers: { "Content-Type": "application/json" },
      body: { message: `Function ${functionName} executed`, request },
      cached: false,
    };
  }

  private generateCacheKey(
    request: GatewayRequest,
    route: GatewayRoute
  ): string {
    let key = `${route.id}:${request.method}:${request.path}`;

    // Добавляем varyByHeaders
    if (route.cache?.varyByHeaders) {
      for (const header of route.cache.varyByHeaders) {
        if (request.headers[header]) {
          key += `:${header}=${request.headers[header]}`;
        }
      }
    }

    // Добавляем varyByQuery
    if (route.cache?.varyByQuery) {
      for (const param of route.cache.varyByQuery) {
        if (request.query[param]) {
          key += `:${param}=${request.query[param]}`;
        }
      }
    }

    return key;
  }

  private generateRateLimitKey(
    request: GatewayRequest,
    rule: RateLimitRule
  ): string {
    switch (rule.scope) {
      case "global":
        return "global";
      case "ip":
        return `ip:${request.ip}`;
      case "user":
        return `user:${request.userId || "anonymous"}`;
      case "route":
        return `route:${request.path}`;
      default:
        return "default";
    }
  }

  private getCachedResponse(cacheKey: string): GatewayResponse | null {
    const cached = this.cache.get(cacheKey);
    if (!cached) return null;

    if (Date.now() > cached.expiresAt) {
      this.cache.delete(cacheKey);
      return null;
    }

    return { ...cached.response, cached: true };
  }

  private cacheResponse(
    cacheKey: string,
    response: GatewayResponse,
    ttl: number
  ): void {
    const expiresAt = Date.now() + ttl * 1000;
    this.cache.set(cacheKey, {
      response,
      expiresAt,
      routeId: response.routeId,
    });
  }

  private createRateLimiter(rule: RateLimitRule) {
    return {
      requests: 0,
      windowStart: Date.now(),
      queue: [],
    };
  }

  private updateMetrics(
    routeId: string,
    startTime: number,
    cached: boolean,
    success: boolean
  ): void {
    const duration = Date.now() - startTime;

    this.metrics.totalRequests++;
    this.metrics.lastRequest = new Date();

    if (success) {
      this.metrics.successfulRequests++;
      this.metrics.averageResponseTime =
        (this.metrics.averageResponseTime * (this.metrics.totalRequests - 1) +
          duration) /
        this.metrics.totalRequests;
    } else {
      this.metrics.failedRequests++;
    }

    if (cached) {
      this.metrics.cacheHitRate =
        (this.metrics.cacheHitRate * (this.metrics.totalRequests - 1) + 1) /
        this.metrics.totalRequests;
    }

    // Обновляем метрики маршрута
    if (routeId !== "unknown") {
      const routeMetrics = this.metrics.routeMetrics.get(routeId);
      if (routeMetrics) {
        routeMetrics.requests++;
        routeMetrics.lastRequest = new Date();

        if (success) {
          routeMetrics.successes++;
          routeMetrics.averageResponseTime =
            (routeMetrics.averageResponseTime * (routeMetrics.requests - 1) +
              duration) /
            routeMetrics.requests;
        } else {
          routeMetrics.failures++;
        }

        if (cached) {
          routeMetrics.cacheHits++;
        }
      }
    }
  }

  private initializeMetrics(): GatewayMetrics {
    return {
      totalRequests: 0,
      successfulRequests: 0,
      failedRequests: 0,
      averageResponseTime: 0,
      routeMetrics: new Map(),
      rateLimitHits: 0,
      cacheHitRate: 0,
      authFailures: 0,
    };
  }

  private initializeRouteMetrics(routeId: string): void {
    this.metrics.routeMetrics.set(routeId, {
      routeId,
      requests: 0,
      successes: 0,
      failures: 0,
      averageResponseTime: 0,
      rateLimitHits: 0,
      cacheHits: 0,
    });
  }

  private async healthCheckRoute(
    route: GatewayRoute
  ): Promise<{
    status: "healthy" | "degraded" | "unhealthy";
    responseTime: number;
  }> {
    const startTime = Date.now();

    try {
      // Создаем тестовый запрос
      const testRequest: GatewayRequest = {
        method: "GET",
        path: route.path,
        headers: {},
        query: {},
        ip: "127.0.0.1",
        userAgent: "Gateway-HealthCheck",
      };

      const response = await this.handleRequest(testRequest);
      const responseTime = Date.now() - startTime;

      let status: "healthy" | "degraded" | "unhealthy";
      if (response.status >= 200 && response.status < 300) {
        status = responseTime < 1000 ? "healthy" : "degraded";
      } else {
        status = "unhealthy";
      }

      return { status, responseTime };
    } catch (error) {
      return {
        status: "error",
        responseTime: Date.now() - startTime,
      };
    }
  }

  private createErrorResponse(
    status: number,
    message: string
  ): GatewayResponse {
    return {
      status,
      headers: { "Content-Type": "application/json" },
      body: { error: message },
      cached: false,
    };
  }

  private loadDefaultRoutes(): void {
    // Загружаем стандартные маршруты для API gateway
    // TODO: Добавить более конкретные маршруты
  }
}

interface RateLimiter {
  requests: number;
  windowStart: number;
  queue: Function[];
}

interface CacheEntry {
  response: GatewayResponse;
  expiresAt: number;
  routeId?: string;
}

export default APIGatewayService;
