// Circuit Breaker Utilities для API Gateway
// Предохранитель для защиты сервисов от каскадных сбоев

export enum CircuitState {
  CLOSED = 'CLOSED',     // Нормальная работа
  OPEN = 'OPEN',         // Заблокировано
  HALF_OPEN = 'HALF_OPEN' // Тестирование восстановления
}

export interface CircuitBreakerConfig {
  failureThreshold: number;      // Количество неудач для переключения в OPEN
  successThreshold: number;      // Количество успехов для переключения в CLOSED (из HALF_OPEN)
  timeout: number;               // Время ожидания перед попыткой перехода в HALF_OPEN
  resetTimeout: number;          // Время ожидания перед автоматическим переходом в HALF_OPEN
  monitoringPeriod: number;      // Период мониторинга для подсчета неудач
  expectedErrors?: number[];     // HTTP коды ошибок, которые считаются "ожидаемыми"
  fallback?: (error: Error) => any; // Функция fallback
}

export interface CircuitBreakerStats {
  state: CircuitState;
  totalRequests: number;
  successfulRequests: number;
  failedRequests: number;
  blockedRequests: number;
  lastFailureTime?: number;
  lastSuccessTime?: number;
  failureRate: number;
  currentWindowFailures: number;
  timeInState: number;
}

/**
 * Circuit Breaker для защиты внешних сервисов
 */
export class CircuitBreaker {
  private state: CircuitState = CircuitState.CLOSED;
  private config: CircuitBreakerConfig;
  private stats: CircuitBreakerStats;
  private failureTimestamps: number[] = [];
  private successTimestamps: number[] = [];
  private stateChangeTime: number;

  constructor(config: Partial<CircuitBreakerConfig> = {}) {
    this.config = {
      failureThreshold: 5,
      successThreshold: 2,
      timeout: 60000,
      resetTimeout: 30000,
      monitoringPeriod: 60000,
      expectedErrors: [400, 401, 403, 404, 409, 422, 429],
      ...config
    };

    this.stats = {
      state: this.state,
      totalRequests: 0,
      successfulRequests: 0,
      failedRequests: 0,
      blockedRequests: 0,
      failureRate: 0,
      currentWindowFailures: 0,
      timeInState: 0
    };

    this.stateChangeTime = Date.now();

    // Запускаем мониторинг состояния
    this.startMonitoring();
  }

  /**
   * Выполняет запрос с защитой circuit breaker
   */
  async execute<T>(operation: () => Promise<T>): Promise<T> {
    // Проверяем состояние circuit breaker
    if (!this.canExecute()) {
      this.stats.blockedRequests++;
      throw new Error(`Circuit breaker is ${this.state}`);
    }

    try {
      this.stats.totalRequests++;
      
      // Выполняем операцию
      const result = await operation();
      
      // Записываем успех
      this.recordSuccess();
      
      return result;
      
    } catch (error) {
      // Записываем неудачу
      this.recordFailure(error as Error);
      throw error;
    }
  }

  /**
   * Проверяет, можно ли выполнить запрос
   */
  private canExecute(): boolean {
    switch (this.state) {
      case CircuitState.CLOSED:
        return true;
      
      case CircuitState.OPEN:
        // Проверяем, прошло ли достаточно времени для попытки восстановления
        if (Date.now() - this.stateChangeTime >= this.config.resetTimeout) {
          this.transitionToHalfOpen();
          return true;
        }
        return false;
      
      case CircuitState.HALF_OPEN:
        return true;
      
      default:
        return false;
    }
  }

  /**
   * Записывает успешный запрос
   */
  private recordSuccess(): void {
    const now = Date.now();
    this.successTimestamps.push(now);
    
    // Очищаем старые записи
    this.cleanupOldTimestamps(now);
    
    this.stats.successfulRequests++;
    this.stats.lastSuccessTime = now;
    
    // Обновляем failure rate
    this.updateFailureRate(now);
    
    // Обрабатываем переход состояния
    if (this.state === CircuitState.HALF_OPEN) {
      if (this.successTimestamps.length >= this.config.successThreshold) {
        this.transitionToClosed();
      }
    } else if (this.state === CircuitState.CLOSED) {
      // В закрытом состоянии успехи нас не особо интересуют
      // Но можем сбросить счетчик неудач
      this.failureTimestamps = [];
      this.stats.currentWindowFailures = 0;
    }
  }

  /**
   * Записывает неудачный запрос
   */
  private recordFailure(error: Error): void {
    const now = Date.now();
    this.failureTimestamps.push(now);
    
    // Очищаем старые записи
    this.cleanupOldTimestamps(now);
    
    this.stats.failedRequests++;
    this.stats.lastFailureTime = now;
    
    // Обновляем failure rate
    this.updateFailureRate(now);
    
    // Определяем, является ли ошибка "ожидаемой"
    const isExpectedError = this.isExpectedError(error);
    
    // Обрабатываем переход состояния
    if (this.state === CircuitState.CLOSED) {
      if (!isExpectedError && this.stats.currentWindowFailures >= this.config.failureThreshold) {
        this.transitionToOpen();
      }
    } else if (this.state === CircuitState.HALF_OPEN) {
      // В полуоткрытом состоянии любая неудача возвращает нас в открытое
      this.transitionToOpen();
    }
  }

  /**
   * Переходит в закрытое состояние
   */
  private transitionToClosed(): void {
    this.state = CircuitState.CLOSED;
    this.stateChangeTime = Date.now();
    
    // Сбрасываем статистику
    this.failureTimestamps = [];
    this.stats.currentWindowFailures = 0;
    
    console.log(`Circuit breaker transitioned to CLOSED`);
  }

  /**
   * Переходит в открытое состояние
   */
  private transitionToOpen(): void {
    this.state = CircuitState.OPEN;
    this.stateChangeTime = Date.now();
    
    console.log(`Circuit breaker transitioned to OPEN`);
  }

  /**
   * Переходит в полуоткрытое состояние
   */
  private transitionToHalfOpen(): void {
    this.state = CircuitState.HALF_OPEN;
    this.stateChangeTime = Date.now();
    
    console.log(`Circuit breaker transitioned to HALF_OPEN`);
  }

  /**
   * Обновляет failure rate
   */
  private updateFailureRate(now: number): void {
    const recentFailures = this.failureTimestamps.filter(t => now - t <= this.config.monitoringPeriod).length;
    const recentRequests = this.stats.totalRequests - 
      (this.failureTimestamps.length + this.successTimestamps.filter(t => now - t > this.config.monitoringPeriod).length);
    
    this.stats.currentWindowFailures = recentFailures;
    this.stats.failureRate = recentRequests > 0 ? (recentFailures / recentRequests) * 100 : 0;
  }

  /**
   * Очищает старые записи
   */
  private cleanupOldTimestamps(now: number): void {
    const cutoff = now - this.config.monitoringPeriod;
    
    this.failureTimestamps = this.failureTimestamps.filter(t => t > cutoff);
    this.successTimestamps = this.successTimestamps.filter(t => t > cutoff);
  }

  /**
   * Проверяет, является ли ошибка "ожидаемой"
   */
  private isExpectedError(error: Error): boolean {
    // Простая проверка по message (в реальном проекте нужно парсить HTTP коды)
    const errorMessage = error.message.toLowerCase();
    
    // Проверяем на ожидаемые ошибки (4xx)
    const expectedPatterns = [
      '401', '403', '404', '409', '422', '429'
    ];
    
    return expectedPatterns.some(pattern => errorMessage.includes(pattern));
  }

  /**
   * Запускает мониторинг состояния
   */
  private startMonitoring(): void {
    setInterval(() => {
      this.stats.state = this.state;
      this.stats.timeInState = Date.now() - this.stateChangeTime;
      
      // Автоматический переход из OPEN в HALF_OPEN
      if (this.state === CircuitState.OPEN && 
          Date.now() - this.stateChangeTime >= this.config.resetTimeout) {
        this.transitionToHalfOpen();
      }
      
      // Очистка старых записей
      this.cleanupOldTimestamps(Date.now());
      
    }, 5000); // Проверяем каждые 5 секунд
  }

  /**
   * Принудительно переводит в открытое состояние
   */
  forceOpen(): void {
    this.transitionToOpen();
  }

  /**
   * Принудительно переводит в закрытое состояние
   */
  forceClose(): void {
    this.transitionToClosed();
  }

  /**
   * Получает текущую статистику
   */
  getStats(): CircuitBreakerStats {
    return {
      ...this.stats,
      state: this.state,
      timeInState: Date.now() - this.stateChangeTime
    };
  }

  /**
   * Получает текущее состояние
   */
  getState(): CircuitState {
    return this.state;
  }

  /**
   * Проверяет, заблокирован ли circuit breaker
   */
  isOpen(): boolean {
    return this.state === CircuitState.OPEN;
  }
}

/**
 * Управляет множественными circuit breaker'ами для разных сервисов
 */
export class CircuitBreakerManager {
  private breakers: Map<string, CircuitBreaker> = new Map();

  /**
   * Получает или создает circuit breaker для сервиса
   */
  getBreaker(serviceName: string, config?: Partial<CircuitBreakerConfig>): CircuitBreaker {
    if (!this.breakers.has(serviceName)) {
      this.breakers.set(serviceName, new CircuitBreaker(config));
    }
    
    return this.breakers.get(serviceName)!;
  }

  /**
   * Выполняет операцию с circuit breaker для сервиса
   */
  async execute<T>(serviceName: string, operation: () => Promise<T>, config?: Partial<CircuitBreakerConfig>): Promise<T> {
    const breaker = this.getBreaker(serviceName, config);
    return breaker.execute(operation);
  }

  /**
   * Получает статистику всех circuit breaker'ов
   */
  getAllStats(): Record<string, CircuitBreakerStats> {
    const stats: Record<string, CircuitBreakerStats> = {};
    
    for (const [name, breaker] of this.breakers) {
      stats[name] = breaker.getStats();
    }
    
    return stats;
  }

  /**
   * Сбрасывает все circuit breaker'ы
   */
  resetAll(): void {
    for (const breaker of this.breakers.values()) {
      breaker.forceClose();
    }
  }

  /**
   * Получает список всех сервисов
   */
  getServices(): string[] {
    return Array.from(this.breakers.keys());
  }
}

// Глобальный экземпляр менеджера circuit breaker
export const circuitBreakerManager = new CircuitBreakerManager();

// Middleware для circuit breaker
export function circuitBreakerMiddleware(serviceName: string, config?: Partial<CircuitBreakerConfig>) {
  const breaker = circuitBreakerManager.getBreaker(serviceName, config);
  
  return async <T>(operation: () => Promise<T>): Promise<T> => {
    return breaker.execute(operation);
  };
}