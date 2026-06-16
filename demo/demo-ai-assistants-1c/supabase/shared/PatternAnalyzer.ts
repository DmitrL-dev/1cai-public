/**
 * Pattern Analyzer for automatic request classification
 * Eliminates duplicate pattern matching logic across all Edge Functions
 */

import { TextAnalyzer, ValidationUtils } from './utils.ts';

export interface PatternMatch {
  pattern: string;
  weight: number;
  category: string;
}

export interface AnalysisResult {
  category: string;
  confidence: number;
  matches: PatternMatch[];
  recommendedAction?: string;
}

export class PatternAnalyzer {
  private static patterns: Record<string, string[]> = {
    // 1С specific patterns
    '1c_integration': [
      'интеграция с 1с', 'интеграция 1с', '1с интеграция', 'обмен с 1с',
      'синхронизация с 1с', 'связь с 1с', 'подключение к 1с', 'api 1с'
    ],
    '1c_documents': [
      'документ', 'документы', 'проведение', 'провести', 'накладная', 
      'приход', 'расход', 'счет', 'акт', 'товарная накладная'
    ],
    '1c_reports': [
      'отчет', 'отчеты', 'отчетность', 'формирование отчета', 'анализ',
      'остатки', 'движения', 'ведомость', 'реестр'
    ],
    '1c_configuration': [
      'конфигурация', 'настройка', 'параметры', 'справочник', 'регистр',
      'общие модули', 'обработка', 'отчеты конфигурации'
    ],

    // Development patterns
    'code_development': [
      'разработка', 'код', 'функция', 'процедура', 'модуль', 'программирование',
      'development', 'coding', 'function', 'procedure', 'module'
    ],
    'api_development': [
      'api', 'веб-сервис', 'rest', 'soap', 'endpoint', 'интерфейс',
      'web service', 'rest api', 'endpoint'
    ],
    'database_design': [
      'база данных', 'таблица', 'схема', 'модель данных', 'структура',
      'database', 'table', 'schema', 'data model'
    ],

    // Testing patterns
    'unit_testing': [
      'unit', 'модульн', 'проверка функции', 'тест функции',
      'unit test', 'function test', 'validation'
    ],
    'integration_testing': [
      'интеграц', 'обмен', 'синхронизац', 'связь между системами',
      'integration', 'sync', 'data exchange'
    ],
    'functional_testing': [
      'функционал', 'бизнес-процесс', 'сценарий', 'пользовательск',
      'functional', 'business process', 'user scenario'
    ],
    'performance_testing': [
      'производительн', 'нагрузк', 'время отклика', 'скорость',
      'performance', 'load', 'response time', 'speed'
    ],
    'test_automation': [
      'автотест', 'автоматиз', 'скрипт', 'бот', 'робот',
      'automation', 'script', 'bot', 'automated test'
    ],

    // Project Management patterns
    'project_planning': [
      'планирование', 'план проекта', 'график', 'сроки', 'этап',
      'planning', 'project plan', 'timeline', 'schedule', 'phase'
    ],
    'risk_management': [
      'риск', 'оценка рисков', 'митигация', 'проблема',
      'risk', 'risk assessment', 'mitigation', 'issue'
    ],
    'resource_management': [
      'ресурсы', 'команда', 'нагрузка', 'мощности', 'доступность',
      'resources', 'team', 'capacity', 'availability'
    ],
    'stakeholder_management': [
      'стейкхолдер', 'заинтересованн', 'коммуникац', 'согласование',
      'stakeholder', 'communication', 'agreement', 'approval'
    ],

    // Business Analysis patterns
    'requirements_analysis': [
      'требован', 'тз', 'техническ задание', 'brd', 'specification',
      'requirement', 'spec', 'functional spec'
    ],
    'process_modeling': [
      'процесс', 'моделирование', 'bpmn', 'диаграмм', 'workflow',
      'process', 'modeling', 'diagram', 'workflow'
    ],
    'user_stories': [
      'user story', 'история пользователя', 'as a', 'я хочу', 'чтобы',
      'user story', 'acceptance criteria'
    ],
    'use_cases': [
      'use case', 'сценарий использования', 'актер', 'действие',
      'use case', 'scenario', 'actor', 'action'
    ],
    'data_analysis': [
      'анализ данных', 'отчет', 'аналитика', 'bi', 'kpi',
      'data analysis', 'analytics', 'business intelligence'
    ],

    // Architecture patterns
    'system_architecture': [
      'архитектура', 'архитектурный', 'системный дизайн', 'компонент',
      'architecture', 'architectural', 'system design', 'component'
    ],
    'microservices': [
      'микросервис', 'сервис-ориентированн', 'разделение сервисов',
      'microservice', 'service-oriented', 'service decomposition'
    ],
    'integration_architecture': [
      'интеграционная архитектура', 'esb', 'api gateway', 'шина данных',
      'integration architecture', 'esb', 'api gateway', 'data bus'
    ],

    // Security patterns
    'security_analysis': [
      'безопасность', 'защита', 'аутентификац', 'авторизац', 'шифрование',
      'security', 'protection', 'authentication', 'authorization', 'encryption'
    ],
    'compliance': [
      'соответствие', 'стандарт', 'сертификац', 'аудит', 'rgpd', 'гост',
      'compliance', 'standard', 'certification', 'audit', 'gdpr'
    ]
  };

  /**
   * Analyze user query and determine the best matching category
   */
  static analyzeQuery(userQuery: string): AnalysisResult {
    if (!userQuery || typeof userQuery !== 'string') {
      return {
        category: 'unknown',
        confidence: 0,
        matches: []
      };
    }

    const normalizedQuery = TextAnalyzer.normalize(userQuery);
    const keywordMatches: PatternMatch[] = [];

    // Score each pattern category
    for (const [category, patterns] of Object.entries(this.patterns)) {
      for (const pattern of patterns) {
        const normalizedPattern = TextAnalyzer.normalize(pattern);
        if (normalizedQuery.includes(normalizedPattern)) {
          keywordMatches.push({
            pattern: pattern,
            weight: this.calculateWeight(normalizedPattern, normalizedQuery),
            category
          });
        }
      }
    }

    // Find best matching category
    const categoryScores = this.scoreCategories(keywordMatches);
    const bestMatch = this.getBestMatch(categoryScores);

    return {
      category: bestMatch.category,
      confidence: bestMatch.confidence,
      matches: keywordMatches.sort((a, b) => b.weight - a.weight),
      recommendedAction: this.getRecommendedAction(bestMatch.category)
    };
  }

  /**
   * Calculate weight of a pattern match
   */
  private static calculateWeight(pattern: string, query: string): number {
    // Exact phrase matches get higher weight
    if (query.includes(pattern)) {
      return pattern.split(' ').length * 2;
    }
    
    // Word matches get base weight
    return 1;
  }

  /**
   * Score categories based on matched patterns
   */
  private static scoreCategories(matches: PatternMatch[]): Record<string, { score: number; matchCount: number }> {
    const scores: Record<string, { score: number; matchCount: number }> = {};

    for (const match of matches) {
      if (!scores[match.category]) {
        scores[match.category] = { score: 0, matchCount: 0 };
      }
      scores[match.category].score += match.weight;
      scores[match.category].matchCount += 1;
    }

    return scores;
  }

  /**
   * Get the best matching category with confidence score
   */
  private static getBestMatch(scores: Record<string, { score: number; matchCount: number }>): { 
    category: string; 
    confidence: number 
  } {
    let bestCategory = 'general';
    let maxScore = 0;
    let totalMatches = 0;

    for (const [category, { score, matchCount }] of Object.entries(scores)) {
      totalMatches += matchCount;
      if (score > maxScore) {
        maxScore = score;
        bestCategory = category;
      }
    }

    // Calculate confidence as ratio of best score to total possible
    const confidence = totalMatches > 0 ? Math.min(maxScore / (totalMatches * 2), 1.0) : 0;

    return { category: bestCategory, confidence };
  }

  /**
   * Get recommended action based on category
   */
  private static getRecommendedAction(category: string): string {
    const actionMap: Record<string, string> = {
      '1c_integration': 'Создать план интеграции с 1С',
      'code_development': 'Сгенерировать код и архитектуру',
      'testing': 'Создать тест-кейсы и стратегию тестирования',
      'project_planning': 'Разработать план проекта',
      'requirements_analysis': 'Извлечь и структурировать требования',
      'system_architecture': 'Спроектировать системную архитектуру',
      'security_analysis': 'Провести анализ безопасности',
      'general': 'Выполнить общий анализ'
    };

    return actionMap[category] || actionMap['general'];
  }

  /**
   * Get all available categories
   */
  static getCategories(): string[] {
    return Object.keys(this.patterns);
  }

  /**
   * Get patterns for a specific category
   */
  static getPatternsForCategory(category: string): string[] {
    return this.patterns[category] || [];
  }

  /**
   * Add custom patterns
   */
  static addPatterns(category: string, patterns: string[]): void {
    if (!this.patterns[category]) {
      this.patterns[category] = [];
    }
    this.patterns[category].push(...patterns);
  }

  /**
   * Check if query matches any of the given patterns
   */
  static matchesAnyPattern(userQuery: string, patterns: string[]): boolean {
    return TextAnalyzer.matchesPatterns(userQuery, patterns);
  }

  /**
   * Find the best matching patterns for a query
   */
  static findBestPatterns(userQuery: string, limit: number = 5): PatternMatch[] {
    const analysis = this.analyzeQuery(userQuery);
    return analysis.matches.slice(0, limit);
  }
}