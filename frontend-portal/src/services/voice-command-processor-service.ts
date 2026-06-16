import { BehaviorSubject, Observable } from 'rxjs';

export interface VoiceCommandRule {
  id: string;
  trigger: RegExp;
  command: string;
  agent?: string;
  parameters: Array<{ name: string; type: 'string' | 'number' | 'boolean'; required: boolean }>;
  priority: number;
  enabled: boolean;
  description?: string;
  examples?: string[];
}

export interface ProcessedCommand {
  id: string;
  originalText: string;
  command: string;
  agent?: string;
  parameters: Record<string, any>;
  confidence: number;
  timestamp: Date;
  status: 'pending' | 'executing' | 'completed' | 'failed';
  result?: any;
  error?: string;
}

export interface CommandExecutionContext {
  agentType: string;
  sessionId: string;
  userId: string;
  projectId?: string;
  environment: 'development' | 'staging' | 'production';
}

export class VoiceCommandProcessorService {
  private rules: VoiceCommandRule[] = [];
  private commandHistory: ProcessedCommand[] = [];
  private activeCommands = new Map<string, ProcessedCommand>();
  
  // Subjects
  private commandProcessedSubject = new BehaviorSubject<ProcessedCommand | null>(null);
  private commandExecutedSubject = new BehaviorSubject<ProcessedCommand | null>(null);
  private commandFailedSubject = new BehaviorSubject<ProcessedCommand | null>(null);
  private historySubject = new BehaviorSubject<ProcessedCommand[]>([]);
  
  // Observables
  public commandProcessed$: Observable<ProcessedCommand | null> = this.commandProcessedSubject.asObservable();
  public commandExecuted$: Observable<ProcessedCommand | null> = this.commandExecutedSubject.asObservable();
  public commandFailed$: Observable<ProcessedCommand | null> = this.commandFailedSubject.asObservable();
  public history$: Observable<ProcessedCommand[]> = this.historySubject.asObservable();

  constructor() {
    this.initializeDefaultRules();
  }

  private initializeDefaultRules(): void {
    // Правила для архитектора
    this.addRule({
      id: 'arch_design_pattern',
      trigger: /(?:создай|добавь|сделай)\s+(?:паттерн|архитектуру|структуру)\s+(.+)/i,
      command: 'create_design_pattern',
      agent: 'architect',
      parameters: [
        { name: 'patternName', type: 'string', required: true }
      ],
      priority: 10,
      enabled: true,
      description: 'Создание архитектурного паттерна',
      examples: ['Создай паттерн MVC', 'Добавь архитектуру проекта']
    });

    // Правила для разработчика
    this.addRule({
      id: 'dev_create_module',
      trigger: /(?:создай|добавь|сделай)\s+(?:модуль|обработку|отчет|справочник|документ)\s+(.+)/i,
      command: 'create_1c_module',
      agent: 'developer',
      parameters: [
        { name: 'moduleName', type: 'string', required: true },
        { name: 'moduleType', type: 'string', required: false }
      ],
      priority: 10,
      enabled: true,
      description: 'Создание модуля 1С',
      examples: ['Создай модуль "Обработка заказов"', 'Добавь справочник "Клиенты"']
    });

    // Правила для менеджера проектов
    this.addRule({
      id: 'pm_create_task',
      trigger: /(?:создай|добавь|сделай)\s+(?:задачу|задание|тикет)\s+(.+)/i,
      command: 'create_project_task',
      agent: 'pm',
      parameters: [
        { name: 'taskName', type: 'string', required: true },
        { name: 'priority', type: 'string', required: false }
      ],
      priority: 10,
      enabled: true,
      description: 'Создание задачи проекта',
      examples: ['Создай задачу "Тестирование модуля"', 'Добавь задачу высокого приоритета']
    });

    // Правила для бизнес-аналитика
    this.addRule({
      id: 'ba_analyze_requirement',
      trigger: /(?:проанализируй|анализ|исследуй)\s+(?:требование|требования|документ)\s*(.+)?/i,
      command: 'analyze_requirement',
      agent: 'ba',
      parameters: [
        { name: 'requirement', type: 'string', required: false }
      ],
      priority: 8,
      enabled: true,
      description: 'Анализ требований',
      examples: ['Проанализируй требование', 'Анализ документа проекта']
    });

    // Правила для аналитика данных
    this.addRule({
      id: 'da_create_dashboard',
      trigger: /(?:создай|сделай)\s+(?:дашборд|отчет|аналитику)\s+(.+)/i,
      command: 'create_data_dashboard',
      agent: 'data_analyst',
      parameters: [
        { name: 'dashboardName', type: 'string', required: true }
      ],
      priority: 9,
      enabled: true,
      description: 'Создание аналитического дашборда',
      examples: ['Создай дашборд продаж', 'Сделай отчет по эффективности']
    });

    // Универсальные правила
    this.addRule({
      id: 'universal_help',
      trigger: /(?:помощь|что можешь|как|справка)/i,
      command: 'show_help',
      parameters: [],
      priority: 5,
      enabled: true,
      description: 'Показать справку',
      examples: ['Помощь', 'Что можешь делать?']
    });

    this.addRule({
      id: 'universal_save',
      trigger: /(?:сохрани|запиши|сохранение)/i,
      command: 'save_state',
      parameters: [],
      priority: 7,
      enabled: true,
      description: 'Сохранить состояние',
      examples: ['Сохрани', 'Запиши изменения']
    });

    this.addRule({
      id: 'universal_export',
      trigger: /(?:экспортируй|выгрузи|скачай|экспорт)/i,
      command: 'export_data',
      parameters: [
        { name: 'format', type: 'string', required: false }
      ],
      priority: 6,
      enabled: true,
      description: 'Экспорт данных',
      examples: ['Экспортируй в Excel', 'Скачай отчет']
    });
  }

  public processSpeechText(text: string, context: CommandExecutionContext): ProcessedCommand | null {
    const normalizedText = text.trim().toLowerCase();
    let bestMatch: VoiceCommandRule | null = null;
    let bestScore = 0;

    // Поиск подходящего правила
    for (const rule of this.rules) {
      if (!rule.enabled) continue;
      
      // Проверяем соответствие текста паттерну
      const match = normalizedText.match(rule.trigger);
      if (match) {
        // Вычисляем score на основе приоритета и длины совпадения
        const score = rule.priority * (match[0].length / text.length);
        
        if (score > bestScore) {
          bestScore = score;
          bestMatch = rule;
        }
      }
    }

    if (!bestMatch) {
      return null;
    }

    // Создаем команду
    const command: ProcessedCommand = {
      id: this.generateId(),
      originalText: text,
      command: bestMatch.command,
      agent: bestMatch.agent,
      parameters: this.extractParameters(bestMatch, normalizedText),
      confidence: Math.min(bestScore / bestMatch.priority, 1.0),
      timestamp: new Date(),
      status: 'pending'
    };

    // Добавляем в историю
    this.commandHistory.unshift(command);
    this.commandHistory = this.commandHistory.slice(0, 1000); // Ограничиваем размер истории
    
    // Обновляем Observables
    this.commandProcessedSubject.next(command);
    this.updateHistory();

    return command;
  }

  private extractParameters(rule: VoiceCommandRule, text: string): Record<string, any> {
    const parameters: Record<string, any> = {};
    const match = text.match(rule.trigger);

    if (!match) return parameters;

    rule.parameters.forEach((param, index) => {
      const captureGroup = match[index + 1]; // +1 потому что match[0] - вся строка
      if (captureGroup) {
        switch (param.type) {
          case 'number':
            const numValue = parseFloat(captureGroup);
            parameters[param.name] = isNaN(numValue) ? null : numValue;
            break;
          case 'boolean':
            parameters[param.name] = /да|yes|true/i.test(captureGroup);
            break;
          default:
            parameters[param.name] = captureGroup.trim();
        }
      } else if (param.required) {
        parameters[param.name] = null; // Обязательный параметр не найден
      }
    });

    return parameters;
  }

  public async executeCommand(command: ProcessedCommand, context: CommandExecutionContext): Promise<ProcessedCommand> {
    const startTime = Date.now();
    
    try {
      command.status = 'executing';
      this.activeCommands.set(command.id, command);

      // Симуляция выполнения команды (в реальном приложении здесь был бы API call)
      const result = await this.simulateCommandExecution(command, context);
      
      command.status = 'completed';
      command.result = result;
      command.timestamp = new Date();
      
      // Обновляем в истории
      const historyIndex = this.commandHistory.findIndex(c => c.id === command.id);
      if (historyIndex >= 0) {
        this.commandHistory[historyIndex] = command;
      }

      this.commandExecutedSubject.next(command);
      this.updateHistory();

      return command;
    } catch (error) {
      command.status = 'failed';
      command.error = error instanceof Error ? error.message : 'Неизвестная ошибка';
      command.timestamp = new Date();
      
      // Обновляем в истории
      const historyIndex = this.commandHistory.findIndex(c => c.id === command.id);
      if (historyIndex >= 0) {
        this.commandHistory[historyIndex] = command;
      }

      this.commandFailedSubject.next(command);
      this.updateHistory();

      throw error;
    } finally {
      this.activeCommands.delete(command.id);
    }
  }

  private async simulateCommandExecution(command: ProcessedCommand, context: CommandExecutionContext): Promise<any> {
    // Симуляция различных типов команд
    switch (command.command) {
      case 'create_design_pattern':
        return {
          success: true,
          message: `Создан архитектурный паттерн: ${command.parameters.patternName}`,
          pattern: command.parameters.patternName,
          timestamp: new Date()
        };

      case 'create_1c_module':
        return {
          success: true,
          message: `Создан модуль 1С: ${command.parameters.moduleName}`,
          module: command.parameters.moduleName,
          type: command.parameters.moduleType || 'Обработка',
          timestamp: new Date()
        };

      case 'create_project_task':
        return {
          success: true,
          message: `Создана задача проекта: ${command.parameters.taskName}`,
          task: command.parameters.taskName,
          priority: command.parameters.priority || 'Средний',
          timestamp: new Date()
        };

      case 'analyze_requirement':
        return {
          success: true,
          message: 'Выполнен анализ требований',
          analysis: {
            complexity: 'Средняя',
            risks: ['Технические сложности', 'Интеграционные проблемы'],
            recommendations: ['Провести дополнительное исследование', 'Планирование ресурсов'],
            timestamp: new Date()
          }
        };

      case 'create_data_dashboard':
        return {
          success: true,
          message: `Создан дашборд: ${command.parameters.dashboardName}`,
          dashboard: command.parameters.dashboardName,
          widgets: ['Метрики продаж', 'График трендов', 'Таблица данных'],
          timestamp: new Date()
        };

      case 'show_help':
        return {
          success: true,
          message: 'Доступные команды:',
          commands: this.getAvailableCommands(),
          timestamp: new Date()
        };

      case 'save_state':
        return {
          success: true,
          message: 'Состояние сохранено',
          timestamp: new Date()
        };

      case 'export_data':
        return {
          success: true,
          message: 'Данные экспортированы',
          format: command.parameters.format || 'Excel',
          timestamp: new Date()
        };

      default:
        // Симуляция произвольной команды
        await this.delay(1000 + Math.random() * 2000); // Имитация работы
        return {
          success: true,
          message: `Команда "${command.command}" выполнена успешно`,
          parameters: command.parameters,
          timestamp: new Date()
        };
    }
  }

  public addRule(rule: VoiceCommandRule): void {
    // Проверяем уникальность ID
    const existingRule = this.rules.find(r => r.id === rule.id);
    if (existingRule) {
      throw new Error(`Правило с ID ${rule.id} уже существует`);
    }

    this.rules.push(rule);
    this.rules.sort((a, b) => b.priority - a.priority);
  }

  public removeRule(ruleId: string): void {
    const index = this.rules.findIndex(r => r.id === ruleId);
    if (index >= 0) {
      this.rules.splice(index, 1);
    }
  }

  public updateRule(ruleId: string, updates: Partial<VoiceCommandRule>): void {
    const rule = this.rules.find(r => r.id === ruleId);
    if (rule) {
      Object.assign(rule, updates);
    }
  }

  public getRules(): VoiceCommandRule[] {
    return [...this.rules];
  }

  public getRuleById(ruleId: string): VoiceCommandRule | undefined {
    return this.rules.find(r => r.id === ruleId);
  }

  public getAvailableCommands(): Array<{ command: string; description: string; examples: string[] }> {
    return this.rules
      .filter(rule => rule.enabled)
      .map(rule => ({
        command: rule.command,
        description: rule.description || 'Описание недоступно',
        examples: rule.examples || []
      }));
  }

  public getCommandHistory(limit?: number): ProcessedCommand[] {
    const history = [...this.commandHistory];
    return limit ? history.slice(0, limit) : history;
  }

  public clearHistory(): void {
    this.commandHistory = [];
    this.updateHistory();
  }

  public getActiveCommands(): ProcessedCommand[] {
    return Array.from(this.activeCommands.values());
  }

  private updateHistory(): void {
    this.historySubject.next([...this.commandHistory]);
  }

  private generateId(): string {
    return `cmd_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  public getCommandStatistics(): {
    totalCommands: number;
    successfulCommands: number;
    failedCommands: number;
    averageExecutionTime: number;
    mostUsedCommands: Array<{ command: string; count: number }>;
  } {
    const commands = this.commandHistory;
    const totalCommands = commands.length;
    const successfulCommands = commands.filter(c => c.status === 'completed').length;
    const failedCommands = commands.filter(c => c.status === 'failed').length;

    // Вычисляем среднее время выполнения
    const completedCommands = commands.filter(c => c.status === 'completed' && c.result);
    const averageExecutionTime = completedCommands.length > 0
      ? completedCommands.reduce((sum, cmd) => {
          const execTime = cmd.timestamp.getTime() - new Date(cmd.timestamp).getTime();
          return sum + execTime;
        }, 0) / completedCommands.length
      : 0;

    // Статистика наиболее используемых команд
    const commandCounts = new Map<string, number>();
    commands.forEach(cmd => {
      commandCounts.set(cmd.command, (commandCounts.get(cmd.command) || 0) + 1);
    });

    const mostUsedCommands = Array.from(commandCounts.entries())
      .map(([command, count]) => ({ command, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);

    return {
      totalCommands,
      successfulCommands,
      failedCommands,
      averageExecutionTime,
      mostUsedCommands
    };
  }

  public cleanup(): void {
    this.commandProcessedSubject.complete();
    this.commandExecutedSubject.complete();
    this.commandFailedSubject.complete();
    this.historySubject.complete();
  }
}