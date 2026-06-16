// Authentication & Authorization Utilities для API Gateway
// Управляет аутентификацией и авторизацией запросов

export interface AuthUser {
  id: string;
  username?: string;
  email?: string;
  roles: string[];
  permissions: string[];
  metadata?: Record<string, any>;
}

export interface AuthToken {
  type: 'bearer' | 'api_key' | 'service_key';
  token: string;
  user?: AuthUser;
  expiresAt?: number;
  scopes: string[];
}

export interface AuthResult {
  success: boolean;
  user?: AuthUser;
  token?: AuthToken;
  error?: string;
  code?: string;
}

export interface AuthorizationContext {
  resource: string;
  action: string;
  context?: Record<string, any>;
}

/**
 * Менеджер аутентификации
 */
export class AuthManager {
  private apiKeys: Map<string, AuthUser> = new Map();
  private users: Map<string, AuthUser> = new Map();
  
  constructor() {
    this.initializeDefaultUsers();
  }

  /**
   * Аутентифицирует запрос
   */
  async authenticate(req: Request): Promise<AuthResult> {
    const authHeader = req.headers.get('authorization');
    const apiKey = req.headers.get('x-api-key');
    const serviceKey = req.headers.get('x-service-key');

    // Проверяем API Key
    if (apiKey) {
      return this.authenticateAPIKey(apiKey);
    }

    // Проверяем Service Key
    if (serviceKey) {
      return this.authenticateServiceKey(serviceKey);
    }

    // Проверяем Bearer Token
    if (authHeader?.startsWith('Bearer ')) {
      const token = authHeader.substring(7);
      return this.authenticateBearerToken(token);
    }

    // Анонимный доступ
    return this.authenticateAnonymous();
  }

  /**
   * Проверяет разрешения пользователя
   */
  async authorize(user: AuthUser | undefined, context: AuthorizationContext): Promise<boolean> {
    if (!user) {
      return false;
    }

    // Проверяем роли
    if (this.hasRequiredRole(user, context)) {
      return true;
    }

    // Проверяем разрешения
    if (this.hasRequiredPermission(user, context)) {
      return true;
    }

    return false;
  }

  /**
   * Аутентификация через API Key
   */
  private async authenticateAPIKey(apiKey: string): Promise<AuthResult> {
    // Проверяем формат API ключа
    if (!apiKey.startsWith('sk-')) {
      return {
        success: false,
        error: 'Invalid API key format',
        code: 'INVALID_API_KEY_FORMAT'
      };
    }

    // Получаем пользователя по API ключу
    const user = this.apiKeys.get(apiKey);
    
    if (!user) {
      return {
        success: false,
        error: 'Invalid API key',
        code: 'INVALID_API_KEY'
      };
    }

    return {
      success: true,
      user,
      token: {
        type: 'api_key',
        token: apiKey,
        user,
        scopes: user.permissions
      }
    };
  }

  /**
   * Аутентификация через Service Key
   */
  private async authenticateServiceKey(serviceKey: string): Promise<AuthResult> {
    // Service keys используются для сервис-сервис взаимодействия
    const serviceUser: AuthUser = {
      id: 'service',
      roles: ['service'],
      permissions: ['service:*'],
      metadata: { type: 'service_account' }
    };

    return {
      success: true,
      user: serviceUser,
      token: {
        type: 'service_key',
        token: serviceKey,
        user: serviceUser,
        scopes: ['service:*']
      }
    };
  }

  /**
   * Аутентификация через Bearer Token (JWT)
   */
  private async authenticateBearerToken(token: string): Promise<AuthResult> {
    try {
      // В реальном проекте здесь была бы проверка JWT
      // Для демонстрации используем простую валидацию
      
      if (token.length < 10) {
        return {
          success: false,
          error: 'Invalid token',
          code: 'INVALID_TOKEN'
        };
      }

      // Ищем пользователя по токену (в реальном проекте - декодирование JWT)
      const user = this.users.get(token) || this.createUserFromToken(token);
      
      if (!user) {
        return {
          success: false,
          error: 'User not found',
          code: 'USER_NOT_FOUND'
        };
      }

      return {
        success: true,
        user,
        token: {
          type: 'bearer',
          token,
          user,
          scopes: user.permissions
        }
      };
      
    } catch (error) {
      return {
        success: false,
        error: 'Token validation failed',
        code: 'TOKEN_VALIDATION_FAILED'
      };
    }
  }

  /**
   * Аутентификация анонимного пользователя
   */
  private async authenticateAnonymous(): Promise<AuthResult> {
    const anonymousUser: AuthUser = {
      id: 'anonymous',
      roles: ['anonymous'],
      permissions: ['public:read']
    };

    return {
      success: true,
      user: anonymousUser,
      token: {
        type: 'bearer',
        token: 'anonymous',
        user: anonymousUser,
        scopes: ['public:read']
      }
    };
  }

  /**
   * Проверяет наличие требуемой роли
   */
  private hasRequiredRole(user: AuthUser, context: AuthorizationContext): boolean {
    const resourceRole = `${context.resource}:${context.action}:role`;
    
    return user.roles.some(role => {
      // Проверяем точное совпадение роли
      if (user.roles.includes(role)) {
        return true;
      }
      
      // Проверяем wildcard паттерны ролей
      if (role.includes('*')) {
        const regex = new RegExp(role.replace(/\*/g, '.*'));
        return regex.test(resourceRole);
      }
      
      return false;
    });
  }

  /**
   * Проверяет наличие требуемого разрешения
   */
  private hasRequiredPermission(user: AuthUser, context: AuthorizationContext): boolean {
    const requiredPermission = `${context.resource}:${context.action}`;
    
    return user.permissions.some(permission => {
      // Точное совпадение разрешения
      if (permission === requiredPermission) {
        return true;
      }
      
      // Wildcard разрешения (например, "service:*" или "*:read")
      if (permission.includes('*')) {
        const regex = new RegExp(permission.replace(/\*/g, '.*'));
        return regex.test(requiredPermission);
      }
      
      // Родительские разрешения (например, "service" дает доступ к "service:*")
      if (permission.endsWith(':*') && requiredPermission.startsWith(permission.slice(0, -1))) {
        return true;
      }
      
      return false;
    });
  }

  /**
   * Создает пользователя из токена (для демонстрации)
   */
  private createUserFromToken(token: string): AuthUser | null {
    // В реальном проекте здесь происходило бы декодирование JWT
    const hash = this.simpleHash(token);
    
    // Создаем пользователя на основе хеша токена
    return {
      id: `user_${hash}`,
      username: `user_${hash}`,
      roles: ['user'],
      permissions: [
        'read:profile',
        'write:profile',
        'read:data',
        'public:read'
      ]
    };
  }

  /**
   * Простая хеш функция
   */
  private simpleHash(str: string): string {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    return Math.abs(hash).toString(36);
  }

  /**
   * Инициализирует стандартных пользователей
   */
  private initializeDefaultUsers(): void {
    // API ключи для демонстрации
    this.apiKeys.set('sk-demo-key-123', {
      id: 'demo-user',
      username: 'demo',
      email: 'demo@example.com',
      roles: ['user'],
      permissions: ['read:demo', 'write:demo', 'public:read']
    });

    this.apiKeys.set('sk-admin-key-456', {
      id: 'admin-user',
      username: 'admin',
      email: 'admin@example.com',
      roles: ['admin'],
      permissions: ['*']
    });

    // Пользователи для Bearer токенов
    this.users.set('valid-jwt-token', {
      id: 'jwt-user',
      username: 'jwtuser',
      roles: ['user'],
      permissions: ['read:data', 'write:data', 'public:read']
    });
  }

  /**
   * Добавляет API ключ
   */
  addAPIKey(apiKey: string, user: AuthUser): void {
    this.apiKeys.set(apiKey, user);
  }

  /**
   * Удаляет API ключ
   */
  removeAPIKey(apiKey: string): void {
    this.apiKeys.delete(apiKey);
  }

  /**
   * Получает статистику аутентификации
   */
  getStats(): any {
    return {
      totalAPIKeys: this.apiKeys.size,
      totalUsers: this.users.size,
      availableUsers: Array.from(this.users.values()).map(u => ({
        id: u.id,
        username: u.username,
        roles: u.roles,
        permissions: u.permissions
      }))
    };
  }
}

/**
 * Middleware для аутентификации
 */
export function authMiddleware(req: Request, publicPaths: string[] = []): AuthResult | null {
  const url = new URL(req.url);
  const path = url.pathname;
  
  // Проверяем, является ли endpoint публичным
  if (publicPaths.some(publicPath => path.startsWith(publicPath))) {
    return {
      success: true,
      user: {
        id: 'public',
        roles: ['public'],
        permissions: ['public:read']
      }
    };
  }
  
  // В реальной реализации здесь был бы вызов AuthManager
  const authManager = new AuthManager();
  return authManager.authenticate(req);
}

/**
 * Middleware для авторизации
 */
export function authorizeMiddleware(user: AuthUser | undefined, context: AuthorizationContext): boolean {
  const authManager = new AuthManager();
  return authManager.authorize(user, context);
}

/**
 * Создает ошибку аутентификации
 */
export function createAuthError(message: string, code: string = 'AUTHENTICATION_FAILED'): Response {
  return new Response(JSON.stringify({
    error: {
      code,
      message,
      timestamp: new Date().toISOString()
    }
  }), {
    status: 401,
    headers: {
      'Content-Type': 'application/json',
      'WWW-Authenticate': 'Bearer realm="api-gateway"'
    }
  });
}

/**
 * Создает ошибку авторизации
 */
export function createAuthzError(message: string = 'Insufficient permissions'): Response {
  return new Response(JSON.stringify({
    error: {
      code: 'AUTHORIZATION_FAILED',
      message,
      timestamp: new Date().toISOString()
    }
  }), {
    status: 403,
    headers: {
      'Content-Type': 'application/json'
    }
  });
}

// Глобальный экземпляр AuthManager
export const authManager = new AuthManager();