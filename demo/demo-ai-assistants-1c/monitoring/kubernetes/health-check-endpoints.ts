/**
 * Health Check Endpoints для Demo AI Assistants
 * Поддерживает liveness, readiness, startup probes
 */

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";

// Health check состояние
const healthState = {
  startup: false,
  ready: false,
  alive: true,
  dependencies: {
    database: false,
    cache: false,
    external_services: false
  },
  metrics: {
    uptime: Date.now(),
    startTime: Date.now(),
    lastCheck: Date.now()
  }
};

// Подключение к базе данных
async function checkDatabase(): Promise<boolean> {
  try {
    // Проверка Supabase подключения
    const response = await fetch(`${Deno.env.get('SUPABASE_URL')}/rest/v1/health`, {
      headers: {
        'apikey': Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') || '',
        'Content-Type': 'application/json'
      }
    });
    return response.ok;
  } catch (error) {
    console.error('Database health check failed:', error);
    return false;
  }
}

// Проверка Redis/cache
async function checkCache(): Promise<boolean> {
  try {
    // Mock проверка кеша (в реальном проекте - подключение к Redis)
    const cacheUrl = Deno.env.get('REDIS_URL') || 'redis://localhost:6379';
    // Здесь был бы Redis клиент, но пока возвращаем true
    return true;
  } catch (error) {
    console.error('Cache health check failed:', error);
    return false;
  }
}

// Проверка внешних сервисов
async function checkExternalServices(): Promise<boolean> {
  try {
    const externalApis = [
      'https://api.openai.com/health',
      'https://api.minimax.chat/health'
    ];
    
    const checks = await Promise.allSettled(
      externalApis.map(url => 
        fetch(url, { method: 'HEAD', timeout: 5000 })
      )
    );
    
    return checks.every(result => 
      result.status === 'fulfilled' && result.value.ok
    );
  } catch (error) {
    console.error('External services health check failed:', error);
    return false;
  }
}

// Полная проверка здоровья
async function performHealthCheck(): Promise<typeof healthState> {
  const now = Date.now();
  
  // Проверка зависимостей
  const [dbStatus, cacheStatus, externalStatus] = await Promise.all([
    checkDatabase(),
    checkCache(),
    checkExternalServices()
  ]);
  
  healthState.dependencies.database = dbStatus;
  healthState.dependencies.cache = cacheStatus;
  healthState.dependencies.external_services = externalStatus;
  healthState.metrics.lastCheck = now;
  
  // Определение состояний
  healthState.startup = dbStatus || healthState.startup; // Старт считается завершенным при первом успешном DB чеке
  healthState.ready = dbStatus && cacheStatus && healthState.startup;
  healthState.alive = healthState.alive; // Всегда alive, если сервис работает
  
  return healthState;
}

// Liveness endpoint
async function livenessHandler(req: Request): Promise<Response> {
  const state = await performHealthCheck();
  
  const isAlive = state.alive;
  const status = isAlive ? 200 : 503;
  
  return new Response(JSON.stringify({
    status: isAlive ? 'alive' : 'dead',
    timestamp: new Date().toISOString(),
    uptime: Date.now() - state.metrics.startTime,
    checks: {
      alive: state.alive
    }
  }), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache, no-store, must-revalidate'
    }
  });
}

// Readiness endpoint
async function readinessHandler(req: Request): Promise<Response> {
  const state = await performHealthCheck();
  
  const isReady = state.ready;
  const status = isReady ? 200 : 503;
  
  return new Response(JSON.stringify({
    status: isReady ? 'ready' : 'not_ready',
    timestamp: new Date().toISOString(),
    uptime: Date.now() - state.metrics.startTime,
    checks: {
      ready: state.ready,
      dependencies: state.dependencies
    }
  }), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache, no-store, must-revalidate'
    }
  });
}

// Startup endpoint
async function startupHandler(req: Request): Promise<Response> {
  const state = await performHealthCheck();
  
  const hasStarted = state.startup;
  const status = hasStarted ? 200 : 503;
  
  return new Response(JSON.stringify({
    status: hasStarted ? 'started' : 'starting',
    timestamp: new Date().toISOString(),
    startupTime: state.startup ? Date.now() - state.metrics.startTime : null,
    checks: {
      started: state.startup,
      dependencies: {
        database: state.dependencies.database,
        cache: state.dependencies.cache
      }
    }
  }), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache, no-store, must-revalidate'
    }
  });
}

// Детальный health check
async function detailedHealthHandler(req: Request): Promise<Response> {
  const state = await performHealthCheck();
  
  const overallStatus = state.ready ? 'healthy' : 
                       state.startup ? 'degraded' : 'unhealthy';
  const status = state.ready ? 200 : 503;
  
  return new Response(JSON.stringify({
    status: overallStatus,
    timestamp: new Date().toISOString(),
    version: Deno.env.get('APP_VERSION') || '1.0.0',
    environment: Deno.env.get('ENVIRONMENT') || 'development',
    checks: {
      liveness: {
        status: state.alive ? 'pass' : 'fail',
        timestamp: new Date().toISOString()
      },
      readiness: {
        status: state.ready ? 'pass' : 'fail',
        timestamp: new Date().toISOString()
      },
      startup: {
        status: state.startup ? 'pass' : 'fail',
        timestamp: new Date().toISOString(),
        startupTime: state.startup ? Date.now() - state.metrics.startTime : null
      },
      dependencies: {
        database: {
          status: state.dependencies.database ? 'healthy' : 'unhealthy',
          service: 'PostgreSQL/Supabase'
        },
        cache: {
          status: state.dependencies.cache ? 'healthy' : 'unhealthy',
          service: 'Redis'
        },
        external_services: {
          status: state.dependencies.external_services ? 'healthy' : 'degraded',
          service: 'External APIs'
        }
      }
    },
    metrics: {
      uptime: Date.now() - state.metrics.startTime,
      memoryUsage: (Deno as any).memoryUsage?.() || null,
      loadAverage: (Deno as any).osLoadavg?.() || null
    }
  }), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache, no-store, must-revalidate'
    }
  });
}

// Metrics endpoint для Prometheus
async function metricsHandler(req: Request): Promise<Response> {
  const state = await performHealthCheck();
  
  const metrics = `# HELP health_check_status Health check status (1 = pass, 0 = fail)
# TYPE health_check_status gauge
health_check_liveness_status ${state.alive ? 1 : 0}
health_check_readiness_status ${state.ready ? 1 : 0} 
health_check_startup_status ${state.startup ? 1 : 0}

# Database health
health_check_database_status ${state.dependencies.database ? 1 : 0}

# Cache health
health_check_cache_status ${state.dependencies.cache ? 1 : 0}

# External services health
health_check_external_services_status ${state.dependencies.external_services ? 1 : 0}

# Uptime in seconds
# TYPE health_check_uptime_seconds gauge
health_check_uptime_seconds ${(Date.now() - state.metrics.startTime) / 1000}
`;

  return new Response(metrics, {
    headers: {
      'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'
    }
  });
}

// Основной сервер
serve(async (req: Request) => {
  const url = new URL(req.url);
  const path = url.pathname;
  
  // CORS заголовки
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  };
  
  if (req.method === 'OPTIONS') {
    return new Response(null, { 
      status: 200, 
      headers: corsHeaders 
    });
  }
  
  try {
    let response: Response;
    
    switch (path) {
      case '/health/live':
      case '/health/liveness':
        response = await livenessHandler(req);
        break;
        
      case '/health/ready':
      case '/health/readiness':
        response = await readinessHandler(req);
        break;
        
      case '/health/startup':
        response = await startupHandler(req);
        break;
        
      case '/health':
      case '/health/detailed':
        response = await detailedHealthHandler(req);
        break;
        
      case '/metrics':
        response = await metricsHandler(req);
        break;
        
      default:
        response = new Response(JSON.stringify({
          error: 'Not Found',
          message: 'Available endpoints: /health/live, /health/ready, /health/startup, /health, /metrics'
        }), {
          status: 404,
          headers: { 'Content-Type': 'application/json' }
        });
    }
    
    // Добавляем CORS заголовки
    const headers = new Headers(response.headers);
    Object.entries(corsHeaders).forEach(([key, value]) => {
      headers.set(key, value);
    });
    
    return new Response(await response.text(), {
      status: response.status,
      headers
    });
    
  } catch (error) {
    console.error('Health check error:', error);
    
    return new Response(JSON.stringify({
      status: 'error',
      message: 'Internal server error',
      timestamp: new Date().toISOString()
    }), {
      status: 500,
      headers: {
        'Content-Type': 'application/json',
        ...corsHeaders
      }
    });
  }
}, {
  port: 8080,
  hostname: '0.0.0.0'
});

console.log('Health check server started on port 8080');
console.log('Available endpoints:');
console.log('  GET /health/live     - Liveness probe');
console.log('  GET /health/ready    - Readiness probe');
console.log('  GET /health/startup  - Startup probe');
console.log('  GET /health          - Detailed health check');
console.log('  GET /metrics         - Prometheus metrics');