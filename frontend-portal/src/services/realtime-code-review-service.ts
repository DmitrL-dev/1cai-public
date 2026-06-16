/**
 * Real-time Code Review Service
 * Анализ кода в реальном времени с предложениями по улучшению
 * Версия: 1.0.0
 */

import { getOpenAIService, OpenAIIntegrationService } from './openai-integration-service';

export interface CodeSuggestion {
  id: string;
  type: 'error' | 'warning' | 'info' | 'hint';
  severity: 'critical' | 'high' | 'medium' | 'low';
  message: string;
  description: string;
  suggestion?: string;
  code?: string;
  position: {
    line: number;
    column: number;
    endLine?: number;
    endColumn?: number;
  };
  category: 'performance' | 'security' | 'best-practice' | 'style' | 'bug' | 'optimization';
  autoFixable: boolean;
  confidence: number; // 0-1
}

export interface CodeAnalysisResult {
  suggestions: CodeSuggestion[];
  metrics: {
    complexity: number;
    maintainability: number;
    securityScore: number;
    performanceScore: number;
    codeQuality: number;
  };
  statistics: {
    totalLines: number;
    functions: number;
    variables: number;
    comments: number;
    potentialIssues: number;
  };
  recommendations: string[];
}

export interface CodeContext {
  content: string;
  language: 'bsl' | 'typescript' | 'javascript' | 'python' | 'java' | 'csharp';
  fileName?: string;
  projectContext?: {
    framework?: string;
    version?: string;
    standards?: string[];
  };
  cursorPosition?: {
    line: number;
    column: number;
  };
  recentChanges?: string[]; // История последних изменений
}

export class RealtimeCodeReviewService {
  private openaiService: OpenAIIntegrationService | null = null;
  private cache = new Map<string, CodeAnalysisResult>();
  private analysisRules: Map<string, (code: string, context: CodeContext) => CodeSuggestion[]> = new Map();

  constructor(openaiService?: OpenAIIntegrationService) {
    this.openaiService = openaiService || null;
    this.initializeRules();
  }

  /**
   * Анализ кода в реальном времени
   */
  async analyzeCode(context: CodeContext): Promise<CodeAnalysisResult> {
    const cacheKey = this.getCacheKey(context);
    
    // Проверка кэша
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey)!;
    }

    // Локальный анализ (быстро)
    const localSuggestions = this.performLocalAnalysis(context);
    
    // AI анализ (если доступен)
    let aiSuggestions: CodeSuggestion[] = [];
    if (this.openaiService) {
      try {
        aiSuggestions = await this.performAIAnalysis(context);
      } catch (error) {
        console.error('AI анализ недоступен:', error);
      }
    }

    // Объединение результатов
    const allSuggestions = [...localSuggestions, ...aiSuggestions]
      .filter((s, index, self) => 
        index === self.findIndex(t => t.position.line === s.position.line && t.message === s.message)
      );

    // Вычисление метрик
    const metrics = this.calculateMetrics(context, allSuggestions);
    
    // Генерация статистики
    const statistics = this.generateStatistics(context);
    
    // Формирование рекомендаций
    const recommendations = this.generateRecommendations(allSuggestions, metrics);

    const result: CodeAnalysisResult = {
      suggestions: allSuggestions.sort((a, b) => {
        const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
        return severityOrder[a.severity] - severityOrder[b.severity];
      }),
      metrics,
      statistics,
      recommendations
    };

    // Кэширование
    this.cache.set(cacheKey, result);
    setTimeout(() => this.cache.delete(cacheKey), 30000); // 30 секунд TTL

    return result;
  }

  /**
   * Локальный анализ кода (быстрый, без AI)
   */
  private performLocalAnalysis(context: CodeContext): CodeSuggestion[] {
    const suggestions: CodeSuggestion[] = [];
    const lines = context.content.split('\n');

    // Применение правил анализа
    for (const [ruleName, rule] of this.analysisRules) {
      try {
        const ruleSuggestions = rule(context.content, context);
        suggestions.push(...ruleSuggestions);
      } catch (error) {
        console.error(`Ошибка в правиле ${ruleName}:`, error);
      }
    }

    return suggestions;
  }

  /**
   * AI анализ кода
   */
  private async performAIAnalysis(context: CodeContext): Promise<CodeSuggestion[]> {
    if (!this.openaiService) {
      return [];
    }

    const prompt = this.buildAnalysisPrompt(context);

    try {
      const response = await this.openaiService.complete({
        messages: [
          {
            role: 'system',
            content: `Ты - опытный code reviewer для языка ${context.language}, специализирующийся на платформе 1С:Предприятие.
            
Анализируй код и предлагай:
- Оптимизации производительности
- Улучшения безопасности
- Best practices
- Выявление потенциальных багов
- Стилистические улучшения

Отвечай в формате JSON массивом предложений.`
          },
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: 0.3,
        maxTokens: 2000
      });

      return this.parseAIResponse(response.content, context);
    } catch (error) {
      console.error('Ошибка AI анализа:', error);
      return [];
    }
  }

  /**
   * Построение промпта для AI
   */
  private buildAnalysisPrompt(context: CodeContext): string {
    return `Проанализируй следующий код на языке ${context.language}:

\`\`\`${context.language}
${context.content}
\`\`\`

Файл: ${context.fileName || 'unknown'}

Контекст проекта:
${context.projectContext ? JSON.stringify(context.projectContext, null, 2) : 'Не указан'}

Найди проблемы и предложи улучшения. Верни результат в формате JSON:
[
  {
    "type": "error|warning|info|hint",
    "severity": "critical|high|medium|low",
    "message": "Краткое описание проблемы",
    "description": "Подробное описание",
    "suggestion": "Предложение по исправлению",
    "line": 1,
    "column": 1,
    "category": "performance|security|best-practice|style|bug|optimization",
    "autoFixable": true|false,
    "confidence": 0.9
  }
]`;
  }

  /**
   * Парсинг ответа AI
   */
  private parseAIResponse(content: string, context: CodeContext): CodeSuggestion[] {
    try {
      // Извлечение JSON из ответа
      const jsonMatch = content.match(/\[[\s\S]*\]/);
      if (!jsonMatch) {
        return [];
      }

      const suggestions = JSON.parse(jsonMatch[0]);
      
      return suggestions.map((s: any, index: number) => ({
        id: `ai-${Date.now()}-${index}`,
        type: s.type || 'info',
        severity: s.severity || 'medium',
        message: s.message || '',
        description: s.description || s.message || '',
        suggestion: s.suggestion,
        position: {
          line: s.line || 1,
          column: s.column || 1,
          endLine: s.endLine,
          endColumn: s.endColumn
        },
        category: s.category || 'best-practice',
        autoFixable: s.autoFixable || false,
        confidence: s.confidence || 0.7
      }));
    } catch (error) {
      console.error('Ошибка парсинга AI ответа:', error);
      return [];
    }
  }

  /**
   * Инициализация правил анализа
   */
  private initializeRules(): void {
    // Правило: проверка производительности циклов
    this.analysisRules.set('performance-loops', (code: string, context: CodeContext) => {
      const suggestions: CodeSuggestion[] = [];
      const lines = code.split('\n');

      lines.forEach((line, index) => {
        // Проверка циклов с запросами к БД
        if (/Для\s+\w+\s*=\s*\d+\s+По\s+\w+/.test(line)) {
          const nextLines = lines.slice(index, index + 10).join('\n');
          if (/Запрос\s*=|Справочники\.|Документы\./.test(nextLines)) {
            suggestions.push({
              id: `perf-${index}`,
              type: 'warning',
              severity: 'high',
              message: 'Возможна проблема производительности: запрос к БД в цикле',
              description: 'Запросы к базе данных внутри цикла могут значительно замедлить выполнение',
              suggestion: 'Рассмотрите вариант выполнения запроса вне цикла или использования группировок',
              position: { line: index + 1, column: 1 },
              category: 'performance',
              autoFixable: false,
              confidence: 0.8
            });
          }
        }
      });

      return suggestions;
    });

    // Правило: проверка безопасности
    this.analysisRules.set('security-checks', (code: string, context: CodeContext) => {
      const suggestions: CodeSuggestion[] = [];
      const lines = code.split('\n');

      lines.forEach((line, index) => {
        // Проверка SQL инъекций
        if (/Запрос\s*=/.test(line) && /[+]/.test(line)) {
          suggestions.push({
            id: `sec-${index}`,
            type: 'error',
            severity: 'critical',
            message: 'Потенциальная SQL инъекция',
            description: 'Конкатенация строк в запросе может быть небезопасной',
            suggestion: 'Используйте параметры запроса вместо конкатенации строк',
            position: { line: index + 1, column: 1 },
            category: 'security',
            autoFixable: false,
            confidence: 0.9
          });
        }

        // Проверка на хардкод паролей
        if (/Пароль\s*=\s*["']/.test(line) || /password\s*=\s*["']/.test(line)) {
          suggestions.push({
            id: `sec-pass-${index}`,
            type: 'error',
            severity: 'critical',
            message: 'Обнаружен хардкод пароля',
            description: 'Пароли не должны храниться в коде',
            suggestion: 'Используйте переменные окружения или хранилище секретов',
            position: { line: index + 1, column: 1 },
            category: 'security',
            autoFixable: false,
            confidence: 1.0
          });
        }
      });

      return suggestions;
    });

    // Правило: best practices для BSL
    this.analysisRules.set('bsl-best-practices', (code: string, context: CodeContext) => {
      if (context.language !== 'bsl') return [];
      
      const suggestions: CodeSuggestion[] = [];
      const lines = code.split('\n');

      lines.forEach((line, index) => {
        // Проверка использования Тип() вместо ПроверитьТип()
        if (/Если\s+Тип\(/.test(line) && !/ПроверитьТип/.test(line)) {
          suggestions.push({
            id: `bsl-type-${index}`,
            type: 'hint',
            severity: 'low',
            message: 'Рекомендуется использовать ПроверитьТип() вместо Тип()',
            description: 'ПроверитьТип() более эффективен и безопасен',
            suggestion: 'Замените Тип() на ПроверитьТип()',
            position: { line: index + 1, column: 1 },
            category: 'best-practice',
            autoFixable: true,
            confidence: 0.7
          });
        }

        // Проверка обработки исключений
        if (/ВызватьИсключение/.test(line) && index > 0) {
          const prevLines = lines.slice(Math.max(0, index - 5), index).join('\n');
          if (!/Попытка/.test(prevLines)) {
            suggestions.push({
              id: `bsl-exception-${index}`,
              type: 'warning',
              severity: 'medium',
              message: 'Исключение вне блока Попытка-Исключение',
              description: 'Исключения должны обрабатываться',
              suggestion: 'Оберните код в блок Попытка-Исключение',
              position: { line: index + 1, column: 1 },
              category: 'best-practice',
              autoFixable: false,
              confidence: 0.8
            });
          }
        }
      });

      return suggestions;
    });
  }

  /**
   * Вычисление метрик кода
   */
  private calculateMetrics(context: CodeContext, suggestions: CodeSuggestion[]): CodeAnalysisResult['metrics'] {
    const criticalIssues = suggestions.filter(s => s.severity === 'critical').length;
    const highIssues = suggestions.filter(s => s.severity === 'high').length;
    const lines = context.content.split('\n').length;

    // Базовая сложность (упрощенная)
    const complexity = Math.min(100, (lines / 100) * 50 + (suggestions.length / 10) * 50);

    // Maintainability индекс (чем меньше проблем, тем выше)
    const maintainability = Math.max(0, 100 - (criticalIssues * 20 + highIssues * 10));

    // Security score
    const securityIssues = suggestions.filter(s => s.category === 'security').length;
    const securityScore = Math.max(0, 100 - securityIssues * 25);

    // Performance score
    const performanceIssues = suggestions.filter(s => s.category === 'performance').length;
    const performanceScore = Math.max(0, 100 - performanceIssues * 15);

    // Общее качество кода
    const codeQuality = (maintainability + securityScore + performanceScore) / 3;

    return {
      complexity: Math.round(complexity),
      maintainability: Math.round(maintainability),
      securityScore: Math.round(securityScore),
      performanceScore: Math.round(performanceScore),
      codeQuality: Math.round(codeQuality)
    };
  }

  /**
   * Генерация статистики
   */
  private generateStatistics(context: CodeContext): CodeAnalysisResult['statistics'] {
    const lines = context.content.split('\n');
    const totalLines = lines.length;
    
    // Подсчет функций (упрощенный для BSL)
    const functions = (context.content.match(/Процедура|Функция/g) || []).length;
    
    // Подсчет переменных
    const variables = (context.content.match(/\w+\s*=/g) || []).length;
    
    // Подсчет комментариев
    const comments = (context.content.match(/\/\/|#|'.*$/gm) || []).length;

    return {
      totalLines,
      functions,
      variables,
      comments,
      potentialIssues: 0 // Будет вычислено из suggestions
    };
  }

  /**
   * Генерация рекомендаций
   */
  private generateRecommendations(suggestions: CodeSuggestion[], metrics: CodeAnalysisResult['metrics']): string[] {
    const recommendations: string[] = [];

    if (metrics.securityScore < 70) {
      recommendations.push('Рекомендуется усилить проверки безопасности в коде');
    }

    if (metrics.performanceScore < 70) {
      recommendations.push('Обнаружены проблемы производительности. Рассмотрите оптимизацию запросов и алгоритмов');
    }

    if (metrics.maintainability < 70) {
      recommendations.push('Код требует улучшения для лучшей поддерживаемости');
    }

    const criticalIssues = suggestions.filter(s => s.severity === 'critical').length;
    if (criticalIssues > 0) {
      recommendations.push(`Обнаружено ${criticalIssues} критических проблем. Требуется немедленное исправление`);
    }

    return recommendations;
  }

  /**
   * Получение ключа для кэша
   */
  private getCacheKey(context: CodeContext): string {
    return `${context.language}-${context.content.length}-${context.content.hashCode()}`;
  }

  /**
   * Применение автозамены
   */
  applyAutoFix(suggestion: CodeSuggestion, code: string): string {
    // Базовые автозамены
    if (suggestion.type === 'hint' && suggestion.autoFixable) {
      // Пример: замена Тип() на ПроверитьТип()
      if (suggestion.message.includes('ПроверитьТип')) {
        const lines = code.split('\n');
        const line = lines[suggestion.position.line - 1];
        if (line) {
          lines[suggestion.position.line - 1] = line.replace(/Тип\(/g, 'ПроверитьТип(');
          return lines.join('\n');
        }
      }
    }

    return code;
  }
}

// Расширение String для hashCode (для кэширования)
declare global {
  interface String {
    hashCode(): number;
  }
}

String.prototype.hashCode = function(): number {
  let hash = 0;
  for (let i = 0; i < this.length; i++) {
    const char = this.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return hash;
};

// Экспорт синглтона
let codeReviewServiceInstance: RealtimeCodeReviewService | null = null;

export function getCodeReviewService(openaiService?: OpenAIIntegrationService): RealtimeCodeReviewService {
  if (!codeReviewServiceInstance) {
    codeReviewServiceInstance = new RealtimeCodeReviewService(openaiService);
  }
  return codeReviewServiceInstance;
}







