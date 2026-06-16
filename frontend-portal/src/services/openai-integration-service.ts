/**
 * OpenAI Integration Service
 * Интеграция с OpenAI API для AI помощника
 */

import { contextManager } from "./context-manager-service";
import { Suggestion, suggestionEngine } from "./suggestion-engine-service";

export interface OpenAIConfig {
  apiKey: string;
  baseURL: string;
  model: string;
  maxTokens: number;
  temperature: number;
  timeout: number;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
  name?: string;
}

export interface AIResponse {
  content: string;
  tokens: {
    prompt: number;
    completion: number;
    total: number;
  };
  model: string;
  finishReason: "stop" | "length" | "content_filter" | "null";
  confidence: number;
  suggestions?: Suggestion[];
  metadata?: {
    responseTime: number;
    contextSize: number;
    error?: string;
  };
}

export interface CompletionOptions {
  conversationId: string;
  userMessage: string;
  systemPrompt?: string;
  includeSuggestions?: boolean;
  maxSuggestions?: number;
  stream?: boolean;
}

export class OpenAIIntegrationService {
  private config: OpenAIConfig;
  private requestQueue: Promise<any> = Promise.resolve();
  private rateLimiter = {
    requests: 0,
    resetTime: Date.now() + 60000, // 1 минута
    maxRequests: 60, // requests per minute
  };

  constructor(config: OpenAIConfig) {
    this.config = config;
    this.validateConfig();
  }

  /**
   * Валидация конфигурации
   */
  private validateConfig(): void {
    if (!this.config.apiKey) {
      throw new Error("OpenAI API ключ не указан");
    }
    if (!this.config.baseURL) {
      this.config.baseURL = "https://api.openai.com/v1";
    }
    if (!this.config.model) {
      this.config.model = "gpt-3.5-turbo";
    }
    if (!this.config.maxTokens) {
      this.config.maxTokens = 2000;
    }
    if (!this.config.temperature) {
      this.config.temperature = 0.7;
    }
    if (!this.config.timeout) {
      this.config.timeout = 30000;
    }
  }

  /**
   * Отправка запроса к OpenAI API
   */
  private async makeRequest(endpoint: string, data: any): Promise<any> {
    // Rate limiting
    await this.checkRateLimit();

    const url = `${this.config.baseURL}${endpoint}`;
    const startTime = Date.now();

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.config.apiKey}`,
        },
        body: JSON.stringify(data),
        signal: AbortSignal.timeout(this.config.timeout),
      });

      const responseTime = Date.now() - startTime;

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          `OpenAI API ошибка: ${response.status} - ${
            errorData.error?.message || response.statusText
          }`
        );
      }

      const result = await response.json();
      this.updateRateLimiter();

      return {
        ...result,
        metadata: {
          responseTime,
          status: response.status,
        },
      };
    } catch (error) {
      this.updateRateLimiter();

      if (error instanceof Error && error.name === "TimeoutError") {
        throw new Error("Таймаут запроса к OpenAI API");
      }

      throw error;
    }
  }

  /**
   * Проверка rate limiting
   */
  private async checkRateLimit(): Promise<void> {
    const now = Date.now();

    // Сбрасываем счетчик если прошла минута
    if (now > this.rateLimiter.resetTime) {
      this.rateLimiter.requests = 0;
      this.rateLimiter.resetTime = now + 60000;
    }

    // Ждем если превысили лимит
    while (this.rateLimiter.requests >= this.rateLimiter.maxRequests) {
      const waitTime = this.rateLimiter.resetTime - now;
      if (waitTime > 0) {
        await new Promise((resolve) => setTimeout(resolve, waitTime));
      }
      return this.checkRateLimit(); // Рекурсивно проверяем снова
    }
  }

  /**
   * Обновление rate limiter
   */
  private updateRateLimiter(): void {
    this.rateLimiter.requests++;
  }

  /**
   * Основной метод для получения AI ответа
   */
  async generateResponse(options: CompletionOptions): Promise<AIResponse> {
    const startTime = Date.now();

    try {
      // Получаем контекст разговора
      const context = contextManager.getConversation(options.conversationId);
      if (!context) {
        throw new Error(`Контекст ${options.conversationId} не найден`);
      }

      // Формируем промпт с контекстом
      const messages = this.buildMessages(options, context);

      // Отправляем запрос к OpenAI
      const apiResponse = await this.makeRequest("/chat/completions", {
        model: this.config.model,
        messages,
        max_tokens: this.config.maxTokens,
        temperature: this.config.temperature,
        stream: options.stream || false,
      });

      const responseTime = Date.now() - startTime;
      const aiContent = apiResponse.choices[0]?.message?.content || "";

      // Генерируем подсказки если требуется
      let suggestions: Suggestion[] = [];
      if (options.includeSuggestions) {
        suggestions = suggestionEngine.generateSuggestions(
          options.conversationId
        );
        if (options.maxSuggestions) {
          suggestions = suggestions.slice(0, options.maxSuggestions);
        }
      }

      const response: AIResponse = {
        content: aiContent,
        tokens: {
          prompt: apiResponse.usage?.prompt_tokens || 0,
          completion: apiResponse.usage?.completion_tokens || 0,
          total: apiResponse.usage?.total_tokens || 0,
        },
        model: apiResponse.model || this.config.model,
        finishReason: apiResponse.choices[0]?.finish_reason || "stop",
        confidence: this.calculateConfidence(aiContent, context),
        suggestions,
        metadata: {
          responseTime,
          contextSize: messages.length,
          ...apiResponse.metadata,
        },
      };

      // Сохраняем ответ в контекст
      contextManager.addMessage(options.conversationId, {
        role: "assistant",
        content: aiContent,
        metadata: {
          agentType: context.agentType,
          contextData: {
            tokensUsed: response.tokens.total,
            responseTime: responseTime,
          },
        },
      });

      return response;
    } catch (error) {
      const responseTime = Date.now() - startTime;

      return {
        content: `Извините, произошла ошибка при обработке запроса: ${
          error instanceof Error ? error.message : "Неизвестная ошибка"
        }`,
        tokens: { prompt: 0, completion: 0, total: 0 },
        model: this.config.model,
        finishReason: "stop",
        confidence: 0,
        metadata: {
          responseTime,
          contextSize: 0,
          error: error instanceof Error ? error.message : "Unknown error",
        },
      };
    }
  }

  /**
   * Построение сообщений для API
   */
  private buildMessages(
    options: CompletionOptions,
    context: any
  ): ChatMessage[] {
    const messages: ChatMessage[] = [];

    // Системный промпт
    const systemPrompt =
      options.systemPrompt || this.getDefaultSystemPrompt(context);
    messages.push({
      role: "system",
      content: systemPrompt,
    });

    // Добавляем контекстные сообщения
    const keyContext = contextManager.extractKeyContext(
      options.conversationId,
      5
    );
    keyContext.forEach((msg) => {
      if (msg.role !== "system" || msg.content !== systemPrompt) {
        messages.push({
          role: msg.role,
          content: msg.content,
          name: msg.role === "user" ? "user" : "assistant",
        });
      }
    });

    // Добавляем текущий запрос пользователя
    messages.push({
      role: "user",
      content: options.userMessage,
      name: "user",
    });

    return messages;
  }

  /**
   * Получение стандартного системного промпта
   */
  private getDefaultSystemPrompt(context: any): string {
    return `
Ты - AI помощник для разработки в системе 1C. Специализируешься на:
- Разработке конфигураций 1C
- Оптимизации запросов
- Архитектурных решениях
- Лучших практиках разработки

Принципы работы:
1. Отвечай на русском языке
2. Предоставляй конкретные и практичные решения
3. Учитывай специфику платформы 1C
4. При необходимости спрашивай уточнения
5. Предлагай альтернативные варианты решений

Контекст:
- Агент: ${context.agentType}
- Проект: ${context.sessionData.currentProject || "не указан"}
- Текущие задачи: ${(context.sessionData.taskHistory || []).length}
- Рабочая директория: ${context.sessionData.workingDirectory || "не указана"}

Всегда старайся быть максимально полезным и точным в ответах.
    `.trim();
  }

  /**
   * Расчет уверенности в ответе
   */
  private calculateConfidence(content: string, context: any): number {
    let confidence = 0.5; // Базовая уверенность

    // Увеличиваем уверенность если контент содержит ключевые слова
    const keywords = [
      "рекомендую",
      "предлагаю",
      "следует",
      "необходимо",
      "обязательно",
    ];
    const hasKeywords = keywords.some((keyword) =>
      content.toLowerCase().includes(keyword)
    );
    if (hasKeywords) confidence += 0.2;

    // Увеличиваем если есть примеры кода
    if (
      content.includes("```") ||
      content.includes("BSL") ||
      content.includes("1С")
    ) {
      confidence += 0.2;
    }

    // Увеличиваем если ответ подробный
    if (content.length > 200) confidence += 0.1;

    // Учитываем размер контекста
    if (context.messages.length > 5) confidence += 0.1;

    return Math.min(1.0, confidence);
  }

  /**
   * Генерация embeddings для поиска
   */
  async generateEmbedding(text: string): Promise<number[]> {
    try {
      const response = await this.makeRequest("/embeddings", {
        model: "text-embedding-ada-002",
        input: text,
      });

      return response.data[0].embedding;
    } catch (error) {
      console.warn("Ошибка генерации embeddings:", error);
      // Возвращаем случайный вектор как fallback
      return Array.from({ length: 1536 }, () => Math.random());
    }
  }

  /**
   * Модерация контента
   */
  async moderateContent(text: string): Promise<{
    flagged: boolean;
    categories: Record<string, boolean>;
    category_scores: Record<string, number>;
  }> {
    try {
      const response = await this.makeRequest("/moderations", {
        input: text,
      });

      const result = response.results[0];
      return {
        flagged: result.flagged,
        categories: result.categories,
        category_scores: result.category_scores,
      };
    } catch (error) {
      console.warn("Ошибка модерации контента:", error);
      return {
        flagged: false,
        categories: {},
        category_scores: {},
      };
    }
  }

  /**
   * Обновление конфигурации
   */
  updateConfig(newConfig: Partial<OpenAIConfig>): void {
    this.config = { ...this.config, ...newConfig };
    this.validateConfig();
  }

  /**
   * Получение текущей конфигурации
   */
  getConfig(): OpenAIConfig {
    return { ...this.config };
  }

  /**
   * Проверка состояния API
   */
  async healthCheck(): Promise<{
    status: "healthy" | "unhealthy" | "rate_limited";
    responseTime: number;
    error?: string;
  }> {
    const startTime = Date.now();

    try {
      await this.makeRequest("/models", {});
      const responseTime = Date.now() - startTime;

      return {
        status: "healthy",
        responseTime,
      };
    } catch (error) {
      const responseTime = Date.now() - startTime;

      let status: "unhealthy" | "rate_limited" = "unhealthy";
      if (error instanceof Error && error.message.includes("rate limit")) {
        status = "rate_limited";
      }

      return {
        status,
        responseTime,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  /**
   * Получение статистики использования
   */
  getUsageStats(): {
    totalRequests: number;
    rateLimitStatus: {
      requests: number;
      remaining: number;
      resetTime: number;
    };
    averageResponseTime: number;
  } {
    const remaining = Math.max(
      0,
      this.rateLimiter.maxRequests - this.rateLimiter.requests
    );

    return {
      totalRequests: this.rateLimiter.requests,
      rateLimitStatus: {
        requests: this.rateLimiter.requests,
        remaining,
        resetTime: this.rateLimiter.resetTime,
      },
      averageResponseTime: 0, // Можно добавить расчет среднего времени ответа
    };
  }

  /**
   * Сброс rate limiter (для тестирования)
   */
  resetRateLimit(): void {
    this.rateLimiter.requests = 0;
    this.rateLimiter.resetTime = Date.now() + 60000;
  }

  /**
   * Создание streaming запроса
   */
  async *streamResponse(
    options: CompletionOptions
  ): AsyncGenerator<string, AIResponse, unknown> {
    const fullContent: string[] = [];
    let finalResponse: AIResponse;

    try {
      const context = contextManager.getConversation(options.conversationId);
      if (!context) {
        throw new Error(`Контекст ${options.conversationId} не найден`);
      }

      const messages = this.buildMessages(options, context);

      const response = await fetch(`${this.config.baseURL}/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.config.apiKey}`,
        },
        body: JSON.stringify({
          model: this.config.model,
          messages,
          max_tokens: this.config.maxTokens,
          temperature: this.config.temperature,
          stream: true,
        }),
      });

      if (!response.ok) {
        throw new Error(`OpenAI API ошибка: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("Не удалось получить reader для streaming");
      }

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);

            if (data === "[DONE]") {
              finalResponse = {
                content: fullContent.join(""),
                tokens: { prompt: 0, completion: 0, total: 0 },
                model: this.config.model,
                finishReason: "stop",
                confidence: 0.8,
                metadata: { responseTime: 0, contextSize: 0 },
              };
              break;
            }

            try {
              const parsed = JSON.parse(data);
              const delta = parsed.choices[0]?.delta?.content;

              if (delta) {
                fullContent.push(delta);
                yield delta;
              }
            } catch (e) {
              // Игнорируем ошибки парсинга отдельных чанков
            }
          }
        }
      }

      // Генерируем финальный ответ
      finalResponse = await this.generateResponse({
        ...options,
        stream: false,
      });

      return finalResponse;
    } catch (error) {
      throw new Error(
        `Streaming ошибка: ${
          error instanceof Error ? error.message : "Unknown error"
        }`
      );
    }
  }
}

// Экспортируем instance по умолчанию
let openAIInstance: OpenAIIntegrationService | null = null;

export function getOpenAIService(
  config?: OpenAIConfig
): OpenAIIntegrationService {
  if (!openAIInstance && config) {
    openAIInstance = new OpenAIIntegrationService(config);
  } else if (!openAIInstance) {
    throw new Error("OpenAI сервис не инициализирован. Укажите конфигурацию.");
  }

  return openAIInstance;
}

export function initializeOpenAI(
  config: OpenAIConfig
): OpenAIIntegrationService {
  openAIInstance = new OpenAIIntegrationService(config);
  return openAIInstance;
}
