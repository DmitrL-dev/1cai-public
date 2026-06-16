import { BehaviorSubject, Observable } from 'rxjs';

export interface PluginAPIConfig {
  baseURL: string;
  version: string;
  timeout: number;
  rateLimit: {
    requests: number;
    window: number; // в миллисекундах
  };
}

export interface PluginResource {
  type: 'service' | 'component' | 'api' | 'hook' | 'middleware';
  name: string;
  description?: string;
  config?: Record<string, any>;
  permissions?: string[];
}

export interface PluginAPIEndpoint {
  path: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  description: string;
  parameters?: Array<{
    name: string;
    type: 'text' | 'numeric' | 'boolean' | 'object' | 'array';
    required: boolean;
    description?: string;
  }>;
  response?: {
    type: 'object' | 'array' | 'text' | 'numeric' | 'boolean';
    description?: string;
  };
  permissions?: string[];
}

export interface PluginHook {
  name: string;
  description: string;
  parameters?: Array<{
    name: string;
    type: string;
    description?: string;
  }>;
  returnType?: string;
}

export interface PluginCapability {
  name: string;
  description: string;
  api: string;
  version: string;
  config?: Record<string, any>;
}

export class PluginAPIService {
  private config: PluginAPIConfig = {
    baseURL: '/api/plugins',
    version: '1.0.0',
    timeout: 30000,
    rateLimit: {
      requests: 100,
      window: 60000 // 1 минута
    }
  };

  private rateLimitTracker = new Map<string, { count: number; windowStart: number }>();
  
  // Available resources and APIs
  private availableResources = new Map<string, PluginResource>();
  private availableEndpoints = new Map<string, PluginAPIEndpoint[]>();
  private availableHooks = new Map<string, PluginHook[]>();
  private availableCapabilities = new Map<string, PluginCapability>();

  constructor() {
    this.initializeAPIs();
  }

  private initializeAPIs(): void {
    this.registerCoreAPIs();
    this.registerAgentAPIs();
    this.registerSystemAPIs();
    this.registerStorageAPIs();
    this.registerUIAPIs();
  }

  private registerCoreAPIs(): void {
    // Core system APIs
    this.availableEndpoints.set('core', [
      {
        path: '/health',
        method: 'GET',
        description: 'Проверка состояния системы',
        response: { type: 'object', description: 'Статус системы и компонентов' }
      },
      {
        path: '/config',
        method: 'GET',
        description: 'Получение конфигурации системы',
        response: { type: 'object', description: 'Конфигурация системы' }
      },
      {
        path: '/config',
        method: 'PUT',
        description: 'Обновление конфигурации',
        parameters: [
          { name: 'config', type: 'object', required: true, description: 'Новая конфигурация' }
        ],
        permissions: ['system:config:write']
      }
    ]);

    // Plugin management APIs
    this.availableEndpoints.set('plugins', [
      {
        path: '/plugins',
        method: 'GET',
        description: 'Получение списка плагинов',
        response: { type: 'array', description: 'Список установленных плагинов' }
      },
      {
        path: '/plugins',
        method: 'POST',
        description: 'Установка плагина',
        parameters: [
          { name: 'manifest', type: 'object', required: true, description: 'Манифест плагина' }
        ],
        permissions: ['plugin:install']
      },
      {
        path: '/plugins/{id}',
        method: 'GET',
        description: 'Получение информации о плагине',
        response: { type: 'object', description: 'Информация о плагине' }
      },
      {
        path: '/plugins/{id}/activate',
        method: 'POST',
        description: 'Активация плагина',
        permissions: ['plugin:activate']
      },
      {
        path: '/plugins/{id}/deactivate',
        method: 'POST',
        description: 'Деактивация плагина',
        permissions: ['plugin:deactivate']
      },
      {
        path: '/plugins/{id}',
        method: 'DELETE',
        description: 'Удаление плагина',
        permissions: ['plugin:uninstall']
      }
    ]);
  }

  private registerAgentAPIs(): void {
    // Agent-specific APIs
    this.availableEndpoints.set('agents', [
      {
        path: '/agents',
        method: 'GET',
        description: 'Получение списка агентов',
        response: { type: 'array', description: 'Список доступных агентов' }
      },
      {
        path: '/agents/{type}/tasks',
        method: 'GET',
        description: 'Получение задач агента',
        response: { type: 'array', description: 'Список задач агента' }
      },
      {
        path: '/agents/{type}/tasks',
        method: 'POST',
        description: 'Создание задачи для агента',
        parameters: [
          { name: 'task', type: 'object', required: true, description: 'Описание задачи' }
        ],
        permissions: ['agent:task:create']
      },
      {
        path: '/agents/{type}/context',
        method: 'GET',
        description: 'Получение контекста агента',
        response: { type: 'object', description: 'Контекст агента' }
      },
      {
        path: '/agents/{type}/context',
        method: 'POST',
        description: 'Обновление контекста агента',
        parameters: [
          { name: 'context', type: 'object', required: true, description: 'Новый контекст' }
        ],
        permissions: ['agent:context:write']
      }
    ]);
  }

  private registerSystemAPIs(): void {
    // System APIs
    this.availableEndpoints.set('system', [
      {
        path: '/system/logs',
        method: 'GET',
        description: 'Получение системных логов',
        parameters: [
          { name: 'level', type: 'text', required: false, description: 'Уровень логирования' },
          { name: 'limit', type: 'number', required: false, description: 'Лимит записей' }
        ],
        permissions: ['system:logs:read']
      },
      {
        path: '/system/metrics',
        method: 'GET',
        description: 'Получение метрик системы',
        response: { type: 'object', description: 'Метрики производительности' },
        permissions: ['system:metrics:read']
      },
      {
        path: '/system/notifications',
        method: 'GET',
        description: 'Получение уведомлений',
        response: { type: 'array', description: 'Список уведомлений' }
      },
      {
        path: '/system/notifications',
        method: 'POST',
        description: 'Создание уведомления',
        parameters: [
          { name: 'notification', type: 'object', required: true, description: 'Данные уведомления' }
        ],
        permissions: ['system:notifications:create']
      }
    ]);
  }

  private registerStorageAPIs(): void {
    // Storage APIs
    this.availableEndpoints.set('storage', [
      {
        path: '/storage/{bucket}',
        method: 'GET',
        description: 'Получение файлов из хранилища',
        response: { type: 'array', description: 'Список файлов' },
        permissions: ['storage:read']
      },
      {
        path: '/storage/{bucket}',
        method: 'POST',
        description: 'Загрузка файла в хранилище',
        parameters: [
          { name: 'file', type: 'object', required: true, description: 'Файл для загрузки' }
        ],
        permissions: ['storage:write']
      },
      {
        path: '/storage/{bucket}/{key}',
        method: 'DELETE',
        description: 'Удаление файла',
        permissions: ['storage:delete']
      },
      {
        path: '/storage/{bucket}/{key}',
        method: 'GET',
        description: 'Получение файла',
        response: { type: 'object', description: 'Файл и метаданные' }
      }
    ]);
  }

  private registerUIAPIs(): void {
    // UI APIs
    this.availableEndpoints.set('ui', [
      {
        path: '/ui/components',
        method: 'GET',
        description: 'Получение списка UI компонентов',
        response: { type: 'array', description: 'Список доступных компонентов' }
      },
      {
        path: '/ui/themes',
        method: 'GET',
        description: 'Получение списка тем',
        response: { type: 'array', description: 'Список доступных тем' }
      },
      {
        path: '/ui/notifications',
        method: 'POST',
        description: 'Отображение уведомления',
        parameters: [
          { name: 'message', type: 'text', required: true, description: 'Текст сообщения' },
          { name: 'type', type: 'text', required: false, description: 'Тип уведомления' }
        ]
      },
      {
        path: '/ui/modal',
        method: 'POST',
        description: 'Отображение модального окна',
        parameters: [
          { name: 'component', type: 'text', required: true, description: 'Компонент модального окна' },
          { name: 'props', type: 'object', required: false, description: 'Свойства компонента' }
        ]
      }
    ]);
  }

  // Hooks registration
  private initializeHooks(): void {
    // System hooks
    this.availableHooks.set('system', [
      {
        name: 'onSystemInit',
        description: 'Вызывается при инициализации системы',
        returnType: 'void'
      },
      {
        name: 'onSystemShutdown',
        description: 'Вызывается при завершении работы системы',
        returnType: 'void'
      },
      {
        name: 'onConfigChange',
        description: 'Вызывается при изменении конфигурации',
        parameters: [
          { name: 'oldConfig', type: 'object', description: 'Старая конфигурация' },
          { name: 'newConfig', type: 'object', description: 'Новая конфигурация' }
        ],
        returnType: 'void'
      }
    ]);

    // Agent hooks
    this.availableHooks.set('agents', [
      {
        name: 'onAgentActivate',
        description: 'Вызывается при активации агента',
        parameters: [
          { name: 'agentType', type: 'text', description: 'Тип агента' }
        ],
        returnType: 'void'
      },
      {
        name: 'onAgentDeactivate',
        description: 'Вызывается при деактивации агента',
        parameters: [
          { name: 'agentType', type: 'text', description: 'Тип агента' }
        ],
        returnType: 'void'
      },
      {
        name: 'onTaskCreated',
        description: 'Вызывается при создании задачи',
        parameters: [
          { name: 'task', type: 'object', description: 'Созданная задача' }
        ],
        returnType: 'void'
      }
    ]);

    // Plugin hooks
    this.availableHooks.set('plugins', [
      {
        name: 'onPluginInstall',
        description: 'Вызывается при установке плагина',
        parameters: [
          { name: 'plugin', type: 'object', description: 'Устанавливаемый плагин' }
        ],
        returnType: 'void'
      },
      {
        name: 'onPluginActivate',
        description: 'Вызывается при активации плагина',
        parameters: [
          { name: 'plugin', type: 'object', description: 'Активируемый плагин' }
        ],
        returnType: 'void'
      },
      {
        name: 'onPluginUninstall',
        description: 'Вызывается при удалении плагина',
        parameters: [
          { name: 'plugin', type: 'object', description: 'Удаляемый плагин' }
        ],
        returnType: 'void'
      }
    ]);
  }

  // Public API methods
  public async callAPI(
    pluginId: string,
    endpoint: string,
    options: RequestInit = {}
  ): Promise<any> {
    // Rate limiting check
    if (!this.checkRateLimit(pluginId)) {
      throw new Error('Превышен лимит запросов');
    }

    const url = `${this.config.baseURL}${endpoint}`;
    
    const defaultOptions: RequestInit = {
      timeout: this.config.timeout,
      headers: {
        'Content-Type': 'application/json',
        'X-Plugin-ID': pluginId,
        'X-API-Version': this.config.version
      }
    };

    const mergedOptions = { ...defaultOptions, ...options };

    try {
      const response = await fetch(url, mergedOptions);
      
      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      this.updateRateLimit(pluginId);
      
      return data;
    } catch (error) {
      throw new Error(`Plugin API call failed: ${error}`);
    }
  }

  public getAvailableEndpoints(category?: string): PluginAPIEndpoint[] {
    if (category) {
      return this.availableEndpoints.get(category) || [];
    }
    
    return Array.from(this.availableEndpoints.values()).flat();
  }

  public getAvailableHooks(category?: string): PluginHook[] {
    if (category) {
      return this.availableHooks.get(category) || [];
    }
    
    return Array.from(this.availableHooks.values()).flat();
  }

  public registerHook(pluginId: string, hookName: string, callback: Function): void {
    // Registration of plugin hooks
    console.log(`Hook ${hookName} registered by plugin ${pluginId}`);
  }

  public unregisterHook(pluginId: string, hookName: string): void {
    // Unregistration of plugin hooks
    console.log(`Hook ${hookName} unregistered by plugin ${pluginId}`);
  }

  public emitHook(hookName: string, ...args: any[]): void {
    // Emit hook to all registered callbacks
    console.log(`Emitting hook ${hookName} with args:`, args);
  }

  public registerResource(resource: PluginResource): void {
    this.availableResources.set(resource.name, resource);
  }

  public getAvailableResources(): PluginResource[] {
    return Array.from(this.availableResources.values());
  }

  public getResource(resourceName: string): PluginResource | undefined {
    return this.availableResources.get(resourceName);
  }

  public createService(name: string, config?: Record<string, any>): Promise<any> {
    // Create plugin service
    return Promise.resolve({
      name,
      config: config || {},
      methods: {}
    });
  }

  public createComponent(name: string, props?: Record<string, any>): any {
    // Create plugin component
    return {
      name,
      props: props || {},
      render: () => null
    };
  }

  public getConfig(): PluginAPIConfig {
    return { ...this.config };
  }

  public updateConfig(updates: Partial<PluginAPIConfig>): void {
    this.config = { ...this.config, ...updates };
  }

  private checkRateLimit(pluginId: string): boolean {
    const tracker = this.rateLimitTracker.get(pluginId);
    
    if (!tracker) {
      return true;
    }

    const now = Date.now();
    
    // Check if we're still in the same window
    if (now - tracker.windowStart > this.config.rateLimit.window) {
      // Reset window
      tracker.count = 0;
      tracker.windowStart = now;
    }

    return tracker.count < this.config.rateLimit.requests;
  }

  private updateRateLimit(pluginId: string): void {
    const tracker = this.rateLimitTracker.get(pluginId) || {
      count: 0,
      windowStart: Date.now()
    };

    tracker.count++;
    this.rateLimitTracker.set(pluginId, tracker);
  }

  public getAPIDocumentation(): {
    version: string;
    endpoints: Record<string, PluginAPIEndpoint[]>;
    hooks: Record<string, PluginHook[]>;
    resources: PluginResource[];
  } {
    return {
      version: this.config.version,
      endpoints: Object.fromEntries(this.availableEndpoints),
      hooks: Object.fromEntries(this.availableHooks),
      resources: this.getAvailableResources()
    };
  }

  public validatePluginAPI(pluginManifest: any): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Basic validation
    if (!pluginManifest.id) {
      errors.push('Plugin ID is required');
    }

    if (!pluginManifest.version) {
      errors.push('Plugin version is required');
    }

    if (!pluginManifest.scripts || !pluginManifest.scripts.entry) {
      errors.push('Entry script is required');
    }

    // API-specific validation
    if (pluginManifest.api) {
      // Validate API configuration
      const apiConfig = pluginManifest.api;
      
      if (apiConfig.endpoints) {
        apiConfig.endpoints.forEach((endpoint: any, index: number) => {
          if (!endpoint.path) {
            errors.push(`Endpoint ${index} missing path`);
          }
          if (!endpoint.method) {
            errors.push(`Endpoint ${index} missing method`);
          }
        });
      }
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  public cleanup(): void {
    this.rateLimitTracker.clear();
  }
}