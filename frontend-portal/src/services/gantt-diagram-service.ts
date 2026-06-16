/**
 * Сервис генерации Gantt диаграмм для управления проектами
 * Поддерживает создание диаграмм с задачами, зависимостями, критическим путем
 * и интеграцией с планированием ресурсов для 1C-разработки
 */

export interface ProjectTask {
  id: string;
  name: string;
  description?: string;
  startDate: Date;
  endDate: Date;
  duration: number; // в днях
  progress: number; // 0-100%
  assignee?: string;
  priority: "low" | "medium" | "high" | "critical";
  status: "not_started" | "in_progress" | "completed" | "blocked" | "on_hold";
  dependencies: string[]; // ID зависимых задач
  resources: Resource[];
  milestones: Milestone[];
  isCritical: boolean;
  isMilestone: boolean;
  color?: string;
  notes?: string;
}

export interface Resource {
  id: string;
  name: string;
  type: "person" | "equipment" | "budget";
  availability: number; // 0-100%
  costPerDay?: number;
  skills?: string[];
  assignments: TaskAssignment[];
}

export interface TaskAssignment {
  taskId: string;
  resourceId: string;
  allocation: number; // 0-100%
  startDate: Date;
  endDate: Date;
}

export interface Milestone {
  id: string;
  name: string;
  date: Date;
  description?: string;
  isCompleted: boolean;
}

export interface ProjectDependency {
  fromTaskId: string;
  toTaskId: string;
  type:
    | "finish_to_start"
    | "start_to_start"
    | "finish_to_finish"
    | "start_to_finish";
  lag: number; // задержка в днях
  description?: string;
}

export interface GanttDiagram {
  id: string;
  name: string;
  project: Project;
  timeline: TimelineConfig;
  viewConfig: ViewConfig;
  resources: Resource[];
  dependencies: ProjectDependency[];
  milestones: Milestone[];
  createdAt: Date;
  updatedAt: Date;
  version: string;
  width: number;
  height: number;
  margins: { top: number; right: number; bottom: number; left: number };
  taskHeight: number;
  rowSpacing: number;
  fontSize: number;
  colors: {
    primary: string;
    secondary: string;
    accent: string;
    success: string;
    warning: string;
    danger: string;
    info: string;
    light: string;
    dark: string;
  };
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  startDate: Date;
  endDate: Date;
  budget?: number;
  currency?: string;
  client?: string;
  status: "planning" | "active" | "on_hold" | "completed" | "cancelled";
  tasks: ProjectTask[];
  priority: "low" | "medium" | "high" | "critical";
  tags?: string[];
}

export interface TimelineConfig {
  startDate: Date;
  endDate: Date;
  scale: "hours" | "days" | "weeks" | "months";
  workingHours: number; // часов в рабочем дне
  workingDays: number[]; // дни недели 0-6 (воскресенье = 0)
  holidays: Date[];
  timezone: string;
}

export interface ViewConfig {
  showCriticalPath: boolean;
  showResourceView: boolean;
  showMilestones: boolean;
  showDependencies: boolean;
  colorCoding: "status" | "priority" | "assignee" | "phase";
  groupBy?: "phase" | "assignee" | "status" | "priority";
  hideCompletedTasks: boolean;
  hideFutureTasks: boolean;
}

export interface CriticalPathTask {
  taskId: string;
  earlyStart: Date;
  earlyFinish: Date;
  lateStart: Date;
  lateFinish: Date;
  slack: number; // float days
  duration: number;
  isCritical: boolean;
}

export interface ProjectMetrics {
  totalTasks: number;
  completedTasks: number;
  inProgressTasks: number;
  blockedTasks: number;
  totalDuration: number; // days
  actualProgress: number; // percentage
  estimatedCompletion: Date;
  criticalPathLength: number; // days
  resourceUtilization: ResourceUtilization[];
  riskFactors: RiskFactor[];
}

export interface ResourceUtilization {
  resourceId: string;
  resourceName: string;
  totalAllocation: number; // percentage
  allocatedTasks: number;
  remainingCapacity: number;
  efficiency: number; // percentage
  overload: number; // negative if underloaded
}

export interface RiskFactor {
  taskId?: string;
  type: "schedule" | "resource" | "budget" | "quality" | "scope";
  probability: number; // 0-100%
  impact: number; // 0-100%
  severity: "low" | "medium" | "high" | "critical";
  description: string;
  mitigation?: string;
}

export interface GanttChartConfig {
  width: number;
  height: number;
  margins: {
    top: number;
    right: number;
    bottom: number;
    left: number;
  };
  taskHeight: number;
  rowSpacing: number;
  fontSize: number;
  colors: {
    primary: string;
    secondary: string;
    accent: string;
    success: string;
    warning: string;
    danger: string;
    info: string;
    light: string;
    dark: string;
  };
}

export type ExportFormat = "png" | "svg" | "pdf" | "excel" | "json" | "xml";

export interface ExportOptions {
  format: ExportFormat;
  includeDependencies: boolean;
  includeResources: boolean;
  includeMilestones: boolean;
  quality?: number; // для PNG, PDF
  scale?: number; // для экспорта в SVG
}

export class GanttDiagramService {
  private readonly config: GanttChartConfig = {
    width: 1200,
    height: 800,
    margins: { top: 60, right: 40, bottom: 40, left: 200 },
    taskHeight: 24,
    rowSpacing: 4,
    fontSize: 12,
    colors: {
      primary: "#3b82f6",
      secondary: "#6b7280",
      accent: "#8b5cf6",
      success: "#10b981",
      warning: "#f59e0b",
      danger: "#ef4444",
      info: "#06b6d4",
      light: "#f3f4f6",
      dark: "#1f2937",
    },
  };

  constructor() {
    // Инициализация сервиса
  }

  /**
   * Создает новый проект с базовой структурой
   */
  createProject(name: string, description?: string): Project {
    const now = new Date();
    return {
      id: this.generateId(),
      name,
      description,
      startDate: now,
      endDate: new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000), // +30 дней
      status: "planning",
      priority: "medium",
      tasks: [],
    };
  }

  /**
   * Добавляет задачу в проект
   */
  addTask(project: Project, taskData: Partial<ProjectTask>): ProjectTask {
    const task: ProjectTask = {
      id: this.generateId(),
      name: taskData.name || "Новая задача",
      description: taskData.description,
      startDate: taskData.startDate || new Date(),
      endDate:
        taskData.endDate || new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
      duration: taskData.duration || 7,
      progress: taskData.progress || 0,
      assignee: taskData.assignee,
      priority: taskData.priority || "medium",
      status: taskData.status || "not_started",
      dependencies: taskData.dependencies || [],
      resources: taskData.resources || [],
      milestones: taskData.milestones || [],
      isCritical: false,
      isMilestone: taskData.isMilestone || false,
      color: taskData.color,
      notes: taskData.notes,
    };

    project.tasks.push(task);
    return task;
  }

  /**
   * Создает зависимость между задачами
   */
  addDependency(
    dependencies: ProjectDependency[],
    fromTaskId: string,
    toTaskId: string,
    type: ProjectDependency["type"] = "finish_to_start",
    lag: number = 0,
    description?: string
  ): ProjectDependency {
    const dependency: ProjectDependency = {
      fromTaskId,
      toTaskId,
      type,
      lag,
      description,
    };

    dependencies.push(dependency);
    return dependency;
  }

  /**
   * Вычисляет критический путь проекта
   */
  calculateCriticalPath(
    project: Project,
    dependencies: ProjectDependency[]
  ): CriticalPathTask[] {
    const tasks = project.tasks;
    const taskMap = new Map(tasks.map((task) => [task.id, task]));

    // Топологическая сортировка
    const sortedTasks = this.topologicalSort(tasks, dependencies);

    // Прямой проход - вычисление раннего начала и окончания
    const criticalPathTasks: CriticalPathTask[] = [];

    for (const taskId of sortedTasks) {
      const task = taskMap.get(taskId)!;
      const dependenciesIds = dependencies.filter((d) => d.toTaskId === taskId);

      let earlyStart = task.startDate;

      // Учитываем зависимости
      for (const dep of dependenciesIds) {
        const fromTask = taskMap.get(dep.fromTaskId)!;
        let dependencyEnd = fromTask.endDate;

        if (dep.lag > 0) {
          dependencyEnd = new Date(
            dependencyEnd.getTime() + dep.lag * 24 * 60 * 60 * 1000
          );
        }

        if (dependencyEnd > earlyStart) {
          earlyStart = dependencyEnd;
        }
      }

      const earlyFinish = new Date(
        earlyStart.getTime() + task.duration * 24 * 60 * 60 * 1000
      );

      criticalPathTasks.push({
        taskId,
        earlyStart,
        earlyFinish,
        lateStart: earlyStart, // будет обновлено в обратном проходе
        lateFinish: earlyFinish, // будет обновлено в обратном проходе
        slack: 0,
        duration: task.duration,
        isCritical: false,
      });
    }

    // Обратный проход - вычисление позднего начала и окончания
    const projectEnd = Math.max(
      ...criticalPathTasks.map((t) => t.earlyFinish.getTime())
    );

    for (let i = criticalPathTasks.length - 1; i >= 0; i--) {
      const currentTask = criticalPathTasks[i];
      const dependents = dependencies.filter(
        (d) => d.fromTaskId === currentTask.taskId
      );

      if (dependents.length === 0) {
        // Последняя задача в проекте
        currentTask.lateFinish = new Date(projectEnd);
        currentTask.lateStart = new Date(
          projectEnd - currentTask.duration * 24 * 60 * 60 * 1000
        );
      } else {
        // Учитываем зависимые задачи
        let latestDependencyStart = new Date(0);

        for (const dep of dependents) {
          const dependentTask = criticalPathTasks.find(
            (t) => t.taskId === dep.toTaskId
          )!;
          let dependentStart = dependentTask.lateStart;

          if (dep.lag > 0) {
            dependentStart = new Date(
              dependentStart.getTime() - dep.lag * 24 * 60 * 60 * 1000
            );
          }

          if (dependentStart > latestDependencyStart) {
            latestDependencyStart = dependentStart;
          }
        }

        currentTask.lateFinish = latestDependencyStart;
        currentTask.lateStart = new Date(
          latestDependencyStart.getTime() -
            currentTask.duration * 24 * 60 * 60 * 1000
        );
      }

      // Вычисляем slack (временной буфер)
      const slackMs =
        currentTask.lateStart.getTime() - currentTask.earlyStart.getTime();
      currentTask.slack = slackMs / (24 * 60 * 60 * 1000);
      currentTask.isCritical = currentTask.slack === 0;
    }

    return criticalPathTasks;
  }

  /**
   * Топологическая сортировка задач на основе зависимостей
   */
  private topologicalSort(
    tasks: ProjectTask[],
    dependencies: ProjectDependency[]
  ): string[] {
    const inDegree = new Map<string, number>();
    const adjList = new Map<string, string[]>();

    // Инициализация
    tasks.forEach((task) => {
      inDegree.set(task.id, 0);
      adjList.set(task.id, []);
    });

    // Подсчет входящих связей
    dependencies.forEach((dep) => {
      if (inDegree.has(dep.toTaskId)) {
        inDegree.set(dep.toTaskId, (inDegree.get(dep.toTaskId) || 0) + 1);
        adjList.get(dep.fromTaskId)?.push(dep.toTaskId);
      }
    });

    // Очередь задач с нулевой степенью
    const queue: string[] = [];
    inDegree.forEach((degree, taskId) => {
      if (degree === 0) {
        queue.push(taskId);
      }
    });

    const result: string[] = [];

    while (queue.length > 0) {
      const current = queue.shift()!;
      result.push(current);

      const neighbors = adjList.get(current) || [];
      neighbors.forEach((neighbor) => {
        inDegree.set(neighbor, (inDegree.get(neighbor) || 0) - 1);
        if ((inDegree.get(neighbor) || 0) === 0) {
          queue.push(neighbor);
        }
      });
    }

    return result;
  }

  /**
   * Генерирует Gantt диаграмму в различных форматах
   */
  generateDiagram(
    project: Project,
    dependencies: ProjectDependency[],
    config: Partial<GanttChartConfig> = {}
  ): GanttDiagram {
    const viewConfig: ViewConfig = {
      showCriticalPath: true,
      showResourceView: true,
      showMilestones: true,
      showDependencies: true,
      colorCoding: "status",
      hideCompletedTasks: false,
      hideFutureTasks: false,
    };

    const timeline: TimelineConfig = {
      startDate: project.startDate,
      endDate: project.endDate,
      scale: "days",
      workingHours: 8,
      workingDays: [1, 2, 3, 4, 5], // ПН-ПТ
      holidays: [],
      timezone: "UTC",
    };

    const mergedConfig = { ...this.config, ...config };

    // Вычисляем критический путь
    const criticalPath = this.calculateCriticalPath(project, dependencies);
    const criticalTaskIds = criticalPath
      .filter((t) => t.isCritical)
      .map((t) => t.taskId);

    // Обновляем задачи с информацией о критическом пути
    project.tasks.forEach((task) => {
      task.isCritical = criticalTaskIds.includes(task.id);
    });

    return {
      id: this.generateId(),
      name: project.name,
      project,
      timeline,
      viewConfig,
      resources: [],
      dependencies,
      milestones: [],
      createdAt: new Date(),
      updatedAt: new Date(),
      version: "1.0.0",
      width: this.config.width,
      height: this.config.height,
      margins: this.config.margins,
      taskHeight: this.config.taskHeight,
      rowSpacing: this.config.rowSpacing,
      fontSize: this.config.fontSize,
      colors: this.config.colors,
    };
  }

  /**
   * Генерирует SVG представление диаграммы
   */
  generateSVG(diagram: GanttDiagram): string {
    const { width, height, margins, taskHeight, rowSpacing, colors } = diagram;
    const chartWidth = width - margins.left - margins.right;
    const chartHeight = height - margins.top - margins.bottom;

    let svg = `
      <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <style>
            .task-bar { stroke: #333; stroke-width: 1; }
            .critical-path { stroke: #ef4444; stroke-width: 2; }
            .milestone { fill: #f59e0b; }
            .dependency-line { stroke: #6b7280; stroke-width: 1; fill: none; }
            .grid-line { stroke: #e5e7eb; stroke-width: 0.5; }
            .text { font-family: Arial, sans-serif; font-size: ${
              diagram.fontSize
            }px; }
            .task-text { fill: white; }
            .date-text { fill: #374151; }
          </style>
        </defs>
        
        <!-- Заголовок -->
        <text x="${
          width / 2
        }" y="30" text-anchor="middle" class="text" font-size="18" font-weight="bold">
          ${diagram.project.name}
        </text>
        
        <!-- Сетка времени -->
        ${this.generateTimeGrid(diagram, chartWidth, chartHeight)}
        
        <!-- Задачи -->
        ${this.generateTaskBars(diagram, chartWidth, chartHeight)}
        
        <!-- Зависимости -->
        ${this.generateDependencyLines(diagram, chartWidth, chartHeight)}
        
        <!-- Milestones -->
        ${this.generateMilestones(diagram, chartWidth, chartHeight)}
        
      </svg>
    `;

    return svg;
  }

  /**
   * Генерирует сетку времени
   */
  private generateTimeGrid(
    diagram: GanttDiagram,
    chartWidth: number,
    chartHeight: number
  ): string {
    const { margins, timeline, colors } = diagram;
    const startTime = timeline.startDate.getTime();
    const endTime = timeline.endDate.getTime();
    const totalDuration = endTime - startTime;

    let grid = "";
    const days = Math.ceil(totalDuration / (24 * 60 * 60 * 1000));

    for (let i = 0; i <= days; i++) {
      const x = margins.left + (i / days) * chartWidth;

      // Вертикальные линии сетки
      grid += `<line x1="${x}" y1="${margins.top}" x2="${x}" y2="${
        margins.top + chartHeight
      }" class="grid-line" />`;

      // Даты
      const date = new Date(startTime + i * 24 * 60 * 60 * 1000);
      grid += `<text x="${x}" y="${
        margins.top - 10
      }" text-anchor="middle" class="text date-text">
        ${this.formatDate(date)}
      </text>`;
    }

    return grid;
  }

  /**
   * Генерирует полосы задач
   */
  private generateTaskBars(
    diagram: GanttDiagram,
    chartWidth: number,
    chartHeight: number
  ): string {
    const { margins, timeline, project, colors } = diagram;
    const startTime = timeline.startDate.getTime();
    const totalDuration = timeline.endDate.getTime() - startTime;

    let taskBars = "";

    project.tasks.forEach((task, index) => {
      const taskStartTime = task.startDate.getTime();
      const taskEndTime = task.endDate.getTime();

      const x =
        margins.left +
        ((taskStartTime - startTime) / totalDuration) * chartWidth;
      const width =
        ((taskEndTime - taskStartTime) / totalDuration) * chartWidth;
      const y = margins.top + index * (diagram.taskHeight + diagram.rowSpacing);

      const color = this.getTaskColor(task, diagram.viewConfig.colorCoding);

      // Полоса задачи
      taskBars += `
        <rect x="${x}" y="${y}" width="${width}" height="${diagram.taskHeight}" 
              fill="${color}" class="task-bar ${
        task.isCritical ? "critical-path" : ""
      }" />
      `;

      // Название задачи
      taskBars += `<text x="${x + 4}" y="${
        y + diagram.taskHeight / 2 + 4
      }" class="text task-text">${task.name}</text>`;

      // Прогресс (если есть)
      if (task.progress > 0) {
        const progressWidth = (task.progress / 100) * width;
        taskBars += `
          <rect x="${x}" y="${y}" width="${progressWidth}" height="${diagram.taskHeight}" 
                fill="${colors.dark}22" />
        `;
      }
    });

    return taskBars;
  }

  /**
   * Генерирует линии зависимостей
   */
  private generateDependencyLines(
    diagram: GanttDiagram,
    chartWidth: number,
    chartHeight: number
  ): string {
    const { margins, timeline, dependencies } = diagram;
    const startTime = timeline.startDate.getTime();
    const totalDuration = timeline.endDate.getTime() - startTime;

    let dependencyLines = "";

    dependencies.forEach((dep) => {
      const fromTask = diagram.project.tasks.find(
        (t) => t.id === dep.fromTaskId
      );
      const toTask = diagram.project.tasks.find((t) => t.id === dep.toTaskId);

      if (!fromTask || !toTask) return;

      const fromX =
        margins.left +
        ((fromTask.endDate.getTime() - startTime) / totalDuration) * chartWidth;
      const fromY =
        margins.top +
        diagram.project.tasks.indexOf(fromTask) *
          (diagram.taskHeight + diagram.rowSpacing) +
        diagram.taskHeight / 2;

      const toX =
        margins.left +
        ((toTask.startDate.getTime() - startTime) / totalDuration) * chartWidth;
      const toY =
        margins.top +
        diagram.project.tasks.indexOf(toTask) *
          (diagram.taskHeight + diagram.rowSpacing) +
        diagram.taskHeight / 2;

      // Рисуем линию зависимости
      dependencyLines += `<line x1="${fromX}" y1="${fromY}" x2="${toX}" y2="${toY}" class="dependency-line" />`;

      // Стрелка в конце
      const arrowX = toX;
      const arrowY = toY;
      dependencyLines += `<polygon points="${arrowX - 6},${
        arrowY - 3
      } ${arrowX},${arrowY} ${arrowX - 6},${arrowY + 3}" fill="#6b7280" />`;
    });

    return dependencyLines;
  }

  /**
   * Генерирует milestone'ы
   */
  private generateMilestones(
    diagram: GanttDiagram,
    chartWidth: number,
    chartHeight: number
  ): string {
    const { margins, timeline, milestones } = diagram;
    const startTime = timeline.startDate.getTime();
    const totalDuration = timeline.endDate.getTime() - startTime;

    let milestoneElements = "";

    milestones.forEach((milestone, index) => {
      const x =
        margins.left +
        ((milestone.date.getTime() - startTime) / totalDuration) * chartWidth;
      const y =
        margins.top +
        diagram.project.tasks.length *
          (diagram.taskHeight + diagram.rowSpacing) +
        index * 20;

      // Diamond shape для milestone
      milestoneElements += `
        <polygon points="${x},${y} ${x + 6},${y + 8} ${x},${y + 16} ${x - 6},${
        y + 8
      }" 
                 class="milestone ${milestone.isCompleted ? "success" : ""}" />
        <text x="${x}" y="${y + 20}" text-anchor="middle" class="text">${
        milestone.name
      }</text>
      `;
    });

    return milestoneElements;
  }

  /**
   * Вычисляет метрики проекта
   */
  calculateMetrics(
    project: Project,
    dependencies: ProjectDependency[]
  ): ProjectMetrics {
    const criticalPath = this.calculateCriticalPath(project, dependencies);
    const criticalTaskIds = criticalPath
      .filter((t) => t.isCritical)
      .map((t) => t.taskId);

    const totalTasks = project.tasks.length;
    const completedTasks = project.tasks.filter(
      (t) => t.status === "completed"
    ).length;
    const inProgressTasks = project.tasks.filter(
      (t) => t.status === "in_progress"
    ).length;
    const blockedTasks = project.tasks.filter(
      (t) => t.status === "blocked"
    ).length;

    const totalDuration = project.tasks.reduce(
      (sum, task) => sum + task.duration,
      0
    );
    const actualProgress =
      totalTasks > 0 ? (completedTasks / totalTasks) * 100 : 0;

    // Оценка завершения проекта
    const remainingTasks = totalTasks - completedTasks;
    const avgTaskDuration = totalDuration / totalTasks;
    const estimatedCompletion = new Date(
      Date.now() + remainingTasks * avgTaskDuration * 24 * 60 * 60 * 1000
    );

    const criticalPathLength = criticalPath.reduce(
      (sum, t) => sum + t.duration,
      0
    );

    const resourceUtilization: ResourceUtilization[] = [];
    const riskFactors: RiskFactor[] = this.identifyRiskFactors(
      project,
      dependencies
    );

    return {
      totalTasks,
      completedTasks,
      inProgressTasks,
      blockedTasks,
      totalDuration,
      actualProgress,
      estimatedCompletion,
      criticalPathLength,
      resourceUtilization,
      riskFactors,
    };
  }

  /**
   * Идентифицирует факторы риска в проекте
   */
  private identifyRiskFactors(
    project: Project,
    dependencies: ProjectDependency[]
  ): RiskFactor[] {
    const risks: RiskFactor[] = [];

    // Риск связанный с задачами с высоким приоритетом, но долгим сроком
    project.tasks
      .filter((t) => t.priority === "critical" && t.duration > 14)
      .forEach((task) => {
        risks.push({
          taskId: task.id,
          type: "schedule",
          probability: 70,
          impact: 80,
          severity: "high",
          description: `Критическая задача "${task.name}" имеет длительный срок выполнения (${task.duration} дней)`,
          mitigation:
            "Рассмотреть разбивку задачи на более мелкие подзадачи или увеличение ресурсов",
        });
      });

    // Риск связанный с циклическими зависимостями
    if (this.hasCircularDependency(project.tasks, dependencies)) {
      risks.push({
        type: "schedule",
        probability: 90,
        impact: 95,
        severity: "critical",
        description: "Обнаружены циклические зависимости в задачах проекта",
        mitigation:
          "Пересмотреть структуру зависимостей и удалить циклические связи",
      });
    }

    // Риск связанный с блокированными задачами
    project.tasks
      .filter((t) => t.status === "blocked")
      .forEach((task) => {
        risks.push({
          taskId: task.id,
          type: "schedule",
          probability: 85,
          impact: 60,
          severity: "medium",
          description: `Задача "${task.name}" заблокирована и не может быть выполнена`,
          mitigation: "Выявить причину блокировки и найти способ её устранения",
        });
      });

    return risks;
  }

  /**
   * Проверяет наличие циклических зависимостей
   */
  private hasCircularDependency(
    tasks: ProjectTask[],
    dependencies: ProjectDependency[]
  ): boolean {
    const taskIds = tasks.map((t) => t.id);
    const visited = new Set<string>();
    const recursionStack = new Set<string>();

    const graph = new Map<string, string[]>();
    dependencies.forEach((dep) => {
      if (!graph.has(dep.fromTaskId)) {
        graph.set(dep.fromTaskId, []);
      }
      graph.get(dep.fromTaskId)!.push(dep.toTaskId);
    });

    const dfs = (nodeId: string): boolean => {
      visited.add(nodeId);
      recursionStack.add(nodeId);

      const neighbors = graph.get(nodeId) || [];
      for (const neighbor of neighbors) {
        if (!visited.has(neighbor)) {
          if (dfs(neighbor)) return true;
        } else if (recursionStack.has(neighbor)) {
          return true; // Найден цикл
        }
      }

      recursionStack.delete(nodeId);
      return false;
    };

    for (const taskId of taskIds) {
      if (!visited.has(taskId)) {
        if (dfs(taskId)) return true;
      }
    }

    return false;
  }

  /**
   * Возвращает цвет задачи в зависимости от статуса/приоритета
   */
  private getTaskColor(
    task: ProjectTask,
    colorCoding: ViewConfig["colorCoding"]
  ): string {
    switch (colorCoding) {
      case "status":
        switch (task.status) {
          case "completed":
            return "#10b981"; // success
          case "in_progress":
            return "#3b82f6"; // primary
          case "blocked":
            return "#ef4444"; // danger
          case "on_hold":
            return "#f59e0b"; // warning
          default:
            return "#6b7280"; // secondary
        }
      case "priority":
        switch (task.priority) {
          case "critical":
            return "#ef4444"; // danger
          case "high":
            return "#f59e0b"; // warning
          case "medium":
            return "#3b82f6"; // primary
          case "low":
            return "#6b7280"; // secondary
          default:
            return "#6b7280";
        }
      case "phase":
        // Цвет в зависимости от фазы проекта
        return task.color || "#6b7280";
      default:
        return task.color || "#6b7280";
    }
  }

  /**
   * Форматирует дату для отображения
   */
  private formatDate(date: Date): string {
    return date.toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
    });
  }

  /**
   * Экспортирует диаграмму в различные форматы
   */
  async exportDiagram(
    diagram: GanttDiagram,
    options: ExportOptions
  ): Promise<string> {
    switch (options.format) {
      case "svg":
        return this.generateSVG(diagram);
      case "png":
        return this.exportToPNG(diagram, options);
      case "pdf":
        return this.exportToPDF(diagram, options);
      case "excel":
        return this.exportToExcel(diagram);
      case "json":
        return JSON.stringify(diagram, null, 2);
      case "xml":
        return this.exportToXML(diagram);
      default:
        throw new Error(`Неподдерживаемый формат экспорта: ${options.format}`);
    }
  }

  /**
   * Экспорт в PNG
   */
  private async exportToPNG(
    diagram: GanttDiagram,
    options: ExportOptions
  ): Promise<string> {
    // В реальном приложении здесь был бы SVG to Canvas to PNG conversion
    const svg = this.generateSVG(diagram);
    return `data:image/png;base64,${btoa(svg)}`; // Заглушка
  }

  /**
   * Экспорт в PDF
   */
  private async exportToPDF(
    diagram: GanttDiagram,
    options: ExportOptions
  ): Promise<string> {
    // В реальном приложении здесь был бы генератор PDF
    return "PDF_DATA_PLACEHOLDER";
  }

  /**
   * Экспорт в Excel
   */
  private exportToExcel(diagram: GanttDiagram): string {
    const tasks = diagram.project.tasks.map((task) => ({
      Название: task.name,
      "Дата начала": this.formatDate(task.startDate),
      "Дата окончания": this.formatDate(task.endDate),
      Длительность: task.duration,
      "Прогресс (%)": task.progress,
      Статус: task.status,
      Приоритет: task.priority,
      Критическая: task.isCritical ? "Да" : "Нет",
    }));

    return JSON.stringify(tasks, null, 2);
  }

  /**
   * Экспорт в XML
   */
  private exportToXML(diagram: GanttDiagram): string {
    let xml = `<?xml version="1.0" encoding="UTF-8"?>\n`;
    xml += `<GanttDiagram version="1.0">\n`;
    xml += `  <Project name="${diagram.project.name}">\n`;

    diagram.project.tasks.forEach((task) => {
      xml += `    <Task id="${task.id}" name="${task.name}">\n`;
      xml += `      <StartDate>${this.formatDate(
        task.startDate
      )}</StartDate>\n`;
      xml += `      <EndDate>${this.formatDate(task.endDate)}</EndDate>\n`;
      xml += `      <Duration>${task.duration}</Duration>\n`;
      xml += `      <Progress>${task.progress}</Progress>\n`;
      xml += `      <Status>${task.status}</Status>\n`;
      xml += `      <Priority>${task.priority}</Priority>\n`;
      xml += `      <Critical>${task.isCritical}</Critical>\n`;
      xml += `    </Task>\n`;
    });

    xml += `  </Project>\n`;
    xml += `</GanttDiagram>`;

    return xml;
  }

  /**
   * Генерирует уникальный ID
   */
  private generateId(): string {
    return `gantt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Валидация данных проекта
   */
  validateProject(
    project: Project,
    dependencies: ProjectDependency[]
  ): { isValid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Проверка задач
    if (project.tasks.length === 0) {
      errors.push("Проект должен содержать хотя бы одну задачу");
    }

    // Проверка временных рамок
    if (project.startDate >= project.endDate) {
      errors.push("Дата начала проекта должна быть раньше даты окончания");
    }

    // Проверка дат задач
    project.tasks.forEach((task, index) => {
      if (task.startDate >= task.endDate) {
        errors.push(
          `Задача "${task.name}" (индекс ${index}): дата начала должна быть раньше даты окончания`
        );
      }

      if (
        task.startDate < project.startDate ||
        task.endDate > project.endDate
      ) {
        errors.push(
          `Задача "${task.name}" (индекс ${index}): выходит за рамки проекта`
        );
      }
    });

    // Проверка зависимостей
    dependencies.forEach((dep) => {
      const fromTask = project.tasks.find((t) => t.id === dep.fromTaskId);
      const toTask = project.tasks.find((t) => t.id === dep.toTaskId);

      if (!fromTask) {
        errors.push(`Зависимость: задача с ID "${dep.fromTaskId}" не найдена`);
      }

      if (!toTask) {
        errors.push(`Зависимость: задача с ID "${dep.toTaskId}" не найдена`);
      }

      if (fromTask && toTask && fromTask.endDate >= toTask.startDate) {
        errors.push(
          `Зависимость: "${fromTask.name}" должна заканчиваться раньше, чем начинается "${toTask.name}"`
        );
      }
    });

    // Проверка циклических зависимостей
    if (this.hasCircularDependency(project.tasks, dependencies)) {
      errors.push("Обнаружены циклические зависимости между задачами");
    }

    return {
      isValid: errors.length === 0,
      errors,
    };
  }

  /**
   * Оптимизирует загрузку ресурсов в проекте
   */
  optimizeResourceAllocation(
    project: Project,
    dependencies: ProjectDependency[]
  ): {
    optimizedProject: Project;
    recommendations: string[];
  } {
    const recommendations: string[] = [];
    const taskMetrics = this.calculateCriticalPath(project, dependencies);

    // Анализ перегруженных задач
    const overloadedTasks = project.tasks.filter(
      (task) => task.progress < 50 && task.endDate < new Date()
    );

    if (overloadedTasks.length > 0) {
      recommendations.push(
        `Обнаружено ${overloadedTasks.length} задач с задержкой. Рекомендуется пересмотреть приоритеты.`
      );
    }

    // Анализ критического пути
    const criticalTasks = taskMetrics.filter((t) => t.isCritical);
    if (criticalTasks.length > project.tasks.length * 0.5) {
      recommendations.push(
        "Более 50% задач на критическом пути. Это может указывать на плохое планирование."
      );
    }

    // Предложения по оптимизации
    const shortTasks = project.tasks.filter((task) => task.duration < 2);
    if (shortTasks.length > 0) {
      recommendations.push(
        `Найдено ${shortTasks.length} коротких задач (<2 дней). Рассмотрите их объединение.`
      );
    }

    return {
      optimizedProject: project,
      recommendations,
    };
  }

  /**
   * Создает отчет о состоянии проекта
   */
  generateProjectReport(
    project: Project,
    dependencies: ProjectDependency[]
  ): string {
    const metrics = this.calculateMetrics(project, dependencies);
    const validation = this.validateProject(project, dependencies);
    const optimization = this.optimizeResourceAllocation(project, dependencies);

    let report = `# Отчет о проекте: ${project.name}\n\n`;

    report += `## Основная информация\n`;
    report += `- **Период**: ${this.formatDate(
      project.startDate
    )} - ${this.formatDate(project.endDate)}\n`;
    report += `- **Статус**: ${project.status}\n`;
    report += `- **Приоритет**: ${project.priority}\n`;
    report += `- **Описание**: ${project.description || "Не указано"}\n\n`;

    report += `## Статистика задач\n`;
    report += `- **Всего задач**: ${metrics.totalTasks}\n`;
    report += `- **Выполнено**: ${metrics.completedTasks}\n`;
    report += `- **В процессе**: ${metrics.inProgressTasks}\n`;
    report += `- **Заблокировано**: ${metrics.blockedTasks}\n`;
    report += `- **Общий прогресс**: ${metrics.actualProgress.toFixed(1)}%\n`;
    report += `- **Предполагаемое завершение**: ${this.formatDate(
      metrics.estimatedCompletion
    )}\n\n`;

    report += `## Анализ критического пути\n`;
    report += `- **Длина критического пути**: ${metrics.criticalPathLength} дней\n`;
    report += `- **Критических задач**: ${
      metrics.riskFactors.filter((r) => r.taskId).length
    }\n\n`;

    report += `## Факторы риска\n`;
    if (metrics.riskFactors.length === 0) {
      report += `- Факторов риска не обнаружено\n`;
    } else {
      metrics.riskFactors.forEach((risk, index) => {
        report += `${index + 1}. **${risk.severity.toUpperCase()}** (${
          risk.probability
        }% вероятность, ${risk.impact}% влияние): ${risk.description}\n`;
        if (risk.mitigation) {
          report += `   *Решение*: ${risk.mitigation}\n`;
        }
      });
    }

    report += `\n## Рекомендации по оптимизации\n`;
    optimization.recommendations.forEach((rec, index) => {
      report += `${index + 1}. ${rec}\n`;
    });

    report += `\n## Валидация проекта\n`;
    if (validation.isValid) {
      report += `- ✅ Проект прошел валидацию\n`;
    } else {
      report += `- ❌ Обнаружены проблемы:\n`;
      validation.errors.forEach((error) => {
        report += `  - ${error}\n`;
      });
    }

    report += `\n---\n`;
    report += `*Отчет сгенерирован: ${new Date().toLocaleString("ru-RU")}*\n`;

    return report;
  }
}
