import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import type { ReactNode } from "react"
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock3,
  Database,
  GitBranch,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Users,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { managementApi, type ExecutiveDashboardResponse } from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/")({
  component: DashboardPage,
})

const nf = new Intl.NumberFormat("ru-RU")

function DashboardPage() {
  const query = useQuery({
    queryKey: ["management", "executive"],
    queryFn: () => managementApi.executive().then((r) => r.data),
    refetchInterval: 60_000,
  })

  const report = query.data

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <BarChart3 size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Executive Control
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Release confidence, ownership risk, offline readiness and internal workflow coverage.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {report && <StatusBadge status={report.decision.status} score={report.decision.score} />}
          <button
            onClick={() => query.refetch()}
            disabled={query.isFetching}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-medium text-card-foreground transition hover:bg-accent disabled:opacity-60"
          >
            {query.isFetching ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            Refresh
          </button>
        </div>
      </header>

      {query.isLoading && (
        <div className="flex min-h-[420px] items-center justify-center rounded-lg border border-border bg-card text-muted-foreground">
          <Loader2 size={22} className="mr-2 animate-spin" />
          Loading executive signals
        </div>
      )}

      {query.isError && (
        <div className="flex min-h-[420px] flex-col items-center justify-center rounded-lg border border-border bg-card px-6 text-center text-destructive">
          <AlertTriangle size={36} />
          <p className="mt-3 text-sm font-semibold">Executive dashboard failed to load.</p>
        </div>
      )}

      {report && <ExecutiveDashboard report={report} />}
    </div>
  )
}

function ExecutiveDashboard({ report }: { report: ExecutiveDashboardResponse }) {
  return (
    <>
      <section className="rounded-lg border border-border bg-card p-4 sm:p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Decision</p>
            <h2 className="mt-1 break-words text-lg font-bold text-card-foreground sm:text-2xl">
              {report.decision.headline}
            </h2>
            <p className="mt-2 break-words text-sm text-muted-foreground">
              {report.decision.release_policy}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge tone={report.available ? "ok" : "danger"}>{report.available ? "store ready" : "store blocked"}</Badge>
            <Badge tone="muted">{new Date(report.generated_at).toLocaleString("ru-RU")}</Badge>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} tone={report.decision.status} />
        <Metric label="Modules" value={report.kpis.modules} icon={Database} />
        <Metric label="Red Areas" value={report.kpis.red_areas} icon={AlertTriangle} tone={report.kpis.red_areas ? "critical" : "ready"} />
        <Metric label="Review Queue" value={report.kpis.review_queue} icon={Users} tone={report.kpis.review_queue ? "watch" : "ready"} />
        <Metric label="Coverage" value={`${report.kpis.coverage_score}%`} icon={CheckCircle2} tone={report.kpis.coverage_score === 100 ? "ready" : "watch"} />
        <Metric label="Offline" value={`${report.kpis.offline_score}%`} icon={Clock3} tone={report.kpis.offline_score >= 90 ? "ready" : "watch"} />
        <Metric label="Call Edges" value={report.kpis.call_edges} icon={GitBranch} />
        <Metric label="High Risk" value={report.risk_summary.high_hotspots} icon={Activity} tone={report.risk_summary.high_hotspots ? "critical" : "ready"} />
      </section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <Panel title="Workstreams" icon={BarChart3}>
          <div className="space-y-3">
            {report.workstreams.map((item) => (
              <div key={item.id} className="rounded-lg border border-border bg-background/60 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                    <p className="mt-0.5 break-words text-xs text-muted-foreground">{item.signal}</p>
                  </div>
                  <Badge tone={toneForStatus(item.status)}>{item.score}%</Badge>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded bg-muted">
                  <div className={cn("h-full rounded", barTone(item.status))} style={{ width: `${Math.max(0, Math.min(100, item.score))}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Manager Actions" icon={AlertTriangle}>
          <div className="space-y-3">
            {report.manager_actions.map((item) => (
              <div key={`${item.severity}-${item.owner}-${item.title}`} className="rounded-lg border border-border bg-background/60 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={severityTone(item.severity)}>{item.severity}</Badge>
                  <span className="text-xs font-semibold uppercase text-muted-foreground">{item.owner}</span>
                </div>
                <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                <p className="mt-1 break-words text-xs text-muted-foreground">{item.impact}</p>
              </div>
            ))}
          </div>
        </Panel>
      </section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel title="Top Risks" icon={Activity}>
          {report.risk_summary.top_risks.length === 0 ? (
            <Empty text="No high-risk hotspots in the current store." />
          ) : (
            <ul className="space-y-3">
              {report.risk_summary.top_risks.map((item) => (
                <li key={`${item.module_path}-${item.risk}`} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge tone={item.risk >= 70 ? "danger" : "warn"}>risk {item.risk}</Badge>
                    <span className="text-xs text-muted-foreground">fan-in {nf.format(item.fan_in)}</span>
                  </div>
                  <p className="mt-2 break-all font-mono text-xs font-semibold text-card-foreground">{item.module_path}</p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{item.domain}</p>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Release Queue" icon={Users}>
          {report.governance.review_queue.length === 0 ? (
            <Empty text="No owner review queue." />
          ) : (
            <ul className="space-y-3">
              {report.governance.review_queue.map((item, index) => (
                <li key={`${String(item.module_path)}-${index}`} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="warn">SLA {String(item.sla ?? "review")}</Badge>
                    <span className="text-xs font-semibold uppercase text-muted-foreground">
                      {String((item.owner as Record<string, unknown> | undefined)?.name ?? "owner")}
                    </span>
                  </div>
                  <p className="mt-2 break-all font-mono text-xs text-card-foreground">{String(item.module_path ?? "")}</p>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </section>

      <section className="rounded-lg border border-border bg-card p-4 sm:p-5">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <CompactFact label="Product Coverage" value={`${report.coverage.done}/${report.coverage.total}`} />
          <CompactFact label="P0 Coverage" value={`${report.coverage.p0_score}%`} />
          <CompactFact label="Governance Snapshots" value={String(report.governance.trend.total ?? 0)} />
        </div>
      </section>
    </>
  )
}

function Metric({ label, value, icon: Icon, tone = "neutral" }: { label: string; value: number | string; icon: LucideIcon; tone?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="min-w-0 break-words text-xs font-semibold uppercase text-muted-foreground">{label}</p>
        <Icon size={17} className={iconTone(tone)} />
      </div>
      <p className="mt-3 break-words text-2xl font-bold tabular-nums text-card-foreground sm:text-3xl">
        {typeof value === "number" ? nf.format(value) : value}
      </p>
    </div>
  )
}

function Panel({ title, icon: Icon, children }: { title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3 sm:px-5">
        <Icon size={17} className="text-primary" />
        <h2 className="break-words text-sm font-semibold text-card-foreground sm:text-base">{title}</h2>
      </div>
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  )
}

function StatusBadge({ status, score }: { status: ExecutiveDashboardResponse["decision"]["status"]; score: number }) {
  const Icon = status === "ready" ? CheckCircle2 : status === "blocked" || status === "critical" ? XCircle : AlertTriangle
  return (
    <span className={cn("inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-semibold", statusClass(status))}>
      <Icon size={16} />
      {status} · {score}
    </span>
  )
}

function Badge({ tone, children }: { tone: string; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold", badgeClass(tone))}>
      {children}
    </span>
  )
}

function CompactFact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-lg font-bold text-card-foreground">{value}</p>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">{text}</p>
}

function toneForStatus(status: string): string {
  if (status === "ready") return "ok"
  if (status === "risk" || status === "critical") return "danger"
  return "warn"
}

function severityTone(severity: string): string {
  if (severity === "critical" || severity === "high") return "danger"
  if (severity === "medium") return "warn"
  return "muted"
}

function barTone(status: string): string {
  if (status === "ready") return "bg-emerald-500"
  if (status === "risk" || status === "critical") return "bg-red-500"
  return "bg-amber-500"
}

function iconTone(tone: string): string {
  if (tone === "ready") return "text-emerald-500"
  if (tone === "critical" || tone === "risk") return "text-red-500"
  if (tone === "watch") return "text-amber-500"
  return "text-muted-foreground"
}

function statusClass(status: string): string {
  if (status === "ready") return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
  if (status === "blocked" || status === "critical") return "bg-red-500/10 text-red-600 dark:text-red-400"
  if (status === "risk") return "bg-orange-500/10 text-orange-600 dark:text-orange-400"
  return "bg-amber-500/10 text-amber-600 dark:text-amber-400"
}

function badgeClass(tone: string): string {
  if (tone === "ok") return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
  if (tone === "danger") return "bg-red-500/10 text-red-600 dark:text-red-400"
  if (tone === "warn") return "bg-amber-500/10 text-amber-600 dark:text-amber-400"
  return "bg-muted text-muted-foreground"
}
