/**
 * Suggestion Engine Service
 * Интеллектуальная система подсказок и предложений для AI помощника
 */

import { contextManager, ConversationContext } from './context-manager-service';

export interface Suggestion {
  id: string;
  type: 'code' | 'task' | 'optimization' | 'documentation' | 'testing' | 'refactor' | 'integration';
  priority: 'high' | 'medium' | 'low';
  title: string;
  description: string;
  code?: string;
  impact: string;
  confidence: number; // 0-1
  relatedFiles: string[];
  metadata?: {
    agentType?: string;
    taskContext?: string;
    performanceGain?: string;
    complexity?: 'low' | 'medium' | 'high';
    estimatedTime?: string;
  };
  createdAt: Date;
}

export interface SuggestionRule {
  id: string;
  name: string;
  condition: string;
  suggestion: Partial<Suggestion>;
  weight: number;
  enabled: boolean;
}

export interface AnalysisContext {
  code: string;
  fileType: string;
  projectType: '1c' | 'web' | 'mobile' | 'other';
  currentTasks: string[];
  recentChanges: string[];
  agentType: string;
  userLevel: 'beginner' | 'intermediate' | 'expert';
}

export class SuggestionEngineService {
  private suggestions = new Map<string, Suggestion[]>();
  private rules = new Map<string, SuggestionRule>();
  private contextCache = new Map<string, AnalysisContext>();

  constructor() {
    this.initializeDefaultRules();
  }

  /**
   * Генерация подсказок на основе контекста
   */
  generateSuggestions(conversationId: string, analysisContext?: Partial<AnalysisContext>): Suggestion[] {
    const context = contextManager.getConversation(conversationId);
    if (!context) {
      throw new Error(`Контекст ${conversationId} не найден`);
    }

    const fullContext: AnalysisContext = {
      code: '',
      fileType: '',
      projectType: '1c',
      currentTasks: [],
      recentChanges: [],
      agentType: context.agentType,
      userLevel: 'intermediate',
      ...analysisContext
    };

    // Сохраняем контекст в кеш
    this.contextCache.set(conversationId, fullContext);

    const suggestions: Suggestion[] = [];

    // Генерируем подсказки на основе правил
    suggestions.push(...this.applyRules(conversationId, fullContext));

    // Генерируем контекстные подсказки
    suggestions.push(...this.generateContextualSuggestions(conversationId, fullContext));

    // Генерируем подсказки на основе истории
    suggestions.push(...this.generateHistoryBasedSuggestions(conversationId, fullContext));

    // Сортируем по приоритету и уверенности
    suggestions.sort((a, b) => {
      const priorityOrder = { high: 3, medium: 2, low: 1 };
      const priorityDiff = priorityOrder[b.priority] - priorityOrder[a.priority];
      if (priorityDiff !== 0) return priorityDiff;
      return b.confidence - a.confidence;
    });

    // Ограничиваем количество подсказок
    const maxSuggestions = 10;
    const finalSuggestions = suggestions.slice(0, maxSuggestions);

    // Сохраняем подсказки
    this.suggestions.set(conversationId, finalSuggestions);

    return finalSuggestions;
  }

  /**
   * Применение правил для генерации подсказок
   */
  private applyRules(conversationId: string, context: AnalysisContext): Suggestion[] {
    const suggestions: Suggestion[] = [];

    for (const rule of this.rules.values()) {
      if (!rule.enabled) continue;

      try {
        const matches = this.evaluateCondition(rule.condition, context);
        if (matches) {
          const suggestion: Suggestion = {
            id: `rule_${rule.id}_${Date.now()}`,
            ...rule.suggestion,
            createdAt: new Date(),
            confidence: Math.min(0.95, rule.weight + 0.1) // Увеличиваем уверенность на основе веса правила
          } as Suggestion;

          suggestions.push(suggestion);
        }
      } catch (error) {
        console.warn(`Ошибка применения правила ${rule.id}:`, error);
      }
    }

    return suggestions;
  }

  /**
   * Оценка условия правила
   */
  private evaluateCondition(condition: string, context: AnalysisContext): boolean {
    // Простой парсер условий (можно расширить)
    const conditions = condition.split(' AND ');
    
    for (const cond of conditions) {
      const [key, operator, value] = this.parseCondition(cond);
      
      const contextValue = this.getContextValue(key, context);
      
      switch (operator) {
        case '==':
          if (contextValue !== value) return false;
          break;
        case '!=':
          if (contextValue === value) return false;
          break;
        case 'contains':
          if (!contextValue || !contextValue.includes(value)) return false;
          break;
        case 'in':
          if (!contextValue || !contextValue.split(',').includes(value)) return false;
          break;
        default:
          return false;
      }
    }
    
    return true;
  }

  /**
   * Парсинг отдельного условия
   */
  private parseCondition(cond: string): [string, string, string] {
    const operators = ['==', '!=', 'contains', 'in'];
    
    for (const op of operators) {
      const parts = cond.split(op);
      if (parts.length === 2) {
        return [parts[0].trim(), op, parts[1].trim().replace(/['"]/g, '')];
      }
    }
    
    throw new Error(`Неверное условие: ${cond}`);
  }

  /**
   * Получение значения из контекста
   */
  private getContextValue(key: string, context: AnalysisContext): string {
    const keys = key.split('.');
    let value: any = context;
    
    for (const k of keys) {
      value = value?.[k];
      if (value === undefined) return '';
    }
    
    return String(value || '');
  }

  /**
   * Генерация контекстных подсказок
   */
  private generateContextualSuggestions(conversationId: string, context: AnalysisContext): Suggestion[] {
    const suggestions: Suggestion[] = [];
    const conversation = contextManager.getConversation(conversationId);

    if (!conversation) return suggestions;

    // Подсказки на основе агента
    suggestions.push(...this.generateAgentSpecificSuggestions(context));

    // Подсказки на основе задач
    const taskHistory = conversation.sessionData.taskHistory;
    if (taskHistory && taskHistory.length > 0) {
      suggestions.push(...this.generateTaskBasedSuggestions(context, taskHistory));
    }

    // Подсказки на основе проекта
    if (conversation.sessionData.currentProject) {
      suggestions.push(...this.generateProjectBasedSuggestions(context, conversation.sessionData.currentProject));
    }

    return suggestions;
  }

  /**
   * Подсказки специфичные для агента
   */
  private generateAgentSpecificSuggestions(context: AnalysisContext): Suggestion[] {
    const suggestions: Suggestion[] = [];

    switch (context.agentType) {
      case 'architect':
        suggestions.push({
          id: `architect_pattern_${Date.now()}`,
          type: 'code',
          priority: 'medium',
          title: 'Применить паттерн Repository',
          description: 'Используйте паттерн Repository для отделения логики доступа к данным',
          code: `// Пример реализации паттерна Repository
class DocumentRepository {
    private connection: Connection;
    
    constructor(connection: Connection) {
        this.connection = connection;
    }
    
    async getDocument(id: string): Promise<Document> {
        // Логика получения документа
    }
    
    async saveDocument(document: Document): Promise<void> {
        // Логика сохранения документа
    }
}`,
          impact: 'Улучшение архитектуры и тестируемости',
          confidence: 0.8,
          relatedFiles: [],
          metadata: {
            complexity: 'medium',
            estimatedTime: '2-3 часа'
          },
          createdAt: new Date()
        });
        break;

      case 'developer':
        suggestions.push({
          id: `dev_testing_${Date.now()}`,
          type: 'testing',
          priority: 'high',
          title: 'Добавить модульные тесты',
          description: 'Рекомендуется покрыть код тестами для повышения качества',
          code: `// Пример теста
describe('DocumentService', () => {
    test('should create document', async () => {
        const service = new DocumentService();
        const document = await service.createDocument({
            name: 'Test Document',
            type: 'Invoice'
        });
        expect(document.id).toBeDefined();
        expect(document.name).toBe('Test Document');
    });
});`,
          impact: 'Повышение качества кода и упрощение отладки',
          confidence: 0.9,
          relatedFiles: [],
          metadata: {
            complexity: 'low',
            estimatedTime: '1-2 часа'
          },
          createdAt: new Date()
        });
        break;

      case 'project_manager':
        suggestions.push({
          id: `pm_risk_${Date.now()}`,
          type: 'task',
          priority: 'high',
          title: 'Анализ рисков проекта',
          description: 'Рекомендуется провести анализ рисков для текущей задачи',
          impact: 'Предотвращение проблем и лучшее планирование',
          confidence: 0.85,
          relatedFiles: [],
          metadata: {
            complexity: 'medium',
            estimatedTime: '30 минут'
          },
          createdAt: new Date()
        });
        break;
    }

    return suggestions;
  }

  /**
   * Подсказки на основе задач
   */
  private generateTaskBasedSuggestions(context: AnalysisContext, tasks: any[]): Suggestion[] {
    const suggestions: Suggestion[] = [];

    const activeTasks = tasks.filter(t => t.status === 'active');
    const overdueTasks = tasks.filter(t => 
      t.status === 'active' && new Date() > new Date(t.deadline || Date.now() + 86400000)
    );

    if (overdueTasks.length > 0) {
      suggestions.push({
        id: `task_overdue_${Date.now()}`,
        type: 'task',
        priority: 'high',
        title: 'Просроченные задачи',
        description: `Обнаружено ${overdueTasks.length} просроченных задач. Требуется пересмотр приоритетов.`,
        impact: 'Предотвращение задержек проекта',
        confidence: 0.95,
        relatedFiles: overdueTasks.map(t => t.relatedFiles).flat(),
        metadata: {
          complexity: 'low',
          estimatedTime: '15 минут'
        },
        createdAt: new Date()
      });
    }

    return suggestions;
  }

  /**
   * Подсказки на основе проекта
   */
  private generateProjectBasedSuggestions(context: AnalysisContext, projectName: string): Suggestion[] {
    const suggestions: Suggestion[] = [];

    // Добавляем специфичные для 1C подсказки
    suggestions.push({
      id: `1c_optimization_${Date.now()}`,
      type: 'optimization',
      priority: 'medium',
      title: 'Оптимизация запросов 1C',
      description: 'Рекомендуется оптимизировать запросы к базе данных для улучшения производительности',
      code: `// Неоптимальный запрос
Запрос = Новый Запрос;
Запрос.Текст = "ВЫБРАТЬ * ИЗ Документ.Продажа ГДЕ Дата >= &НачалоПериода";
Запрос.УстановитьПараметр("НачалоПериода", НачалоПериода);
Результат = Запрос.Выполнить();

// Оптимизированный запрос с индексами
Запрос = Новый Запрос;
Запрос.Текст = "ВЫБРАТЬ
|    Продажа.Ссылка,
|    Продажа.Дата,
|    Продажа.Контрагент
|ИЗ
|    Документ.Продажа КАК Продажа
|ГДЕ
|    Продажа.Дата МЕЖДУ &НачалоПериода И &КонецПериода
|    И Продажа.Проведен = ИСТИНА
|УПОРЯДОЧИТЬ ПО Продажа.Дата УБЫВ";`,
      impact: 'Улучшение производительности системы',
      confidence: 0.8,
      relatedFiles: [],
      metadata: {
        complexity: 'medium',
        estimatedTime: '1 час'
      },
      createdAt: new Date()
    });

    return suggestions;
  }

  /**
   * Подсказки на основе истории
   */
  private generateHistoryBasedSuggestions(conversationId: string, context: AnalysisContext): Suggestion[] {
    const suggestions: Suggestion[] = [];
    const conversation = contextManager.getConversation(conversationId);

    if (!conversation) return suggestions;

    // Анализируем повторяющиеся паттерны
    const userMessages = (conversation.messages || []).filter(m => m.role === 'user');
    const similarMessages = this.findSimilarMessages(userMessages);

    if (similarMessages.length > 3) {
      suggestions.push({
        id: `history_pattern_${Date.now()}`,
        type: 'refactor',
        priority: 'low',
        title: 'Повторяющиеся действия',
        description: 'Обнаружены повторяющиеся действия. Рекомендуется создать автоматизацию.',
        impact: 'Сокращение времени на рутинные операции',
        confidence: 0.7,
        relatedFiles: [],
        metadata: {
          complexity: 'high',
          estimatedTime: '4-6 часов'
        },
        createdAt: new Date()
      });
    }

    return suggestions;
  }

  /**
   * Поиск похожих сообщений
   */
  private findSimilarMessages(messages: any[]): string[] {
    const patterns: { [key: string]: number } = {};

    messages.forEach(msg => {
      const words = msg.content.toLowerCase().split(/\s+/);
      const key = words.slice(0, 3).join(' '); // Первые 3 слова как ключ
      patterns[key] = (patterns[key] || 0) + 1;
    });

    return Object.entries(patterns)
      .filter(([_, count]) => count > 1)
      .map(([pattern, _]) => pattern);
  }

  /**
   * Применение подсказки
   */
  applySuggestion(conversationId: string, suggestionId: string): boolean {
    const suggestions = this.suggestions.get(conversationId) || [];
    const suggestion = suggestions.find(s => s.id === suggestionId);

    if (!suggestion) {
      return false;
    }

    // Логируем применение подсказки
    contextManager.addSystemMessage(conversationId, 
      `Применена подсказка: ${suggestion.title}`
    );

    // Обновляем статистику применения
    this.updateSuggestionStats(suggestionId);

    return true;
  }

  /**
   * Отклонение подсказки
   */
  rejectSuggestion(conversationId: string, suggestionId: string, reason?: string): boolean {
    const suggestions = this.suggestions.get(conversationId) || [];
    const suggestion = suggestions.find(s => s.id === suggestionId);

    if (!suggestion) {
      return false;
    }

    // Логируем отклонение
    contextManager.addSystemMessage(conversationId, 
      `Подсказка отклонена: ${suggestion.title}${reason ? ` (причина: ${reason})` : ''}`
    );

    return true;
  }

  /**
   * Обновление статистики подсказки
   */
  private updateSuggestionStats(suggestionId: string): void {
    // Здесь можно добавить логику сбора статистики
    // Например, частота применения разных типов подсказок
  }

  /**
   * Инициализация стандартных правил
   */
  private initializeDefaultRules(): void {
    // Правило для 1C разработки
    this.addRule({
      id: '1c_best_practices',
      name: '1C лучшие практики',
      condition: 'projectType == "1c" AND agentType == "developer"',
      suggestion: {
        type: 'code',
        priority: 'medium',
        title: 'Следование 1C стандартам',
        description: 'Используйте рекомендуемые практики разработки 1C',
        impact: 'Повышение качества и поддерживаемости кода',
        confidence: 0.9
      },
      weight: 0.8,
      enabled: true
    });

    // Правило для больших проектов
    this.addRule({
      id: 'large_project',
      name: 'Большой проект',
      condition: 'currentTasks.length > 10',
      suggestion: {
        type: 'task',
        priority: 'medium',
        title: 'Рефакторинг задач',
        description: 'Рекомендуется разбить большие задачи на меньшие',
        impact: 'Улучшение управляемости проекта',
        confidence: 0.7
      },
      weight: 0.6,
      enabled: true
    });

    // Правило для начинающих
    this.addRule({
      id: 'beginner_help',
      name: 'Помощь начинающим',
      condition: 'userLevel == "beginner"',
      suggestion: {
        type: 'documentation',
        priority: 'low',
        title: 'Добавить комментарии',
        description: 'Рекомендуется добавить подробные комментарии к коду',
        impact: 'Улучшение понимания кода',
        confidence: 0.8
      },
      weight: 0.5,
      enabled: true
    });
  }

  /**
   * Добавление правила
   */
  addRule(rule: SuggestionRule): void {
    this.rules.set(rule.id, rule);
  }

  /**
   * Удаление правила
   */
  removeRule(ruleId: string): boolean {
    return this.rules.delete(ruleId);
  }

  /**
   * Включение/выключение правила
   */
  toggleRule(ruleId: string, enabled: boolean): boolean {
    const rule = this.rules.get(ruleId);
    if (rule) {
      rule.enabled = enabled;
      return true;
    }
    return false;
  }

  /**
   * Получение всех правил
   */
  getAllRules(): SuggestionRule[] {
    return Array.from(this.rules.values());
  }

  /**
   * Получение подсказок для контекста
   */
  getSuggestions(conversationId: string): Suggestion[] {
    return this.suggestions.get(conversationId) || [];
  }

  /**
   * Очистка кеша подсказок
   */
  clearSuggestions(conversationId: string): void {
    this.suggestions.delete(conversationId);
    this.contextCache.delete(conversationId);
  }

  /**
   * Получение статистики движка подсказок
   */
  getEngineStats(): {
    totalSuggestions: number;
    activeRules: number;
    contextsProcessed: number;
    avgSuggestionsPerContext: number;
  } {
    const totalSuggestions = Array.from(this.suggestions.values())
      .reduce((sum, suggestions) => sum + suggestions.length, 0);
    
    const activeRules = Array.from(this.rules.values())
      .filter(rule => rule.enabled).length;

    const contextsProcessed = this.suggestions.size;
    const avgSuggestions = contextsProcessed > 0 ? totalSuggestions / contextsProcessed : 0;

    return {
      totalSuggestions,
      activeRules,
      contextsProcessed,
      avgSuggestionsPerContext: Math.round(avgSuggestions * 100) / 100
    };
  }
}

export const suggestionEngine = new SuggestionEngineService();