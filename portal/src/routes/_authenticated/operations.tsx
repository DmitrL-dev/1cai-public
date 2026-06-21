import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileCode,
  GitBranch,
  Loader2,
  Search,
  TestTube2,
  Users,
  Wrench,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  operationsApi,
  type IncidentReportRequest,
  type IncidentReportResponse,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/operations")({
  component: OperationsPage,
})

const sampleModule = "CommonModules/СводнаяТаблицаУХ/Ext/Module.bsl"
const nf = new Intl.NumberFormat("ru-RU")

function OperationsPage() {
  const [title, setTitle] = useState("Slow posting in production")
  const [description, setDescription] = useState("Slow posting, lock waits, users report timeouts in peak load.")
  const [logPath, setLogPath] = useState("")
  const [modules, setModules] = useState(sampleModule)
  const [minDuration, setMinDuration] = useState(100)
  const [topN, setTopN] = useState(10)

  const mutation = useMutation({
    mutationFn: async () => {
      const body: IncidentReportRequest = {
        incident_title: title.trim() || "Production incident",
        description,
        symptoms: description
          .split(/[.,;\n]/)
          .map((item) => item.trim())
          .filter(Boolean),
        changed_modules: modules
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean),
        min_duration_ms: minDuration,
        top_n: topN,
        log_path: logPath.trim() || undefined,
      }
      return operationsApi.incidentReport(body).then((r) => r.data)
    },
  })

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <AlertTriangle size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl">
              Incident
            </h1>
          </div>
          <p className="mt-2 break-words text-sm text-muted-foreground sm:text-base">
            Symptoms and logs to impacted modules, owners, tests and runbook.
          </p>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)] xl:gap-6">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5 sm:py-4">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Triage</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <TextField label="Title" value={title} onChange={setTitle} />
            <TextArea
              label="Symptoms"
              value={description}
              minHeight="min-h-28"
              onChange={setDescription}
            />
            <TextArea
              label="TJ path"
              value={logPath}
              minHeight="min-h-16"
              onChange={setLogPath}
              placeholder="C:\\logs\\tj or C:\\logs\\tj\\rphost.log"
              mono
            />
            <TextArea
              label="Suspect modules"
              value={modules}
              minHeight="min-h-32"
              onChange={setModules}
              mono
            />
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <NumberField label="Min ms" value={minDuration} min={0} max={60000} onChange={setMinDuration} />
              <NumberField label="Top N" value={topN} min={1} max={50} onChange={setTopN} />
            </div>
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || (!description.trim() && !modules.trim() && !logPath.trim())}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
              Build Report
            </button>
          </div>
        </section>

        <section className="min-h-[620px] min-w-0 rounded-lg border border-border bg-card">
          {!mutation.data && !mutation.isError && (
            <div className="flex min-h-[620px] flex-col items-center justify-center gap-3 px-6 text-center text-muted-foreground">
              <Activity size={42} className="opacity-30" />
              <p className="text-sm">Waiting for incident context.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[620px] flex-col items-center justify-center gap-3 px-6 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Incident report failed. Check backend availability and paths.</p>
            </div>
          )}

          {mutation.data && <IncidentReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function IncidentReport({ report }: { report: IncidentReportResponse }) {
  const status = report.decision.status
  const StatusIcon = status === "low" ? CheckCircle2 : AlertTriangle
  return (
    <div>
      <div className="flex flex-col gap-4 border-b border-border p-4 sm:p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <StatusIcon className={statusTone(status)} size={23} />
            <h2 className="min-w-0 break-words text-lg font-bold text-card-foreground sm:text-xl">
              {report.incident.title}
            </h2>
          </div>
          <p className="mt-1 break-words text-xs text-muted-foreground">
            {new Date(report.generated_at).toLocaleString("ru-RU")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={status === "critical" ? "danger" : status === "high" ? "warn" : status === "medium" ? "warn" : "ok"}>
            {status}
          </Badge>
          <Badge tone="muted">score {report.decision.severity_score}</Badge>
          <Badge tone="muted">risk {report.decision.max_module_risk}</Badge>
          <Link
            to="/lock-radar"
            className="inline-flex h-7 items-center justify-center rounded-md border border-border bg-background px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
          >
            Lock Radar
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-4">
        <Metric label="Hotspots" value={report.summary.hotspots} icon={Activity} />
        <Metric label="Locks" value={report.summary.lock_waits + report.summary.deadlocks} icon={Clock3} />
        <Metric label="Impact" value={report.summary.total_impact_edges} icon={GitBranch} />
        <Metric label="Gaps" value={report.summary.test_gaps} icon={TestTube2} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Signals" icon={AlertTriangle}>
            <SignalList items={report.signals} />
          </Panel>

          <Panel title="Module Plan" icon={FileCode}>
            {report.module_plan.length === 0 ? (
              <Empty text="No module impact context yet." />
            ) : (
              <ul className="space-y-3">
                {report.module_plan.slice(0, 12).map((item) => (
                  <li key={item.module_ref} className="rounded-lg border border-border bg-background/60 p-3">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className="break-all font-mono text-xs font-semibold text-card-foreground">
                          {item.module_ref}
                        </p>
                        <p className="mt-1 break-words text-xs text-muted-foreground">
                          {item.owner?.name ?? "unassigned"} · {item.sources.join(", ")}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        <Badge tone={(item.quality?.risk ?? 0) >= 70 ? "danger" : "muted"}>
                          risk {item.quality?.risk ?? 0}
                        </Badge>
                        <Badge tone={item.impact_total >= 300 ? "warn" : "muted"}>
                          impact {nf.format(item.impact_total)}
                        </Badge>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Actions" icon={Wrench}>
            <ActionList items={report.recommended_actions} />
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Runbook" icon={Clock3}>
            <ul className="space-y-3">
              {report.runbook.map((item) => (
                <li key={item.phase} className="text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{item.phase}</Badge>
                    <span className="text-xs font-semibold uppercase text-muted-foreground">{item.owner}</span>
                  </div>
                  <p className="mt-1 break-words text-card-foreground">{item.action}</p>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Owners" icon={Users}>
            <KeyValue values={report.team_governance.owner_counts} />
          </Panel>

          <Panel title="Markdown" icon={FileCode}>
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {report.markdown}
            </pre>
          </Panel>
        </aside>
      </div>
    </div>
  )
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-10 w-full resize-y rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-primary"
      />
    </label>
  )
}

function TextArea({
  label,
  value,
  minHeight,
  onChange,
  placeholder,
  mono,
}: {
  label: string
  value: string
  minHeight: string
  onChange: (value: string) => void
  placeholder?: string
  mono?: boolean
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
      <textarea
        value={value}
        placeholder={placeholder}
        spellCheck={false}
        onChange={(event) => onChange(event.target.value)}
        className={cn(
          minHeight,
          "w-full resize-y rounded-lg border border-border bg-background p-3 text-sm text-foreground outline-none transition focus:border-primary",
          mono && "font-mono text-xs",
        )}
      />
    </label>
  )
}

function NumberField({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
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

function Metric({ label, value, icon: Icon }: { label: string; value: number; icon: LucideIcon }) {
  return (
    <div className="border-b border-r border-border px-4 py-4 last:border-r-0 md:border-b-0 sm:px-5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <Icon size={16} className="text-primary" />
      </div>
      <p className="mt-2 break-words text-xl font-bold tabular-nums text-card-foreground sm:text-2xl">
        {nf.format(value)}
      </p>
    </div>
  )
}

function Panel({ title, icon: Icon, children }: { title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-background/50">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Icon size={15} className="text-primary" />
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      </div>
      <div className="p-3">{children}</div>
    </section>
  )
}

function SignalList({ items }: { items: IncidentReportResponse["signals"] }) {
  if (items.length === 0) return <Empty text="No explicit incident signals." />
  return (
    <ul className="space-y-2">
      {items.map((item, index) => (
        <li key={`${item.kind}-${index}`} className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <span className="break-words text-sm font-medium text-card-foreground">{item.title}</span>
          <Badge tone={item.severity === "critical" ? "danger" : item.severity === "high" ? "warn" : "muted"}>
            {item.severity}
          </Badge>
        </li>
      ))}
    </ul>
  )
}

function ActionList({ items }: { items: IncidentReportResponse["recommended_actions"] }) {
  return (
    <ul className="space-y-3">
      {items.slice(0, 14).map((item, index) => (
        <li key={`${item.kind}-${item.target}-${index}`} className="text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={item.severity === "critical" || item.severity === "high" ? "danger" : item.severity === "medium" ? "warn" : "muted"}>
              {item.owner}
            </Badge>
            <span className="break-words font-medium text-card-foreground">{item.title}</span>
          </div>
          {item.target && <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{item.target}</p>}
        </li>
      ))}
    </ul>
  )
}

function KeyValue({ values }: { values: Record<string, number> }) {
  const entries = Object.entries(values)
  if (entries.length === 0) return <Empty text="No owners mapped." />
  return (
    <ul className="space-y-2">
      {entries.map(([key, value]) => (
        <li key={key} className="flex items-start justify-between gap-3 text-sm">
          <span className="min-w-0 break-words text-muted-foreground">{key}</span>
          <span className="font-semibold tabular-nums text-card-foreground">{nf.format(value)}</span>
        </li>
      ))}
    </ul>
  )
}

function Badge({ tone, children }: { tone: "danger" | "warn" | "ok" | "muted"; children: ReactNode }) {
  const tones = {
    danger: "bg-red-500/10 text-red-600 dark:text-red-400 ring-red-500/25",
    warn: "bg-amber-500/10 text-amber-600 dark:text-amber-400 ring-amber-500/25",
    ok: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 ring-emerald-500/25",
    muted: "bg-muted text-muted-foreground ring-border",
  }
  return (
    <span className={cn("rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset", tones[tone])}>
      {children}
    </span>
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

function statusTone(status: IncidentReportResponse["decision"]["status"]) {
  if (status === "critical") return "text-red-500"
  if (status === "high") return "text-amber-500"
  if (status === "medium") return "text-amber-500"
  return "text-emerald-500"
}
