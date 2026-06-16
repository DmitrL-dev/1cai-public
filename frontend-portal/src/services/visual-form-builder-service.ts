/**
 * Visual Form Builder Service
 * Сервис для создания форм с помощью визуального конструктора
 */

export interface FormField {
  id: string;
  type: 'text' | 'email' | 'password' | 'number' | 'textarea' | 'select' | 'checkbox' | 'radio' | 'date' | 'file';
  label: string;
  placeholder?: string;
  required: boolean;
  validation?: FormValidation;
  options?: FormOption[];
  defaultValue?: any;
  helpText?: string;
  order: number;
  width?: 'full' | 'half' | 'third' | 'quarter';
  style?: FormFieldStyle;
  conditionalLogic?: ConditionalLogic;
}

export interface FormOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface FormValidation {
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  customValidator?: string;
  errorMessage?: string;
}

export interface FormFieldStyle {
  className?: string;
  customCSS?: Record<string, string>;
}

export interface ConditionalLogic {
  showWhen: {
    fieldId: string;
    operator: 'equals' | 'not_equals' | 'contains' | 'not_contains' | 'greater_than' | 'less_than';
    value: any;
  };
  logicalOperator?: 'and' | 'or';
  conditions?: ConditionalLogic[];
}

export interface FormLayout {
  title: string;
  description?: string;
  submitButtonText: string;
  resetButtonText?: string;
  fieldsPerRow?: number;
  showProgressBar?: boolean;
  enableAjax?: boolean;
  customCSS?: string;
  customJS?: string;
}

export interface FormSettings {
  layout: FormLayout;
  emailNotifications?: EmailNotification[];
  databaseIntegration?: DatabaseIntegration;
  integrations?: FormIntegration[];
  security?: FormSecurity;
}

export interface EmailNotification {
  id: string;
  trigger: 'submission' | 'approval' | 'rejection';
  to: string[];
  cc?: string[];
  bcc?: string[];
  subject: string;
  template: string;
  attachments?: string[];
}

export interface DatabaseIntegration {
  enabled: boolean;
  tableName: string;
  fields: Array<{
    formFieldId: string;
    databaseColumn: string;
    dataType: string;
    required: boolean;
  }>;
}

export interface FormIntegration {
  type: 'webhook' | 'api' | 'zapier' | 'make';
  config: Record<string, any>;
  enabled: boolean;
}

export interface FormSecurity {
  enableCSRF: boolean;
  enableCaptcha: boolean;
  allowedFileTypes?: string[];
  maxFileSize?: number;
  rateLimiting?: {
    enabled: boolean;
    maxSubmissions: number;
    timeWindow: number; // в минутах
  };
}

export interface FormSubmission {
  id: string;
  formId: string;
  data: Record<string, any>;
  submittedAt: Date;
  ipAddress?: string;
  userAgent?: string;
  status: 'pending' | 'approved' | 'rejected';
  reviewedBy?: string;
  reviewedAt?: Date;
  reviewNotes?: string;
  attachments?: FormAttachment[];
}

export interface FormAttachment {
  id: string;
  fieldId: string;
  filename: string;
  originalName: string;
  size: number;
  mimeType: string;
  uploadedAt: Date;
  url?: string;
}

export interface FormAnalytics {
  formId: string;
  totalViews: number;
  totalSubmissions: number;
  conversionRate: number;
  averageCompletionTime: number;
  abandonmentRate: number;
  fieldAnalytics: FieldAnalytics[];
  submissionTrends: Array<{
    date: Date;
    submissions: number;
    views: number;
  }>;
}

export interface FieldAnalytics {
  fieldId: string;
  fieldLabel: string;
  viewCount: number;
  completionCount: number;
  averageTime: number;
  errorRate: number;
  dropOffRate: number;
}

export class VisualFormBuilderService {
  private forms = new Map<string, {
    fields: FormField[];
    settings: FormSettings;
    createdAt: Date;
    updatedAt: Date;
  }>();
  private submissions = new Map<string, FormSubmission[]>();
  private analytics = new Map<string, FormAnalytics>();

  constructor() {}

  /**
   * Создание новой формы
   */
  createForm(formId: string, fields: FormField[], settings: FormSettings): void {
    this.forms.set(formId, {
      fields: fields.sort((a, b) => a.order - b.order),
      settings,
      createdAt: new Date(),
      updatedAt: new Date()
    });

    // Инициализируем аналитику
    this.initializeAnalytics(formId);
  }

  /**
   * Обновление формы
   */
  updateForm(formId: string, fields?: FormField[], settings?: Partial<FormSettings>): boolean {
    const form = this.forms.get(formId);
    if (!form) return false;

    if (fields) {
      form.fields = fields.sort((a, b) => a.order - b.order);
    }

    if (settings) {
      form.settings = { ...form.settings, ...settings };
    }

    form.updatedAt = new Date();
    return true;
  }

  /**
   * Удаление формы
   */
  deleteForm(formId: string): boolean {
    const deleted = this.forms.delete(formId);
    if (deleted) {
      this.submissions.delete(formId);
      this.analytics.delete(formId);
    }
    return deleted;
  }

  /**
   * Получение формы
   */
  getForm(formId: string): { fields: FormField[]; settings: FormSettings } | null {
    return this.forms.get(formId) || null;
  }

  /**
   * Получение всех форм
   */
  getAllForms(): Array<{ formId: string; fields: FormField[]; settings: FormSettings }> {
    return Array.from(this.forms.entries()).map(([formId, form]) => ({
      formId,
      fields: form.fields,
      settings: form.settings
    }));
  }

  /**
   * Добавление поля в форму
   */
  addField(formId: string, field: FormField): boolean {
    const form = this.forms.get(formId);
    if (!form) return false;

    form.fields.push(field);
    form.fields.sort((a, b) => a.order - b.order);
    form.updatedAt = new Date();
    return true;
  }

  /**
   * Обновление поля
   */
  updateField(formId: string, fieldId: string, updates: Partial<FormField>): boolean {
    const form = this.forms.get(formId);
    if (!form) return false;

    const fieldIndex = form.fields.findIndex(f => f.id === fieldId);
    if (fieldIndex === -1) return false;

    form.fields[fieldIndex] = { ...form.fields[fieldIndex], ...updates };
    form.updatedAt = new Date();
    return true;
  }

  /**
   * Удаление поля
   */
  removeField(formId: string, fieldId: string): boolean {
    const form = this.forms.get(formId);
    if (!form) return false;

    const fieldIndex = form.fields.findIndex(f => f.id === fieldId);
    if (fieldIndex === -1) return false;

    form.fields.splice(fieldIndex, 1);
    form.updatedAt = new Date();
    return true;
  }

  /**
   * Переупорядочение полей
   */
  reorderFields(formId: string, fieldOrders: Array<{ fieldId: string; order: number }>): boolean {
    const form = this.forms.get(formId);
    if (!form) return false;

    fieldOrders.forEach(({ fieldId, order }) => {
      const field = form.fields.find(f => f.id === fieldId);
      if (field) {
        field.order = order;
      }
    });

    form.fields.sort((a, b) => a.order - b.order);
    form.updatedAt = new Date();
    return true;
  }

  /**
   * Валидация формы
   */
  validateForm(formId: string, data: Record<string, any>): { isValid: boolean; errors: Record<string, string> } {
    const form = this.forms.get(formId);
    if (!form) {
      return { isValid: false, errors: { general: 'Форма не найдена' } };
    }

    const errors: Record<string, string> = {};

    form.fields.forEach(field => {
      const value = data[field.id];

      // Проверка обязательности
      if (field.required && (value === undefined || value === null || value === '')) {
        errors[field.id] = field.validation?.errorMessage || `Поле "${field.label}" обязательно для заполнения`;
        return;
      }

      // Пропускаем валидацию если поле пустое и не обязательное
      if (!field.required && (value === undefined || value === null || value === '')) {
        return;
      }

      // Валидация длины
      if (field.validation?.minLength && String(value).length < field.validation.minLength) {
        errors[field.id] = `Минимальная длина: ${field.validation.minLength} символов`;
      }

      if (field.validation?.maxLength && String(value).length > field.validation.maxLength) {
        errors[field.id] = `Максимальная длина: ${field.validation.maxLength} символов`;
      }

      // Валидация паттерна
      if (field.validation?.pattern) {
        const regex = new RegExp(field.validation.pattern);
        if (!regex.test(String(value))) {
          errors[field.id] = field.validation.errorMessage || 'Неверный формат поля';
        }
      }

      // Валидация типа поля
      switch (field.type) {
        case 'email':
          const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
          if (!emailRegex.test(String(value))) {
            errors[field.id] = 'Неверный формат email адреса';
          }
          break;
        case 'number':
          if (isNaN(Number(value))) {
            errors[field.id] = 'Поле должно содержать число';
          }
          break;
        case 'date':
          if (isNaN(Date.parse(String(value)))) {
            errors[field.id] = 'Неверный формат даты';
          }
          break;
      }
    });

    return {
      isValid: Object.keys(errors).length === 0,
      errors
    };
  }

  /**
   * Отправка формы
   */
  async submitForm(formId: string, data: Record<string, any>, metadata?: {
    ipAddress?: string;
    userAgent?: string;
  }): Promise<{ success: boolean; submissionId?: string; error?: string }> {
    const form = this.forms.get(formId);
    if (!form) {
      return { success: false, error: 'Форма не найдена' };
    }

    // Валидация
    const validation = this.validateForm(formId, data);
    if (!validation.isValid) {
      return { success: false, error: 'Валидация не пройдена', ...validation };
    }

    const submission: FormSubmission = {
      id: this.generateSubmissionId(),
      formId,
      data,
      submittedAt: new Date(),
      ipAddress: metadata?.ipAddress,
      userAgent: metadata?.userAgent,
      status: 'pending'
    };

    // Сохраняем отправку
    if (!this.submissions.has(formId)) {
      this.submissions.set(formId, []);
    }
    this.submissions.get(formId)!.push(submission);

    // Обновляем аналитику
    this.updateAnalytics(formId, 'submission');

    // Обрабатываем интеграции
    try {
      await this.processIntegrations(formId, submission);
    } catch (error) {
      console.warn('Ошибка обработки интеграций:', error);
    }

    // Отправляем уведомления по email
    try {
      await this.processEmailNotifications(formId, submission);
    } catch (error) {
      console.warn('Ошибка отправки email уведомлений:', error);
    }

    return { success: true, submissionId: submission.id };
  }

  /**
   * Получение отправок формы
   */
  getSubmissions(formId: string, status?: FormSubmission['status']): FormSubmission[] {
    const submissions = this.submissions.get(formId) || [];
    return status ? submissions.filter(s => s.status === status) : submissions;
  }

  /**
   * Обновление статуса отправки
   */
  updateSubmissionStatus(formId: string, submissionId: string, status: FormSubmission['status'], reviewedBy?: string, reviewNotes?: string): boolean {
    const submissions = this.submissions.get(formId);
    if (!submissions) return false;

    const submission = submissions.find(s => s.id === submissionId);
    if (!submission) return false;

    submission.status = status;
    submission.reviewedBy = reviewedBy;
    submission.reviewedAt = new Date();
    submission.reviewNotes = reviewNotes;

    return true;
  }

  /**
   * Получение аналитики формы
   */
  getFormAnalytics(formId: string): FormAnalytics | null {
    return this.analytics.get(formId) || null;
  }

  /**
   * Экспорт формы в JSON
   */
  exportForm(formId: string): string | null {
    const form = this.forms.get(formId);
    if (!form) return null;

    const exportData = {
      formId,
      ...form,
      exportedAt: new Date().toISOString()
    };

    return JSON.stringify(exportData, null, 2);
  }

  /**
   * Импорт формы из JSON
   */
  importForm(formJson: string): { success: boolean; formId?: string; error?: string } {
    try {
      const importData = JSON.parse(formJson);
      
      if (!importData.formId || !importData.fields || !importData.settings) {
        return { success: false, error: 'Неверный формат данных формы' };
      }

      this.forms.set(importData.formId, {
        fields: importData.fields,
        settings: importData.settings,
        createdAt: new Date(importData.createdAt),
        updatedAt: new Date(importData.updatedAt)
      });

      return { success: true, formId: importData.formId };

    } catch (error) {
      return { success: false, error: 'Ошибка парсинга JSON' };
    }
  }

  /**
   * Клонирование формы
   */
  cloneForm(formId: string, newFormId: string): boolean {
    const originalForm = this.forms.get(formId);
    if (!originalForm) return false;

    const clonedForm = {
      fields: originalForm.fields.map(field => ({
        ...field,
        id: this.generateFieldId()
      })),
      settings: { ...originalForm.settings },
      createdAt: new Date(),
      updatedAt: new Date()
    };

    this.forms.set(newFormId, clonedForm);
    this.initializeAnalytics(newFormId);

    return true;
  }

  /**
   * Проверка доступности ID формы
   */
  isFormIdAvailable(formId: string): boolean {
    return !this.forms.has(formId);
  }

  /**
   * Получение статистики сервиса
   */
  getServiceStats(): {
    totalForms: number;
    totalSubmissions: number;
    averageFieldsPerForm: number;
    mostPopularFieldTypes: Array<{ type: string; count: number }>;
  } {
    const totalForms = this.forms.size;
    const totalSubmissions = Array.from(this.submissions.values())
      .reduce((sum, submissions) => sum + submissions.length, 0);

    const totalFields = Array.from(this.forms.values())
      .reduce((sum, form) => sum + form.fields.length, 0);
    
    const averageFieldsPerForm = totalForms > 0 ? totalFields / totalForms : 0;

    // Подсчет типов полей
    const fieldTypeCounts = new Map<string, number>();
    this.forms.forEach(form => {
      form.fields.forEach(field => {
        fieldTypeCounts.set(field.type, (fieldTypeCounts.get(field.type) || 0) + 1);
      });
    });

    const mostPopularFieldTypes = Array.from(fieldTypeCounts.entries())
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);

    return {
      totalForms,
      totalSubmissions,
      averageFieldsPerForm: Math.round(averageFieldsPerForm * 100) / 100,
      mostPopularFieldTypes
    };
  }

  // Private methods

  private initializeAnalytics(formId: string): void {
    this.analytics.set(formId, {
      formId,
      totalViews: 0,
      totalSubmissions: 0,
      conversionRate: 0,
      averageCompletionTime: 0,
      abandonmentRate: 0,
      fieldAnalytics: [],
      submissionTrends: []
    });
  }

  private updateAnalytics(formId: string, event: 'view' | 'submission'): void {
    const analytics = this.analytics.get(formId);
    if (!analytics) return;

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    switch (event) {
      case 'view':
        analytics.totalViews++;
        break;
      case 'submission':
        analytics.totalSubmissions++;
        // Обновляем тренды
        const todayTrend = analytics.submissionTrends.find(t => 
          t.date.getTime() === today.getTime()
        );
        if (todayTrend) {
          todayTrend.submissions++;
          todayTrend.views++;
        } else {
          analytics.submissionTrends.push({
            date: today,
            submissions: 1,
            views: 1
          });
        }
        break;
    }

    // Пересчитываем метрики
    analytics.conversionRate = analytics.totalViews > 0 
      ? (analytics.totalSubmissions / analytics.totalViews) * 100 
      : 0;
  }

  private async processIntegrations(formId: string, submission: FormSubmission): Promise<void> {
    const form = this.forms.get(formId);
    if (!form || !form.settings.integrations) return;

    for (const integration of form.settings.integrations) {
      if (!integration.enabled) continue;

      try {
        switch (integration.type) {
          case 'webhook':
            await this.processWebhookIntegration(integration, submission);
            break;
          case 'api':
            await this.processAPIIntegration(integration, submission);
            break;
          // Добавить другие типы интеграций
        }
      } catch (error) {
        console.warn(`Ошибка интеграции ${integration.type}:`, error);
      }
    }
  }

  private async processWebhookIntegration(integration: FormIntegration, submission: FormSubmission): Promise<void> {
    // Упрощенная реализация webhook
    try {
      await fetch(integration.config.url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...integration.config.headers
        },
        body: JSON.stringify({
          event: 'form_submission',
          formId: submission.formId,
          submissionId: submission.id,
          data: submission.data,
          timestamp: submission.submittedAt
        })
      });
    } catch (error) {
      console.warn('Webhook интеграция не удалась:', error);
    }
  }

  private async processAPIIntegration(integration: FormIntegration, submission: FormSubmission): Promise<void> {
    // Упрощенная реализация API интеграции
    if (integration.config.endpoint) {
      try {
        await fetch(integration.config.endpoint, {
          method: integration.config.method || 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...integration.config.headers
          },
          body: JSON.stringify(submission.data)
        });
      } catch (error) {
        console.warn('API интеграция не удалась:', error);
      }
    }
  }

  private async processEmailNotifications(formId: string, submission: FormSubmission): Promise<void> {
    const form = this.forms.get(formId);
    if (!form || !form.settings.emailNotifications) return;

    // Упрощенная реализация отправки email
    // В реальном приложении здесь была бы интеграция с email сервисом
    console.log('Отправка email уведомлений для формы', formId);
  }

  private generateFieldId(): string {
    return `field_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private generateSubmissionId(): string {
    return `sub_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

// Экспортируем instance по умолчанию
export const visualFormBuilderService = new VisualFormBuilderService();