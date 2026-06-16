import { createFileRoute } from "@tanstack/react-router"
import { Users, Radio, Activity } from "lucide-react"
import { cn } from "@/lib/utils"

function AdminPage() {
  const stats = [
    { label: "Total Users", value: "156", icon: Users, color: "text-blue-500" },
    { label: "Active Sessions", value: "23", icon: Radio, color: "text-green-500" },
    { label: "API Calls Today", value: "4,521", icon: Activity, color: "text-purple-500" },
  ]

  const auditLog = [
    { timestamp: "2026-02-22 14:32:10", actor: "admin", action: "User Login", target: "Portal Dashboard" },
    { timestamp: "2026-02-22 14:28:45", actor: "ivanov.a", action: "Code Review Approved", target: "PR #412 — Sales Module" },
    { timestamp: "2026-02-22 13:55:02", actor: "petrov.d", action: "Plugin Installed", target: "BSL Language Server v2.4" },
    { timestamp: "2026-02-22 13:41:18", actor: "admin", action: "User Created", target: "sidorov.m@company.ru" },
    { timestamp: "2026-02-22 12:17:33", actor: "kuznetsova.e", action: "Configuration Deployed", target: "ERP Production" },
    { timestamp: "2026-02-22 11:52:09", actor: "novikov.s", action: "BPMN Diagram Edited", target: "Order Processing v3" },
    { timestamp: "2026-02-22 11:30:44", actor: "admin", action: "Role Assigned", target: "petrov.d → Developer" },
    { timestamp: "2026-02-22 10:05:21", actor: "morozova.l", action: "Wiki Article Published", target: "Deployment Guide" },
  ]

  return (
    <div className="space-y-8 p-6">
      <h1 className="text-3xl font-bold tracking-tight text-foreground">
        Admin Panel
      </h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="flex items-center gap-4 rounded-lg border bg-card p-6"
          >
            <div className={cn("rounded-md bg-muted p-3", stat.color)}>
              <stat.icon className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
              <p className="text-2xl font-semibold text-foreground">
                {stat.value}
              </p>
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-foreground">Audit Log</h2>
        <div className="overflow-x-auto rounded-lg border bg-card">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b bg-muted/60">
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                  Timestamp
                </th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                  Actor
                </th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                  Action
                </th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                  Target
                </th>
              </tr>
            </thead>
            <tbody>
              {auditLog.map((row, i) => (
                <tr
                  key={i}
                  className={cn(
                    "border-b last:border-b-0",
                    i % 2 !== 0 && "bg-muted/50",
                  )}
                >
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-muted-foreground">
                    {row.timestamp}
                  </td>
                  <td className="px-4 py-3 font-medium text-foreground">
                    {row.actor}
                  </td>
                  <td className="px-4 py-3 text-foreground">{row.action}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {row.target}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export const Route = createFileRoute("/_authenticated/admin")({
  component: AdminPage,
})
