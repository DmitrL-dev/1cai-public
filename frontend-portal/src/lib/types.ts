export interface DashboardMetric {
  value: number;
  change: number;
  trend: "up" | "down" | "stable";
  status: "good" | "warning" | "critical";
  message?: string;
}

export interface DeveloperDashboard {
  id: string;
  name: string;
  assigned_tasks: any[];
  code_reviews: any[];
  build_status: any;
  code_quality: any;
}

export interface ExecutiveDashboard {
  id: string;
  health: {
    status: "good" | "warning" | "critical";
    message: string;
  };
  roi: DashboardMetric;
  users: DashboardMetric;
  growth: DashboardMetric;
  revenue_trend: any[];
  alerts: any[];
  objectives: any[];
  metrics: any;
}

export interface SprintProgress {
  sprint_number: number;
  tasks_done: number;
  tasks_total: number;
  progress: number;
  blockers: number;
  end_date: string;
}

export interface PMDashboard {
  id: string;
  projects: any[];
  projects_summary: any;
  timeline: any[];
  team_workload: any[];
  sprint_progress: SprintProgress;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
}
