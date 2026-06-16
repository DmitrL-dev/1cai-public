import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Database,
  FileCode,
  GitBranch,
  Loader2,
  RefreshCw,
  Save,
  Search,
  TestTube2,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  requirementsApi,
  type RequirementTraceRecord,
  type RequirementTraceRequest,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/requirements")({
  component: RequirementsPage,
})

const sampleRequirement = "Order posting must validate customer credit limit and explain why posting is blocked."
const sampleCriteria = "Posting is blocked when credit limit is exceeded\nUser sees the blocking reason\nFocused regression tests cover posting"
const nf = new Intl.NumberFormat("ru-RU")

function RequirementsPage() {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState("Credit limit control")
  const [text, setText] = useState(sampleRequirement)
  const [criteria, setCriteria] = useState(sampleCriteria)
  const [limit, setLimit] = useState(6)
  const [includeIts, setIncludeIts] = useState(true)
  const [save, setSave] = useState(true)
  const [report, setReport] = useState<RequirementTraceRecord | null>(null)

  const traces = useQuery({
    queryKey: ["requirements-traces"],
    queryFn: () => requirementsApi.traces(12).then((r) => r.data),
  })

  const traceMutation = useMutation({
    mutationFn: async () => {
      const body: RequirementTraceRequest = {
        title: title.trim() || undefined,
        text,
        acceptance_criteria: criteria
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean),
        limit,
        include_its_context: includeIts,
        save,
      }
      return requirementsApi.trace(body).then((r) => r.data)
    },
    onSuccess: (data) => {
      setReport(data)
      queryClient.invalidateQueries({ queryKey: ["requirements-traces"] })
    },
  })

  const loadMutation = useMutation({
    mutationFn: (traceId: string) => requirementsApi.traceDetails(traceId).then((r) => r.data),
    onSuccess: setReport,
  })

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="hidden rounded-lg bg-primary/10 p-2 sm:block">
              <ClipboardList size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-lg font-bold leading-tight tracking-tight text-foreground sm:text-3xl">
              Requirements Traceability
            </h1>
          </div>
          <p className="mt-2 break-words text-sm text-muted-foreground sm:text-base">
            Requirement to metadata, code, risk, tests and local evidence.
          </p>
        </div>

        <button
          onClick={() => traces.refetch()}
          disabled={traces.isFetching}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-semibold text-card-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw size={16} className={traces.isFetching ? "animate-spin" : undefined} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="min-w-0 space-y-5">
          <Panel title="Requirement" icon={ClipboardList}>
            <div className="space-y-4">
              <label className="block space-y-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Title
                </span>
                <input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary"
                />
              </label>

              <label className="block space-y-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Requirement
                </span>
                <textarea
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  spellCheck={false}
                  className="min-h-[180px] w-full resize-y rounded-lg border border-border bg-background p-3 text-sm text-foreground outline-none transition focus:border-primary"
                />
              </label>

              <label className="block space-y-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Acceptance Criteria
                </span>
                <textarea
                  value={criteria}
                  onChange={(event) => setCriteria(event.target.value)}
                  spellCheck={false}
                  className="min-h-[120px] w-full resize-y rounded-lg border border-border bg-background p-3 text-sm text-foreground outline-none transition focus:border-primary"
                />
              </label>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <NumberField label="Limit" value={limit} min={1} max={20} onChange={setLimit} />
                <ToggleBox checked={includeIts} label="ITS" onChange={setIncludeIts} />
                <ToggleBox checked={save} label="Save" onChange={setSave} />
              </div>

              <button
                onClick={() => traceMutation.mutate()}
                disabled={traceMutation.isPending || text.trim().length < 8}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {traceMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : save ? <Save size={16} /> : <Search size={16} />}
                Build Trace
              </button>
            </div>
          </Panel>

          <Panel title="Stored Traces" icon={FileCode}>
            {traces.isLoading && <EmptyLine icon={Loader2} text="Loading traces." />}
            {traces.data && traces.data.items.length === 0 && (
              <EmptyLine icon={ClipboardList} text="No stored requirement traces yet." />
            )}
            {traces.data && traces.data.items.length > 0 && (
              <ul className="space-y-2">
                {traces.data.items.map((item) => (
                  <li key={item.id} className="rounded-lg border border-border bg-background/50 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-card-foreground">{item.title}</p>
                        <p className="mt-1 font-mono text-xs text-muted-foreground">{item.id}</p>
                      </div>
                      <Badge tone={item.status === "needs_review" ? "warn" : "muted"}>
                        {item.status}
                      </Badge>
                    </div>
                    <button
                      onClick={() => loadMutation.mutate(item.id)}
                      className="mt-3 inline-flex items-center gap-2 rounded-md border border-border px-2.5 py-1.5 text-xs font-semibold text-card-foreground transition hover:bg-muted"
                    >
                      <Search size={13} />
                      Open
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </section>

        <section className="min-w-0 min-h-[640px] rounded-xl border border-border bg-card">
          {traceMutation.isError && (
            <div className="flex min-h-[640px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Trace build failed. Check backend availability and requirement text.</p>
            </div>
          )}

          {!report && !traceMutation.isError && (
            <div className="flex min-h-[640px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <ClipboardList size={42} className="opacity-30" />
              <p className="text-sm">Waiting for a requirement trace.</p>
            </div>
          )}

          {report && <TraceReport report={report} />}
        </section>
      </div>
    </div>
  )
}

function TraceReport({ report }: { report: RequirementTraceRecord }) {
  const statusTone = report.status === "needs_review" ? "warn" : "ok"
  return (
    <div>
      <div className="flex flex-col gap-4 border-b border-border p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ClipboardList size={24} className={statusTone === "warn" ? "text-amber-500" : "text-emerald-500"} />
            <h2 className="min-w-0 break-words text-lg font-bold text-card-foreground sm:text-xl">
              {report.title}
            </h2>
          </div>
          <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{report.id}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={statusTone}>{report.status}</Badge>
          <Badge tone="muted">{report.links.its.length} ITS</Badge>
          <Badge tone={report.risk_summary.mapped_tests ? "ok" : "warn"}>
            {report.risk_summary.mapped_tests} mapped tests
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 border-b border-border sm:grid-cols-2 md:grid-cols-4">
        <Metric label="Modules" value={report.risk_summary.modules} icon={GitBranch} />
        <Metric label="Metadata" value={report.risk_summary.metadata_objects} icon={Database} />
        <Metric label="Impact" value={report.risk_summary.total_impact_edges} icon={AlertTriangle} />
        <Metric label="Tests" value={report.risk_summary.test_actions} icon={TestTube2} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Trace Matrix" icon={ClipboardList}>
            <TraceMatrix report={report} />
          </Panel>

          <Panel title="Requirement" icon={FileCode}>
            <p className="text-sm text-card-foreground">{report.requirement}</p>
            {report.acceptance_criteria.length > 0 && (
              <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                {report.acceptance_criteria.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <div className="min-w-0 space-y-5">
          <Panel title="Next Actions" icon={CheckCircle2}>
            <ul className="space-y-3">
              {report.next_actions.map((action, index) => (
                <li key={`${action.owner}-${action.target}-${index}`} className="space-y-1">
                  <Badge tone={action.severity === "high" ? "danger" : action.severity === "medium" ? "warn" : "muted"}>
                    {action.owner}
                  </Badge>
                  <p className="text-sm font-medium text-card-foreground">{action.title}</p>
                  {action.target && (
                    <p className="break-all font-mono text-xs text-muted-foreground">{action.target}</p>
                  )}
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Markdown" icon={FileCode}>
            <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {report.markdown}
            </pre>
          </Panel>
        </div>
      </div>
    </div>
  )
}

function TraceMatrix({ report }: { report: RequirementTraceRecord }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="py-2 pr-3 font-semibold">Module</th>
            <th className="px-3 py-2 font-semibold">Metadata</th>
            <th className="px-3 py-2 font-semibold">Impact</th>
            <th className="px-3 py-2 font-semibold">Risk</th>
            <th className="px-3 py-2 font-semibold">Coverage</th>
            <th className="py-2 pl-3 font-semibold">Tests</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {report.trace_matrix.map((row) => (
            <tr key={row.module_path}>
              <td className="py-3 pr-3">
                <p className="max-w-[260px] break-all font-mono text-xs text-card-foreground">{row.module_path}</p>
                <p className="mt-1 text-xs text-muted-foreground">{row.match_terms.slice(0, 4).join(", ")}</p>
              </td>
              <td className="px-3 py-3 text-muted-foreground">{row.metadata_object || "unmapped"}</td>
              <td className="px-3 py-3 tabular-nums text-card-foreground">{nf.format(row.impact_edges)}</td>
              <td className="px-3 py-3 tabular-nums text-card-foreground">{row.risk}</td>
              <td className="px-3 py-3">
                <Badge tone={row.coverage === "mapped" ? "ok" : row.coverage === "planned" ? "warn" : "danger"}>
                  {row.coverage}
                </Badge>
              </td>
              <td className="py-3 pl-3">
                <p className="max-w-[240px] break-all text-xs text-muted-foreground">{row.tests.slice(0, 3).join(", ")}</p>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
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

function ToggleBox({
  checked,
  label,
  onChange,
}: {
  checked: boolean
  label: string
  onChange: (checked: boolean) => void
}) {
  return (
    <label className="flex h-[62px] items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 text-sm text-card-foreground">
      <span>{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 accent-primary"
      />
    </label>
  )
}

function Metric({ label, value, icon: Icon }: { label: string; value: number; icon: LucideIcon }) {
  return (
    <div className="border-b border-r border-border px-5 py-4 last:border-r-0 md:border-b-0">
      <div className="flex items-center justify-between gap-3">
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
    <div className="rounded-lg border border-border bg-background/50">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Icon size={15} className="text-primary" />
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {title}
        </h3>
      </div>
      <div className="p-3">{children}</div>
    </div>
  )
}

function Badge({
  tone,
  children,
}: {
  tone: "danger" | "warn" | "ok" | "muted"
  children: ReactNode
}) {
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

function EmptyLine({ icon: Icon, text }: { icon: LucideIcon; text: string }) {
  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Icon size={15} />
      {text}
    </p>
  )
}
