/**
 * Context Manager Service
 * Управление контекстом разговора и состоянием AI помощника
 */

// Генерация UUID с помощью Web Crypto API
const generateUUID = (): string => {
  return crypto.randomUUID();
};

export interface ConversationContext {
  id: string;
  userId: string;
  agentType: 'architect' | 'developer' | 'project_manager' | 'business_analyst' | 'data_analyst';
  messages: Message[];
  sessionData: SessionData;
  createdAt: Date;
  updatedAt: Date;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  metadata?: {
    agentType?: string;
    contextData?: Record<string, any>;
    suggestions?: string[];
  };
}

export interface SessionData {
  currentProject?: string;
  workingDirectory?: string;
  selectedFiles?: string[];
  recentActions?: string[];
  userPreferences?: Record<string, any>;
  knowledgeBase?: string[];
  taskHistory?: TaskContext[];
}

export interface TaskContext {
  id: string;
  name: string;
  status: 'active' | 'completed' | 'paused' | 'cancelled';
  progress: number;
  relatedFiles: string[];
  dependencies: string[];
  createdAt: Date;
  completedAt?: Date;
}

export interface ContextFilter {
  agentType?: string;
  timeRange?: {
    start: Date;
    end: Date;
  };
  keywords?: string[];
  project?: string;
}

export class ContextManagerService {
  private conversations = new Map<string, ConversationContext>();
  private globalContext = new Map<string, any>();
  private sessionCache = new Map<string, ConversationContext>();

  constructor() {
    // Инициализация с базовым контекстом
    this.initializeGlobalContext();
  }

  /**
   * Создание нового контекста разговора
   */
  createConversation(userId: string, agentType: string): string {
    const conversationId = generateUUID();
    
    const context: ConversationContext = {
      id: conversationId,
      userId,
      agentType: agentType as any,
      messages: [],
      sessionData: {},
      createdAt: new Date(),
      updatedAt: new Date()
    };

    this.conversations.set(conversationId, context);
    this.sessionCache.set(`${userId}:${agentType}`, context);

    // Добавляем системное сообщение
    this.addSystemMessage(conversationId, 
      `Контекст для агента ${agentType} успешно инициализирован. Готов к работе.`
    );

    return conversationId;
  }

  /**
   * Добавление сообщения в контекст
   */
  addMessage(conversationId: string, message: Omit<Message, 'id' | 'timestamp'>): void {
    const context = this.conversations.get(conversationId);
    if (!context) {
      throw new Error(`Контекст ${conversationId} не найден`);
    }

    const fullMessage: Message = {
      ...message,
      id: generateUUID(),
      timestamp: new Date()
    };

    context.messages.push(fullMessage);
    context.updatedAt = new Date();

    // Обновляем кеш сессии
    this.sessionCache.set(`${context.userId}:${context.agentType}`, context);

    // Автоматически обновляем контекст на основе сообщения
    this.updateContextFromMessage(context, fullMessage);
  }

  /**
   * Добавление системного сообщения
   */
  addSystemMessage(conversationId: string, content: string, metadata?: any): void {
    this.addMessage(conversationId, {
      role: 'system',
      content,
      metadata
    });
  }

  /**
   * Получение контекста разговора
   */
  getConversation(conversationId: string): ConversationContext | null {
    return this.conversations.get(conversationId) || null;
  }

  /**
   * Получение активного контекста для пользователя и агента
   */
  getActiveContext(userId: string, agentType: string): ConversationContext | null {
    return this.sessionCache.get(`${userId}:${agentType}`) || null;
  }

  /**
   * Поиск контекстов по фильтру
   */
  findContexts(filter: ContextFilter): ConversationContext[] {
    const contexts = Array.from(this.conversations.values());

    return contexts.filter(context => {
      if (filter.agentType && context.agentType !== filter.agentType) {
        return false;
      }

      if (filter.timeRange) {
        const createdAt = context.createdAt.getTime();
        if (createdAt < filter.timeRange.start.getTime() || 
            createdAt > filter.timeRange.end.getTime()) {
          return false;
        }
      }

      if (filter.keywords && filter.keywords.length > 0) {
        const content = (context.messages || [])
          .map(m => m.content.toLowerCase())
          .join(' ');
        
        const hasKeywords = filter.keywords.some(keyword => 
          content.includes(keyword.toLowerCase())
        );
        
        if (!hasKeywords) {
          return false;
        }
      }

      if (filter.project && context.sessionData.currentProject !== filter.project) {
        return false;
      }

      return true;
    });
  }

  /**
   * Обновление данных сессии
   */
  updateSessionData(conversationId: string, updates: Partial<SessionData>): void {
    const context = this.conversations.get(conversationId);
    if (!context) {
      throw new Error(`Контекст ${conversationId} не найден`);
    }

    context.sessionData = { ...context.sessionData, ...updates };
    context.updatedAt = new Date();
  }

  /**
   * Добавление задачи в контекст
   */
  addTaskToContext(conversationId: string, task: Omit<TaskContext, 'id' | 'createdAt'>): void {
    const context = this.conversations.get(conversationId);
    if (!context) {
      throw new Error(`Контекст ${conversationId} не найден`);
    }

    const fullTask: TaskContext = {
      ...task,
      id: generateUUID(),
      createdAt: new Date()
    };

    context.sessionData.taskHistory = context.sessionData.taskHistory || [];
    context.sessionData.taskHistory.push(fullTask);
    context.updatedAt = new Date();
  }

  /**
   * Обновление статуса задачи
   */
  updateTaskStatus(conversationId: string, taskId: string, status: TaskContext['status'], progress?: number): void {
    const context = this.conversations.get(conversationId);
    if (!context || !context.sessionData.taskHistory) {
      return;
    }

    const task = context.sessionData.taskHistory.find(t => t.id === taskId);
    if (task) {
      task.status = status;
      if (progress !== undefined) {
        task.progress = progress;
      }
      if (status === 'completed') {
        task.completedAt = new Date();
      }
      context.updatedAt = new Date();
    }
  }

  /**
   * Генерация контекстного резюме
   */
  generateContextSummary(conversationId: string): string {
    const context = this.conversations.get(conversationId);
    if (!context) {
      throw new Error(`Контекст ${conversationId} не найден`);
    }

    const messageCount = context.messages.length;
    const userMessages = context.messages.filter(m => m.role === 'user').length;
    const tasksCompleted = (context.sessionData.taskHistory || []).filter(t => t.status === 'completed').length;
    const tasksActive = (context.sessionData.taskHistory || []).filter(t => t.status === 'active').length;

    const summary = `
Контекст сессии:
- Агент: ${context.agentType}
- Сообщений: ${messageCount} (пользователь: ${userMessages})
- Завершенных задач: ${tasksCompleted}
- Активных задач: ${tasksActive}
- Проект: ${context.sessionData.currentProject || 'не указан'}
- Рабочая директория: ${context.sessionData.workingDirectory || 'не указана'}
- Последнее обновление: ${context.updatedAt.toLocaleString('ru-RU')}
    `.trim();

    return summary;
  }

  /**
   * Извлечение ключевых данных из контекста
   */
  extractKeyContext(conversationId: string, limit: number = 10): Message[] {
    const context = this.conversations.get(conversationId);
    if (!context) {
      throw new Error(`Контекст ${conversationId} не найден`);
    }

    // Возвращаем последние сообщения + наиболее релевантные
    const recentMessages = context.messages.slice(-limit);
    
    // Добавляем важные системные сообщения
    const importantMessages = context.messages.filter(m => 
      m.role === 'system' && 
      (m.content.includes('задача') || m.content.includes('ошибка') || m.content.includes('создан'))
    );

    return [...importantMessages, ...recentMessages].slice(0, limit);
  }

  /**
   * Создание контекстного промпта для AI
   */
  buildAIPrompt(conversationId: string, userMessage: string): string {
    const context = this.conversations.get(conversationId);
    if (!context) {
      throw new Error(`Контекст ${conversationId} не найден`);
    }

    const keyContext = this.extractKeyContext(conversationId, 5);
    const sessionSummary = this.generateContextSummary(conversationId);

    const contextMessages = keyContext
      .map(m => `${m.role}: ${m.content}`)
      .join('\n');

    return `
Контекст системы 1C AI Assistant:

Агент: ${context.agentType}
${sessionSummary}

Последние сообщения:
${contextMessages}

Текущий запрос пользователя: ${userMessage}

Инструкции:
1. Анализируй контекст и историю работы
2. Учитывай специфику 1C разработки
3. Предоставляй конкретные и практичные решения
4. При необходимости запрашивай дополнительную информацию
5. Отвечай на русском языке
    `.trim();
  }

  /**
   * Очистка старых контекстов
   */
  cleanupOldContexts(daysToKeep: number = 30): void {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - daysToKeep);

    for (const [id, context] of this.conversations.entries()) {
      if (context.updatedAt < cutoffDate) {
        this.conversations.delete(id);
        
        // Очищаем из кеша
        const cacheKey = `${context.userId}:${context.agentType}`;
        this.sessionCache.delete(cacheKey);
      }
    }
  }

  /**
   * Получение статистики использования
   */
  getUsageStats(): {
    totalConversations: number;
    activeContexts: number;
    messagesProcessed: number;
    avgConversationLength: number;
  } {
    const contexts = Array.from(this.conversations.values());
    const totalMessages = contexts.reduce((sum, ctx) => sum + ctx.messages.length, 0);
    const avgLength = contexts.length > 0 ? totalMessages / contexts.length : 0;

    return {
      totalConversations: contexts.length,
      activeContexts: this.sessionCache.size,
      messagesProcessed: totalMessages,
      avgConversationLength: Math.round(avgLength * 100) / 100
    };
  }

  /**
   * Инициализация глобального контекста
   */
  private initializeGlobalContext(): void {
    this.globalContext.set('system_version', '1.0.0');
    this.globalContext.set('supported_agents', [
      'architect', 'developer', 'project_manager', 'business_analyst', 'data_analyst'
    ]);
    this.globalContext.set('1c_version', '8.3');
    this.globalContext.set('features', [
      'code_analysis', 'form_builder', 'testing', 'git_integration',
      'project_management', 'gantt_charts', 'risk_analysis', 'reporting',
      'bpmn_modeling', 'nlp_analysis', 'traceability_matrix', 'roi_calculation',
      'dashboards', 'ml_analysis', 'etl_processes', 'anomaly_detection'
    ]);
  }

  /**
   * Обновление контекста на основе сообщения
   */
  private updateContextFromMessage(context: ConversationContext, message: Message): void {
    if (message.role === 'user') {
      // Анализируем содержимое сообщения для извлечения ключевых данных
      const content = message.content.toLowerCase();
      
      // Извлекаем упоминания файлов
      const fileMatches = content.match(/[а-яё]+\.bsl|[а-яё]+\.xml|[а-яё]+\.json/gi);
      if (fileMatches) {
        context.sessionData.selectedFiles = [
          ...(context.sessionData.selectedFiles || []),
          ...fileMatches
        ];
      }

      // Извлекаем упоминания проектов
      if (content.includes('проект') || content.includes('project')) {
        const projectMatch = content.match(/проект[:\s]+([а-яё\s]+)/i);
        if (projectMatch) {
          context.sessionData.currentProject = projectMatch[1].trim();
        }
      }

      // Добавляем в историю действий
      context.sessionData.recentActions = [
        ...(context.sessionData.recentActions || []),
        `${message.timestamp.toISOString()}: ${message.content.substring(0, 100)}`
      ].slice(-10); // Оставляем последние 10 действий
    }
  }

  /**
   * Экспорт контекста в JSON
   */
  exportContext(conversationId: string): string {
    const context = this.conversations.get(conversationId);
    if (!context) {
      throw new Error(`Контекст ${conversationId} не найден`);
    }

    return JSON.stringify(context, null, 2);
  }

  /**
   * Импорт контекста из JSON
   */
  importContext(jsonData: string): string {
    try {
      const contextData = JSON.parse(jsonData);
      
      // Валидация структуры
      if (!contextData.id || !contextData.userId || !contextData.agentType) {
        throw new Error('Неверная структура контекста');
      }

      // Проверяем на конфликт ID
      if (this.conversations.has(contextData.id)) {
        contextData.id = generateUUID(); // Генерируем новый ID
      }

      // Восстанавливаем даты
      contextData.createdAt = new Date(contextData.createdAt);
      contextData.updatedAt = new Date(contextData.updatedAt);
      contextData.messages = contextData.messages.map((msg: any) => ({
        ...msg,
        timestamp: new Date(msg.timestamp)
      }));

      this.conversations.set(contextData.id, contextData);
      return contextData.id;
    } catch (error) {
      throw new Error(`Ошибка импорта контекста: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`);
    }
  }
}

export const contextManager = new ContextManagerService();