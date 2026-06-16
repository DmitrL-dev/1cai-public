/**
 * PM Dashboard
 * For Project Manager / Product Owner
 */

import { api } from "@/lib/api-client";
import type { PMDashboard as PMDashboardType } from "@/lib/types";
import Card from "@/shared/components/Card/Card";
import MetricCard from "@/shared/components/MetricCard/MetricCard";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Clock, Pause } from "lucide-react";
import React from "react";

export const PMDashboard: React.FC = () => {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "pm"],
    queryFn: () => api.dashboard.pm().then((r) => r.data as PMDashboardType),
  });

  if (isLoading || !data) {
    return <div>Loading...</div>;
  }

  const { projects_summary, timeline, team_workload, sprint_progress } = data;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Projects Overview</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Manage all your projects and track team progress
        </p>
      </div>

      {/* Project Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Active Projects"
          value={projects_summary.active}
          icon={<Clock />}
          status="good"
        />

        <MetricCard
          title="Completed"
          value={projects_summary.completed}
          icon={<CheckCircle2 />}
          status="good"
        />

        <MetricCard
          title="Paused"
          value={projects_summary.paused}
          icon={<Pause />}
          status="warning"
        />

        <MetricCard
          title="At Risk"
          value={projects_summary.at_risk}
          icon={<AlertTriangle />}
          status="critical"
        />
      </div>

      {/* Timeline View */}
      <Card>
        <Card.Header>
          <h3 className="text-lg font-semibold">Project Timeline</h3>
        </Card.Header>
        <Card.Body>
          <div className="space-y-4">
            {timeline.map((project) => (
              <div
                key={project.project_id}
                className="border-b border-gray-200 dark:border-gray-700 pb-4 last:border-0"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium">{project.project_name}</span>
                  <span className="text-sm text-gray-500">
                    {project.current_phase}
                  </span>
                </div>

                {/* Progress Bar */}
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
                  <div
                    className="bg-primary-500 h-2.5 rounded-full transition-all"
                    style={{ width: `${project.progress}%` }}
                  />
                </div>

                <div className="flex items-center justify-between mt-1">
                  <span className="text-xs text-gray-500">
                    {project.progress}%
                  </span>
                  <span
                    className={clsx(
                      "text-xs px-2 py-0.5 rounded-full",
                      project.status === "on_track" &&
                        "bg-success-100 text-success-700",
                      project.status === "delayed" &&
                        "bg-error-100 text-error-700"
                    )}
                  >
                    {project.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card.Body>
      </Card>

      {/* Team Workload & Sprint */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Team Workload */}
        <Card>
          <Card.Header>
            <h3 className="text-lg font-semibold">Team Workload</h3>
          </Card.Header>
          <Card.Body>
            <div className="space-y-3">
              {team_workload.map((member) => (
                <div key={member.member_id}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">
                      {member.member_name}
                    </span>
                    <span className="text-sm text-gray-500">
                      {member.workload}%
                    </span>
                  </div>

                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={clsx(
                        "h-2 rounded-full",
                        member.status === "available" && "bg-success-500",
                        member.status === "normal" && "bg-primary-500",
                        member.status === "overloaded" && "bg-error-500"
                      )}
                      style={{ width: `${Math.min(member.workload, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card.Body>
        </Card>

        {/* Sprint Progress */}
        <Card>
          <Card.Header>
            <h3 className="text-lg font-semibold">
              Sprint {sprint_progress.sprint_number}
            </h3>
          </Card.Header>
          <Card.Body>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span>
                    Tasks: {sprint_progress.tasks_done}/
                    {sprint_progress.tasks_total}
                  </span>
                  <span>{sprint_progress.progress}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div
                    className="bg-primary-500 h-3 rounded-full"
                    style={{ width: `${sprint_progress.progress}%` }}
                  />
                </div>
              </div>

              {sprint_progress.blockers > 0 && (
                <div className="bg-error-50 border border-error-200 rounded-lg p-3">
                  <p className="text-sm font-medium text-error-700">
                    🔥 {sprint_progress.blockers} blocker
                    {sprint_progress.blockers > 1 ? "s" : ""}
                  </p>
                </div>
              )}

              <p className="text-xs text-gray-500">
                Ends: {new Date(sprint_progress.end_date).toLocaleDateString()}
              </p>
            </div>
          </Card.Body>
        </Card>
      </div>
    </div>
  );
};

export default PMDashboard;
