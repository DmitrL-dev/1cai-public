  // EventEmitter polyfill for browser compatibility

export interface APIMonitor {
  id: string;
  name: string;
  endpoint: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  schedule: MonitorSchedule;
  conditions: MonitorCondition[];
  actions: MonitorAction[];
  metadata?: Record<string, any>;
  enabled: boolean;
}

export interface MonitorSchedule {
  type: 'interval' | 'cron' | 'once';
  interval?: number; // в секундах для interval
  cron?: string; // для cron
  startAt?: Date;
  endAt?: Date;
}

export interface MonitorCondition {
  type: 'status_code' | 'response_time' | 'content' | 'uptime' | 'custom';
  operator: 'equals' | 'not_equals' | 'greater_than' | 'less_than' | 'contains' | 'regex' | 'in_range';
  value: any;
  threshold?: {
    warning: number;
    critical: number;
  };
  duration?: number; // в секундах, для какого времени должно сохраняться условие
}

export interface MonitorAction {
  type: 'email' | 'webhook' | 'slack' | 'teams' | 'sms' | 'log' | 'custom';
  config: {
    recipients?: string[];
    webhookUrl?: string;
    channel?: string;
    message?: string;
    template?: string;
  };
  condition: 'warning' | 'critical' | 'any';
  cooldown?: number; // в секундах, минимальное время между уведомлениями
  enabled: boolean;
}

export interface MonitorCheckResult {
  monitorId: string;
  timestamp: Date;
  status: 'pass' | 'warning' | 'critical' | 'unknown';
  response: APIResponse;
  conditionResults: ConditionResult[];
  actionsTriggered: string[];
  executionTime: number;
}

export interface ConditionResult {
  condition: MonitorCondition;
  passed: boolean;
  actualValue: any;
  message: string;
  severity: 'info' | 'warning' | 'critical';
}

export interface APIResponse {
  status: number;
  statusText: string;
  headers: Record<string, string>;
  body: any;
  timing: {
    dns?: number;
    connect?: number;
    ttfb?: number;
    download?: number;
    total: number;
  };
}

export interface MonitorMetrics {
  totalChecks: number;
  passingChecks: number;
  failingChecks: number;
  warningChecks: number;
  averageResponseTime: number;
  uptime: number; // в процентах
  lastCheck?: Date;
  monitorMetrics: Map<string, MonitorMetricsData>;
}

export interface MonitorMetricsData {
  monitorId: string;
  totalChecks: number;
  passingChecks: number;
  failingChecks: number;
  warningChecks: number;
  averageResponseTime: number;
  lastCheck?: Date;
  uptime: number;
  downtimes: Downtime[];
  incidents: Incident[];
}

export interface Downtime {
  id: string;
  startTime: Date;
  endTime?: Date;
  duration?: number; // в секундах
  reason: string;
  severity: 'warning' | 'critical';
}

export interface Incident {
  id: string;
  monitorId: string;
  title: string;
  description: string;
  severity: 'warning' | 'critical';
  status: 'open' | 'investigating' | 'resolved';
  startTime: Date;
  endTime?: Date;
  resolution?: string;
}

export class APIMonitoringService extends EventEmitter {
  private monitors: Map<string, APIMonitor> = new Map();
  private activeMonitors: Set<string> = new Set();
  private checkResults: Map<string, MonitorCheckResult[]> = new Map();
  private metrics: MonitorMetrics;
  private timers: Map<string, NodeJS.Timeout> = new Map();
  private downtimes: Map<string, Downtime[]> = new Map();
  private incidents: Map<string, Incident[]> = new Map();
  private lastNotificationTime: Map<string, number> = new Map();

  constructor() {
    super();
    this.metrics = this.initializeMetrics();
    this.loadStoredMonitors();
    this.startScheduler();
  }

  /**
   * Регистрирует новый монитор
   */
  async registerMonitor(monitor: APIMonitor): Promise<void> {
    if (this.monitors.has(monitor.id)) {
      throw new Error(`Monitor with id '${monitor.id}' already exists`);
    }

    this.monitors.set(monitor.id, monitor);
    this.initializeMonitorMetrics(monitor.id);
    this.initializeMonitorData(monitor.id);

    if (monitor.enabled) {
      await this.startMonitor(monitor.id);
    }

    this.emit('monitor-registered', { monitorId: monitor.id, monitor });
  }

  /**
   * Удаляет монитор
   */
  async unregisterMonitor(monitorId: string): Promise<void> {
    const monitor = this.monitors.get(monitorId);
    if (!monitor) {
      throw new Error(`Monitor with id '${monitorId}' not found`);
    }

    await this.stopMonitor(monitorId);
    this.monitors.delete(monitorId);
    this.metrics.monitorMetrics.delete(monitorId);
    this.checkResults.delete(monitorId);
    this.downtimes.delete(monitorId);
    this.incidents.delete(monitorId);

    this.emit('monitor-unregistered', { monitorId });
  }

  /**
   * Обновляет монитор
   */
  async updateMonitor(monitorId: string, updates: Partial<APIMonitor>): Promise<void> {
    const monitor = this.monitors.get(monitorId);
    if (!monitor) {
      throw new Error(`Monitor with id '${monitorId}' not found`);
    }

    const updatedMonitor = { ...monitor, ...updates };
    this.monitors.set(monitorId, updatedMonitor);

    // Перезапускаем монитор если нужно
    if (updates.enabled !== undefined) {
      if (updates.enabled) {
        await this.startMonitor(monitorId);
      } else {
        await this.stopMonitor(monitorId);
      }
    }

    this.emit('monitor-updated', { monitorId, updates });
  }

  /**
   * Запускает монитор
   */
  async startMonitor(monitorId: string): Promise<void> {
    const monitor = this.monitors.get(monitorId);
    if (!monitor) {
      throw new Error(`Monitor with id '${monitorId}' not found`);
    }

    if (this.activeMonitors.has(monitorId)) {
      return; // Уже активен
    }

    this.activeMonitors.add(monitorId);

    // Планируем выполнение
    if (monitor.schedule.type === 'interval' && monitor.schedule.interval) {
      const timer = setInterval(() => {
        this.executeCheck(monitorId);
      }, monitor.schedule.interval * 1000);
      
      this.timers.set(monitorId, timer);
      
      // Выполняем немедленно первый раз
      this.executeCheck(monitorId);
    }

    this.emit('monitor-started', { monitorId });
  }

  /**
   * Останавливает монитор
   */
  async stopMonitor(monitorId: string): Promise<void> {
    if (!this.activeMonitors.has(monitorId)) {
      return; // Не активен
    }

    this.activeMonitors.delete(monitorId);

    const timer = this.timers.get(monitorId);
    if (timer) {
      clearInterval(timer);
      this.timers.delete(monitorId);
    }

    this.emit('monitor-stopped', { monitorId });
  }

  /**
   * Выполняет проверку монитора вручную
   */
  async executeCheck(monitorId: string): Promise<MonitorCheckResult> {
    const monitor = this.monitors.get(monitorId);
    if (!monitor) {
      throw new Error(`Monitor with id '${monitorId}' not found`);
    }

    const startTime = Date.now();

    try {
      const response = await this.makeRequest(monitor);
      const result = await this.evaluateConditions(monitor, response);
      
      const checkResult: MonitorCheckResult = {
        monitorId,
        timestamp: new Date(),
        status: result.status,
        response,
        conditionResults: result.conditionResults,
        actionsTriggered: [],
        executionTime: Date.now() - startTime
      };

      // Сохраняем результат
      this.saveCheckResult(checkResult);

      // Выполняем действия
      checkResult.actionsTriggered = await this.executeActions(checkResult, monitor);

      // Обновляем метрики
      this.updateMetrics(monitorId, checkResult);

      // Обрабатываем инциденты
      await this.processIncident(checkResult, monitor);

      this.emit('check-completed', { monitorId, result: checkResult });

      return checkResult;

    } catch (error) {
      const checkResult: MonitorCheckResult = {
        monitorId,
        timestamp: new Date(),
        status: 'unknown',
        response: {
          status: 0,
          statusText: 'Request Failed',
          headers: {},
          body: null,
          timing: { total: Date.now() - startTime }
        },
        conditionResults: [{
          condition: { type: 'uptime', operator: 'equals', value: true },
          passed: false,
          actualValue: false,
          message: `Request failed: ${(error as Error).message}`,
          severity: 'critical'
        }],
        actionsTriggered: [],
        executionTime: Date.now() - startTime
      };

      this.saveCheckResult(checkResult);
      this.updateMetrics(monitorId, checkResult);
      await this.processIncident(checkResult, monitor);

      this.emit('check-failed', { monitorId, error: error as Error });
      throw error;
    }
  }

  /**
   * Получает историю проверок монитора
   */
  getCheckHistory(monitorId: string, limit: number = 100): MonitorCheckResult[] {
    const results = this.checkResults.get(monitorId) || [];
    return results.slice(-limit);
  }

  /**
   * Получает все мониторы
   */
  getMonitors(): APIMonitor[] {
    return Array.from(this.monitors.values());
  }

  /**
   * Получает монитор по ID
   */
  getMonitor(monitorId: string): APIMonitor | null {
    return this.monitors.get(monitorId) || null;
  }

  /**
   * Получает метрики мониторинга
   */
  getMetrics(): MonitorMetrics {
    return { ...this.metrics };
  }

  /**
   * Получает метрики конкретного монитора
   */
  getMonitorMetrics(monitorId: string): MonitorMetricsData | null {
    return this.metrics.monitorMetrics.get(monitorId) || null;
  }

  /**
   * Получает активные инциденты
   */
  getActiveIncidents(): Incident[] {
    const allIncidents: Incident[] = [];
    for (const incidents of this.incidents.values()) {
      allIncidents.push(...incidents.filter(i => i.status !== 'resolved'));
    }
    return allIncidents;
  }

  /**
   * Получает историю простоев
   */
  getDowntimes(monitorId?: string): Downtime[] {
    if (monitorId) {
      return this.downtimes.get(monitorId) || [];
    }

    const allDowntimes: Downtime[] = [];
    for (const downtimes of this.downtimes.values()) {
      allDowntimes.push(...downtimes);
    }
    return allDowntimes;
  }

  /**
   * Обновляет инцидент
   */
  async updateIncident(incidentId: string, updates: Partial<Incident>): Promise<void> {
    let foundIncident: Incident | null = null;
    let foundMonitorId: string | null = null;

    for (const [monitorId, incidents] of this.incidents.entries()) {
      const incident = incidents.find(i => i.id === incidentId);
      if (incident) {
        foundIncident = incident;
        foundMonitorId = monitorId;
        break;
      }
    }

    if (!foundIncident || !foundMonitorId) {
      throw new Error(`Incident with id '${incidentId}' not found`);
    }

    Object.assign(foundIncident, updates);

    if (updates.status === 'resolved') {
      foundIncident.endTime = new Date();
    }

    this.emit('incident-updated', { incidentId, updates });
  }

  /**
   * Экспортирует конфигурацию мониторов
   */
  exportMonitors(): string {
    const config = {
      monitors: this.getMonitors(),
      exportDate: new Date().toISOString()
    };
    return JSON.stringify(config, null, 2);
  }

  /**
   * Импортирует конфигурацию мониторов
   */
  async importMonitors(configJson: string): Promise<void> {
    try {
      const config = JSON.parse(configJson);
      
      if (!config.monitors || !Array.isArray(config.monitors)) {
        throw new Error('Invalid monitors configuration format');
      }

      // Очищаем существующие мониторы
      this.monitors.clear();
      this.activeMonitors.clear();
      this.metrics.monitorMetrics.clear();
      this.checkResults.clear();
      this.downtimes.clear();
      this.incidents.clear();

      // Импортируем новые
      for (const monitor of config.monitors) {
        await this.registerMonitor(monitor);
      }

      this.emit('monitors-imported', { 
        importedMonitors: config.monitors.length 
      });

    } catch (error) {
      throw new Error(`Failed to import monitors configuration: ${(error as Error).message}`);
    }
  }

  // Private methods

  private startScheduler(): void {
    // Проверяем завершение scheduled мониторов
    setInterval(() => {
      this.checkScheduledCompletion();
    }, 60000); // каждую минуту

    // Очищаем старые результаты проверок
    setInterval(() => {
      this.cleanupOldResults();
    }, 60 * 60 * 1000); // каждый час
  }

  private async makeRequest(monitor: APIMonitor): Promise<APIResponse> {
    const startTime = Date.now();
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 секунд timeout

    try {
      const response = await fetch(monitor.endpoint, {
        method: monitor.method,
        signal: controller.signal,
        headers: {
          'User-Agent': 'APIMonitor/1.0',
          'Accept': 'application/json'
        }
      });

      clearTimeout(timeoutId);

      const responseText = await response.text();
      let body: any;
      
      try {
        body = JSON.parse(responseText);
      } catch {
        body = responseText;
      }

      const timing = {
        total: Date.now() - startTime
      };

      return {
        status: response.status,
        statusText: response.statusText,
        headers: Object.fromEntries(response.headers.entries()),
        body,
        timing
      };

    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  }

  private async evaluateConditions(monitor: APIMonitor, response: APIResponse): Promise<{
    status: 'pass' | 'warning' | 'critical';
    conditionResults: ConditionResult[];
  }> {
    const conditionResults: ConditionResult[] = [];
    let overallStatus: 'pass' | 'warning' | 'critical' = 'pass';

    for (const condition of monitor.conditions) {
      const result = this.evaluateCondition(condition, response);
      conditionResults.push(result);

      // Определяем общий статус
      if (result.severity === 'critical') {
        overallStatus = 'critical';
      } else if (result.severity === 'warning' && overallStatus === 'pass') {
        overallStatus = 'warning';
      }
    }

    return { status: overallStatus, conditionResults };
  }

  private evaluateCondition(condition: MonitorCondition, response: APIResponse): ConditionResult {
    let actualValue: any;
    let passed = false;
    let message = '';
    let severity: 'info' | 'warning' | 'critical' = 'info';

    // Извлекаем значение для проверки
    switch (condition.type) {
      case 'status_code':
        actualValue = response.status;
        break;
      case 'response_time':
        actualValue = response.timing.total;
        break;
      case 'content':
        actualValue = typeof response.body === 'string' ? response.body : JSON.stringify(response.body);
        break;
      case 'uptime':
        actualValue = response.status >= 200 && response.status < 400;
        break;
      case 'custom':
        // TODO: Реализовать custom evaluation
        actualValue = null;
        break;
      default:
        actualValue = null;
    }

    // Проверяем условие
    switch (condition.operator) {
      case 'equals':
        passed = actualValue === condition.value;
        message = `Expected ${condition.value}, got ${actualValue}`;
        break;
      case 'not_equals':
        passed = actualValue !== condition.value;
        message = `Expected not ${condition.value}, got ${actualValue}`;
        break;
      case 'greater_than':
        passed = actualValue > condition.value;
        message = `Expected > ${condition.value}, got ${actualValue}`;
        break;
      case 'less_than':
        passed = actualValue < condition.value;
        message = `Expected < ${condition.value}, got ${actualValue}`;
        break;
      case 'contains':
        passed = typeof actualValue === 'string' && actualValue.includes(condition.value);
        message = `Expected to contain "${condition.value}", got "${actualValue}"`;
        break;
      case 'regex':
        try {
          const regex = new RegExp(condition.value);
          passed = regex.test(String(actualValue));
          message = `Expected to match ${condition.value}, got "${actualValue}"`;
        } catch {
          passed = false;
          message = 'Invalid regex pattern';
        }
        break;
      case 'in_range':
        const [min, max] = condition.value;
        passed = actualValue >= min && actualValue <= max;
        message = `Expected between ${min}-${max}, got ${actualValue}`;
        break;
    }

    // Определяем severity
    if (condition.threshold) {
      if (condition.type === 'response_time') {
        if (actualValue > condition.threshold.critical) {
          severity = 'critical';
        } else if (actualValue > condition.threshold.warning) {
          severity = 'warning';
        }
      } else {
        severity = passed ? 'info' : 'critical';
      }
    } else {
      severity = passed ? 'info' : 'critical';
    }

    return {
      condition,
      passed,
      actualValue,
      message,
      severity
    };
  }

  private async executeActions(result: MonitorCheckResult, monitor: APIMonitor): Promise<string[]> {
    const triggeredActions: string[] = [];

    for (const action of monitor.actions) {
      if (!action.enabled) continue;

      // Проверяем cooldown
      const cooldownKey = `${monitor.id}:${action.type}`;
      const lastNotification = this.lastNotificationTime.get(cooldownKey) || 0;
      const now = Date.now();
      
      if (action.cooldown && now - lastNotification < action.cooldown * 1000) {
        continue;
      }

      // Проверяем условие для выполнения действия
      if (action.condition === 'any' || 
          (action.condition === 'warning' && result.status === 'warning') ||
          (action.condition === 'critical' && result.status === 'critical')) {

        try {
          await this.executeAction(action, result, monitor);
          triggeredActions.push(action.type);
          this.lastNotificationTime.set(cooldownKey, now);
        } catch (error) {
          console.error(`Action ${action.type} failed:`, error);
          this.emit('action-failed', { action, error: error as Error, result });
        }
      }
    }

    return triggeredActions;
  }

  private async executeAction(action: MonitorAction, result: MonitorCheckResult, monitor: APIMonitor): Promise<void> {
    switch (action.type) {
      case 'email':
        await this.sendEmail(action, result, monitor);
        break;
      case 'webhook':
        await this.sendWebhook(action, result, monitor);
        break;
      case 'log':
        console.log(`[Monitor Alert] ${monitor.name}: ${result.status} - ${result.conditionResults.map(r => r.message).join(', ')}`);
        break;
      case 'custom':
        // TODO: Реализовать custom actions
        break;
      default:
        throw new Error(`Unknown action type: ${action.type}`);
    }

    this.emit('action-executed', { action, result, monitor });
  }

  private async sendEmail(action: MonitorAction, result: MonitorCheckResult, monitor: APIMonitor): Promise<void> {
    if (!action.config.recipients?.length) {
      throw new Error('No recipients specified for email action');
    }

    const subject = `[${result.status.toUpperCase()}] ${monitor.name}`;
    const body = this.formatEmailMessage(action.config.message || this.getDefaultMessage(), result, monitor);

    console.log(`Sending email to ${action.config.recipients.join(', ')}: ${subject}`);
    // TODO: Реальная отправка email через SMTP или email service
  }

  private async sendWebhook(action: MonitorAction, result: MonitorCheckResult, monitor: APIMonitor): Promise<void> {
    if (!action.config.webhookUrl) {
      throw new Error('No webhook URL specified');
    }

    const payload = {
      monitor: {
        id: monitor.id,
        name: monitor.name,
        endpoint: monitor.endpoint
      },
      check: result,
      timestamp: new Date().toISOString()
    };

    const response = await fetch(action.config.webhookUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Webhook request failed: ${response.status} ${response.statusText}`);
    }
  }

  private async processIncident(result: MonitorCheckResult, monitor: APIMonitor): Promise<void> {
    const monitorIncidents = this.incidents.get(monitor.id) || [];
    const hasActiveIncident = monitorIncidents.some(i => i.status !== 'resolved');

    // Определяем есть ли проблема
    const hasIssue = result.status === 'warning' || result.status === 'critical';

    if (hasIssue && !hasActiveIncident) {
      // Создаем новый инцидент
      const incident: Incident = {
        id: this.generateIncidentId(),
        monitorId: monitor.id,
        title: `${monitor.name} - ${result.status}`,
        description: result.conditionResults.map(r => r.message).join('; '),
        severity: result.status === 'critical' ? 'critical' : 'warning',
        status: 'open',
        startTime: result.timestamp
      };

      monitorIncidents.push(incident);
      this.incidents.set(monitor.id, monitorIncidents);

      this.emit('incident-created', { incident, result });

    } else if (!hasIssue && hasActiveIncident) {
      // Закрываем активный инцидент
      const activeIncident = monitorIncidents.find(i => i.status !== 'resolved');
      if (activeIncident) {
        activeIncident.status = 'resolved';
        activeIncident.endTime = result.timestamp;
        activeIncident.resolution = 'Monitor check passed';

        this.emit('incident-resolved', { incident: activeIncident, result });
      }
    }

    // Обрабатываем простои
    await this.processDowntime(result, monitor);
  }

  private async processDowntime(result: MonitorCheckResult, monitor: APIMonitor): Promise<void> {
    const monitorDowntimes = this.downtimes.get(monitor.id) || [];
    const hasActiveDowntime = monitorDowntimes.some(d => !d.endTime);

    const hasIssue = result.status === 'warning' || result.status === 'critical';

    if (hasIssue && !hasActiveDowntime) {
      // Начинаем простой
      const downtime: Downtime = {
        id: this.generateDowntimeId(),
        startTime: result.timestamp,
        reason: result.conditionResults.map(r => r.message).join('; '),
        severity: result.status === 'critical' ? 'critical' : 'warning'
      };

      monitorDowntimes.push(downtime);
      this.downtimes.set(monitor.id, monitorDowntimes);

    } else if (!hasIssue && hasActiveDowntime) {
      // Заканчиваем простой
      const activeDowntime = monitorDowntimes.find(d => !d.endTime);
      if (activeDowntime) {
        activeDowntime.endTime = result.timestamp;
        activeDowntime.duration = Math.floor((activeDowntime.endTime.getTime() - activeDowntime.startTime.getTime()) / 1000);
      }
    }
  }

  private saveCheckResult(result: MonitorCheckResult): void {
    const results = this.checkResults.get(result.monitorId) || [];
    results.push(result);
    
    // Ограничиваем размер истории
    if (results.length > 1000) {
      results.shift();
    }
    
    this.checkResults.set(result.monitorId, results);
  }

  private updateMetrics(monitorId: string, result: MonitorCheckResult): void {
    this.metrics.totalChecks++;
    this.metrics.lastCheck = result.timestamp;

    switch (result.status) {
      case 'pass':
        this.metrics.passingChecks++;
        break;
      case 'warning':
        this.metrics.warningChecks++;
        break;
      case 'critical':
      case 'unknown':
        this.metrics.failingChecks++;
        break;
    }

    // Обновляем среднее время ответа
    this.metrics.averageResponseTime = 
      (this.metrics.averageResponseTime * (this.metrics.totalChecks - 1) + result.response.timing.total) / this.metrics.totalChecks;

    // Обновляем метрики монитора
    const monitorMetrics = this.metrics.monitorMetrics.get(monitorId);
    if (monitorMetrics) {
      monitorMetrics.totalChecks++;
      monitorMetrics.lastCheck = result.timestamp;

      switch (result.status) {
        case 'pass':
          monitorMetrics.passingChecks++;
          break;
        case 'warning':
          monitorMetrics.warningChecks++;
          break;
        case 'critical':
        case 'unknown':
          monitorMetrics.failingChecks++;
          break;
      }

      monitorMetrics.averageResponseTime = 
        (monitorMetrics.averageResponseTime * (monitorMetrics.totalChecks - 1) + result.response.timing.total) / monitorMetrics.totalChecks;

      // Пересчитываем uptime
      const uptimeChecks = monitorMetrics.passingChecks + monitorMetrics.warningChecks;
      monitorMetrics.uptime = uptimeChecks / monitorMetrics.totalChecks * 100;
    }

    // Пересчитываем общий uptime
    const totalSuccessfulChecks = this.metrics.passingChecks + this.metrics.warningChecks;
    this.metrics.uptime = totalSuccessfulChecks / this.metrics.totalChecks * 100;
  }

  private initializeMetrics(): MonitorMetrics {
    return {
      totalChecks: 0,
      passingChecks: 0,
      failingChecks: 0,
      warningChecks: 0,
      averageResponseTime: 0,
      uptime: 0,
      monitorMetrics: new Map()
    };
  }

  private initializeMonitorMetrics(monitorId: string): void {
    this.metrics.monitorMetrics.set(monitorId, {
      monitorId,
      totalChecks: 0,
      passingChecks: 0,
      failingChecks: 0,
      warningChecks: 0,
      averageResponseTime: 0,
      uptime: 0,
      downtimes: [],
      incidents: []
    });
  }

  private initializeMonitorData(monitorId: string): void {
    this.checkResults.set(monitorId, []);
    this.downtimes.set(monitorId, []);
    this.incidents.set(monitorId, []);
  }

  private checkScheduledCompletion(): void {
    const now = new Date();
    
    for (const monitor of this.monitors.values()) {
      if (monitor.schedule.type === 'once' && monitor.schedule.endAt && now > monitor.schedule.endAt) {
        this.stopMonitor(monitor.id);
      }
    }
  }

  private cleanupOldResults(): void {
    const cutoffTime = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000); // 7 дней
    
    for (const [monitorId, results] of this.checkResults.entries()) {
      const filtered = results.filter(r => r.timestamp > cutoffTime);
      this.checkResults.set(monitorId, filtered);
    }
  }

  private formatEmailMessage(template: string, result: MonitorCheckResult, monitor: APIMonitor): string {
    let message = template;
    
    message = message.replace(/{monitor_name}/g, monitor.name);
    message = message.replace(/{endpoint}/g, monitor.endpoint);
    message = message.replace(/{status}/g, result.status);
    message = message.replace(/{timestamp}/g, result.timestamp.toISOString());
    message = message.replace(/{response_time}/g, `${result.response.timing.total}ms`);
    
    const conditionsText = result.conditionResults.map(r => `- ${r.message}`).join('\n');
    message = message.replace(/{conditions}/g, conditionsText);
    
    return message;
  }

  private getDefaultMessage(): string {
    return `Monitor Alert: {monitor_name}

Status: {status}
Endpoint: {endpoint}
Response Time: {response_time}
Timestamp: {timestamp}

Conditions:
{conditions}`;
  }

  private loadStoredMonitors(): void {
    try {
      const stored = localStorage.getItem('api_monitors');
      if (stored) {
        const config = JSON.parse(stored);
        for (const monitor of config.monitors || []) {
          this.monitors.set(monitor.id, monitor);
          this.initializeMonitorMetrics(monitor.id);
          this.initializeMonitorData(monitor.id);
          
          if (monitor.enabled) {
            this.startMonitor(monitor.id);
          }
        }
      }
    } catch (error) {
      console.error('Failed to load stored monitors:', error);
    }
  }

  private generateIncidentId(): string {
    return `incident_${Date.now()}_${this.generateRandomString(8)}`;
  }

  private generateDowntimeId(): string {
    return `downtime_${Date.now()}_${this.generateRandomString(8)}`;
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

export default APIMonitoringService;