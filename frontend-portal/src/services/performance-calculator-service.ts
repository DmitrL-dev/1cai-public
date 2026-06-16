// Сервис для расчета производительности системы

export interface PerformanceMetric {
  name: string;
  value: number;
  unit: string;
  threshold: {
    warning: number;
    critical: number;
  };
  status: 'good' | 'warning' | 'critical';
}

export interface ScalabilityProjection {
  currentUsers: number;
  projectedUsers: number;
  timeHorizon: number; // дней
  resourceRequirements: {
    cpu: number;
    memory: number;
    storage: number;
    network: number;
  };
  costImpact: number;
  riskAssessment: 'low' | 'medium' | 'high';
  recommendations: string[];
}

export interface PerformanceBottleneck {
  id: string;
  component: string;
  type: 'cpu' | 'memory' | 'disk' | 'network' | 'database' | 'application';
  severity: 'low' | 'medium' | 'high' | 'critical';
  impact: {
    throughput: number; // процент снижения
    latency: number; // мс
    availability: number; // процент
  };
  rootCause: string;
  solutions: string[];
  priority: number;
  estimatedFixTime: number; // часов
}

export interface OptimizationRecommendation {
  id: string;
  category: 'performance' | 'scalability' | 'reliability' | 'cost' | 'security';
  title: string;
  description: string;
  impact: {
    performance: number; // % улучшения
    cost: number; // % изменения стоимости
    effort: number; // часов на реализацию
  };
  implementation: {
    steps: string[];
    prerequisites: string[];
    risks: string[];
  };
  priority: 'low' | 'medium' | 'high' | 'urgent';
  roi: number; // возврат инвестиций в днях
  tags: string[];
}

export interface PerformanceAnalysis {
  timestamp: Date;
  metrics: PerformanceMetric[];
  bottlenecks: PerformanceBottleneck[];
  scalabilityProjections: ScalabilityProjection[];
  recommendations: OptimizationRecommendation[];
  overallScore: number; // 0-100
  summary: string;
}

export interface SystemLoad {
  cpu: number; // 0-100%
  memory: number; // 0-100%
  disk: {
    read: number; // MB/s
    write: number; // MB/s
    usage: number; // 0-100%
  };
  network: {
    inbound: number; // MB/s
    outbound: number; // MB/s
    latency: number; // ms
  };
  database: {
    connections: number;
    queryTime: number; // ms
    lockWait: number; // ms
  };
  application: {
    activeUsers: number;
    requestsPerSecond: number;
    errorRate: number; // %
    responseTime: number; // ms
  };
}

export interface HistoricalData {
  timestamp: Date;
  load: SystemLoad;
  performance: number; // общий скор производительности
  availability: number; // %
  incidents: number;
}

export class PerformanceCalculatorService {
  private historicalData: HistoricalData[] = [];
  private baselineMetrics: Map<string, number> = new Map();

  constructor() {
    this.initializeBaselineMetrics();
  }

  private initializeBaselineMetrics(): void {
    this.baselineMetrics.set('cpu_threshold', 70);
    this.baselineMetrics.set('memory_threshold', 80);
    this.baselineMetrics.set('response_time_threshold', 1000);
    this.baselineMetrics.set('error_rate_threshold', 2);
    this.baselineMetrics.set('throughput_target', 1000);
  }

  /**
   * Анализ текущей производительности системы
   */
  analyzeCurrentPerformance(load: SystemLoad): PerformanceAnalysis {
    const metrics = this.calculateMetrics(load);
    const bottlenecks = this.identifyBottlenecks(load, metrics);
    const scalabilityProjections = this.calculateScalabilityProjections(load);
    const recommendations = this.generateRecommendations(load, bottlenecks);
    
    const overallScore = this.calculateOverallScore(metrics, bottlenecks);
    
    return {
      timestamp: new Date(),
      metrics,
      bottlenecks,
      scalabilityProjections,
      recommendations,
      overallScore,
      summary: this.generateAnalysisSummary(overallScore, bottlenecks, recommendations)
    };
  }

  /**
   * Расчет метрик производительности
   */
  private calculateMetrics(load: SystemLoad): PerformanceMetric[] {
    const metrics: PerformanceMetric[] = [];

    // CPU метрики
    metrics.push({
      name: 'CPU Usage',
      value: load.cpu,
      unit: '%',
      threshold: { warning: 70, critical: 90 },
      status: this.getMetricStatus(load.cpu, 70, 90)
    });

    // Memory метрики
    metrics.push({
      name: 'Memory Usage',
      value: load.memory,
      unit: '%',
      threshold: { warning: 80, critical: 95 },
      status: this.getMetricStatus(load.memory, 80, 95)
    });

    // Response Time
    metrics.push({
      name: 'Response Time',
      value: load.application.responseTime,
      unit: 'ms',
      threshold: { warning: 1000, critical: 3000 },
      status: this.getMetricStatus(load.application.responseTime, 1000, 3000, true)
    });

    // Error Rate
    metrics.push({
      name: 'Error Rate',
      value: load.application.errorRate,
      unit: '%',
      threshold: { warning: 2, critical: 5 },
      status: this.getMetricStatus(load.application.errorRate, 2, 5, true)
    });

    // Throughput
    metrics.push({
      name: 'Requests per Second',
      value: load.application.requestsPerSecond,
      unit: 'req/s',
      threshold: { warning: 500, critical: 200 },
      status: this.getMetricStatus(load.application.requestsPerSecond, 500, 200, false, true)
    });

    // Database Query Time
    metrics.push({
      name: 'Database Query Time',
      value: load.database.queryTime,
      unit: 'ms',
      threshold: { warning: 500, critical: 2000 },
      status: this.getMetricStatus(load.database.queryTime, 500, 2000, true)
    });

    return metrics;
  }

  private getMetricStatus(
    value: number, 
    warning: number, 
    critical: number, 
    inverse: boolean = false, 
    higherIsBetter: boolean = false
  ): 'good' | 'warning' | 'critical' {
    const isGood = inverse ? 
      (higherIsBetter ? value >= warning : value <= warning) :
      (higherIsBetter ? value >= warning : value <= warning);
    
    const isCritical = inverse ?
      (higherIsBetter ? value >= critical : value <= critical) :
      (higherIsBetter ? value >= critical : value <= critical);

    if (isCritical) return 'critical';
    if (isGood) return 'good';
    return 'warning';
  }

  /**
   * Идентификация узких мест
   */
  private identifyBottlenecks(load: SystemLoad, metrics: PerformanceMetric[]): PerformanceBottleneck[] {
    const bottlenecks: PerformanceBottleneck[] = [];

    // CPU bottlenecks
    if (load.cpu > 80) {
      bottlenecks.push({
        id: `cpu_${Date.now()}`,
        component: 'CPU',
        type: 'cpu',
        severity: load.cpu > 95 ? 'critical' : 'high',
        impact: {
          throughput: Math.min(50, (load.cpu - 80) * 2),
          latency: (load.cpu - 70) * 10,
          availability: Math.max(0, 100 - (load.cpu - 80) * 5)
        },
        rootCause: 'Высокая загрузка процессора',
        solutions: [
          'Оптимизировать алгоритмы',
          'Добавить вычислительные ресурсы',
          'Реализовать кэширование',
          'Оптимизировать запросы к БД'
        ],
        priority: 1,
        estimatedFixTime: 8
      });
    }

    // Memory bottlenecks
    if (load.memory > 85) {
      bottlenecks.push({
        id: `memory_${Date.now()}`,
        component: 'Memory',
        type: 'memory',
        severity: load.memory > 95 ? 'critical' : 'high',
        impact: {
          throughput: Math.min(30, (load.memory - 85) * 2),
          latency: (load.memory - 80) * 5,
          availability: Math.max(0, 100 - (load.memory - 85) * 3)
        },
        rootCause: 'Недостаток оперативной памяти',
        solutions: [
          'Оптимизировать использование памяти',
          'Увеличить объем RAM',
          'Реализовать garbage collection',
          'Оптимизировать структуры данных'
        ],
        priority: 2,
        estimatedFixTime: 4
      });
    }

    // Database bottlenecks
    if (load.database.queryTime > 1000) {
      bottlenecks.push({
        id: `database_${Date.now()}`,
        component: 'Database',
        type: 'database',
        severity: load.database.queryTime > 5000 ? 'critical' : 'medium',
        impact: {
          throughput: Math.min(40, (load.database.queryTime - 500) / 100),
          latency: load.database.queryTime - 500,
          availability: 90
        },
        rootCause: 'Медленные запросы к базе данных',
        solutions: [
          'Оптимизировать SQL запросы',
          'Добавить индексы',
          'Настроить кэширование',
          'Масштабировать базу данных'
        ],
        priority: 3,
        estimatedFixTime: 12
      });
    }

    // Network bottlenecks
    if (load.network.latency > 100) {
      bottlenecks.push({
        id: `network_${Date.now()}`,
        component: 'Network',
        type: 'network',
        severity: load.network.latency > 500 ? 'high' : 'medium',
        impact: {
          throughput: Math.min(25, (load.network.latency - 50) / 10),
          latency: load.network.latency - 50,
          availability: 95
        },
        rootCause: 'Высокая сетевая задержка',
        solutions: [
          'Оптимизировать сетевую архитектуру',
          'Использовать CDN',
          'Настроить сжатие данных',
          'Оптимизировать API вызовы'
        ],
        priority: 4,
        estimatedFixTime: 16
      });
    }

    return bottlenecks.sort((a, b) => a.priority - b.priority);
  }

  /**
   * Расчет прогнозов масштабируемости
   */
  private calculateScalabilityProjections(load: SystemLoad): ScalabilityProjection[] {
    const projections: ScalabilityProjection[] = [];

    // Прогноз на 3 месяца
    projections.push({
      currentUsers: load.application.activeUsers,
      projectedUsers: Math.round(load.application.activeUsers * 2.5),
      timeHorizon: 90,
      resourceRequirements: {
        cpu: load.cpu * 2.5,
        memory: load.memory * 2.2,
        storage: 100, // GB
        network: 1000 // Mbps
      },
      costImpact: 150, // % увеличения
      riskAssessment: this.assessScalabilityRisk(load),
      recommendations: this.generateScalabilityRecommendations(load, 2.5)
    });

    // Прогноз на 6 месяцев
    projections.push({
      currentUsers: load.application.activeUsers,
      projectedUsers: Math.round(load.application.activeUsers * 5),
      timeHorizon: 180,
      resourceRequirements: {
        cpu: load.cpu * 5,
        memory: load.memory * 4.5,
        storage: 500, // GB
        network: 2000 // Mbps
      },
      costImpact: 300, // % увеличения
      riskAssessment: this.assessScalabilityRisk(load, 5),
      recommendations: this.generateScalabilityRecommendations(load, 5)
    });

    return projections;
  }

  private assessScalabilityRisk(load: SystemLoad, multiplier: number = 2.5): 'low' | 'medium' | 'high' {
    const scaledCpu = load.cpu * multiplier;
    const scaledMemory = load.memory * multiplier;
    
    if (scaledCpu > 120 || scaledMemory > 120) return 'high';
    if (scaledCpu > 90 || scaledMemory > 90) return 'medium';
    return 'low';
  }

  private generateScalabilityRecommendations(load: SystemLoad, multiplier: number): string[] {
    const recommendations: string[] = [];

    if (load.cpu * multiplier > 80) {
      recommendations.push('Планировать горизонтальное масштабирование CPU');
      recommendations.push('Рассмотреть возможность использования контейнеризации');
    }

    if (load.memory * multiplier > 80) {
      recommendations.push('Планировать увеличение оперативной памяти');
      recommendations.push('Оптимизировать использование памяти в приложении');
    }

    if (load.application.requestsPerSecond * multiplier > 1000) {
      recommendations.push('Внедрить балансировщик нагрузки');
      recommendations.push('Рассмотреть микросервисную архитектуру');
    }

    recommendations.push('Настроить мониторинг производительности');
    recommendations.push('Создать план аварийного масштабирования');

    return recommendations;
  }

  /**
   * Генерация рекомендаций по оптимизации
   */
  private generateRecommendations(load: SystemLoad, bottlenecks: PerformanceBottleneck[]): OptimizationRecommendation[] {
    const recommendations: OptimizationRecommendation[] = [];

    // Рекомендации на основе узких мест
    bottlenecks.forEach(bottleneck => {
      switch (bottleneck.type) {
        case 'cpu':
          recommendations.push({
            id: `opt_cpu_${Date.now()}`,
            category: 'performance',
            title: 'Оптимизация вычислений',
            description: 'Снижение нагрузки на процессор через оптимизацию алгоритмов',
            impact: {
              performance: 30,
              cost: -15,
              effort: 40
            },
            implementation: {
              steps: [
                'Профилирование CPU-интенсивных операций',
                'Оптимизация алгоритмов',
                'Внедрение кэширования',
                'Тестирование производительности'
              ],
              prerequisites: ['Доступ к исходному коду', 'Среда для тестирования'],
              risks: ['Регрессия производительности', 'Введение новых ошибок']
            },
            priority: 'high',
            roi: 30,
            tags: ['cpu', 'optimization', 'algorithm']
          });
          break;

        case 'memory':
          recommendations.push({
            id: `opt_memory_${Date.now()}`,
            category: 'performance',
            title: 'Оптимизация использования памяти',
            description: 'Снижение потребления оперативной памяти',
            impact: {
              performance: 25,
              cost: -10,
              effort: 20
            },
            implementation: {
              steps: [
                'Анализ использования памяти',
                'Устранение утечек памяти',
                'Оптимизация структур данных',
                'Настройка garbage collection'
              ],
              prerequisites: ['Инструменты профилирования памяти'],
              risks: ['Временное увеличение использования CPU']
            },
            priority: 'high',
            roi: 20,
            tags: ['memory', 'optimization', 'gc']
          });
          break;

        case 'database':
          recommendations.push({
            id: `opt_db_${Date.now()}`,
            category: 'performance',
            title: 'Оптимизация базы данных',
            description: 'Улучшение производительности БД через оптимизацию запросов и индексов',
            impact: {
              performance: 40,
              cost: 5,
              effort: 30
            },
            implementation: {
              steps: [
                'Анализ медленных запросов',
                'Создание/оптимизация индексов',
                'Оптимизация SQL запросов',
                'Настройка кэширования БД'
              ],
              prerequisites: ['Доступ к БД', 'Права на изменение схемы'],
              risks: ['Блокировки таблиц во время создания индексов']
            },
            priority: 'urgent',
            roi: 25,
            tags: ['database', 'sql', 'indexes']
          });
          break;
      }
    });

    // Общие рекомендации по масштабируемости
    if (load.application.activeUsers > 1000) {
      recommendations.push({
        id: `opt_scale_${Date.now()}`,
        category: 'scalability',
        title: 'Внедрение горизонтального масштабирования',
        description: 'Подготовка инфраструктуры к росту нагрузки',
        impact: {
          performance: 50,
          cost: 100,
          effort: 80
        },
        implementation: {
          steps: [
            'Внедрение контейнеризации',
            'Настройка оркестрации (Kubernetes)',
            'Внедрение балансировщика нагрузки',
            'Настройка автоматического масштабирования'
          ],
          prerequisites: ['Облачная инфраструктура', 'CI/CD пайплайн'],
          risks: ['Увеличение сложности системы']
        },
        priority: 'medium',
        roi: 60,
        tags: ['scaling', 'kubernetes', 'load-balancer']
      });
    }

    return recommendations.sort((a, b) => b.roi - a.roi);
  }

  /**
   * Расчет общего скора производительности
   */
  private calculateOverallScore(metrics: PerformanceMetric[], bottlenecks: PerformanceBottleneck[]): number {
    let score = 100;

    // Снижение за метрики
    metrics.forEach(metric => {
      switch (metric.status) {
        case 'warning':
          score -= 10;
          break;
        case 'critical':
          score -= 25;
          break;
      }
    });

    // Снижение за узкие места
    bottlenecks.forEach(bottleneck => {
      switch (bottleneck.severity) {
        case 'low':
          score -= 5;
          break;
        case 'medium':
          score -= 15;
          break;
        case 'high':
          score -= 30;
          break;
        case 'critical':
          score -= 50;
          break;
      }
    });

    return Math.max(0, Math.min(100, score));
  }

  /**
   * Генерация сводки анализа
   */
  private generateAnalysisSummary(
    score: number, 
    bottlenecks: PerformanceBottleneck[], 
    recommendations: OptimizationRecommendation[]
  ): string {
    const criticalBottlenecks = bottlenecks.filter(b => b.severity === 'critical').length;
    const urgentRecommendations = recommendations.filter(r => r.priority === 'urgent').length;

    let summary = `Общий скоринг производительности: ${score}/100. `;

    if (score >= 80) {
      summary += 'Система работает хорошо. ';
    } else if (score >= 60) {
      summary += 'Система работает с некоторыми проблемами. ';
    } else {
      summary += 'Система требует оптимизации. ';
    }

    if (criticalBottlenecks > 0) {
      summary += `Обнаружено ${criticalBottlenecks} критических узких мест. `;
    }

    if (urgentRecommendations > 0) {
      summary += `Рекомендуется выполнить ${urgentRecommendations} срочных оптимизаций.`;
    }

    return summary;
  }

  /**
   * Добавление исторических данных
   */
  addHistoricalData(data: HistoricalData): void {
    this.historicalData.push(data);
    
    // Ограничиваем размер истории (последние 1000 записей)
    if (this.historicalData.length > 1000) {
      this.historicalData = this.historicalData.slice(-1000);
    }
  }

  /**
   * Получение трендов производительности
   */
  getPerformanceTrends(days: number = 7): {
    trends: ('improving' | 'stable' | 'declining')[];
    changeRate: number;
  } {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - days);

    const recentData = this.historicalData
      .filter(d => d.timestamp >= cutoffDate)
      .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

    if (recentData.length < 2) {
      return { trends: ['stable'], changeRate: 0 };
    }

    const first = recentData[0];
    const last = recentData[recentData.length - 1];

    const changeRate = ((last.performance - first.performance) / first.performance) * 100;

    let trend: 'improving' | 'stable' | 'declining';
    if (changeRate > 5) {
      trend = 'improving';
    } else if (changeRate < -5) {
      trend = 'declining';
    } else {
      trend = 'stable';
    }

    return { trends: [trend], changeRate };
  }

  /**
   * Экспорт анализа в JSON
   */
  exportAnalysis(analysis: PerformanceAnalysis): string {
    return JSON.stringify(analysis, null, 2);
  }

  /**
   * Очистка ресурсов
   */
  cleanup(): void {
    this.historicalData = [];
    this.baselineMetrics.clear();
  }
}