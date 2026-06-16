/**
 * Health Check Middleware для Node.js приложений
 * Предоставляет эндпоинты для мониторинга состояния сервисов
 */

const express = require('express');
const prometheus = require('prom-client');
const { createPool } = require('mysql2/promise');
const redis = require('redis');

class HealthCheckMiddleware {
  constructor(config = {}) {
    this.config = {
      healthCheckPath: '/health',
      readyCheckPath: '/ready',
      liveCheckPath: '/live',
      metricsPath: '/metrics',
      detailedChecks: true,
      timeout: 5000,
      externalAPIs: {},
      ...config
    };

    // Prometheus метрики
    this.initializeMetrics();
    
    // Подключения
    this.database = config.database;
    this.redis = config.redis;
    
    // Метрики времени работы
    this.startTime = Date.now();
  }

  /**
   * Инициализация Prometheus метрик
   */
  initializeMetrics() {
    // Счетчик запросов
    this.requestCounter = new prometheus.Counter({
      name: 'http_requests_total',
      help: 'Total number of HTTP requests',
      labelNames: ['method', 'route', 'status_code']
    });

    // Гистограмма времени ответа
    this.responseTime = new prometheus.Histogram({
      name: 'http_request_duration_seconds',
      help: 'Duration of HTTP requests in seconds',
      labelNames: ['method', 'route'],
      buckets: [0.1, 0.3, 0.5, 0.7, 1, 3, 5, 7, 10]
    });

    // Gauge метрики
    this.uptimeGauge = new prometheus.Gauge({
      name: 'app_uptime_seconds',
      help: 'Application uptime in seconds'
    });

    this.memoryUsageGauge = new prometheus.Gauge({
      name: 'app_memory_usage_bytes',
      help: 'Application memory usage in bytes',
      labelNames: ['type']
    });

    this.cpuUsageGauge = new prometheus.Gauge({
      name: 'app_cpu_usage_percent',
      help: 'Application CPU usage percentage'
    });

    // Обновление метрик каждую секунду
    setInterval(() => {
      this.updateSystemMetrics();
    }, 1000);

    // Обновление uptime метрики
    setInterval(() => {
      this.uptimeGauge.set((Date.now() - this.startTime) / 1000);
    }, 5000);
  }

  /**
   * Express middleware для мониторинга запросов
   */
  monitoringMiddleware() {
    return (req, res, next) => {
      const start = Date.now();
      
      res.on('finish', () => {
        const duration = (Date.now() - start) / 1000;
        
        this.requestCounter
          .labels(req.method, req.route?.path || req.path, res.statusCode)
          .inc();
          
        this.responseTime
          .labels(req.method, req.route?.path || req.path)
          .observe(duration);
      });
      
      next();
    };
  }

  /**
   * Health check endpoint
   */
  async health() {
    const checks = await this.performHealthChecks();
    const status = this.determineOverallStatus(checks);
    const httpStatus = status === 'healthy' ? 200 : 503;

    const response = {
      status,
      timestamp: new Date().toISOString(),
      version: process.env.npm_package_version || '1.0.0',
      uptime: Math.floor((Date.now() - this.startTime) / 1000),
      checks: this.config.detailedChecks ? checks : undefined
    };

    return res.status(httpStatus).json(response);
  }

  /**
   * Ready check endpoint (Kubernetes)
   */
  async ready() {
    const ready = await this.checkReadiness();
    
    const response = {
      ready,
      timestamp: new Date().toISOString(),
      checks: {
        database: await this.checkDatabaseConnection(),
        redis: await this.checkRedisConnection(),
        external_apis: await this.checkExternalAPIs()
      }
    };

    return res.status(ready ? 200 : 503).json(response);
  }

  /**
   * Live check endpoint (Kubernetes)
   */
  async live() {
    const response = {
      live: true,
      timestamp: new Date().toISOString(),
      uptime: Math.floor((Date.now() - this.startTime) / 1000)
    };

    return res.status(200).json(response);
  }

  /**
   * Prometheus metrics endpoint
   */
  async metrics() {
    res.set('Content-Type', prometheus.register.contentType);
    return res.end(await prometheus.register.metrics());
  }

  /**
   * Выполнение всех проверок состояния
   */
  async performHealthChecks() {
    const checks = {};

    // Системные проверки
    checks.system = await this.checkSystem();
    
    // База данных
    checks.database = await this.checkDatabaseConnection();
    
    // Redis
    checks.redis = await this.checkRedisConnection();
    
    // Внешние API
    checks.external_apis = await this.checkExternalAPIs();
    
    // Память
    checks.memory = await this.checkMemoryUsage();
    
    // Дисковое пространство
    checks.disk_space = await this.checkDiskSpace();

    return checks;
  }

  /**
   * Проверка готовности сервиса
   */
  async checkReadiness() {
    const [dbOk, redisOk] = await Promise.all([
      this.checkDatabaseConnection(),
      this.checkRedisConnection()
    ]);
    
    return dbOk.status && redisOk.status;
  }

  /**
   * Проверка системных ресурсов
   */
  async checkSystem() {
    const os = require('os');
    const loadAvg = os.loadavg();
    const cpuUsage = await this.getCpuUsage();
    const memoryUsage = this.getMemoryUsage();
    
    const healthy = (
      loadAvg[0] < 2.0 && // CPU load average (1 min)
      cpuUsage < 80 &&    // CPU usage %
      memoryUsage < 85    // Memory usage %
    );

    return {
      status: healthy,
      data: {
        load_average: loadAvg,
        cpu_usage_percent: cpuUsage,
        memory_usage_percent: memoryUsage,
        free_memory_gb: (os.freemem() / 1024 / 1024 / 1024).toFixed(2),
        total_memory_gb: (os.totalmem() / 1024 / 1024 / 1024).toFixed(2)
      }
    };
  }

  /**
   * Проверка подключения к базе данных
   */
  async checkDatabaseConnection() {
    try {
      if (!this.database) {
        return { status: false, error: 'Database not configured' };
      }
      
      const start = Date.now();
      await this.database.query('SELECT 1');
      const duration = Date.now() - start;
      
      const healthy = duration < 1000; // Response time should be < 1 second
      
      return {
        status: healthy,
        duration: duration,
        connection_pool: await this.getConnectionPoolInfo()
      };
    } catch (error) {
      return {
        status: false,
        error: error.message
      };
    }
  }

  /**
   * Проверка подключения к Redis
   */
  async checkRedisConnection() {
    try {
      if (!this.redis) {
        return { status: false, error: 'Redis not configured' };
      }
      
      const start = Date.now();
      await this.redis.ping();
      const duration = Date.now() - start;
      
      const healthy = duration < 500; // Response time should be < 0.5 seconds
      
      return {
        status: healthy,
        duration: duration,
        info: await this.redis.info()
      };
    } catch (error) {
      return {
        status: false,
        error: error.message
      };
    }
  }

  /**
   * Проверка внешних API
   */
  async checkExternalAPIs() {
    const apis = this.config.externalAPIs;
    const results = {};
    const apiPromises = [];

    for (const [name, config] of Object.entries(apis)) {
      apiPromises.push(
        this.checkApi(name, config).then(result => ({ name, result }))
      );
    }

    const apiResults = await Promise.allSettled(apiPromises);
    
    for (const { name, result } of apiResults) {
      if (result.status === 'fulfilled') {
        results[name] = result.value;
      } else {
        results[name] = {
          status: false,
          error: result.reason.message
        };
      }
    }

    const allHealthy = Object.keys(results).length === 0 || 
      Object.values(results).every(result => result.status);

    return {
      status: allHealthy,
      apis: results
    };
  }

  /**
   * Проверка конкретного API
   */
  async checkApi(name, config) {
    const axios = require('axios');
    
    try {
      const start = Date.now();
      const response = await axios.get(config.url, {
        timeout: config.timeout || 5000,
        validateStatus: () => true
      });
      const duration = Date.now() - start;
      
      const healthy = response.status >= 200 && response.status < 300;
      
      return {
        status: healthy,
        duration: duration,
        status_code: response.status
      };
    } catch (error) {
      return {
        status: false,
        error: error.message
      };
    }
  }

  /**
   * Проверка использования памяти
   */
  async checkMemoryUsage() {
    const memUsage = process.memoryUsage();
    const totalHeap = memUsage.heapTotal;
    const usedHeap = memUsage.heapUsed;
    const external = memUsage.external;
    
    const heapPercent = (usedHeap / totalHeap) * 100;
    const totalPercent = ((usedHeap + external) / require('os').totalmem()) * 100;
    
    const healthy = heapPercent < 80;

    return {
      status: healthy,
      data: {
        heap_usage_percent: heapPercent.toFixed(2),
        total_usage_percent: totalPercent.toFixed(2),
        heap_used_mb: (usedHeap / 1024 / 1024).toFixed(2),
        heap_total_mb: (totalHeap / 1024 / 1024).toFixed(2),
        external_mb: (external / 1024 / 1024).toFixed(2)
      }
    };
  }

  /**
   * Проверка дискового пространства
   */
  async checkDiskSpace() {
    const fs = require('fs').promises;
    const os = require('os');
    
    try {
      const stats = await fs.stat(__dirname);
      const { available, total } = require('fs').statSync(__dirname);
      
      const freeBytes = available;
      const totalBytes = total;
      const usagePercent = ((totalBytes - freeBytes) / totalBytes) * 100;
      
      const healthy = usagePercent < 85;

      return {
        status: healthy,
        data: {
          usage_percent: usagePercent.toFixed(2),
          free_gb: (freeBytes / 1024 / 1024 / 1024).toFixed(2),
          total_gb: (totalBytes / 1024 / 1024 / 1024).toFixed(2)
        }
      };
    } catch (error) {
      return {
        status: false,
        error: error.message
      };
    }
  }

  /**
   * Обновление системных метрик
   */
  async updateSystemMetrics() {
    const os = require('os');
    const memUsage = process.memoryUsage();
    
    this.memoryUsageGauge.labels('heap_used').set(memUsage.heapUsed);
    this.memoryUsageGauge.labels('heap_total').set(memUsage.heapTotal);
    this.memoryUsageGauge.labels('external').set(memUsage.external);
    this.memoryUsageGauge.labels('rss').set(memUsage.rss);
    
    this.cpuUsageGauge.set(await this.getCpuUsage());
  }

  /**
   * Получение использования CPU
   */
  async getCpuUsage() {
    const startUsage = process.cpuUsage();
    await new Promise(resolve => setTimeout(resolve, 100));
    const endUsage = process.cpuUsage(startUsage);
    
    const totalUsage = endUsage.user + endUsage.system;
    const cpuUsage = (totalUsage / 100000) * 100; // Конвертация в проценты
    
    return Math.min(cpuUsage, 100);
  }

  /**
   * Получение использования памяти
   */
  getMemoryUsage() {
    const memUsage = process.memoryUsage();
    const totalMem = require('os').totalmem();
    const usagePercent = ((memUsage.heapUsed + memUsage.external) / totalMem) * 100;
    
    return Math.min(usagePercent, 100);
  }

  /**
   * Получение информации о пуле соединений
   */
  async getConnectionPoolInfo() {
    try {
      if (this.database.pool) {
        const [rows] = await this.database.pool.query('SHOW STATUS LIKE "Threads_connected"');
        return {
          active_connections: rows[0].Value,
          max_connections: 'config'
        };
      }
      return { error: 'No connection pool available' };
    } catch (error) {
      return { error: error.message };
    }
  }

  /**
   * Определение общего статуса системы
   */
  determineOverallStatus(checks) {
    // Если есть критические ошибки
    for (const check of Object.values(checks)) {
      if (check.status === false) {
        return 'unhealthy';
      }
    }
    
    // Если есть предупреждения
    for (const check of Object.values(checks)) {
      if (check.status === 'warning') {
        return 'degraded';
      }
    }
    
    return 'healthy';
  }

  /**
   * Получение Express router
   */
  getRouter() {
    const router = express.Router();
    
    // Мониторинг запросов
    router.use(this.monitoringMiddleware());
    
    // Health check endpoints
    router.get(this.config.healthCheckPath, this.health.bind(this));
    router.get(this.config.readyCheckPath, this.ready.bind(this));
    router.get(this.config.liveCheckPath, this.live.bind(this));
    router.get(this.config.metricsPath, this.metrics.bind(this));
    
    return router;
  }
}

module.exports = HealthCheckMiddleware;

// Пример использования
if (require.main === module) {
  const app = express();
  const healthCheck = new HealthCheckMiddleware({
    externalAPIs: {
      'payment_api': { url: 'http://payment-service:8080/health' },
      'notification_api': { url: 'http://notification-service:8080/health' }
    }
  });
  
  app.use(healthCheck.getRouter());
  
  app.get('/', (req, res) => {
    res.json({ message: 'Service is running' });
  });
  
  const PORT = process.env.PORT || 3000;
  app.listen(PORT, () => {
    console.log(`Health check service running on port ${PORT}`);
  });
}