import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Download,
  FileText,
  Loader2,
  Network,
  RefreshCw,
  ShieldCheck,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  lockRadarApi,
  type LockRadarEvent,
  type LockRadarResponse,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/lock-radar")({
  component: LockRadarPage,
})

const nf = new Intl.NumberFormat("ru-RU")
const sampleModule = "CommonModule.Sales.Module"

type AppRoute = "/lock-radar" | "/operations" | "/platform-doctor" | "/update-war-room" | "/release-readiness" | "/evidence-bundle"

function downloadMarkdown(filename: string, markdown: string) {
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function LockRadarPage() {
  const [logPath, setLogPath] = useState("data/tj")
  const [modulesText, setModulesText] = useState(sampleModule)
  const [moduleLimit, setModuleLimit] = useState(12)
  const [maxDepth, setMaxDepth] = useState(5)

  const mutation = useMutation({
    mutationFn: () =>
      lockRadarApi
        .analyze({
          log_path: logPath.trim() || undefined,
          changed_modules: modulesText
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter(Boolean),
          module_limit: moduleLimit,
          max_depth: maxDepth,
        })
        .then((r) => r.data),
  })

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <Activity size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Lock Radar
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Блокировки, таймауты, дедлоки, затронутые модули, тесты и операционный runbook по технологическому журналу.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} risk={mutation.data.decision.risk_score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Technology Journal</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <TextField label="TJ path" value={logPath} onChange={setLogPath} mono />
            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Changed modules</span>
              <textarea
                value={modulesText}
                onChange={(event) => setModulesText(event.target.value)}
                spellCheck={false}
                className="min-h-[160px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <NumberField label="Module limit" value={moduleLimit} min={1} max={50} onChange={setModuleLimit} />
              <NumberField label="Graph depth" value={maxDepth} min={1} max={12} onChange={setMaxDepth} />
            </div>
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Собрать Lock Radar
            </button>
            {mutation.data && (
              <button
                onClick={() => downloadMarkdown("rentgen-lock-radar.md", mutation.data.markdown)}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:bg-accent"
              >
                <Download size={16} />
                Markdown
              </button>
            )}
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          {!mutation.data && !mutation.isError && (
            <div className="flex min-h-[560px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <Activity size={42} className="opacity-30" />
              <p className="text-sm">Жду путь к ТЖ для операционного анализа.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[560px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Lock Radar не загрузился. Проверьте backend и параметры.</p>
            </div>
          )}

          {mutation.data && <LockRadarReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function LockRadarReport({ report }: { report: LockRadarResponse }) {
  return (
    <div>
      <div className="flex flex-col gap-4 border-b border-border p-4 sm:p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <DecisionIcon status={report.decision.status} />
            <h2 className="break-words text-lg font-bold text-card-foreground sm:text-xl">
              {report.decision.headline}
            </h2>
          </div>
          <p className="mt-2 break-words font-mono text-xs text-muted-foreground">
            {report.source.path || "no TJ path"} · {report.source.available ? "evidence available" : "evidence missing"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <LinkButton to="/operations" icon={Clock3}>Operations</LinkButton>
          <LinkButton to="/update-war-room" icon={Network}>Update</LinkButton>
          <LinkButton to="/evidence-bundle" icon={FileText}>Evidence</LinkButton>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-6">
        <Metric label="Risk" value={report.decision.risk_score} icon={AlertTriangle} />
        <Metric label="Locks" value={report.summary.lock_waits} icon={Clock3} />
        <Metric label="Timeouts" value={report.summary.timeouts} icon={XCircle} />
        <Metric label="Deadlocks" value={report.summary.deadlocks} icon={AlertTriangle} />
        <Metric label="Modules" value={report.summary.modules} icon={FileText} />
        <Metric label="Gaps" value={report.summary.test_gaps} icon={ShieldCheck} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Events" icon={Activity}>
            <EventTable events={report.events} />
          </Panel>

          <Panel title="Affected Modules" icon={Network}>
            <ModuleList report={report} />
          </Panel>

          <Panel title="Runbook" icon={Clock3}>
            <div className="space-y-3">
              {report.runbook.map((item) => (
                <div key={`${item.phase}-${item.owner}`} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-card-foreground">{item.phase}</p>
                    <Badge tone="muted">{item.owner}</Badge>
                  </div>
                  <p className="mt-2 break-words text-sm text-muted-foreground">{item.action}</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Actions" icon={ShieldCheck}>
            <div className="space-y-3">
              {report.recommended_actions.map((action, index) => (
                <div key={`${action.kind}-${index}`} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={toneForSeverity(action.severity)}>{action.severity}</Badge>
                    <span className="text-xs font-medium uppercase text-muted-foreground">{action.owner}</span>
                  </div>
                  <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{action.title}</p>
                  {action.target && (
                    <p className="mt-1 break-words font-mono text-xs text-muted-foreground">{action.target}</p>
                  )}
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Caveats" icon={AlertTriangle}>
            {report.caveats.length ? (
              <ul className="space-y-2 text-sm text-muted-foreground">
                {report.caveats.map((item) => (
                  <li key={item} className="break-words">{item}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Caveats отсутствуют.</p>
            )}
          </Panel>
        </aside>
      </div>
    </div>
  )
}

function EventTable({ events }: { events: LockRadarEvent[] }) {
  if (!events.length) {
    return <p className="text-sm text-muted-foreground">События блокировок в выбранном срезе не найдены.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-border text-sm">
        <thead>
          <tr className="text-left text-xs font-semibold uppercase text-muted-foreground">
            <th className="py-2 pr-3">Kind</th>
            <th className="px-3 py-2">Duration</th>
            <th className="px-3 py-2">User</th>
            <th className="px-3 py-2">Module</th>
            <th className="py-2 pl-3">Context</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {events.map((item, index) => (
            <tr key={`${item.timestamp}-${item.kind}-${index}`}>
              <td className="py-2 pr-3 align-top">
                <Badge tone={toneForKind(item.kind)}>{item.kind}</Badge>
                <p className="mt-1 whitespace-nowrap text-xs text-muted-foreground">{item.timestamp}</p>
              </td>
              <td className="px-3 py-2 align-top text-card-foreground">{nf.format(item.duration_ms)} ms</td>
              <td className="px-3 py-2 align-top text-muted-foreground">{item.user || "n/a"}</td>
              <td className="max-w-[260px] px-3 py-2 align-top">
                <p className="break-words font-mono text-xs text-card-foreground">{item.top_module || "unknown"}</p>
              </td>
              <td className="min-w-[260px] py-2 pl-3 align-top">
                <pre className="max-h-24 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-2 text-xs text-muted-foreground">
                  {(item.context || []).join("\n") || "no context"}
                </pre>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ModuleList({ report }: { report: LockRadarResponse }) {
  if (!report.modules.length) {
    return <p className="text-sm text-muted-foreground">Модули не определены.</p>
  }

  const impactByModule = new Map(
    report.module_plan.map((item) => [String(item.module_ref ?? ""), item]),
  )
  return (
    <div className="space-y-3">
      {report.modules.map((item) => {
        const impact = impactByModule.get(item.module_ref)
        return (
          <div key={item.module_ref} className="rounded-lg border border-border bg-background/60 p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="break-words font-mono text-xs font-semibold text-card-foreground">{item.module_ref}</p>
                <p className="mt-1 text-xs text-muted-foreground">{item.sources.join(", ") || "source unknown"}</p>
              </div>
              <Badge tone={item.lock_events ? "warn" : "muted"}>{item.lock_events} events</Badge>
            </div>
            {impact && (
              <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
                <Fact label="Impact" value={String(impact.impact_total ?? 0)} />
                <Fact label="Risk" value={String((impact.quality as Record<string, unknown> | undefined)?.risk ?? "n/a")} />
                <Fact label="Entries" value={String(impact.entry_subroutines ?? 0)} />
                <Fact label="Graph" value={String((impact.graph_modules as unknown[] | undefined)?.length ?? 0)} />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function TextField({
  label,
  value,
  onChange,
  mono,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  mono?: boolean
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={cn(
          "h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary",
          mono && "font-mono",
        )}
      />
    </label>
  )
}

function NumberField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  onChange: (value: number) => void
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary"
      />
    </label>
  )
}

function Panel({ title, icon: Icon, children }: { title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Icon size={17} className="text-primary" />
        <h3 className="text-sm font-semibold text-card-foreground">{title}</h3>
      </div>
      <div className="p-4">{children}</div>
    </section>
  )
}

function Metric({ label, value, icon: Icon }: { label: string; value: string | number; icon: LucideIcon }) {
  return (
    <div className="min-w-0 border-b border-r border-border p-3 last:border-r-0 md:border-b-0 sm:p-4">
      <div className="flex items-center gap-2 text-xs font-medium uppercase text-muted-foreground">
        <Icon size={14} className="shrink-0" />
        <span className="truncate">{label}</span>
      </div>
      <p className="mt-2 break-words text-xl font-bold text-card-foreground">{value}</p>
    </div>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-card/70 p-2">
      <p className="text-[10px] font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-bold text-card-foreground">{value}</p>
    </div>
  )
}

function LinkButton({ to, icon: Icon, children }: { to: AppRoute; icon: LucideIcon; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-semibold text-card-foreground transition hover:bg-accent"
    >
      <Icon size={15} />
      {children}
    </Link>
  )
}

function Badge({ tone, children }: { tone: "ok" | "warn" | "danger" | "muted"; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex min-h-6 max-w-full items-center rounded-md px-2 py-0.5 text-xs font-semibold uppercase",
        tone === "ok" && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
        tone === "warn" && "bg-amber-500/10 text-amber-700 dark:text-amber-300",
        tone === "danger" && "bg-red-500/10 text-red-700 dark:text-red-300",
        tone === "muted" && "bg-muted text-muted-foreground",
      )}
    >
      <span className="break-words">{children}</span>
    </span>
  )
}

function StatusBadge({ status, risk }: { status: string; risk: number }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2">
      <DecisionIcon status={status} />
      <div>
        <p className="text-xs font-medium uppercase text-muted-foreground">{status}</p>
        <p className="text-sm font-bold text-card-foreground">Risk {risk}</p>
      </div>
    </div>
  )
}

function DecisionIcon({ status }: { status: string }) {
  if (status === "ready") {
    return <CheckCircle2 size={18} className="shrink-0 text-emerald-600" />
  }
  if (status === "critical" || status === "risk") {
    return <XCircle size={18} className="shrink-0 text-red-600" />
  }
  return <AlertTriangle size={18} className="shrink-0 text-amber-600" />
}

function toneForSeverity(severity: string): "ok" | "warn" | "danger" | "muted" {
  if (severity === "critical" || severity === "high") return "danger"
  if (severity === "medium") return "warn"
  if (severity === "low") return "muted"
  return "warn"
}

function toneForKind(kind: string): "ok" | "warn" | "danger" | "muted" {
  if (kind === "TDEADLOCK") return "danger"
  if (kind === "TTIMEOUT") return "danger"
  if (kind === "TLOCK") return "warn"
  return "muted"
}
