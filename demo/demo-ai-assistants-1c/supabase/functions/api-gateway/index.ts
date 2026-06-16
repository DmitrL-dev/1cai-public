// API Gateway Edge Function для микросервисной архитектуры
// Основные функции: маршрутизация, балансировка нагрузки, аутентификация, rate limiting, кэширование

import { corsMiddleware } from './middleware/cors.ts';
import { validationMiddleware, createValidationErrorResponse } from './middleware/validation.ts';
import { loggingMiddleware, logRequestCompletion, createMetricsEndpoint, createLogsEndpoint } from './middleware/logging.ts';
import { securityMiddleware, createSecureResponse } from './middleware/security.ts';
import { authManager, createAuthError, createAuthzError } from './utils/auth.ts';
import { rateLimiter, createRateLimitError } from './utils/rateLimit.ts';
import { cacheManager } from './utils/cache.ts';
import { circuitBreakerManager } from './utils/circuitBreaker.ts';
import { getServiceConfigByPath, matchRoutingRule, isPublicEndpoint, gatewayConfig } from './config.ts';

// Общие endpoints для публичного доступа
const PUBLIC_ENDPOINTS = ['/health', '/status', '/metrics', '/docs', '/openapi.json'];

Deno.serve(async (req) => {
  const startTime = Date.now();
  const requestId = crypto.randomUUID();

  try {
    // 1. CORS Middleware - обрабатываем preflight запросы
    const corsResponse = corsMiddleware.preflight(req);
    if (corsResponse) {
      return corsResponse;
    }

    // 2. Logging Middleware - начинаем логирование запроса
    loggingMiddleware(req, requestId);

    // Парсим URL
    const url = new URL(req.url);
    const path = url.pathname;
    const method = req.method;
    const apiVersion = url.searchParams.get('v') || 'v1';

    // Специальные endpoints для мониторинга и управления
    if (path === '/metrics') {
      return securityMiddleware(createMetricsEndpoint());
    }
    
    if (path === '/logs') {
      const logsResponse = createLogsEndpoint();
      return securityMiddleware(logsResponse);
    }
    
    if (path === '/status') {
      const statusResponse = createSecureResponse(JSON.stringify({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        uptime: Date.now() - startTime,
        services: circuitBreakerManager.getAllStats()
      }));
      return securityMiddleware(statusResponse);
    }

    // 3. Request Validation Middleware
    const validationResult = validationMiddleware(req, path, method);
    if (!validationResult.valid) {
      const errorResponse = createValidationErrorResponse(validationResult, requestId);
      return securityMiddleware(errorResponse);
    }

    // 4. Security Headers Middleware
    const urlObj = new URL(req.url);

    // 5. Authentication & Authorization
    const authResult = await authManager.authenticate(req);
    if (!authResult.success) {
      const errorResponse = createAuthError(authResult.error || 'Authentication failed', authResult.code);
      logRequestCompletion(requestId, 401, Date.now() - startTime, undefined, false, authResult.error);
      return securityMiddleware(errorResponse);
    }

    // Проверяем, является ли endpoint публичным
    if (!isPublicEndpoint(path) && authResult.user?.id === 'anonymous') {
      const errorResponse = createAuthError('Authentication required for this endpoint');
      logRequestCompletion(requestId, 401, Date.now() - startTime, undefined, false, 'Authentication required');
      return securityMiddleware(errorResponse);
    }

    // 6. Rate Limiting
    const rateLimitResult = await rateLimiter.checkLimit(req);
    if (!rateLimitResult.allowed) {
      const errorResponse = createRateLimitError(rateLimitResult);
      logRequestCompletion(requestId, 429, Date.now() - startTime, undefined, false, 'Rate limit exceeded');
      return securityMiddleware(errorResponse);
    }

    // 7. Authorization - проверяем права доступа
    if (!isPublicEndpoint(path)) {
      const routingRule = matchRoutingRule(path, method);
      if (routingRule?.auth?.required && authResult.user) {
        const hasPermission = await authManager.authorize(authResult.user, {
          resource: 'api',
          action: method.toLowerCase(),
          context: { path, service: routingRule.service }
        });
        
        if (!hasPermission) {
          const errorResponse = createAuthzError('Insufficient permissions');
          logRequestCompletion(requestId, 403, Date.now() - startTime, routingRule.service, false, 'Insufficient permissions');
          return securityMiddleware(errorResponse);
        }
      }
    }

    // 8. Request Caching - проверяем кэш
    const cachedResponse = cacheManager.getCachedResponse(req);
    if (cachedResponse) {
      // Добавляем cache hit headers
      const hitResponse = new Response(cachedResponse.body, {
        status: cachedResponse.status,
        headers: {
          ...Object.fromEntries(new Headers(cachedResponse.headers).entries()),
          ...cacheManager.createCacheHitHeaders(),
          'X-Request-ID': requestId,
          'X-Response-Time': `${Date.now() - startTime}ms`
        }
      });
      
      logRequestCompletion(requestId, cachedResponse.status, Date.now() - startTime, undefined, true);
      return securityMiddleware(hitResponse);
    }

    // 9. Service Discovery & Load Balancing
    const serviceConfig = getServiceConfigByPath(path);
    if (!serviceConfig) {
      const errorResponse = createSecureResponse(JSON.stringify({
        error: {
          code: 'SERVICE_NOT_FOUND',
          message: `No service found for path: ${path}`,
          requestId
        }
      }), 404);
      
      logRequestCompletion(requestId, 404, Date.now() - startTime, undefined, false, 'Service not found');
      return securityMiddleware(errorResponse);
    }

    // 10. Load Balancing - выбираем healthy инстанс
    const targetService = selectHealthyInstance(serviceConfig);
    if (!targetService) {
      const errorResponse = createSecureResponse(JSON.stringify({
        error: {
          code: 'SERVICE_UNAVAILABLE',
          message: 'All service instances are unavailable',
          requestId
        }
      }), 503);
      
      logRequestCompletion(requestId, 503, Date.now() - startTime, serviceConfig.name, false, 'All instances unavailable');
      return securityMiddleware(errorResponse);
    }

    // 11. Request/Response Transformation - подготовка запроса к сервису
    const transformedRequest = await transformRequest(req, serviceConfig, authResult);

    // 12. Route to Service с Circuit Breaker
    let serviceResponse: Response;
    try {
      serviceResponse = await circuitBreakerManager.execute(
        serviceConfig.name,
        async () => {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), serviceConfig.timeout);
          
          try {
            const response = await fetch(targetService.url, {
              method: transformedRequest.method,
              headers: transformedRequest.headers,
              body: transformedRequest.body,
              signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            return response;
          } catch (error) {
            clearTimeout(timeoutId);
            throw error;
          }
        },
        {
          failureThreshold: serviceConfig.circuitBreaker?.failureThreshold || gatewayConfig.circuitBreakerDefaults.failureThreshold,
          timeout: serviceConfig.circuitBreaker?.timeout || gatewayConfig.circuitBreakerDefaults.timeout,
          resetTimeout: serviceConfig.circuitBreaker?.resetTimeout || gatewayConfig.circuitBreakerDefaults.resetTimeout
        }
      );
    } catch (error) {
      // Circuit breaker сработал или сервис недоступен
      const errorResponse = createSecureResponse(JSON.stringify({
        error: {
          code: 'SERVICE_UNAVAILABLE',
          message: `Service ${serviceConfig.name} is currently unavailable`,
          requestId,
          details: { originalError: error.message }
        }
      }), 503);
      
      logRequestCompletion(requestId, 503, Date.now() - startTime, serviceConfig.name, false, error.message);
      return securityMiddleware(errorResponse);
    }

    // 13. Response Transformation
    const transformedResponse = await transformResponse(serviceResponse, serviceConfig, requestId, Date.now() - startTime);

    // 14. Cache Response если нужно
    if (shouldCache(serviceResponse, path, method)) {
      const ttl = cacheManager.getTTLForEndpoint(path);
      cacheManager.cacheResponse(req, transformedResponse, ttl);
    }

    // 15. Завершение логирования
    logRequestCompletion(requestId, serviceResponse.status, Date.now() - startTime, serviceConfig.name);

    return securityMiddleware(transformedResponse);

  } catch (error) {
    console.error(`[${requestId}] Gateway error:`, error);
    
    // Fallback error handling
    const fallbackResponse = await handleFallback(req, requestId, startTime);
    if (fallbackResponse) {
      return securityMiddleware(fallbackResponse);
    }

    const errorResponse = createSecureResponse(JSON.stringify({
      error: {
        code: 'INTERNAL_ERROR',
        message: 'Gateway internal error',
        requestId,
        details: { error: error.message }
      }
    }), 500);
    
    logRequestCompletion(requestId, 500, Date.now() - startTime, undefined, false, error.message);
    return securityMiddleware(errorResponse);
  }
});

// ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

/**
 * Выбирает здоровый инстанс сервиса с учетом load balancing
 */
function selectHealthyInstance(serviceConfig: any): any {
  const healthyInstances = serviceConfig.instances.filter((instance: any) => instance.healthy);
  
  if (healthyInstances.length === 0) {
    return null;
  }
  
  // Weighted round-robin
  const totalWeight = healthyInstances.reduce((sum: number, instance: any) => sum + instance.weight, 0);
  let random = Math.random() * totalWeight;
  
  for (const instance of healthyInstances) {
    random -= instance.weight;
    if (random <= 0) {
      return instance;
    }
  }
  
  return healthyInstances[0];
}

/**
 * Трансформирует запрос для отправки в сервис
 */
async function transformRequest(req: Request, serviceConfig: any, authResult: any): Promise<Request> {
  const headers = new Headers(req.headers);
  
  // Добавляем gateway метаданные
  headers.set('X-Gateway-Request', 'true');
  headers.set('X-User-ID', authResult.user?.id || 'anonymous');
  headers.set('X-Service-Timeout', serviceConfig.timeout.toString());
  headers.set('X-Service-Name', serviceConfig.name);
  
  // Удаляем gateway-специфичные заголовки для внешнего мира
  headers.delete('x-api-key');
  headers.delete('x-service-key');
  
  // Сохраняем Authorization header для сервисов
  if (authResult.token?.type === 'bearer') {
    headers.set('Authorization', `Bearer ${authResult.token.token}`);
  }
  
  return new Request(req.url, {
    method: req.method,
    headers: headers,
    body: req.body
  });
}

/**
 * Трансформирует ответ от сервиса
 */
async function transformResponse(response: Response, serviceConfig: any, requestId: string, duration: number): Promise<Response> {
  const headers = new Headers(response.headers);
  
  // Добавляем gateway метаданные
  headers.set('X-Gateway-Response', 'true');
  headers.set('X-Server-Name', serviceConfig.name);
  headers.set('X-Request-ID', requestId);
  headers.set('X-Response-Time', `${duration}ms`);
  headers.set('X-API-Version', serviceConfig.version);
  
  // Добавляем cache headers если кэш включен
  if (serviceConfig.cache?.enabled) {
    Object.entries(cacheManager.createCacheHeaders(serviceConfig.cache.ttl)).forEach(([key, value]) => {
      headers.set(key, value);
    });
  }
  
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: headers
  });
}

/**
 * Определяет, нужно ли кэшировать ответ
 */
function shouldCache(response: Response, path: string, method: string): boolean {
  // Кэшируем только GET запросы с успешным статусом
  if (method !== 'GET') return false;
  if (response.status >= 400) return false;
  
  // Не кэшируем динамические endpoints
  const noCachePatterns = ['/health', '/status', '/metrics', '/logs'];
  if (noCachePatterns.some(pattern => path.includes(pattern))) return false;
  
  return true;
}

/**
 * Обработка fallback сценариев
 */
async function handleFallback(req: Request, requestId: string, startTime: number): Promise<Response | null> {
  const url = new URL(req.url);
  
  // Fallback для health checks
  if (url.pathname === '/health') {
    const fallbackResponse = createSecureResponse(JSON.stringify({
      status: 'degraded',
      message: 'Some services are unavailable, but gateway is operational',
      requestId,
      timestamp: new Date().toISOString(),
      uptime: Date.now() - startTime
    }), 200);
    
    logRequestCompletion(requestId, 200, Date.now() - startTime, 'health-service', false, 'Fallback response');
    return fallbackResponse;
  }
  
  return null;
}