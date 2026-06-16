/**
 * Executive Dashboard
 * For CEO, CTO, Business Owner
 */

import { api } from "@/lib/api-client";
import type { ExecutiveDashboard as ExecutiveDashboardType } from "@/lib/types";
import Card from "@/shared/components/Card/Card";
import MetricCard from "@/shared/components/MetricCard/MetricCard";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Activity, DollarSign, TrendingUp, Users } from "lucide-react";
import React from "react";

export const ExecutiveDashboard: React.FC = () => {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "executive"],
    queryFn: () =>
      api.dashboard.executive().then((r) => r.data as ExecutiveDashboardType),
    refetchInterval: 60000, // Refresh every minute
  });

  if (isLoading || !data) {
    return <DashboardSkeleton />;
  }

  const { health, roi, users, growth, revenue_trend, alerts, objectives } =
    data;

  // Health status color
  const healthColors = {
    healthy: "text-success-500",
    warning: "text-warning-500",
    critical: "text-error-500",
  };

  const healthIcons = {
    healthy: "🟢",
    warning: "🟡",
    critical: "🔴",
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            Executive Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            High-level overview of project health and business impact
          </p>
        </div>

        <button className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
          Export Report
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Health */}
        <MetricCard
          title="Project Health"
          value={healthIcons[health.status]}
          subtitle={health.message}
          status={
            health.status === "good"
              ? "good"
              : health.status === "warning"
              ? "warning"
              : "critical"
          }
          icon={<Activity />}
        />

        {/* ROI */}
        <MetricCard
          title="Monthly ROI"
          value={roi.value as number}
          change={roi.change}
          trend={roi.trend}
          status={roi.status}
          format="currency"
          icon={<DollarSign />}
        />

        {/* Users */}
        <MetricCard
          title="Active Users"
          value={users.value as number}
          change={users.change}
          trend={users.trend}
          subtitle={`+${Math.abs(users.change || 0)} this month`}
          icon={<Users />}
        />

        {/* Growth */}
        <MetricCard
          title="MoM Growth"
          value={growth.value}
          change={growth.change}
          trend={growth.trend}
          status={growth.status}
          format="percentage"
          icon={<TrendingUp />}
        />
      </div>

      {/* Charts & Alerts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Revenue Trend */}
        <Card className="lg:col-span-2">
          <Card.Header>
            <h3 className="text-lg font-semibold">Revenue Trend</h3>
          </Card.Header>
          <Card.Body>
            {/* TODO: Add Recharts component */}
            <div className="h-64 flex items-center justify-center text-gray-400">
              Revenue chart (Recharts)
            </div>
          </Card.Body>
        </Card>

        {/* Alerts */}
        <Card>
          <Card.Header>
            <h3 className="text-lg font-semibold">Alerts</h3>
            <span className="text-sm text-gray-500">({alerts.length})</span>
          </Card.Header>
          <Card.Body>
            <div className="space-y-3">
              {alerts.length === 0 ? (
                <p className="text-gray-500 text-sm">No alerts</p>
              ) : (
                alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className={clsx(
                      "p-3 rounded-lg border-l-4",
                      alert.type === "warning" &&
                        "bg-warning-50 border-warning-500",
                      alert.type === "error" && "bg-error-50 border-error-500",
                      alert.type === "success" &&
                        "bg-success-50 border-success-500",
                      alert.type === "info" && "bg-blue-50 border-blue-500"
                    )}
                  >
                    <p className="text-sm font-medium">{alert.title}</p>
                    <p className="text-xs text-gray-600 mt-1">
                      {alert.message}
                    </p>
                  </div>
                ))
              )}
            </div>
          </Card.Body>
        </Card>
      </div>

      {/* Objectives */}
      <Card>
        <Card.Header>
          <h3 className="text-lg font-semibold">Key Objectives</h3>
        </Card.Header>
        <Card.Body>
          <div className="space-y-4">
            {objectives.map((objective) => (
              <div key={objective.id}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">{objective.title}</span>
                  <span
                    className={clsx(
                      "text-xs px-2 py-1 rounded-full",
                      objective.status === "on_track" &&
                        "bg-success-100 text-success-700",
                      objective.status === "behind" &&
                        "bg-warning-100 text-warning-700",
                      objective.status === "at_risk" &&
                        "bg-error-100 text-error-700"
                    )}
                  >
                    {objective.status.replace("_", " ")}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={clsx(
                      "h-2 rounded-full transition-all",
                      objective.status === "on_track" && "bg-success-500",
                      objective.status === "behind" && "bg-warning-500",
                      objective.status === "at_risk" && "bg-error-500"
                    )}
                    style={{ width: `${objective.progress}%` }}
                  />
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  {objective.progress}% complete
                </p>
              </div>
            ))}
          </div>
        </Card.Body>
      </Card>
    </div>
  );
};

const DashboardSkeleton: React.FC = () => {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      <div className="h-8 bg-gray-200 rounded w-64" />
      <div className="grid grid-cols-4 gap-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-40 bg-gray-200 rounded-xl" />
        ))}
      </div>
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 h-80 bg-gray-200 rounded-xl" />
        <div className="h-80 bg-gray-200 rounded-xl" />
      </div>
    </div>
  );
};

export default ExecutiveDashboard;
