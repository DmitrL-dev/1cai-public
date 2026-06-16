/**
 * Сервис ROI калькулятора для Business Analyst
 * Предоставляет возможности расчета экономической эффективности проектов и функций 1C
 */

  // Генерация UUID с помощью Web Crypto API
  const generateUUID = (): string => {
    return crypto.randomUUID();
  };

export interface ROIProject {
  id: string;
  name: string;
  description?: string;
  category: 'automation' | 'integration' | 'reporting' | 'user-interface' | 'data-management' | 'custom';
  priority: 'low' | 'medium' | 'high' | 'critical';
  status: 'planning' | 'analysis' | 'development' | 'testing' | 'deployed' | 'completed';
  
  // Финансовые показатели
  developmentCost: number; // Стоимость разработки
  implementationCost: number; // Стоимость внедрения
  maintenanceCost: number; // Стоимость сопровождения (в год)
  
  // Экономические выгоды
  timeSavings: {
    hoursPerTransaction: number; // Экономия времени на одну операцию
    transactionsPerMonth: number; // Количество операций в месяц
    hourlyRate: number; // Стоимость часа работы
  };
  
  costReduction: {
    description: string;
    amount: number; // Сумма экономии в месяц
    frequency: 'monthly' | 'quarterly' | 'yearly';
  }[];
  
  revenueIncrease: {
    description: string;
    amount: number; // Дополнительная выручка в месяц
    frequency: 'monthly' | 'quarterly' | 'yearly';
  }[];
  
  riskReduction: {
    description: string;
    riskValue: number; // Стоимость риска
    probability: number; // Вероятность возникновения (0-1)
    reduction: number; // Процент снижения риска (0-1)
  }[];
  
  // Дополнительные параметры
  implementationPeriod: number; // Период внедрения в месяцах
  paybackPeriod?: number; // Период окупаемости в месяцах
  riskLevel: 'low' | 'medium' | 'high';
  
  // Метаданные
  createdAt: Date;
  modifiedAt: Date;
  createdBy: string;
  approvedBy?: string;
  notes?: string;
}

export interface ROICalculation {
  projectId: string;
  calculationDate: Date;
  
  // Основные показатели
  totalInvestment: number;
  totalBenefits: number;
  netPresentValue: number;
  roiPercentage: number;
  paybackPeriod: number;
  
  // Детальные расчеты
  annualBenefits: number;
  netCashFlow: number[];
  cumulativeCashFlow: number[];
  breakEvenPoint: number;
  
  // Анализ рисков
  riskAdjustedROI: number;
  scenarioAnalysis: {
    optimistic: number;
    realistic: number;
    pessimistic: number;
  };
  
  // Показатели эффективности
  efficiencyRatios: {
    benefitCostRatio: number;
    profitabilityIndex: number;
    internalRateOfReturn: number;
  };
}

export interface ROIScenario {
  id: string;
  name: string;
  description: string;
  parameters: {
    discountRate: number; // Ставка дисконтирования
    timeHorizon: number; // Горизонт планирования в годах
    inflationRate: number; // Уровень инфляции
    riskMultiplier: number; // Мультипликатор риска
  };
  projects: string[]; // ID проектов в сценарии
  totalROI: number;
  totalInvestment: number;
  totalBenefits: number;
  recommended: boolean;
}

export class ROICalculatorService {
  private projects: Map<string, ROIProject> = new Map();
  private calculations: Map<string, ROICalculation> = new Map();
  private scenarios: Map<string, ROIScenario> = new Map();
  
  // Константы для расчетов
  private readonly DEFAULT_DISCOUNT_RATE = 0.10; // 10% ставка дисконтирования
  private readonly DEFAULT_TIME_HORIZON = 3; // 3 года
  private readonly MONTHS_PER_YEAR = 12;

  /**
   * Создать новый ROI проект
   */
  createProject(project: Omit<ROIProject, 'id' | 'createdAt' | 'modifiedAt'>): string {
    const id = generateUUID();
    const now = new Date();
    
    const newProject: ROIProject = {
      ...project,
      id,
      createdAt: now,
      modifiedAt: now
    };

    this.projects.set(id, newProject);
    return id;
  }

  /**
   * Получить проект по ID
   */
  getProject(projectId: string): ROIProject | undefined {
    return this.projects.get(projectId);
  }

  /**
   * Получить все проекты
   */
  getAllProjects(): ROIProject[] {
    return Array.from(this.projects.values());
  }

  /**
   * Обновить проект
   */
  updateProject(projectId: string, updates: Partial<ROIProject>): boolean {
    const project = this.projects.get(projectId);
    if (!project) return false;

    const updated = {
      ...project,
      ...updates,
      modifiedAt: new Date()
    };

    this.projects.set(projectId, updated);
    
    // Очищаем кэш расчетов для этого проекта
    this.calculations.delete(projectId);
    
    return true;
  }

  /**
   * Удалить проект
   */
  deleteProject(projectId: string): boolean {
    this.calculations.delete(projectId);
    return this.projects.delete(projectId);
  }

  /**
   * Расчет ROI для проекта
   */
  calculateROI(projectId: string, parameters?: {
    discountRate?: number;
    timeHorizon?: number;
  }): ROICalculation | null {
    const project = this.projects.get(projectId);
    if (!project) return null;

    const discountRate = parameters?.discountRate || this.DEFAULT_DISCOUNT_RATE;
    const timeHorizon = parameters?.timeHorizon || this.DEFAULT_TIME_HORIZON;
    
    // Базовые инвестиции
    const totalInvestment = project.developmentCost + project.implementationCost;
    
    // Расчет ежегодных выгод
    const annualBenefits = this.calculateAnnualBenefits(project);
    
    // Денежные потоки по годам
    const netCashFlow: number[] = [];
    const cumulativeCashFlow: number[] = [];
    
    let cumulative = -totalInvestment; // Начальные инвестиции
    
    for (let year = 1; year <= timeHorizon; year++) {
      // Ежегодные выгоды с учетом инфляции
      const inflationAdjustedBenefits = annualBenefits * Math.pow(1.03, year - 1);
      
      // Сопровождение
      const maintenance = project.maintenanceCost;
      
      // Чистый денежный поток за год
      const yearlyNetCashFlow = inflationAdjustedBenefits - maintenance;
      netCashFlow.push(yearlyNetCashFlow);
      
      // Накопленный поток
      cumulative += yearlyNetCashFlow;
      cumulativeCashFlow.push(cumulative);
    }
    
    // Расчет показателей эффективности
    const totalBenefits = netCashFlow.reduce((sum, flow) => sum + flow, 0);
    const netPresentValue = this.calculateNPV(netCashFlow, discountRate);
    const roiPercentage = ((totalBenefits - totalInvestment) / totalInvestment) * 100;
    
    // Точка безубыточности
    const breakEvenPoint = this.findBreakEvenPoint(totalInvestment, netCashFlow);
    
    // Период окупаемости
    const paybackPeriod = this.calculatePaybackPeriod(totalInvestment, netCashFlow);
    
    // Анализ рисков
    const riskAdjustedROI = this.calculateRiskAdjustedROI(roiPercentage, project.riskLevel);
    
    // Сценарный анализ
    const scenarioAnalysis = {
      optimistic: roiPercentage * 1.3, // +30%
      realistic: roiPercentage,
      pessimistic: roiPercentage * 0.7 // -30%
    };
    
    // Показатели эффективности
    const efficiencyRatios = {
      benefitCostRatio: totalBenefits / totalInvestment,
      profitabilityIndex: (netPresentValue + totalInvestment) / totalInvestment,
      internalRateOfReturn: this.calculateIRR(totalInvestment, netCashFlow)
    };
    
    const calculation: ROICalculation = {
      projectId,
      calculationDate: new Date(),
      totalInvestment,
      totalBenefits,
      netPresentValue,
      roiPercentage,
      paybackPeriod,
      annualBenefits,
      netCashFlow,
      cumulativeCashFlow,
      breakEvenPoint,
      riskAdjustedROI,
      scenarioAnalysis,
      efficiencyRatios
    };
    
    // Кэшируем результат
    this.calculations.set(projectId, calculation);
    
    return calculation;
  }

  /**
   * Расчет ежегодных выгод проекта
   */
  private calculateAnnualBenefits(project: ROIProject): number {
    let annualBenefits = 0;
    
    // Экономия времени
    const timeSavingsAnnual = project.timeSavings.hoursPerTransaction * 
                             project.timeSavings.transactionsPerMonth * 
                             this.MONTHS_PER_YEAR * 
                             project.timeSavings.hourlyRate;
    annualBenefits += timeSavingsAnnual;
    
    // Снижение затрат
    project.costReduction.forEach(cost => {
      let annualAmount = cost.amount;
      if (cost.frequency === 'quarterly') {
        annualAmount *= 4;
      } else if (cost.frequency === 'yearly') {
        // остается как есть
      } else {
        annualAmount *= this.MONTHS_PER_YEAR; // monthly
      }
      annualBenefits += annualAmount;
    });
    
    // Увеличение выручки
    project.revenueIncrease.forEach(revenue => {
      let annualAmount = revenue.amount;
      if (revenue.frequency === 'quarterly') {
        annualAmount *= 4;
      } else if (revenue.frequency === 'yearly') {
        // остается как есть
      } else {
        annualAmount *= this.MONTHS_PER_YEAR; // monthly
      }
      annualBenefits += annualAmount;
    });
    
    // Снижение рисков
    project.riskReduction.forEach(risk => {
      const annualRiskReduction = risk.riskValue * risk.probability * risk.reduction;
      annualBenefits += annualRiskReduction;
    });
    
    return annualBenefits;
  }

  /**
   * Расчет NPV (чистой приведенной стоимости)
   */
  private calculateNPV(cashFlows: number[], discountRate: number): number {
    let npv = 0;
    cashFlows.forEach((flow, index) => {
      npv += flow / Math.pow(1 + discountRate, index + 1);
    });
    return npv;
  }

  /**
   * Расчет IRR (внутренней нормы доходности)
   */
  private calculateIRR(initialInvestment: number, cashFlows: number[]): number {
    // Упрощенный расчет IRR методом итерации
    let rate = 0.1; // Начальное предположение 10%
    const tolerance = 0.0001;
    const maxIterations = 100;
    
    for (let i = 0; i < maxIterations; i++) {
      const npv = this.calculateNPVWithRate(cashFlows, rate);
      const npvNext = this.calculateNPVWithRate(cashFlows, rate + 0.001);
      
      if (Math.abs(npv) < tolerance) break;
      
      // Линейная интерполяция
      const slope = (npvNext - npv) / 0.001;
      if (Math.abs(slope) < tolerance) break;
      
      rate = rate - npv / slope;
    }
    
    return rate * 100; // Возвращаем в процентах
  }

  /**
   * Вспомогательная функция для расчета NPV с заданной ставкой
   */
  private calculateNPVWithRate(cashFlows: number[], rate: number): number {
    let npv = 0;
    cashFlows.forEach((flow, index) => {
      npv += flow / Math.pow(1 + rate, index + 1);
    });
    return npv;
  }

  /**
   * Поиск точки безубыточности
   */
  private findBreakEvenPoint(initialInvestment: number, cashFlows: number[]): number {
    let cumulative = -initialInvestment;
    for (let i = 0; i < cashFlows.length; i++) {
      cumulative += cashFlows[i];
      if (cumulative >= 0) {
        return i + 1; // Возвращаем год (начиная с 1)
      }
    }
    return cashFlows.length; // Если не достигнута, возвращаем последний год
  }

  /**
   * Расчет периода окупаемости
   */
  private calculatePaybackPeriod(initialInvestment: number, cashFlows: number[]): number {
    let cumulative = -initialInvestment;
    for (let i = 0; i < cashFlows.length; i++) {
      cumulative += cashFlows[i];
      if (cumulative >= 0) {
        // Линейная интерполация для более точного расчета
        const previousCumulative = cumulative - cashFlows[i];
        const paybackFraction = Math.abs(previousCumulative) / cashFlows[i];
        return i + paybackFraction;
      }
    }
    return cashFlows.length; // Если не окупился, возвращаем горизонт планирования
  }

  /**
   * Расчет скорректированного ROI с учетом рисков
   */
  private calculateRiskAdjustedROI(baseROI: number, riskLevel: string): number {
    const riskMultiplier = {
      'low': 0.9,
      'medium': 0.8,
      'high': 0.7
    }[riskLevel] || 0.8;
    
    return baseROI * riskMultiplier;
  }

  /**
   * Создать сценарий ROI
   */
  createScenario(scenario: Omit<ROIScenario, 'id' | 'totalROI' | 'totalInvestment' | 'totalBenefits'>): string {
    const id = generateUUID();
    
    // Рассчитываем показатели сценария
    let totalInvestment = 0;
    let totalBenefits = 0;
    let weightedROI = 0;
    
    scenario.projects.forEach(projectId => {
      const calculation = this.calculateROI(projectId, scenario.parameters);
      if (calculation) {
        totalInvestment += calculation.totalInvestment;
        totalBenefits += calculation.totalBenefits;
        weightedROI += calculation.roiPercentage;
      }
    });
    
    const avgROI = scenario.projects.length > 0 ? weightedROI / scenario.projects.length : 0;
    
    const newScenario: ROIScenario = {
      ...scenario,
      id,
      totalROI: avgROI,
      totalInvestment,
      totalBenefits
    };
    
    this.scenarios.set(id, newScenario);
    return id;
  }

  /**
   * Получить сценарий по ID
   */
  getScenario(scenarioId: string): ROIScenario | undefined {
    return this.scenarios.get(scenarioId);
  }

  /**
   * Получить все сценарии
   */
  getAllScenarios(): ROIScenario[] {
    return Array.from(this.scenarios.values());
  }

  /**
   * Удалить сценарий
   */
  deleteScenario(scenarioId: string): boolean {
    return this.scenarios.delete(scenarioId);
  }

  /**
   * Сравнение проектов по ROI
   */
  compareProjects(projectIds: string[]): {
    ranking: Array<{
      project: ROIProject;
      calculation: ROICalculation;
      rank: number;
    }>;
    summary: {
      averageROI: number;
      bestProject: string;
      worstProject: string;
      totalInvestment: number;
      totalBenefits: number;
    };
  } {
    const rankings: Array<{
      project: ROIProject;
      calculation: ROICalculation;
      rank: number;
    }> = [];
    
    projectIds.forEach(projectId => {
      const calculation = this.calculateROI(projectId);
      const project = this.projects.get(projectId);
      
      if (calculation && project) {
        rankings.push({
          project,
          calculation,
          rank: 0 // Будет установлен после сортировки
        });
      }
    });
    
    // Сортируем по ROI по убыванию
    rankings.sort((a, b) => b.calculation.roiPercentage - a.calculation.roiPercentage);
    
    // Устанавливаем ранги
    rankings.forEach((item, index) => {
      item.rank = index + 1;
    });
    
    // Сводная информация
    const totalROI = rankings.reduce((sum, item) => sum + item.calculation.roiPercentage, 0);
    const totalInvestment = rankings.reduce((sum, item) => sum + item.calculation.totalInvestment, 0);
    const totalBenefits = rankings.reduce((sum, item) => sum + item.calculation.totalBenefits, 0);
    
    const summary = {
      averageROI: rankings.length > 0 ? totalROI / rankings.length : 0,
      bestProject: rankings.length > 0 ? rankings[0].project.name : '',
      worstProject: rankings.length > 0 ? rankings[rankings.length - 1].project.name : '',
      totalInvestment,
      totalBenefits
    };
    
    return {
      ranking: rankings,
      summary
    };
  }

  /**
   * Генерация отчета по ROI
   */
  generateROIReport(projectIds: string[], format: 'detailed' | 'summary' = 'detailed'): string {
    const projects = projectIds.map(id => this.projects.get(id)).filter(Boolean);
    const calculations = projectIds.map(id => this.calculateROI(id)).filter(Boolean);
    
    if (projects.length === 0) {
      return 'Нет данных для генерации отчета';
    }
    
    let report = `# Отчет по расчету ROI\n\n`;
    report += `**Дата создания:** ${new Date().toLocaleDateString()}\n`;
    report += `**Количество проектов:** ${projects.length}\n\n`;
    
    if (format === 'summary') {
      report += `## Сводная информация\n\n`;
      
      const comparison = this.compareProjects(projectIds);
      report += `**Средний ROI:** ${comparison.summary.averageROI.toFixed(2)}%\n`;
      report += `**Лучший проект:** ${comparison.summary.bestProject}\n`;
      report += `**Худший проект:** ${comparison.summary.worstProject}\n`;
      report += `**Общие инвестиции:** ${comparison.summary.totalInvestment.toLocaleString()} руб.\n`;
      report += `**Общие выгоды:** ${comparison.summary.totalBenefits.toLocaleString()} руб.\n\n`;
      
      report += `## Рейтинг проектов\n\n`;
      report += `| Ранг | Название | ROI (%) | NPV (руб.) | Период окупаемости |\n`;
      report += `|------|----------|---------|------------|--------------------|\n`;
      
      comparison.ranking.forEach(item => {
        report += `| ${item.rank} | ${item.project.name} | ${item.calculation.roiPercentage.toFixed(2)}% | ${item.calculation.netPresentValue.toLocaleString()} | ${item.calculation.paybackPeriod.toFixed(1)} мес. |\n`;
      });
    } else {
      // Детальный отчет
      projects.forEach((project, index) => {
        const calculation = calculations[index];
        if (!project || !calculation) return;
        
        report += `## ${index + 1}. ${project.name}\n\n`;
        report += `**Описание:** ${project.description || 'Не указано'}\n`;
        report += `**Категория:** ${project.category}\n`;
        report += `**Приоритет:** ${project.priority}\n\n`;
        
        report += `### Финансовые показатели\n\n`;
        report += `- **Общие инвестиции:** ${calculation.totalInvestment.toLocaleString()} руб.\n`;
        report += `- **Общие выгоды:** ${calculation.totalBenefits.toLocaleString()} руб.\n`;
        report += `- **ROI:** ${calculation.roiPercentage.toFixed(2)}%\n`;
        report += `- **NPV:** ${calculation.netPresentValue.toLocaleString()} руб.\n`;
        report += `- **Период окупаемости:** ${calculation.paybackPeriod.toFixed(1)} месяцев\n`;
        report += `- **IRR:** ${calculation.efficiencyRatios.internalRateOfReturn.toFixed(2)}%\n\n`;
        
        report += `### Анализ рисков\n\n`;
        report += `- **Скорректированный ROI:** ${calculation.riskAdjustedROI.toFixed(2)}%\n`;
        report += `- **Оптимистичный сценарий:** ${calculation.scenarioAnalysis.optimistic.toFixed(2)}%\n`;
        report += `- **Реалистичный сценарий:** ${calculation.scenarioAnalysis.realistic.toFixed(2)}%\n`;
        report += `- **Пессимистичный сценарий:** ${calculation.scenarioAnalysis.pessimistic.toFixed(2)}%\n\n`;
        
        report += `---\n\n`;
      });
    }
    
    return report;
  }

  /**
   * Экспорт данных проектов
   */
  exportProjectsData(format: 'json' | 'csv' = 'json'): string {
    const projects = this.getAllProjects();
    
    if (format === 'csv') {
      let csv = 'Название,Категория,Приоритет,Статус,Инвестиции,Выгоды,ROI,NPV,Период окупаемости\n';
      
      projects.forEach(project => {
        const calculation = this.calculateROI(project.id);
        if (calculation) {
          csv += `"${project.name}","${project.category}","${project.priority}","${project.status}",`;
          csv += `${calculation.totalInvestment},${calculation.totalBenefits},${calculation.roiPercentage},`;
          csv += `${calculation.netPresentValue},${calculation.paybackPeriod}\n`;
        }
      });
      
      return csv;
    }
    
    return JSON.stringify(projects, null, 2);
  }

  /**
   * Импорт данных проектов
   */
  importProjectsData(data: string, format: 'json' | 'csv' = 'json'): number {
    try {
      let projects: ROIProject[] = [];
      
      if (format === 'json') {
        projects = JSON.parse(data);
      } else {
        // Парсинг CSV (упрощенный)
        const lines = data.split('\n');
        const headers = lines[0].split(',');
        
        for (let i = 1; i < lines.length; i++) {
          const values = lines[i].split(',');
          if (values.length >= 5) {
            projects.push({
              id: generateUUID(),
              name: values[0].replace(/"/g, ''),
              category: 'custom',
              priority: 'medium',
              status: 'planning',
              developmentCost: parseFloat(values[4]) || 0,
              implementationCost: 0,
              maintenanceCost: 0,
              timeSavings: { hoursPerTransaction: 0, transactionsPerMonth: 0, hourlyRate: 0 },
              costReduction: [],
              revenueIncrease: [],
              riskReduction: [],
              implementationPeriod: 1,
              riskLevel: 'medium',
              createdAt: new Date(),
              modifiedAt: new Date(),
              createdBy: 'import'
            });
          }
        }
      }
      
      // Добавляем проекты
      projects.forEach(project => {
        const { id, ...projectData } = project;
        this.createProject(projectData);
      });
      
      return projects.length;
    } catch (error) {
      console.error('Ошибка импорта:', error);
      return 0;
    }
  }

  /**
   * Получение статистики сервиса
   */
  getServiceStatistics(): {
    totalProjects: number;
    completedProjects: number;
    averageROI: number;
    totalInvestment: number;
    totalBenefits: number;
    projectsByCategory: Record<string, number>;
    projectsByStatus: Record<string, number>;
  } {
    const projects = this.getAllProjects();
    const calculations = projects.map(p => this.calculateROI(p.id)).filter(Boolean);
    
    const completedProjects = projects.filter(p => p.status === 'completed' || p.status === 'deployed').length;
    const averageROI = calculations.length > 0 ? 
      calculations.reduce((sum, calc) => sum + calc.roiPercentage, 0) / calculations.length : 0;
    const totalInvestment = calculations.reduce((sum, calc) => sum + calc.totalInvestment, 0);
    const totalBenefits = calculations.reduce((sum, calc) => sum + calc.totalBenefits, 0);
    
    const projectsByCategory: Record<string, number> = {};
    const projectsByStatus: Record<string, number> = {};
    
    projects.forEach(project => {
      projectsByCategory[project.category] = (projectsByCategory[project.category] || 0) + 1;
      projectsByStatus[project.status] = (projectsByStatus[project.status] || 0) + 1;
    });
    
    return {
      totalProjects: projects.length,
      completedProjects,
      averageROI,
      totalInvestment,
      totalBenefits,
      projectsByCategory,
      projectsByStatus
    };
  }

  /**
   * Поиск проектов
   */
  searchProjects(query: string): ROIProject[] {
    const searchTerm = query.toLowerCase();
    return this.getAllProjects().filter(project =>
      project.name.toLowerCase().includes(searchTerm) ||
      project.description?.toLowerCase().includes(searchTerm) ||
      project.category.toLowerCase().includes(searchTerm)
    );
  }

  /**
   * Получение лучших проектов
   */
  getTopProjects(limit: number = 10, sortBy: 'roi' | 'npv' | 'payback' = 'roi'): ROIProject[] {
    const projects = this.getAllProjects();
    const projectsWithCalc = projects.map(project => ({
      project,
      calculation: this.calculateROI(project.id)
    })).filter(item => item.calculation !== null);
    
    // Сортируем по выбранному критерию
    projectsWithCalc.sort((a, b) => {
      if (!a.calculation || !b.calculation) return 0;
      
      switch (sortBy) {
        case 'roi':
          return b.calculation.roiPercentage - a.calculation.roiPercentage;
        case 'npv':
          return b.calculation.netPresentValue - a.calculation.netPresentValue;
        case 'payback':
          return a.calculation.paybackPeriod - b.calculation.paybackPeriod; // Меньше = лучше
        default:
          return 0;
      }
    });
    
    return projectsWithCalc.slice(0, limit).map(item => item.project);
  }
}

// Экспортируем экземпляр сервиса
export const roiCalculatorService = new ROICalculatorService();