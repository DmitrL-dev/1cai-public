/**
 * Сервис AI-анализа рисков проекта
 * Обеспечивает автоматическую идентификацию, анализ и прогнозирование рисков
 * с использованием машинного обучения и правил экспертной системы
 */

export interface RiskFactor {
  id: string;
  title: string;
  description: string;
  category: RiskCategory;
  probability: number; // 0-100%
  impact: RiskImpact;
  severity: RiskSeverity;
  confidence: number; // 0-100% уверенность AI в оценке
  likelihood: number; // расчетная вероятность с учетом контекста
  
  // Контекстная информация
  affectedTasks: string[]; // ID задач, которые затрагивает риск
  rootCauses: RootCause[];
  earlyWarning: EarlyWarningIndicator[];
  
  // Рекомендации по управлению
  mitigationStrategies: MitigationStrategy[];
  responsePlan: ResponsePlan;
  
  // Метаданные
  firstDetected: Date;
  lastUpdated: Date;
  detectedBy: 'ai_algorithm' | 'user_input' | 'system_rule';
  status: RiskStatus;
  
  // Связи с другими рисками
  relatedRisks: string[]; // ID связанных рисков
  cascadingEffect: boolean; // может ли вызвать другие риски
  
  // Временные данные
  timeToImpact?: number; // дней до потенциального проявления
  optimalResponseTime?: number; // рекомендуемое время для реакции
  
  // Экономическое воздействие
  costImpact?: CostImpact;
  scheduleImpact?: ScheduleImpact;
  qualityImpact?: QualityImpact;
}

export interface RiskCategory {
  id: string;
  name: string;
  description: string;
  color: string;
  icon: string;
}

export interface RiskImpact {
  schedule: number; // влияние на сроки (0-100%)
  budget: number; // влияние на бюджет (0-100%)
  scope: number; // влияние на объем (0-100%)
  quality: number; // влияние на качество (0-100%)
  risk: number; // влияние на другие риски (0-100%)
}

export type RiskSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface RootCause {
  id: string;
  description: string;
  probability: number; // вероятность того, что это действительно причина
  evidence: Evidence[];
  category: 'technical' | 'organizational' | 'environmental' | 'external';
}

export interface Evidence {
  type: 'metric' | 'pattern' | 'anomaly' | 'expert_opinion';
  description: string;
  strength: number; // 0-100% сила доказательства
  source: string;
  timestamp: Date;
}

export interface EarlyWarningIndicator {
  id: string;
  name: string;
  type: 'metric' | 'behavior' | 'pattern';
  currentValue: number;
  threshold: number;
  trend: 'improving' | 'stable' | 'worsening';
  description: string;
  severity: RiskSeverity;
}

export interface MitigationStrategy {
  id: string;
  title: string;
  description: string;
  approach: 'avoid' | 'reduce' | 'transfer' | 'accept';
  priority: 'low' | 'medium' | 'high';
  
  // Оценка эффективности
  effectiveness: number; // 0-100%
  costBenefitRatio: number; // соотношение стоимость/польза
  implementationDifficulty: 'easy' | 'medium' | 'hard';
  timeToImplement: number; // дней
  
  // Ресурсы
  requiredResources: Resource[];
  stakeholders: string[];
  
  // Планирование
  owner: string;
  timeline: Timeline;
  milestones: Milestone[];
  
  // Мониторинг
  successCriteria: string[];
  monitoringPlan: MonitoringPlan;
}

export interface Resource {
  id: string;
  type: 'human' | 'financial' | 'technical' | 'organizational';
  name: string;
  amount: number;
  unit: string;
  availability: number; // 0-100%
  cost?: number;
}

export interface Timeline {
  startDate: Date;
  endDate: Date;
  criticalPath: boolean;
  dependencies: string[];
}

export interface Milestone {
  id: string;
  name: string;
  date: Date;
  description: string;
  isCompleted: boolean;
}

export interface MonitoringPlan {
  frequency: 'daily' | 'weekly' | 'monthly';
  metrics: string[];
  reportingLevel: 'task' | 'project' | 'portfolio';
  alertThresholds: AlertThreshold[];
}

export interface AlertThreshold {
  metric: string;
  warningLevel: number;
  criticalLevel: number;
}

export interface ResponsePlan {
  triggers: Trigger[];
  actions: ResponseAction[];
  escalationPath: EscalationStep[];
  communicationPlan: CommunicationPlan;
}

export interface Trigger {
  id: string;
  type: 'probability' | 'impact' | 'time' | 'external_event';
  condition: string;
  description: string;
}

export interface ResponseAction {
  id: string;
  name: string;
  description: string;
  trigger: string; // ID триггера
  owner: string;
  timeline: number; // часов для выполнения
  resources: Resource[];
  successCriteria: string[];
}

export interface EscalationStep {
  level: number;
  title: string;
  authority: string;
  responseTime: number; // часов
  criteria: string[];
}

export interface CommunicationPlan {
  stakeholders: Stakeholder[];
  messages: Message[];
  channels: CommunicationChannel[];
  frequency: 'real_time' | 'daily' | 'weekly' | 'as_needed';
}

export interface Stakeholder {
  id: string;
  name: string;
  role: string;
  responsibility: string;
  contact: string;
}

export interface Message {
  id: string;
  purpose: string;
  content: string;
  audience: string;
  timing: string;
}

export interface CommunicationChannel {
  type: 'email' | 'meeting' | 'report' | 'dashboard' | 'alert';
  purpose: string;
  frequency: string;
  participants: string[];
}

export interface RiskStatus {
  current: 'identified' | 'assessed' | 'planned' | 'implemented' | 'resolved' | 'closed';
  history: StatusChange[];
  lastReviewDate: Date;
  nextReviewDate: Date;
}

export interface StatusChange {
  from: string;
  to: string;
  date: Date;
  reason: string;
  changedBy: string;
}

export interface CostImpact {
  direct: number; // прямое увеличение затрат
  indirect: number; // косвенные затраты
  opportunity: number; // упущенная выгода
  contingency: number; // резервный фонд
  total: number; // общий финансовый ущерб
  currency: string;
}

export interface ScheduleImpact {
  criticalPathDelay: number; // дней
  totalDurationIncrease: number; // дней
  milestoneDelays: MilestoneDelay[];
  resourceOverallocation: number; // часов
}

export interface MilestoneDelay {
  milestoneId: string;
  originalDate: Date;
  newDate: Date;
  delay: number; // дней
}

export interface QualityImpact {
  functionalRequirements: number; // % невыполненных требований
  nonFunctionalRequirements: number; // % невыполненных требований
  testingGaps: number; // % покрытия тестами
  complianceIssues: number; // количество нарушений
  customerSatisfaction: number; // снижение удовлетворенности (0-100)
}

export interface RiskAnalysisContext {
  project: {
    id: string;
    name: string;
    type: ProjectType;
    complexity: 'low' | 'medium' | 'high' | 'very_high';
    size: 'small' | 'medium' | 'large' | 'very_large';
    domain: string;
    technology: string[];
    teamSize: number;
    teamExperience: 'junior' | 'mixed' | 'senior';
    budget: number;
    timeline: number; // дней
    methodology: 'waterfall' | 'agile' | 'hybrid' | 'custom';
    stakeholderCount: number;
  };
  
  environment: {
    industry: string;
    regulatory: string[];
    marketVolatility: number; // 0-100%
    competitionLevel: number; // 0-100%
    technologyMaturity: 'emerging' | 'mature' | 'legacy';
  };
  
  historical: {
    projectHistory: ProjectHistory[];
    riskPatterns: RiskPattern[];
    teamPerformance: PerformanceMetrics;
    externalFactors: ExternalFactor[];
  };
  
  current: {
    taskProgress: TaskProgress[];
    resourceUtilization: ResourceUtilization[];
    issueLog: IssueLog[];
    changeRequests: ChangeRequest[];
  };
}

export type ProjectType = 'software_development' | 'infrastructure' | 'integration' | 'digital_transformation' | 'custom';

export interface ProjectHistory {
  projectId: string;
  name: string;
  type: ProjectType;
  outcome: 'successful' | 'delayed' | 'cancelled' | 'partially_successful';
  duration: number; // дней
  budget: number;
  actualBudget: number;
  teamSize: number;
  risks: string[];
  lessons: Lesson[];
}

export interface Lesson {
  category: 'technical' | 'organizational' | 'process' | 'communication';
  description: string;
  impact: 'positive' | 'negative';
  applicability: 'specific' | 'general' | 'transferable';
}

export interface RiskPattern {
  name: string;
  description: string;
  frequency: number; // 0-100%
  categories: string[];
  indicators: string[];
  mitigation: string[];
}

export interface PerformanceMetrics {
  onTimeDelivery: number; // 0-100%
  budgetAdherence: number; // 0-100%
  qualityScore: number; // 0-100%
  stakeholderSatisfaction: number; // 0-100%
  teamProductivity: number; // 0-100%
}

export interface ExternalFactor {
  type: 'economic' | 'political' | 'technological' | 'social' | 'environmental';
  description: string;
  probability: number; // 0-100%
  impact: number; // 0-100%
  timeframe: string;
  uncertainty: number; // 0-100%
}

export interface TaskProgress {
  taskId: string;
  plannedProgress: number; // 0-100%
  actualProgress: number; // 0-100%
  variance: number; // %
  issues: string[];
  blockers: string[];
}

export interface ResourceUtilization {
  resourceId: string;
  plannedUtilization: number; // 0-100%
  actualUtilization: number; // 0-100%
  efficiency: number; // 0-100%
  availability: number; // часов
  allocatedHours: number;
}

export interface IssueLog {
  id: string;
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'open' | 'in_progress' | 'resolved' | 'closed';
  impact: number; // 0-100%
  resolutionTime: number; // часов
  affectedTasks: string[];
}

export interface ChangeRequest {
  id: string;
  description: string;
  type: 'scope' | 'schedule' | 'budget' | 'quality' | 'resource';
  status: 'requested' | 'approved' | 'rejected' | 'implemented';
  impact: {
    schedule: number; // дней
    budget: number;
    scope: number; // %
    risk: number; // 0-100%
  };
  requestDate: Date;
  implementationDate?: Date;
}

export interface AIRiskAnalysisResult {
  overallRiskScore: number; // 0-100%
  riskLevel: RiskSeverity;
  riskDistribution: RiskDistribution;
  topRisks: RiskFactor[];
  emergingRisks: RiskFactor[];
  riskTrends: RiskTrend[];
  
  // Детальный анализ
  riskCategories: CategoryAnalysis[];
  timeBasedRisks: TimeBasedRisk[];
  cascadingRisks: CascadingRisk[];
  
  // Рекомендации
  prioritizedActions: PrioritizedAction[];
  resourceRecommendations: ResourceRecommendation[];
  monitoringPlan: MonitoringPlan;
  
  // Метаданные
  analysisDate: Date;
  confidence: number;
  limitations: string[];
  assumptions: string[];
}

export interface RiskDistribution {
  byCategory: { category: string; count: number; percentage: number }[];
  bySeverity: { severity: RiskSeverity; count: number; percentage: number }[];
  byLikelihood: { range: string; count: number; percentage: number }[];
  byImpact: { range: string; count: number; percentage: number }[];
}

export interface RiskTrend {
  riskId: string;
  trend: 'increasing' | 'stable' | 'decreasing';
  changeRate: number; // % изменения за период
  factors: string[];
  prediction: string;
  timeHorizon: number; // дней
}

export interface CategoryAnalysis {
  category: string;
  riskCount: number;
  avgProbability: number;
  avgImpact: number;
  riskScore: number;
  trends: RiskTrend[];
  recommendations: string[];
}

export interface TimeBasedRisk {
  timeframe: 'immediate' | 'short_term' | 'medium_term' | 'long_term';
  description: string;
  risks: RiskFactor[];
  probability: number;
  impact: number;
  preparationTime: number; // дней
}

export interface CascadingRisk {
  primaryRisk: string;
  cascadePath: CascadeStep[];
  amplification: number; // % усиления
  probabilityOfCascade: number; // 0-100%
}

export interface CascadeStep {
  from: string;
  to: string;
  mechanism: string;
  delay: number; // дней
}

export interface PrioritizedAction {
  action: string;
  description: string;
  priority: RiskSeverity;
  impact: number; // ожидаемое снижение риска
  effort: number; // требуемые усилия
  timeframe: number; // дней
  owner: string;
  resources: string[];
}

export interface ResourceRecommendation {
  type: 'human' | 'financial' | 'technical' | 'organizational';
  description: string;
  justification: string;
  estimatedCost: number;
  expectedBenefit: number;
  timeline: number; // дней
  priority: 'low' | 'medium' | 'high';
}

export class AIRiskAnalysisService {
  private readonly riskCategories: RiskCategory[] = [
    {
      id: 'technical',
      name: 'Технические риски',
      description: 'Проблемы с технологиями, архитектурой, интеграцией',
      color: '#ef4444',
      icon: 'cpu'
    },
    {
      id: 'schedule',
      name: 'Риски сроков',
      description: 'Задержки в выполнении задач и вехах проекта',
      color: '#f59e0b',
      icon: 'clock'
    },
    {
      id: 'budget',
      name: 'Бюджетные риски',
      description: 'Превышение стоимости и недостаток финансирования',
      color: '#10b981',
      icon: 'dollar'
    },
    {
      id: 'quality',
      name: 'Риски качества',
      description: 'Недостижение требуемых стандартов качества',
      color: '#8b5cf6',
      icon: 'shield'
    },
    {
      id: 'resource',
      name: 'Ресурсные риски',
      description: 'Проблемы с персоналом, оборудованием, инфраструктурой',
      color: '#06b6d4',
      icon: 'users'
    },
    {
      id: 'organizational',
      name: 'Организационные риски',
      description: 'Проблемы в управлении, коммуникации, процессах',
      color: '#84cc16',
      icon: 'building'
    },
    {
      id: 'external',
      name: 'Внешние риски',
      description: 'Факторы внешней среды, рынка, законодательства',
      color: '#ec4899',
      icon: 'globe'
    }
  ];

  private readonly riskPatterns = [
    {
      name: 'Технический долг',
      pattern: /deprecated|legacy|outdated|technical debt/i,
      severity: 'medium',
      category: 'technical'
    },
    {
      name: 'Недостаток опыта',
      pattern: /first time|learning|unfamiliar|new technology/i,
      severity: 'high',
      category: 'resource'
    },
    {
      name: 'Интеграционные сложности',
      pattern: /integration|api|interface|compatibility/i,
      severity: 'high',
      category: 'technical'
    },
    {
      name: 'Требования не определены',
      pattern: /unclear|ambiguous|undefined|missing requirements/i,
      severity: 'critical',
      category: 'scope'
    },
    {
      name: 'Изменение требований',
      pattern: /change|modification|add|remove requirements/i,
      severity: 'high',
      category: 'scope'
    }
  ];

  constructor() {
    // Инициализация сервиса анализа рисков
  }

  /**
   * Основной метод анализа рисков проекта
   */
  async analyzeProjectRisks(context: RiskAnalysisContext): Promise<AIRiskAnalysisResult> {
    const risks = await this.identifyRisks(context);
    const analyzedRisks = await this.analyzeRiskFactors(risks, context);
    const filteredRisks = this.filterSignificantRisks(analyzedRisks);
    
    return {
      overallRiskScore: this.calculateOverallRiskScore(filteredRisks),
      riskLevel: this.determineRiskLevel(filteredRisks),
      riskDistribution: this.analyzeRiskDistribution(filteredRisks),
      topRisks: this.getTopRisks(filteredRisks, 10),
      emergingRisks: this.identifyEmergingRisks(filteredRisks),
      riskTrends: this.analyzeRiskTrends(filteredRisks),
      riskCategories: this.analyzeByCategory(filteredRisks),
      timeBasedRisks: this.analyzeTimeBasedRisks(filteredRisks),
      cascadingRisks: this.identifyCascadingRisks(filteredRisks),
      prioritizedActions: this.generatePrioritizedActions(filteredRisks),
      resourceRecommendations: this.generateResourceRecommendations(filteredRisks, context),
      monitoringPlan: this.createMonitoringPlan(filteredRisks),
      analysisDate: new Date(),
      confidence: this.calculateAnalysisConfidence(filteredRisks, context),
      limitations: this.identifyLimitations(context),
      assumptions: this.identifyAssumptions(context)
    };
  }

  /**
   * Идентификация потенциальных рисков
   */
  private async identifyRisks(context: RiskAnalysisContext): Promise<Partial<RiskFactor>[]> {
    const risks: Partial<RiskFactor>[] = [];

    // Анализ технических рисков
    risks.push(...this.identifyTechnicalRisks(context));
    
    // Анализ рисков сроков
    risks.push(...this.analyzeScheduleRisks(context));
    
    // Анализ бюджетных рисков
    risks.push(...this.analyzeBudgetRisks(context));
    
    // Анализ рисков ресурсов
    risks.push(...this.analyzeResourceRisks(context));
    
    // Анализ внешних факторов
    risks.push(...this.analyzeExternalRisks(context));
    
    // Анализ рисков качества
    risks.push(...this.analyzeQualityRisks(context));
    
    // Pattern-based анализ
    risks.push(...this.analyzePatternBasedRisks(context));

    return risks;
  }

  /**
   * Анализ технических рисков
   */
  private identifyTechnicalRisks(context: RiskAnalysisContext): Partial<RiskFactor>[] {
    const risks: Partial<RiskFactor>[] = [];

    // Анализ сложности технологии
    if (context.project.technology.some(tech => 
      ['machine learning', 'blockchain', 'quantum', 'ar/vr'].some(emerging => 
        tech.toLowerCase().includes(emerging)
      )
    )) {
      risks.push({
        title: 'Использование экспериментальных технологий',
        description: 'Проект использует незрелые или экспериментальные технологии',
        category: this.getCategory('technical'),
        probability: 75,
        impact: {
          schedule: 60,
          budget: 40,
          scope: 30,
          quality: 50,
          risk: 70
        },
        severity: 'high',
        detectedBy: 'ai_algorithm'
      });
    }

    // Анализ интеграционных сложностей
    if (context.project.technology.length > 5) {
      risks.push({
        title: 'Высокая сложность интеграции',
        description: 'Большое количество технологий увеличивает риск интеграционных проблем',
        category: this.getCategory('technical'),
        probability: 65,
        impact: {
          schedule: 80,
          budget: 50,
          scope: 40,
          quality: 60,
          risk: 75
        },
        severity: 'high',
        detectedBy: 'ai_algorithm'
      });
    }

    // Анализ соответствия требованиям архитектуры
    if (context.project.complexity === 'very_high') {
      risks.push({
        title: 'Сложность архитектуры',
        description: 'Высокая сложность проекта может привести к архитектурным проблемам',
        category: this.getCategory('technical'),
        probability: 70,
        impact: {
          schedule: 40,
          budget: 60,
          scope: 50,
          quality: 80,
          risk: 65
        },
        severity: 'high',
        detectedBy: 'ai_algorithm'
      });
    }

    return risks;
  }

  /**
   * Анализ рисков сроков
   */
  private analyzeScheduleRisks(context: RiskAnalysisContext): Partial<RiskFactor>[] {
    const risks: Partial<RiskFactor>[] = [];

    // Анализ размера команды vs объем работ
    const tasksPerPerson = context.project.teamSize > 0 ? 
      Math.ceil(context.project.timeline / context.project.teamSize) : 0;
    
    if (tasksPerPerson > 20) {
      risks.push({
        title: 'Перегрузка команды',
        description: `Каждый член команды должен выполнить ${tasksPerPerson} задач, что может привести к задержкам`,
        category: this.getCategory('schedule'),
        probability: 80,
        impact: {
          schedule: 85,
          budget: 60,
          scope: 40,
          quality: 70,
          risk: 75
        },
        severity: 'critical',
        detectedBy: 'ai_algorithm'
      });
    }

    // Анализ опыта команды
    if (context.project.teamExperience === 'junior' && context.project.complexity === 'high') {
      risks.push({
        title: 'Недостаток опыта команды',
        description: 'Неопытная команда работает над сложным проектом',
        category: this.getCategory('resource'),
        probability: 70,
        impact: {
          schedule: 75,
          budget: 55,
          scope: 45,
          quality: 60,
          risk: 65
        },
        severity: 'high',
        detectedBy: 'ai_algorithm'
      });
    }

    // Анализ количества заинтересованных сторон
    if (context.project.stakeholderCount > 10) {
      risks.push({
        title: 'Высокая сложность управления стейкхолдерами',
        description: 'Большое количество заинтересованных сторон увеличивает риск изменений требований',
        category: this.getCategory('organizational'),
        probability: 60,
        impact: {
          schedule: 65,
          budget: 40,
          scope: 80,
          quality: 50,
          risk: 60
        },
        severity: 'medium',
        detectedBy: 'ai_algorithm'
      });
    }

    // Анализ текущего прогресса задач
    const delayedTasks = context.current.taskProgress.filter(t => t.variance < -10);
    if (delayedTasks.length > 0) {
      const delayPercentage = (delayedTasks.length / context.current.taskProgress.length) * 100;
      
      risks.push({
        title: 'Отставание от графика',
        description: `${delayPercentage.toFixed(1)}% задач отстают от планового графика на более чем 10%`,
        category: this.getCategory('schedule'),
        probability: Math.min(90, delayPercentage * 2),
        impact: {
          schedule: Math.min(95, delayPercentage * 1.5),
          budget: Math.min(80, delayPercentage),
          scope: 30,
          quality: 40,
          risk: 70
        },
        severity: delayPercentage > 25 ? 'critical' : 'high',
        detectedBy: 'ai_algorithm'
      });
    }

    return risks;
  }

  /**
   * Анализ бюджетных рисков
   */
  private analyzeBudgetRisks(context: RiskAnalysisContext): Partial<RiskFactor>[] {
    const risks: Partial<RiskFactor>[] = [];

    // Анализ размера бюджета vs сложность
    if (context.project.budget < context.project.teamSize * context.project.timeline * 1000) {
      risks.push({
        title: 'Недостаточное финансирование',
        description: 'Бюджет проекта может быть недостаточным для запланированного объема работ',
        category: this.getCategory('budget'),
        probability: 70,
        impact: {
          schedule: 40,
          budget: 90,
          scope: 60,
          quality: 50,
          risk: 70
        },
        severity: 'high',
        detectedBy: 'ai_algorithm'
      });
    }

    // Анализ волатильности рынка
    if (context.environment.marketVolatility > 70) {
      risks.push({
        title: 'Волатильность рынка',
        description: 'Высокая волатильность рынка может повлиять на стоимость ресурсов и материалов',
        category: this.getCategory('external'),
        probability: 60,
        impact: {
          schedule: 20,
          budget: 75,
          scope: 40,
          quality: 30,
          risk: 55
        },
        severity: 'medium',
        detectedBy: 'ai_algorithm'
      });
    }

    return risks;
  }

  /**
   * Анализ рисков ресурсов
   */
  private analyzeResourceRisks(context: RiskAnalysisContext): Partial<RiskFactor>[] {
    const risks: Partial<RiskFactor>[] = [];

    // Анализ перегрузки ресурсов
    const overloadedResources = context.current.resourceUtilization.filter(r => r.actualUtilization > 90);
    if (overloadedResources.length > 0) {
      risks.push({
        title: 'Перегрузка ресурсов',
        description: `${overloadedResources.length} ресурсов загружены более чем на 90%`,
        category: this.getCategory('resource'),
        probability: 85,
        impact: {
          schedule: 80,
          budget: 60,
          scope: 50,
          quality: 70,
          risk: 75
        },
        severity: 'high',
        detectedBy: 'ai_algorithm'
      });
    }

    // Анализ доступности ресурсов
    const unavailableResources = context.current.resourceUtilization.filter(r => r.availability < 50);
    if (unavailableResources.length > 0) {
      risks.push({
        title: 'Ограниченная доступность ресурсов',
        description: `${unavailableResources.length} ресурсов имеют ограниченную доступность`,
        category: this.getCategory('resource'),
        probability: 75,
        impact: {
          schedule: 70,
          budget: 65,
          scope: 45,
          quality: 60,
          risk: 65
        },
        severity: 'high',
        detectedBy: 'ai_algorithm'
      });
    }

    return risks;
  }

  /**
   * Анализ внешних рисков
   */
  private analyzeExternalRisks(context: RiskAnalysisContext): Partial<RiskFactor>[] {
    const risks: Partial<RiskFactor>[] = [];

    // Анализ внешних факторов
    context.historical.externalFactors.forEach(factor => {
      if (factor.probability > 50 && factor.impact > 60) {
        risks.push({
          title: `Внешний риск: ${factor.type}`,
          description: factor.description,
          category: this.getCategory('external'),
          probability: factor.probability,
          impact: {
            schedule: factor.impact * 0.7,
            budget: factor.impact * 0.8,
            scope: factor.impact * 0.5,
            quality: factor.impact * 0.6,
            risk: factor.impact * 0.9
          },
          severity: factor.impact > 80 ? 'critical' : 'high',
          detectedBy: 'ai_algorithm'
        });
      }
    });

    return risks;
  }

  /**
   * Анализ рисков качества
   */
  private analyzeQualityRisks(context: RiskAnalysisContext): Partial<RiskFactor>[] {
    const risks: Partial<RiskFactor>[] = [];

    // Анализ метрик качества команды
    if (context.historical.teamPerformance.qualityScore < 70) {
      risks.push({
        title: 'Риск низкого качества',
        description: 'История команды показывает низкие показатели качества',
        category: this.getCategory('quality'),
        probability: 65,
        impact: {
          schedule: 30,
          budget: 40,
          scope: 25,
          quality: 85,
          risk: 60
        },
        severity: 'medium',
        detectedBy: 'ai_algorithm'
      });
    }

    // Анализ количества открытых проблем
    if (context.current.issueLog.filter(i => i.severity === 'high' || i.severity === 'critical').length > 5) {
      risks.push({
        title: 'Высокое количество критических проблем',
        description: 'В проекте много открытых критических проблем',
        category: this.getCategory('quality'),
        probability: 75,
        impact: {
          schedule: 50,
          budget: 60,
          scope: 40,
          quality: 90,
          risk: 70
        },
        severity: 'high',
        detectedBy: 'ai_algorithm'
      });
    }

    return risks;
  }

  /**
   * Pattern-based анализ рисков
   */
  private analyzePatternBasedRisks(context: RiskAnalysisContext): Partial<RiskFactor>[] {
    const risks: Partial<RiskFactor>[] = [];

    // Анализ текста проекта
    const projectText = [
      context.project.name,
      context.project.description || '',
      ...context.project.domain.split(' ')
    ].join(' ').toLowerCase();

    // Поиск паттернов рисков
    this.riskPatterns.forEach(pattern => {
      if (pattern.pattern.test(projectText)) {
        risks.push({
          title: `Риск: ${pattern.name}`,
          description: `Обнаружен паттерн "${pattern.name}" в описании проекта`,
          category: this.getCategory(pattern.category as any),
          probability: 60,
          impact: {
            schedule: 50,
            budget: 40,
            scope: 60,
            quality: 70,
            risk: 55
          },
          severity: pattern.severity as RiskSeverity,
          detectedBy: 'ai_algorithm'
        });
      }
    });

    return risks;
  }

  /**
   * Детальный анализ факторов риска
   */
  private async analyzeRiskFactors(risks: Partial<RiskFactor>[], context: RiskAnalysisContext): Promise<RiskFactor[]> {
    return risks.map(risk => {
      const analyzedRisk: RiskFactor = {
        id: this.generateId(),
        title: risk.title || 'Не определено',
        description: risk.description || '',
        category: risk.category || this.getCategory('technical'),
        probability: risk.probability || 50,
        impact: risk.impact || {
          schedule: 50,
          budget: 50,
          scope: 50,
          quality: 50,
          risk: 50
        },
        severity: risk.severity || 'medium',
        confidence: this.calculateConfidence(risk, context),
        likelihood: this.calculateLikelihood(risk, context),
        affectedTasks: [],
        rootCauses: this.identifyRootCauses(risk, context),
        earlyWarning: this.generateEarlyWarningIndicators(risk, context),
        mitigationStrategies: this.generateMitigationStrategies(risk),
        responsePlan: this.generateResponsePlan(risk),
        firstDetected: new Date(),
        lastUpdated: new Date(),
        detectedBy: risk.detectedBy || 'ai_algorithm',
        status: {
          current: 'identified',
          history: [],
          lastReviewDate: new Date(),
          nextReviewDate: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000) // +7 дней
        },
        relatedRisks: [],
        cascadingEffect: false,
        costImpact: this.calculateCostImpact(risk),
        scheduleImpact: this.calculateScheduleImpact(risk),
        qualityImpact: this.calculateQualityImpact(risk)
      };

      return analyzedRisk;
    });
  }

  /**
   * Вычисление уверенности в анализе риска
   */
  private calculateConfidence(risk: Partial<RiskFactor>, context: RiskAnalysisContext): number {
    let confidence = 50; // базовая уверенность

    // Увеличиваем уверенность на основе доступных данных
    if (context.historical.projectHistory.length > 0) confidence += 15;
    if (context.historical.riskPatterns.length > 0) confidence += 10;
    if (context.current.taskProgress.length > 0) confidence += 15;
    if (context.current.issueLog.length > 0) confidence += 10;

    // Снижаем уверенность при высокой неопределенности
    if (context.environment.marketVolatility > 70) confidence -= 15;
    if (context.project.complexity === 'very_high') confidence -= 10;

    return Math.max(0, Math.min(100, confidence));
  }

  /**
   * Вычисление вероятности с учетом контекста
   */
  private calculateLikelihood(risk: Partial<RiskFactor>, context: RiskAnalysisContext): number {
    let likelihood = risk.probability || 50;

    // Корректировка на основе истории команды
    const teamPerf = context.historical.teamPerformance;
    if (teamPerf.onTimeDelivery < 60) likelihood += 15;
    if (teamPerf.budgetAdherence < 70) likelihood += 10;

    // Корректировка на основе текущих метрик
    const delayedTasks = context.current.taskProgress.filter(t => t.variance < -10);
    if (delayedTasks.length > 0) {
      likelihood += (delayedTasks.length / context.current.taskProgress.length) * 20;
    }

    return Math.max(0, Math.min(100, likelihood));
  }

  /**
   * Идентификация корневых причин риска
   */
  private identifyRootCauses(risk: Partial<RiskFactor>, context: RiskAnalysisContext): RootCause[] {
    const causes: RootCause[] = [];

    // Анализ на основе категории риска
    switch (risk.category?.id) {
      case 'technical':
        causes.push({
          id: this.generateId(),
          description: 'Недостаточная техническая экспертиза команды',
          probability: 70,
          evidence: [
            {
              type: 'pattern',
              description: 'Использование новых технологий',
              strength: 80,
              source: 'Анализ технологий проекта',
              timestamp: new Date()
            }
          ],
          category: 'technical'
        });
        break;

      case 'schedule':
        causes.push({
          id: this.generateId(),
          description: 'Нереалистичное планирование сроков',
          probability: 75,
          evidence: [
            {
              type: 'metric',
              description: 'Отставание от графика',
              strength: 85,
              source: 'Анализ прогресса задач',
              timestamp: new Date()
            }
          ],
          category: 'organizational'
        });
        break;

      case 'resource':
        causes.push({
          id: this.generateId(),
          description: 'Недостаток ключевых ресурсов',
          probability: 80,
          evidence: [
            {
              type: 'metric',
              description: 'Перегрузка команды',
              strength: 90,
              source: 'Анализ загрузки ресурсов',
              timestamp: new Date()
            }
          ],
          category: 'organizational'
        });
        break;
    }

    return causes;
  }

  /**
   * Генерация индикаторов раннего предупреждения
   */
  private generateEarlyWarningIndicators(risk: Partial<RiskFactor>, context: RiskAnalysisContext): EarlyWarningIndicator[] {
    const indicators: EarlyWarningIndicator[] = [];

    // Общие индикаторы на основе типа риска
    switch (risk.category?.id) {
      case 'technical':
        indicators.push({
          id: this.generateId(),
          name: 'Количество технических проблем',
          type: 'metric',
          currentValue: context.current.issueLog.filter(i => i.severity === 'high').length,
          threshold: 5,
          trend: 'worsening',
          description: 'Увеличение количества технических проблем',
          severity: risk.severity || 'medium'
        });
        break;

      case 'schedule':
        indicators.push({
          id: this.generateId(),
          name: 'Отклонение от графика',
          type: 'metric',
          currentValue: this.calculateScheduleVariance(context),
          threshold: -15,
          trend: 'worsening',
          description: 'Увеличение отклонения от планового графика',
          severity: risk.severity || 'medium'
        });
        break;
    }

    return indicators;
  }

  /**
   * Генерация стратегий митигации
   */
  private generateMitigationStrategies(risk: Partial<RiskFactor>): MitigationStrategy[] {
    const strategies: MitigationStrategy[] = [];

    // Стратегии в зависимости от категории и подхода
    strategies.push({
      id: this.generateId(),
      title: this.getDefaultMitigationTitle(risk.category?.id || 'technical'),
      description: this.getDefaultMitigationDescription(risk.category?.id || 'technical'),
      approach: 'reduce',
      priority: risk.severity === 'critical' ? 'high' : 'medium',
      effectiveness: 70,
      costBenefitRatio: 2.5,
      implementationDifficulty: 'medium',
      timeToImplement: 14,
      requiredResources: [
        {
          id: this.generateId(),
          type: 'human',
          name: 'Технический специалист',
          amount: 1,
          unit: 'человек',
          availability: 80
        }
      ],
      stakeholders: ['Project Manager', 'Technical Lead'],
      owner: 'Project Manager',
      timeline: {
        startDate: new Date(),
        endDate: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000),
        criticalPath: false,
        dependencies: []
      },
      milestones: [],
      successCriteria: ['Снижение вероятности риска на 40%', 'Улучшение показателей проекта'],
      monitoringPlan: {
        frequency: 'weekly',
        metrics: ['Вероятность риска', 'Влияние на проект'],
        reportingLevel: 'project',
        alertThresholds: []
      }
    });

    return strategies;
  }

  /**
   * Генерация плана реагирования
   */
  private generateResponsePlan(risk: Partial<RiskFactor>): ResponsePlan {
    return {
      triggers: [
        {
          id: this.generateId(),
          type: 'probability',
          condition: 'probability > 80%',
          description: 'Высокая вероятность проявления риска'
        },
        {
          id: this.generateId(),
          type: 'impact',
          condition: 'impact.score > 70%',
          description: 'Значительное влияние на проект'
        }
      ],
      actions: [
        {
          id: this.generateId(),
          name: 'Активация плана реагирования',
          description: 'Немедленное начало реализации мер по митигации риска',
          trigger: 'probability > 80%',
          owner: 'Project Manager',
          timeline: 4,
          requiredResources: [],
          successCriteria: ['Реализация ключевых мер митигации', 'Снижение риска']
        }
      ],
      escalationPath: [
        {
          level: 1,
          title: 'Project Manager',
          authority: 'Управление проектом',
          responseTime: 4,
          criteria: ['Критический риск выявлен']
        },
        {
          level: 2,
          title: 'Program Manager',
          authority: 'Управление портфелем',
          responseTime: 8,
          criteria: ['Критический риск не управляется на уровне проекта']
        }
      ],
      communicationPlan: {
        stakeholders: [],
        messages: [],
        channels: [],
        frequency: 'real_time'
      }
    };
  }

  /**
   * Вспомогательные методы
   */
  private getCategory(categoryId: string): RiskCategory {
    return this.riskCategories.find(c => c.id === categoryId) || this.riskCategories[0];
  }

  private generateId(): string {
    return `risk_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private calculateScheduleVariance(context: RiskAnalysisContext): number {
    if (context.current.taskProgress.length === 0) return 0;
    
    const totalVariance = context.current.taskProgress.reduce((sum, task) => sum + task.variance, 0);
    return totalVariance / context.current.taskProgress.length;
  }

  private getDefaultMitigationTitle(categoryId: string): string {
    const titles: Record<string, string> = {
      technical: 'Техническая оптимизация',
      schedule: 'Управление сроками',
      budget: 'Финансовое планирование',
      quality: 'Контроль качества',
      resource: 'Оптимизация ресурсов',
      organizational: 'Организационные улучшения',
      external: 'Управление внешними факторами'
    };
    return titles[categoryId] || 'Общие меры митигации';
  }

  private getDefaultMitigationDescription(categoryId: string): string {
    const descriptions: Record<string, string> = {
      technical: 'Улучшение технической архитектуры и процессов разработки',
      schedule: 'Оптимизация планирования и контроля выполнения задач',
      budget: 'Детальное планирование бюджета и контроль затрат',
      quality: 'Внедрение процессов контроля качества',
      resource: 'Оптимизация распределения и использования ресурсов',
      organizational: 'Улучшение организационных процессов и коммуникации',
      external: 'Мониторинг и адаптация к внешним факторам'
    };
    return descriptions[categoryId] || 'Общие меры по снижению риска';
  }

  private calculateCostImpact(risk: Partial<RiskFactor>): CostImpact {
    const baseImpact = (risk.impact?.budget || 50) / 100;
    const budget = 100000; // Примерный бюджет
    
    return {
      direct: budget * baseImpact * 0.7,
      indirect: budget * baseImpact * 0.3,
      opportunity: budget * baseImpact * 0.2,
      contingency: budget * baseImpact * 0.15,
      total: budget * baseImpact,
      currency: 'RUB'
    };
  }

  private calculateScheduleImpact(risk: Partial<RiskFactor>): ScheduleImpact {
    const baseImpact = (risk.impact?.schedule || 50) / 100;
    const criticalPathDelay = baseImpact * 10; // дней
    
    return {
      criticalPathDelay,
      totalDurationIncrease: baseImpact * 15,
      milestoneDelays: [],
      resourceOverallocation: baseImpact * 100 // часов
    };
  }

  private calculateQualityImpact(risk: Partial<RiskFactor>): QualityImpact {
    const baseImpact = (risk.impact?.quality || 50) / 100;
    
    return {
      functionalRequirements: baseImpact * 20,
      nonFunctionalRequirements: baseImpact * 15,
      testingGaps: baseImpact * 25,
      complianceIssues: baseImpact * 10,
      customerSatisfaction: 100 - baseImpact * 30
    };
  }

  private filterSignificantRisks(risks: RiskFactor[]): RiskFactor[] {
    return risks.filter(risk => 
      risk.probability >= 30 || 
      this.calculateRiskScore(risk) >= 50 ||
      risk.severity === 'critical'
    );
  }

  private calculateRiskScore(risk: RiskFactor): number {
    return (risk.probability + this.calculateImpactScore(risk.impact)) / 2;
  }

  private calculateImpactScore(impact: RiskImpact): number {
    return (impact.schedule + impact.budget + impact.scope + impact.quality + impact.risk) / 5;
  }

  private calculateOverallRiskScore(risks: RiskFactor[]): number {
    if (risks.length === 0) return 0;
    
    const totalScore = risks.reduce((sum, risk) => sum + this.calculateRiskScore(risk), 0);
    return Math.round(totalScore / risks.length);
  }

  private determineRiskLevel(risks: RiskFactor[]): RiskSeverity {
    const score = this.calculateOverallRiskScore(risks);
    
    if (score >= 80) return 'critical';
    if (score >= 60) return 'high';
    if (score >= 40) return 'medium';
    return 'low';
  }

  private analyzeRiskDistribution(risks: RiskFactor[]): RiskDistribution {
    const total = risks.length;
    
    return {
      byCategory: this.riskCategories.map(cat => ({
        category: cat.name,
        count: risks.filter(r => r.category.id === cat.id).length,
        percentage: total > 0 ? Math.round(risks.filter(r => r.category.id === cat.id).length / total * 100) : 0
      })),
      bySeverity: ['low', 'medium', 'high', 'critical'].map(sev => ({
        severity: sev as RiskSeverity,
        count: risks.filter(r => r.severity === sev).length,
        percentage: total > 0 ? Math.round(risks.filter(r => r.severity === sev).length / total * 100) : 0
      })),
      byLikelihood: [
        { range: '0-30%', count: risks.filter(r => r.probability <= 30).length, percentage: 0 },
        { range: '31-60%', count: risks.filter(r => r.probability > 30 && r.probability <= 60).length, percentage: 0 },
        { range: '61-80%', count: risks.filter(r => r.probability > 60 && r.probability <= 80).length, percentage: 0 },
        { range: '81-100%', count: risks.filter(r => r.probability > 80).length, percentage: 0 }
      ],
      byImpact: [
        { range: '0-30%', count: risks.filter(r => this.calculateImpactScore(r.impact) <= 30).length, percentage: 0 },
        { range: '31-60%', count: risks.filter(r => this.calculateImpactScore(r.impact) > 30 && this.calculateImpactScore(r.impact) <= 60).length, percentage: 0 },
        { range: '61-80%', count: risks.filter(r => this.calculateImpactScore(r.impact) > 60 && this.calculateImpactScore(r.impact) <= 80).length, percentage: 0 },
        { range: '81-100%', count: risks.filter(r => this.calculateImpactScore(r.impact) > 80).length, percentage: 0 }
      ]
    };
  }

  private getTopRisks(risks: RiskFactor[], limit: number): RiskFactor[] {
    return risks
      .sort((a, b) => this.calculateRiskScore(b) - this.calculateRiskScore(a))
      .slice(0, limit);
  }

  private identifyEmergingRisks(risks: RiskFactor[]): RiskFactor[] {
    // Риски с растущей вероятностью
    return risks.filter(risk => 
      risk.earlyWarning.some(indicator => indicator.trend === 'worsening') ||
      risk.timeToImpact && risk.timeToImpact < 30 // появятся в течение месяца
    );
  }

  private analyzeRiskTrends(risks: RiskFactor[]): RiskTrend[] {
    return risks.map(risk => ({
      riskId: risk.id,
      trend: this.determineTrend(risk),
      changeRate: this.calculateChangeRate(risk),
      factors: [],
      prediction: 'Стабильное состояние',
      timeHorizon: 30
    }));
  }

  private determineTrend(risk: RiskFactor): 'increasing' | 'stable' | 'decreasing' {
    const worseningIndicators = risk.earlyWarning.filter(i => i.trend === 'worsening').length;
    const improvingIndicators = risk.earlyWarning.filter(i => i.trend === 'improving').length;
    
    if (worseningIndicators > improvingIndicators) return 'increasing';
    if (improvingIndicators > worseningIndicators) return 'decreasing';
    return 'stable';
  }

  private calculateChangeRate(risk: RiskFactor): number {
    // Упрощенный расчет изменения риска
    return (risk.probability - 50) / 10; // базовая оценка
  }

  private analyzeByCategory(risks: RiskFactor[]): CategoryAnalysis[] {
    return this.riskCategories.map(category => {
      const categoryRisks = risks.filter(r => r.category.id === category.id);
      
      if (categoryRisks.length === 0) return null;
      
      return {
        category: category.name,
        riskCount: categoryRisks.length,
        avgProbability: categoryRisks.reduce((sum, r) => sum + r.probability, 0) / categoryRisks.length,
        avgImpact: categoryRisks.reduce((sum, r) => sum + this.calculateImpactScore(r.impact), 0) / categoryRisks.length,
        riskScore: this.calculateOverallRiskScore(categoryRisks),
        trends: [],
        recommendations: this.generateCategoryRecommendations(category.id)
      };
    }).filter(Boolean) as CategoryAnalysis[];
  }

  private generateCategoryRecommendations(categoryId: string): string[] {
    const recommendations: Record<string, string[]> = {
      technical: [
        'Провести техническую экспертизу',
        'Установить дополнительные контрольные точки',
        'Обеспечить техническую поддержку'
      ],
      schedule: [
        'Усилить контроль за выполнением задач',
        'Добавить буферное время',
        'Оптимизировать процессы планирования'
      ],
      budget: [
        'Усилить контроль затрат',
        'Создать резервный фонд',
        'Оптимизировать использование ресурсов'
      ]
    };
    
    return recommendations[categoryId] || ['Провести дополнительный анализ'];
  }

  private analyzeTimeBasedRisks(risks: RiskFactor[]): TimeBasedRisk[] {
    return [
      {
        timeframe: 'immediate',
        description: 'Риски, которые могут проявиться в ближайшее время',
        risks: risks.filter(r => r.timeToImpact && r.timeToImpact <= 7),
        probability: 70,
        impact: 60,
        preparationTime: 7
      },
      {
        timeframe: 'short_term',
        description: 'Риски, ожидаемые в ближайшие месяцы',
        risks: risks.filter(r => r.timeToImpact && r.timeToImpact > 7 && r.timeToImpact <= 90),
        probability: 60,
        impact: 70,
        preparationTime: 30
      }
    ];
  }

  private identifyCascadingRisks(risks: RiskFactor[]): CascadingRisk[] {
    return risks
      .filter(r => r.cascadingEffect)
      .map(risk => ({
        primaryRisk: risk.id,
        cascadePath: [],
        amplification: 50,
        probabilityOfCascade: risk.probability * 0.7
      }));
  }

  private generatePrioritizedActions(risks: RiskFactor[]): PrioritizedAction[] {
    const actions: PrioritizedAction[] = [];
    
    risks.slice(0, 5).forEach((risk, index) => {
      actions.push({
        action: `Митигация риска: ${risk.title}`,
        description: risk.description,
        priority: risk.severity,
        impact: this.calculateRiskScore(risk),
        effort: 50,
        timeframe: 14,
        owner: 'Project Manager',
        resources: ['Team Lead', 'Subject Matter Expert']
      });
    });
    
    return actions;
  }

  private generateResourceRecommendations(risks: RiskFactor[], context: RiskAnalysisContext): ResourceRecommendation[] {
    const recommendations: ResourceRecommendation[] = [];
    
    const highRiskCount = risks.filter(r => r.severity === 'high' || r.severity === 'critical').length;
    
    if (highRiskCount > 3) {
      recommendations.push({
        type: 'human',
        description: 'Добавить дополнительных специалистов для управления рисками',
        justification: `В проекте ${highRiskCount} высокорискованных проблем`,
        estimatedCost: 500000,
        expectedBenefit: 70,
        timeline: 30,
        priority: 'high'
      });
    }
    
    return recommendations;
  }

  private createMonitoringPlan(risks: RiskFactor[]): MonitoringPlan {
    return {
      frequency: 'weekly',
      metrics: ['Вероятность риска', 'Влияние на проект', 'Эффективность митигации'],
      reportingLevel: 'project',
      alertThresholds: risks.slice(0, 5).map(risk => ({
        metric: `risk_${risk.id}`,
        warningLevel: risk.probability * 1.2,
        criticalLevel: risk.probability * 1.5
      }))
    };
  }

  private calculateAnalysisConfidence(risks: RiskFactor[], context: RiskAnalysisContext): number {
    if (risks.length === 0) return 0;
    
    const avgConfidence = risks.reduce((sum, risk) => sum + risk.confidence, 0) / risks.length;
    const dataQuality = this.assessDataQuality(context);
    
    return Math.round((avgConfidence + dataQuality) / 2);
  }

  private assessDataQuality(context: RiskAnalysisContext): number {
    let score = 50;
    
    if (context.historical.projectHistory.length > 0) score += 15;
    if (context.current.taskProgress.length > 0) score += 15;
    if (context.current.issueLog.length > 0) score += 10;
    if (context.historical.teamPerformance) score += 10;
    
    return Math.min(100, score);
  }

  private identifyLimitations(context: RiskAnalysisContext): string[] {
    const limitations: string[] = [];
    
    if (context.historical.projectHistory.length < 3) {
      limitations.push('Недостаточно исторических данных для точного анализа');
    }
    
    if (context.environment.marketVolatility > 70) {
      limitations.push('Высокая неопределенность внешней среды снижает точность прогнозов');
    }
    
    if (context.project.complexity === 'very_high') {
      limitations.push('Высокая сложность проекта увеличивает неопределенность анализа');
    }
    
    return limitations;
  }

  private identifyAssumptions(context: RiskAnalysisContext): string[] {
    return [
      'Команда будет доступна в запланированном объеме',
      'Технологии будут работать в соответствии с документацией',
      'Внешние условия останутся стабильными',
      'Требования не изменятся кардинально',
      'Бюджет останется на текущем уровне'
    ];
  }

  /**
   * Создание отчета об анализе рисков
   */
  generateRiskReport(analysis: AIRiskAnalysisResult): string {
    let report = `# Отчет об анализе рисков проекта\n\n`;
    
    report += `## Общая оценка риска\n`;
    report += `- **Общий уровень риска**: ${analysis.riskLevel.toUpperCase()} (${analysis.overallRiskScore}%)\n`;
    report += `- **Уверенность в анализе**: ${analysis.confidence}%\n`;
    report += `- **Дата анализа**: ${analysis.analysisDate.toLocaleDateString('ru-RU')}\n\n`;
    
    report += `## Топ риски проекта\n`;
    analysis.topRisks.forEach((risk, index) => {
      report += `${index + 1}. **${risk.title}** (${risk.severity.toUpperCase()})\n`;
      report += `   - Вероятность: ${risk.probability}%\n`;
      report += `   - Описание: ${risk.description}\n\n`;
    });
    
    report += `## Распределение рисков\n`;
    analysis.riskDistribution.byCategory.forEach(cat => {
      report += `- **${cat.category}**: ${cat.count} рисков (${cat.percentage}%)\n`;
    });
    
    report += `\n## Рекомендуемые действия\n`;
    analysis.prioritizedActions.slice(0, 5).forEach((action, index) => {
      report += `${index + 1}. **${action.action}** (${action.priority.toUpperCase()})\n`;
      report += `   - Срок выполнения: ${action.timeframe} дней\n`;
      report += `   - Ожидаемое воздействие: ${action.impact}%\n\n`;
    });
    
    report += `---\n`;
    report += `*Отчет сгенерирован: ${new Date().toLocaleString('ru-RU')}*\n`;
    
    return report;
  }
}

// Экспорт под псевдонимом для обратной совместимости
export const RiskAnalysisService = AIRiskAnalysisService;

// Дополнительные интерфейсы для обратной совместимости
export interface RiskAnalysisReport {
  projectId: string;
  analysisDate: Date;
  risks: RiskFactor[];
  recommendations: string[];
  overallRisk: number;
  executiveSummary: string;
}