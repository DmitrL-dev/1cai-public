// Request Validation Middleware для API Gateway
// Валидирует входящие запросы по различным критериям

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings?: ValidationWarning[];
}

export interface ValidationError {
  field?: string;
  code: string;
  message: string;
  details?: any;
}

export interface ValidationWarning {
  field?: string;
  code: string;
  message: string;
  suggestion?: string;
}

export interface ValidationRule {
  field: string;
  required?: boolean;
  type?: 'string' | 'number' | 'boolean' | 'object' | 'array' | 'email' | 'url';
  minLength?: number;
  maxLength?: number;
  min?: number;
  max?: number;
  pattern?: RegExp;
  enum?: any[];
  custom?: (value: any) => boolean | string;
}

export interface ValidationSchema {
  body?: ValidationRule[];
  query?: ValidationRule[];
  headers?: ValidationRule[];
  params?: ValidationRule[];
}

export class RequestValidator {
  private schemas: Map<string, ValidationSchema> = new Map();

  constructor() {
    this.initializeDefaultSchemas();
  }

  /**
   * Инициализирует стандартные схемы валидации
   */
  private initializeDefaultSchemas(): void {
    // Схема для POST/PUT запросов
    this.schemas.set('json-body', {
      body: [
        { field: 'data', required: true, type: 'object' },
        { field: 'metadata', type: 'object' }
      ]
    });

    // Схема для query параметров
    this.schemas.set('query-params', {
      query: [
        { field: 'limit', type: 'number', min: 1, max: 1000 },
        { field: 'offset', type: 'number', min: 0 },
        { field: 'sort', type: 'string', pattern: /^[a-zA-Z_-]+:(asc|desc)$/ },
        { field: 'filter', type: 'string', maxLength: 500 }
      ]
    });

    // Схема для заголовков
    this.schemas.set('headers', {
      headers: [
        { field: 'content-type', required: true, enum: ['application/json', 'application/x-www-form-urlencoded'] },
        { field: 'user-agent', type: 'string', minLength: 1 },
        { field: 'accept', type: 'string' }
      ]
    });
  }

  /**
   * Валидирует весь запрос
   */
  validateRequest(req: Request, path: string, method: string): ValidationResult {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];

    // Валидируем метод
    const methodValidation = this.validateMethod(method);
    if (!methodValidation.valid) {
      errors.push(...methodValidation.errors);
    }

    // Валидируем заголовки
    const headersValidation = this.validateHeaders(req.headers);
    if (!headersValidation.valid) {
      errors.push(...headersValidation.errors);
    }

    // Валидируем URL и параметры
    const urlValidation = this.validateURL(req.url);
    if (!urlValidation.valid) {
      errors.push(...urlValidation.errors);
    }

    // Валидируем тело запроса если есть
    if (this.hasBody(method)) {
      const bodyValidation = this.validateBody(req, method);
      if (!bodyValidation.valid) {
        errors.push(...bodyValidation.errors);
      }
      warnings.push(...(bodyValidation.warnings || []));
    }

    // Валидируем размер запроса
    const sizeValidation = this.validateRequestSize(req);
    if (!sizeValidation.valid) {
      errors.push(...sizeValidation.errors);
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings: warnings.length > 0 ? warnings : undefined
    };
  }

  /**
   * Валидирует HTTP метод
   */
  private validateMethod(method: string): ValidationResult {
    const allowedMethods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'];
    
    if (!allowedMethods.includes(method)) {
      return {
        valid: false,
        errors: [{
          code: 'INVALID_METHOD',
          message: `HTTP method ${method} is not allowed`,
          details: { method, allowedMethods }
        }]
      };
    }

    return { valid: true, errors: [] };
  }

  /**
   * Валидирует заголовки запроса
   */
  private validateHeaders(headers: Headers): ValidationResult {
    const errors: ValidationError[] = [];
    
    // Проверяем обязательные заголовки
    const requiredHeaders = ['host'];
    for (const header of requiredHeaders) {
      if (!headers.has(header)) {
        errors.push({
          code: 'MISSING_HEADER',
          message: `Required header '${header}' is missing`,
          details: { header }
        });
      }
    }

    // Проверяем content-type для POST/PUT/PATCH
    const contentType = headers.get('content-type');
    if (contentType && !this.isValidContentType(contentType)) {
      errors.push({
        code: 'INVALID_CONTENT_TYPE',
        message: 'Invalid content type',
        details: { contentType }
      });
    }

    // Проверяем размер заголовков
    const totalHeaderSize = this.calculateHeaderSize(headers);
    if (totalHeaderSize > 8192) { // 8KB limit
      errors.push({
        code: 'HEADERS_TOO_LARGE',
        message: 'Request headers exceed size limit',
        details: { size: totalHeaderSize, limit: 8192 }
      });
    }

    return { valid: errors.length === 0, errors };
  }

  /**
   * Валидирует URL и параметры
   */
  private validateURL(url: string): ValidationResult {
    const errors: ValidationError[] = [];
    
    try {
      const urlObj = new URL(url);
      
      // Проверяем длину URL
      if (url.length > 2048) {
        errors.push({
          code: 'URL_TOO_LONG',
          message: 'URL exceeds maximum length',
          details: { length: url.length, limit: 2048 }
        });
      }

      // Валидируем query параметры
      for (const [key, value] of urlObj.searchParams.entries()) {
        if (key.length > 100) {
          errors.push({
            code: 'QUERY_PARAM_TOO_LONG',
            message: 'Query parameter key too long',
            details: { key, length: key.length, limit: 100 }
          });
        }
        
        if (value.length > 1000) {
          errors.push({
            code: 'QUERY_PARAM_VALUE_TOO_LONG',
            message: 'Query parameter value too long',
            details: { key, value: value.substring(0, 100), length: value.length, limit: 1000 }
          });
        }
      }

    } catch (error) {
      errors.push({
        code: 'INVALID_URL',
        message: 'Invalid URL format',
        details: { url, error: error.message }
      });
    }

    return { valid: errors.length === 0, errors };
  }

  /**
   * Валидирует тело запроса
   */
  private async validateBody(req: Request, method: string): Promise<ValidationResult> {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];
    
    try {
      const contentType = req.headers.get('content-type') || '';
      const contentLength = req.headers.get('content-length');
      
      // Проверяем наличие тела для методов, которые его требуют
      if (!contentLength && ['POST', 'PUT', 'PATCH'].includes(method)) {
        warnings.push({
          code: 'NO_BODY_EXPECTED',
          message: 'Request body expected but not provided',
          suggestion: 'Provide a request body or check if the method is correct'
        });
        return { valid: true, errors, warnings };
      }

      // Валидируем JSON
      if (contentType.includes('application/json')) {
        const bodyText = await req.text();
        
        if (bodyText.trim()) {
          try {
            JSON.parse(bodyText);
          } catch (error) {
            errors.push({
              code: 'INVALID_JSON',
              message: 'Request body contains invalid JSON',
              details: { error: error.message }
            });
          }
        }
      }

      // Валидируем x-www-form-urlencoded
      if (contentType.includes('application/x-www-form-urlencoded')) {
        const bodyText = await req.text();
        // Простая проверка на валидность URL-encoded данных
        if (bodyText && !bodyText.includes('=')) {
          errors.push({
            code: 'INVALID_FORM_DATA',
            message: 'Invalid form data format'
          });
        }
      }

    } catch (error) {
      errors.push({
        code: 'BODY_VALIDATION_ERROR',
        message: 'Error validating request body',
        details: { error: error.message }
      });
    }

    return { valid: errors.length === 0, errors, warnings };
  }

  /**
   * Валидирует размер запроса
   */
  private validateRequestSize(req: Request): ValidationResult {
    const errors: ValidationError[] = [];
    const contentLength = req.headers.get('content-length');
    
    if (contentLength) {
      const size = parseInt(contentLength);
      const maxSize = 10 * 1024 * 1024; // 10MB
      
      if (size > maxSize) {
        errors.push({
          code: 'REQUEST_TOO_LARGE',
          message: 'Request size exceeds maximum allowed',
          details: { size, maxSize }
        });
      }
    }

    return { valid: errors.length === 0, errors };
  }

  /**
   * Проверяет валидность content-type
   */
  private isValidContentType(contentType: string): boolean {
    const allowedTypes = [
      'application/json',
      'application/x-www-form-urlencoded',
      'multipart/form-data',
      'text/plain',
      'application/xml'
    ];
    
    return allowedTypes.some(type => contentType.includes(type));
  }

  /**
   * Вычисляет общий размер заголовков
   */
  private calculateHeaderSize(headers: Headers): number {
    let totalSize = 0;
    for (const [key, value] of headers.entries()) {
      totalSize += key.length + value.length + 4; // +4 for ": " and "\r\n"
    }
    return totalSize;
  }

  /**
   * Проверяет, есть ли тело у метода
   */
  private hasBody(method: string): boolean {
    return ['POST', 'PUT', 'PATCH'].includes(method);
  }

  /**
   * Валидирует конкретное значение по правилу
   */
  private validateField(value: any, rule: ValidationRule): ValidationError[] {
    const errors: ValidationError[] = [];

    // Проверка required
    if (rule.required && (value === undefined || value === null || value === '')) {
      errors.push({
        field: rule.field,
        code: 'REQUIRED_FIELD',
        message: `Field '${rule.field}' is required`
      });
      return errors;
    }

    if (value === undefined || value === null) {
      return errors; // Skip validation if field is optional and empty
    }

    // Проверка типа
    if (rule.type && !this.validateType(value, rule.type)) {
      errors.push({
        field: rule.field,
        code: 'INVALID_TYPE',
        message: `Field '${rule.field}' must be of type ${rule.type}`,
        details: { value, expectedType: rule.type, actualType: typeof value }
      });
    }

    // Проверка длины для строк
    if (typeof value === 'string') {
      if (rule.minLength && value.length < rule.minLength) {
        errors.push({
          field: rule.field,
          code: 'MIN_LENGTH_VIOLATION',
          message: `Field '${rule.field}' must be at least ${rule.minLength} characters`,
          details: { value: value.substring(0, 50), length: value.length, minLength: rule.minLength }
        });
      }

      if (rule.maxLength && value.length > rule.maxLength) {
        errors.push({
          field: rule.field,
          code: 'MAX_LENGTH_VIOLATION',
          message: `Field '${rule.field}' must be no more than ${rule.maxLength} characters`,
          details: { value: value.substring(0, 50), length: value.length, maxLength: rule.maxLength }
        });
      }

      // Проверка паттерна
      if (rule.pattern && !rule.pattern.test(value)) {
        errors.push({
          field: rule.field,
          code: 'PATTERN_VIOLATION',
          message: `Field '${rule.field}' does not match required pattern`
        });
      }
    }

    // Проверка числовых значений
    if (typeof value === 'number') {
      if (rule.min !== undefined && value < rule.min) {
        errors.push({
          field: rule.field,
          code: 'MIN_VALUE_VIOLATION',
          message: `Field '${rule.field}' must be at least ${rule.min}`,
          details: { value, min: rule.min }
        });
      }

      if (rule.max !== undefined && value > rule.max) {
        errors.push({
          field: rule.field,
          code: 'MAX_VALUE_VIOLATION',
          message: `Field '${rule.field}' must be no more than ${rule.max}`,
          details: { value, max: rule.max }
        });
      }
    }

    // Проверка enum
    if (rule.enum && !rule.enum.includes(value)) {
      errors.push({
        field: rule.field,
        code: 'ENUM_VIOLATION',
        message: `Field '${rule.field}' must be one of: ${rule.enum.join(', ')}`,
        details: { value, allowedValues: rule.enum }
      });
    }

    // Пользовательская валидация
    if (rule.custom) {
      const customResult = rule.custom(value);
      if (customResult !== true) {
        errors.push({
          field: rule.field,
          code: 'CUSTOM_VALIDATION_FAILED',
          message: typeof customResult === 'string' ? customResult : `Field '${rule.field}' failed custom validation`
        });
      }
    }

    return errors;
  }

  /**
   * Валидирует тип значения
   */
  private validateType(value: any, expectedType: string): boolean {
    switch (expectedType) {
      case 'string':
        return typeof value === 'string';
      case 'number':
        return typeof value === 'number' && !isNaN(value);
      case 'boolean':
        return typeof value === 'boolean';
      case 'object':
        return typeof value === 'object' && value !== null && !Array.isArray(value);
      case 'array':
        return Array.isArray(value);
      case 'email':
        return typeof value === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
      case 'url':
        try {
          new URL(value);
          return true;
        } catch {
          return false;
        }
      default:
        return true;
    }
  }
}

// Middleware функция для использования в Deno.serve
export function validationMiddleware(req: Request, path: string, method: string): ValidationResult {
  const validator = new RequestValidator();
  return validator.validateRequest(req, path, method);
}

// Создает error response для результатов валидации
export function createValidationErrorResponse(result: ValidationResult, requestId: string): Response {
  return new Response(JSON.stringify({
    error: {
      code: 'VALIDATION_ERROR',
      message: 'Request validation failed',
      requestId,
      details: {
        errors: result.errors,
        warnings: result.warnings
      }
    }
  }), {
    status: 400,
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': requestId
    }
  });
}