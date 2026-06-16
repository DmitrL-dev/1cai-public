// Security Headers Middleware для API Gateway
// Обеспечивает безопасность через правильные HTTP заголовки

import { gatewayConfig } from '../config.ts';

export interface SecurityConfig {
  // Content Security Policy
  contentSecurityPolicy?: {
    directives: Record<string, string[]>;
    reportOnly?: boolean;
  };
  
  // CORS настройки
  cors?: {
    allowedOrigins: string[];
    allowedMethods: string[];
    allowedHeaders: string[];
    maxAge?: number;
  };
  
  // Security заголовки
  headers: Record<string, string>;
  
  // HSTS настройки
  hsts?: {
    maxAge: number;
    includeSubDomains: boolean;
    preload: boolean;
  };
}

export class SecurityMiddleware {
  private config: SecurityConfig;

  constructor(config?: Partial<SecurityConfig>) {
    this.config = {
      ...gatewayConfig.security,
      ...config,
      headers: {
        ...gatewayConfig.security.headers,
        ...config?.headers
      }
    };
  }

  /**
   * Применяет security заголовки к ответу
   */
  applySecurityHeaders(response: Response): Response {
    const headers = new Headers(response.headers);
    
    // Применяем базовые security заголовки
    Object.entries(this.config.headers).forEach(([key, value]) => {
      headers.set(key, value);
    });

    // Content Security Policy
    if (this.config.contentSecurityPolicy) {
      const csp = this.buildContentSecurityPolicy(this.config.contentSecurityPolicy);
      headers.set('Content-Security-Policy', csp);
    }

    // HTTP Strict Transport Security
    if (this.config.hsts) {
      const hsts = this.buildHSTSHeader(this.config.hsts);
      headers.set('Strict-Transport-Security', hsts);
    }

    // Permissions Policy
    headers.set('Permissions-Policy', this.buildPermissionsPolicy());

    // Cross-Origin Resource Policy
    headers.set('Cross-Origin-Resource-Policy', 'same-origin');

    // Cross-Origin Embedder Policy
    headers.set('Cross-Origin-Embedder-Policy', 'require-corp');

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers
    });
  }

  /**
   * Валидирует security заголовки в запросе
   */
  validateSecurityHeaders(headers: Headers): { valid: boolean; warnings: string[] } {
    const warnings: string[] = [];

    // Проверяем присутствие важных security заголовков
    const importantHeaders = [
      'user-agent',
      'accept',
      'accept-language'
    ];

    for (const header of importantHeaders) {
      if (!headers.has(header)) {
        warnings.push(`Missing security-related header: ${header}`);
      }
    }

    // Проверяем подозрительные заголовки
    const suspiciousHeaders = [
      'x-forwarded-host',
      'x-original-url',
      'x-rewrite-url'
    ];

    for (const header of suspiciousHeaders) {
      if (headers.has(header)) {
        warnings.push(`Suspicious header detected: ${header}`);
      }
    }

    return {
      valid: warnings.length === 0,
      warnings
    };
  }

  /**
   * Фильтрует опасные заголовки из запроса
   */
  filterRequestHeaders(headers: Headers): Headers {
    const filtered = new Headers();
    
    // Список разрешенных заголовков
    const allowedHeaders = [
      'authorization',
      'content-type',
      'accept',
      'accept-language',
      'user-agent',
      'accept-encoding',
      'connection',
      'host',
      'x-api-key',
      'x-client-info',
      'x-request-id',
      'x-correlation-id',
      'x-forwarded-for',
      'x-real-ip',
      'cache-control',
      'if-none-match',
      'if-modified-since'
    ];

    // Добавляем разрешенные заголовки
    for (const [key, value] of headers.entries()) {
      if (allowedHeaders.includes(key.toLowerCase())) {
        filtered.set(key, value);
      }
    }

    return filtered;
  }

  /**
   * Создает Content Security Policy
   */
  private buildContentSecurityPolicy(csp: SecurityConfig['contentSecurityPolicy']): string {
    if (!csp) return '';

    const directives = [];
    
    for (const [directive, sources] of Object.entries(csp.directives)) {
      const sourceList = sources.join(' ');
      directives.push(`${directive} ${sourceList}`);
    }

    const cspString = directives.join('; ');
    return csp.reportOnly ? cspString : cspString;
  }

  /**
   * Создает HSTS заголовок
   */
  private buildHSTSHeader(hsts: SecurityConfig['hsts']): string {
    if (!hsts) return '';

    let header = `max-age=${hsts.maxAge}`;
    
    if (hsts.includeSubDomains) {
      header += '; includeSubDomains';
    }
    
    if (hsts.preload) {
      header += '; preload';
    }

    return header;
  }

  /**
   * Создает Permissions Policy заголовок
   */
  private buildPermissionsPolicy(): string {
    return [
      'camera=()',
      'microphone=()',
      'geolocation=()',
      'payment=()',
      'usb=()',
      'accelerometer=()',
      'gyroscope=()',
      'magnetometer=()',
      'picture-in-picture=()',
      'screen-wake-lock=()',
      'web-share=()'
    ].join(', ');
  }

  /**
   * Создает security error response
   */
  createSecurityErrorResponse(message: string, code: string = 'SECURITY_VIOLATION'): Response {
    return new Response(JSON.stringify({
      error: {
        code,
        message,
        timestamp: new Date().toISOString(),
        details: 'Request blocked by security policies'
      }
    }), {
      status: 403,
      headers: {
        'Content-Type': 'application/json',
        ...this.config.headers,
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
      }
    });
  }

  /**
   * Middleware функция для автоматического применения security headers
   */
  static middleware(response: Response): Response {
    const security = new SecurityMiddleware();
    return security.applySecurityHeaders(response);
  }

  /**
   * Создает фиксированный набор security headers для development
   */
  static developmentHeaders(): Record<string, string> {
    return {
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'SAMEORIGIN',
      'X-XSS-Protection': '1; mode=block',
      'Referrer-Policy': 'strict-origin-when-cross-origin',
      'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
    };
  }

  /**
   * Создает фиксированный набор security headers для production
   */
  static productionHeaders(): Record<string, string> {
    return {
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'X-XSS-Protection': '1; mode=block',
      'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
      'Referrer-Policy': 'strict-origin-when-cross-origin',
      'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
      'Cross-Origin-Resource-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
      'Cross-Origin-Opener-Policy': 'same-origin'
    };
  }
}

// Глобальный экземпляр security middleware
export const security = new SecurityMiddleware();

// Экспортируем middleware функции
export const securityMiddleware = {
  apply: SecurityMiddleware.middleware,
  validate: (headers: Headers) => security.validateSecurityHeaders(headers),
  filter: (headers: Headers) => security.filterRequestHeaders(headers),
  error: (message: string, code?: string) => security.createSecurityErrorResponse(message, code),
  devHeaders: SecurityMiddleware.developmentHeaders,
  prodHeaders: SecurityMiddleware.productionHeaders
};

// Функция для получения security заголовков как объекта
export function getSecurityHeaders(): Record<string, string> {
  return security.config.headers;
}

// Функция для создания response с security заголовками
export function createSecureResponse(
  body: string | Uint8Array,
  status: number = 200,
  contentType: string = 'application/json'
): Response {
  return security.applySecurityHeaders(new Response(body, {
    status,
    headers: {
      'Content-Type': contentType,
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      'Pragma': 'no-cache',
      'Expires': '0'
    }
  }));
}