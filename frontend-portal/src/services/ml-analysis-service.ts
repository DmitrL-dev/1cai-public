/**
 * Сервис ML анализа и прогнозирования для 1C данных
 * Поддерживает различные алгоритмы машинного обучения и прогнозирования
 */

export interface MLModel {
  id: string;
  name: string;
  type: 'regression' | 'classification' | 'clustering' | 'time_series' | 'anomaly_detection';
  algorithm: string;
  dataset: DatasetConfig;
  parameters: ModelParameters;
  performance: ModelPerformance;
  createdAt: Date;
  lastTrained: Date;
  status: 'training' | 'ready' | 'failed' | 'deprecated';
}

export interface DatasetConfig {
  id: string;
  name: string;
  source: 'database' | 'file' | 'api' | 'realtime';
  tableName?: string;
  filePath?: string;
  apiEndpoint?: string;
  columns: DatasetColumn[];
  sampleSize?: number;
  timeColumn?: string;
  targetColumn?: string;
  features: string[];
}

export interface DatasetColumn {
  name: string;
  type: 'numeric' | 'categorical' | 'datetime' | 'text';
  nullable: boolean;
  unique?: boolean;
  description?: string;
  isFeature: boolean;
  isTarget: boolean;
}

export interface ModelParameters {
  [key: string]: any;
}

export interface ModelPerformance {
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1Score?: number;
  mse?: number;
  mae?: number;
  r2?: number;
  auc?: number;
  confusionMatrix?: number[][];
  featureImportance?: FeatureImportance[];
  crossValidationScore?: number;
}

export interface FeatureImportance {
  feature: string;
  importance: number;
  type: 'positive' | 'negative' | 'neutral';
}

export interface PredictionRequest {
  modelId: string;
  features: Record<string, any>;
  includeConfidence?: boolean;
  outputFormat?: 'single' | 'batch';
}

export interface PredictionResult {
  prediction: any;
  confidence?: number;
  probabilities?: Record<string, number>;
  featureImpact?: FeatureImpact[];
  timestamp: Date;
}

export interface FeatureImpact {
  feature: string;
  impact: number;
  direction: 'positive' | 'negative';
  explanation: string;
}

export interface TimeSeriesForecast {
  timestamps: Date[];
  values: number[];
  confidenceIntervals: {
    lower: number[];
    upper: number[];
  };
  trend: 'increasing' | 'decreasing' | 'stable' | 'volatile';
  seasonality?: {
    period: number;
    strength: number;
  };
}

export interface ModelEvaluation {
  modelId: string;
  evaluationMetrics: ModelPerformance;
  validationDataset: DatasetConfig;
  testResults: TestResult[];
  recommendations: string[];
  createdAt: Date;
}

export interface TestResult {
  actual: any;
  predicted: any;
  error: number;
  absoluteError: number;
  residual: number;
}

export interface ModelTrainingConfig {
  datasetId: string;
  targetColumn: string;
  featureColumns: string[];
  algorithm: string;
  hyperparameters: ModelParameters;
  validationMethod: 'k_fold' | 'train_test_split' | 'time_series_split';
  validationParams: any;
  preprocessing: PreprocessingConfig;
}

export interface PreprocessingConfig {
  handleMissing: 'drop' | 'fill_mean' | 'fill_median' | 'fill_mode' | 'interpolate';
  handleOutliers: 'remove' | 'cap' | 'transform';
  featureScaling: 'none' | 'standardize' | 'normalize' | 'robust';
  encoding: 'none' | 'one_hot' | 'label' | 'target';
  featureSelection: 'none' | 'correlation' | 'chi2' | 'recursive';
  dimensionalityReduction: 'none' | 'pca' | 'tsne' | 'umap';
}

export class MLAnalysisService {
  private models: Map<string, MLModel> = new Map();
  private datasets: Map<string, DatasetConfig> = new Map();
  private predictions: Map<string, PredictionResult[]> = new Map();

  constructor() {
    this.initializeSampleDatasets();
  }

  /**
   * Инициализация образцовых наборов данных
   */
  private initializeSampleDatasets(): void {
    // Набор данных продаж
    this.datasets.set('sales_data', {
      id: 'sales_data',
      name: 'Данные продаж 1C',
      source: 'database',
      tableName: 'sales_transactions',
      columns: [
        { name: 'date', type: 'datetime', nullable: false, unique: false, isFeature: true, isTarget: false },
        { name: 'amount', type: 'numeric', nullable: false, unique: false, isFeature: true, isTarget: true },
        { name: 'customer_id', type: 'categorical', nullable: false, unique: true, isFeature: true, isTarget: false },
        { name: 'product_id', type: 'categorical', nullable: false, unique: false, isFeature: true, isTarget: false },
        { name: 'region', type: 'categorical', nullable: true, unique: false, isFeature: true, isTarget: false },
        { name: 'quantity', type: 'numeric', nullable: false, unique: false, isFeature: true, isTarget: false },
        { name: 'discount', type: 'numeric', nullable: true, unique: false, isFeature: true, isTarget: false }
      ],
      sampleSize: 10000,
      timeColumn: 'date',
      targetColumn: 'amount',
      features: ['customer_id', 'product_id', 'region', 'quantity', 'discount']
    });

    // Набор данных производства
    this.datasets.set('production_data', {
      id: 'production_data',
      name: 'Производственные данные',
      source: 'database',
      tableName: 'production_metrics',
      columns: [
        { name: 'timestamp', type: 'datetime', nullable: false, unique: false, isFeature: true, isTarget: false },
        { name: 'output_volume', type: 'numeric', nullable: false, unique: false, isFeature: true, isTarget: true },
        { name: 'machine_id', type: 'categorical', nullable: false, unique: true, isFeature: true, isTarget: false },
        { name: 'operator_id', type: 'categorical', nullable: true, unique: true, isFeature: true, isTarget: false },
        { name: 'shift', type: 'categorical', nullable: false, unique: false, isFeature: true, isTarget: false },
        { name: 'quality_score', type: 'numeric', nullable: false, unique: false, isFeature: true, isTarget: false },
        { name: 'energy_consumption', type: 'numeric', nullable: false, unique: false, isFeature: true, isTarget: false }
      ],
      sampleSize: 5000,
      timeColumn: 'timestamp',
      targetColumn: 'output_volume',
      features: ['machine_id', 'operator_id', 'shift', 'quality_score', 'energy_consumption']
    });

    // Набор данных клиентов
    this.datasets.set('customer_data', {
      id: 'customer_data',
      name: 'Данные клиентов',
      source: 'database',
      tableName: 'customers',
      columns: [
        { name: 'customer_id', type: 'categorical', nullable: false, unique: true, isFeature: true, isTarget: false },
        { name: 'registration_date', type: 'datetime', nullable: false, unique: false, isFeature: true, isTarget: false },
        { name: 'total_purchases', type: 'numeric', nullable: false, unique: false, isFeature: true, isTarget: true },
        { name: 'avg_order_value', type: 'numeric', nullable: false, unique: false, isFeature: true, isTarget: false },
        { name: 'customer_segment', type: 'categorical', nullable: false, unique: false, isFeature: true, isTarget: false },
        { name: 'churn_risk', type: 'categorical', nullable: true, unique: false, isFeature: false, isTarget: true },
        { name: 'last_purchase_date', type: 'datetime', nullable: true, unique: false, isFeature: true, isTarget: false }
      ],
      sampleSize: 15000,
      targetColumn: 'churn_risk',
      features: ['registration_date', 'total_purchases', 'avg_order_value', 'customer_segment', 'last_purchase_date']
    });
  }

  /**
   * Создание модели машинного обучения
   */
  createModel(config: ModelTrainingConfig): string {
    const modelId = this.generateId();
    const dataset = this.datasets.get(config.datasetId);
    
    if (!dataset) throw new Error('Набор данных не найден');

    const model: MLModel = {
      id: modelId,
      name: `Model_${config.algorithm}_${Date.now()}`,
      type: this.getModelType(config.algorithm),
      algorithm: config.algorithm,
      dataset: dataset,
      parameters: config.hyperparameters,
      performance: {
        crossValidationScore: 0
      },
      createdAt: new Date(),
      lastTrained: new Date(),
      status: 'training'
    };

    this.models.set(modelId, model);
    
    // Запуск обучения в фоне
    setTimeout(() => this.trainModel(modelId, config), 100);
    
    return modelId;
  }

  /**
   * Обучение модели
   */
  private async trainModel(modelId: string, config: ModelTrainingConfig): Promise<void> {
    const model = this.models.get(modelId);
    if (!model) return;

    try {
      // Симуляция обучения модели
      const trainingResult = await this.simulateTraining(config);
      
      model.performance = trainingResult.performance;
      model.status = 'ready';
      model.lastTrained = new Date();
      
      this.models.set(modelId, model);
    } catch (error) {
      model.status = 'failed';
      this.models.set(modelId, model);
    }
  }

  /**
   * Симуляция обучения модели
   */
  private async simulateTraining(config: ModelTrainingConfig): Promise<{ performance: ModelPerformance }> {
    // Имитация времени обучения
    await new Promise(resolve => setTimeout(resolve, 2000 + Math.random() * 3000));

    const performance: ModelPerformance = {
      accuracy: 0.85 + Math.random() * 0.1,
      precision: 0.82 + Math.random() * 0.12,
      recall: 0.78 + Math.random() * 0.15,
      f1Score: 0.80 + Math.random() * 0.12,
      crossValidationScore: 0.83 + Math.random() * 0.1,
      featureImportance: config.featureColumns.map(feature => ({
        feature,
        importance: Math.random(),
        type: Math.random() > 0.5 ? 'positive' : 'negative'
      }))
    };

    // Дополнительные метрики для регрессии
    if (config.targetColumn) {
      performance.mse = Math.random() * 0.1;
      performance.mae = Math.random() * 0.05;
      performance.r2 = 0.75 + Math.random() * 0.2;
    }

    return { performance };
  }

  /**
   * Предсказание с использованием обученной модели
   */
  predict(request: PredictionRequest): PredictionResult {
    const model = this.models.get(request.modelId);
    if (!model) throw new Error('Модель не найдена');
    if (model.status !== 'ready') throw new Error('Модель не готова для предсказаний');

    const result = this.generatePrediction(model, request);
    
    // Сохранение предсказания
    if (!this.predictions.has(request.modelId)) {
      this.predictions.set(request.modelId, []);
    }
    this.predictions.get(request.modelId)!.push(result);

    return result;
  }

  /**
   * Генерация предсказания
   */
  private generatePrediction(model: MLModel, request: PredictionRequest): PredictionResult {
    // Симуляция предсказания на основе типа модели и алгоритма
    switch (model.type) {
      case 'regression':
        return this.generateRegressionPrediction(model, request);
      case 'classification':
        return this.generateClassificationPrediction(model, request);
      case 'clustering':
        return this.generateClusteringPrediction(model, request);
      case 'time_series':
        return this.generateTimeSeriesPrediction(model, request);
      case 'anomaly_detection':
        return this.generateAnomalyPrediction(model, request);
      default:
        throw new Error(`Неподдерживаемый тип модели: ${model.type}`);
    }
  }

  /**
   * Предсказание регрессии
   */
  private generateRegressionPrediction(model: MLModel, request: PredictionRequest): PredictionResult {
    const baseValue = 100 + Math.random() * 1000;
    const prediction = baseValue * (0.8 + Math.random() * 0.4);
    const confidence = 0.7 + Math.random() * 0.25;

    return {
      prediction,
      confidence,
      featureImpact: Object.keys(request.features).slice(0, 3).map(feature => ({
        feature,
        impact: (Math.random() - 0.5) * 100,
        direction: Math.random() > 0.5 ? 'positive' : 'negative',
        explanation: `Влияние признака ${feature} на результат`
      })),
      timestamp: new Date()
    };
  }

  /**
   * Предсказание классификации
   */
  private generateClassificationPrediction(model: MLModel, request: PredictionRequest): PredictionResult {
    const classes = ['High', 'Medium', 'Low', 'Very High'];
    const prediction = classes[Math.floor(Math.random() * classes.length)];
    const confidence = 0.6 + Math.random() * 0.35;

    const probabilities: Record<string, number> = {};
    classes.forEach(cls => {
      probabilities[cls] = cls === prediction ? confidence : (1 - confidence) / (classes.length - 1);
    });

    return {
      prediction,
      confidence,
      probabilities,
      featureImpact: Object.keys(request.features).slice(0, 3).map(feature => ({
        feature,
        impact: Math.random() * 50,
        direction: Math.random() > 0.5 ? 'positive' : 'negative',
        explanation: `Признак ${feature} влияет на классификацию`
      })),
      timestamp: new Date()
    };
  }

  /**
   * Предсказание кластеризации
   */
  private generateClusteringPrediction(model: MLModel, request: PredictionRequest): PredictionResult {
    const clusterId = Math.floor(Math.random() * 5) + 1;
    const confidence = 0.7 + Math.random() * 0.25;

    return {
      prediction: `Cluster ${clusterId}`,
      confidence,
      featureImpact: Object.keys(request.features).slice(0, 3).map(feature => ({
        feature,
        impact: Math.random() * 30,
        direction: Math.random() > 0.5 ? 'positive' : 'negative',
        explanation: `Влияние на кластеризацию: ${feature}`
      })),
      timestamp: new Date()
    };
  }

  /**
   * Предсказание временного ряда
   */
  private generateTimeSeriesPrediction(model: MLModel, request: PredictionRequest): PredictionResult {
    const currentValue = request.features['current_value'] || 100;
    const trend = (Math.random() - 0.5) * 20;
    const seasonality = Math.sin(Date.now() / 86400000) * 10; // Суточный цикл
    const prediction = currentValue + trend + seasonality;
    const confidence = 0.75 + Math.random() * 0.2;

    return {
      prediction,
      confidence,
      featureImpact: [
        { feature: 'trend', impact: trend, direction: trend > 0 ? 'positive' : 'negative', explanation: 'Основной тренд' },
        { feature: 'seasonality', impact: seasonality, direction: 'neutral', explanation: 'Сезонная составляющая' }
      ],
      timestamp: new Date()
    };
  }

  /**
   * Предсказание аномалий
   */
  private generateAnomalyPrediction(model: MLModel, request: PredictionRequest): PredictionResult {
    const isAnomaly = Math.random() < 0.1; // 10% вероятность аномалии
    const confidence = isAnomaly ? (0.8 + Math.random() * 0.15) : (0.85 + Math.random() * 0.1);

    return {
      prediction: isAnomaly ? 'Anomaly' : 'Normal',
      confidence,
      featureImpact: Object.keys(request.features).slice(0, 3).map(feature => ({
        feature,
        impact: isAnomaly ? (Math.random() * 100) : (Math.random() * 30),
        direction: Math.random() > 0.5 ? 'positive' : 'negative',
        explanation: isAnomaly ? 'Подозрительное значение' : 'Нормальное значение'
      })),
      timestamp: new Date()
    };
  }

  /**
   * Прогнозирование временного ряда
   */
  forecastTimeSeries(modelId: string, periods: number = 12): TimeSeriesForecast {
    const model = this.models.get(modelId);
    if (!model) throw new Error('Модель не найдена');
    if (model.type !== 'time_series') throw new Error('Модель не предназначена для прогнозирования временных рядов');

    const timestamps: Date[] = [];
    const values: number[] = [];
    const lower: number[] = [];
    const upper: number[] = [];

    const baseValue = 100 + Math.random() * 500;
    const trend = (Math.random() - 0.5) * 5;
    const seasonalityStrength = 0.3 + Math.random() * 0.4;
    const volatility = 0.1 + Math.random() * 0.2;

    for (let i = 0; i < periods; i++) {
      const date = new Date();
      date.setMonth(date.getMonth() + i);
      timestamps.push(date);

      const seasonal = Math.sin((i / 12) * 2 * Math.PI) * baseValue * seasonalityStrength;
      const trendComponent = baseValue + (trend * i);
      const randomComponent = (Math.random() - 0.5) * baseValue * volatility;
      
      const value = trendComponent + seasonal + randomComponent;
      values.push(Math.max(0, value));
      
      const confidence = 0.95;
      const margin = value * (1 - confidence);
      lower.push(Math.max(0, value - margin));
      upper.push(value + margin);
    }

    const trendDirection = trend > 1 ? 'increasing' : trend < -1 ? 'decreasing' : 'stable';
    const volatility = volatility > 0.3 ? 'volatile' : 'stable';

    return {
      timestamps,
      values,
      confidenceIntervals: { lower, upper },
      trend: trendDirection as any,
      seasonality: {
        period: 12,
        strength: seasonalityStrength
      }
    };
  }

  /**
   * Оценка модели
   */
  evaluateModel(modelId: string): ModelEvaluation {
    const model = this.models.get(modelId);
    if (!model) throw new Error('Модель не найдена');

    const evaluation: ModelEvaluation = {
      modelId,
      evaluationMetrics: model.performance,
      validationDataset: model.dataset,
      testResults: this.generateTestResults(model),
      recommendations: this.generateRecommendations(model),
      createdAt: new Date()
    };

    return evaluation;
  }

  /**
   * Генерация тестовых результатов
   */
  private generateTestResults(model: MLModel): TestResult[] {
    const results: TestResult[] = [];
    const sampleSize = 100;

    for (let i = 0; i < sampleSize; i++) {
      const actual = Math.random() * 1000;
      const predicted = actual + (Math.random() - 0.5) * 100;
      const error = predicted - actual;
      const absoluteError = Math.abs(error);
      const residual = error;

      results.push({
        actual,
        predicted,
        error,
        absoluteError,
        residual
      });
    }

    return results;
  }

  /**
   * Генерация рекомендаций
   */
  private generateRecommendations(model: MLModel): string[] {
    const recommendations: string[] = [];

    if (model.performance.accuracy && model.performance.accuracy < 0.8) {
      recommendations.push('Рассмотрите возможность увеличения размера обучающей выборки');
      recommendations.push('Попробуйте другие алгоритмы или настройки гиперпараметров');
    }

    if (model.performance.f1Score && model.performance.f1Score < 0.7) {
      recommendations.push('Проанализируйте дисбаланс классов в данных');
      recommendations.push('Рассмотрите методы балансировки классов');
    }

    if (model.performance.featureImportance && model.performance.featureImportance.length > 0) {
      const lowImportanceFeatures = model.performance.featureImportance.filter(f => f.importance < 0.1);
      if (lowImportanceFeatures.length > 0) {
        recommendations.push(`Рассмотрите исключение малозначимых признаков: ${lowImportanceFeatures.map(f => f.feature).join(', ')}`);
      }
    }

    recommendations.push('Регулярно переобучайте модель с новыми данными');
    recommendations.push('Мониторьте производительность модели в продакшене');

    return recommendations;
  }

  /**
   * Получение модели по ID
   */
  getModel(id: string): MLModel | null {
    return this.models.get(id) || null;
  }

  /**
   * Получение всех моделей
   */
  getAllModels(): MLModel[] {
    return Array.from(this.models.values());
  }

  /**
   * Получение набора данных
   */
  getDataset(id: string): DatasetConfig | null {
    return this.datasets.get(id) || null;
  }

  /**
   * Получение всех наборов данных
   */
  getAllDatasets(): DatasetConfig[] {
    return Array.from(this.datasets.values());
  }

  /**
   * Получение предсказаний модели
   */
  getModelPredictions(modelId: string): PredictionResult[] {
    return this.predictions.get(modelId) || [];
  }

  /**
   * Удаление модели
   */
  deleteModel(id: string): boolean {
    const deleted = this.models.delete(id);
    if (deleted) {
      this.predictions.delete(id);
    }
    return deleted;
  }

  /**
   * Обновление статуса модели
   */
  updateModelStatus(id: string, status: MLModel['status']): boolean {
    const model = this.models.get(id);
    if (!model) return false;

    model.status = status;
    this.models.set(id, model);
    return true;
  }

  /**
   * Экспорт модели
   */
  exportModel(id: string): string {
    const model = this.models.get(id);
    if (!model) throw new Error('Модель не найдена');

    return JSON.stringify({
      model,
      exportedAt: new Date(),
      version: '1.0'
    }, null, 2);
  }

  /**
   * Получение статистики ML системы
   */
  getMLStatistics(): any {
    const totalModels = this.models.size;
    const readyModels = Array.from(this.models.values()).filter(m => m.status === 'ready').length;
    const totalDatasets = this.datasets.size;
    const totalPredictions = Array.from(this.predictions.values()).reduce((sum, preds) => sum + preds.length, 0);

    return {
      totalModels,
      readyModels,
      trainingModels: Array.from(this.models.values()).filter(m => m.status === 'training').length,
      totalDatasets,
      totalPredictions,
      avgModelAccuracy: this.calculateAverageAccuracy()
    };
  }

  /**
   * Вычисление средней точности моделей
   */
  private calculateAverageAccuracy(): number {
    const models = Array.from(this.models.values());
    const accuracies = models.map(m => m.performance.accuracy).filter(a => a !== undefined);
    
    if (accuracies.length === 0) return 0;
    return accuracies.reduce((sum, acc) => sum + acc, 0) / accuracies.length;
  }

  /**
   * Определение типа модели по алгоритму
   */
  private getModelType(algorithm: string): MLModel['type'] {
    const algorithmMap: Record<string, MLModel['type']> = {
      'linear_regression': 'regression',
      'random_forest_regressor': 'regression',
      'svm_regressor': 'regression',
      'neural_network': 'regression',
      'logistic_regression': 'classification',
      'random_forest_classifier': 'classification',
      'svm_classifier': 'classification',
      'naive_bayes': 'classification',
      'gradient_boosting_classifier': 'classification',
      'kmeans': 'clustering',
      'dbscan': 'clustering',
      'hierarchical_clustering': 'clustering',
      'isolation_forest': 'anomaly_detection',
      'one_class_svm': 'anomaly_detection',
      'lstm': 'time_series',
      'arima': 'time_series',
      'prophet': 'time_series'
    };

    return algorithmMap[algorithm] || 'regression';
  }

  /**
   * Генерация уникального ID
   */
  private generateId(): string {
    return 'ml_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
  }
}