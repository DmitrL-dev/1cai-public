import { BehaviorSubject, Observable } from 'rxjs';
import { PluginManifest, PluginCategory } from './plugin-manager-service';

export interface PluginRegistryEntry {
  id: string;
  manifest: PluginManifest;
  installCount: number;
  rating: number;
  downloadCount: number;
  lastUpdated: Date;
  verified: boolean;
  signature?: string;
  marketplace?: PluginMarketplaceInfo;
  reviews?: PluginReview[];
}

export interface PluginReview {
  id: string;
  userId: string;
  rating: number;
  title: string;
  content: string;
  date: Date;
  helpful: number;
}

export interface PluginMarketplaceInfo {
  featured: boolean;
  category: string;
  tags: string[];
  screenshots: string[];
  changelog: string[];
  compatibility: {
    agentVersions: string[];
    browsers: string[];
  };
  dependencies?: string[];
}

export interface PluginSearchQuery {
  query?: string;
  category?: PluginCategory;
  author?: string;
  rating?: number;
  verified?: boolean;
  featured?: boolean;
  tags?: string[];
  limit?: number;
  offset?: number;
  sortBy?: 'name' | 'rating' | 'downloads' | 'updated' | 'installs';
  sortOrder?: 'asc' | 'desc';
}

export interface PluginSearchResult {
  plugins: PluginRegistryEntry[];
  total: number;
  hasMore: boolean;
  facets: {
    categories: Array<{ category: PluginCategory; count: number }>;
    authors: Array<{ author: string; count: number }>;
    ratings: Array<{ rating: number; count: number }>;
    tags: Array<{ tag: string; count: number }>;
  };
}

export interface PluginDownloadOptions {
  version?: string;
  force?: boolean;
  backup?: boolean;
  checksum?: boolean;
}

export class PluginRegistryService {
  private registry = new Map<string, PluginRegistryEntry>();
  private localRegistry = new Map<string, PluginRegistryEntry>();
  
  // Built-in and official plugins
  private officialPlugins: PluginRegistryEntry[] = [];
  
  // Subjects for real-time updates
  private searchResultSubject = new BehaviorSubject<PluginSearchResult | null>(null);
  private registryUpdateSubject = new BehaviorSubject<PluginRegistryEntry[]>([]);
  
  // Observables
  public searchResult$ = this.searchResultSubject.asObservable();
  public registryUpdate$ = this.registryUpdateSubject.asObservable();

  constructor() {
    this.initializeOfficialPlugins();
  }

  private initializeOfficialPlugins(): void {
    // Official plugins from MiniMax team
    this.officialPlugins = [
      {
        id: 'minimax-code-assistant',
        manifest: {
          id: 'minimax-code-assistant',
          name: 'MiniMax Code Assistant',
          version: '2.1.0',
          description: 'AI-помощник для разработки кода 1С с интеллектуальными подсказками',
          author: 'MiniMax Team',
          category: 'development',
          compatibility: {
            minAgentVersion: '1.0.0',
            supportedAgents: ['developer', 'architect']
          },
          permissions: [
            { type: 'storage', description: 'Доступ к хранилищу кода', required: true },
            { type: 'network', description: 'Сетевые запросы к AI API', required: true },
            { type: 'ui', description: 'UI интеграция', required: true }
          ],
          resources: [
            { type: 'service', name: 'CodeAssistant', path: './services/CodeAssistant' },
            { type: 'component', name: 'CodeSuggestions', path: './components/CodeSuggestions' },
            { type: 'api', name: 'AICodeAPI', path: './api/AICodeAPI' }
          ],
          scripts: {
            entry: './index.js',
            activation: './activate.js'
          },
          metadata: {
            homepage: 'https://minimax.ai/code-assistant',
            repository: 'https://github.com/minimax/code-assistant',
            license: 'MIT',
            keywords: ['ai', 'code', 'assistant', '1c', 'development', 'intelligence']
          }
        },
        installCount: 1247,
        rating: 4.8,
        downloadCount: 3567,
        lastUpdated: new Date('2024-11-15'),
        verified: true,
        signature: 'verified_signature_1',
        marketplace: {
          featured: true,
          category: 'Разработка',
          tags: ['ai', 'code', 'assistant', '1c', 'разработка'],
          screenshots: [
            'https://example.com/screenshots/code-assistant-1.png',
            'https://example.com/screenshots/code-assistant-2.png'
          ],
          changelog: [
            '2.1.0: Улучшенная интеграция с 1C разработкой',
            '2.0.0: Полная переработка интерфейса',
            '1.9.0: Поддержка новых типов 1С объектов'
          ],
          compatibility: {
            agentVersions: ['1.0.0', '1.1.0', '1.2.0'],
            browsers: ['Chrome', 'Edge', 'Firefox', 'Safari']
          }
        },
        reviews: [
          {
            id: 'review_1',
            userId: 'user_dev_001',
            rating: 5,
            title: 'Отличный помощник!',
            content: 'Плагин значительно ускоряет разработку. AI подсказки очень точны.',
            date: new Date('2024-11-10'),
            helpful: 15
          }
        ]
      },
      {
        id: 'minimax-analytics-suite',
        manifest: {
          id: 'minimax-analytics-suite',
          name: 'MiniMax Analytics Suite',
          version: '1.5.2',
          description: 'Расширенная аналитика данных для 1C с ML возможностями',
          author: 'MiniMax Team',
          category: 'analytics',
          compatibility: {
            minAgentVersion: '1.0.0',
            supportedAgents: ['data_analyst', 'ba']
          },
          permissions: [
            { type: 'storage', description: 'Доступ к аналитическим данным', required: true },
            { type: 'network', description: 'ML модели и API', required: true }
          ],
          resources: [
            { type: 'service', name: 'AnalyticsEngine', path: './services/AnalyticsEngine' },
            { type: 'component', name: 'AdvancedCharts', path: './components/AdvancedCharts' },
            { type: 'api', name: 'MLAPI', path: './api/MLAPI' }
          ],
          scripts: {
            entry: './index.js'
          },
          metadata: {
            homepage: 'https://minimax.ai/analytics',
            repository: 'https://github.com/minimax/analytics-suite',
            license: 'Commercial',
            keywords: ['analytics', 'ml', 'data', 'visualization', '1c']
          }
        },
        installCount: 832,
        rating: 4.6,
        downloadCount: 2156,
        lastUpdated: new Date('2024-11-12'),
        verified: true,
        signature: 'verified_signature_2',
        marketplace: {
          featured: true,
          category: 'Аналитика',
          tags: ['analytics', 'ml', 'data', 'visualization', 'отчеты'],
          screenshots: [
            'https://example.com/screenshots/analytics-1.png'
          ],
          changelog: [
            '1.5.2: Улучшенная производительность',
            '1.5.0: Новые типы графиков',
            '1.4.0: ML модели'
          ],
          compatibility: {
            agentVersions: ['1.0.0', '1.1.0'],
            browsers: ['Chrome', 'Edge']
          }
        }
      },
      {
        id: 'minimax-integration-hub',
        manifest: {
          id: 'minimax-integration-hub',
          name: 'MiniMax Integration Hub',
          version: '1.3.1',
          description: 'Централизованный хаб для интеграции с внешними системами',
          author: 'MiniMax Team',
          category: 'integration',
          compatibility: {
            minAgentVersion: '1.0.0',
            supportedAgents: ['all']
          },
          permissions: [
            { type: 'network', description: 'Внешние интеграции', required: true },
            { type: 'storage', description: 'Конфигурации интеграций', required: true }
          ],
          resources: [
            { type: 'service', name: 'IntegrationManager', path: './services/IntegrationManager' },
            { type: 'component', name: 'ConnectionConfig', path: './components/ConnectionConfig' },
            { type: 'api', name: 'ExternalAPI', path: './api/ExternalAPI' }
          ],
          scripts: {
            entry: './index.js'
          },
          metadata: {
            homepage: 'https://minimax.ai/integration',
            repository: 'https://github.com/minimax/integration-hub',
            license: 'MIT',
            keywords: ['integration', 'api', 'external', 'connectors']
          }
        },
        installCount: 445,
        rating: 4.3,
        downloadCount: 987,
        lastUpdated: new Date('2024-11-08'),
        verified: true,
        signature: 'verified_signature_3',
        marketplace: {
          featured: false,
          category: 'Интеграция',
          tags: ['integration', 'api', 'external', 'connectors'],
          changelog: [
            '1.3.1: Исправления багов',
            '1.3.0: Новые коннекторы',
            '1.2.0: Webhook поддержка'
          ],
          compatibility: {
            agentVersions: ['1.0.0', '1.1.0', '1.2.0'],
            browsers: ['Chrome', 'Edge', 'Firefox']
          }
        }
      },
      {
        id: 'community-theme-pack',
        manifest: {
          id: 'community-theme-pack',
          name: 'Community Theme Pack',
          version: '2.0.0',
          description: 'Коллекция тем от сообщества разработчиков',
          author: 'Community',
          category: 'theme',
          compatibility: {
            minAgentVersion: '1.0.0',
            supportedAgents: ['all']
          },
          permissions: [
            { type: 'ui', description: 'Управление темами', required: true }
          ],
          resources: [
            { type: 'theme', name: 'DarkPro', path: './themes/DarkPro' },
            { type: 'theme', name: 'LightModern', path: './themes/LightModern' },
            { type: 'component', name: 'ThemeSelector', path: './components/ThemeSelector' }
          ],
          scripts: {
            entry: './index.js'
          },
          metadata: {
            license: 'MIT',
            keywords: ['theme', 'ui', 'design', 'customization']
          }
        },
        installCount: 2156,
        rating: 4.2,
        downloadCount: 4521,
        lastUpdated: new Date('2024-11-05'),
        verified: false,
        marketplace: {
          featured: true,
          category: 'Темы',
          tags: ['theme', 'ui', 'design', 'customization'],
          changelog: [
            '2.0.0: Полная переработка',
            '1.5.0: Новые темы',
            '1.0.0: Первая версия'
          ],
          compatibility: {
            agentVersions: ['1.0.0', '1.1.0', '1.2.0'],
            browsers: ['Chrome', 'Edge', 'Firefox', 'Safari']
          }
        }
      }
    ];

    // Add official plugins to registry
    this.officialPlugins.forEach(plugin => {
      this.registry.set(plugin.id, plugin);
    });

    this.updateRegistry();
  }

  public async searchPlugins(query: PluginSearchQuery): Promise<PluginSearchResult> {
    let results = Array.from(this.registry.values());
    
    // Apply filters
    if (query.query) {
      const searchTerm = query.query.toLowerCase();
      results = results.filter(plugin => 
        plugin.manifest.name.toLowerCase().includes(searchTerm) ||
        plugin.manifest.description.toLowerCase().includes(searchTerm) ||
        plugin.manifest.metadata.keywords?.some(keyword => 
          keyword.toLowerCase().includes(searchTerm)
        ) ||
        plugin.manifest.author.toLowerCase().includes(searchTerm)
      );
    }

    if (query.category) {
      results = results.filter(plugin => plugin.manifest.category === query.category);
    }

    if (query.author) {
      results = results.filter(plugin => 
        plugin.manifest.author.toLowerCase().includes(query.author!.toLowerCase())
      );
    }

    if (query.rating) {
      results = results.filter(plugin => plugin.rating >= query.rating!);
    }

    if (query.verified !== undefined) {
      results = results.filter(plugin => plugin.verified === query.verified);
    }

    if (query.featured !== undefined) {
      results = results.filter(plugin => 
        plugin.marketplace?.featured === query.featured
      );
    }

    if (query.tags && query.tags.length > 0) {
      results = results.filter(plugin => {
        const pluginTags = [
          ...plugin.manifest.metadata.keywords || [],
          ...plugin.marketplace?.tags || []
        ];
        return query.tags!.some(tag => 
          pluginTags.some(pluginTag => 
            pluginTag.toLowerCase().includes(tag.toLowerCase())
          )
        );
      });
    }

    // Sorting
    const sortBy = query.sortBy || 'rating';
    const sortOrder = query.sortOrder || 'desc';
    
    results.sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'name':
          comparison = a.manifest.name.localeCompare(b.manifest.name);
          break;
        case 'rating':
          comparison = a.rating - b.rating;
          break;
        case 'downloads':
          comparison = a.downloadCount - b.downloadCount;
          break;
        case 'updated':
          comparison = a.lastUpdated.getTime() - b.lastUpdated.getTime();
          break;
        case 'installs':
          comparison = a.installCount - b.installCount;
          break;
      }
      
      return sortOrder === 'desc' ? -comparison : comparison;
    });

    // Pagination
    const offset = query.offset || 0;
    const limit = query.limit || 20;
    const paginatedResults = results.slice(offset, offset + limit);

    // Generate facets
    const facets = {
      categories: this.generateFacet('category'),
      authors: this.generateFacet('author'),
      ratings: this.generateFacet('rating'),
      tags: this.generateFacet('tags')
    };

    const result: PluginSearchResult = {
      plugins: paginatedResults,
      total: results.length,
      hasMore: offset + limit < results.length,
      facets
    };

    this.searchResultSubject.next(result);
    return result;
  }

  private generateFacet(type: 'category' | 'author' | 'rating' | 'tags'): any[] {
    const plugins = Array.from(this.registry.values());
    
    switch (type) {
      case 'category':
        const categoryCounts = new Map<PluginCategory, number>();
        plugins.forEach(plugin => {
          const category = plugin.manifest.category;
          categoryCounts.set(category, (categoryCounts.get(category) || 0) + 1);
        });
        return Array.from(categoryCounts.entries()).map(([category, count]) => ({ 
          category, 
          count 
        }));
        
      case 'author':
        const authorCounts = new Map<string, number>();
        plugins.forEach(plugin => {
          const author = plugin.manifest.author;
          authorCounts.set(author, (authorCounts.get(author) || 0) + 1);
        });
        return Array.from(authorCounts.entries()).map(([author, count]) => ({ 
          author, 
          count 
        }));
        
      case 'rating':
        const ratingCounts = new Map<number, number>();
        plugins.forEach(plugin => {
          const rating = Math.floor(plugin.rating);
          ratingCounts.set(rating, (ratingCounts.get(rating) || 0) + 1);
        });
        return Array.from(ratingCounts.entries()).map(([rating, count]) => ({ 
          rating, 
          count 
        }));
        
      case 'tags':
        const tagCounts = new Map<string, number>();
        plugins.forEach(plugin => {
          const tags = [
            ...plugin.manifest.metadata.keywords || [],
            ...plugin.marketplace?.tags || []
          ];
          tags.forEach(tag => {
            tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
          });
        });
        return Array.from(tagCounts.entries())
          .sort((a, b) => b[1] - a[1])
          .slice(0, 20)
          .map(([tag, count]) => ({ tag, count }));
          
      default:
        return [];
    }
  }

  public getPlugin(pluginId: string): PluginRegistryEntry | undefined {
    return this.registry.get(pluginId);
  }

  public getAllPlugins(): PluginRegistryEntry[] {
    return Array.from(this.registry.values());
  }

  public getFeaturedPlugins(): PluginRegistryEntry[] {
    return Array.from(this.registry.values())
      .filter(plugin => plugin.marketplace?.featured)
      .sort((a, b) => b.rating - a.rating);
  }

  public getPluginsByCategory(category: PluginCategory): PluginRegistryEntry[] {
    return Array.from(this.registry.values())
      .filter(plugin => plugin.manifest.category === category);
  }

  public getPopularPlugins(limit: number = 10): PluginRegistryEntry[] {
    return Array.from(this.registry.values())
      .sort((a, b) => b.downloadCount - a.downloadCount)
      .slice(0, limit);
  }

  public getTopRatedPlugins(limit: number = 10): PluginRegistryEntry[] {
    return Array.from(this.registry.values())
      .sort((a, b) => b.rating - a.rating)
      .slice(0, limit);
  }

  public async downloadPlugin(pluginId: string, options: PluginDownloadOptions = {}): Promise<{
    success: boolean;
    downloadUrl?: string;
    error?: string;
    version?: string;
  }> {
    const plugin = this.registry.get(pluginId);
    if (!plugin) {
      return {
        success: false,
        error: 'Plugin not found in registry'
      };
    }

    // Simulate download process
    try {
      // In real implementation, this would download from actual registry
      const downloadUrl = `https://plugins.minimax.ai/download/${pluginId}/${options.version || plugin.manifest.version}`;
      const version = options.version || plugin.manifest.version;
      
      // Update download statistics
      plugin.downloadCount++;
      plugin.installCount++; // Assuming download leads to install
      
      this.updatePlugin(plugin);
      
      return {
        success: true,
        downloadUrl,
        version
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Download failed'
      };
    }
  }

  public addReview(pluginId: string, review: Omit<PluginReview, 'id' | 'date'>): void {
    const plugin = this.registry.get(pluginId);
    if (!plugin) {
      throw new Error('Plugin not found');
    }

    const newReview: PluginReview = {
      id: `review_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      date: new Date(),
      ...review
    };

    if (!plugin.reviews) {
      plugin.reviews = [];
    }

    plugin.reviews.push(newReview);
    
    // Recalculate rating
    this.recalculateRating(plugin);
    
    this.updatePlugin(plugin);
  }

  private recalculateRating(plugin: PluginRegistryEntry): void {
    if (!plugin.reviews || plugin.reviews.length === 0) {
      return;
    }

    const totalRating = plugin.reviews.reduce((sum, review) => sum + review.rating, 0);
    plugin.rating = totalRating / plugin.reviews.length;
  }

  public registerLocalPlugin(plugin: PluginRegistryEntry): void {
    this.localRegistry.set(plugin.id, plugin);
    this.registry.set(plugin.id, plugin);
    this.updateRegistry();
  }

  public getLocalPlugins(): PluginRegistryEntry[] {
    return Array.from(this.localRegistry.values());
  }

  public getRegistryStatistics(): {
    totalPlugins: number;
    verifiedPlugins: number;
    featuredPlugins: number;
    averageRating: number;
    totalDownloads: number;
    categoriesDistribution: Record<PluginCategory, number>;
  } {
    const plugins = Array.from(this.registry.values());
    
    const stats = {
      totalPlugins: plugins.length,
      verifiedPlugins: plugins.filter(p => p.verified).length,
      featuredPlugins: plugins.filter(p => p.marketplace?.featured).length,
      averageRating: plugins.length > 0 
        ? plugins.reduce((sum, p) => sum + p.rating, 0) / plugins.length 
        : 0,
      totalDownloads: plugins.reduce((sum, p) => sum + p.downloadCount, 0),
      categoriesDistribution: {} as Record<PluginCategory, number>
    };

    // Categories distribution
    plugins.forEach(plugin => {
      const category = plugin.manifest.category;
      stats.categoriesDistribution[category] = (stats.categoriesDistribution[category] || 0) + 1;
    });

    return stats;
  }

  private updatePlugin(plugin: PluginRegistryEntry): void {
    this.registry.set(plugin.id, plugin);
    this.updateRegistry();
  }

  private updateRegistry(): void {
    this.registryUpdateSubject.next([...this.registry.values()]);
  }

  public cleanup(): void {
    this.searchResultSubject.complete();
    this.registryUpdateSubject.complete();
  }
}