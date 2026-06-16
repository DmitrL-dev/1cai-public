// CORS Middleware для API Gateway
// Обрабатывает CORS запросы и управляет политикой доступа

import { gatewayConfig } from './config.ts';

export interface CORSMiddleware {
  handlePreflight: (req: Request) => Response | null;
  addCORSHeaders: (response: Response) => Response;
  validateOrigin: (origin: string) => boolean;
  setVaryHeader: (response: Response, varyValue: string) => Response;
}

export class CORSHandler implements CORSMiddleware {
  private config = gatewayConfig.security.cors;

  /**
   * Обрабатывает CORS preflight запросы (OPTIONS)
   */
  handlePreflight(req: Request): Response | null {
    if (req.method !== 'OPTIONS') {
      return null;
    }

    const origin = req.headers.get('Origin') || '';
    const accessControlRequestMethod = req.headers.get('Access-Control-Request-Method') || '';
    const accessControlRequestHeaders = req.headers.get('Access-Control-Request-Headers') || '';

    // Проверяем происхождение
    if (!this.validateOrigin(origin)) {
      return new Response('Origin not allowed', { status: 403 });
    }

    // Создаем ответ на preflight запрос
    const headers = new Headers();
    
    // Разрешенные источники
    if (this.config.allowedOrigins.includes('*')) {
      headers.set('Access-Control-Allow-Origin', '*');
    } else {
      headers.set('Access-Control-Allow-Origin', origin);
      headers.set('Vary', 'Origin');
    }

    // Разрешенные методы
    headers.set('Access-Control-Allow-Methods', this.config.allowedMethods.join(', '));
    
    // Разрешенные заголовки
    headers.set('Access-Control-Allow-Headers', accessControlRequestHeaders || this.config.allowedHeaders.join(', '));
    
    // Разрешенные credentials
    headers.set('Access-Control-Allow-Credentials', 'true');
    
    // Cache preflight response
    headers.set('Access-Control-Max-Age', this.config.maxAge.toString());

    return new Response(null, { status: 204, headers });
  }

  /**
   * Добавляет CORS заголовки к ответу
   */
  addCORSHeaders(response: Response): Response {
    const headers = new Headers(response.headers);
    const origin = this.getRequestOrigin();

    // Разрешенные источники
    if (this.config.allowedOrigins.includes('*')) {
      headers.set('Access-Control-Allow-Origin', '*');
    } else if (this.validateOrigin(origin)) {
      headers.set('Access-Control-Allow-Origin', origin);
      headers.set('Vary', 'Origin');
    }

    // Добавляем другие CORS заголовки
    headers.set('Access-Control-Allow-Methods', this.config.allowedMethods.join(', '));
    headers.set('Access-Control-Allow-Headers', this.config.allowedHeaders.join(', '));
    headers.set('Access-Control-Allow-Credentials', 'true');

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers
    });
  }

  /**
   * Проверяет разрешено ли происхождение
   */
  validateOrigin(origin: string): boolean {
    // Если разрешены все источники
    if (this.config.allowedOrigins.includes('*')) {
      return true;
    }

    // Проверяем точное совпадение
    if (this.config.allowedOrigins.includes(origin)) {
      return true;
    }

    // Проверяем wildcard паттерны
    for (const allowedOrigin of this.config.allowedOrigins) {
      if (allowedOrigin.includes('*')) {
        const regex = new RegExp(allowedOrigin.replace(/\*/g, '.*'));
        if (regex.test(origin)) {
          return true;
        }
      }
    }

    // Разрешаем localhost и 127.0.0.1 для разработки
    if (origin.includes('localhost') || origin.includes('127.0.0.1')) {
      return true;
    }

    return false;
  }

  /**
   * Устанавливает Vary заголовок для кэширования
   */
  setVaryHeader(response: Response, varyValue: string): Response {
    const headers = new Headers(response.headers);
    const vary = headers.get('Vary') || '';
    const varyList = vary.split(',').map(v => v.trim()).filter(v => v);
    
    if (!varyList.includes(varyValue)) {
      varyList.push(varyValue);
    }
    
    headers.set('Vary', varyList.join(', '));
    
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers
    });
  }

  /**
   * Получает origin из текущего запроса
   */
  private getRequestOrigin(): string {
    // В реальной реализации здесь нужно получить origin из контекста запроса
    return '';
  }

  /**
   * Создает CORS error response
   */
  createCORSError(message: string, status: number = 403): Response {
    return new Response(JSON.stringify({
      error: {
        code: 'CORS_ERROR',
        message,
        timestamp: new Date().toISOString()
      }
    }), {
      status,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'authorization, content-type, x-api-key'
      }
    });
  }

  /**
   * Middleware функция для использования в Deno.serve
   */
  static middleware(req: Request): Response | null {
    const cors = new CORSHandler();
    
    // Обрабатываем preflight запросы
    const preflightResponse = cors.handlePreflight(req);
    if (preflightResponse) {
      return preflightResponse;
    }

    return null;
  }

  /**
   * Декоратор для добавления CORS заголовков к ответу
   */
  static addHeaders(response: Response): Response {
    const cors = new CORSHandler();
    return cors.addCORSHeaders(response);
  }
}

// Экспортируем middleware функции для удобного использования
export const corsMiddleware = {
  preflight: CORSHandler.middleware,
  addHeaders: CORSHandler.addHeaders,
  validateOrigin: (origin: string) => new CORSHandler().validateOrigin(origin),
  createError: (message: string, status?: number) => new CORSHandler().createCORSError(message, status)
};