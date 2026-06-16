/**
 * Сервис интеграции с системами управления задачами (Jira, Trello)
 * Обеспечивает синхронизацию задач, автоматическое обновление диаграмм
 * и webhook поддержку для real-time обновлений
 */

export interface TaskManagementSystem {
  id: string;
  type: 'jira' | 'trello' | 'github' | 'azure_devops' | 'custom';
  name: string;
  description: string;
  baseUrl: string;
  credentials: SystemCredentials;
  settings: SystemSettings;
  isActive: boolean;
  lastSync: Date | null;
  syncStatus: 'idle' | 'syncing' | 'error' | 'success';
}

export interface SystemCredentials {
  type: 'basic' | 'oauth' | 'api_token' | 'bearer';
  username?: string;
  password?: string;
  apiToken?: string;
  accessToken?: string;
  refreshToken?: string;
  clientId?: string;
  clientSecret?: string;
}

export interface SystemSettings {
  autoSync: boolean;
  syncInterval: number; // минут
  webhookEnabled: boolean;
  webhookUrl?: string;
  projectMapping: Record<string, string>; // localProjectId -> externalProjectId
  fieldMapping: FieldMapping;
  conflictResolution: 'skip' | 'overwrite' | 'merge';
  syncDirection: 'one-way' | 'two-way';
}

export interface FieldMapping {
  summary: string; // поле для названия задачи
  description: string; // поле для описания
  assignee: string; // поле для исполнителя
  status: string; // поле для статуса
  priority: string; // поле для приоритета
  dueDate: string; // поле для срока
  labels: string; // поле для тегов
  customFields: Record<string, string>; // кастомные поля
}

export interface ExternalTask {
  id: string;
  key?: string; // для систем типа Jira
  title: string;
  description: string;
  status: string;
  priority: string;
  assignee?: string;
  creator?: string;
  created: Date;
  updated: Date;
  dueDate?: Date;
  labels: string[];
  url: string;
  
  // Метаданные
  type: string;
  project: string;
  version?: string;
  comments: TaskComment[];
  attachments: TaskAttachment[];
  customFields: Record<string, any>;
  
  // История изменений
  history: TaskHistoryEntry[];
  
  // Связи
  parent?: string;
  subtasks: string[];
  related: string[];
}

export interface TaskComment {
  id: string;
  author: string;
  body: string;
  created: Date;
  updated: Date;
  isInternal: boolean;
}

export interface TaskAttachment {
  id: string;
  filename: string;
  mimeType: string;
  size: number;
  url: string;
  created: Date;
  author: string;
}

export interface TaskHistoryEntry {
  id: string;
  author: string;
  field: string;
  oldValue: string;
  newValue: string;
  created: Date;
  additionalInfo?: any;
}

export interface SyncResult {
  success: boolean;
  timestamp: Date;
  duration: number; // миллисекунды
  summary: SyncSummary;
  errors: SyncError[];
  warnings: SyncWarning[];
  changes: TaskChange[];
}

export interface SyncSummary {
  totalTasks: number;
  importedTasks: number;
  updatedTasks: number;
  exportedTasks: number;
  deletedTasks: number;
  conflicts: number;
  skippedTasks: number;
}

export interface TaskChange {
  taskId: string;
  type: 'created' | 'updated' | 'deleted' | 'status_changed' | 'assignee_changed';
  changes: FieldChange[];
  timestamp: Date;
  source: 'local' | 'external';
}

export interface FieldChange {
  field: string;
  oldValue: any;
  newValue: any;
  type: 'add' | 'remove' | 'update';
}

export interface SyncError {
  code: string;
  message: string;
  taskId?: string;
  field?: string;
  severity: 'error' | 'warning' | 'info';
  details?: any;
}

export interface SyncWarning {
  code: string;
  message: string;
  taskId?: string;
  field?: string;
  suggestion?: string;
}

export interface WebhookEvent {
  id: string;
  source: string;
  type: WebhookEventType;
  timestamp: Date;
  data: any;
  processed: boolean;
}

export type WebhookEventType = 
  | 'task_created' 
  | 'task_updated' 
  | 'task_deleted' 
  | 'task_status_changed'
  | 'task_assigned'
  | 'comment_added'
  | 'attachment_added'
  | 'project_updated'
  | 'user_updated';

export interface SyncConfig {
  systems: TaskManagementSystem[];
  globalSettings: GlobalSyncSettings;
  mappings: MappingConfig[];
  schedules: SyncSchedule[];
  rules: SyncRule[];
}

export interface GlobalSyncSettings {
  defaultConflictResolution: 'skip' | 'overwrite' | 'merge';
  defaultSyncDirection: 'one-way' | 'two-way';
  autoResolveConflicts: boolean;
  batchSize: number;
  rateLimit: number; // запросов в минуту
  retryAttempts: number;
  retryDelay: number; // миллисекунды
}

export interface MappingConfig {
  id: string;
  localSystem: string; // ID локальной системы
  externalSystem: string; // ID внешней системы
  projectMappings: ProjectMapping[];
  fieldMappings: FieldMappingConfig[];
  statusMappings: StatusMappingConfig[];
  priorityMappings: PriorityMappingConfig[];
}

export interface ProjectMapping {
  localProjectId: string;
  externalProjectId: string;
  externalProjectKey?: string;
  name: string;
  isActive: boolean;
}

export interface FieldMappingConfig {
  localField: string;
  externalField: string;
  transformation?: string; // функция преобразования
  required: boolean;
  defaultValue?: any;
}

export interface StatusMappingConfig {
  localStatus: string;
  externalStatus: string;
  localColor?: string;
  externalColor?: string;
  isActive: boolean;
}

export interface PriorityMappingConfig {
  localPriority: string;
  externalPriority: string;
  localOrder: number;
  externalOrder?: number;
  isActive: boolean;
}

export interface SyncSchedule {
  id: string;
  name: string;
  systems: string[]; // ID систем для синхронизации
  cronExpression: string; // выражение для планировщика
  isActive: boolean;
  lastRun: Date | null;
  nextRun: Date | null;
  config: ScheduleConfig;
}

export interface ScheduleConfig {
  syncType: 'full' | 'incremental' | 'delta';
  includeSubtasks: boolean;
  includeComments: boolean;
  includeAttachments: boolean;
  filterCriteria?: FilterCriteria;
  notifyOnComplete: boolean;
  notifyOnError: boolean;
}

export interface FilterCriteria {
  projects?: string[];
  assignees?: string[];
  statuses?: string[];
  priorities?: string[];
  labels?: string[];
  dateRange?: {
    start: Date;
    end: Date;
  };
  customFilters?: Record<string, any>;
}

export interface SyncRule {
  id: string;
  name: string;
  description: string;
  conditions: RuleCondition[];
  actions: RuleAction[];
  priority: number;
  isActive: boolean;
}

export interface RuleCondition {
  field: string;
  operator: 'equals' | 'not_equals' | 'contains' | 'not_contains' | 'greater_than' | 'less_than';
  value: any;
  type: 'local' | 'external' | 'constant';
}

export interface RuleAction {
  type: 'sync' | 'skip' | 'transform' | 'notify' | 'assign';
  parameters: Record<string, any>;
}

export interface IntegrationMetrics {
  totalSyncs: number;
  successfulSyncs: number;
  failedSyncs: number;
  totalTasksSynced: number;
  averageSyncDuration: number; // миллисекунды
  lastSyncDate: Date | null;
  errorRate: number; // процент
  systemsStatus: SystemStatus[];
}

export interface SystemStatus {
  systemId: string;
  systemName: string;
  isConnected: boolean;
  lastSyncDate: Date | null;
  syncSuccessRate: number; // процент
  errorCount: number;
  warningCount: number;
  lastError?: string;
  health: 'healthy' | 'warning' | 'error';
}

export interface ConflictResolution {
  id: string;
  taskId: string;
  conflictType: 'field_conflict' | 'status_conflict' | 'assignee_conflict';
  localValue: any;
  externalValue: any;
  resolution: 'local_wins' | 'external_wins' | 'merge' | 'manual';
  resolvedBy?: string;
  resolvedAt?: Date;
  notes?: string;
}

export interface NotificationConfig {
  enabled: boolean;
  channels: NotificationChannel[];
  triggers: NotificationTrigger[];
  recipients: NotificationRecipient[];
}

export interface NotificationChannel {
  id: string;
  type: 'email' | 'slack' | 'teams' | 'webhook';
  name: string;
  config: Record<string, any>;
  isActive: boolean;
}

export interface NotificationTrigger {
  id: string;
  event: 'sync_success' | 'sync_failure' | 'conflict_detected' | 'system_offline';
  condition?: string;
  channels: string[];
  template: string;
  isActive: boolean;
}

export interface NotificationRecipient {
  id: string;
  name: string;
  email?: string;
  slackChannel?: string;
  webhookUrl?: string;
  systemIds: string[]; // ID систем, для которых получать уведомления
}

export class TaskManagementIntegrationService {
  private readonly supportedSystems = ['jira', 'trello', 'github', 'azure_devops'];
  private readonly syncConfigs = new Map<string, SyncConfig>();
  private readonly webhookHandlers = new Map<string, WebhookHandler>();
  private readonly systemConnections = new Map<string, SystemConnection>();

  constructor() {
    this.initializeWebhookHandlers();
  }

  /**
   * Подключение к системе управления задачами
   */
  async connectSystem(config: TaskManagementSystem): Promise<SystemConnection> {
    try {
      const connection = await this.createConnection(config);
      this.systemConnections.set(config.id, connection);
      
      // Тестирование подключения
      await connection.testConnection();
      
      return connection;
    } catch (error) {
      throw new Error(`Ошибка подключения к системе ${config.name}: ${error}`);
    }
  }

  /**
   * Создание соединения с системой
   */
  private async createConnection(config: TaskManagementSystem): Promise<SystemConnection> {
    switch (config.type) {
      case 'jira':
        return new JiraConnection(config);
      case 'trello':
        return new TrelloConnection(config);
      case 'github':
        return new GitHubConnection(config);
      case 'azure_devops':
        return new AzureDevOpsConnection(config);
      default:
        throw new Error(`Неподдерживаемый тип системы: ${config.type}`);
    }
  }

  /**
   * Синхронизация задач между системами
   */
  async syncTasks(
    localSystemId: string, 
    externalSystemId: string, 
    options?: SyncOptions
  ): Promise<SyncResult> {
    const startTime = Date.now();
    
    try {
      const localSystem = this.systemConnections.get(localSystemId);
      const externalSystem = this.systemConnections.get(externalSystemId);
      
      if (!localSystem || !externalSystem) {
        throw new Error('Системы не подключены');
      }

      // Получение задач из обеих систем
      const [localTasks, externalTasks] = await Promise.all([
        localSystem.getTasks(options?.filterCriteria),
        externalSystem.getTasks(options?.filterCriteria)
      ]);

      // Анализ изменений
      const changes = await this.analyzeChanges(localTasks, externalTasks, localSystemId, externalSystemId);
      
      // Применение изменений
      const syncResult = await this.applyChanges(changes, localSystem, externalSystem, options);
      
      // Обновление метрик
      this.updateSyncMetrics(localSystemId, externalSystemId, syncResult);
      
      return {
        success: true,
        timestamp: new Date(),
        duration: Date.now() - startTime,
        summary: syncResult.summary,
        errors: syncResult.errors,
        warnings: syncResult.warnings,
        changes: syncResult.changes
      };
      
    } catch (error) {
      return {
        success: false,
        timestamp: new Date(),
        duration: Date.now() - startTime,
        summary: {
          totalTasks: 0,
          importedTasks: 0,
          updatedTasks: 0,
          exportedTasks: 0,
          deletedTasks: 0,
          conflicts: 0,
          skippedTasks: 0
        },
        errors: [{
          code: 'SYNC_FAILED',
          message: error instanceof Error ? error.message : 'Неизвестная ошибка синхронизации',
          severity: 'error'
        }],
        warnings: [],
        changes: []
      };
    }
  }

  /**
   * Анализ изменений между системами
   */
  private async analyzeChanges(
    localTasks: ExternalTask[],
    externalTasks: ExternalTask[],
    localSystemId: string,
    externalSystemId: string
  ): Promise<TaskChange[]> {
    const changes: TaskChange[] = [];
    
    // Создание индексов для быстрого поиска
    const localIndex = new Map(localTasks.map(task => [task.id, task]));
    const externalIndex = new Map(externalTasks.map(task => [task.id, task]));
    
    // Анализ внешних задач
    for (const externalTask of externalTasks) {
      const localTask = localIndex.get(externalTask.id);
      
      if (!localTask) {
        // Новая задача в внешней системе
        changes.push({
          taskId: externalTask.id,
          type: 'created',
          changes: this.createTaskFromExternal(externalTask),
          timestamp: new Date(),
          source: 'external'
        });
      } else {
        // Сравнение существующей задачи
        const taskChanges = this.compareTasks(localTask, externalTask);
        if (taskChanges.length > 0) {
          changes.push({
            taskId: externalTask.id,
            type: 'updated',
            changes: taskChanges,
            timestamp: new Date(),
            source: 'external'
          });
        }
      }
    }
    
    // Анализ удаленных задач
    for (const localTask of localTasks) {
      if (!externalIndex.has(localTask.id)) {
        // Задача была удалена из внешней системы
        changes.push({
          taskId: localTask.id,
          type: 'deleted',
          changes: [],
          timestamp: new Date(),
          source: 'external'
        });
      }
    }
    
    return changes;
  }

  /**
   * Сравнение задач для выявления изменений
   */
  private compareTasks(localTask: ExternalTask, externalTask: ExternalTask): FieldChange[] {
    const changes: FieldChange[] = [];
    
    // Сравнение основных полей
    const fields = [
      'title', 'description', 'status', 'priority', 'assignee', 'dueDate', 'labels'
    ];
    
    for (const field of fields) {
      const localValue = (localTask as any)[field];
      const externalValue = (externalTask as any)[field];
      
      if (JSON.stringify(localValue) !== JSON.stringify(externalValue)) {
        changes.push({
          field,
          oldValue: localValue,
          newValue: externalValue,
          type: this.determineChangeType(localValue, externalValue)
        });
      }
    }
    
    return changes;
  }

  /**
   * Определение типа изменения
   */
  private determineChangeType(oldValue: any, newValue: any): 'add' | 'remove' | 'update' {
    if (oldValue === undefined || oldValue === null) return 'add';
    if (newValue === undefined || newValue === null) return 'remove';
    return 'update';
  }

  /**
   * Создание задачи из внешней системы
   */
  private createTaskFromExternal(externalTask: ExternalTask): FieldChange[] {
    return [
      { field: 'title', oldValue: null, newValue: externalTask.title, type: 'add' },
      { field: 'description', oldValue: null, newValue: externalTask.description, type: 'add' },
      { field: 'status', oldValue: null, newValue: externalTask.status, type: 'add' },
      { field: 'priority', oldValue: null, newValue: externalTask.priority, type: 'add' },
      { field: 'assignee', oldValue: null, newValue: externalTask.assignee, type: 'add' },
      { field: 'dueDate', oldValue: null, newValue: externalTask.dueDate, type: 'add' },
      { field: 'labels', oldValue: null, newValue: externalTask.labels, type: 'add' }
    ];
  }

  /**
   * Применение изменений
   */
  private async applyChanges(
    changes: TaskChange[],
    localSystem: SystemConnection,
    externalSystem: SystemConnection,
    options?: SyncOptions
  ): Promise<{
    summary: SyncSummary;
    errors: SyncError[];
    warnings: SyncWarning[];
    changes: TaskChange[];
  }> {
    const summary: SyncSummary = {
      totalTasks: changes.length,
      importedTasks: 0,
      updatedTasks: 0,
      exportedTasks: 0,
      deletedTasks: 0,
      conflicts: 0,
      skippedTasks: 0
    };
    
    const errors: SyncError[] = [];
    const warnings: SyncWarning[] = [];
    
    for (const change of changes) {
      try {
        switch (change.type) {
          case 'created':
            await this.importTask(change, localSystem, externalSystem);
            summary.importedTasks++;
            break;
            
          case 'updated':
            await this.updateTask(change, localSystem, externalSystem);
            summary.updatedTasks++;
            break;
            
          case 'deleted':
            await this.deleteTask(change, localSystem, externalSystem);
            summary.deletedTasks++;
            break;
        }
      } catch (error) {
        errors.push({
          code: 'APPLY_CHANGES_FAILED',
          message: `Ошибка применения изменения для задачи ${change.taskId}: ${error}`,
          taskId: change.taskId,
          severity: 'error',
          details: error
        });
        summary.skippedTasks++;
      }
    }
    
    return { summary, errors, warnings, changes };
  }

  /**
   * Импорт задачи из внешней системы
   */
  private async importTask(
    change: TaskChange,
    localSystem: SystemConnection,
    externalSystem: SystemConnection
  ): Promise<void> {
    const externalTask = await externalSystem.getTask(change.taskId);
    await localSystem.createTask(this.transformExternalTask(externalTask));
  }

  /**
   * Обновление задачи
   */
  private async updateTask(
    change: TaskChange,
    localSystem: SystemConnection,
    externalSystem: SystemConnection
  ): Promise<void> {
    // В зависимости от направления синхронизации
    if (change.source === 'external') {
      // Обновляем локальную задачу
      await localSystem.updateTask(change.taskId, this.transformChanges(change.changes));
    } else {
      // Обновляем внешнюю задачу
      await externalSystem.updateTask(change.taskId, this.transformChanges(change.changes));
    }
  }

  /**
   * Удаление задачи
   */
  private async deleteTask(
    change: TaskChange,
    localSystem: SystemConnection,
    externalSystem: SystemConnection
  ): Promise<void> {
    // В зависимости от настроек
    if (change.source === 'external') {
      await localSystem.deleteTask(change.taskId);
    } else {
      await externalSystem.deleteTask(change.taskId);
    }
  }

  /**
   * Трансформация внешней задачи
   */
  private transformExternalTask(externalTask: ExternalTask): any {
    return {
      title: externalTask.title,
      description: externalTask.description,
      status: this.transformStatus(externalTask.status),
      priority: this.transformPriority(externalTask.priority),
      assignee: externalTask.assignee,
      dueDate: externalTask.dueDate,
      labels: externalTask.labels,
      customFields: externalTask.customFields
    };
  }

  /**
   * Трансформация изменений
   */
  private transformChanges(changes: FieldChange[]): any {
    const transformed: any = {};
    
    for (const change of changes) {
      switch (change.field) {
        case 'status':
          transformed[change.field] = this.transformStatus(change.newValue);
          break;
        case 'priority':
          transformed[change.field] = this.transformPriority(change.newValue);
          break;
        default:
          transformed[change.field] = change.newValue;
      }
    }
    
    return transformed;
  }

  /**
   * Трансформация статуса
   */
  private transformStatus(status: string): string {
    // Маппинг статусов между системами
    const statusMappings: Record<string, string> = {
      'todo': 'To Do',
      'in_progress': 'In Progress',
      'done': 'Done',
      'open': 'Open',
      'resolved': 'Resolved',
      'closed': 'Closed'
    };
    
    return statusMappings[status.toLowerCase()] || status;
  }

  /**
   * Трансформация приоритета
   */
  private transformPriority(priority: string): string {
    // Маппинг приоритетов между системами
    const priorityMappings: Record<string, string> = {
      'lowest': 'Low',
      'low': 'Low',
      'medium': 'Medium',
      'high': 'High',
      'highest': 'High'
    };
    
    return priorityMappings[priority.toLowerCase()] || priority;
  }

  /**
   * Настройка webhook'ов
   */
  setupWebhook(systemId: string, webhookUrl: string): Promise<void> {
    const system = this.systemConnections.get(systemId);
    if (!system) {
      throw new Error('Система не подключена');
    }
    
    return system.setupWebhook(webhookUrl);
  }

  /**
   * Обработка webhook событий
   */
  async handleWebhook(event: WebhookEvent): Promise<void> {
    const handler = this.webhookHandlers.get(event.source);
    if (!handler) {
      throw new Error(`Обработчик для источника ${event.source} не найден`);
    }
    
    await handler.handle(event);
  }

  /**
   * Получение метрик интеграции
   */
  getIntegrationMetrics(): IntegrationMetrics {
    const systems = Array.from(this.systemConnections.values());
    
    return {
      totalSyncs: 0, // Будет реализовано с сохранением истории
      successfulSyncs: 0,
      failedSyncs: 0,
      totalTasksSynced: 0,
      averageSyncDuration: 0,
      lastSyncDate: null,
      errorRate: 0,
      systemsStatus: systems.map(system => ({
        systemId: system.config.id,
        systemName: system.config.name,
        isConnected: system.isConnected,
        lastSyncDate: system.lastSyncDate,
        syncSuccessRate: 100, // Упрощенно
        errorCount: 0,
        warningCount: 0,
        health: 'healthy'
      }))
    };
  }

  /**
   * Разрешение конфликтов
   */
  async resolveConflict(conflict: ConflictResolution): Promise<void> {
    const system = this.systemConnections.get(conflict.id.split(':')[0]);
    if (!system) {
      throw new Error('Система не найдена');
    }
    
    await system.resolveConflict(conflict);
  }

  /**
   * Инициализация обработчиков webhook'ов
   */
  private initializeWebhookHandlers(): void {
    this.webhookHandlers.set('jira', new JiraWebhookHandler());
    this.webhookHandlers.set('trello', new TrelloWebhookHandler());
    this.webhookHandlers.set('github', new GitHubWebhookHandler());
  }

  /**
   * Обновление метрик синхронизации
   */
  private updateSyncMetrics(
    localSystemId: string,
    externalSystemId: string,
    result: SyncResult
  ): void {
    // Здесь можно добавить логику сохранения метрик
    // Например, в базу данных или файл
    console.log(`Синхронизация между ${localSystemId} и ${externalSystemId} завершена:`, result.summary);
  }
}

/**
 * Абстрактный класс для соединений с системами
 */
abstract class SystemConnection {
  protected config: TaskManagementSystem;
  protected isConnected = false;
  public lastSyncDate: Date | null = null;

  constructor(config: TaskManagementSystem) {
    this.config = config;
  }

  abstract testConnection(): Promise<void>;
  abstract getTasks(filterCriteria?: FilterCriteria): Promise<ExternalTask[]>;
  abstract getTask(taskId: string): Promise<ExternalTask>;
  abstract createTask(task: any): Promise<string>;
  abstract updateTask(taskId: string, updates: any): Promise<void>;
  abstract deleteTask(taskId: string): Promise<void>;
  abstract setupWebhook(webhookUrl: string): Promise<void>;
  abstract resolveConflict(conflict: ConflictResolution): Promise<void>;
}

/**
 * Конкретные реализации для различных систем
 */
class JiraConnection extends SystemConnection {
  async testConnection(): Promise<void> {
    // Реализация тестирования соединения с Jira
  }

  async getTasks(filterCriteria?: FilterCriteria): Promise<ExternalTask[]> {
    // Реализация получения задач из Jira
    return [];
  }

  async getTask(taskId: string): Promise<ExternalTask> {
    // Реализация получения конкретной задачи из Jira
    return {} as ExternalTask;
  }

  async createTask(task: any): Promise<string> {
    // Реализация создания задачи в Jira
    return '';
  }

  async updateTask(taskId: string, updates: any): Promise<void> {
    // Реализация обновления задачи в Jira
  }

  async deleteTask(taskId: string): Promise<void> {
    // Реализация удаления задачи из Jira
  }

  async setupWebhook(webhookUrl: string): Promise<void> {
    // Реализация настройки webhook в Jira
  }

  async resolveConflict(conflict: ConflictResolution): Promise<void> {
    // Реализация разрешения конфликта в Jira
  }
}

class TrelloConnection extends SystemConnection {
  async testConnection(): Promise<void> {
    // Реализация тестирования соединения с Trello
  }

  async getTasks(filterCriteria?: FilterCriteria): Promise<ExternalTask[]> {
    return [];
  }

  async getTask(taskId: string): Promise<ExternalTask> {
    return {} as ExternalTask;
  }

  async createTask(task: any): Promise<string> {
    return '';
  }

  async updateTask(taskId: string, updates: any): Promise<void> {
    // Implementation
  }

  async deleteTask(taskId: string): Promise<void> {
    // Implementation
  }

  async setupWebhook(webhookUrl: string): Promise<void> {
    // Implementation
  }

  async resolveConflict(conflict: ConflictResolution): Promise<void> {
    // Implementation
  }
}

class GitHubConnection extends SystemConnection {
  async testConnection(): Promise<void> {
    // Implementation
  }

  async getTasks(filterCriteria?: FilterCriteria): Promise<ExternalTask[]> {
    return [];
  }

  async getTask(taskId: string): Promise<ExternalTask> {
    return {} as ExternalTask;
  }

  async createTask(task: any): Promise<string> {
    return '';
  }

  async updateTask(taskId: string, updates: any): Promise<void> {
    // Implementation
  }

  async deleteTask(taskId: string): Promise<void> {
    // Implementation
  }

  async setupWebhook(webhookUrl: string): Promise<void> {
    // Implementation
  }

  async resolveConflict(conflict: ConflictResolution): Promise<void> {
    // Implementation
  }
}

class AzureDevOpsConnection extends SystemConnection {
  async testConnection(): Promise<void> {
    // Implementation
  }

  async getTasks(filterCriteria?: FilterCriteria): Promise<ExternalTask[]> {
    return [];
  }

  async getTask(taskId: string): Promise<ExternalTask> {
    return {} as ExternalTask;
  }

  async createTask(task: any): Promise<string> {
    return '';
  }

  async updateTask(taskId: string, updates: any): Promise<void> {
    // Implementation
  }

  async deleteTask(taskId: string): Promise<void> {
    // Implementation
  }

  async setupWebhook(webhookUrl: string): Promise<void> {
    // Implementation
  }

  async resolveConflict(conflict: ConflictResolution): Promise<void> {
    // Implementation
  }
}

/**
 * Обработчики webhook событий
 */
abstract class WebhookHandler {
  abstract handle(event: WebhookEvent): Promise<void>;
}

class JiraWebhookHandler extends WebhookHandler {
  async handle(event: WebhookEvent): Promise<void> {
    // Обработка webhook событий от Jira
    console.log('Обработка Jira webhook:', event);
  }
}

class TrelloWebhookHandler extends WebhookHandler {
  async handle(event: WebhookEvent): Promise<void> {
    // Обработка webhook событий от Trello
    console.log('Обработка Trello webhook:', event);
  }
}

class GitHubWebhookHandler extends WebhookHandler {
  async handle(event: WebhookEvent): Promise<void> {
    // Обработка webhook событий от GitHub
    console.log('Обработка GitHub webhook:', event);
  }
}

// Дополнительные интерфейсы
interface SyncOptions {
  filterCriteria?: FilterCriteria;
  conflictResolution?: 'skip' | 'overwrite' | 'merge';
  syncDirection?: 'one-way' | 'two-way';
  includeSubtasks?: boolean;
  includeComments?: boolean;
  includeAttachments?: boolean;
}

// Алиас для обратной совместимости
export type TaskIntegrationService = TaskManagementIntegrationService;