/**
 * Сервис автоматических отчетов для управления проектами
 * Обеспечивает генерацию отчетов о прогрессе, KPI dashboard,
 * автоматические напоминания и аналитику трендов
 */

export interface ReportTemplate {
  id: string;
  name: string;
  description: string;
  type: ReportType;
  category: ReportCategory;
  sections: ReportSection[];
  parameters: ReportParameter[];
  schedule?: ReportSchedule;
  recipients: ReportRecipient[];
  format: ReportFormat[];
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export type ReportType = 
  | 'progress' 
  | 'status' 
  | 'kpi' 
  | 'resource' 
  | 'financial' 
  | 'risk' 
  | 'timeline' 
  | 'quality' 
  | 'comprehensive'
  | 'executive'
  | 'custom';

export type ReportCategory = 
  | 'executive' 
  | 'management' 
  | 'team' 
  | 'stakeholder' 
  | 'technical' 
  | 'compliance'
  | 'audit';

export interface ReportSection {
  id: string;
  name: string;
  title: string;
  type: SectionType;
  position: number;
  width: number; // 1-12 (bootstrap grid)
  content: SectionContent;
  visibility: SectionVisibility;
  chartConfig?: ChartConfiguration;
}

export type SectionType = 
  | 'text' 
  | 'chart' 
  | 'table' 
  | 'metric' 
  | 'image' 
  | 'widget'
  | 'gantt'
  | 'timeline'
  | 'risk_matrix'
  | 'resource_allocation';

export interface SectionContent {
  dataSource: string;
  query?: string;
  aggregation?: 'count' | 'sum' | 'avg' | 'min' | 'max';
  filters?: Record<string, any>;
  orderBy?: string;
  limit?: number;
}

export interface SectionVisibility {
  show: boolean;
  roles: string[]; // роли, которым видна секция
  conditions?: VisibilityCondition[];
}

export interface VisibilityCondition {
  field: string;
  operator: 'equals' | 'not_equals' | 'greater_than' | 'less_than' | 'contains';
  value: any;
}

export interface ReportParameter {
  id: string;
  name: string;
  label: string;
  type: ParameterType;
  required: boolean;
  defaultValue: any;
  options?: ParameterOption[];
  validation?: ParameterValidation;
  description?: string;
}

export type ParameterType = 'text' | 'numeric' | 'datetime' | 'boolean' | 'select' | 'multiselect';

export interface ParameterOption {
  value: any;
  label: string;
}

export interface ParameterValidation {
  min?: number;
  max?: number;
  pattern?: string;
  custom?: (value: any) => boolean;
}

export interface ReportSchedule {
  frequency: ScheduleFrequency;
  cronExpression?: string;
  timezone: string;
  startDate: Date;
  endDate?: Date;
  daysOfWeek?: number[]; // 0-6, воскресенье = 0
  dayOfMonth?: number; // 1-31
  time: string; // HH:mm
  isActive: boolean;
}

export type ScheduleFrequency = 
  | 'realtime' 
  | 'hourly' 
  | 'daily' 
  | 'weekly' 
  | 'monthly' 
  | 'quarterly' 
  | 'annually'
  | 'custom';

export interface ReportRecipient {
  id: string;
  type: RecipientType;
  address: string;
  name?: string;
  role?: string;
  format: ReportFormat;
  language: string;
  timezone: string;
}

export type RecipientType = 'email' | 'slack' | 'teams' | 'webhook' | 'file';

export type ReportFormat = 'pdf' | 'html' | 'excel' | 'pptx' | 'json' | 'csv' | 'png' | 'svg';

export interface ChartConfiguration {
  type: ChartType;
  title?: string;
  data: ChartData;
  options: ChartOptions;
  position?: ChartPosition;
}

export type ChartType = 
  | 'line' 
  | 'bar' 
  | 'pie' 
  | 'doughnut' 
  | 'area' 
  | 'scatter' 
  | 'radar'
  | 'gauge'
  | 'heatmap'
  | 'treemap'
  | 'sankey'
  | 'funnel'
  | 'waterfall';

export interface ChartData {
  labels: string[];
  datasets: ChartDataset[];
}

export interface ChartDataset {
  label: string;
  data: number[];
  backgroundColor?: string | string[];
  borderColor?: string;
  borderWidth?: number;
  fill?: boolean;
}

export interface ChartOptions {
  responsive: boolean;
  maintainAspectRatio: boolean;
  scales?: ChartScales;
  plugins?: ChartPlugins;
  animation?: ChartAnimation;
  interaction?: ChartInteraction;
}

export interface ChartScales {
  x?: ChartScale;
  y?: ChartScale;
}

export interface ChartScale {
  type: 'linear' | 'logarithmic' | 'category' | 'time';
  position: 'top' | 'bottom' | 'left' | 'right';
  min?: number;
  max?: number;
  grid?: ChartGrid;
  ticks?: ChartTicks;
}

export interface ChartGrid {
  display: boolean;
  color?: string;
}

export interface ChartTicks {
  maxTicksLimit?: number;
  color?: string;
}

export interface ChartPlugins {
  legend?: ChartLegend;
  tooltip?: ChartTooltip;
  title?: ChartTitle;
}

export interface ChartLegend {
  display: boolean;
  position: 'top' | 'bottom' | 'left' | 'right';
}

export interface ChartTooltip {
  enabled: boolean;
  backgroundColor?: string;
  titleColor?: string;
  bodyColor?: string;
}

export interface ChartTitle {
  display: boolean;
  text: string;
  color?: string;
}

export interface ChartAnimation {
  duration: number;
  easing: 'linear' | 'easeInQuad' | 'easeOutQuad' | 'easeInOutQuad';
}

export interface ChartInteraction {
  mode: 'point' | 'nearest' | 'index' | 'dataset' | 'x' | 'y';
}

export interface ChartPosition {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface GeneratedReport {
  id: string;
  templateId: string;
  templateName: string;
  type: ReportType;
  title: string;
  generatedAt: Date;
  parameters: Record<string, any>;
  data: ReportData;
  summary: ReportSummary;
  format: ReportFormat;
  filePath?: string;
  fileSize?: number;
  status: ReportStatus;
  error?: string;
  executionTime: number; // milliseconds
  metadata: ReportMetadata;
}

export interface ReportData {
  sections: GeneratedSection[];
  rawData: Record<string, any>;
  aggregations: Record<string, any>;
  trends: TrendData[];
  insights: InsightData[];
}

export interface GeneratedSection {
  id: string;
  name: string;
  title: string;
  type: SectionType;
  content: any;
  chartData?: ChartData;
  metrics?: MetricData[];
  tableData?: TableData;
}

export interface MetricData {
  id: string;
  name: string;
  value: number | string;
  unit?: string;
  change?: number; // процент изменения
  trend: 'up' | 'down' | 'stable';
  target?: number;
  status: 'good' | 'warning' | 'critical';
}

export interface TableData {
  columns: TableColumn[];
  rows: any[];
  totalRows: number;
  pagination?: TablePagination;
}

export interface TableColumn {
  key: string;
  label: string;
  type: 'text' | 'numeric' | 'datetime' | 'boolean';
  sortable: boolean;
  format?: string;
}

export interface TablePagination {
  page: number;
  pageSize: number;
  totalPages: number;
  totalRows: number;
}

export interface ReportSummary {
  overallStatus: StatusLevel;
  keyMetrics: KeyMetric[];
  alerts: ReportAlert[];
  recommendations: string[];
  executiveSummary: string;
}

export type StatusLevel = 'excellent' | 'good' | 'warning' | 'critical';

export interface KeyMetric {
  name: string;
  value: number | string;
  unit?: string;
  target?: number;
  variance?: number; // отклонение от плана в %
  status: StatusLevel;
}

export interface ReportAlert {
  id: string;
  type: AlertType;
  severity: AlertSeverity;
  title: string;
  description: string;
  recommendation?: string;
  actionRequired: boolean;
  assignedTo?: string;
  dueDate?: Date;
}

export type AlertType = 'schedule' | 'budget' | 'quality' | 'resource' | 'risk' | 'compliance';
export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface InsightData {
  id: string;
  type: InsightType;
  title: string;
  description: string;
  confidence: number; // 0-100%
  impact: 'low' | 'medium' | 'high';
  category: InsightCategory;
  actionable: boolean;
}

export type InsightType = 'trend' | 'pattern' | 'anomaly' | 'prediction' | 'recommendation';
export type InsightCategory = 'performance' | 'efficiency' | 'quality' | 'risk' | 'opportunity';

export interface TrendData {
  metric: string;
  period: string;
  values: TrendValue[];
  trend: 'increasing' | 'decreasing' | 'stable';
  strength: number; // 0-100%
  forecast?: TrendValue[];
}

export interface TrendValue {
  date: Date;
  value: number;
  label?: string;
}

export interface ReportMetadata {
  projectId: string;
  generatedBy: string;
  version: string;
  environment: 'development' | 'staging' | 'production';
  dataSource: string;
  lastDataUpdate: Date;
  confidentiality: 'public' | 'internal' | 'confidential' | 'restricted';
  retentionPeriod?: number; // дней
}

export type ReportStatus = 'generating' | 'completed' | 'failed' | 'cancelled' | 'expired';

export interface KPI {
  id: string;
  name: string;
  description: string;
  category: KPICategory;
  unit: string;
  calculation: KPICalculation;
  target: number;
  thresholds: KPIThresholds;
  frequency: KPIFrequency;
  dataSource: string;
  isActive: boolean;
  owner: string;
}

export type KPICategory = 
  | 'schedule' 
  | 'quality' 
  | 'productivity' 
  | 'financial' 
  | 'customer' 
  | 'team' 
  | 'risk';

export interface KPICalculation {
  type: 'sum' | 'average' | 'count' | 'percentage' | 'ratio' | 'custom';
  formula?: string;
  parameters: Record<string, any>;
}

export interface KPIThresholds {
  excellent: number;
  good: number;
  warning: number;
  critical: number;
}

export type KPIFrequency = 'realtime' | 'hourly' | 'daily' | 'weekly' | 'monthly';

export interface KPIDashboard {
  id: string;
  name: string;
  description: string;
  layout: DashboardLayout;
  widgets: DashboardWidget[];
  filters: DashboardFilter[];
  isPublic: boolean;
  permissions: DashboardPermission[];
  refreshInterval: number;
}

export interface DashboardLayout {
  type: 'grid' | 'flex' | 'custom';
  columns: number;
  rows: number;
  gap: number;
  responsive: boolean;
}

export interface DashboardWidget {
  id: string;
  type: WidgetType;
  title: string;
  position: WidgetPosition;
  size: WidgetSize;
  config: WidgetConfig;
  dataSource: string;
}

export type WidgetType = 'kpi' | 'chart' | 'table' | 'gauge' | 'progress' | 'status';

export interface WidgetPosition {
  x: number;
  y: number;
  z?: number;
}

export interface WidgetSize {
  width: number;
  height: number;
  minWidth?: number;
  minHeight?: number;
  maxWidth?: number;
  maxHeight?: number;
}

export interface WidgetConfig {
  [key: string]: any;
}

export interface DashboardFilter {
  id: string;
  name: string;
  type: FilterType;
  field: string;
  operator: FilterOperator;
  value: any;
  options?: FilterOption[];
}

export type FilterType = 'select' | 'multiselect' | 'date' | 'daterange' | 'text' | 'number';
export type FilterOperator = 'equals' | 'not_equals' | 'contains' | 'starts_with' | 'greater_than' | 'less_than';

export interface FilterOption {
  value: any;
  label: string;
  count?: number;
}

export interface DashboardPermission {
  userId: string;
  role: string;
  permissions: Permission[];
}

export type Permission = 'view' | 'edit' | 'admin' | 'export';

export interface NotificationRule {
  id: string;
  name: string;
  description: string;
  trigger: NotificationTrigger;
  conditions: NotificationCondition[];
  recipients: NotificationRecipient[];
  template: NotificationTemplate;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface NotificationTrigger {
  type: TriggerType;
  schedule?: ScheduleFrequency;
  threshold?: number;
  event?: string;
}

export type TriggerType = 'threshold' | 'schedule' | 'event' | 'manual';

export interface NotificationCondition {
  field: string;
  operator: 'equals' | 'not_equals' | 'greater_than' | 'less_than' | 'contains';
  value: any;
  logicalOperator?: 'AND' | 'OR';
}

export interface NotificationRecipient {
  type: RecipientType;
  address: string;
  name?: string;
  role?: string;
}

export interface NotificationTemplate {
  subject: string;
  body: string;
  format: 'html' | 'text' | 'markdown';
  variables: TemplateVariable[];
  attachments?: TemplateAttachment[];
}

export interface TemplateVariable {
  name: string;
  description: string;
  required: boolean;
  defaultValue?: string;
}

export interface TemplateAttachment {
  type: 'report' | 'chart' | 'file';
  name: string;
  format: ReportFormat;
}

export interface ReportScheduler {
  id: string;
  name: string;
  description: string;
  templates: string[]; // template IDs
  schedule: ReportSchedule;
  priority: number; // 1-10
  status: 'active' | 'paused' | 'disabled';
  lastRun?: Date;
  nextRun: Date;
  runCount: number;
  successCount: number;
  failureCount: number;
  averageDuration: number; // milliseconds
}

export class AutomatedReportingService {
  private readonly reportTemplates = new Map<string, ReportTemplate>();
  private readonly generatedReports = new Map<string, GeneratedReport>();
  private readonly kpiDashboards = new Map<string, KPIDashboard>();
  private readonly notificationRules = new Map<string, NotificationRule>();
  private readonly schedulers = new Map<string, ReportScheduler>();

  constructor() {
    this.initializeDefaultTemplates();
    this.initializeKPIs();
  }

  /**
   * Инициализация шаблонов отчетов по умолчанию
   */
  private initializeDefaultTemplates(): void {
    // Шаблон отчета о прогрессе проекта
    const progressTemplate: ReportTemplate = {
      id: 'progress_report',
      name: 'Отчет о прогрессе проекта',
      description: 'Еженедельный отчет о состоянии выполнения проекта',
      type: 'progress',
      category: 'management',
      sections: [
        {
          id: 'summary',
          name: 'summary',
          title: 'Общая сводка',
          type: 'text',
          position: 1,
          width: 12,
          content: {
            dataSource: 'project_summary',
            query: 'SELECT * FROM project_status WHERE project_id = :projectId'
          },
          visibility: { show: true, roles: ['project_manager', 'stakeholder'] }
        },
        {
          id: 'kpi_dashboard',
          name: 'kpi_dashboard',
          title: 'Ключевые показатели',
          type: 'widget',
          position: 2,
          width: 12,
          content: {
            dataSource: 'kpi_metrics',
            query: 'SELECT * FROM kpi_metrics WHERE project_id = :projectId'
          },
          visibility: { show: true, roles: ['project_manager', 'executive'] },
          chartConfig: {
            type: 'gauge',
            title: 'Прогресс проекта',
            data: {
              labels: ['Выполнено'],
              datasets: [{
                label: 'Прогресс',
                data: [0], // будет заполнено динамически
                backgroundColor: ['#3b82f6']
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { display: false }
              }
            }
          }
        },
        {
          id: 'resource_utilization',
          name: 'resource_utilization',
          title: 'Загрузка ресурсов',
          type: 'chart',
          position: 3,
          width: 6,
          content: {
            dataSource: 'resource_metrics',
            query: 'SELECT resource_name, utilization FROM resource_metrics WHERE project_id = :projectId'
          },
          visibility: { show: true, roles: ['project_manager'] },
          chartConfig: {
            type: 'bar',
            title: 'Загрузка ресурсов (%)',
            data: { labels: [], datasets: [] },
            options: { responsive: true, maintainAspectRatio: false }
          }
        },
        {
          id: 'schedule_status',
          name: 'schedule_status',
          title: 'Статус графика',
          type: 'gantt',
          position: 4,
          width: 6,
          content: {
            dataSource: 'schedule_data',
            query: 'SELECT task_name, start_date, end_date, progress FROM tasks WHERE project_id = :projectId'
          },
          visibility: { show: true, roles: ['project_manager', 'team_lead'] }
        }
      ],
      parameters: [
        {
          id: 'projectId',
          name: 'projectId',
          label: 'ID проекта',
          type: 'text',
          required: true,
          defaultValue: ''
        },
        {
          id: 'period',
          name: 'period',
          label: 'Период',
          type: 'select',
          required: false,
          defaultValue: 'week',
          options: [
            { value: 'day', label: 'День' },
            { value: 'week', label: 'Неделя' },
            { value: 'month', label: 'Месяц' },
            { value: 'quarter', label: 'Квартал' }
          ]
        }
      ],
      schedule: {
        frequency: 'weekly',
        timezone: 'UTC',
        startDate: new Date(),
        daysOfWeek: [1], // Понедельник
        time: '09:00',
        isActive: true
      },
      recipients: [
        {
          id: 'default_pm',
          type: 'email',
          address: 'project-manager@company.com',
          format: 'pdf',
          language: 'ru',
          timezone: 'UTC'
        }
      ],
      format: ['pdf', 'html'],
      isActive: true,
      createdAt: new Date(),
      updatedAt: new Date()
    };

    this.reportTemplates.set(progressTemplate.id, progressTemplate);

    // Исполнительный отчет
    const executiveTemplate: ReportTemplate = {
      id: 'executive_summary',
      name: 'Исполнительное резюме',
      description: 'Краткий отчет для высшего руководства',
      type: 'executive',
      category: 'executive',
      sections: [
        {
          id: 'status_overview',
          name: 'status_overview',
          title: 'Обзор статуса',
          type: 'metric',
          position: 1,
          width: 12,
          content: {
            dataSource: 'executive_metrics',
            query: 'SELECT * FROM executive_dashboard WHERE project_id = :projectId'
          },
          visibility: { show: true, roles: ['executive', 'stakeholder'] }
        },
        {
          id: 'key_risks',
          name: 'key_risks',
          title: 'Основные риски',
          type: 'risk_matrix',
          position: 2,
          width: 12,
          content: {
            dataSource: 'risk_data',
            query: 'SELECT * FROM risks WHERE project_id = :projectId AND severity IN ("high", "critical")'
          },
          visibility: { show: true, roles: ['executive', 'project_manager'] }
        },
        {
          id: 'financial_status',
          name: 'financial_status',
          title: 'Финансовый статус',
          type: 'chart',
          position: 3,
          width: 6,
          content: {
            dataSource: 'financial_metrics',
            query: 'SELECT category, budget, spent, variance FROM financial_data WHERE project_id = :projectId'
          },
          visibility: { show: true, roles: ['executive', 'finance'] },
          chartConfig: {
            type: 'bar',
            title: 'Бюджет по категориям',
            data: { labels: [], datasets: [] },
            options: { responsive: true, maintainAspectRatio: false }
          }
        },
        {
          id: 'milestone_timeline',
          name: 'milestone_timeline',
          title: 'Временная шкала вех',
          type: 'timeline',
          position: 4,
          width: 6,
          content: {
            dataSource: 'milestone_data',
            query: 'SELECT name, date, status, description FROM milestones WHERE project_id = :projectId'
          },
          visibility: { show: true, roles: ['executive', 'stakeholder'] }
        }
      ],
      parameters: [
        {
          id: 'projectId',
          name: 'projectId',
          label: 'ID проекта',
          type: 'text',
          required: true,
          defaultValue: ''
        }
      ],
      recipients: [
        {
          id: 'executive_team',
          type: 'email',
          address: 'executives@company.com',
          format: 'pdf',
          language: 'ru',
          timezone: 'UTC'
        }
      ],
      format: ['pdf'],
      isActive: true,
      createdAt: new Date(),
      updatedAt: new Date()
    };

    this.reportTemplates.set(executiveTemplate.id, executiveTemplate);
  }

  /**
   * Инициализация KPI
   */
  private initializeKPIs(): void {
    const schedulePerformance: KPI = {
      id: 'schedule_performance',
      name: 'Производительность графика',
      description: 'Отношение фактического времени к плановому',
      category: 'schedule',
      unit: '%',
      calculation: {
        type: 'percentage',
        formula: '(planned_hours / actual_hours) * 100',
        parameters: {}
      },
      target: 100,
      thresholds: {
        excellent: 110,
        good: 100,
        warning: 90,
        critical: 75
      },
      frequency: 'weekly',
      dataSource: 'schedule_metrics',
      isActive: true,
      owner: 'project_manager'
    };

    const budgetVariance: KPI = {
      id: 'budget_variance',
      name: 'Отклонение от бюджета',
      description: 'Процентное отклонение от запланированного бюджета',
      category: 'financial',
      unit: '%',
      calculation: {
        type: 'percentage',
        formula: '((actual_cost - budget) / budget) * 100',
        parameters: {}
      },
      target: 0,
      thresholds: {
        excellent: -2,
        good: 5,
        warning: 10,
        critical: 20
      },
      frequency: 'weekly',
      dataSource: 'financial_metrics',
      isActive: true,
      owner: 'finance_manager'
    };

    const qualityScore: KPI = {
      id: 'quality_score',
      name: 'Показатель качества',
      description: 'Средний показатель качества выполненных работ',
      category: 'quality',
      unit: 'балл',
      calculation: {
        type: 'average',
        formula: 'AVG(quality_rating)',
        parameters: {}
      },
      target: 4.5,
      thresholds: {
        excellent: 4.8,
        good: 4.5,
        warning: 4.0,
        critical: 3.5
      },
      frequency: 'weekly',
      dataSource: 'quality_metrics',
      isActive: true,
      owner: 'quality_manager'
    };

    // Создание KPI dashboard
    const defaultDashboard: KPIDashboard = {
      id: 'project_executive_dashboard',
      name: 'Исполнительный Dashboard проекта',
      description: 'Основные KPI для высшего руководства',
      layout: {
        type: 'grid',
        columns: 3,
        rows: 2,
        gap: 16,
        responsive: true
      },
      widgets: [
        {
          id: 'schedule_kpi',
          type: 'kpi',
          title: 'Производительность графика',
          position: { x: 0, y: 0 },
          size: { width: 1, height: 1 },
          config: {
            kpiId: 'schedule_performance',
            showTrend: true,
            showTarget: true
          },
          dataSource: 'kpi_metrics'
        },
        {
          id: 'budget_kpi',
          type: 'kpi',
          title: 'Бюджет',
          position: { x: 1, y: 0 },
          size: { width: 1, height: 1 },
          config: {
            kpiId: 'budget_variance',
            showTrend: true,
            showTarget: true
          },
          dataSource: 'kpi_metrics'
        },
        {
          id: 'quality_kpi',
          type: 'kpi',
          title: 'Качество',
          position: { x: 2, y: 0 },
          size: { width: 1, height: 1 },
          config: {
            kpiId: 'quality_score',
            showTrend: true,
            showTarget: true
          },
          dataSource: 'kpi_metrics'
        },
        {
          id: 'progress_chart',
          type: 'chart',
          title: 'Прогресс по времени',
          position: { x: 0, y: 1 },
          size: { width: 2, height: 1 },
          config: {
            chartType: 'line',
            timeRange: '30d'
          },
          dataSource: 'progress_metrics'
        },
        {
          id: 'resource_gauge',
          type: 'gauge',
          title: 'Загрузка ресурсов',
          position: { x: 2, y: 1 },
          size: { width: 1, height: 1 },
          config: {
            gaugeType: 'semicircle',
            colorScheme: 'blue'
          },
          dataSource: 'resource_metrics'
        }
      ],
      filters: [
        {
          id: 'date_range',
          name: 'Период',
          type: 'daterange',
          field: 'date',
          operator: 'between',
          value: null
        },
        {
          id: 'project_filter',
          name: 'Проект',
          type: 'multiselect',
          field: 'project_id',
          operator: 'in',
          value: null,
          options: []
        }
      ],
      isPublic: false,
      permissions: [],
      refreshInterval: 300000 // 5 минут
    };

    this.kpiDashboards.set(defaultDashboard.id, defaultDashboard);
  }

  /**
   * Генерация отчета по шаблону
   */
  async generateReport(templateId: string, parameters: Record<string, any>): Promise<GeneratedReport> {
    const template = this.reportTemplates.get(templateId);
    if (!template) {
      throw new Error(`Шаблон отчета ${templateId} не найден`);
    }

    const startTime = Date.now();

    try {
      // Валидация параметров
      this.validateParameters(template, parameters);

      // Сбор данных для секций
      const sectionData = await this.collectSectionData(template.sections, parameters);

      // Создание отчета
      const report: GeneratedReport = {
        id: this.generateId(),
        templateId: template.id,
        templateName: template.name,
        type: template.type,
        title: `${template.name} - ${new Date().toLocaleDateString('ru-RU')}`,
        generatedAt: new Date(),
        parameters,
        data: sectionData,
        summary: await this.generateSummary(sectionData, template),
        format: template.format[0], // основной формат
        status: 'generating',
        executionTime: 0,
        metadata: {
          projectId: parameters.projectId || 'unknown',
          generatedBy: 'system',
          version: '1.0.0',
          environment: 'production',
          dataSource: 'primary',
          lastDataUpdate: new Date(),
          confidentiality: 'internal'
        }
      };

      // Симуляция обработки
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Завершение генерации
      report.status = 'completed';
      report.executionTime = Date.now() - startTime;

      this.generatedReports.set(report.id, report);

      return report;

    } catch (error) {
      const report: GeneratedReport = {
        id: this.generateId(),
        templateId: template.id,
        templateName: template.name,
        type: template.type,
        title: `${template.name} - ${new Date().toLocaleDateString('ru-RU')}`,
        generatedAt: new Date(),
        parameters,
        data: { sections: [], rawData: {}, aggregations: {}, trends: [], insights: [] },
        summary: {
          overallStatus: 'critical',
          keyMetrics: [],
          alerts: [],
          recommendations: [],
          executiveSummary: 'Ошибка генерации отчета'
        },
        format: template.format[0],
        status: 'failed',
        error: error instanceof Error ? error.message : 'Неизвестная ошибка',
        executionTime: Date.now() - startTime,
        metadata: {
          projectId: parameters.projectId || 'unknown',
          generatedBy: 'system',
          version: '1.0.0',
          environment: 'production',
          dataSource: 'primary',
          lastDataUpdate: new Date(),
          confidentiality: 'internal'
        }
      };

      this.generatedReports.set(report.id, report);
      return report;
    }
  }

  /**
   * Валидация параметров отчета
   */
  private validateParameters(template: ReportTemplate, parameters: Record<string, any>): void {
    for (const param of template.parameters) {
      if (param.required && (!parameters.hasOwnProperty(param.name) || parameters[param.name] === null || parameters[param.name] === '')) {
        throw new Error(`Обязательный параметр ${param.name} не задан`);
      }

      if (parameters.hasOwnProperty(param.name) && param.validation) {
        const value = parameters[param.name];
        
        if (param.type === 'number') {
          if (param.validation.min !== undefined && value < param.validation.min) {
            throw new Error(`Параметр ${param.name} меньше минимального значения ${param.validation.min}`);
          }
          if (param.validation.max !== undefined && value > param.validation.max) {
            throw new Error(`Параметр ${param.name} больше максимального значения ${param.validation.max}`);
          }
        }

        if (param.type === 'string' && param.validation.pattern) {
          const regex = new RegExp(param.validation.pattern);
          if (!regex.test(value)) {
            throw new Error(`Параметр ${param.name} не соответствует формату`);
          }
        }
      }
    }
  }

  /**
   * Сбор данных для секций отчета
   */
  private async collectSectionData(sections: ReportSection[], parameters: Record<string, any>): Promise<ReportData> {
    const sectionResults: GeneratedSection[] = [];
    const rawData: Record<string, any> = {};
    const aggregations: Record<string, any> = {};
    const trends: TrendData[] = [];
    const insights: InsightData[] = [];

    for (const section of sections) {
      const sectionResult = await this.processSection(section, parameters);
      sectionResults.push(sectionResult);

      // Сохранение данных
      rawData[section.id] = sectionResult.content;
      if (sectionResult.metrics) {
        sectionResult.metrics.forEach(metric => {
          aggregations[metric.name] = metric.value;
        });
      }
    }

    return {
      sections: sectionResults,
      rawData,
      aggregations,
      trends,
      insights
    };
  }

  /**
   * Обработка отдельной секции
   */
  private async processSection(section: ReportSection, parameters: Record<string, any>): Promise<GeneratedSection> {
    // Симуляция получения данных
    const mockData = this.generateMockData(section, parameters);

    switch (section.type) {
      case 'metric':
        return {
          id: section.id,
          name: section.name,
          title: section.title,
          type: section.type,
          content: mockData,
          metrics: this.generateMetrics(mockData)
        };

      case 'chart':
        return {
          id: section.id,
          name: section.name,
          title: section.title,
          type: section.type,
          content: mockData,
          chartData: this.generateChartData(section, mockData)
        };

      case 'table':
        return {
          id: section.id,
          name: section.name,
          title: section.title,
          type: section.type,
          content: mockData,
          tableData: this.generateTableData(mockData)
        };

      default:
        return {
          id: section.id,
          name: section.name,
          title: section.title,
          type: section.type,
          content: mockData
        };
    }
  }

  /**
   * Генерация мок-данных для секции
   */
  private generateMockData(section: ReportSection, parameters: Record<string, any>): any {
    switch (section.type) {
      case 'metric':
        return {
          value: Math.floor(Math.random() * 100),
          unit: '%',
          target: 85,
          change: (Math.random() - 0.5) * 20
        };

      case 'chart':
        return {
          labels: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
          datasets: [{
            label: 'Прогресс',
            data: [20, 35, 45, 60, 75, 85, 90],
            backgroundColor: '#3b82f6'
          }]
        };

      case 'table':
        return {
          columns: [
            { key: 'task', label: 'Задача', type: 'text', sortable: true },
            { key: 'status', label: 'Статус', type: 'text', sortable: true },
            { key: 'progress', label: 'Прогресс', type: 'numeric', sortable: true },
            { key: 'assignee', label: 'Исполнитель', type: 'text', sortable: true }
          ],
          rows: [
            { task: 'Анализ требований', status: 'Завершено', progress: 100, assignee: 'Иван' },
            { task: 'Проектирование', status: 'В работе', progress: 75, assignee: 'Мария' },
            { task: 'Разработка', status: 'Запланировано', progress: 0, assignee: 'Петр' }
          ],
          totalRows: 3
        };

      case 'gantt':
        return {
          tasks: [
            { name: 'Анализ требований', start: '2024-01-01', end: '2024-01-15', progress: 100 },
            { name: 'Проектирование', start: '2024-01-16', end: '2024-01-31', progress: 75 },
            { name: 'Разработка', start: '2024-02-01', end: '2024-02-28', progress: 25 }
          ]
        };

      case 'text':
        return {
          summary: 'Проект выполняется согласно плану. Основные вехи достигнуты в срок.',
          details: 'Детальная информация о текущем состоянии проекта...'
        };

      default:
        return { message: `Данные для секции ${section.name}` };
    }
  }

  /**
   * Генерация метрик
   */
  private generateMetrics(data: any): MetricData[] {
    return [
      {
        id: 'progress',
        name: 'Общий прогресс',
        value: data.value || 0,
        unit: data.unit || '%',
        change: data.change || 0,
        trend: (data.change || 0) > 0 ? 'up' : (data.change || 0) < 0 ? 'down' : 'stable',
        target: data.target || 100,
        status: (data.value || 0) >= (data.target || 100) ? 'good' : 'warning'
      },
      {
        id: 'deadline',
        name: 'Дней до дедлайна',
        value: 45,
        unit: 'дней',
        trend: 'stable',
        status: 'good'
      },
      {
        id: 'budget_usage',
        name: 'Использование бюджета',
        value: 68,
        unit: '%',
        target: 70,
        status: 'good'
      }
    ];
  }

  /**
   * Генерация данных для графика
   */
  private generateChartData(section: ReportSection, data: any): ChartData {
    if (section.chartConfig) {
      return {
        labels: data.labels || [],
        datasets: data.datasets || []
      };
    }

    return {
      labels: ['Данные 1', 'Данные 2', 'Данные 3'],
      datasets: [{
        label: section.title,
        data: [Math.random() * 100, Math.random() * 100, Math.random() * 100],
        backgroundColor: '#3b82f6'
      }]
    };
  }

  /**
   * Генерация табличных данных
   */
  private generateTableData(data: any): TableData {
    return {
      columns: data.columns || [],
      rows: data.rows || [],
      totalRows: data.totalRows || 0,
      pagination: {
        page: 1,
        pageSize: 10,
        totalPages: Math.ceil((data.totalRows || 0) / 10),
        totalRows: data.totalRows || 0
      }
    };
  }

  /**
   * Генерация резюме отчета
   */
  private async generateSummary(data: ReportData, template: ReportTemplate): Promise<ReportSummary> {
    // Анализ общего статуса
    const allMetrics = data.sections.flatMap(s => s.metrics || []);
    const avgStatus = this.calculateOverallStatus(allMetrics);

    // Формирование ключевых метрик
    const keyMetrics: KeyMetric[] = allMetrics.map(metric => ({
      name: metric.name,
      value: metric.value,
      unit: metric.unit,
      target: metric.target,
      variance: metric.target ? ((+metric.value - metric.target) / metric.target) * 100 : undefined,
      status: metric.status
    }));

    // Генерация алертов
    const alerts: ReportAlert[] = allMetrics
      .filter(metric => metric.status === 'critical' || metric.status === 'warning')
      .map(metric => ({
        id: this.generateId(),
        type: 'schedule',
        severity: metric.status === 'critical' ? 'high' : 'medium',
        title: `Внимание: ${metric.name}`,
        description: `Метрика ${metric.name} имеет статус ${metric.status}`,
        actionRequired: metric.status === 'critical',
        assignedTo: 'project_manager'
      }));

    // Рекомендации
    const recommendations = this.generateRecommendations(allMetrics);

    // Исполнительное резюме
    const executiveSummary = this.generateExecutiveSummary(avgStatus, keyMetrics);

    return {
      overallStatus: avgStatus,
      keyMetrics,
      alerts,
      recommendations,
      executiveSummary
    };
  }

  /**
   * Расчет общего статуса
   */
  private calculateOverallStatus(metrics: MetricData[]): StatusLevel {
    if (metrics.length === 0) return 'good';

    const statusCounts = {
      good: metrics.filter(m => m.status === 'good').length,
      warning: metrics.filter(m => m.status === 'warning').length,
      critical: metrics.filter(m => m.status === 'critical').length
    };

    if (statusCounts.critical > 0) return 'critical';
    if (statusCounts.warning > statusCounts.good) return 'warning';
    return 'good';
  }

  /**
   * Генерация рекомендаций
   */
  private generateRecommendations(metrics: MetricData[]): string[] {
    const recommendations: string[] = [];

    const lowProgressMetrics = metrics.filter(m => 
      typeof m.value === 'number' && 
      m.target && 
      +m.value < m.target * 0.8
    );

    if (lowProgressMetrics.length > 0) {
      recommendations.push('Рассмотреть увеличение ресурсов для ускорения прогресса');
    }

    const overdueMetrics = metrics.filter(m => 
      m.trend === 'down' && 
      typeof m.value === 'number'
    );

    if (overdueMetrics.length > 0) {
      recommendations.push('Принять меры по улучшению показателей с негативным трендом');
    }

    if (recommendations.length === 0) {
      recommendations.push('Проект идет в соответствии с планом');
    }

    return recommendations;
  }

  /**
   * Генерация исполнительного резюме
   */
  private generateExecutiveSummary(status: StatusLevel, metrics: KeyMetric[]): string {
    const statusText = {
      excellent: 'отличное',
      good: 'хорошее',
      warning: 'требует внимания',
      critical: 'критическое'
    }[status];

    const summary = `Общее состояние проекта оценивается как ${statusText}. `;

    if (metrics.length > 0) {
      const topMetric = metrics[0];
      summary += `Ключевой показатель "${topMetric.name}" составляет ${topMetric.value}${topMetric.unit || ''}.`;
    }

    return summary;
  }

  /**
   * Создание нового шаблона отчета
   */
  async createTemplate(template: Omit<ReportTemplate, 'id' | 'createdAt' | 'updatedAt'>): Promise<ReportTemplate> {
    const newTemplate: ReportTemplate = {
      ...template,
      id: this.generateId(),
      createdAt: new Date(),
      updatedAt: new Date()
    };

    this.reportTemplates.set(newTemplate.id, newTemplate);
    return newTemplate;
  }

  /**
   * Обновление шаблона отчета
   */
  async updateTemplate(templateId: string, updates: Partial<ReportTemplate>): Promise<ReportTemplate> {
    const template = this.reportTemplates.get(templateId);
    if (!template) {
      throw new Error(`Шаблон ${templateId} не найден`);
    }

    const updatedTemplate = {
      ...template,
      ...updates,
      updatedAt: new Date()
    };

    this.reportTemplates.set(templateId, updatedTemplate);
    return updatedTemplate;
  }

  /**
   * Получение списка шаблонов
   */
  getTemplates(): ReportTemplate[] {
    return Array.from(this.reportTemplates.values());
  }

  /**
   * Получение отчета по ID
   */
  getReport(reportId: string): GeneratedReport | undefined {
    return this.generatedReports.get(reportId);
  }

  /**
   * Получение списка сгенерированных отчетов
   */
  getReports(projectId?: string): GeneratedReport[] {
    let reports = Array.from(this.generatedReports.values());
    
    if (projectId) {
      reports = reports.filter(r => r.metadata.projectId === projectId);
    }
    
    return reports.sort((a, b) => b.generatedAt.getTime() - a.generatedAt.getTime());
  }

  /**
   * Генерация уникального ID
   */
  private generateId(): string {
    return `report_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Планирование отчетов
   */
  scheduleReports(): void {
    // Здесь была бы логика планировщика для автоматической генерации отчетов
    console.log('Планировщик отчетов инициализирован');
  }

  /**
   * Создание отчета в различных форматах
   */
  async exportReport(reportId: string, format: ReportFormat): Promise<string> {
    const report = this.generatedReports.get(reportId);
    if (!report) {
      throw new Error(`Отчет ${reportId} не найден`);
    }

    // Симуляция экспорта
    switch (format) {
      case 'pdf':
        return `/exports/report_${reportId}.pdf`;
      case 'html':
        return `/exports/report_${reportId}.html`;
      case 'excel':
        return `/exports/report_${reportId}.xlsx`;
      default:
        throw new Error(`Формат ${format} не поддерживается`);
    }
  }
}

/**
 * KPI проекта для автоматических отчетов
 */
export interface ProjectKPIs {
  projectId: string;
  projectName: string;
  period: {
    startDate: Date;
    endDate: Date;
  };
  metrics: ProjectMetric[];
  trends: ProjectTrend[];
  targets: ProjectTarget[];
  alerts: ProjectAlert[];
  overallScore: number;
  status: 'excellent' | 'good' | 'warning' | 'critical';
  generatedAt: Date;
}

export interface ProjectMetric {
  id: string;
  name: string;
  value: number | string;
  unit?: string;
  target: number;
  actual: number;
  variance: number; // percentage
  status: 'on-track' | 'at-risk' | 'off-track';
  trend: 'improving' | 'stable' | 'declining';
  category: 'schedule' | 'budget' | 'quality' | 'resources' | 'stakeholder';
}

export interface ProjectTrend {
  metricId: string;
  period: string;
  values: TrendValue[];
  forecast?: TrendValue[];
  trend: 'increasing' | 'decreasing' | 'stable';
  strength: number; // 0-100%
}

export interface ProjectTarget {
  metricId: string;
  targetValue: number;
  targetDate: Date;
  probability: number; // 0-100%
  confidence: number; // 0-100%
  assumptions: string[];
}

export interface ProjectAlert {
  id: string;
  type: 'threshold' | 'trend' | 'schedule' | 'budget' | 'quality';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  metricId?: string;
  currentValue: number;
  thresholdValue: number;
  recommendedActions: string[];
  dueDate?: Date;
}