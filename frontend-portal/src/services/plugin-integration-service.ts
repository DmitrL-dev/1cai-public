import { BehaviorSubject, Observable } from 'rxjs';
import { PluginManagerService, PluginInstance, PluginManifest, PluginContext } from './plugin-manager-service';
import { PluginAPIService } from './plugin-api-service';
import { PluginRegistryService } from './plugin-registry-service';

export interface PluginIntegrationConfig {
  enabledAgents: string[];
  autoLoad: boolean;
  sandboxMode: boolean;
  resourceLimit: {
    memory: number; // MB
    cpu: number; // percentage
    storage: number; // MB
  };
  security: {
    allowNetworkAccess: boolean;
    allowFileSystemAccess: boolean;
    requireSignature: boolean;
  };
}

export interface PluginAgentBinding {
  pluginId: string;
  agentType: string;
  enabled: boolean;
  configuration: Record<string, any>;
  permissions: string[];
  hooks: PluginHookBinding[];
}

export interface PluginHookBinding {
  hookName: string;
  callback: Function;
  priority: number;
  enabled: boolean;
}

export interface PluginResourceMapping {
  pluginId: string;
  agentType: string;
  resources: {
    components: Map<string, any>;
    services: Map<string, any>;
    apis: Map<string, any>;
  };
}

export class PluginIntegrationService {
  private config: PluginIntegrationConfig = {
    enabledAgents: ['architect', 'developer', 'pm', 'ba', 'data_analyst'],
    autoLoad: true,
    sandboxMode: true,
    resourceLimit: {
      memory: 100, // MB
      cpu: 50, // percentage
      storage: 1000 // MB
    },
    security: {
      allowNetworkAccess: true,
      allowFileSystemAccess: false,
      requireSignature: true
    }
  };

  private agentBindings = new Map<string, PluginAgentBinding[]>();
  private resourceMappings = new Map<string, PluginResourceMapping>();
  private activeHooks = new Map<string, PluginHookBinding[]>();
  
  // Integration state
  private isInitialized = false;
  private integrationMetrics = {
    totalIntegrations: 0,
    activeIntegrations: 0,
    totalResources: 0,
    totalHooks: 0,
    memoryUsage: 0,
    errorCount: 0
  };

  // Subjects for monitoring
  private integrationEventSubject = new BehaviorSubject<any>(null);
  private agentIntegrationSubject = new BehaviorSubject<Map<string, PluginAgentBinding[]>>(new Map());
  private metricsSubject = new BehaviorSubject<typeof this.integrationMetrics>(this.integrationMetrics);
  
  // Observables
  public integrationEvent$ = this.integrationEventSubject.asObservable();
  public agentIntegration$ = this.agentIntegrationSubject.asObservable();
  public metrics$ = this.metricsSubject.asObservable();

  constructor(
    private pluginManager: PluginManagerService,
    private apiService: PluginAPIService,
    private registryService: PluginRegistryService
  ) {}

  public async initialize(): Promise<void> {
    if (this.isInitialized) {
      return;
    }

    try {
      // Subscribe to plugin events
      this.pluginManager.pluginEvent$.subscribe(event => {
        if (event) {
          this.handlePluginEvent(event);
        }
      });

      // Subscribe to plugin list changes
      this.pluginManager.pluginList$.subscribe(plugins => {
        this.updateAgentIntegrations(plugins);
      });

      // Initialize API service
      this.apiService.updateConfig({
        baseURL: '/api/plugins/integration'
      });

      this.isInitialized = true;
      this.emitIntegrationEvent({
        type: 'initialized',
        timestamp: new Date(),
        data: { config: this.config }
      });

      console.log('Plugin Integration Service initialized');
    } catch (error) {
      console.error('Failed to initialize Plugin Integration Service:', error);
      throw error;
    }
  }

  public async integratePluginWithAgent(
    pluginId: string,
    agentType: string,
    config: Record<string, any> = {}
  ): Promise<string> {
    if (!this.isInitialized) {
      throw new Error('Service not initialized');
    }

    if (!this.config.enabledAgents.includes(agentType)) {
      throw new Error(`Agent ${agentType} is not enabled for plugin integration`);
    }

    const plugin = this.pluginManager.getPlugin(pluginId);
    if (!plugin) {
      throw new Error(`Plugin ${pluginId} not found`);
    }

    if (!plugin.manifest.compatibility.supportedAgents.includes('all') && 
        !plugin.manifest.compatibility.supportedAgents.includes(agentType)) {
      throw new Error(`Plugin ${pluginId} does not support agent ${agentType}`);
    }

    try {
      // Create integration binding
      const binding: PluginAgentBinding = {
        pluginId,
        agentType,
        enabled: true,
        configuration: config,
        permissions: this.extractPluginPermissions(plugin.manifest),
        hooks: []
      };

      // Load plugin resources for the agent
      await this.loadPluginResourcesForAgent(plugin, agentType);

      // Register hooks
      await this.registerPluginHooks(plugin, agentType);

      // Add to agent bindings
      const agentBindings = this.agentBindings.get(agentType) || [];
      agentBindings.push(binding);
      this.agentBindings.set(agentType, agentBindings);

      // Update metrics
      this.integrationMetrics.totalIntegrations++;
      this.integrationMetrics.activeIntegrations++;

      // Update observability
      this.updateAgentIntegrationMap();
      this.updateMetrics();

      this.emitIntegrationEvent({
        type: 'integration_created',
        pluginId,
        agentType,
        timestamp: new Date(),
        data: binding
      });

      return `${pluginId}_${agentType}`;
    } catch (error) {
      this.integrationMetrics.errorCount++;
      this.updateMetrics();
      throw error;
    }
  }

  public async removePluginFromAgent(pluginId: string, agentType: string): Promise<void> {
    const agentBindings = this.agentBindings.get(agentType) || [];
    const bindingIndex = agentBindings.findIndex(b => b.pluginId === pluginId);
    
    if (bindingIndex === -1) {
      throw new Error(`Plugin ${pluginId} not integrated with agent ${agentType}`);
    }

    try {
      const binding = agentBindings[bindingIndex];
      
      // Remove hooks
      await this.unregisterPluginHooks(pluginId, agentType);

      // Unload resources
      await this.unloadPluginResourcesForAgent(pluginId, agentType);

      // Remove binding
      agentBindings.splice(bindingIndex, 1);
      this.agentBindings.set(agentType, agentBindings);

      // Update metrics
      this.integrationMetrics.activeIntegrations--;

      // Update observability
      this.updateAgentIntegrationMap();
      this.updateMetrics();

      this.emitIntegrationEvent({
        type: 'integration_removed',
        pluginId,
        agentType,
        timestamp: new Date()
      });
    } catch (error) {
      this.integrationMetrics.errorCount++;
      this.updateMetrics();
      throw error;
    }
  }

  public getAgentIntegrations(agentType: string): PluginAgentBinding[] {
    return this.agentBindings.get(agentType) || [];
  }

  public getPluginIntegrations(pluginId: string): Array<{ agentType: string; binding: PluginAgentBinding }> {
    const integrations: Array<{ agentType: string; binding: PluginAgentBinding }> = [];
    
    this.agentBindings.forEach((bindings, agentType) => {
      const binding = bindings.find(b => b.pluginId === pluginId);
      if (binding) {
        integrations.push({ agentType, binding });
      }
    });

    return integrations;
  }

  public async loadPluginResource(
    pluginId: string,
    agentType: string,
    resourceType: 'component' | 'service' | 'api',
    resourceName: string
  ): Promise<any> {
    const mapping = this.resourceMappings.get(`${pluginId}_${agentType}`);
    if (!mapping) {
      throw new Error(`Resource mapping not found for ${pluginId} on ${agentType}`);
    }

    const resources = mapping.resources;
    let targetMap: Map<string, any>;

    switch (resourceType) {
      case 'component':
        targetMap = resources.components;
        break;
      case 'service':
        targetMap = resources.services;
        break;
      case 'api':
        targetMap = resources.apis;
        break;
      default:
        throw new Error(`Unknown resource type: ${resourceType}`);
    }

    if (targetMap.has(resourceName)) {
      return targetMap.get(resourceName);
    }

    // Load resource if not already loaded
    const resource = await this.loadResource(pluginId, resourceType, resourceName);
    targetMap.set(resourceName, resource);
    
    return resource;
  }

  public registerPluginHook(
    pluginId: string,
    agentType: string,
    hookName: string,
    callback: Function,
    priority: number = 0
  ): void {
    const hookBinding: PluginHookBinding = {
      hookName,
      callback,
      priority,
      enabled: true
    };

    const agentBindings = this.agentBindings.get(agentType);
    if (!agentBindings) {
      throw new Error(`No integrations found for agent ${agentType}`);
    }

    const binding = agentBindings.find(b => b.pluginId === pluginId);
    if (!binding) {
      throw new Error(`Plugin ${pluginId} not integrated with agent ${agentType}`);
    }

    binding.hooks.push(hookBinding);

    // Add to global hook registry
    const globalHooks = this.activeHooks.get(hookName) || [];
    globalHooks.push({
      ...hookBinding,
      pluginId,
      agentType
    } as any);
    
    // Sort by priority
    globalHooks.sort((a, b) => (b as any).priority - (a as any).priority);
    this.activeHooks.set(hookName, globalHooks);

    this.integrationMetrics.totalHooks++;
    this.updateMetrics();

    this.emitIntegrationEvent({
      type: 'hook_registered',
      pluginId,
      agentType,
      hookName,
      timestamp: new Date()
    });
  }

  public unregisterPluginHook(pluginId: string, agentType: string, hookName: string): void {
    // Remove from agent binding
    const agentBindings = this.agentBindings.get(agentType);
    if (agentBindings) {
      const binding = agentBindings.find(b => b.pluginId === pluginId);
      if (binding) {
        binding.hooks = binding.hooks.filter(h => h.hookName !== hookName);
      }
    }

    // Remove from global registry
    const globalHooks = this.activeHooks.get(hookName);
    if (globalHooks) {
      const filteredHooks = globalHooks.filter(h => 
        !(h as any).pluginId || (h as any).pluginId !== pluginId || (h as any).agentType !== agentType
      );
      this.activeHooks.set(hookName, filteredHooks);
    }

    this.integrationMetrics.totalHooks--;
    this.updateMetrics();

    this.emitIntegrationEvent({
      type: 'hook_unregistered',
      pluginId,
      agentType,
      hookName,
      timestamp: new Date()
    });
  }

  public async emitHook(hookName: string, agentType: string, ...args: any[]): Promise<any[]> {
    const globalHooks = this.activeHooks.get(hookName) || [];
    const agentSpecificHooks = globalHooks.filter(h => 
      !(h as any).agentType || (h as any).agentType === agentType
    );

    const results: any[] = [];
    
    for (const hook of agentSpecificHooks) {
      if (hook.enabled) {
        try {
          const result = await hook.callback(...args);
          results.push(result);
        } catch (error) {
          console.error(`Hook ${hookName} error:`, error);
        }
      }
    }

    return results;
  }

  private async loadPluginResourcesForAgent(plugin: PluginInstance, agentType: string): Promise<void> {
    const mapping: PluginResourceMapping = {
      pluginId: plugin.manifest.id,
      agentType,
      resources: {
        components: new Map(),
        services: new Map(),
        apis: new Map()
      }
    };

    // Load each resource type
    for (const resource of plugin.manifest.resources) {
      if (this.shouldLoadResource(resource, agentType)) {
        try {
          const loadedResource = await this.loadResource(
            plugin.manifest.id,
            resource.type,
            resource.name
          );
          
          switch (resource.type) {
            case 'component':
              mapping.resources.components.set(resource.name, loadedResource);
              break;
            case 'service':
              mapping.resources.services.set(resource.name, loadedResource);
              break;
            case 'api':
              mapping.resources.apis.set(resource.name, loadedResource);
              break;
          }
          
          this.integrationMetrics.totalResources++;
        } catch (error) {
          console.warn(`Failed to load resource ${resource.name}:`, error);
        }
      }
    }

    this.resourceMappings.set(`${plugin.manifest.id}_${agentType}`, mapping);
  }

  private shouldLoadResource(resource: any, agentType: string): boolean {
    // Load resources based on agent compatibility
    return !resource.agentSpecific || 
           !pluginRequiresSpecificAgent(resource) ||
           pluginSupportsAgent(resource, agentType);
  }

  private async loadResource(
    pluginId: string,
    resourceType: string,
    resourceName: string
  ): Promise<any> {
    switch (resourceType) {
      case 'service':
        return this.apiService.createService(resourceName);
      case 'component':
        return this.apiService.createComponent(resourceName);
      case 'api':
        return this.createPluginAPI(pluginId, resourceName);
      default:
        throw new Error(`Unknown resource type: ${resourceType}`);
    }
  }

  private async unloadPluginResourcesForAgent(pluginId: string, agentType: string): Promise<void> {
    const mappingKey = `${pluginId}_${agentType}`;
    const mapping = this.resourceMappings.get(mappingKey);
    
    if (mapping) {
      // Clean up resources
      mapping.resources.components.clear();
      mapping.resources.services.clear();
      mapping.resources.apis.clear();
      
      this.resourceMappings.delete(mappingKey);
      this.integrationMetrics.totalResources--;
    }
  }

  private async registerPluginHooks(plugin: PluginInstance, agentType: string): Promise<void> {
    // Register built-in hooks based on plugin type
    const hooks = this.getPluginHooks(plugin.manifest);
    
    for (const hookName of hooks) {
      const callback = this.createHookCallback(plugin.manifest.id, hookName);
      this.registerPluginHook(plugin.manifest.id, agentType, hookName, callback, 0);
    }
  }

  private async unregisterPluginHooks(pluginId: string, agentType: string): Promise<void> {
    const agentBindings = this.agentBindings.get(agentType);
    if (!agentBindings) return;

    const binding = agentBindings.find(b => b.pluginId === pluginId);
    if (!binding) return;

    // Unregister all hooks for this plugin
    for (const hook of binding.hooks) {
      this.unregisterPluginHook(pluginId, agentType, hook.hookName);
    }
  }

  private getPluginHooks(manifest: PluginManifest): string[] {
    const hooks: string[] = [];
    
    // Add hooks based on plugin category
    switch (manifest.category) {
      case 'development':
        hooks.push('onCodeGenerated', 'onFileChanged', 'onBuildComplete');
        break;
      case 'analytics':
        hooks.push('onDataProcessed', 'onReportGenerated', 'onMetricCalculated');
        break;
      case 'integration':
        hooks.push('onConnectionEstablished', 'onDataSynced', 'onIntegrationError');
        break;
      case 'theme':
        hooks.push('onThemeChanged', 'onUIUpdate', 'onStyleApplied');
        break;
    }

    // Add generic hooks
    hooks.push('onPluginInit', 'onPluginCleanup');

    return hooks;
  }

  private createHookCallback(pluginId: string, hookName: string): Function {
    return (...args: any[]) => {
      console.log(`Hook ${hookName} called by plugin ${pluginId} with args:`, args);
      return null; // Plugin hook implementation would go here
    };
  }

  private extractPluginPermissions(manifest: PluginManifest): string[] {
    return manifest.permissions.map(p => p.type);
  }

  private createPluginAPI(pluginId: string, apiName: string): any {
    // Create plugin-specific API
    return {
      pluginId,
      apiName,
      methods: {
        get: (path: string, params?: any) => this.apiService.callAPI(pluginId, path, { method: 'GET', params }),
        post: (path: string, data?: any) => this.apiService.callAPI(pluginId, path, { method: 'POST', body: JSON.stringify(data) }),
        put: (path: string, data?: any) => this.apiService.callAPI(pluginId, path, { method: 'PUT', body: JSON.stringify(data) }),
        delete: (path: string) => this.apiService.callAPI(pluginId, path, { method: 'DELETE' })
      }
    };
  }

  private handlePluginEvent(event: any): void {
    switch (event.type) {
      case 'activated':
        this.handlePluginActivated(event);
        break;
      case 'deactivated':
        this.handlePluginDeactivated(event);
        break;
      case 'uninstalled':
        this.handlePluginUninstalled(event);
        break;
    }
  }

  private async handlePluginActivated(event: any): Promise<void> {
    // Auto-integrate if configured
    if (this.config.autoLoad) {
      for (const agentType of this.config.enabledAgents) {
        try {
          await this.integratePluginWithAgent(event.pluginId, agentType);
        } catch (error) {
          console.warn(`Failed to integrate plugin ${event.pluginId} with agent ${agentType}:`, error);
        }
      }
    }
  }

  private async handlePluginDeactivated(event: any): Promise<void> {
    // Remove all integrations
    const integrations = this.getPluginIntegrations(event.pluginId);
    for (const { agentType } of integrations) {
      await this.removePluginFromAgent(event.pluginId, agentType);
    }
  }

  private async handlePluginUninstalled(event: any): Promise<void> {
    // Clean up all references
    await this.handlePluginDeactivated(event);
  }

  private updateAgentIntegrations(plugins: PluginInstance[]): void {
    // Update integration metrics based on current plugins
    let totalIntegrations = 0;
    
    this.agentBindings.forEach(bindings => {
      totalIntegrations += bindings.filter(b => b.enabled).length;
    });
    
    this.integrationMetrics.activeIntegrations = totalIntegrations;
    this.updateMetrics();
  }

  private updateAgentIntegrationMap(): void {
    const integrationMap = new Map<string, PluginAgentBinding[]>();
    
    this.agentBindings.forEach((bindings, agentType) => {
      integrationMap.set(agentType, [...bindings]);
    });
    
    this.agentIntegrationSubject.next(integrationMap);
  }

  private updateMetrics(): void {
    this.metricsSubject.next({ ...this.integrationMetrics });
  }

  private emitIntegrationEvent(event: any): void {
    this.integrationEventSubject.next(event);
  }

  public getIntegrationStatistics(): {
    totalIntegrations: number;
    activeIntegrations: number;
    integrationsByAgent: Record<string, number>;
    totalResources: number;
    totalHooks: number;
    memoryUsage: number;
    errorRate: number;
  } {
    const integrationsByAgent: Record<string, number> = {};
    
    this.agentBindings.forEach((bindings, agentType) => {
      integrationsByAgent[agentType] = bindings.filter(b => b.enabled).length;
    });

    return {
      totalIntegrations: this.integrationMetrics.totalIntegrations,
      activeIntegrations: this.integrationMetrics.activeIntegrations,
      integrationsByAgent,
      totalResources: this.integrationMetrics.totalResources,
      totalHooks: this.integrationMetrics.totalHooks,
      memoryUsage: this.integrationMetrics.memoryUsage,
      errorRate: this.integrationMetrics.totalIntegrations > 0 
        ? this.integrationMetrics.errorCount / this.integrationMetrics.totalIntegrations 
        : 0
    };
  }

  public updateConfig(config: Partial<PluginIntegrationConfig>): void {
    this.config = { ...this.config, ...config };
    this.emitIntegrationEvent({
      type: 'config_updated',
      timestamp: new Date(),
      data: config
    });
  }

  public getConfig(): PluginIntegrationConfig {
    return { ...this.config };
  }

  public cleanup(): void {
    // Remove all integrations
    this.agentBindings.forEach((bindings, agentType) => {
      bindings.forEach(binding => {
        this.removePluginFromAgent(binding.pluginId, agentType).catch(console.error);
      });
    });

    // Clear maps
    this.agentBindings.clear();
    this.resourceMappings.clear();
    this.activeHooks.clear();

    // Complete subjects
    this.integrationEventSubject.complete();
    this.agentIntegrationSubject.complete();
    this.metricsSubject.complete();
  }
}

// Helper functions
function pluginRequiresSpecificAgent(resource: any): boolean {
  return resource.requiresAgent === true;
}

function pluginSupportsAgent(resource: any, agentType: string): boolean {
  return !resource.supportedAgents || 
         resource.supportedAgents.includes('all') || 
         resource.supportedAgents.includes(agentType);
}