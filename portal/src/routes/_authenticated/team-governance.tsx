import { type ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Loader2,
  RefreshCw,
  Save,
  ShieldAlert,
  Users,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { teamGovernanceApi, type TeamGovernanceResponse } from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/team-governance")({
  component: TeamGovernancePage,
})

const nf = new Intl.NumberFormat("ru-RU")

function TeamGovernancePage() {
  const queryClient = useQueryClient()
  const boardQ = useQuery({
    queryKey: ["team-governance-board"],
    queryFn: () => teamGovernanceApi.board({ limit: 40 }).then((r) => r.data),
  })

  const snapshotM = useMutation({
    mutationFn: () => teamGovernanceApi.snapshot(40).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team-governance-board"] }),
  })

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <Users size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl">
              Team Governance
            </h1>
          </div>
          <p className="mt-2 break-words text-sm text-muted-foreground sm:text-base">
            {boardQ.data?.trend.path ?? "Ownership, risk SLA and release review queue"}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => boardQ.refetch()}
            disabled={boardQ.isFetching}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-semibold text-card-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw size={16} className={boardQ.isFetching ? "animate-spin" : undefined} />
            Refresh
          </button>
          <button
            onClick={() => snapshotM.mutate()}
            disabled={snapshotM.isPending}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {snapshotM.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            Snapshot
          </button>
        </div>
      </header>

      {boardQ.isLoading && (
        <div className="flex min-h-[420px] items-center justify-center rounded-lg border border-border bg-card">
          <Loader2 size={34} className="animate-spin text-primary" />
        </div>
      )}

      {boardQ.isError && (
        <div className="flex min-h-[360px] flex-col items-center justify-center gap-3 rounded-lg border border-border bg-card px-6 text-center text-destructive">
          <AlertTriangle size={38} />
          <p className="text-sm">Team governance request failed.</p>
        </div>
      )}

      {boardQ.data && <GovernanceReport report={boardQ.data} />}
    </div>
  )
}

function GovernanceReport({ report }: { report: TeamGovernanceResponse }) {
  const queue = report.release_board.review_queue
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <Metric label="Areas" value={report.summary.areas} icon={Users} />
        <Metric label="Red" value={report.summary.red_areas} icon={ShieldAlert} tone="red" />
        <Metric label="Yellow" value={report.summary.yellow_areas} icon={Clock3} tone="yellow" />
        <Metric label="Queue" value={report.summary.review_queue} icon={AlertTriangle} />
        <Metric label="Modules" value={report.summary.total_modules} icon={CheckCircle2} />
        <Metric label="Issues" value={report.summary.modules_with_issues} icon={AlertTriangle} />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="min-w-0 space-y-6">
          <Panel title="Ownership Areas" icon={Users}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {report.areas.slice(0, 12).map((area) => (
                <div key={area.domain} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={area.status} />
                    <span className="break-words text-sm font-semibold text-card-foreground">{area.domain}</span>
                  </div>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{area.owner.name}</p>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    <Small label="Modules" value={nf.format(area.modules)} />
                    <Small label="Risk" value={nf.format(area.max_risk)} />
                    <Small label="SLA" value={area.risk_sla} />
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Review Queue" icon={AlertTriangle}>
            {queue.length === 0 ? (
              <Empty text="No queued high-risk modules." />
            ) : (
              <ul className="space-y-3">
                {queue.slice(0, 20).map((item, index) => (
                  <li key={`${index}-${String(item.module_path)}`} className="rounded-lg border border-border bg-background/60 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge>{String(item.risk ?? 0)}</Badge>
                      <span className="text-xs font-semibold uppercase text-muted-foreground">
                        {String((item.owner as Record<string, unknown>)?.name ?? "owner")}
                      </span>
                    </div>
                    <p className="mt-2 break-all font-mono text-xs text-card-foreground">{String(item.module_path ?? "")}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{String(item.sla ?? "")}</p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </section>

        <aside className="min-w-0 space-y-6">
          <Panel title="Actions" icon={ShieldAlert}>
            <ActionList items={report.recommendations} />
          </Panel>

          <Panel title="SLA Policy" icon={Clock3}>
            <KeyValue values={report.release_board.sla_policy} />
          </Panel>

          <Panel title="Trend" icon={Save}>
            <KeyValue
              values={{
                Snapshots: nf.format(report.trend.total),
                Latest: String(report.trend.snapshots[0]?.created_at ?? "none"),
              }}
            />
          </Panel>

          <Panel title="Markdown" icon={CheckCircle2}>
            <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {report.markdown}
            </pre>
          </Panel>
        </aside>
      </div>
    </div>
  )
}

function Metric({ label, value, icon: Icon, tone }: { label: string; value: number; icon: LucideIcon; tone?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <Icon size={17} className={cn(tone === "red" && "text-red-500", tone === "yellow" && "text-amber-500", !tone && "text-primary")} />
      </div>
      <p className="mt-3 break-words text-xl font-bold tabular-nums text-card-foreground">{nf.format(value)}</p>
    </div>
  )
}

function Panel({ title, icon: Icon, children }: { title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Icon size={16} className="text-primary" />
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h2>
      </div>
      <div className="p-4">{children}</div>
    </section>
  )
}

function StatusBadge({ status }: { status: string }) {
  const classes = {
    red: "bg-red-500/10 text-red-600 dark:text-red-400 ring-red-500/25",
    yellow: "bg-amber-500/10 text-amber-600 dark:text-amber-400 ring-amber-500/25",
    green: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 ring-emerald-500/25",
  }[status] ?? "bg-muted text-muted-foreground ring-border"
  return <span className={cn("rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset", classes)}>{status}</span>
}

function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary ring-1 ring-inset ring-primary/20">
      {children}
    </span>
  )
}

function Small({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md border border-border bg-card px-2 py-1.5">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className="mt-1 break-words font-semibold text-card-foreground">{value}</p>
    </div>
  )
}

function ActionList({ items }: { items: TeamGovernanceResponse["recommendations"] }) {
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={`${item.owner}-${item.title}`} className="rounded-lg border border-border bg-background/60 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{item.severity}</Badge>
            <span className="text-xs font-semibold uppercase text-muted-foreground">{item.owner}</span>
          </div>
          <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{item.title}</p>
        </li>
      ))}
    </ul>
  )
}

function KeyValue({ values }: { values: Record<string, string> }) {
  return (
    <ul className="space-y-2">
      {Object.entries(values).map(([key, value]) => (
        <li key={key} className="flex items-start justify-between gap-3 text-sm">
          <span className="text-muted-foreground">{key}</span>
          <span className="min-w-0 break-words text-right font-semibold text-card-foreground">{value}</span>
        </li>
      ))}
    </ul>
  )
}

function Empty({ text }: { text: string }) {
  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <CheckCircle2 size={15} />
      {text}
    </p>
  )
}
