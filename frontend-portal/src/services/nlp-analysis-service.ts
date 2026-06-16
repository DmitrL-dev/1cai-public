/**
 * Сервис NLP анализа требований для Business Analyst
 * Предоставляет возможности анализа и структурирования текстовых требований 1C проектов
 */

  // Генерация UUID с помощью Web Crypto API
  const generateUUID = (): string => {
    return crypto.randomUUID();
  };

export interface Requirement {
  id: string;
  title: string;
  description: string;
  type: 'functional' | 'non-functional' | 'business' | 'technical';
  priority: 'must-have' | 'should-have' | 'could-have' | 'wont-have';
  complexity: 'low' | 'medium' | 'high';
  status: 'draft' | 'analyzed' | 'approved' | 'implemented';
  tags: string[];
  entities: Entity[];
  relationships: Relationship[];
  acceptanceCriteria: string[];
  dependencies: string[];
  estimatedEffort?: number; // в часах
  businessValue: number; // 1-10
  riskLevel: 'low' | 'medium' | 'high';
  createdAt: Date;
  modifiedAt: Date;
}

export interface Entity {
  id: string;
  type: 'document' | 'reference' | 'user' | 'process' | 'report' | 'form' | 'integration';
  name: string;
  description: string;
  attributes: string[];
}

export interface Relationship {
  id: string;
  sourceEntityId: string;
  targetEntityId: string;
  type: 'uses' | 'creates' | 'updates' | 'reads' | 'validates';
  description: string;
  strength: 'weak' | 'medium' | 'strong';
}

export interface AnalysisResult {
  requirementId: string;
  summary: string;
  entities: Entity[];
  relationships: Relationship[];
  risks: Risk[];
  suggestions: Suggestion[];
  metadata: {
    confidence: number;
    processingTime: number;
    language: string;
    keyPhrases: string[];
  };
}

export interface Risk {
  id: string;
  type: 'technical' | 'business' | 'compliance' | 'integration';
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  probability: number; // 0-1
  impact: number; // 1-10
  mitigation: string;
}

export interface Suggestion {
  id: string;
  category: 'optimization' | 'implementation' | 'testing' | 'documentation';
  title: string;
  description: string;
  priority: 'low' | 'medium' | 'high';
  effort: 'low' | 'medium' | 'high';
  benefits: string[];
}

export class NLPAnalysisService {
  private requirements: Map<string, Requirement> = new Map();
  private analysisCache: Map<string, AnalysisResult> = new Map();

  // Ключевые слова для 1C домена
  private readonly c1cKeywords = {
    documents: [
      'документ', 'поступление', 'реализация', 'счет-фактура', 'накладная',
      'платежное поручение', 'приходный кассовый ордер', 'расходный кассовый ордер',
      'ведомость', 'отчет', 'акт', 'товарная накладная'
    ],
    references: [
      'справочник', 'номенклатура', 'контрагенты', 'сотрудники', 'должности',
      'подразделения', 'склады', 'договоры', 'банки', 'валюты'
    ],
    processes: [
      'заказ', 'продажа', 'покупка', 'инвентаризация', 'перемещение',
      'списание', 'оприходование', 'корректировка', 'возврат'
    ],
    integrations: [
      'обмен', 'синхронизация', 'интеграция', 'веб-сервис', 'API',
      'COM', 'OLE', 'файл обмена', 'план обмена'
    ]
  };

  // Паттерны для извлечения сущностей
  private readonly entityPatterns = {
    document: /(\w+(?:\s+\w+)*)\s+(?:документ|форма|обработка|отчет)/i,
    reference: /справочник\s+(\w+(?:\s+\w+)*)/i,
    user: /(?:пользователь|менеджер|оператор|администратор|бухгалтер)\s+(\w+)/i,
    process: /(?:процесс|операция|действие)\s+(\w+(?:\s+\w+)*)/i,
    integration: /(?:обмен|синхронизация|интеграция)\s+(?:с\s+)?(\w+(?:\s+\w+)*)/i
  };

  /**
   * Добавить новое требование
   */
  addRequirement(requirement: Omit<Requirement, 'id' | 'createdAt' | 'modifiedAt'>): string {
    const id = generateUUID();
    const now = new Date();
    
    const newRequirement: Requirement = {
      ...requirement,
      id,
      createdAt: now,
      modifiedAt: now
    };

    this.requirements.set(id, newRequirement);
    return id;
  }

  /**
   * Обновить требование
   */
  updateRequirement(id: string, updates: Partial<Requirement>): boolean {
    const requirement = this.requirements.get(id);
    if (!requirement) return false;

    const updated = {
      ...requirement,
      ...updates,
      modifiedAt: new Date()
    };

    this.requirements.set(id, updated);
    
    // Очищаем кэш анализа
    this.analysisCache.delete(id);
    
    return true;
  }

  /**
   * Удалить требование
   */
  deleteRequirement(id: string): boolean {
    return this.requirements.delete(id);
  }

  /**
   * Получить требование по ID
   */
  getRequirement(id: string): Requirement | undefined {
    return this.requirements.get(id);
  }

  /**
   * Получить все требования
   */
  getAllRequirements(): Requirement[] {
    return Array.from(this.requirements.values());
  }

  /**
   * Основной метод анализа требования
   */
  async analyzeRequirement(requirementId: string): Promise<AnalysisResult | null> {
    const requirement = this.requirements.get(requirementId);
    if (!requirement) return null;

    // Проверяем кэш
    const cacheKey = this.getCacheKey(requirement);
    if (this.analysisCache.has(cacheKey)) {
      return this.analysisCache.get(cacheKey)!;
    }

    const startTime = Date.now();
    
    try {
      // Анализ текста
      const analysis = await this.performTextAnalysis(requirement);
      
      // Извлечение сущностей
      const entities = this.extractEntities(requirement.description);
      
      // Анализ отношений
      const relationships = this.analyzeRelationships(entities, requirement.description);
      
      // Выявление рисков
      const risks = this.identifyRisks(requirement, entities);
      
      // Генерация предложений
      const suggestions = this.generateSuggestions(requirement, entities, relationships);

      const result: AnalysisResult = {
        requirementId,
        summary: analysis.summary,
        entities,
        relationships,
        risks,
        suggestions,
        metadata: {
          confidence: analysis.confidence,
          processingTime: Date.now() - startTime,
          language: 'ru',
          keyPhrases: analysis.keyPhrases
        }
      };

      // Кэшируем результат
      this.analysisCache.set(cacheKey, result);
      
      return result;
    } catch (error) {
      console.error('Ошибка анализа требования:', error);
      return null;
    }
  }

  /**
   * Анализ текста требования
   */
  private async performTextAnalysis(requirement: Requirement): Promise<{
    summary: string;
    confidence: number;
    keyPhrases: string[];
  }> {
    const { description } = requirement;
    
    // Извлечение ключевых фраз
    const keyPhrases = this.extractKeyPhrases(description);
    
    // Генерация краткого изложения
    const summary = this.generateSummary(description, keyPhrases);
    
    // Оценка уверенности анализа
    const confidence = this.calculateConfidence(description, keyPhrases);

    return {
      summary,
      confidence,
      keyPhrases
    };
  }

  /**
   * Извлечение ключевых фраз из текста
   */
  private extractKeyPhrases(text: string): string[] {
    const phrases: string[] = [];
    
    // Ищем ключевые слова 1C
    Object.values(this.c1cKeywords).flat().forEach(keyword => {
      const regex = new RegExp(`\\b${keyword}\\b`, 'gi');
      const matches = text.match(regex);
      if (matches) {
        phrases.push(...matches);
      }
    });

    // Ищем глаголы действия
    const actionVerbs = [
      'создать', 'сформировать', 'заполнить', 'провести', 'отменить',
      'рассчитать', 'обновить', 'удалить', 'экспортировать', 'импортировать',
      'синхронизировать', 'проверить', 'валидировать', 'отправить', 'получить'
    ];

    actionVerbs.forEach(verb => {
      const regex = new RegExp(`\\b${verb}\\b`, 'gi');
      const matches = text.match(regex);
      if (matches) {
        phrases.push(...matches.map(match => `${match} (действие)`));
      }
    });

    // Убираем дубликаты и возвращаем уникальные
    return [...new Set(phrases)];
  }

  /**
   * Генерация краткого изложения
   */
  private generateSummary(text: string, keyPhrases: string[]): string {
    // Простое извлечение предложений
    const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 0);
    
    if (sentences.length === 0) return 'Краткое изложение недоступно';
    if (sentences.length === 1) return sentences[0].trim();

    // Берем первое предложение как основу
    let summary = sentences[0].trim();
    
    // Добавляем второе предложение, если оно короткое
    if (sentences.length > 1 && sentences[1].length < 100) {
      summary += '. ' + sentences[1].trim();
    }

    // Добавляем контекст из ключевых фраз
    const relevantPhrases = keyPhrases.slice(0, 3).join(', ');
    if (relevantPhrases) {
      summary += ` Основные элементы: ${relevantPhrases}.`;
    }

    return summary;
  }

  /**
   * Расчет уверенности анализа
   */
  private calculateConfidence(text: string, keyPhrases: string[]): number {
    let confidence = 0.5; // базовая уверенность

    // Увеличиваем за счет длины текста
    const textLength = text.length;
    if (textLength > 100) confidence += 0.1;
    if (textLength > 300) confidence += 0.1;
    if (textLength > 500) confidence += 0.1;

    // Увеличиваем за счет количества ключевых фраз
    const keyPhraseRatio = keyPhrases.length / textLength;
    if (keyPhraseRatio > 0.02) confidence += 0.2;
    if (keyPhraseRatio > 0.05) confidence += 0.1;

    // Уменьшаем за короткие тексты
    if (textLength < 50) confidence -= 0.2;

    return Math.max(0.1, Math.min(1.0, confidence));
  }

  /**
   * Извлечение сущностей из текста
   */
  private extractEntities(text: string): Entity[] {
    const entities: Entity[] = [];

    // Анализируем каждый тип сущности
    Object.entries(this.entityPatterns).forEach(([type, pattern]) => {
      const matches = text.match(new RegExp(pattern, 'gi'));
      if (matches) {
        matches.forEach(match => {
          const name = match.replace(pattern, '$1').trim();
          if (name && name.length > 1) {
            const entity: Entity = {
              id: generateUUID(),
              type: type as any,
              name: this.capitalizeFirst(name),
              description: `Извлечено из требования: ${match}`,
              attributes: this.extractAttributes(text, name)
            };
            entities.push(entity);
          }
        });
      }
    });

    return this.removeDuplicateEntities(entities);
  }

  /**
   * Извлечение атрибутов для сущности
   */
  private extractAttributes(text: string, entityName: string): string[] {
    const attributes: string[] = [];
    const entityRegex = new RegExp(entityName, 'gi');
    
    // Ищем предложения с упоминанием сущности
    const sentences = text.split(/[.!?]+/);
    sentences.forEach(sentence => {
      if (entityRegex.test(sentence)) {
        // Ищем паттерны атрибутов
        const attrPatterns = [
          /(\w+)\s*=\s*([^,.;]+)/g,
          /(\w+)\s+(\w+)/g,
          /номер\s+(\w+)/g,
          /код\s+(\w+)/g,
          /наименование\s+(\w+)/g
        ];
        
        attrPatterns.forEach(pattern => {
          const matches = sentence.match(pattern);
          if (matches) {
            attributes.push(...matches.map(m => m.trim()));
          }
        });
      }
    });

    return [...new Set(attributes)].slice(0, 5); // Ограничиваем количество
  }

  /**
   * Удаление дублирующихся сущностей
   */
  private removeDuplicateEntities(entities: Entity[]): Entity[] {
    const unique: Entity[] = [];
    const seen = new Set<string>();

    entities.forEach(entity => {
      const key = `${entity.type}:${entity.name.toLowerCase()}`;
      if (!seen.has(key)) {
        seen.add(key);
        unique.push(entity);
      }
    });

    return unique;
  }

  /**
   * Анализ отношений между сущностями
   */
  private analyzeRelationships(entities: Entity[], text: string): Relationship[] {
    const relationships: Relationship[] = [];
    const sentences = text.split(/[.!?]+/);

    entities.forEach(sourceEntity => {
      entities.forEach(targetEntity => {
        if (sourceEntity.id === targetEntity.id) return;

        // Ищем паттерны отношений в предложениях
        sentences.forEach(sentence => {
          const sourceInSentence = new RegExp(sourceEntity.name, 'i').test(sentence);
          const targetInSentence = new RegExp(targetEntity.name, 'i').test(sentence);

          if (sourceInSentence && targetInSentence) {
            const relationship = this.extractRelationship(sentence, sourceEntity, targetEntity);
            if (relationship) {
              relationships.push(relationship);
            }
          }
        });
      });
    });

    return this.removeDuplicateRelationships(relationships);
  }

  /**
   * Извлечение типа отношения из предложения
   */
  private extractRelationship(sentence: string, source: Entity, target: Entity): Relationship | null {
    const sentence_lower = sentence.toLowerCase();
    
    let type: 'uses' | 'creates' | 'updates' | 'reads' | 'validates' = 'uses';
    let strength: 'weak' | 'medium' | 'strong' = 'medium';

    // Определяем тип отношения по ключевым словам
    if (sentence_lower.includes('созда') || sentence_lower.includes('формиру')) {
      type = 'creates';
      strength = 'strong';
    } else if (sentence_lower.includes('обновля') || sentence_lower.includes('изменя')) {
      type = 'updates';
      strength = 'strong';
    } else if (sentence_lower.includes('читает') || sentence_lower.includes('получа')) {
      type = 'reads';
      strength = 'medium';
    } else if (sentence_lower.includes('проверя') || sentence_lower.includes('валидир')) {
      type = 'validates';
      strength = 'weak';
    }

    return {
      id: generateUUID(),
      sourceEntityId: source.id,
      targetEntityId: target.id,
      type,
      description: `Отношение из предложения: ${sentence.trim()}`,
      strength
    };
  }

  /**
   * Удаление дублирующихся отношений
   */
  private removeDuplicateRelationships(relationships: Relationship[]): Relationship[] {
    const unique: Relationship[] = [];
    const seen = new Set<string>();

    relationships.forEach(rel => {
      const key = `${rel.sourceEntityId}:${rel.targetEntityId}:${rel.type}`;
      if (!seen.has(key)) {
        seen.add(key);
        unique.push(rel);
      }
    });

    return unique;
  }

  /**
   * Выявление рисков
   */
  private identifyRisks(requirement: Requirement, entities: Entity[]): Risk[] {
    const risks: Risk[] = [];
    
    // Анализируем риски на основе типа требования
    if (requirement.type === 'technical') {
      risks.push({
        id: generateUUID(),
        type: 'technical',
        description: 'Техническая сложность реализации',
        severity: requirement.complexity === 'high' ? 'high' : 'medium',
        probability: requirement.complexity === 'high' ? 0.7 : 0.4,
        impact: requirement.businessValue,
        mitigation: 'Провести техническое исследование и создать прототип'
      });
    }

    // Анализируем интеграционные риски
    const integrationEntities = entities.filter(e => e.type === 'integration');
    if (integrationEntities.length > 0) {
      risks.push({
        id: generateUUID(),
        type: 'integration',
        description: 'Риски интеграции с внешними системами',
        severity: 'medium',
        probability: 0.5,
        impact: 7,
        mitigation: 'Провести тестирование интеграции на ранних этапах'
      });
    }

    // Анализируем риски документооборота
    const documentEntities = entities.filter(e => e.type === 'document');
    if (documentEntities.length > 3) {
      risks.push({
        id: generateUUID(),
        type: 'business',
        description: 'Сложность документооборота',
        severity: 'medium',
        probability: 0.6,
        impact: 6,
        mitigation: 'Упростить бизнес-процессы и автоматизировать операции'
      });
    }

    return risks;
  }

  /**
   * Генерация предложений
   */
  private generateSuggestions(requirement: Requirement, entities: Entity[], relationships: Relationship[]): Suggestion[] {
    const suggestions: Suggestion[] = [];

    // Предложения по оптимизации
    if (entities.length > 5) {
      suggestions.push({
        id: generateUUID(),
        category: 'optimization',
        title: 'Рассмотреть декомпозицию требования',
        description: 'Большое количество сущностей указывает на сложность. Рекомендуется разбить на более мелкие требования.',
        priority: 'medium',
        effort: 'medium',
        benefits: ['Упрощение разработки', 'Лучшее тестирование', 'Повышение качества']
      });
    }

    // Предложения по тестированию
    const integrationEntities = entities.filter(e => e.type === 'integration');
    if (integrationEntities.length > 0) {
      suggestions.push({
        id: generateUUID(),
        category: 'testing',
        title: 'План тестирования интеграции',
        description: 'Создать детальный план тестирования интеграционных компонентов',
        priority: 'high',
        effort: 'high',
        benefits: ['Выявление проблем на ранних этапах', 'Повышение надежности']
      });
    }

    // Предложения по документации
    suggestions.push({
      id: generateUUID(),
      category: 'documentation',
      title: 'Создание технической документации',
      description: 'Документировать архитектуру и взаимодействие компонентов',
      priority: 'medium',
      effort: 'medium',
      benefits: ['Упрощение сопровождения', 'Обучение команды']
    });

    return suggestions;
  }

  /**
   * Пакетный анализ требований
   */
  async analyzeRequirementsBatch(requirementIds: string[]): Promise<Map<string, AnalysisResult>> {
    const results = new Map<string, AnalysisResult>();
    
    // Анализируем требования параллельно
    const promises = requirementIds.map(async id => {
      const result = await this.analyzeRequirement(id);
      return { id, result };
    });

    const analyses = await Promise.all(promises);
    
    analyses.forEach(({ id, result }) => {
      if (result) {
        results.set(id, result);
      }
    });

    return results;
  }

  /**
   * Генерация отчета по требованиям
   */
  generateRequirementsReport(): {
    total: number;
    byType: Record<string, number>;
    byPriority: Record<string, number>;
    byStatus: Record<string, number>;
    averageBusinessValue: number;
    highRiskCount: number;
    suggestionsCount: number;
  } {
    const requirements = this.getAllRequirements();
    const analysisPromises = requirements.map(req => this.analyzeRequirement(req.id));
    
    // В реальном приложении здесь был бы await, но для демо используем синхронный подход
    const analysisResults = requirements.map(req => this.analysisCache.get(this.getCacheKey(req))).filter(Boolean);

    const report = {
      total: requirements.length,
      byType: {} as Record<string, number>,
      byPriority: {} as Record<string, number>,
      byStatus: {} as Record<string, number>,
      averageBusinessValue: 0,
      highRiskCount: 0,
      suggestionsCount: 0
    };

    // Подсчет по типам
    requirements.forEach(req => {
      report.byType[req.type] = (report.byType[req.type] || 0) + 1;
      report.byPriority[req.priority] = (report.byPriority[req.priority] || 0) + 1;
      report.byStatus[req.status] = (report.byStatus[req.status] || 0) + 1;
    });

    // Средняя бизнес-ценность
    const totalBusinessValue = requirements.reduce((sum, req) => sum + req.businessValue, 0);
    report.averageBusinessValue = requirements.length > 0 ? totalBusinessValue / requirements.length : 0;

    // Подсчет рисков и предложений
    analysisResults.forEach(result => {
      if (result) {
        report.highRiskCount += result.risks.filter(r => r.severity === 'high' || r.severity === 'critical').length;
        report.suggestionsCount += result.suggestions.length;
      }
    });

    return report;
  }

  /**
   * Вспомогательные методы
   */
  private getCacheKey(requirement: Requirement): string {
    return `${requirement.id}:${requirement.description.length}:${requirement.modifiedAt.getTime()}`;
  }

  private capitalizeFirst(str: string): string {
    if (!str || str.length === 0) return str;
    return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
  }

  /**
   * Экспорт данных
   */
  exportToJSON(): string {
    const data = {
      requirements: this.getAllRequirements(),
      analysisResults: Array.from(this.analysisCache.entries()),
      exportedAt: new Date().toISOString()
    };
    return JSON.stringify(data, null, 2);
  }

  /**
   * Импорт данных
   */
  importFromJSON(jsonData: string): boolean {
    try {
      const data = JSON.parse(jsonData);
      if (data.requirements && Array.isArray(data.requirements)) {
        data.requirements.forEach((req: any) => {
          if (req.id) {
            this.requirements.set(req.id, req);
          }
        });
        return true;
      }
      return false;
    } catch (error) {
      console.error('Ошибка импорта данных:', error);
      return false;
    }
  }

  /**
   * Получение статистики сервиса
   */
  getServiceStatistics(): {
    totalRequirements: number;
    totalAnalyses: number;
    cacheSize: number;
    averageAnalysisTime: number;
  } {
    const analyses = Array.from(this.analysisCache.values());
    const totalAnalysisTime = analyses.reduce((sum, analysis) => sum + analysis.metadata.processingTime, 0);
    
    return {
      totalRequirements: this.requirements.size,
      totalAnalyses: this.analysisCache.size,
      cacheSize: this.analysisCache.size,
      averageAnalysisTime: analyses.length > 0 ? totalAnalysisTime / analyses.length : 0
    };
  }
}

// Экспортируем экземпляр сервиса
export const nlpAnalysisService = new NLPAnalysisService();