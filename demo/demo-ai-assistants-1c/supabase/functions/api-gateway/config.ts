// Конфигурация маршрутизации для API Gateway
// Определяет все доступные сервисы, их инстансы и настройки

export interface ServiceInstance {
  url: string;
  weight: number;
  healthy: boolean;
  lastCheck: number;
  region?: string;
  latency?: number;
}

export interface ServiceConfig {
  name: string;
  version: string;
  instances: ServiceInstance[];
  timeout: number;
  retryCount: number;
  circuitBreaker?: {
    failureThreshold: number;
    timeout: number;
    resetTimeout: number;
  };
  rateLimit?: {
    requestsPerMinute: number;
    burstSize: number;
  };
  cache?: {
    enabled: boolean;
    ttl: number;
    varyBy: string[];
  };
  authentication?: {
    required: boolean;
    scopes: string[];
  };
  rewrite?: {
    path?: string;
    query?: Record<string, string>;
  };
}

export interface RoutingRule {
  pattern: string;
  service: string;
  version: string;
  methods: string[];
  auth?: {
    required: boolean;
    scopes: string[];
  };
  rateLimit?: {
    requestsPerMinute: number;
    burstSize: number;
  };
  cache?: {
    enabled: boolean;
    ttl: number;
  };
  rewrite?: {
    path?: string;
    query?: Record<string, string>;
  };
}

// Конфигурация сервисов
export const serviceConfigs: Record<string, ServiceConfig> = {
  // Architect Service
  'v1/architect': {
    name: 'architect-service',
    version: 'v1',
    instances: [
      {
        url: 'https://api-demo.supabase.co/functions/v1/architect-demo',
        weight: 2,
        healthy: true,
        lastCheck: Date.now(),
        region: 'us-east-1'
      },
      {
        url: 'https://backup-architect.supabase.co/functions/v1/architect-demo',
        weight: 1,
        healthy: true,
        lastCheck: Date.now(),
        region: 'us-west-2'
      }
    ],
    timeout: 8000,
    retryCount: 3,
    circuitBreaker: {
      failureThreshold: 5,
      timeout: 60000,
      resetTimeout: 30000
    },
    rateLimit: {
      requestsPerMinute: 100,
      burstSize: 20
    },
    cache: {
      enabled: true,
      ttl: 300000, // 5 минут
      varyBy: ['authorization', 'accept-language']
    },
    authentication: {
      required: true,
      scopes: ['read:architect', 'write:architect']
    }
  },

  // Business Analyst Service
  'v1/ba': {
    name: 'ba-service',
    version: 'v1',
    instances: [
      {
        url: 'https://api-demo.supabase.co/functions/v1/ba-demo',
        weight: 1,
        healthy: true,
        lastCheck: Date.now(),
        region: 'us-east-1'
      }
    ],
    timeout: 10000,
    retryCount: 2,
    circuitBreaker: {
      failureThreshold: 3,
      timeout: 90000,
      resetTimeout: 60000
    },
    rateLimit: {
      requestsPerMinute: 50,
      burstSize: 10
    },
    cache: {
      enabled: true,
      ttl: 600000, // 10 минут
      varyBy: ['authorization']
    },
    authentication: {
      required: false,
      scopes: ['read:ba']
    }
  },

  // Developer Service
  'v1/developer': {
    name: 'developer-service',
    version: 'v1',
    instances: [
      {
        url: 'https://api-demo.supabase.co/functions/v1/developer-demo',
        weight: 3,
        healthy: true,
        lastCheck: Date.now(),
        region: 'us-east-1'
      },
      {
        url: 'https://dev-backup.supabase.co/functions/v1/developer-demo',
        weight: 1,
        healthy: true,
        lastCheck: Date.now(),
        region: 'us-west-2'
      }
    ],
    timeout: 12000,
    retryCount: 3,
    circuitBreaker: {
      failureThreshold: 4,
      timeout: 120000,
      resetTimeout: 90000
    },
    rateLimit: {
      requestsPerMinute: 200,
      burstSize: 50
    },
    cache: {
      enabled: true,
      ttl: 180000, // 3 минуты
      varyBy: ['authorization', 'x-api-version']
    },
    authentication: {
      required: true,
      scopes: ['read:developer', 'write:developer', 'admin:developer']
    }
  },

  // Project Manager Service
  'v1/pm': {
    name: 'pm-service',
    version: 'v1',
    instances: [
      {
        url: 'https://api-demo.supabase.co/functions/v1/pm-demo',
        weight: 2,
        healthy: true,
        lastCheck: Date.now(),
        region: 'us-east-1'
      }
    ],
    timeout: 7000,
    retryCount: 3,
    circuitBreaker: {
      failureThreshold: 3,
      timeout: 60000,
      resetTimeout: 45000
    },
    rateLimit: {
      requestsPerMinute: 150,
      burstSize: 30
    },
    cache: {
      enabled: true,
      ttl: 240000, // 4 минуты
      varyBy: ['authorization']
    },
    authentication: {
      required: true,
      scopes: ['read:pm', 'write:pm']
    }
  },

  // Tester Service
  'v1/tester': {
    name: 'tester-service',
    version: 'v1',
    instances: [
      {
        url: 'https://api-demo.supabase.co/functions/v1/tester-demo',
        weight: 1,
        healthy: true,
        lastCheck: Date.now(),
        region: 'us-east-1'
      }
    ],
    timeout: 9000,
    retryCount: 2,
    circuitBreaker: {
      failureThreshold: 3,
      timeout: 75000,
      resetTimeout: 60000
    },
    rateLimit: {
      requestsPerMinute: 75,
      burstSize: 15
    },
    cache: {
      enabled: true,
      ttl: 180000, // 3 минуты
      varyBy: ['authorization', 'accept-encoding']
    },
    authentication: {
      required: true,
      scopes: ['read:tester', 'write:tester']
    }
  }
};

// Правила маршрутизации
export const routingRules: RoutingRule[] = [
  // Архитектор сервис
  {
    pattern: '/v1/architect/*',
    service: 'architect-service',
    version: 'v1',
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
    auth: {
      required: true,
      scopes: ['read:architect']
    },
    rateLimit: {
      requestsPerMinute: 100,
      burstSize: 20
    },
    cache: {
      enabled: true,
      ttl: 300000
    }
  },

  // BA сервис
  {
    pattern: '/v1/ba/*',
    service: 'ba-service',
    version: 'v1',
    methods: ['GET', 'POST'],
    auth: {
      required: false,
      scopes: ['read:ba']
    },
    rateLimit: {
      requestsPerMinute: 50,
      burstSize: 10
    },
    cache: {
      enabled: true,
      ttl: 600000
    }
  },

  // Developer сервис
  {
    pattern: '/v1/developer/*',
    service: 'developer-service',
    version: 'v1',
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
    auth: {
      required: true,
      scopes: ['read:developer']
    },
    rateLimit: {
      requestsPerMinute: 200,
      burstSize: 50
    },
    cache: {
      enabled: true,
      ttl: 180000
    }
  },

  // PM сервис
  {
    pattern: '/v1/pm/*',
    service: 'pm-service',
    version: 'v1',
    methods: ['GET', 'POST', 'PUT'],
    auth: {
      required: true,
      scopes: ['read:pm']
    },
    rateLimit: {
      requestsPerMinute: 150,
      burstSize: 30
    },
    cache: {
      enabled: true,
      ttl: 240000
    }
  },

  // Tester сервис
  {
    pattern: '/v1/tester/*',
    service: 'tester-service',
    version: 'v1',
    methods: ['GET', 'POST', 'PUT'],
    auth: {
      required: true,
      scopes: ['read:tester']
    },
    rateLimit: {
      requestsPerMinute: 75,
      burstSize: 15
    },
    cache: {
      enabled: true,
      ttl: 180000
    }
  }
];

// Публичные endpoints (не требуют аутентификации)
export const publicEndpoints = [
  '/health',
  '/status',
  '/metrics',
  '/docs',
  '/openapi.json',
  '/v1/health'
];

// Глобальные настройки API Gateway
export const gatewayConfig = {
  // Общие настройки
  defaultTimeout: 10000,
  defaultRetryCount: 3,
  
  // Rate limiting
  defaultRateLimit: {
    requestsPerMinute: 1000,
    burstSize: 100
  },
  
  // Cache
  defaultCacheTTL: 300000, // 5 минут
  maxCacheSize: 1000, // максимум элементов в кэше
  
  // Circuit Breaker
  circuitBreakerDefaults: {
    failureThreshold: 5,
    timeout: 60000,
    resetTimeout: 30000
  },
  
  // Security
  security: {
    cors: {
      allowedOrigins: ['*'],
      allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
      allowedHeaders: ['authorization', 'x-client-info', 'apikey', 'content-type', 'x-api-key'],
      maxAge: 86400
    },
    headers: {
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'X-XSS-Protection': '1; mode=block',
      'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
      'Referrer-Policy': 'strict-origin-when-cross-origin'
    }
  },
  
  // Monitoring
  monitoring: {
    enabled: true,
    logLevel: 'info',
    metricsInterval: 60000
  }
};

// Функции для работы с конфигурацией
export function getServiceConfigByPath(path: string): ServiceConfig | null {
  const pathParts = path.split('/').filter(p => p);
  if (pathParts.length < 2) return null;
  
  const version = pathParts[0] || 'v1';
  const serviceName = pathParts[1];
  const serviceKey = `${version}/${serviceName}`;
  
  return serviceConfigs[serviceKey] || null;
}

export function matchRoutingRule(path: string, method: string): RoutingRule | null {
  return routingRules.find(rule => {
    // Простое сопоставление паттерна (в реальном проекте используйте regex)
    const pattern = rule.pattern.replace('/*', '');
    const pathMatch = path.startsWith(pattern) || path === pattern.replace('/*', '');
    const methodMatch = rule.methods.includes(method);
    
    return pathMatch && methodMatch;
  }) || null;
}

export function isPublicEndpoint(path: string): boolean {
  return publicEndpoints.some(endpoint => {
    return path === endpoint || path.startsWith(endpoint + '/');
  });
}