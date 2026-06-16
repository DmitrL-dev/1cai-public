/**
 * Сервис матрицы трассируемости для Business Analyst
 * Предоставляет возможности отслеживания связей между требованиями, тестами, компонентами и артефактами
 */

  // Генерация UUID с помощью Web Crypto API
  const generateUUID = (): string => {
    return crypto.randomUUID();
  };

export interface TraceabilityMatrix {
  id: string;
  name: string;
  description?: string;
  type: 'requirements-to-tests' | 'requirements-to-components' | 'requirements-to-artifacts' | 'custom';
  items: MatrixItem[];
  createdAt: Date;
  modifiedAt: Date;
}

export interface MatrixItem {
  id: string;
  sourceType: 'requirement' | 'test' | 'component' | 'artifact';
  sourceId: string;
  sourceName: string;
  targetType: 'requirement' | 'test' | 'component' | 'artifact';
  targetId: string;
  targetName: string;
  relationshipType: 'implements' | 'tests' | 'depends-on' | 'relates-to' | 'blocked-by' | 'supersedes';
  status: 'covered' | 'partial' | 'uncovered' | 'blocked';
  coverage: number; // 0-100
  notes?: string;
  lastReviewed?: Date;
}

export interface CoverageReport {
  matrixId: string;
  totalItems: number;
  coveragePercentage: number;
  coveredItems: number;
  partialItems: number;
  uncoveredItems: number;
  blockedItems: number;
  issues: CoverageIssue[];
  recommendations: string[];
}

export interface CoverageIssue {
  type: 'uncovered-requirement' | 'unmapped-test' | 'orphaned-component' | 'circular-dependency';
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  affectedItems: string[];
  suggestedAction: string;
}

export interface TraceabilityLink {
  id: string;
  from: {
    type: 'requirement' | 'test' | 'component' | 'artifact';
    id: string;
    name: string;
  };
  to: {
    type: 'requirement' | 'test' | 'component' | 'artifact';
    id: string;
    name: string;
  };
  relationship: string;
  strength: 'weak' | 'medium' | 'strong';
  confidence: number;
  createdBy: string;
  createdAt: Date;
  metadata?: Record<string, any>;
}

export class TraceabilityMatrixService {
  private matrices: Map<string, TraceabilityMatrix> = new Map();
  private links: Map<string, TraceabilityLink> = new Map();
  private coverageCache: Map<string, CoverageReport> = new Map();

  /**
   * Создать новую матрицу трассируемости
   */
  createMatrix(name: string, description?: string, type: string = 'custom'): string {
    const matrix: TraceabilityMatrix = {
      id: generateUUID(),
      name,
      description,
      type: type as any,
      items: [],
      createdAt: new Date(),
      modifiedAt: new Date()
    };

    this.matrices.set(matrix.id, matrix);
    return matrix.id;
  }

  /**
   * Получить матрицу по ID
   */
  getMatrix(matrixId: string): TraceabilityMatrix | undefined {
    return this.matrices.get(matrixId);
  }

  /**
   * Получить все матрицы
   */
  getAllMatrices(): TraceabilityMatrix[] {
    return Array.from(this.matrices.values());
  }

  /**
   * Обновить матрицу
   */
  updateMatrix(matrixId: string, updates: Partial<TraceabilityMatrix>): boolean {
    const matrix = this.matrices.get(matrixId);
    if (!matrix) return false;

    const updated = {
      ...matrix,
      ...updates,
      modifiedAt: new Date()
    };

    this.matrices.set(matrixId, updated);
    
    // Очищаем кэш отчетов
    this.coverageCache.delete(matrixId);
    
    return true;
  }

  /**
   * Удалить матрицу
   */
  deleteMatrix(matrixId: string): boolean {
    // Удаляем связанные элементы и ссылки
    const matrix = this.matrices.get(matrixId);
    if (matrix) {
      matrix.items.forEach(item => {
        this.deleteLink(item.id);
      });
    }

    return this.matrices.delete(matrixId);
  }

  /**
   * Добавить элемент в матрицу
   */
  addMatrixItem(
    matrixId: string,
    source: { type: string; id: string; name: string },
    target: { type: string; id: string; name: string },
    relationshipType: string,
    status: string = 'uncovered',
    coverage: number = 0
  ): string {
    const matrix = this.matrices.get(matrixId);
    if (!matrix) {
      throw new Error(`Матрица ${matrixId} не найдена`);
    }

    const item: MatrixItem = {
      id: generateUUID(),
      sourceType: source.type as any,
      sourceId: source.id,
      sourceName: source.name,
      targetType: target.type as any,
      targetId: target.id,
      targetName: target.name,
      relationshipType: relationshipType as any,
      status: status as any,
      coverage
    };

    matrix.items.push(item);
    matrix.modifiedAt = new Date();
    
    // Создаем связь трассируемости
    this.createLink(source, target, relationshipType, 'medium', 0.8);
    
    return item.id;
  }

  /**
   * Обновить элемент матрицы
   */
  updateMatrixItem(matrixId: string, itemId: string, updates: Partial<MatrixItem>): boolean {
    const matrix = this.matrices.get(matrixId);
    if (!matrix) return false;

    const itemIndex = matrix.items.findIndex(item => item.id === itemId);
    if (itemIndex === -1) return false;

    matrix.items[itemIndex] = {
      ...matrix.items[itemIndex],
      ...updates
    };

    matrix.modifiedAt = new Date();
    this.coverageCache.delete(matrixId);
    
    return true;
  }

  /**
   * Удалить элемент матрицы
   */
  deleteMatrixItem(matrixId: string, itemId: string): boolean {
    const matrix = this.matrices.get(matrixId);
    if (!matrix) return false;

    const item = matrix.items.find(item => item.id === itemId);
    if (item) {
      this.deleteLink(itemId);
    }

    matrix.items = matrix.items.filter(item => item.id !== itemId);
    matrix.modifiedAt = new Date();
    this.coverageCache.delete(matrixId);
    
    return true;
  }

  /**
   * Создать связь трассируемости
   */
  createLink(
    from: { type: string; id: string; name: string },
    to: { type: string; id: string; name: string },
    relationship: string,
    strength: string = 'medium',
    confidence: number = 0.5
  ): string {
    const link: TraceabilityLink = {
      id: generateUUID(),
      from,
      to,
      relationship,
      strength: strength as any,
      confidence,
      createdBy: 'system',
      createdAt: new Date()
    };

    this.links.set(link.id, link);
    return link.id;
  }

  /**
   * Удалить связь
   */
  deleteLink(linkId: string): boolean {
    return this.links.delete(linkId);
  }

  /**
   * Получить связи для элемента
   */
  getLinksForElement(elementType: string, elementId: string): TraceabilityLink[] {
    return Array.from(this.links.values()).filter(
      link => 
        (link.from.type === elementType && link.from.id === elementId) ||
        (link.to.type === elementType && link.to.id === elementId)
    );
  }

  /**
   * Генерировать отчет о покрытии
   */
  generateCoverageReport(matrixId: string): CoverageReport {
    const matrix = this.matrices.get(matrixId);
    if (!matrix) {
      throw new Error(`Матрица ${matrixId} не найдена`);
    }

    // Проверяем кэш
    if (this.coverageCache.has(matrixId)) {
      return this.coverageCache.get(matrixId)!;
    }

    const totalItems = matrix.items.length;
    const coveredItems = matrix.items.filter(item => item.status === 'covered').length;
    const partialItems = matrix.items.filter(item => item.status === 'partial').length;
    const uncoveredItems = matrix.items.filter(item => item.status === 'uncovered').length;
    const blockedItems = matrix.items.filter(item => item.status === 'blocked').length;

    const coveragePercentage = totalItems > 0 ? Math.round((coveredItems / totalItems) * 100) : 0;

    // Анализируем проблемы
    const issues: CoverageIssue[] = [];
    
    // Непокрытые требования
    const uncoveredRequirements = matrix.items.filter(item => 
      item.sourceType === 'requirement' && item.status === 'uncovered'
    );
    if (uncoveredRequirements.length > 0) {
      issues.push({
        type: 'uncovered-requirement',
        severity: uncoveredRequirements.length > 5 ? 'critical' : 'high',
        description: `Найдено ${uncoveredRequirements.length} непокрытых требований`,
        affectedItems: uncoveredRequirements.map(item => item.sourceName),
        suggestedAction: 'Создать тесты или компоненты для покрытия этих требований'
      });
    }

    // Неотображенные тесты
    const unmappedTests = matrix.items.filter(item => 
      item.targetType === 'test' && item.status === 'uncovered'
    );
    if (unmappedTests.length > 0) {
      issues.push({
        type: 'unmapped-test',
        severity: 'medium',
        description: `Найдено ${unmappedTests.length} тестов без связи с требованиями`,
        affectedItems: unmappedTests.map(item => item.targetName),
        suggestedAction: 'Определить требования, которые покрывают эти тесты'
      });
    }

    // Сиротские компоненты
    const orphanedComponents = matrix.items.filter(item => 
      item.targetType === 'component' && item.status === 'uncovered'
    );
    if (orphanedComponents.length > 0) {
      issues.push({
        type: 'orphaned-component',
        severity: 'medium',
        description: `Найдено ${orphanedComponents.length} компонентов без связи с требованиями`,
        affectedItems: orphanedComponents.map(item => item.targetName),
        suggestedAction: 'Проверить, нужны ли эти компоненты для реализации требований'
      });
    }

    // Циркулярные зависимости
    const circularDeps = this.detectCircularDependencies(matrixId);
    if (circularDeps.length > 0) {
      issues.push({
        type: 'circular-dependency',
        severity: 'high',
        description: `Обнаружено ${circularDeps.length} циркулярных зависимостей`,
        affectedItems: circularDeps.flat(),
        suggestedAction: 'Рефакторинг для устранения циркулярных зависимостей'
      });
    }

    // Генерируем рекомендации
    const recommendations: string[] = [];
    
    if (coveragePercentage < 50) {
      recommendations.push('Низкий процент покрытия. Увеличить количество тестов или связей.');
    } else if (coveragePercentage < 80) {
      recommendations.push('Умеренное покрытие. Рассмотреть добавление недостающих связей.');
    } else {
      recommendations.push('Хороший уровень покрытия. Поддерживать актуальность связей.');
    }

    if (issues.length > 0) {
      recommendations.push('Необходимо решить выявленные проблемы трассируемости.');
    }

    const report: CoverageReport = {
      matrixId,
      totalItems,
      coveragePercentage,
      coveredItems,
      partialItems,
      uncoveredItems,
      blockedItems,
      issues,
      recommendations
    };

    // Кэшируем отчет
    this.coverageCache.set(matrixId, report);
    
    return report;
  }

  /**
   * Обнаружение циркулярных зависимостей
   */
  private detectCircularDependencies(matrixId: string): string[][] {
    const matrix = this.matrices.get(matrixId);
    if (!matrix) return [];

    // Строим граф зависимостей
    const graph = new Map<string, string[]>();
    
    matrix.items.forEach(item => {
      if (item.relationshipType === 'depends-on' || item.relationshipType === 'blocked-by') {
        if (!graph.has(item.sourceId)) {
          graph.set(item.sourceId, []);
        }
        graph.get(item.sourceId)!.push(item.targetId);
      }
    });

    // DFS для поиска циклов
    const visited = new Set<string>();
    const recursionStack = new Set<string>();
    const cycles: string[][] = [];

    const dfs = (node: string, path: string[]): void => {
      if (recursionStack.has(node)) {
        // Найден цикл
        const cycleStart = path.indexOf(node);
        if (cycleStart !== -1) {
          cycles.push([...path.slice(cycleStart), node]);
        }
        return;
      }

      if (visited.has(node)) return;

      visited.add(node);
      recursionStack.add(node);
      const newPath = [...path, node];

      const neighbors = graph.get(node) || [];
      neighbors.forEach(neighbor => {
        dfs(neighbor, newPath);
      });

      recursionStack.delete(node);
    };

    graph.forEach((_, node) => {
      if (!visited.has(node)) {
        dfs(node, []);
      }
    });

    return cycles;
  }

  /**
   * Создать автоматически матрицу требований к тестам
   */
  createRequirementsToTestsMatrix(requirements: any[], tests: any[]): string {
    const matrixId = this.createMatrix(
      'Матрица требований к тестам',
      'Автоматически созданная матрица трассируемости между требованиями и тестами',
      'requirements-to-tests'
    );

    requirements.forEach(req => {
      const reqTests = tests.filter(test => 
        test.name.toLowerCase().includes(req.title.toLowerCase()) ||
        test.description.toLowerCase().includes(req.title.toLowerCase())
      );

      if (reqTests.length > 0) {
        reqTests.forEach(test => {
          this.addMatrixItem(
            matrixId,
            { type: 'requirement', id: req.id, name: req.title },
            { type: 'test', id: test.id, name: test.name },
            'tests',
            'covered',
            100
          );
        });
      } else {
        // Требование не покрыто тестами
        this.addMatrixItem(
          matrixId,
          { type: 'requirement', id: req.id, name: req.title },
          { type: 'test', id: 'none', name: 'Не покрыто' },
          'tests',
          'uncovered',
          0
        );
      }
    });

    return matrixId;
  }

  /**
   * Создать матрицу требований к компонентам
   */
  createRequirementsToComponentsMatrix(requirements: any[], components: any[]): string {
    const matrixId = this.createMatrix(
      'Матрица требований к компонентам',
      'Автоматически созданная матрица трассируемости между требованиями и компонентами системы',
      'requirements-to-components'
    );

    requirements.forEach(req => {
      const relatedComponents = components.filter(component => 
        component.name.toLowerCase().includes(req.title.toLowerCase()) ||
        component.description?.toLowerCase().includes(req.title.toLowerCase()) ||
        req.description?.toLowerCase().includes(component.name.toLowerCase())
      );

      if (relatedComponents.length > 0) {
        relatedComponents.forEach(component => {
          this.addMatrixItem(
            matrixId,
            { type: 'requirement', id: req.id, name: req.title },
            { type: 'component', id: component.id, name: component.name },
            'implements',
            'covered',
            100
          );
        });
      } else {
        // Требование не реализовано компонентами
        this.addMatrixItem(
          matrixId,
          { type: 'requirement', id: req.id, name: req.title },
          { type: 'component', id: 'none', name: 'Не реализовано' },
          'implements',
          'uncovered',
          0
        );
      }
    });

    return matrixId;
  }

  /**
   * Валидация матрицы
   */
  validateMatrix(matrixId: string): { isValid: boolean; errors: string[]; warnings: string[] } {
    const matrix = this.matrices.get(matrixId);
    if (!matrix) {
      return { isValid: false, errors: [`Матрица ${matrixId} не найдена`], warnings: [] };
    }

    const errors: string[] = [];
    const warnings: string[] = [];

    // Проверяем наличие элементов
    if (matrix.items.length === 0) {
      warnings.push('Матрица не содержит элементов');
    }

    // Проверяем дубликаты
    const seen = new Set<string>();
    matrix.items.forEach(item => {
      const key = `${item.sourceId}-${item.targetId}-${item.relationshipType}`;
      if (seen.has(key)) {
        errors.push(`Дубликат связи: ${item.sourceName} -> ${item.targetName}`);
      }
      seen.add(key);
    });

    // Проверяем покрытие
    const uncoveredCount = matrix.items.filter(item => item.status === 'uncovered').length;
    if (uncoveredCount > matrix.items.length * 0.3) {
      warnings.push(`Высокий процент непокрытых элементов: ${Math.round((uncoveredCount / matrix.items.length) * 100)}%`);
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings
    };
  }

  /**
   * Экспорт матрицы в различные форматы
   */
  exportToExcel(matrixId: string): string {
    const matrix = this.matrices.get(matrixId);
    if (!matrix) {
      throw new Error(`Матрица ${matrixId} не найдена`);
    }

    // Генерируем CSV данные (можно легко импортировать в Excel)
    let csv = 'Источник,Тип источника,Цель,Тип цели,Отношение,Статус,Покрытие,Примечания\n';
    
    matrix.items.forEach(item => {
      csv += `"${item.sourceName}","${item.sourceType}","${item.targetName}","${item.targetType}","${item.relationshipType}","${item.status}","${item.coverage}%","${item.notes || ''}"\n`;
    });

    return csv;
  }

  exportToJSON(matrixId: string): string {
    const matrix = this.matrices.get(matrixId);
    if (!matrix) {
      throw new Error(`Матрица ${matrixId} не найдена`);
    }

    return JSON.stringify(matrix, null, 2);
  }

  exportToDOT(matrixId: string): string {
    const matrix = this.matrices.get(matrixId);
    if (!matrix) {
      throw new Error(`Матрица ${matrixId} не найдена`);
    }

    let dot = `digraph TraceabilityMatrix_${matrixId} {\n`;
    dot += '  rankdir=LR;\n';
    dot += '  node [shape=box];\n\n';

    matrix.items.forEach(item => {
      const sourceNode = `req_${item.sourceId}`;
      const targetNode = `test_${item.targetId}`;
      
      // Создаем узлы
      dot += `  ${sourceNode} [label="${item.sourceName}" style=filled fillcolor=lightblue];\n`;
      dot += `  ${targetNode} [label="${item.targetName}" style=filled fillcolor=lightgreen];\n`;
      
      // Создаем связь
      const color = item.status === 'covered' ? 'green' : 
                   item.status === 'partial' ? 'orange' : 'red';
      dot += `  ${sourceNode} -> ${targetNode} [label="${item.relationshipType}" color=${color}];\n\n`;
    });

    dot += '}';
    return dot;
  }

  /**
   * Получение статистики сервиса
   */
  getServiceStatistics(): {
    totalMatrices: number;
    totalItems: number;
    totalLinks: number;
    averageCoverage: number;
    matricesByType: Record<string, number>;
  } {
    const matrices = this.getAllMatrices();
    const totalItems = matrices.reduce((sum, matrix) => sum + matrix.items.length, 0);
    
    const coveredItems = matrices.reduce((sum, matrix) => 
      sum + matrix.items.filter(item => item.status === 'covered').length, 0
    );

    const matricesByType: Record<string, number> = {};
    matrices.forEach(matrix => {
      matricesByType[matrix.type] = (matricesByType[matrix.type] || 0) + 1;
    });

    return {
      totalMatrices: matrices.length,
      totalItems,
      totalLinks: this.links.size,
      averageCoverage: totalItems > 0 ? Math.round((coveredItems / totalItems) * 100) : 0,
      matricesByType
    };
  }

  /**
   * Поиск по матрицам
   */
  searchMatrices(query: string): TraceabilityMatrix[] {
    const searchTerm = query.toLowerCase();
    return this.getAllMatrices().filter(matrix => 
      matrix.name.toLowerCase().includes(searchTerm) ||
      matrix.description?.toLowerCase().includes(searchTerm) ||
      matrix.type.toLowerCase().includes(searchTerm)
    );
  }

  /**
   * Получение матриц по типу
   */
  getMatricesByType(type: string): TraceabilityMatrix[] {
    return this.getAllMatrices().filter(matrix => matrix.type === type);
  }
}

// Экспортируем экземпляр сервиса
export const traceabilityMatrixService = new TraceabilityMatrixService();