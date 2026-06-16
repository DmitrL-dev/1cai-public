/**
 * Сервис обнаружения аномалий для 1C данных
 * Поддерживает различные алгоритмы обнаружения аномалий в данных и системах
 */

export interface AnomalyDetectionJob {
  id: string;
  name: string;
  description?: string;
  dataSource: DataSourceConfig;
  algorithm: AnomalyAlgorithm;
  parameters: AlgorithmParameters;
  threshold: number;
  status: 'active' | 'paused' | 'disabled';
  createdAt: Date;
  lastScan?: Date;
  nextScan?: Date;
  statistics: JobStatistics;
  alerts: AlertConfiguration[];
}

export interface DataSourceConfig {
  type: 'database' | 'file' | 'api' | 'stream';
  connection: DataConnection;
  tableName?: string;
  fields: string[];
  filters?: DataFilter[];
  samplingRate?: number;
}

export interface DataConnection {
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  password?: string;
  filePath?: string;
  apiEndpoint?: string;
  apiKey?: string;
  ssl?: boolean;
}

export interface DataFilter {
  field: string;
  operator: 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'like' | 'in';
  value: any;
}

export interface AnomalyAlgorithm {
  type: 'statistical' | 'machine_learning' | 'rule_based' | 'time_series' | 'pattern_based';
  name: string;
  description: string;
  supportedDataTypes: string[];
  parameters: AlgorithmParameters;
}

export interface AlgorithmParameters {
  [key: string]: any;
}

export interface AnomalyResult {
  id: string;
  jobId: string;
  timestamp: Date;
  anomalyType: AnomalyType;
  severity: 'low' | 'medium' | 'high' | 'critical';
  confidence: number;
  description: string;
  affectedRecords: AnomalyRecord[];
  metrics: AnomalyMetrics;
  recommendations: string[];
  resolved: boolean;
  resolvedAt?: Date;
  resolvedBy?: string;
}

export type AnomalyType = 
  | 'value_outlier'
  | 'pattern_deviation'
  | 'frequency_anomaly'
  | 'correlation_break'
  | 'trend_anomaly'
  | 'volume_spike'
  | 'behavior_change'
  | 'data_quality'
  | 'system_performance'
  | 'business_rule_violation';

export interface AnomalyRecord {
  id: string;
  field: string;
  originalValue: any;
  expectedValue?: any;
  deviation: number;
  zScore?: number;
  percentile?: number;
  timestamp: Date;
}

export interface AnomalyMetrics {
  affectedFields: string[];
  impactScore: number;
  dataVolume: number;
  statisticalSignificance: number;
  businessImpact: BusinessImpact;
}

export interface BusinessImpact {
  level: 'minimal' | 'moderate' | 'significant' | 'severe';
  description: string;
  estimatedCost?: number;
  affectedProcesses: string[];
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
}

export interface AlertConfiguration {
  id: string;
  type: 'email' | 'sms' | 'webhook' | 'slack' | 'teams';
  enabled: boolean;
  triggers: AlertTrigger[];
  recipients: string[];
  template: AlertTemplate;
}

export interface AlertTrigger {
  condition: 'severity' | 'confidence' | 'frequency' | 'business_impact';
  operator: 'gte' | 'lte' | 'eq' | 'ne';
  value: any;
  timeWindow?: number; // minutes
}

export interface AlertTemplate {
  subject: string;
  message: string;
  includeDetails: boolean;
  includeRecommendations: boolean;
}

export interface JobStatistics {
  totalScans: number;
  anomaliesDetected: number;
  anomaliesResolved: number;
  avgDetectionTime: number;
  accuracy: number;
  falsePositives: number;
  lastAnomalyTime?: Date;
  mostCommonAnomalyTypes: { type: AnomalyType; count: number }[];
}

export interface AnomalyPattern {
  id: string;
  name: string;
  description: string;
  pattern: any;
  threshold: number;
  context: PatternContext;
  learningPeriod: number; // days
  lastUpdate: Date;
}

export interface PatternContext {
  timeOfDay?: TimePattern;
  dayOfWeek?: DayPattern;
  seasonal?: SeasonalPattern;
  business?: BusinessContext;
}

export interface TimePattern {
  hours: number[];
  timezone: string;
}

export interface DayPattern {
  days: number[]; // 0-6, Sunday = 0
}

export interface SeasonalPattern {
  period: 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'yearly';
  strength: number;
}

export interface BusinessContext {
  businessHours: { start: string; end: string }[];
  holidays: string[];
  peakSeasons: string[];
  lowSeasons: string[];
}

export class AnomalyDetectionService {
  private jobs: Map<string, AnomalyDetectionJob> = new Map();
  private results: Map<string, AnomalyResult[]> = new Map();
  private patterns: Map<string, AnomalyPattern> = new Map();
  private algorithms: Map<string, AnomalyAlgorithm> = new Map();

  constructor() {
    this.initializeAlgorithms();
    this.initializeSampleJobs();
  }

  /**
   * Инициализация алгоритмов обнаружения аномалий
   */
  private initializeAlgorithms(): void {
    // Статистические методы
    this.algorithms.set('zscore', {
      type: 'statistical',
      name: 'Z-Score',
      description: 'Обнаружение аномалий на основе статистических отклонений',
      supportedDataTypes: ['numeric'],
      parameters: {
        threshold: 3,
        minDataPoints: 30,
        robust: false
      }
    });

    this.algorithms.set('iqr', {
      type: 'statistical',
      name: 'Interquartile Range',
      description: 'Использует межквартильный размах для определения выбросов',
      supportedDataTypes: ['numeric'],
      parameters: {
        multiplier: 1.5,
        minDataPoints: 20
      }
    });

    // Машинное обучение
    this.algorithms.set('isolation_forest', {
      type: 'machine_learning',
      name: 'Isolation Forest',
      description: 'Алгогоритм машинного обучения для обнаружения аномалий',
      supportedDataTypes: ['numeric', 'categorical'],
      parameters: {
        nEstimators: 100,
        contamination: 0.1,
        maxFeatures: 1.0,
        randomState: 42
      }
    });

    this.algorithms.set('local_outlier', {
      type: 'machine_learning',
      name: 'Local Outlier Factor',
      description: 'Локальный алгоритм обнаружения выбросов',
      supportedDataTypes: ['numeric'],
      parameters: {
        nNeighbors: 20,
        contamination: 0.1,
        metric: 'minkowski'
      }
    });

    // Правила
    this.algorithms.set('business_rules', {
      type: 'rule_based',
      name: 'Business Rules',
      description: 'Обнаружение аномалий на основе бизнес-правил',
      supportedDataTypes: ['numeric', 'categorical', 'datetime'],
      parameters: {
        rules: [],
        strictMode: false
      }
    });

    // Временные ряды
    this.algorithms.set('time_series_ewma', {
      type: 'time_series',
      name: 'Exponentially Weighted Moving Average',
      description: 'Обнаружение аномалий во временных рядах',
      supportedDataTypes: ['numeric', 'datetime'],
      parameters: {
        alpha: 0.3,
        threshold: 2,
        minDataPoints: 50
      }
    });

    // Паттерны
    this.algorithms.set('pattern_matching', {
      type: 'pattern_based',
      name: 'Pattern Matching',
      description: 'Обнаружение аномалий по отклонениям от известных паттернов',
      supportedDataTypes: ['numeric', 'categorical', 'datetime'],
      parameters: {
        patternLength: 24, // часы
        similarityThreshold: 0.8,
        minOccurrences: 5
      }
    });
  }

  /**
   * Инициализация образцовых заданий
   */
  private initializeSampleJobs(): void {
    // Мониторинг продаж
    const salesMonitoringJob: AnomalyDetectionJob = {
      id: this.generateId(),
      name: 'Мониторинг аномалий продаж',
      description: 'Обнаружение аномальных паттернов в данных о продажах',
      dataSource: {
        type: 'database',
        connection: {
          host: '1c-server',
          database: 'sales_db',
          username: 'etl_user'
        },
        tableName: 'sales_transactions',
        fields: ['amount', 'quantity', 'customer_id', 'timestamp'],
        samplingRate: 1.0
      },
      algorithm: this.algorithms.get('time_series_ewma')!,
      parameters: {
        alpha: 0.3,
        threshold: 2.5,
        minDataPoints: 100
      },
      threshold: 0.8,
      status: 'active',
      createdAt: new Date(),
      lastScan: new Date(Date.now() - 60 * 60 * 1000),
      nextScan: new Date(Date.now() + 30 * 60 * 1000),
      statistics: {
        totalScans: 1440,
        anomaliesDetected: 23,
        anomaliesResolved: 20,
        avgDetectionTime: 5000,
        accuracy: 92.3,
        falsePositives: 3,
        lastAnomalyTime: new Date(Date.now() - 4 * 60 * 60 * 1000),
        mostCommonAnomalyTypes: [
          { type: 'volume_spike', count: 8 },
          { type: 'pattern_deviation', count: 7 },
          { type: 'value_outlier', count: 5 }
        ]
      },
      alerts: [
        {
          id: this.generateId(),
          type: 'email',
          enabled: true,
          triggers: [
            { condition: 'severity', operator: 'gte', value: 'high' }
          ],
          recipients: ['admin@company.com', 'sales-manager@company.com'],
          template: {
            subject: '🚨 Обнаружена аномалия в продажах: {{severity}}',
            message: 'Обнаружена аномалия {{anomalyType}} с уровнем важности {{severity}}. Описание: {{description}}',
            includeDetails: true,
            includeRecommendations: true
          }
        }
      ]
    };

    this.jobs.set(salesMonitoringJob.id, salesMonitoringJob);

    // Мониторинг производственных данных
    const productionMonitoringJob: AnomalyDetectionJob = {
      id: this.generateId(),
      name: 'Контроль производственных показателей',
      description: 'Обнаружение отклонений в производственных метриках',
      dataSource: {
        type: 'database',
        connection: {
          host: 'production-db',
          database: 'production_metrics'
        },
        tableName: 'machine_sensors',
        fields: ['temperature', 'pressure', 'vibration', 'efficiency', 'timestamp'],
        samplingRate: 0.1 // 10% выборка
      },
      algorithm: this.algorithms.get('isolation_forest')!,
      parameters: {
        nEstimators: 100,
        contamination: 0.05,
        maxFeatures: 0.8
      },
      threshold: 0.9,
      status: 'active',
      createdAt: new Date(),
      lastScan: new Date(Date.now() - 15 * 60 * 1000),
      nextScan: new Date(Date.now() + 45 * 60 * 1000),
      statistics: {
        totalScans: 2880,
        anomaliesDetected: 12,
        anomaliesResolved: 11,
        avgDetectionTime: 3000,
        accuracy: 95.1,
        falsePositives: 1,
        lastAnomalyTime: new Date(Date.now() - 2 * 60 * 60 * 1000),
        mostCommonAnomalyTypes: [
          { type: 'value_outlier', count: 6 },
          { type: 'system_performance', count: 4 },
          { type: 'pattern_deviation', count: 2 }
        ]
      },
      alerts: [
        {
          id: this.generateId(),
          type: 'slack',
          enabled: true,
          triggers: [
            { condition: 'confidence', operator: 'gte', value: 0.8 }
          ],
          recipients: ['#production-alerts'],
          template: {
            subject: 'Производственная аномалия',
            message: 'Аномалия в производственных данных: {{description}}',
            includeDetails: true,
            includeRecommendations: true
          }
        }
      ]
    };

    this.jobs.set(productionMonitoringJob.id, productionMonitoringJob);

    // Мониторинг качества данных
    const dataQualityJob: AnomalyDetectionJob = {
      id: this.generateId(),
      name: 'Контроль качества данных',
      description: 'Обнаружение проблем с качеством данных в 1C',
      dataSource: {
        type: 'database',
        connection: {
          database: '1c_data_quality'
        },
        fields: ['completeness_score', 'accuracy_score', 'consistency_score', 'validation_errors'],
        filters: [
          { field: 'table_name', operator: 'in', value: ['customers', 'products', 'orders'] }
        ]
      },
      algorithm: this.algorithms.get('business_rules')!,
      parameters: {
        rules: [
          { field: 'completeness_score', operator: 'lt', value: 95 },
          { field: 'accuracy_score', operator: 'lt', value: 98 },
          { field: 'validation_errors', operator: 'gt', value: 10 }
        ],
        strictMode: true
      },
      threshold: 0.85,
      status: 'active',
      createdAt: new Date(),
      lastScan: new Date(Date.now() - 2 * 60 * 60 * 1000),
      nextScan: new Date(Date.now() + 22 * 60 * 60 * 1000),
      statistics: {
        totalScans: 720,
        anomaliesDetected: 8,
        anomaliesResolved: 7,
        avgDetectionTime: 2000,
        accuracy: 88.9,
        falsePositives: 2,
        mostCommonAnomalyTypes: [
          { type: 'data_quality', count: 5 },
          { type: 'business_rule_violation', count: 3 }
        ]
      },
      alerts: [
        {
          id: this.generateId(),
          type: 'email',
          enabled: true,
          triggers: [
            { condition: 'business_impact', operator: 'gte', value: 'significant' }
          ],
          recipients: ['data-team@company.com'],
          template: {
            subject: '⚠️ Проблема с качеством данных',
            message: 'Обнаружена проблема с качеством данных: {{description}}',
            includeDetails: true,
            includeRecommendations: true
          }
        }
      ]
    };

    this.jobs.set(dataQualityJob.id, dataQualityJob);
  }

  /**
   * Создание нового задания обнаружения аномалий
   */
  createJob(name: string, description?: string): string {
    const jobId = this.generateId();
    
    const job: AnomalyDetectionJob = {
      id: jobId,
      name,
      description,
      dataSource: { type: 'database', connection: {}, fields: [] },
      algorithm: this.algorithms.get('zscore')!,
      parameters: { threshold: 3 },
      threshold: 0.8,
      status: 'disabled',
      createdAt: new Date(),
      statistics: {
        totalScans: 0,
        anomaliesDetected: 0,
        anomaliesResolved: 0,
        avgDetectionTime: 0,
        accuracy: 0,
        falsePositives: 0,
        mostCommonAnomalyTypes: []
      },
      alerts: []
    };

    this.jobs.set(jobId, job);
    return jobId;
  }

  /**
   * Настройка источника данных
   */
  setDataSource(jobId: string, source: DataSourceConfig): boolean {
    const job = this.jobs.get(jobId);
    if (!job) return false;

    job.dataSource = source;
    this.jobs.set(jobId, job);
    return true;
  }

  /**
   * Настройка алгоритма
   */
  setAlgorithm(jobId: string, algorithmName: string): boolean {
    const job = this.jobs.get(jobId);
    if (!job) return false;

    const algorithm = this.algorithms.get(algorithmName);
    if (!algorithm) return false;

    job.algorithm = algorithm;
    this.jobs.set(jobId, job);
    return true;
  }

  /**
   * Обновление параметров алгоритма
   */
  updateAlgorithmParameters(jobId: string, parameters: AlgorithmParameters): boolean {
    const job = this.jobs.get(jobId);
    if (!job) return false;

    job.parameters = { ...job.parameters, ...parameters };
    job.algorithm.parameters = job.parameters;
    this.jobs.set(jobId, job);
    return true;
  }

  /**
   * Добавление предупреждения
   */
  addAlert(jobId: string, alert: Omit<AlertConfiguration, 'id'>): string {
    const job = this.jobs.get(jobId);
    if (!job) throw new Error('Задание не найдено');

    const alertId = this.generateId();
    const newAlert: AlertConfiguration = {
      ...alert,
      id: alertId
    };

    job.alerts.push(newAlert);
    this.jobs.set(jobId, job);

    return alertId;
  }

  /**
   * Запуск сканирования аномалий
   */
  async runScan(jobId: string): Promise<string> {
    const job = this.jobs.get(jobId);
    if (!job) throw new Error('Задание не найдено');
    if (job.status !== 'active') throw new Error('Задание не активно');

    const scanId = this.generateId();
    
    // Запуск сканирования в фоне
    this.performScan(jobId, scanId).catch(console.error);

    // Обновление времени последнего сканирования
    job.lastScan = new Date();
    this.jobs.set(jobId, job);

    return scanId;
  }

  /**
   * Выполнение сканирования
   */
  private async performScan(jobId: string, scanId: string): Promise<void> {
    const job = this.jobs.get(jobId);
    if (!job) return;

    try {
      const startTime = Date.now();

      // Получение данных
      const data = await this.fetchData(job.dataSource);
      
      // Применение алгоритма обнаружения аномалий
      const anomalies = await this.detectAnomalies(job, data);
      
      // Обработка найденных аномалий
      for (const anomaly of anomalies) {
        await this.processAnomaly(jobId, anomaly);
      }

      const detectionTime = Date.now() - startTime;
      
      // Обновление статистики
      this.updateJobStatistics(jobId, anomalies.length, detectionTime);

    } catch (error) {
      console.error(`Ошибка сканирования для задания ${jobId}:`, error);
    }
  }

  /**
   * Получение данных из источника
   */
  private async fetchData(source: DataSourceConfig): Promise<any[]> {
    switch (source.type) {
      case 'database':
        return this.fetchFromDatabase(source);
      case 'file':
        return this.fetchFromFile(source);
      case 'api':
        return this.fetchFromAPI(source);
      case 'stream':
        return this.fetchFromStream(source);
      default:
        throw new Error(`Неподдерживаемый тип источника: ${source.type}`);
    }
  }

  /**
   * Получение данных из базы данных
   */
  private async fetchFromDatabase(source: DataSourceConfig): Promise<any[]> {
    // Симуляция получения данных из БД
    await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 2000));

    const sampleSize = 100 + Math.floor(Math.random() * 900);
    
    return Array.from({ length: sampleSize }, (_, index) => {
      const record: any = {
        id: index + 1,
        timestamp: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000)
      };

      // Генерация значений полей
      source.fields.forEach(field => {
        if (field.includes('amount') || field.includes('value') || field.includes('score')) {
          record[field] = this.generateNumericValue(field);
        } else if (field.includes('id')) {
          record[field] = `ID_${index + 1}`;
        } else if (field.includes('timestamp') || field.includes('date')) {
          record[field] = new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000);
        } else {
          record[field] = this.generateCategoricalValue(field);
        }
      });

      return record;
    });
  }

  /**
   * Получение данных из файла
   */
  private async fetchFromFile(source: DataSourceConfig): Promise<any[]> {
    await new Promise(resolve => setTimeout(resolve, 800 + Math.random() * 1200));
    
    const sampleSize = 50 + Math.floor(Math.random() * 450);
    
    return Array.from({ length: sampleSize }, (_, index) => ({
      id: index + 1,
      filename: source.connection.filePath || 'unknown.csv',
      line_number: index + 1,
      data: `row_${index + 1}`,
      processed_at: new Date()
    }));
  }

  /**
   * Получение данных из API
   */
  private async fetchFromAPI(source: DataSourceConfig): Promise<any[]> {
    await new Promise(resolve => setTimeout(resolve, 1500 + Math.random() * 2500));
    
    const sampleSize = 80 + Math.floor(Math.random() * 120);
    
    return Array.from({ length: sampleSize }, (_, index) => ({
      id: index + 1,
      api_endpoint: source.connection.apiEndpoint || 'unknown',
      response_time: Math.random() * 1000,
      status_code: [200, 404, 500][Math.floor(Math.random() * 3)],
      timestamp: new Date()
    }));
  }

  /**
   * Получение данных из потока
   */
  private async fetchFromStream(source: DataSourceConfig): Promise<any[]> {
    await new Promise(resolve => setTimeout(resolve, 500 + Math.random() * 1000));
    
    const sampleSize = 30 + Math.floor(Math.random() * 70);
    
    return Array.from({ length: sampleSize }, (_, index) => ({
      id: index + 1,
      stream_id: 'realtime_stream',
      message_id: `msg_${index + 1}`,
      payload: JSON.stringify({ value: Math.random() * 100 }),
      received_at: new Date()
    }));
  }

  /**
   * Обнаружение аномалий
   */
  private async detectAnomalies(job: AnomalyDetectionJob, data: any[]): Promise<AnomalyResult[]> {
    switch (job.algorithm.type) {
      case 'statistical':
        return this.detectStatisticalAnomalies(job, data);
      case 'machine_learning':
        return this.detectMLAnomalies(job, data);
      case 'rule_based':
        return this.detectRuleBasedAnomalies(job, data);
      case 'time_series':
        return this.detectTimeSeriesAnomalies(job, data);
      case 'pattern_based':
        return this.detectPatternAnomalies(job, data);
      default:
        return [];
    }
  }

  /**
   * Статистическое обнаружение аномалий
   */
  private detectStatisticalAnomalies(job: AnomalyDetectionJob, data: any[]): AnomalyResult[] {
    const anomalies: AnomalyResult[] = [];
    
    job.dataSource.fields.forEach(field => {
      if (this.isNumericField(data, field)) {
        const values = data.map(d => d[field]).filter(v => v != null);
        const mean = values.reduce((sum, v) => sum + v, 0) / values.length;
        const std = Math.sqrt(values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / values.length);
        
        if (job.algorithm.name === 'Z-Score') {
          const threshold = job.parameters.threshold || 3;
          
          data.forEach((record, index) => {
            const value = record[field];
            if (value != null) {
              const zScore = Math.abs((value - mean) / std);
              
              if (zScore > threshold) {
                anomalies.push(this.createAnomalyResult(job, record, field, value, mean, zScore, 'value_outlier'));
              }
            }
          });
        }
        
        if (job.algorithm.name === 'Interquartile Range') {
          const sorted = values.sort((a, b) => a - b);
          const q1 = sorted[Math.floor(sorted.length * 0.25)];
          const q3 = sorted[Math.floor(sorted.length * 0.75)];
          const iqr = q3 - q1;
          const lowerBound = q1 - (job.parameters.multiplier || 1.5) * iqr;
          const upperBound = q3 + (job.parameters.multiplier || 1.5) * iqr;
          
          data.forEach(record => {
            const value = record[field];
            if (value != null && (value < lowerBound || value > upperBound)) {
              anomalies.push(this.createAnomalyResult(job, record, field, value, mean, 0, 'value_outlier'));
            }
          });
        }
      }
    });
    
    return anomalies;
  }

  /**
   * ML обнаружение аномалий
   */
  private async detectMLAnomalies(job: AnomalyDetectionJob, data: any[]): Promise<AnomalyResult[]> {
    // Симуляция ML алгоритмов
    const anomalies: AnomalyResult[] = [];
    
    if (job.algorithm.name === 'Isolation Forest') {
      // Симуляция Isolation Forest
      data.forEach((record, index) => {
        const anomalyScore = Math.random();
        
        if (anomalyScore > (1 - job.parameters.contamination || 0.1)) {
          const field = job.dataSource.fields[0];
          const value = record[field];
          anomalies.push(this.createAnomalyResult(job, record, field, value, 0, anomalyScore, 'pattern_deviation'));
        }
      });
    }
    
    if (job.algorithm.name === 'Local Outlier Factor') {
      // Симуляция LOF
      data.slice(0, Math.floor(data.length * 0.05)).forEach(record => {
        const field = job.dataSource.fields[0];
        const value = record[field];
        anomalies.push(this.createAnomalyResult(job, record, field, value, 0, 0.85, 'behavior_change'));
      });
    }
    
    return anomalies;
  }

  /**
   * Обнаружение на основе правил
   */
  private detectRuleBasedAnomalies(job: AnomalyDetectionJob, data: any[]): AnomalyResult[] {
    const anomalies: AnomalyResult[] = [];
    const rules = job.parameters.rules || [];
    
    data.forEach(record => {
      rules.forEach(rule => {
        const value = record[rule.field];
        let isAnomaly = false;
        
        switch (rule.operator) {
          case 'lt':
            isAnomaly = value < rule.value;
            break;
          case 'gt':
            isAnomaly = value > rule.value;
            break;
          case 'eq':
            isAnomaly = value === rule.value;
            break;
          case 'ne':
            isAnomaly = value !== rule.value;
            break;
        }
        
        if (isAnomaly) {
          anomalies.push(this.createAnomalyResult(job, record, rule.field, value, rule.value, 0.95, 'business_rule_violation'));
        }
      });
    });
    
    return anomalies;
  }

  /**
   * Обнаружение аномалий во временных рядах
   */
  private detectTimeSeriesAnomalies(job: AnomalyDetectionJob, data: any[]): AnomalyResult[] {
    const anomalies: AnomalyResult[] = [];
    
    if (job.algorithm.name === 'Exponentially Weighted Moving Average') {
      const alpha = job.parameters.alpha || 0.3;
      const threshold = job.parameters.threshold || 2;
      
      // Группировка по времени
      const timeGroups = this.groupByTime(data, 'timestamp');
      
      Object.entries(timeGroups).forEach(([timeKey, records]) => {
        const values = records.map(r => r[job.dataSource.fields[0]]).filter(v => v != null);
        if (values.length > 0) {
          const mean = values.reduce((sum, v) => sum + v, 0) / values.length;
          
          records.forEach(record => {
            const value = record[job.dataSource.fields[0]];
            if (value != null) {
              const deviation = Math.abs(value - mean);
              if (deviation > mean * threshold / 100) {
                anomalies.push(this.createAnomalyResult(job, record, job.dataSource.fields[0], value, mean, deviation / mean, 'trend_anomaly'));
              }
            }
          });
        }
      });
    }
    
    return anomalies;
  }

  /**
   * Обнаружение паттерн-аномалий
   */
  private detectPatternAnomalies(job: AnomalyDetectionJob, data: any[]): AnomalyResult[] {
    const anomalies: AnomalyResult[] = [];
    
    // Простое обнаружение паттернов
    const patternLength = job.parameters.patternLength || 24;
    const similarityThreshold = job.parameters.similarityThreshold || 0.8;
    
    // Группировка данных по паттернам времени
    const patterns = this.extractPatterns(data, patternLength);
    
    Object.entries(patterns).forEach(([patternKey, patternData]) => {
      if (patternData.length < (job.parameters.minOccurrences || 5)) {
        // Редкий паттерн - возможная аномалия
        patternData.forEach(record => {
          anomalies.push(this.createAnomalyResult(job, record, 'pattern', 'unknown', 0, 0.7, 'pattern_deviation'));
        });
      }
    });
    
    return anomalies;
  }

  /**
   * Создание результата аномалии
   */
  private createAnomalyResult(
    job: AnomalyDetectionJob, 
    record: any, 
    field: string, 
    value: any, 
    expectedValue: any, 
    confidence: number, 
    type: AnomalyType
  ): AnomalyResult {
    return {
      id: this.generateId(),
      jobId: job.id,
      timestamp: new Date(),
      anomalyType: type,
      severity: this.calculateSeverity(confidence, type),
      confidence,
      description: this.generateAnomalyDescription(type, field, value, expectedValue),
      affectedRecords: [
        {
          id: this.generateId(),
          field,
          originalValue: value,
          expectedValue,
          deviation: Math.abs(value - (expectedValue || 0)),
          timestamp: new Date()
        }
      ],
      metrics: {
        affectedFields: [field],
        impactScore: this.calculateImpactScore(confidence, type),
        dataVolume: 1,
        statisticalSignificance: confidence,
        businessImpact: this.assessBusinessImpact(type, confidence)
      },
      recommendations: this.generateRecommendations(type, field),
      resolved: false
    };
  }

  /**
   * Обработка найденной аномалии
   */
  private async processAnomaly(jobId: string, anomaly: AnomalyResult): Promise<void> {
    const job = this.jobs.get(jobId);
    if (!job) return;

    // Сохранение аномалии
    if (!this.results.has(jobId)) {
      this.results.set(jobId, []);
    }
    this.results.get(jobId)!.push(anomaly);

    // Отправка уведомлений
    await this.sendAlerts(job, anomaly);
  }

  /**
   * Отправка уведомлений
   */
  private async sendAlerts(job: AnomalyDetectionJob, anomaly: AnomalyResult): Promise<void> {
    for (const alert of job.alerts) {
      if (!alert.enabled) continue;

      // Проверка триггеров
      const shouldSend = alert.triggers.every(trigger => {
        switch (trigger.condition) {
          case 'severity':
            return this.compareValues(anomaly.severity, trigger.operator, trigger.value);
          case 'confidence':
            return this.compareValues(anomaly.confidence, trigger.operator, trigger.value);
          case 'business_impact':
            return this.compareValues(anomaly.metrics.businessImpact.level, trigger.operator, trigger.value);
          default:
            return false;
        }
      });

      if (shouldSend) {
        await this.sendAlert(alert, anomaly, job);
      }
    }
  }

  /**
   * Отправка отдельного уведомления
   */
  private async sendAlert(alert: AlertConfiguration, anomaly: AnomalyResult, job: AnomalyDetectionJob): Promise<void> {
    const message = this.formatAlertMessage(alert.template, anomaly, job);
    
    switch (alert.type) {
      case 'email':
        console.log(`EMAIL to ${alert.recipients.join(', ')}: ${message}`);
        break;
      case 'slack':
        console.log(`SLACK to ${alert.recipients.join(', ')}: ${message}`);
        break;
      case 'webhook':
        console.log(`WEBHOOK: ${message}`);
        break;
      default:
        console.log(`${alert.type.toUpperCase()}: ${message}`);
    }
  }

  /**
   * Обновление статистики задания
   */
  private updateJobStatistics(jobId: string, anomalyCount: number, detectionTime: number): void {
    const job = this.jobs.get(jobId);
    if (!job) return;

    job.statistics.totalScans++;
    job.statistics.anomaliesDetected += anomalyCount;
    job.statistics.avgDetectionTime = (
      job.statistics.avgDetectionTime * (job.statistics.totalScans - 1) + detectionTime
    ) / job.statistics.totalScans;

    if (anomalyCount > 0) {
      job.statistics.lastAnomalyTime = new Date();
    }

    this.jobs.set(jobId, job);
  }

  // Вспомогательные методы

  private isNumericField(data: any[], field: string): boolean {
    const values = data.map(d => d[field]).filter(v => v != null);
    return values.length > 0 && values.every(v => typeof v === 'number' || !isNaN(Number(v)));
  }

  private generateNumericValue(field: string): number {
    if (field.includes('amount') || field.includes('value') || field.includes('score')) {
      return Math.random() * 10000;
    }
    if (field.includes('efficiency') || field.includes('temperature')) {
      return Math.random() * 100;
    }
    return Math.random() * 1000;
  }

  private generateCategoricalValue(field: string): string {
    const categories = ['A', 'B', 'C', 'D', 'E'];
    return categories[Math.floor(Math.random() * categories.length)];
  }

  private calculateSeverity(confidence: number, type: AnomalyType): AnomalyResult['severity'] {
    if (confidence > 0.9) return 'critical';
    if (confidence > 0.8) return 'high';
    if (confidence > 0.6) return 'medium';
    return 'low';
  }

  private calculateImpactScore(confidence: number, type: AnomalyType): number {
    const baseScore = confidence * 100;
    const typeMultiplier = {
      'business_rule_violation': 1.5,
      'system_performance': 1.3,
      'data_quality': 1.2,
      'volume_spike': 1.1,
      'value_outlier': 1.0,
      'pattern_deviation': 0.9,
      'frequency_anomaly': 0.8,
      'correlation_break': 0.8,
      'trend_anomaly': 0.7,
      'behavior_change': 0.6
    }[type] || 1.0;

    return Math.min(100, baseScore * typeMultiplier);
  }

  private assessBusinessImpact(type: AnomalyType, confidence: number): BusinessImpact {
    const impacts = {
      'business_rule_violation': { level: 'significant' as const, description: 'Нарушение бизнес-правил' },
      'system_performance': { level: 'severe' as const, description: 'Проблемы с производительностью системы' },
      'data_quality': { level: 'moderate' as const, description: 'Проблемы с качеством данных' },
      'volume_spike': { level: 'moderate' as const, description: 'Необычный всплеск активности' },
      'value_outlier': { level: 'minimal' as const, description: 'Статистический выброс' },
      'pattern_deviation': { level: 'moderate' as const, description: 'Отклонение от ожидаемого паттерна' }
    };

    const baseImpact = impacts[type] || { level: 'minimal' as const, description: 'Обнаружена аномалия' };
    
    if (confidence > 0.9) {
      const levels = ['minimal', 'moderate', 'significant', 'severe'];
      const currentIndex = levels.indexOf(baseImpact.level);
      const escalatedLevel = levels[Math.min(currentIndex + 1, levels.length - 1)];
      return { ...baseImpact, level: escalatedLevel };
    }

    return baseImpact;
  }

  private generateAnomalyDescription(type: AnomalyType, field: string, value: any, expected: any): string {
    const descriptions = {
      'value_outlier': `Обнаружен выброс в поле ${field}: значение ${value} значительно отклоняется от ожидаемого ${expected}`,
      'pattern_deviation': `Обнаружено отклонение от ожидаемого паттерна в поле ${field}`,
      'volume_spike': `Необычный всплеск активности в поле ${field}: значение ${value}`,
      'business_rule_violation': `Нарушение бизнес-правила в поле ${field}: значение ${value} не соответствует правилам`,
      'system_performance': `Проблемы с производительностью системы обнаружены в поле ${field}`,
      'data_quality': `Проблемы с качеством данных обнаружены в поле ${field}`,
      'frequency_anomaly': `Необычная частота событий в поле ${field}`,
      'correlation_break': `Нарушение корреляции в поле ${field}`,
      'trend_anomaly': `Отклонение тренда в поле ${field}`,
      'behavior_change': `Изменение поведения системы в поле ${field}`
    };

    return descriptions[type] || `Обнаружена аномалия в поле ${field}: ${value}`;
  }

  private generateRecommendations(type: AnomalyType, field: string): string[] {
    const recommendations = {
      'value_outlier': [
        'Проверьте корректность ввода данных',
        'Убедитесь в правильности единиц измерения',
        'Проверьте систему на предмет технических проблем'
      ],
      'pattern_deviation': [
        'Проанализируйте причины изменения паттерна',
        'Проверьте влияние внешних факторов',
        'Рассмотрите обновление эталонных паттернов'
      ],
      'business_rule_violation': [
        'Проверьте соответствие бизнес-правилам',
        'Убедитесь в корректности настройки правил',
        'Проанализируйте влияние на бизнес-процессы'
      ],
      'system_performance': [
        'Проверьте загрузку системы',
        'Проанализируйте логи системы',
        'Рассмотрите масштабирование ресурсов'
      ],
      'data_quality': [
        'Запустите процедуры очистки данных',
        'Проверьте источники данных',
        'Улучшите процессы валидации'
      ]
    };

    return recommendations[type] || [
      'Проанализируйте контекст аномалии',
      'Проверьте связанные системы и процессы',
      'Документируйте найденные проблемы'
    ];
  }

  private compareValues(actual: any, operator: string, expected: any): boolean {
    switch (operator) {
      case 'gte': return actual >= expected;
      case 'lte': return actual <= expected;
      case 'eq': return actual === expected;
      case 'ne': return actual !== expected;
      default: return false;
    }
  }

  private formatAlertMessage(template: AlertTemplate, anomaly: AnomalyResult, job: AnomalyDetectionJob): string {
    let message = template.message
      .replace('{{anomalyType}}', anomaly.anomalyType)
      .replace('{{severity}}', anomaly.severity)
      .replace('{{description}}', anomaly.description)
      .replace('{{confidence}}', (anomaly.confidence * 100).toFixed(1) + '%')
      .replace('{{jobName}}', job.name);

    if (template.includeDetails) {
      message += `\n\nДетали:\n- Поля: ${anomaly.metrics.affectedFields.join(', ')}\n- Влияние: ${anomaly.metrics.businessImpact.description}\n- Затронуто записей: ${anomaly.affectedRecords.length}`;
    }

    if (template.includeRecommendations) {
      message += `\n\nРекомендации:\n${anomaly.recommendations.map(r => `- ${r}`).join('\n')}`;
    }

    return message;
  }

  private groupByTime(data: any[], timeField: string): Record<string, any[]> {
    return data.reduce((groups, record) => {
      const timeKey = new Date(record[timeField]).toISOString().split('T')[0]; // Группировка по дням
      if (!groups[timeKey]) {
        groups[timeKey] = [];
      }
      groups[timeKey].push(record);
      return groups;
    }, {} as Record<string, any[]>);
  }

  private extractPatterns(data: any[], patternLength: number): Record<string, any[]> {
    // Упрощенное извлечение паттернов
    return data.reduce((patterns, record) => {
      const hour = new Date(record.timestamp || Date.now()).getHours();
      const patternKey = `hour_${hour}`;
      if (!patterns[patternKey]) {
        patterns[patternKey] = [];
      }
      patterns[patternKey].push(record);
      return patterns;
    }, {} as Record<string, any[]>);
  }

  // Публичные методы API

  getJob(id: string): AnomalyDetectionJob | null {
    return this.jobs.get(id) || null;
  }

  getAllJobs(): AnomalyDetectionJob[] {
    return Array.from(this.jobs.values());
  }

  getAvailableAlgorithms(): AnomalyAlgorithm[] {
    return Array.from(this.algorithms.values());
  }

  getJobResults(jobId: string): AnomalyResult[] {
    return this.results.get(jobId) || [];
  }

  getAllResults(): AnomalyResult[] {
    return Array.from(this.results.values()).flat();
  }

  updateJobStatus(jobId: string, status: AnomalyDetectionJob['status']): boolean {
    const job = this.jobs.get(jobId);
    if (!job) return false;

    job.status = status;
    this.jobs.set(jobId, job);
    return true;
  }

  resolveAnomaly(jobId: string, anomalyId: string, resolvedBy: string): boolean {
    const results = this.results.get(jobId);
    if (!results) return false;

    const anomaly = results.find(a => a.id === anomalyId);
    if (!anomaly) return false;

    anomaly.resolved = true;
    anomaly.resolvedAt = new Date();
    anomaly.resolvedBy = resolvedBy;

    // Обновление статистики
    const job = this.jobs.get(jobId);
    if (job) {
      job.statistics.anomaliesResolved++;
      this.jobs.set(jobId, job);
    }

    return true;
  }

  deleteJob(jobId: string): boolean {
    return this.jobs.delete(jobId);
  }

  getStatistics(): any {
    const totalJobs = this.jobs.size;
    const activeJobs = Array.from(this.jobs.values()).filter(j => j.status === 'active').length;
    const totalAnomalies = Array.from(this.results.values()).reduce((sum, results) => sum + results.length, 0);
    const resolvedAnomalies = Array.from(this.results.values()).flat().filter(r => r.resolved).length;

    return {
      totalJobs,
      activeJobs,
      totalAnomalies,
      resolvedAnomalies,
      resolutionRate: totalAnomalies > 0 ? (resolvedAnomalies / totalAnomalies * 100).toFixed(1) + '%' : '0%',
      avgDetectionTime: Array.from(this.jobs.values()).reduce((sum, job) => sum + job.statistics.avgDetectionTime, 0) / totalJobs || 0
    };
  }

  private generateId(): string {
    return 'anomaly_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
  }
}