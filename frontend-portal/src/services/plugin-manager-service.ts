import { BehaviorSubject, Observable } from 'rxjs';

export interface PluginManifest {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  category: PluginCategory;
  compatibility: {
    minAgentVersion: string;
    supportedAgents: string[];
    dependencies?: string[];
  };
  permissions: PluginPermission[];
  resources: PluginResource[];
  scripts: {
    entry: string;
    activation?: string;
    deactivation?: string;
  };
  metadata: {
    homepage?: string;
    repository?: string;
    license: string;
    keywords?: string[];
    icon?: string;
    screenshots?: string[];
  };
}

export interface PluginResource {
  type: 'component' | 'service' | 'api' | 'command' | 'theme';
  name: string;
  path: string;
  description?: string;
}

export interface PluginPermission {
  type: 'storage' | 'network' | 'ui' | 'agent_access' | 'system';
  description: string;
  required: boolean;
}

export type PluginCategory = 
  | 'development'
  | 'analytics' 
  | 'integration'
  | 'productivity'
  | 'visualization'
  | 'automation'
  | 'custom'
  | 'theme'
  | 'utility';

export interface PluginInstance {
  id: string;
  manifest: PluginManifest;
  status: 'inactive' | 'active' | 'error' | 'loading';
  instance: any;
  context: PluginContext;
  createdAt: Date;
  lastActivated: Date | null;
  error?: string;
  performance?: PluginPerformance;
}

export interface PluginContext {
  agentType: string;
  sessionId: string;
  userId: string;
  permissions: Set<string>;
  configuration: Record<string, any>;
  eventBus: any;
}

export interface PluginPerformance {
  memoryUsage: number;
  cpuUsage: number;
  responseTime: number;
  errorCount: number;
  lastActivity: Date;
}

export interface PluginEvent {
  type: 'installed' | 'activated' | 'deactivated' | 'uninstalled' | 'error' | 'updated';
  pluginId: string;
  version: string;
  timestamp: Date;
  data?: any;
}

export interface PluginConfig {
  autoUpdate: boolean;
  allowUnsigned: boolean;
  sandboxMode: boolean;
  performanceMonitoring: boolean;
  maxInstances: number;
}

export class PluginManagerService {
  private plugins = new Map<string, PluginInstance>();
  private config: PluginConfig = {
    autoUpdate: false,
    allowUnsigned: false,
    sandboxMode: true,
    performanceMonitoring: true,
    maxInstances: 10
  };
  
  // Subjects для событий
  private pluginEventSubject = new BehaviorSubject<PluginEvent | null>(null);
  private pluginListSubject = new BehaviorSubject<PluginInstance[]>([]);
  private performanceSubject = new BehaviorSubject<Map<string, PluginPerformance>>(new Map());
  
  // Observables
  public pluginEvent$: Observable<PluginEvent | null> = this.pluginEventSubject.asObservable();
  public pluginList$: Observable<PluginInstance[]> = this.pluginListSubject.asObservable();
  public performance$: Observable<Map<string, PluginPerformance>> = this.performanceSubject.asObservable();

  constructor() {
    this.initializeDefaultPlugins();
  }

  private initializeDefaultPlugins(): void {
    // Инициализация встроенных плагинов
    this.loadBuiltInPlugins();
  }

  private loadBuiltInPlugins(): void {
    // Встроенные плагины системы
    const builtInPlugins: PluginManifest[] = [
      {
        id: 'core-ui-extensions',
        name: 'UI Extensions',
        version: '1.0.0',
        description: 'Расширения пользовательского интерфейса',
        author: 'System',
        category: 'utility',
        compatibility: {
          minAgentVersion: '1.0.0',
          supportedAgents: ['all']
        },
        permissions: [
          { type: 'ui', description: 'Доступ к UI компонентам', required: true }
        ],
        resources: [
          { type: 'component', name: 'ContextMenu', path: './components/ContextMenu' },
          { type: 'component', name: 'Toolbar', path: './components/Toolbar' }
        ],
        scripts: {
          entry: './index.js',
          activation: './activate.js'
        },
        metadata: {
          license: 'MIT',
          keywords: ['ui', 'interface', 'extensions']
        }
      },
      {
        id: 'code-snippets',
        name: 'Code Snippets Library',
        version: '1.0.0',
        description: 'Библиотека сниппетов кода для 1С',
        author: 'System',
        category: 'development',
        compatibility: {
          minAgentVersion: '1.0.0',
          supportedAgents: ['developer', 'architect']
        },
        permissions: [
          { type: 'storage', description: 'Сохранение сниппетов', required: true }
        ],
        resources: [
          { type: 'service', name: 'SnippetService', path: './services/SnippetService' },
          { type: 'api', name: 'CodeAPI', path: './api/CodeAPI' }
        ],
        scripts: {
          entry: './index.js'
        },
        metadata: {
          license: 'MIT',
          keywords: ['code', 'snippets', '1c', 'development']
        }
      },
      {
        id: 'project-templates',
        name: 'Project Templates',
        version: '1.0.0',
        description: 'Шаблоны проектов для быстрого старта',
        author: 'System',
        category: 'productivity',
        compatibility: {
          minAgentVersion: '1.0.0',
          supportedAgents: ['architect', 'pm']
        },
        permissions: [
          { type: 'storage', description: 'Управление шаблонами', required: true }
        ],
        resources: [
          { type: 'service', name: 'TemplateService', path: './services/TemplateService' }
        ],
        scripts: {
          entry: './index.js'
        },
        metadata: {
          license: 'MIT',
          keywords: ['templates', 'projects', 'productivity']
        }
      },
      {
        id: 'data-exporters',
        name: 'Data Export Utilities',
        version: '1.0.0',
        description: 'Утилиты экспорта данных в различные форматы',
        author: 'System',
        category: 'analytics',
        compatibility: {
          minAgentVersion: '1.0.0',
          supportedAgents: ['data_analyst', 'ba']
        },
        permissions: [
          { type: 'network', description: 'Доступ к сети для экспорта', required: false },
          { type: 'storage', description: 'Сохранение экспортированных файлов', required: true }
        ],
        resources: [
          { type: 'api', name: 'ExportAPI', path: './api/ExportAPI' },
          { type: 'service', name: 'ExportService', path: './services/ExportService' }
        ],
        scripts: {
          entry: './index.js'
        },
        metadata: {
          license: 'MIT',
          keywords: ['export', 'data', 'analytics']
        }
      },
      {
        id: 'theme-manager',
        name: 'Advanced Theme Manager',
        version: '1.0.0',
        description: 'Расширенное управление темами и стилями',
        author: 'System',
        category: 'theme',
        compatibility: {
          minAgentVersion: '1.0.0',
          supportedAgents: ['all']
        },
        permissions: [
          { type: 'ui', description: 'Изменение UI тем', required: true }
        ],
        resources: [
          { type: 'theme', name: 'ThemeEngine', path: './theme/ThemeEngine' },
          { type: 'component', name: 'ThemeSelector', path: './components/ThemeSelector' }
        ],
        scripts: {
          entry: './index.js'
        },
        metadata: {
          license: 'MIT',
          keywords: ['theme', 'ui', 'customization']
        }
      }
    ];

    builtInPlugins.forEach(manifest => {
      this.createPluginInstance(manifest);
    });
  }

  public async installPlugin(manifest: PluginManifest): Promise<string> {
    try {
      // Проверка совместимости
      if (!this.checkCompatibility(manifest)) {
        throw new Error(`Plugin ${manifest.name} не совместим с текущей версией системы`);
      }

      // Проверка разрешений
      if (!this.validatePermissions(manifest.permissions)) {
        throw new Error(`Недостаточно разрешений для установки плагина ${manifest.name}`);
      }

      // Создание экземпляра плагина
      const instance = await this.createPluginInstance(manifest);
      
      // Автоматическая активация если нужно
      if (this.shouldAutoActivate(manifest)) {
        await this.activatePlugin(instance.id);
      }

      this.emitEvent({
        type: 'installed',
        pluginId: manifest.id,
        version: manifest.version,
        timestamp: new Date()
      });

      return instance.id;
    } catch (error) {
      this.emitEvent({
        type: 'error',
        pluginId: manifest.id,
        version: manifest.version,
        timestamp: new Date(),
        data: { error: error instanceof Error ? error.message : String(error) }
      });
      throw error;
    }
  }

  public async activatePlugin(pluginId: string): Promise<void> {
    const plugin = this.plugins.get(pluginId);
    if (!plugin) {
      throw new Error(`Plugin ${pluginId} не найден`);
    }

    if (plugin.status === 'active') {
      return; // Уже активен
    }

    try {
      plugin.status = 'loading';
      this.updatePluginList();

      // Загрузка ресурсов плагина
      await this.loadPluginResources(plugin);
      
      // Инициализация контекста
      plugin.context = this.createPluginContext(plugin.manifest);
      
      // Активация плагина
      if (plugin.manifest.scripts.activation) {
        await this.executePluginScript(plugin, plugin.manifest.scripts.activation);
      }

      plugin.status = 'active';
      plugin.lastActivated = new Date();
      plugin.error = undefined;

      this.emitEvent({
        type: 'activated',
        pluginId: plugin.manifest.id,
        version: plugin.manifest.version,
        timestamp: new Date()
      });

      this.updatePluginList();
    } catch (error) {
      plugin.status = 'error';
      plugin.error = error instanceof Error ? error.message : String(error);
      
      this.emitEvent({
        type: 'error',
        pluginId: plugin.manifest.id,
        version: plugin.manifest.version,
        timestamp: new Date(),
        data: { error: plugin.error }
      });

      this.updatePluginList();
      throw error;
    }
  }

  public async deactivatePlugin(pluginId: string): Promise<void> {
    const plugin = this.plugins.get(pluginId);
    if (!plugin) {
      throw new Error(`Plugin ${pluginId} не найден`);
    }

    if (plugin.status !== 'active') {
      return;
    }

    try {
      // Выполнение скрипта деактивации
      if (plugin.manifest.scripts.deactivation) {
        await this.executePluginScript(plugin, plugin.manifest.scripts.deactivation);
      }

      // Очистка ресурсов
      await this.unloadPluginResources(plugin);

      plugin.status = 'inactive';

      this.emitEvent({
        type: 'deactivated',
        pluginId: plugin.manifest.id,
        version: plugin.manifest.version,
        timestamp: new Date()
      });

      this.updatePluginList();
    } catch (error) {
      plugin.error = error instanceof Error ? error.message : String(error);
      
      this.emitEvent({
        type: 'error',
        pluginId: plugin.manifest.id,
        version: plugin.manifest.version,
        timestamp: new Date(),
        data: { error: plugin.error }
      });

      this.updatePluginList();
      throw error;
    }
  }

  public async uninstallPlugin(pluginId: string): Promise<void> {
    const plugin = this.plugins.get(pluginId);
    if (!plugin) {
      throw new Error(`Plugin ${pluginId} не найден`);
    }

    // Деактивация если активен
    if (plugin.status === 'active') {
      await this.deactivatePlugin(pluginId);
    }

    // Удаление из реестра
    this.plugins.delete(pluginId);

    this.emitEvent({
      type: 'uninstalled',
      pluginId: plugin.manifest.id,
      version: plugin.manifest.version,
      timestamp: new Date()
    });

    this.updatePluginList();
  }

  public getPlugin(pluginId: string): PluginInstance | undefined {
    return this.plugins.get(pluginId);
  }

  public getAllPlugins(): PluginInstance[] {
    return Array.from(this.plugins.values());
  }

  public getPluginsByCategory(category: PluginCategory): PluginInstance[] {
    return this.getAllPlugins().filter(plugin => plugin.manifest.category === category);
  }

  public getActivePlugins(): PluginInstance[] {
    return this.getAllPlugins().filter(plugin => plugin.status === 'active');
  }

  public updateConfig(updates: Partial<PluginConfig>): void {
    this.config = { ...this.config, ...updates };
  }

  public getConfig(): PluginConfig {
    return { ...this.config };
  }

  private checkCompatibility(manifest: PluginManifest): boolean {
    // Проверка поддержки агента
    if (manifest.compatibility.supportedAgents.includes('all')) {
      return true;
    }
    
    // Здесь должна быть проверка версии системы
    return true; // Упрощено для примера
  }

  private validatePermissions(permissions: PluginPermission[]): boolean {
    for (const permission of permissions) {
      if (permission.required && !this.hasPermission(permission.type)) {
        return false;
      }
    }
    return true;
  }

  private hasPermission(type: string): boolean {
    // Проверка наличия разрешения в конфигурации
    return true; // Упрощено для примера
  }

  private shouldAutoActivate(manifest: PluginManifest): boolean {
    // Автоматическая активация для системных плагинов
    return manifest.author === 'System';
  }

  private async createPluginInstance(manifest: PluginManifest): Promise<PluginInstance> {
    const instance: PluginInstance = {
      id: manifest.id,
      manifest,
      status: 'inactive',
      instance: null,
      context: {} as PluginContext,
      createdAt: new Date(),
      lastActivated: null
    };

    this.plugins.set(manifest.id, instance);
    this.updatePluginList();
    
    return instance;
  }

  private async loadPluginResources(plugin: PluginInstance): Promise<void> {
    // Загрузка ресурсов плагина
    for (const resource of plugin.manifest.resources) {
      try {
        await this.loadResource(plugin, resource);
      } catch (error) {
        console.warn(`Не удалось загрузить ресурс ${resource.name}:`, error);
      }
    }
  }

  private async loadResource(plugin: PluginInstance, resource: PluginResource): Promise<void> {
    // Симуляция загрузки ресурса
    switch (resource.type) {
      case 'service':
        // Загрузка сервиса
        break;
      case 'component':
        // Загрузка компонента
        break;
      case 'api':
        // Загрузка API
        break;
    }
  }

  private async unloadPluginResources(plugin: PluginInstance): Promise<void> {
    // Очистка ресурсов плагина
    for (const resource of plugin.manifest.resources) {
      try {
        await this.unloadResource(plugin, resource);
      } catch (error) {
        console.warn(`Не удалось выгрузить ресурс ${resource.name}:`, error);
      }
    }
  }

  private async unloadResource(plugin: PluginInstance, resource: PluginResource): Promise<void> {
    // Очистка ресурса
  }

  private createPluginContext(manifest: PluginManifest): PluginContext {
    return {
      agentType: 'general',
      sessionId: `plugin_${Date.now()}`,
      userId: 'system',
      permissions: new Set(manifest.permissions.map(p => p.type)),
      configuration: {},
      eventBus: null
    };
  }

  private async executePluginScript(plugin: PluginInstance, scriptPath: string): Promise<void> {
    // Выполнение скрипта плагина (заглушка)
    console.log(`Выполнение скрипта ${scriptPath} для плагина ${plugin.manifest.name}`);
  }

  private emitEvent(event: PluginEvent): void {
    this.pluginEventSubject.next(event);
  }

  private updatePluginList(): void {
    this.pluginListSubject.next([...this.plugins.values()]);
  }

  public getPluginStatistics(): {
    totalPlugins: number;
    activePlugins: number;
    pluginsByCategory: Record<PluginCategory, number>;
    errorCount: number;
    totalMemoryUsage: number;
  } {
    const plugins = this.getAllPlugins();
    const stats = {
      totalPlugins: plugins.length,
      activePlugins: plugins.filter(p => p.status === 'active').length,
      pluginsByCategory: {} as Record<PluginCategory, number>,
      errorCount: plugins.filter(p => p.status === 'error').length,
      totalMemoryUsage: 0
    };

    plugins.forEach(plugin => {
      const category = plugin.manifest.category;
      stats.pluginsByCategory[category] = (stats.pluginsByCategory[category] || 0) + 1;
      
      if (plugin.performance) {
        stats.totalMemoryUsage += plugin.performance.memoryUsage;
      }
    });

    return stats;
  }

  public cleanup(): void {
    // Деактивация всех активных плагинов
    this.getActivePlugins().forEach(plugin => {
      this.deactivatePlugin(plugin.id).catch(console.error);
    });

    this.pluginEventSubject.complete();
    this.pluginListSubject.complete();
    this.performanceSubject.complete();
  }
}