  // EventEmitter polyfill for browser compatibility

export interface WebhookEndpoint {
  id: string;
  name: string;
  url: string;
  events: string[];
  secret?: string;
  active: boolean;
  retryPolicy: RetryPolicy;
  transformation?: WebhookTransformation;
  filters?: WebhookFilter[];
  timeout: number;
  maxRetries: number;
  metadata?: Record<string, any>;
}

export interface WebhookTransformation {
  request?: {
    headers?: Record<string, string>;
    body?: string; // JavaScript function
  };
  response?: {
    headers?: Record<string, string>;
    body?: string; // JavaScript function
  };
}

export interface WebhookFilter {
  field: string;
  operator: 'equals' | 'contains' | 'regex' | 'in' | 'not_in';
  value: string | string[];
  negate?: boolean;
}

export interface RetryPolicy {
  maxAttempts: number;
  backoffStrategy: 'exponential' | 'linear' | 'fixed';
  baseDelay: number;
  maxDelay?: number;
  retryableStatusCodes?: number[];
  retryableErrors?: string[];
}

export interface WebhookEvent {
  id: string;
  source: string;
  type: string;
  data: any;
  timestamp: Date;
  metadata?: Record<string, any>;
}

export interface WebhookDelivery {
  id: string;
  webhookId: string;
  event: WebhookEvent;
  status: 'pending' | 'sending' | 'delivered' | 'failed' | 'retrying';
  attempts: number;
  lastAttempt?: Date;
  response?: WebhookResponse;
  error?: string;
  createdAt: Date;
}

export interface WebhookResponse {
  status: number;
  headers: Record<string, string>;
  body: string;
  timing: {
    startTime: number;
    endTime: number;
    duration: number;
  };
}

export interface WebhookMetrics {
  totalEvents: number;
  deliveredEvents: number;
  failedEvents: number;
  retryEvents: number;
  averageDeliveryTime: number;
  webhookMetrics: Map<string, WebhookEndpointMetrics>;
  lastEvent?: Date;
  errorRate: number;
}

export interface WebhookEndpointMetrics {
  endpointId: string;
  totalDeliveries: number;
  successfulDeliveries: number;
  failedDeliveries: number;
  retryDeliveries: number;
  averageResponseTime: number;
  lastDelivery?: Date;
  errorRate: number;
  successRate: number;
}

export class WebhookService extends EventEmitter {
  private endpoints: Map<string, WebhookEndpoint> = new Map();
  private eventQueue: WebhookEvent[] = [];
  private deliveryQueue: WebhookDelivery[] = [];
  private deliveredEvents: Set<string> = new Set();
  private metrics: WebhookMetrics;
  private processing: boolean = false;
  private retryTimers: Map<string, NodeJS.Timeout> = new Map();

  constructor() {
    super();
    this.metrics = this.initializeMetrics();
    this.startProcessing();
  }

  /**
   * Регистрирует новый webhook endpoint
   */
  async registerEndpoint(endpoint: WebhookEndpoint): Promise<void> {
    if (this.endpoints.has(endpoint.id)) {
      throw new Error(`Webhook endpoint with id '${endpoint.id}' already exists`);
    }

    this.endpoints.set(endpoint.id, endpoint);
    this.initializeEndpointMetrics(endpoint.id);

    this.emit('webhook-registered', { endpointId: endpoint.id, endpoint });
  }

  /**
   * Удаляет webhook endpoint
   */
  async unregisterEndpoint(endpointId: string): Promise<void> {
    if (!this.endpoints.has(endpointId)) {
      throw new Error(`Webhook endpoint with id '${endpointId}' not found`);
    }

    this.endpoints.delete(endpointId);
    this.metrics.webhookMetrics.delete(endpointId);
    
    // Очищаем таймеры повторных попыток
    const timer = this.retryTimers.get(endpointId);
    if (timer) {
      clearTimeout(timer);
      this.retryTimers.delete(endpointId);
    }

    this.emit('webhook-unregistered', { endpointId });
  }

  /**
   * Обновляет webhook endpoint
   */
  async updateEndpoint(endpointId: string, updates: Partial<WebhookEndpoint>): Promise<void> {
    const endpoint = this.endpoints.get(endpointId);
    if (!endpoint) {
      throw new Error(`Webhook endpoint with id '${endpointId}' not found`);
    }

    const updatedEndpoint = { ...endpoint, ...updates };
    this.endpoints.set(endpointId, updatedEndpoint);

    this.emit('webhook-updated', { endpointId, updates });
  }

  /**
   * Получает все webhook endpoints
   */
  getEndpoints(): WebhookEndpoint[] {
    return Array.from(this.endpoints.values());
  }

  /**
   * Получает webhook endpoint по ID
   */
  getEndpoint(endpointId: string): WebhookEndpoint | null {
    return this.endpoints.get(endpointId) || null;
  }

  /**
   * Инициирует событие для отправки
   */
  async triggerEvent(event: Omit<WebhookEvent, 'id' | 'timestamp'>): Promise<string> {
    const fullEvent: WebhookEvent = {
      ...event,
      id: this.generateEventId(),
      timestamp: new Date()
    };

    // Добавляем в очередь
    this.eventQueue.push(fullEvent);
    this.metrics.totalEvents++;
    this.metrics.lastEvent = fullEvent.timestamp;

    // Пересчитываем errorRate
    this.recalculateErrorRate();

    this.emit('event-triggered', { eventId: fullEvent.id, event: fullEvent });

    return fullEvent.id;
  }

  /**
   * Получает все события
   */
  getEvents(): WebhookEvent[] {
    return [...this.eventQueue];
  }

  /**
   * Получает все доставки
   */
  getDeliveries(): WebhookDelivery[] {
    return [...this.deliveryQueue];
  }

  /**
   * Получает доставки для webhook'а
   */
  getDeliveriesForWebhook(webhookId: string): WebhookDelivery[] {
    return this.deliveryQueue.filter(d => d.webhookId === webhookId);
  }

  /**
   * Получает метрики webhook service
   */
  getMetrics(): WebhookMetrics {
    // Пересчитываем errorRate для актуальных данных
    this.recalculateErrorRate();
    return { ...this.metrics };
  }

  /**
   * Получает метрики конкретного webhook'а
   */
  getEndpointMetrics(endpointId: string): WebhookEndpointMetrics | null {
    return this.metrics.webhookMetrics.get(endpointId) || null;
  }

  /**
   * Повторно отправляет неудачную доставку
   */
  async retryDelivery(deliveryId: string): Promise<void> {
    const delivery = this.deliveryQueue.find(d => d.id === deliveryId);
    if (!delivery) {
      throw new Error(`Delivery with id '${deliveryId}' not found`);
    }

    if (delivery.status === 'delivered') {
      throw new Error('Cannot retry a successful delivery');
    }

    delivery.status = 'pending';
    delivery.attempts++;
    delivery.lastAttempt = new Date();
    delivery.error = undefined;

    this.emit('delivery-retry', { deliveryId });
  }

  /**
   * Тестирует webhook endpoint
   */
  async testEndpoint(endpointId: string, testData?: any): Promise<{
    success: boolean;
    response?: WebhookResponse;
    error?: string;
    duration: number;
  }> {
    const endpoint = this.endpoints.get(endpointId);
    if (!endpoint) {
      throw new Error(`Webhook endpoint with id '${endpointId}' not found`);
    }

    const startTime = Date.now();
    const testEvent: WebhookEvent = {
      id: this.generateEventId(),
      source: 'test',
      type: 'test.event',
      data: testData || { message: 'Test webhook event' },
      timestamp: new Date(),
      metadata: { test: true }
    };

    try {
      const response = await this.deliverEvent(testEvent, endpoint);
      const duration = Date.now() - startTime;

      return {
        success: response.status >= 200 && response.status < 300,
        response,
        duration
      };

    } catch (error) {
      const duration = Date.now() - startTime;
      return {
        success: false,
        error: (error as Error).message,
        duration
      };
    }
  }

  /**
   * Очищает очередь событий
   */
  clearQueue(): void {
    this.eventQueue = [];
    this.emit('queue-cleared');
  }

  /**
   * Получает статистику по событиям
   */
  getEventStats(): {
    total: number;
    pending: number;
    processing: number;
    delivered: number;
    failed: number;
  } {
    return {
      total: this.eventQueue.length,
      pending: this.eventQueue.filter(e => !this.deliveredEvents.has(e.id)).length,
      processing: 0, // TODO: Отслеживать обрабатываемые события
      delivered: this.deliveredEvents.size,
      failed: this.metrics.failedEvents
    };
  }

  /**
   * Экспортирует конфигурацию webhook'ов
   */
  exportEndpoints(): string {
    const config = {
      endpoints: this.getEndpoints(),
      exportDate: new Date().toISOString()
    };
    return JSON.stringify(config, null, 2);
  }

  /**
   * Импортирует конфигурацию webhook'ов
   */
  async importEndpoints(configJson: string): Promise<void> {
    try {
      const config = JSON.parse(configJson);
      
      if (!config.endpoints || !Array.isArray(config.endpoints)) {
        throw new Error('Invalid endpoints configuration format');
      }

      // Очищаем существующие endpoints
      this.endpoints.clear();
      this.metrics.webhookMetrics.clear();

      // Импортируем новые
      for (const endpoint of config.endpoints) {
        await this.registerEndpoint(endpoint);
      }

      this.emit('endpoints-imported', { 
        importedEndpoints: config.endpoints.length 
      });

    } catch (error) {
      throw new Error(`Failed to import endpoints configuration: ${(error as Error).message}`);
    }
  }

  // Private methods

  private recalculateErrorRate(): void {
    if (this.metrics.totalEvents === 0) {
      this.metrics.errorRate = 0;
    } else {
      this.metrics.errorRate = (this.metrics.failedEvents / this.metrics.totalEvents) * 100;
    }
  }

  private async startProcessing(): Promise<void> {
    if (this.processing) return;
    this.processing = true;

    // Основной цикл обработки
    setInterval(async () => {
      await this.processEventQueue();
      await this.processDeliveryQueue();
    }, 1000);

    // Очистка старых событий
    setInterval(() => {
      this.cleanupOldEvents();
    }, 5 * 60 * 1000); // каждые 5 минут
  }

  private async processEventQueue(): Promise<void> {
    if (this.eventQueue.length === 0) return;

    const event = this.eventQueue.shift();
    if (!event) return;

    try {
      // Находим подходящие webhook endpoints
      const endpoints = this.findMatchingEndpoints(event);
      
      for (const endpoint of endpoints) {
        const delivery = this.createDelivery(event, endpoint);
        this.deliveryQueue.push(delivery);
        
        // Немедленно отправляем если возможно
        await this.processDelivery(delivery);
      }

    } catch (error) {
      console.error('Event processing failed:', error);
      this.emit('event-processing-error', { event, error: error as Error });
    }
  }

  private async processDeliveryQueue(): Promise<void> {
    const pendingDeliveries = this.deliveryQueue.filter(d => d.status === 'pending');
    
    for (const delivery of pendingDeliveries) {
      // Ограничиваем параллельные отправки
      const activeDeliveries = this.deliveryQueue.filter(d => d.status === 'sending').length;
      if (activeDeliveries >= 10) break; // Максимум 10 параллельных отправок

      await this.processDelivery(delivery);
    }
  }

  private async processDelivery(delivery: WebhookDelivery): Promise<void> {
    const endpoint = this.endpoints.get(delivery.webhookId);
    if (!endpoint || !endpoint.active) {
      delivery.status = 'failed';
      delivery.error = 'Endpoint not found or inactive';
      this.updateMetrics(delivery, false);
      return;
    }

    delivery.status = 'sending';
    delivery.attempts++;
    delivery.lastAttempt = new Date();

    try {
      const response = await this.deliverEvent(delivery.event, endpoint);
      
      delivery.status = response.status >= 200 && response.status < 300 ? 'delivered' : 'failed';
      delivery.response = response;
      
      if (delivery.status === 'failed') {
        delivery.error = `HTTP ${response.status}`;
        this.updateMetrics(delivery, false);
        
        // Планируем повторную попытку если возможно
        if (delivery.attempts < endpoint.maxRetries) {
          this.scheduleRetry(delivery, endpoint);
        }
      } else {
        this.updateMetrics(delivery, true);
        this.deliveredEvents.add(delivery.event.id);
      }

      this.emit('delivery-processed', { deliveryId: delivery.id, status: delivery.status });

    } catch (error) {
      delivery.status = 'failed';
      delivery.error = (error as Error).message;
      this.updateMetrics(delivery, false);

      // Планируем повторную попытку
      if (delivery.attempts < endpoint.maxRetries) {
        this.scheduleRetry(delivery, endpoint);
      }

      this.emit('delivery-error', { deliveryId: delivery.id, error: error as Error });
    }
  }

  private scheduleRetry(delivery: WebhookDelivery, endpoint: WebhookEndpoint): void {
    const delay = this.calculateRetryDelay(delivery.attempts - 1, endpoint.retryPolicy);
    
    const timer = setTimeout(() => {
      delivery.status = 'pending';
      this.retryTimers.delete(delivery.id);
      this.emit('delivery-retry-scheduled', { deliveryId: delivery.id, delay });
    }, delay);

    this.retryTimers.set(delivery.id, timer);
    delivery.status = 'retrying';
  }

  private async deliverEvent(event: WebhookEvent, endpoint: WebhookEndpoint): Promise<WebhookResponse> {
    const startTime = Date.now();

    // Применяем трансформацию запроса
    const transformedRequest = this.transformRequest(event, endpoint.transformation?.request);

    const payload = JSON.stringify(transformedRequest.data);
    const signature = endpoint.secret ? await this.generateSignature(payload, endpoint.secret) : undefined;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'User-Agent': 'WebhookService/1.0',
      'X-Webhook-Event': event.type,
      'X-Webhook-Id': event.id,
      'X-Webhook-Timestamp': event.timestamp.toISOString(),
      ...endpoint.transformation?.request?.headers
    };

    if (signature) {
      headers['X-Webhook-Signature'] = signature;
    }

    const response = await fetch(endpoint.url, {
      method: 'POST',
      headers,
      body: payload,
      signal: AbortSignal.timeout(endpoint.timeout)
    });

    const responseText = await response.text();
    const endTime = Date.now();

    const responseHeaders: Record<string, string> = {};
    response.headers.forEach((value, key) => {
      responseHeaders[key] = value;
    });

    // Применяем трансформацию ответа
    const transformedResponse = this.transformResponse(
      { 
        status: response.status, 
        headers: responseHeaders, 
        body: responseText,
        timing: {
          startTime,
          endTime,
          duration: endTime - startTime
        }
      },
      endpoint.transformation?.response
    );

    return transformedResponse;
  }

  private findMatchingEndpoints(event: WebhookEvent): WebhookEndpoint[] {
    return Array.from(this.endpoints.values()).filter(endpoint => {
      // Проверяем что endpoint активен
      if (!endpoint.active) return false;

      // Проверяем что тип события подходит
      if (!endpoint.events.includes(event.type)) return false;

      // Проверяем фильтры если есть
      if (endpoint.filters && !this.applyFilters(event, endpoint.filters)) {
        return false;
      }

      return true;
    });
  }

  private applyFilters(event: WebhookEvent, filters: WebhookFilter[]): boolean {
    return filters.every(filter => {
      const value = this.getNestedValue(event, filter.field);
      const matches = this.evaluateFilter(value, filter.operator, filter.value);
      return filter.negate ? !matches : matches;
    });
  }

  private evaluateFilter(value: any, operator: WebhookFilter['operator'], filterValue: string | string[]): boolean {
    switch (operator) {
      case 'equals':
        return value === filterValue;
      case 'contains':
        return typeof value === 'string' && typeof filterValue === 'string' && 
               value.includes(filterValue);
      case 'regex':
        const regex = new RegExp(filterValue as string);
        return regex.test(String(value));
      case 'in':
        return Array.isArray(filterValue) && filterValue.includes(value);
      case 'not_in':
        return Array.isArray(filterValue) && !filterValue.includes(value);
      default:
        return false;
    }
  }

  private getNestedValue(obj: any, path: string): any {
    return path.split('.').reduce((current, key) => current?.[key], obj);
  }

  private transformRequest(event: WebhookEvent, transformation?: WebhookTransformation['request']): WebhookEvent {
    if (!transformation) return event;

    const transformed = { ...event };

    if (transformation.body) {
      try {
        const transformFunction = new Function('event', transformation.body);
        transformed.data = transformFunction(transformed);
      } catch (error) {
        console.error('Request transformation failed:', error);
      }
    }

    return transformed;
  }

  private transformResponse(response: WebhookResponse, transformation?: WebhookTransformation['response']): WebhookResponse {
    if (!transformation) return response;

    const transformed = { ...response };

    if (transformation.body) {
      try {
        const transformFunction = new Function('response', transformation.body);
        transformed.body = transformFunction(transformed);
      } catch (error) {
        console.error('Response transformation failed:', error);
      }
    }

    return transformed;
  }

  private createDelivery(event: WebhookEvent, endpoint: WebhookEndpoint): WebhookDelivery {
    return {
      id: this.generateDeliveryId(),
      webhookId: endpoint.id,
      event,
      status: 'pending',
      attempts: 0,
      createdAt: new Date()
    };
  }

  private updateMetrics(delivery: WebhookDelivery, success: boolean): void {
    this.metrics.deliveredEvents++;
    this.metrics.lastEvent = delivery.event.timestamp;

    if (!success) {
      this.metrics.failedEvents++;
      this.metrics.retryEvents++;
    }

    // Обновляем метрики endpoint'а
    const endpointMetrics = this.metrics.webhookMetrics.get(delivery.webhookId);
    if (endpointMetrics) {
      endpointMetrics.totalDeliveries++;
      endpointMetrics.lastDelivery = new Date();

      if (success) {
        endpointMetrics.successfulDeliveries++;
        endpointMetrics.averageResponseTime = 
          (endpointMetrics.averageResponseTime * (endpointMetrics.totalDeliveries - 1) + 
           (delivery.response?.timing.duration || 0)) / endpointMetrics.totalDeliveries;
      } else {
        endpointMetrics.failedDeliveries++;
        endpointMetrics.retryDeliveries++;
      }

      // Пересчитываем проценты
      endpointMetrics.successRate = (endpointMetrics.successfulDeliveries / endpointMetrics.totalDeliveries) * 100;
      endpointMetrics.errorRate = (endpointMetrics.failedDeliveries / endpointMetrics.totalDeliveries) * 100;
    }

    // Обновляем общий error rate
    this.recalculateErrorRate();
    this.metrics.averageDeliveryTime = 
      (this.metrics.averageDeliveryTime * (this.metrics.deliveredEvents - 1) + 
       (delivery.response?.timing.duration || 0)) / this.metrics.deliveredEvents;
  }

  private initializeMetrics(): WebhookMetrics {
    return {
      totalEvents: 0,
      deliveredEvents: 0,
      failedEvents: 0,
      retryEvents: 0,
      averageDeliveryTime: 0,
      webhookMetrics: new Map(),
      errorRate: 0
    };
  }

  private initializeEndpointMetrics(endpointId: string): void {
    this.metrics.webhookMetrics.set(endpointId, {
      endpointId,
      totalDeliveries: 0,
      successfulDeliveries: 0,
      failedDeliveries: 0,
      retryDeliveries: 0,
      averageResponseTime: 0,
      errorRate: 0,
      successRate: 0
    });
  }

  private cleanupOldEvents(): void {
    const cutoffTime = new Date(Date.now() - 24 * 60 * 60 * 1000); // 24 часа
    const originalLength = this.eventQueue.length;
    
    this.eventQueue = this.eventQueue.filter(event => event.timestamp > cutoffTime);
    this.deliveredEvents.clear();
    
    const removedCount = originalLength - this.eventQueue.length;
    if (removedCount > 0) {
      this.emit('events-cleaned', { removedCount });
    }
  }

  private calculateRetryDelay(attempt: number, policy: RetryPolicy): number {
    let delay = policy.baseDelay;
    
    switch (policy.backoffStrategy) {
      case 'exponential':
        delay = policy.baseDelay * Math.pow(2, attempt);
        break;
      case 'linear':
        delay = policy.baseDelay * (attempt + 1);
        break;
      case 'fixed':
        // delay остается базовым
        break;
    }
    
    if (policy.maxDelay && delay > policy.maxDelay) {
      delay = policy.maxDelay;
    }
    
    return delay * 1000; // в миллисекундах
  }

  private async generateSignature(payload: string, secret: string): Promise<string> {
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
      'raw',
      encoder.encode(secret),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign']
    );
    
    const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(payload));
    const hashArray = Array.from(new Uint8Array(signature));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }

  private generateEventId(): string {
    return `evt_${Date.now()}_${this.generateRandomString(16)}`;
  }

  private generateDeliveryId(): string {
    return `del_${Date.now()}_${this.generateRandomString(16)}`;
  }

  private generateRandomString(length: number): string {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  }
}

export default WebhookService;