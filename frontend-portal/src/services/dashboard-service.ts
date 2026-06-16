/**
 * Сервис интерактивных дашбордов для анализа данных 1C
 * Поддерживает создание, настройку и управление аналитическими панелями
 */

import { apiClient } from "../lib/api-client";

export interface MetricDefinition {
  id: string;
  name: string;
  type: "number" | "percentage" | "currency" | "text" | "datetime";
  source: string;
  calculation?: string;
  format?: string;
  color?: string;
  icon?: string;
  description?: string;
}

export interface ChartConfiguration {
  id: string;
  type: "bar" | "line" | "pie" | "area" | "scatter" | "gauge" | "heatmap";
  title: string;
  dataSource: string;
  xAxis?: string;
  yAxis?: string;
  colorScheme?: string;
  showLegend?: boolean;
  showGrid?: boolean;
  responsive?: boolean;
  animation?: boolean;
  config?: any;
}

export interface DashboardWidget {
  id: string;
  type: "metric" | "chart" | "table" | "text" | "map";
  title: string;
  position: { x: number; y: number; width: number; height: number };
  config: MetricDefinition | ChartConfiguration | any;
  refreshInterval?: number;
  filters?: DashboardFilter[];
  actions?: WidgetAction[];
}

export interface DashboardFilter {
  id: string;
  type: "date-range" | "select" | "multi-select" | "text" | "number";
  field: string;
  label: string;
  options?: FilterOption[];
  defaultValue?: any;
  required?: boolean;
}

export interface FilterOption {
  value: string | number;
  label: string;
  color?: string;
}

export interface WidgetAction {
  id: string;
  type: "link" | "modal" | "download" | "refresh" | "filter";
  label: string;
  icon?: string;
  config: any;
}

export interface Dashboard {
  id: string;
  name: string;
  description?: string;
  widgets: DashboardWidget[];
  filters: DashboardFilter[];
  layout: DashboardLayout;
  permissions: DashboardPermissions;
  createdAt: Date;
  updatedAt: Date;
  tags?: string[];
  isPublic?: boolean;
  owner: string;
}

export interface DashboardLayout {
  columns: number;
  rows: number;
  spacing: number;
  theme: "light" | "dark" | "auto";
  backgroundColor?: string;
  textColor?: string;
  accentColor?: string;
}

export interface DashboardPermissions {
  viewers: string[];
  editors: string[];
  isPublic: boolean;
}

export interface DashboardMetrics {
  totalViews: number;
  uniqueVisitors: number;
  averageTimeOnDashboard: number;
  mostUsedWidgets: string[];
  filterUsage: FilterUsageStats[];
  performanceScore: number;
}

export interface FilterUsageStats {
  filterId: string;
  filterName: string;
  usageCount: number;
  uniqueUsers: number;
}

export interface DashboardTemplate {
  id: string;
  name: string;
  description: string;
  category:
    | "financial"
    | "operational"
    | "sales"
    | "inventory"
    | "hr"
    | "custom";
  widgets: Partial<DashboardWidget>[];
  previewImage?: string;
  tags: string[];
  isBuiltIn: boolean;
}

export class DashboardService {
  private dashboards: Map<string, Dashboard> = new Map();
  private templates: Map<string, DashboardTemplate> = new Map();
  private metrics: Map<string, DashboardMetrics> = new Map();

  constructor() {
    this.initializeBuiltInTemplates();
  }

  /**
   * Инициализация встроенных шаблонов дашбордов
   */
  private initializeBuiltInTemplates(): void {
    // Финансовый дашборд
    this.templates.set("financial-overview", {
      id: "financial-overview",
      name: "Обзор финансов",
      description: "Основные финансовые показатели и KPI",
      category: "financial",
      widgets: [
        {
          id: "revenue-metric",
          type: "metric",
          title: "Выручка",
          position: { x: 0, y: 0, width: 3, height: 2 },
          config: {
            id: "revenue",
            name: "Выручка",
            type: "currency",
            source: "financial_data.revenue",
            format: "currency",
            color: "#22c55e",
            icon: "💰",
          },
        },
        {
          id: "expenses-metric",
          type: "metric",
          title: "Расходы",
          position: { x: 3, y: 0, width: 3, height: 2 },
          config: {
            id: "expenses",
            name: "Расходы",
            type: "currency",
            source: "financial_data.expenses",
            format: "currency",
            color: "#ef4444",
            icon: "💸",
          },
        },
        {
          id: "profit-chart",
          type: "chart",
          title: "Прибыль по месяцам",
          position: { x: 0, y: 2, width: 6, height: 4 },
          config: {
            id: "profit-trend",
            type: "line",
            title: "Тренд прибыли",
            dataSource: "financial_data.profit",
            xAxis: "month",
            yAxis: "amount",
            colorScheme: "#22c55e",
          },
        },
      ],
      tags: ["финансы", "KPI", "доходы"],
      isBuiltIn: true,
    });

    // Операционный дашборд
    this.templates.set("operational-metrics", {
      id: "operational-metrics",
      name: "Операционные метрики",
      description: "Ключевые операционные показатели производства",
      category: "operational",
      widgets: [
        {
          id: "production-volume",
          type: "metric",
          title: "Объем производства",
          position: { x: 0, y: 0, width: 2, height: 2 },
          config: {
            id: "production_volume",
            name: "Объем производства",
            type: "number",
            source: "production.volume",
            format: "number",
            color: "#3b82f6",
            icon: "🏭",
          },
        },
        {
          id: "efficiency-gauge",
          type: "chart",
          title: "Эффективность производства",
          position: { x: 2, y: 0, width: 2, height: 2 },
          config: {
            id: "efficiency",
            type: "gauge",
            title: "Эффективность",
            dataSource: "production.efficiency",
            colorScheme: "#10b981",
          },
        },
        {
          id: "quality-metrics",
          type: "chart",
          title: "Показатели качества",
          position: { x: 4, y: 0, width: 2, height: 2 },
          config: {
            id: "quality",
            type: "pie",
            title: "Качество продукции",
            dataSource: "production.quality",
            colorScheme: "#f59e0b",
          },
        },
      ],
      tags: ["производство", "эффективность", "качество"],
      isBuiltIn: true,
    });

    // Продажный дашборд
    this.templates.set("sales-analytics", {
      id: "sales-analytics",
      name: "Аналитика продаж",
      description: "Детальная аналитика продаж и клиентской активности",
      category: "sales",
      widgets: [
        {
          id: "sales-chart",
          type: "chart",
          title: "Динамика продаж",
          position: { x: 0, y: 0, width: 4, height: 3 },
          config: {
            id: "sales_trend",
            type: "bar",
            title: "Продажи по месяцам",
            dataSource: "sales.data",
            xAxis: "month",
            yAxis: "amount",
            colorScheme: "#8b5cf6",
          },
        },
        {
          id: "top-products",
          type: "chart",
          title: "Топ товары",
          position: { x: 4, y: 0, width: 2, height: 3 },
          config: {
            id: "top_products",
            type: "pie",
            title: "Лучшие товары",
            dataSource: "sales.top_products",
            colorScheme: "#ec4899",
          },
        },
      ],
      tags: ["продажи", "аналитика", "товары"],
      isBuiltIn: true,
    });

    // Складской дашборд
    this.templates.set("inventory-management", {
      id: "inventory-management",
      name: "Управление складом",
      description: "Контроль остатков и оборачиваемости товаров",
      category: "inventory",
      widgets: [
        {
          id: "stock-levels",
          type: "metric",
          title: "Уровень запасов",
          position: { x: 0, y: 0, width: 2, height: 2 },
          config: {
            id: "stock_level",
            name: "Уровень запасов",
            type: "number",
            source: "inventory.stock_level",
            format: "number",
            color: "#06b6d4",
            icon: "📦",
          },
        },
        {
          id: "turnover-chart",
          type: "chart",
          title: "Оборачиваемость",
          position: { x: 2, y: 0, width: 4, height: 2 },
          config: {
            id: "turnover",
            type: "line",
            title: "Оборачиваемость товаров",
            dataSource: "inventory.turnover",
            xAxis: "product",
            yAxis: "turnover_rate",
            colorScheme: "#84cc16",
          },
        },
      ],
      tags: ["склад", "запасы", "оборачиваемость"],
      isBuiltIn: true,
    });
  }

  /**
   * Создание нового дашборда
   */
  createDashboard(
    name: string,
    description?: string,
    templateId?: string
  ): string {
    const id = this.generateId();
    let dashboard: Dashboard;

    if (templateId && this.templates.has(templateId)) {
      const template = this.templates.get(templateId)!;
      dashboard = this.createFromTemplate(template, name, description);
    } else {
      dashboard = this.createEmptyDashboard(id, name, description);
    }

    this.dashboards.set(id, dashboard);
    this.initializeMetrics(id);

    return id;
  }

  /**
   * Создание дашборда из шаблона
   */
  private createFromTemplate(
    template: DashboardTemplate,
    name: string,
    description?: string
  ): Dashboard {
    return {
      id: this.generateId(),
      name,
      description: description || template.description,
      widgets: template.widgets.map((widget) => ({
        id: this.generateId(),
        type: widget.type!,
        title: widget.title!,
        position: widget.position!,
        config: widget.config!,
      })),
      filters: [],
      layout: {
        columns: 6,
        rows: 8,
        spacing: 16,
        theme: "light",
        backgroundColor: "#ffffff",
        textColor: "#1f2937",
        accentColor: "#3b82f6",
      },
      permissions: {
        viewers: [],
        editors: [],
        isPublic: false,
      },
      createdAt: new Date(),
      updatedAt: new Date(),
      tags: template.tags,
      isPublic: false,
      owner: "current-user",
    };
  }

  /**
   * Создание пустого дашборда
   */
  private createEmptyDashboard(
    id: string,
    name: string,
    description?: string
  ): Dashboard {
    return {
      id,
      name,
      description,
      widgets: [],
      filters: [],
      layout: {
        columns: 6,
        rows: 8,
        spacing: 16,
        theme: "light",
        backgroundColor: "#ffffff",
        textColor: "#1f2937",
        accentColor: "#3b82f6",
      },
      permissions: {
        viewers: [],
        editors: [],
        isPublic: false,
      },
      createdAt: new Date(),
      updatedAt: new Date(),
      tags: [],
      isPublic: false,
      owner: "current-user",
    };
  }

  /**
   * Получение дашборда по ID
   */
  getDashboard(id: string): Dashboard | null {
    return this.dashboards.get(id) || null;
  }

  /**
   * Получение всех дашбордов пользователя
   */
  getUserDashboards(userId: string): Dashboard[] {
    return Array.from(this.dashboards.values()).filter(
      (dashboard) =>
        dashboard.owner === userId ||
        dashboard.permissions.viewers.includes(userId)
    );
  }

  /**
   * Обновление дашборда
   */
  updateDashboard(id: string, updates: Partial<Dashboard>): boolean {
    const dashboard = this.dashboards.get(id);
    if (!dashboard) return false;

    const updatedDashboard = {
      ...dashboard,
      ...updates,
      id: dashboard.id,
      createdAt: dashboard.createdAt,
      updatedAt: new Date(),
    };

    this.dashboards.set(id, updatedDashboard);
    return true;
  }

  /**
   * Добавление виджета к дашборду
   */
  addWidget(dashboardId: string, widget: Omit<DashboardWidget, "id">): string {
    const dashboard = this.dashboards.get(dashboardId);
    if (!dashboard) throw new Error("Дашборд не найден");

    const widgetId = this.generateId();
    const newWidget: DashboardWidget = {
      ...widget,
      id: widgetId,
    };

    dashboard.widgets.push(newWidget);
    dashboard.updatedAt = new Date();
    this.dashboards.set(dashboardId, dashboard);

    return widgetId;
  }

  /**
   * Обновление виджета
   */
  updateWidget(
    dashboardId: string,
    widgetId: string,
    updates: Partial<DashboardWidget>
  ): boolean {
    const dashboard = this.dashboards.get(dashboardId);
    if (!dashboard) return false;

    const widgetIndex = dashboard.widgets.findIndex((w) => w.id === widgetId);
    if (widgetIndex === -1) return false;

    dashboard.widgets[widgetIndex] = {
      ...dashboard.widgets[widgetIndex],
      ...updates,
      id: widgetId,
    };

    dashboard.updatedAt = new Date();
    this.dashboards.set(dashboardId, dashboard);

    return true;
  }

  /**
   * Удаление виджета
   */
  removeWidget(dashboardId: string, widgetId: string): boolean {
    const dashboard = this.dashboards.get(dashboardId);
    if (!dashboard) return false;

    const initialLength = dashboard.widgets.length;
    dashboard.widgets = dashboard.widgets.filter((w) => w.id !== widgetId);

    if (dashboard.widgets.length === initialLength) return false;

    dashboard.updatedAt = new Date();
    this.dashboards.set(dashboardId, dashboard);

    return true;
  }

  /**
   * Добавление фильтра
   */
  addFilter(dashboardId: string, filter: Omit<DashboardFilter, "id">): string {
    const dashboard = this.dashboards.get(dashboardId);
    if (!dashboard) throw new Error("Дашборд не найден");

    const filterId = this.generateId();
    const newFilter: DashboardFilter = {
      ...filter,
      id: filterId,
    };

    dashboard.filters.push(newFilter);
    dashboard.updatedAt = new Date();
    this.dashboards.set(dashboardId, dashboard);

    return filterId;
  }

  /**
   * Применение фильтров к данным
   */
  applyFilters(
    data: any[],
    filters: DashboardFilter[],
    filterValues: Record<string, any>
  ): any[] {
    return data.filter((item) => {
      return filters.every((filter) => {
        const value = filterValues[filter.id];
        if (value === undefined || value === null) return true;

        switch (filter.type) {
          case "date-range":
            if (filter.required && (!value.start || !value.end)) return false;
            const itemDate = new Date(item[filter.field]);
            return (
              itemDate >= new Date(value.start) &&
              itemDate <= new Date(value.end)
            );

          case "select":
            return item[filter.field] === value;

          case "multi-select":
            return Array.isArray(value)
              ? value.includes(item[filter.field])
              : false;

          case "text":
            return String(item[filter.field])
              .toLowerCase()
              .includes(String(value).toLowerCase());

          case "number":
            return (
              item[filter.field] >= value.min && item[filter.field] <= value.max
            );

          default:
            return true;
        }
      });
    });
  }

  /**
   * Получение доступных шаблонов
   */
  getTemplates(): DashboardTemplate[] {
    return Array.from(this.templates.values());
  }

  /**
   * Создание шаблона из дашборда
   */
  createTemplate(
    dashboardId: string,
    name: string,
    description: string,
    category: string
  ): string {
    const dashboard = this.dashboards.get(dashboardId);
    if (!dashboard) throw new Error("Дашборд не найден");

    const templateId = this.generateId();
    const template: DashboardTemplate = {
      id: templateId,
      name,
      description,
      category: category as any,
      widgets: dashboard.widgets.map((widget) => ({
        ...widget,
        id: "", // Сброс ID для нового шаблона
      })),
      tags: dashboard.tags || [],
      isBuiltIn: false,
    };

    this.templates.set(templateId, template);
    return templateId;
  }

  /**
   * Получение метрик дашборда
   */
  getDashboardMetrics(dashboardId: string): DashboardMetrics | null {
    return this.metrics.get(dashboardId) || null;
  }

  /**
   * Инициализация метрик для нового дашборда
   */
  private initializeMetrics(dashboardId: string): void {
    const metrics: DashboardMetrics = {
      totalViews: 0,
      uniqueVisitors: 0,
      averageTimeOnDashboard: 0,
      mostUsedWidgets: [],
      filterUsage: [],
      performanceScore: 100,
    };

    this.metrics.set(dashboardId, metrics);
  }

  /**
   * Запись просмотра дашборда
   */
  recordView(dashboardId: string, userId: string, timeSpent: number): void {
    const metrics = this.metrics.get(dashboardId);
    if (!metrics) return;

    metrics.totalViews++;
    metrics.averageTimeOnDashboard =
      (metrics.averageTimeOnDashboard + timeSpent) / 2;

    this.metrics.set(dashboardId, metrics);
  }

  /**
   * Запись использования фильтра
   */
  recordFilterUsage(
    dashboardId: string,
    filterId: string,
    userId: string
  ): void {
    const metrics = this.metrics.get(dashboardId);
    if (!metrics) return;

    const filterUsage = metrics.filterUsage.find(
      (f) => f.filterId === filterId
    );
    if (filterUsage) {
      filterUsage.usageCount++;
    } else {
      metrics.filterUsage.push({
        filterId,
        filterName: "Unknown Filter",
        usageCount: 1,
        uniqueUsers: 1,
      });
    }

    this.metrics.set(dashboardId, metrics);
  }

  /**
   * Экспорт дашборда
   */
  exportDashboard(dashboardId: string): string {
    const dashboard = this.dashboards.get(dashboardId);
    if (!dashboard) throw new Error("Дашборд не найден");

    return JSON.stringify(
      {
        dashboard,
        exportedAt: new Date(),
        version: "1.0",
      },
      null,
      2
    );
  }

  /**
   * Импорт дашборда
   */
  importDashboard(dashboardJson: string, ownerId: string): string {
    try {
      const importData = JSON.parse(dashboardJson);
      const dashboard = importData.dashboard;

      // Генерируем новый ID и обновляем владельца
      const newId = this.generateId();
      dashboard.id = newId;
      dashboard.owner = ownerId;
      dashboard.createdAt = new Date();
      dashboard.updatedAt = new Date();

      // Сброс метрик
      this.initializeMetrics(newId);

      this.dashboards.set(newId, dashboard);
      return newId;
    } catch (error) {
      throw new Error("Неверный формат дашборда");
    }
  }

  /**
   * Дублирование дашборда
   */
  duplicateDashboard(
    dashboardId: string,
    newName: string,
    ownerId: string
  ): string {
    const original = this.dashboards.get(dashboardId);
    if (!original) throw new Error("Дашборд не найден");

    const duplicateId = this.generateId();
    const duplicate: Dashboard = {
      ...original,
      id: duplicateId,
      name: newName,
      owner: ownerId,
      createdAt: new Date(),
      updatedAt: new Date(),
      widgets: original.widgets.map((widget) => ({
        ...widget,
        id: this.generateId(),
      })),
    };

    this.initializeMetrics(duplicateId);
    this.dashboards.set(duplicateId, duplicate);
    return duplicateId;
  }

  /**
   * Удаление дашборда
   */
  deleteDashboard(dashboardId: string): boolean {
    const dashboard = this.dashboards.get(dashboardId);
    if (!dashboard) return false;

    this.dashboards.delete(dashboardId);
    this.metrics.delete(dashboardId);
    return true;
  }

  /**
   * Генерация уникального ID
   */
  private generateId(): string {
    return "id_" + Math.random().toString(36).substr(2, 9) + "_" + Date.now();
  }

  /**
   * Получение статистики использования
   */
  getUsageStatistics(): any {
    const totalDashboards = this.dashboards.size;
    const totalViews = Array.from(this.metrics.values()).reduce(
      (sum, m) => sum + m.totalViews,
      0
    );
    const avgWidgetsPerDashboard =
      Array.from(this.dashboards.values()).reduce(
        (sum, d) => sum + d.widgets.length,
        0
      ) / totalDashboards;

    return {
      totalDashboards,
      totalViews,
      avgWidgetsPerDashboard,
      templatesCount: this.templates.size,
      publicDashboards: Array.from(this.dashboards.values()).filter(
        (d) => d.isPublic
      ).length,
    };
  }

  /**
   * Получение данных дашборда из API
   */
  async getDashboardData(dashboardId: string): Promise<any> {
    try {
      // Определяем тип дашборда по ID или другим признакам
      // В реальном приложении это может быть поле type в Dashboard
      // Здесь используем простую логику на основе ID шаблонов

      const dashboard = this.dashboards.get(dashboardId);
      // Если дашборд создан из шаблона, используем ID шаблона для определения типа
      // Или проверяем имя/теги

      let response;

      // Логика маппинга
      if (
        dashboardId.includes("financial") ||
        (dashboard && dashboard.tags?.includes("финансы"))
      ) {
        response = await apiClient.dashboard.owner();
      } else if (
        dashboardId.includes("operational") ||
        (dashboard && dashboard.tags?.includes("производство"))
      ) {
        response = await apiClient.dashboard.executive();
      } else if (
        dashboardId.includes("sales") ||
        (dashboard && dashboard.tags?.includes("продажи"))
      ) {
        // Используем PM для продаж как пример, или executive
        response = await apiClient.dashboard.pm();
      } else if (
        dashboardId.includes("inventory") ||
        (dashboard && dashboard.tags?.includes("склад"))
      ) {
        response = await apiClient.dashboard.developer();
      } else {
        // По умолчанию пробуем owner
        response = await apiClient.dashboard.owner();
      }

      return response.data;
    } catch (error) {
      console.error("Ошибка получения данных дашборда:", error);
      throw error;
    }
  }
}
