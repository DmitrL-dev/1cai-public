// Сервис для экспорта данных в различных форматах

export type ExportFormat = 'pdf' | 'docx' | 'xlsx' | 'csv' | 'json' | 'xml' | 'html' | 'txt';

export interface ExportOptions {
  format: ExportFormat;
  template?: string;
  includeMetadata: boolean;
  includeImages: boolean;
  includeCharts: boolean;
  customFields?: Record<string, any>;
  compression?: boolean;
  encryption?: boolean;
}

export interface ExportTask {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: number; // 0-100
  format: ExportFormat;
  filename: string;
  createdAt: Date;
  startedAt?: Date;
  completedAt?: Date;
  error?: string;
  result?: ExportResult;
}

export interface ExportResult {
  success: boolean;
  data?: Blob | string;
  filename: string;
  size: number; // bytes
  downloadUrl?: string;
  metadata?: {
    recordsCount: number;
    generatedAt: Date;
    version: string;
  };
}

export interface ExportTemplate {
  id: string;
  name: string;
  description: string;
  format: ExportFormat;
  fields: ExportField[];
  styling?: Record<string, any>;
  metadata?: Record<string, any>;
}

export interface ExportField {
  name: string;
  label: string;
  type: 'text' | 'numeric' | 'datetime' | 'boolean' | 'object' | 'array';
  required: boolean;
  defaultValue?: any;
  validation?: {
    min?: number;
    max?: number;
    pattern?: string;
    custom?: (value: any) => boolean;
  };
}

export class ExportManager {
  private tasks: Map<string, ExportTask> = new Map();
  private templates: ExportTemplate[] = [];
  private processingQueue: string[] = [];

  constructor() {
    this.initializeDefaultTemplates();
  }

  private initializeDefaultTemplates(): void {
    this.templates = [
      {
        id: 'project_report',
        name: 'Отчет по проекту',
        description: 'Стандартный отчет по проекту в PDF',
        format: 'pdf',
        fields: [
          {
            name: 'projectName',
            label: 'Название проекта',
            type: 'text',
            required: true
          },
          {
            name: 'projectDescription',
            label: 'Описание проекта',
            type: 'text',
            required: false
          },
          {
            name: 'tasks',
            label: 'Задачи',
            type: 'array',
            required: true
          },
          {
            name: 'budget',
            label: 'Бюджет',
            type: 'numeric',
            required: false
          }
        ]
      },
      {
        id: 'risk_analysis',
        name: 'Анализ рисков',
        description: 'Отчет по анализу рисков в Excel',
        format: 'xlsx',
        fields: [
          {
            name: 'riskFactors',
            label: 'Факторы риска',
            type: 'array',
            required: true
          },
          {
            name: 'mitigationStrategies',
            label: 'Стратегии митигации',
            type: 'array',
            required: false
          }
        ]
      }
    ];
  }

  /**
   * Создание новой задачи экспорта
   */
  async createExportTask(
    data: any, 
    options: ExportOptions, 
    templateId?: string
  ): Promise<string> {
    const taskId = this.generateTaskId();
    
    const task: ExportTask = {
      id: taskId,
      status: 'pending',
      progress: 0,
      format: options.format,
      filename: this.generateFilename(options.format),
      createdAt: new Date()
    };

    this.tasks.set(taskId, task);
    this.processingQueue.push(taskId);

    // Асинхронная обработка
    this.processExport(taskId, data, options, templateId).catch(error => {
      this.failTask(taskId, error.message);
    });

    return taskId;
  }

  /**
   * Обработка экспорта
   */
  private async processExport(
    taskId: string, 
    data: any, 
    options: ExportOptions, 
    templateId?: string
  ): Promise<void> {
    const task = this.tasks.get(taskId);
    if (!task) return;

    try {
      task.status = 'processing';
      task.startedAt = new Date();
      this.updateProgress(taskId, 10);

      // Валидация данных
      this.validateData(data, templateId);
      this.updateProgress(taskId, 30);

      // Генерация контента
      const content = await this.generateContent(data, options, templateId);
      this.updateProgress(taskId, 60);

      // Форматирование согласно формату
      const result = await this.formatContent(content, options);
      this.updateProgress(taskId, 90);

      // Сохранение результата
      const exportResult = await this.saveResult(result, options);
      
      task.result = exportResult;
      task.status = 'completed';
      task.progress = 100;
      task.completedAt = new Date();

    } catch (error) {
      this.failTask(taskId, error instanceof Error ? error.message : 'Неизвестная ошибка');
    }
  }

  private validateData(data: any, templateId?: string): void {
    if (!templateId) return;

    const template = this.templates.find(t => t.id === templateId);
    if (!template) {
      throw new Error(`Template not found: ${templateId}`);
    }

    // Валидация обязательных полей
    const requiredFields = template.fields.filter(f => f.required);
    for (const field of requiredFields) {
      if (!(field.name in data)) {
        throw new Error(`Required field missing: ${field.name}`);
      }

      // Валидация типа поля
      const value = data[field.name];
      if (!this.validateFieldType(value, field.type)) {
        throw new Error(`Invalid type for field ${field.name}: expected ${field.type}`);
      }

      // Валидация правил
      if (field.validation) {
        this.validateFieldRules(value, field.validation, field.name);
      }
    }
  }

  private validateFieldType(value: any, expectedType: string): boolean {
    if (value === null || value === undefined) return false;

    switch (expectedType) {
      case 'string':
        return typeof value === 'string';
      case 'number':
        return typeof value === 'number' && !isNaN(value);
      case 'boolean':
        return typeof value === 'boolean';
      case 'date':
        return value instanceof Date || !isNaN(Date.parse(value));
      case 'object':
        return typeof value === 'object' && !Array.isArray(value);
      case 'array':
        return Array.isArray(value);
      default:
        return true;
    }
  }

  private validateFieldRules(value: any, rules: any, fieldName: string): void {
    if (rules.min !== undefined && value < rules.min) {
      throw new Error(`Field ${fieldName} must be >= ${rules.min}`);
    }

    if (rules.max !== undefined && value > rules.max) {
      throw new Error(`Field ${fieldName} must be <= ${rules.max}`);
    }

    if (rules.pattern && !new RegExp(rules.pattern).test(value)) {
      throw new Error(`Field ${fieldName} does not match required pattern`);
    }

    if (rules.custom && !rules.custom(value)) {
      throw new Error(`Field ${fieldName} failed custom validation`);
    }
  }

  private async generateContent(data: any, options: ExportOptions, templateId?: string): Promise<any> {
    let content = { ...data };

    // Применение шаблона если указан
    if (templateId) {
      const template = this.templates.find(t => t.id === templateId);
      if (template) {
        content = this.applyTemplate(content, template);
      }
    }

    // Добавление метаданных если требуется
    if (options.includeMetadata) {
      content.metadata = {
        generatedAt: new Date(),
        version: '1.0',
        generator: 'ExportManager'
      };
    }

    return content;
  }

  private applyTemplate(data: any, template: ExportTemplate): any {
    const result: any = {};

    template.fields.forEach(field => {
      if (field.name in data) {
        result[field.name] = data[field.name];
      } else if (field.defaultValue !== undefined) {
        result[field.name] = field.defaultValue;
      }
    });

    return result;
  }

  private async formatContent(content: any, options: ExportOptions): Promise<ExportResult> {
    let formattedContent: Blob | string;
    let filename = this.generateFilename(options.format);

    switch (options.format) {
      case 'json':
        formattedContent = JSON.stringify(content, null, 2);
        break;
      
      case 'csv':
        formattedContent = this.convertToCSV(content);
        break;
      
      case 'xml':
        formattedContent = this.convertToXML(content);
        break;
      
      case 'html':
        formattedContent = this.convertToHTML(content);
        break;
      
      case 'txt':
        formattedContent = this.convertToText(content);
        break;
      
      case 'pdf':
      case 'docx':
      case 'xlsx':
        // В реальном приложении здесь был бы вызов соответствующих библиотек
        formattedContent = new Blob([`Mock ${options.format.toUpperCase()} content`], { 
          type: this.getMimeType(options.format) 
        });
        break;
      
      default:
        throw new Error(`Unsupported format: ${options.format}`);
    }

    // Подсчет размера
    const size = formattedContent instanceof Blob ? 
      formattedContent.size : 
      new Blob([formattedContent]).size;

    return {
      success: true,
      data: formattedContent,
      filename,
      size,
      metadata: {
        recordsCount: Array.isArray(content) ? content.length : 1,
        generatedAt: new Date(),
        version: '1.0'
      }
    };
  }

  private convertToCSV(data: any): string {
    if (!Array.isArray(data) || data.length === 0) {
      return '';
    }

    const headers = Object.keys(data[0]);
    const csvHeaders = headers.join(',');
    
    const csvRows = data.map(row => 
      headers.map(header => {
        const value = row[header];
        // Экранирование запятых и кавычек
        if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
          return `"${value.replace(/"/g, '""')}"`;
        }
        return value;
      }).join(',')
    );

    return [csvHeaders, ...csvRows].join('\n');
  }

  private convertToXML(data: any): string {
    const encodeXML = (str: string): string => {
      return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;');
    };

    const convertObject = (obj: any, rootName: string): string => {
      let xml = `<${rootName}>`;
      
      Object.entries(obj).forEach(([key, value]) => {
        if (Array.isArray(value)) {
          xml += `<${key}>`;
          value.forEach(item => {
            if (typeof item === 'object') {
              xml += convertObject(item, 'item');
            } else {
              xml += `<item>${encodeXML(String(item))}</item>`;
            }
          });
          xml += `</${key}>`;
        } else if (typeof value === 'object' && value !== null) {
          xml += convertObject(value, key);
        } else {
          xml += `<${key}>${encodeXML(String(value))}</${key}>`;
        }
      });
      
      xml += `</${rootName}>`;
      return xml;
    };

    const rootName = Array.isArray(data) ? 'data' : 'export';
    const xmlData = Array.isArray(data) ? 
      data.map(item => convertObject(item, 'item')).join('') :
      convertObject(data, rootName);

    return `<?xml version="1.0" encoding="UTF-8"?>\n<root>${xmlData}</root>`;
  }

  private convertToHTML(data: any): string {
    const style = `
      <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .metadata { background-color: #f9f9f9; padding: 10px; margin-bottom: 20px; }
      </style>
    `;

    const generateHTMLTable = (obj: any): string => {
      if (Array.isArray(obj) && obj.length > 0 && typeof obj[0] === 'object') {
        // Таблица из массива объектов
        const headers = Object.keys(obj[0]);
        let html = '<table><thead><tr>';
        headers.forEach(header => {
          html += `<th>${header}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        obj.forEach(item => {
          html += '<tr>';
          headers.forEach(header => {
            const value = item[header];
            html += `<td>${this.escapeHTML(String(value))}</td>`;
          });
          html += '</tr>';
        });
        
        html += '</tbody></table>';
        return html;
      } else {
        // Простой список свойств
        let html = '<div class="data">';
        Object.entries(obj).forEach(([key, value]) => {
          html += `<div><strong>${key}:</strong> ${this.escapeHTML(String(value))}</div>`;
        });
        html += '</div>';
        return html;
      }
    };

    let content = '<div class="content">';
    
    if (Array.isArray(data)) {
      data.forEach((item, index) => {
        content += `<h2>Item ${index + 1}</h2>${generateHTMLTable(item)}`;
      });
    } else {
      content += generateHTMLTable(data);
    }
    
    content += '</div>';

    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Export Report</title>
  ${style}
</head>
<body>
  <h1>Export Report</h1>
  <div class="metadata">
    <p><strong>Generated:</strong> ${new Date().toLocaleString()}</p>
    <p><strong>Records:</strong> ${Array.isArray(data) ? data.length : 1}</p>
  </div>
  ${content}
</body>
</html>`;
  }

  private convertToText(data: any): string {
    const formatValue = (value: any, indent: number = 0): string => {
      const spaces = ' '.repeat(indent);
      
      if (Array.isArray(value)) {
        return value.map(item => formatValue(item, indent + 2)).join('\n');
      } else if (typeof value === 'object' && value !== null) {
        return Object.entries(value)
          .map(([key, val]) => `${spaces}${key}: ${formatValue(val, indent + 2)}`)
          .join('\n');
      } else {
        return `${spaces}${value}`;
      }
    };

    return formatValue(data);
  }

  private escapeHTML(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  private async saveResult(result: ExportResult, options: ExportOptions): Promise<ExportResult> {
    // В реальном приложении здесь была бы загрузка в хранилище
    // Пока что просто возвращаем результат как есть
    
    if (typeof result.data === 'string') {
      result.data = new Blob([result.data], { type: this.getMimeType(options.format) });
    }

    // Генерируем URL для скачивания (mock)
    if (result.data instanceof Blob) {
      result.downloadUrl = URL.createObjectURL(result.data);
    }

    return result;
  }

  private getMimeType(format: ExportFormat): string {
    const mimeTypes: Record<ExportFormat, string> = {
      'pdf': 'application/pdf',
      'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'csv': 'text/csv',
      'json': 'application/json',
      'xml': 'application/xml',
      'html': 'text/html',
      'txt': 'text/plain'
    };

    return mimeTypes[format];
  }

  private generateFilename(format: ExportFormat): string {
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '');
    return `export_${timestamp}.${format}`;
  }

  private generateTaskId(): string {
    return `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Получение статуса задачи
   */
  getTaskStatus(taskId: string): ExportTask | null {
    return this.tasks.get(taskId) || null;
  }

  /**
   * Получение всех задач
   */
  getAllTasks(): ExportTask[] {
    return Array.from(this.tasks.values());
  }

  /**
   * Отмена задачи
   */
  cancelTask(taskId: string): boolean {
    const task = this.tasks.get(taskId);
    if (!task || task.status === 'completed' || task.status === 'failed') {
      return false;
    }

    task.status = 'cancelled';
    this.processingQueue = this.processingQueue.filter(id => id !== taskId);
    return true;
  }

  /**
   * Получение доступных шаблонов
   */
  getTemplates(): ExportTemplate[] {
    return [...this.templates];
  }

  /**
   * Создание пользовательского шаблона
   */
  createTemplate(template: Omit<ExportTemplate, 'id'>): string {
    const id = `template_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const newTemplate: ExportTemplate = { ...template, id };
    this.templates.push(newTemplate);
    return id;
  }

  /**
   * Скачивание результата
   */
  downloadResult(taskId: string): void {
    const task = this.tasks.get(taskId);
    if (!task || !task.result || !task.result.downloadUrl) {
      throw new Error('Task not found or result not available');
    }

    const link = document.createElement('a');
    link.href = task.result.downloadUrl;
    link.download = task.result.filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  /**
   * Обновление прогресса задачи
   */
  private updateProgress(taskId: string, progress: number): void {
    const task = this.tasks.get(taskId);
    if (task) {
      task.progress = progress;
    }
  }

  /**
   * Отметка задачи как неуспешной
   */
  private failTask(taskId: string, error: string): void {
    const task = this.tasks.get(taskId);
    if (task) {
      task.status = 'failed';
      task.error = error;
      task.completedAt = new Date();
    }
  }

  /**
   * Очистка завершенных задач
   */
  cleanup(): void {
    const now = Date.now();
    const maxAge = 24 * 60 * 60 * 1000; // 24 часа

    for (const [taskId, task] of this.tasks.entries()) {
      if (task.completedAt && (now - task.completedAt.getTime()) > maxAge) {
        this.tasks.delete(taskId);
      }
    }
  }
}

// Экспорт экземпляра сервиса для глобального использования
export const exportManager = new ExportManager();

// Дополнительные типы для обратной совместимости
export type ExportData = any;
export type ExportManager = ExportManager;