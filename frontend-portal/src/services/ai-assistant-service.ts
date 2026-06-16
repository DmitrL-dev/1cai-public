/**
 * AI Assistant Service
 * Основной сервис AI помощника, объединяющий Context Manager, Suggestion Engine и OpenAI
 */

import { apiClient } from "../lib/api-client";
import { contextManager, ConversationContext } from "./context-manager-service";
import {
  AIResponse,
  getOpenAIService,
  OpenAIIntegrationService,
} from "./openai-integration-service";
import { AnalysisContext, suggestionEngine } from "./suggestion-engine-service";

export interface AIAssistantConfig {
  openai?: {
    apiKey: string;
    baseURL?: string;
    model?: string;
    maxTokens?: number;
    temperature?: number;
  };
  suggestions?: {
    enabled: boolean;
    maxSuggestions?: number;
    autoSuggest?: boolean;
  };
  context?: {
    maxHistoryLength?: number;
    autoCleanup?: boolean;
    retentionDays?: number;
  };
  features?: {
    streaming?: boolean;
    embeddings?: boolean;
    moderation?: boolean;
  };
}

export interface ChatSession {
  id: string;
  userId: string;
  conversationId: string;
  status: "active" | "paused" | "closed";
  preferences: {
    language: "ru" | "en";
    verbosity: "brief" | "normal" | "detailed";
    includeCode: boolean;
    includeSuggestions: boolean;
  };
  createdAt: Date;
  lastActivity: Date;
}

export interface AICommand {
  id: string;
  name: string;
  description: string;
  syntax: string;
  handler: (params: any, context: ConversationContext) => Promise<any>;
  category: "system" | "analysis" | "generation" | "navigation";
}

export interface TaskSuggestion {
  id: string;
  taskType: string;
  estimatedTime: string;
  complexity: "low" | "medium" | "high";
  description: string;
  prerequisites: string[];
  steps: string[];
}

export class AIAssistantService {
  private config: AIAssistantConfig;
  private openaiService: OpenAIIntegrationService | null = null;
  private chatSessions = new Map<string, ChatSession>();
  private commands = new Map<string, AICommand>();
  private taskSuggestions = new Map<string, TaskSuggestion[]>();

  constructor(config: AIAssistantConfig) {
    this.config = config;
    this.initializeOpenAI();
    this.registerDefaultCommands();
    this.initializeTaskSuggestions();
  }

  /**
   * Инициализация OpenAI сервиса
   */
  private initializeOpenAI(): void {
    if (this.config.openai?.apiKey) {
      try {
        this.openaiService = getOpenAIService({
          apiKey: this.config.openai.apiKey,
          baseURL: this.config.openai.baseURL || "https://api.openai.com/v1",
          model: this.config.openai.model || "gpt-3.5-turbo",
          maxTokens: this.config.openai.maxTokens || 2000,
          temperature: this.config.openai.temperature || 0.7,
          timeout: 30000,
        });
        console.log("OpenAI сервис успешно инициализирован");
      } catch (error) {
        console.error("Ошибка инициализации OpenAI:", error);
      }
    }
  }

  /**
   * Создание нового чат сессии
   */
  async createChatSession(
    userId: string,
    agentType: string,
    preferences?: Partial<ChatSession["preferences"]>
  ): Promise<string> {
    // Создаем контекст разговора
    const conversationId = contextManager.createConversation(userId, agentType);

    // Создаем чат сессию
    const sessionId = `session_${Date.now()}_${Math.random()
      .toString(36)
      .substr(2, 9)}`;
    const session: ChatSession = {
      id: sessionId,
      userId,
      conversationId,
      status: "active",
      preferences: {
        language: "ru",
        verbosity: "normal",
        includeCode: true,
        includeSuggestions: this.config.suggestions?.autoSuggest ?? true,
        ...preferences,
      },
      createdAt: new Date(),
      lastActivity: new Date(),
    };

    this.chatSessions.set(sessionId, session);

    // Добавляем приветственное сообщение
    contextManager.addSystemMessage(
      conversationId,
      `AI помощник для агента ${agentType} готов к работе. Как я могу вам помочь?`
    );

    return sessionId;
  }

  /**
   * Отправка сообщения AI помощнику
   */
  async sendMessage(
    sessionId: string,
    message: string,
    options?: {
      includeSuggestions?: boolean;
      stream?: boolean;
    }
  ): Promise<{
    response: AIResponse;
    session: ChatSession;
  }> {
    const session = this.chatSessions.get(sessionId);
    if (!session) {
      throw new Error(`Сессия ${sessionId} не найдена`);
    }

    if (session.status !== "active") {
      throw new Error("Сессия неактивна");
    }

    // Обновляем время последней активности
    session.lastActivity = new Date();

    // Добавляем сообщение пользователя в контекст
    contextManager.addMessage(session.conversationId, {
      role: "user",
      content: message,
      metadata: {
        agentType: session.id,
      },
    });

    // Проверяем команду
    const commandResult = await this.processCommand(message, session);
    if (commandResult) {
      return {
        response: commandResult,
        session,
      };
    }

    // Генерируем AI ответ
    const response = await this.generateAIResponse(
      session.conversationId,
      message,
      {
        includeSuggestions:
          options?.includeSuggestions ?? session.preferences.includeSuggestions,
        maxSuggestions: this.config.suggestions?.maxSuggestions,
        stream: options?.stream ?? this.config.features?.streaming,
      }
    );

    return {
      response,
      session,
    };
  }

  /**
   * Обработка команд
   */
  private async processCommand(
    message: string,
    session: ChatSession
  ): Promise<AIResponse | null> {
    // Проверяем все зарегистрированные команды
    for (const command of this.commands.values()) {
      if (this.matchesCommand(message, command)) {
        try {
          const params = this.extractCommandParams(message, command);
          const result = await command.handler(
            params,
            contextManager.getConversation(session.conversationId)!
          );

          return {
            content: `Команда "${
              command.name
            }" выполнена успешно:\n\n${JSON.stringify(result, null, 2)}`,
            tokens: { prompt: 0, completion: 0, total: 0 },
            model: this.openaiService?.getConfig()?.model || "local",
            finishReason: "stop",
            confidence: 1.0,
            metadata: { responseTime: 0, contextSize: 0 },
          };
        } catch (error) {
          return {
            content: `Ошибка выполнения команды "${command.name}": ${
              error instanceof Error ? error.message : "Неизвестная ошибка"
            }`,
            tokens: { prompt: 0, completion: 0, total: 0 },
            model: "local",
            finishReason: "stop",
            confidence: 0,
            metadata: {
              responseTime: 0,
              contextSize: 0,
              error: error instanceof Error ? error.message : "Unknown error",
            },
          };
        }
      }
    }

    return null;
  }

  /**
   * Проверка соответствия сообщения команде
   */
  private matchesCommand(message: string, command: AICommand): boolean {
    const cleanMessage = message.trim().toLowerCase();
    const commandName = command.name.toLowerCase();
    const commandSyntax = command.syntax.toLowerCase();

    return (
      cleanMessage.startsWith(commandName) ||
      cleanMessage.startsWith(commandSyntax.split(" ")[0])
    );
  }

  /**
   * Извлечение параметров команды
   */
  private extractCommandParams(message: string, command: AICommand): any {
    // Простое извлечение параметров (можно расширить)
    const parts = message.split(" ");
    const params: any = {};

    for (let i = 1; i < parts.length; i++) {
      const part = parts[i];
      if (part.startsWith("--")) {
        const [key, value] = part.substring(2).split("=");
        params[key] = value || true;
      }
    }

    return params;
  }

  /**
   * Генерация AI ответа
   */
  private async generateAIResponse(
    conversationId: string,
    message: string,
    options: {
      includeSuggestions?: boolean;
      maxSuggestions?: number;
      stream?: boolean;
    }
  ): Promise<AIResponse> {
    try {
      // Используем backend API для запросов к AI
      // Это обеспечивает прохождение через Security Layer (Agents Rule of Two)
      const response = await apiClient.ai.query(message, conversationId);

      // Преобразуем ответ API в формат AIResponse
      // Предполагаем, что API возвращает структуру, совместимую или содержащую нужные поля
      const apiData = response.data;

      return {
        content:
          apiData.content ||
          apiData.response ||
          apiData.answer ||
          JSON.stringify(apiData),
        tokens: apiData.tokens || { prompt: 0, completion: 0, total: 0 },
        model: apiData.model || "backend-ai",
        finishReason: apiData.finish_reason || "stop",
        confidence: apiData.confidence || 1.0,
        suggestions: options.includeSuggestions
          ? suggestionEngine.generateSuggestions(conversationId)
          : [],
      };
    } catch (error) {
      console.error("Ошибка генерации ответа через API:", error);
      // Fallback к локальному ответу при ошибке API
      return this.generateLocalResponse(conversationId, message, options);
    }
  }

  /**
   * Локальный ответ без OpenAI
   */
  private generateLocalResponse(
    conversationId: string,
    message: string,
    options: {
      includeSuggestions?: boolean;
    }
  ): AIResponse {
    const context = contextManager.getConversation(conversationId);

    let response = `Я понимаю ваш запрос: "${message}".`;

    // Добавляем контекстную информацию
    if (context) {
      response += `\n\nТекущий агент: ${context.agentType}`;
      if (context.sessionData.currentProject) {
        response += `\nТекущий проект: ${context.sessionData.currentProject}`;
      }
      if (
        context.sessionData.taskHistory &&
        context.sessionData.taskHistory.length > 0
      ) {
        const activeTasks = context.sessionData.taskHistory.filter(
          (t) => t.status === "active"
        ).length;
        response += `\nАктивных задач: ${activeTasks}`;
      }
    }

    response += `\n\nДля получения более подробной помощи, пожалуйста, настройте OpenAI API ключ в конфигурации.`;

    return {
      content: response,
      tokens: { prompt: 0, completion: 0, total: 0 },
      model: "local",
      finishReason: "stop",
      confidence: 0.6,
      suggestions: options.includeSuggestions
        ? suggestionEngine.generateSuggestions(conversationId)
        : [],
    };
  }

  /**
   * Получение подсказок для задач
   */
  getTaskSuggestions(
    taskType: string,
    context?: Partial<AnalysisContext>
  ): TaskSuggestion[] {
    return this.taskSuggestions.get(taskType) || [];
  }

  /**
   * Получение сессии чата
   */
  getChatSession(sessionId: string): ChatSession | null {
    return this.chatSessions.get(sessionId) || null;
  }

  /**
   * Получение всех сессий пользователя
   */
  getUserSessions(userId: string): ChatSession[] {
    return Array.from(this.chatSessions.values()).filter(
      (session) => session.userId === userId
    );
  }

  /**
   * Закрытие сессии
   */
  closeSession(sessionId: string): boolean {
    const session = this.chatSessions.get(sessionId);
    if (session) {
      session.status = "closed";

      // Сохраняем сессию для истории
      contextManager.addSystemMessage(
        session.conversationId,
        `Сессия завершена пользователем ${
          session.userId
        } в ${new Date().toLocaleString("ru-RU")}`
      );

      return true;
    }
    return false;
  }

  /**
   * Обновление настроек сессии
   */
  updateSessionPreferences(
    sessionId: string,
    preferences: Partial<ChatSession["preferences"]>
  ): boolean {
    const session = this.chatSessions.get(sessionId);
    if (session) {
      session.preferences = { ...session.preferences, ...preferences };
      return true;
    }
    return false;
  }

  /**
   * Регистрация команды
   */
  registerCommand(command: AICommand): void {
    this.commands.set(command.id, command);
  }

  /**
   * Удаление команды
   */
  unregisterCommand(commandId: string): boolean {
    return this.commands.delete(commandId);
  }

  /**
   * Получение всех команд
   */
  getAllCommands(): AICommand[] {
    return Array.from(this.commands.values());
  }

  /**
   * Получение команд по категории
   */
  getCommandsByCategory(category: AICommand["category"]): AICommand[] {
    return Array.from(this.commands.values()).filter(
      (command) => command.category === category
    );
  }

  /**
   * Проверка здоровья сервиса
   */
  async healthCheck(): Promise<{
    service: "healthy" | "degraded" | "unhealthy";
    openai: "available" | "unavailable" | "error";
    contextManager: "healthy" | "unhealthy";
    suggestionEngine: "healthy" | "unhealthy";
    uptime: number;
  }> {
    const checks: {
      openai: "available" | "unavailable" | "error";
      contextManager: "healthy" | "unhealthy";
      suggestionEngine: "healthy" | "unhealthy";
    } = {
      openai: "unavailable",
      contextManager: "healthy",
      suggestionEngine: "healthy",
    };

    // Проверяем OpenAI
    if (this.openaiService) {
      try {
        const health = await this.openaiService.healthCheck();
        checks.openai =
          health.status === "healthy"
            ? ("available" as const)
            : ("error" as const);
      } catch {
        checks.openai = "error";
      }
    }

    // Определяем общий статус
    let serviceStatus: "healthy" | "degraded" | "unhealthy" = "healthy";
    if (checks.openai === "error") serviceStatus = "degraded";
    if (
      checks.contextManager === "unhealthy" ||
      checks.suggestionEngine === "unhealthy"
    ) {
      serviceStatus = "unhealthy";
    }

    return {
      service: serviceStatus,
      openai: checks.openai,
      contextManager: checks.contextManager,
      suggestionEngine: checks.suggestionEngine,
      uptime: Date.now() - (this as any).startTime || 0,
    };
  }

  /**
   * Регистрация стандартных команд
   */
  private registerDefaultCommands(): void {
    // Команда помощи
    this.registerCommand({
      id: "help",
      name: "help",
      description: "Показать список доступных команд",
      syntax: "help [команда]",
      category: "system",
      handler: async (params, context) => {
        const commands = this.getAllCommands();
        const commandList = commands
          .map(
            (cmd) =>
              `${cmd.name} - ${cmd.description}\n   Синтаксис: ${cmd.syntax}`
          )
          .join("\n\n");

        return {
          commands: commandList,
          totalCommands: commands.length,
        };
      },
    });

    // Команда статистики
    this.registerCommand({
      id: "stats",
      name: "stats",
      description: "Показать статистику использования",
      syntax: "stats",
      category: "system",
      handler: async (params, context) => {
        return {
          chatSessions: this.chatSessions.size,
          commands: this.commands.size,
          openaiConfigured: !!this.openaiService,
          contextStats: contextManager.getUsageStats(),
          suggestionStats: suggestionEngine.getEngineStats(),
        };
      },
    });

    // Команда контекста
    this.registerCommand({
      id: "context",
      name: "context",
      description: "Показать текущий контекст",
      syntax: "context",
      category: "system",
      handler: async (params, context) => {
        return {
          conversationId: context.id,
          agentType: context.agentType,
          messageCount: (context.messages || []).length,
          tasks: context.sessionData.taskHistory || [],
          currentProject: context.sessionData.currentProject,
          summary: contextManager.generateContextSummary(context.id),
        };
      },
    });

    // Команда очистки контекста
    this.registerCommand({
      id: "clear",
      name: "clear",
      description: "Очистить историю разговора",
      syntax: "clear",
      category: "system",
      handler: async (params, context) => {
        // Создаем новый контекст
        const newContextId = contextManager.createConversation(
          context.userId,
          context.agentType
        );
        return {
          oldContextId: context.id,
          newContextId,
          message: "Контекст очищен. Начинаем новый разговор.",
        };
      },
    });
  }

  /**
   * Инициализация подсказок для задач
   */
  private initializeTaskSuggestions(): void {
    // Подсказки для разработки 1C
    this.taskSuggestions.set("1c_development", [
      {
        id: "create_document",
        taskType: "create_document",
        estimatedTime: "2-4 часа",
        complexity: "medium",
        description: "Создание нового документа в 1C",
        prerequisites: [
          "Знание структуры конфигурации",
          "Понимание бизнес-логики",
        ],
        steps: [
          "Определить реквизиты документа",
          "Создать форму документа",
          "Реализовать проведение",
          "Добавить печатные формы",
          "Написать модуль объекта",
        ],
      },
      {
        id: "optimize_query",
        taskType: "optimize_query",
        estimatedTime: "1-2 часа",
        complexity: "medium",
        description: "Оптимизация запроса к базе данных",
        prerequisites: ["Знание языка запросов 1C", "Понимание индексов"],
        steps: [
          "Проанализировать текущий запрос",
          "Выявить узкие места",
          "Добавить индексы",
          "Оптимизировать условия",
          "Протестировать производительность",
        ],
      },
    ]);

    // Подсказки для архитектуры
    this.taskSuggestions.set("architecture", [
      {
        id: "design_pattern",
        taskType: "design_pattern",
        estimatedTime: "4-8 часов",
        complexity: "high",
        description: "Применение паттерна проектирования",
        prerequisites: ["Знание паттернов GoF", "Понимание архитектуры 1C"],
        steps: [
          "Выбрать подходящий паттерн",
          "Адаптировать под 1C",
          "Реализовать структуру",
          "Интегрировать с существующим кодом",
          "Написать документацию",
        ],
      },
    ]);
  }

  /**
   * Обновление конфигурации
   */
  updateConfig(newConfig: Partial<AIAssistantConfig>): void {
    this.config = { ...this.config, ...newConfig };

    // Обновляем OpenAI если изменилась конфигурация
    if (newConfig.openai) {
      this.initializeOpenAI();
    }
  }

  /**
   * Получение текущей конфигурации
   */
  getConfig(): AIAssistantConfig {
    return { ...this.config };
  }

  /**
   * Получение статистики сервиса
   */
  getServiceStats(): {
    sessions: {
      total: number;
      active: number;
      closed: number;
    };
    commands: {
      total: number;
      byCategory: Record<string, number>;
    };
    openai: {
      configured: boolean;
      healthy: boolean;
    };
    features: {
      suggestions: boolean;
      streaming: boolean;
      embeddings: boolean;
    };
  } {
    const sessions = this.chatSessions.values();
    const commands = this.commands.values();

    return {
      sessions: {
        total: this.chatSessions.size,
        active: Array.from(sessions).filter((s) => s.status === "active")
          .length,
        closed: Array.from(sessions).filter((s) => s.status === "closed")
          .length,
      },
      commands: {
        total: this.commands.size,
        byCategory: Array.from(commands).reduce((acc, cmd) => {
          acc[cmd.category] = (acc[cmd.category] || 0) + 1;
          return acc;
        }, {} as Record<string, number>),
      },
      openai: {
        configured: !!this.openaiService,
        healthy: this.openaiService?.getUsageStats()?.totalRequests > 0,
      },
      features: {
        suggestions: this.config.suggestions?.enabled ?? true,
        streaming: this.config.features?.streaming ?? false,
        embeddings: this.config.features?.embeddings ?? false,
      },
    };
  }
}

// Экспортируем instance по умолчанию
let aiAssistantInstance: AIAssistantService | null = null;

export function getAIAssistant(config?: AIAssistantConfig): AIAssistantService {
  if (!aiAssistantInstance && config) {
    aiAssistantInstance = new AIAssistantService(config);
  } else if (!aiAssistantInstance) {
    throw new Error(
      "AI Assistant сервис не инициализирован. Укажите конфигурацию."
    );
  }

  return aiAssistantInstance;
}

export function initializeAIAssistant(
  config: AIAssistantConfig
): AIAssistantService {
  aiAssistantInstance = new AIAssistantService(config);
  return aiAssistantInstance;
}
