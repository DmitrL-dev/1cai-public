// Logging & Metrics Middleware для API Gateway
// Обеспечивает детальное логирование запросов и сбор метрик

export interface RequestLog {
  timestamp: string;
  requestId: string;
  method: string;
  url: string;
  path: string;
  userAgent?: string;
  ip?: string;
  userId?: string;
  status?: number;
  duration?: number;
  service?: string;
  instance?: string;
  cacheHit?: boolean;
  error?: string;
  size?: {
    request: number;
    response: number;
  };
}

export interface MetricsData {
  totalRequests: number;
  totalResponses: number;
  errors: number;
  averageResponseTime: number;
  requestsPerService: Record<string, number>;
  requestsPerMethod: Record<string, number>;
  statusCodes: Record<string, number>;
  cacheHitRate: number;
  activeConnections: number;
  memoryUsage: number;
}

export class Logger {
  private logs: RequestLog[] = [];
  private maxLogs = 10000; // Храним только последние 10000 логов
  private startTime = Date.now();

  /**
   * Логирует начало запроса
   */
  logRequestStart(req: Request, requestId: string): void {
    const url = new URL(req.url);
    const log: RequestLog = {
      timestamp: new Date().toISOString(),
      requestId,
      method: req.method,
      url: req.url,
      path: url.pathname,
      userAgent: req.headers.get('user-agent'),
      ip: this.getClientIP(req),
      userId: this.extractUserId(req),
      size: {
        request: parseInt(req.headers.get('content-length') || '0'),
        response: 0
      }
    };

    this.logs.push(log);
    
    // Ограничиваем размер логов
    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(-this.maxLogs);
    }

    console.log(`[${requestId}] START ${req.method} ${url.pathname} - ${log.userAgent || 'Unknown'}`);
  }

  /**
   * Логирует завершение запроса
   */
  logRequestEnd(log: Partial<RequestLog>): void {
    if (!log.requestId) return;

    const existingLog = this.logs.find(l => l.requestId === log.requestId);
    if (existingLog) {
      Object.assign(existingLog, log);
      
      console.log(`[${log.requestId}] END ${existingLog.method} ${existingLog.path} - ` +
                  `${existingLog.status} ${existingLog.duration}ms ${existingLog.cacheHit ? '[CACHE]' : ''}`);
    }
  }

  /**
   * Логирует ошибку
   */
  logError(requestId: string, error: Error | string, context?: any): void {
    const errorLog: RequestLog = {
      timestamp: new Date().toISOString(),
      requestId,
      method: 'ERROR',
      url: 'error',
      path: 'error',
      error: typeof error === 'string' ? error : error.message,
      ...context
    };

    console.error(`[${requestId}] ERROR:`, typeof error === 'string' ? error : error, context);
  }

  /**
   * Получает все логи
   */
  getLogs(filter?: Partial<RequestLog>): RequestLog[] {
    if (!filter) return this.logs;

    return this.logs.filter(log => {
      return Object.entries(filter).every(([key, value]) => {
        return (log as any)[key] === value;
      });
    });
  }

  /**
   * Получает логи за период времени
   */
  getLogsByTimeRange(startTime: Date, endTime: Date): RequestLog[] {
    return this.logs.filter(log => {
      const logTime = new Date(log.timestamp);
      return logTime >= startTime && logTime <= endTime;
    });
  }

  /**
   * Очищает логи
   */
  clearLogs(): void {
    this.logs = [];
  }

  /**
   * Извлекает IP адрес клиента
   */
  private getClientIP(req: Request): string {
    return req.headers.get('x-forwarded-for') || 
           req.headers.get('x-real-ip') || 
           'unknown';
  }

  /**
   * Извлекает ID пользователя из заголовков
   */
  private extractUserId(req: Request): string | undefined {
    const authHeader = req.headers.get('authorization');
    const apiKey = req.headers.get('x-api-key');
    
    if (authHeader?.startsWith('Bearer ')) {
      // В реальном проекте здесь декодировался бы JWT
      return 'authenticated-user';
    }
    
    if (apiKey?.startsWith('sk-')) {
      return 'api-user';
    }
    
    return 'anonymous';
  }
}

export class MetricsCollector {
  private metrics: MetricsData = {
    totalRequests: 0,
    totalResponses: 0,
    errors: 0,
    averageResponseTime: 0,
    requestsPerService: {},
    requestsPerMethod: {},
    statusCodes: {},
    cacheHitRate: 0,
    activeConnections: 0,
    memoryUsage: 0
  };

  private responseTimes: number[] = [];
  private maxResponseTimes = 1000; // Храним только последние 1000 значений
  private cacheHits = 0;
  private totalCacheableRequests = 0;

  /**
   * Записывает метрику запроса
   */
  recordRequest(method: string, path: string, service?: string): void {
    this.metrics.totalRequests++;
    
    // Статистика по методам
    this.metrics.requestsPerMethod[method] = (this.metrics.requestsPerMethod[method] || 0) + 1;
    
    // Статистика по сервисам
    if (service) {
      this.metrics.requestsPerService[service] = (this.metrics.requestsPerService[service] || 0) + 1;
    }

    // Подсчитываем кэшируемые запросы
    if (method === 'GET') {
      this.totalCacheableRequests++;
    }
  }

  /**
   * Записывает метрику ответа
   */
  recordResponse(
    statusCode: number, 
    duration: number, 
    cacheHit: boolean = false, 
    service?: string
  ): void {
    this.metrics.totalResponses++;
    
    // Время ответа
    this.responseTimes.push(duration);
    if (this.responseTimes.length > this.maxResponseTimes) {
      this.responseTimes.shift();
    }
    
    // Обновляем среднее время ответа
    this.metrics.averageResponseTime = this.responseTimes.reduce((a, b) => a + b, 0) / this.responseTimes.length;
    
    // Статистика по кодам статуса
    const statusGroup = Math.floor(statusCode / 100) * 100;
    this.metrics.statusCodes[statusGroup.toString()] = (this.metrics.statusCodes[statusGroup.toString()] || 0) + 1;
    
    // Статистика ошибок
    if (statusCode >= 400) {
      this.metrics.errors++;
    }
    
    // Статистика кэша
    if (cacheHit) {
      this.cacheHits++;
    }
    
    // Обновляем hit rate кэша
    if (this.totalCacheableRequests > 0) {
      this.metrics.cacheHitRate = (this.cacheHits / this.totalCacheableRequests) * 100;
    }
  }

  /**
   * Обновляет активные соединения
   */
  setActiveConnections(count: number): void {
    this.metrics.activeConnections = count;
  }

  /**
   * Обновляет использование памяти
   */
  updateMemoryUsage(): void {
    if (typeof Deno !== 'undefined' && (Deno as any).memory) {
      const memory = (Deno as any).memory();
      this.metrics.memoryUsage = memory.heapUsed;
    }
  }

  /**
   * Получает текущие метрики
   */
  getMetrics(): MetricsData {
    this.updateMemoryUsage();
    return { ...this.metrics };
  }

  /**
   * Сбрасывает метрики
   */
  reset(): void {
    this.metrics = {
      totalRequests: 0,
      totalResponses: 0,
      errors: 0,
      averageResponseTime: 0,
      requestsPerService: {},
      requestsPerMethod: {},
      statusCodes: {},
      cacheHitRate: 0,
      activeConnections: 0,
      memoryUsage: 0
    };
    this.responseTimes = [];
    this.cacheHits = 0;
    this.totalCacheableRequests = 0;
  }

  /**
   * Создает отчет по метрикам
   */
  generateReport(): string {
    const metrics = this.getMetrics();
    const uptime = Date.now() - this.startTime;
    
    return `
API Gateway Metrics Report
===========================
Uptime: ${Math.floor(uptime / 1000 / 60)} minutes
Total Requests: ${metrics.totalRequests}
Total Responses: ${metrics.totalResponses}
Errors: ${metrics.errors}
Error Rate: ${((metrics.errors / metrics.totalResponses) * 100).toFixed(2)}%
Average Response Time: ${metrics.averageResponseTime.toFixed(2)}ms
Cache Hit Rate: ${metrics.cacheHitRate.toFixed(2)}%
Memory Usage: ${(metrics.memoryUsage / 1024 / 1024).toFixed(2)}MB

Requests by Method:
${Object.entries(metrics.requestsPerMethod).map(([method, count]) => `  ${method}: ${count}`).join('\n')}

Requests by Service:
${Object.entries(metrics.requestsPerService).map(([service, count]) => `  ${service}: ${count}`).join('\n')}

Status Codes:
${Object.entries(metrics.statusCodes).map(([code, count]) => `  ${code}xx: ${count}`).join('\n')}
`;
  }
}

// Глобальные экземпляры
export const logger = new Logger();
export const metrics = new MetricsCollector();

// Middleware функции
export function loggingMiddleware(req: Request, requestId: string): void {
  logger.logRequestStart(req, requestId);
}

export function metricsMiddleware(req: Request, path: string): void {
  const method = req.method;
  const service = extractServiceFromPath(path);
  metrics.recordRequest(method, path, service);
}

// Вспомогательная функция для извлечения сервиса из пути
function extractServiceFromPath(path: string): string | undefined {
  const parts = path.split('/').filter(p => p);
  if (parts.length >= 2) {
    return parts[1]; // /v1/service/...
  }
  return undefined;
}

// Функция для логирования завершения запроса
export function logRequestCompletion(
  requestId: string,
  statusCode: number,
  duration: number,
  service?: string,
  cacheHit?: boolean,
  error?: string
): void {
  logger.logRequestEnd({
    requestId,
    status: statusCode,
    duration,
    service,
    cacheHit,
    error
  });
  
  metrics.recordResponse(statusCode, duration, cacheHit, service);
}

// Endpoint для получения метрик
export function createMetricsEndpoint(): Response {
  const report = metrics.generateReport();
  return new Response(report, {
    headers: {
      'Content-Type': 'text/plain',
      'Cache-Control': 'no-cache'
    }
  });
}

// Endpoint для получения логов
export function createLogsEndpoint(filter?: any): Response {
  const logs = logger.getLogs(filter);
  return new Response(JSON.stringify({
    logs,
    count: logs.length,
    timestamp: new Date().toISOString()
  }, null, 2), {
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache'
    }
  });
}