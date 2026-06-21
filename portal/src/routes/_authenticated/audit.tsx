import { useState, type ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation, useQuery } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  Fingerprint,
  History,
  Loader2,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { auditApi, type AuditEvent, type AuditVerifyReport } from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/audit")({
  component: AuditPage,
})

const nf = new Intl.NumberFormat("ru-RU")

function downloadText(filename: string, content: string, type = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function AuditPage() {
  const [actor, setActor] = useState("")
  const [action, setAction] = useState("")
  const [category, setCategory] = useState("")
  const [target, setTarget] = useState("")
  const [limit, setLimit] = useState(100)

  const verifyQuery = useQuery({
    queryKey: ["audit", "verify"],
    queryFn: () => auditApi.verify().then((response) => response.data),
  })
  const eventsQuery = useQuery({
    queryKey: ["audit", "events", actor, action, category, target, limit],
    queryFn: () =>
      auditApi
        .events({
          actor: actor.trim() || undefined,
          action: action.trim() || undefined,
          category: category.trim() || undefined,
          target: target.trim() || undefined,
          limit,
        })
        .then((response) => response.data),
  })
  const exportMutation = useMutation({
    mutationFn: (format: "jsonl" | "json") => auditApi.export(format).then((response) => response.data),
    onSuccess: (result) => {
      downloadText(
        `rentgen-audit.${result.format === "json" ? "json" : "jsonl"}`,
        result.content,
        result.format === "json" ? "application/json;charset=utf-8" : "application/x-ndjson;charset=utf-8",
      )
    },
  })
  const siemExportMutation = useMutation({
    mutationFn: () => auditApi.siemExport("jsonl", limit).then((response) => response.data),
    onSuccess: (result) => {
      downloadText(
        result.ingestion.recommended_filename,
        result.content,
        "application/x-ndjson;charset=utf-8",
      )
    },
  })

  const refresh = () => {
    verifyQuery.refetch()
    eventsQuery.refetch()
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <ScrollText size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Audit Log
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-all font-mono text-xs text-muted-foreground">
            {verifyQuery.data?.path ?? eventsQuery.data?.path ?? "data/audit_log.ndjson"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={refresh}
            disabled={verifyQuery.isFetching || eventsQuery.isFetching}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-semibold text-card-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw size={16} className={verifyQuery.isFetching || eventsQuery.isFetching ? "animate-spin" : undefined} />
            Refresh
          </button>
          <button
            onClick={() => exportMutation.mutate("jsonl")}
            disabled={exportMutation.isPending}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {exportMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
            JSONL
          </button>
          <button
            onClick={() => exportMutation.mutate("json")}
            disabled={exportMutation.isPending}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-semibold text-card-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download size={16} />
            JSON
          </button>
          <button
            onClick={() => siemExportMutation.mutate()}
            disabled={siemExportMutation.isPending}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-semibold text-card-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            {siemExportMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
            SIEM
          </button>
        </div>
      </header>

      {verifyQuery.data && <VerifySummary report={verifyQuery.data} />}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="min-w-0 space-y-5">
          <Panel title="Filters" icon={History}>
            <div className="space-y-3">
              <TextField label="Actor" value={actor} onChange={setActor} />
              <TextField label="Action" value={action} onChange={setAction} />
              <TextField label="Category" value={category} onChange={setCategory} />
              <TextField label="Target" value={target} onChange={setTarget} />
              <label className="block space-y-1.5">
                <span className="text-xs font-semibold uppercase text-muted-foreground">Limit</span>
                <input
                  type="number"
                  min={1}
                  max={1000}
                  value={limit}
                  onChange={(event) => setLimit(Math.max(1, Math.min(Number(event.target.value) || 100, 1000)))}
                  className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary"
                />
              </label>
            </div>
          </Panel>

          <Panel title="Proof Routes" icon={Fingerprint}>
            <div className="grid grid-cols-1 gap-2">
              <RouteLink to="/approvals" label="Approvals" />
              <RouteLink to="/evidence-bundle" label="Evidence Bundle" />
              <RouteLink to="/enterprise-trust-center" label="Trust Center" />
            </div>
          </Panel>

          {verifyQuery.data?.broken?.length ? (
            <Panel title="Broken Entries" icon={XCircle}>
              <div className="space-y-3">
                {verifyQuery.data.broken.map((item) => (
                  <div key={`${item.index}-${item.id}`} className="rounded-lg border border-destructive/30 bg-destructive/10 p-3">
                    <p className="font-mono text-xs text-destructive">{item.id}</p>
                    <p className="mt-1 text-xs text-destructive">{item.reasons.join(", ")}</p>
                  </div>
                ))}
              </div>
            </Panel>
          ) : null}
        </aside>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          <div className="flex flex-col gap-2 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-card-foreground">Recent Events</h2>
              <p className="mt-1 text-xs text-muted-foreground">{nf.format(eventsQuery.data?.total ?? 0)} matching</p>
            </div>
            {(exportMutation.isError || siemExportMutation.isError) && <span className="text-xs text-destructive">Export failed</span>}
          </div>

          {eventsQuery.isLoading && <LoadingState />}
          {eventsQuery.isError && <ErrorState text="Audit events did not load." />}
          {eventsQuery.data && eventsQuery.data.items.length === 0 && <EmptyState />}
          {eventsQuery.data && eventsQuery.data.items.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead className="border-b border-border text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Time</th>
                    <th className="px-4 py-3 font-semibold">Actor</th>
                    <th className="px-4 py-3 font-semibold">Action</th>
                    <th className="px-4 py-3 font-semibold">Category</th>
                    <th className="px-4 py-3 font-semibold">Outcome</th>
                    <th className="px-4 py-3 font-semibold">Target</th>
                    <th className="px-4 py-3 font-semibold">ID</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {eventsQuery.data.items.map((item) => (
                    <EventRow key={item.id} event={item} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function VerifySummary({ report }: { report: AuditVerifyReport }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
      <Metric label="Valid" value={report.valid ? "yes" : "no"} icon={report.valid ? CheckCircle2 : XCircle} tone={report.valid ? "ok" : "danger"} />
      <Metric label="Total" value={report.total} icon={ScrollText} />
      <Metric label="Chained" value={report.chained} icon={ShieldCheck} tone="ok" />
      <Metric label="Legacy" value={report.legacy} icon={AlertTriangle} tone={report.legacy ? "warn" : undefined} />
      <Metric label="Broken" value={report.broken.length} icon={XCircle} tone={report.broken.length ? "danger" : "ok"} />
    </div>
  )
}

function EventRow({ event }: { event: AuditEvent }) {
  return (
    <tr className="align-top">
      <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(event.timestamp)}</td>
      <td className="px-4 py-3 font-mono text-xs text-card-foreground">{event.actor}</td>
      <td className="px-4 py-3">
        <p className="break-words text-xs font-semibold text-card-foreground">{event.action}</p>
        {event.correlation_id && <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">{event.correlation_id}</p>}
      </td>
      <td className="px-4 py-3"><Badge tone="muted">{event.category}</Badge></td>
      <td className="px-4 py-3"><Badge tone={event.outcome === "success" ? "ok" : "danger"}>{event.outcome}</Badge></td>
      <td className="px-4 py-3 max-w-[220px] break-all font-mono text-xs text-muted-foreground">{event.target || "n/a"}</td>
      <td className="px-4 py-3 max-w-[240px] break-all font-mono text-xs text-muted-foreground">{event.id}</td>
    </tr>
  )
}

function Panel({ title, icon: Icon, children }: { title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Icon size={16} className="text-primary" />
        <h2 className="text-xs font-semibold uppercase text-muted-foreground">{title}</h2>
      </div>
      <div className="p-4">{children}</div>
    </section>
  )
}

function Metric({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string
  value: number | string
  icon: LucideIcon
  tone?: "ok" | "warn" | "danger"
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium uppercase text-muted-foreground">{label}</p>
        <Icon
          size={17}
          className={cn(
            tone === "ok" && "text-emerald-600",
            tone === "warn" && "text-amber-600",
            tone === "danger" && "text-destructive",
            !tone && "text-primary",
          )}
        />
      </div>
      <p className="mt-3 break-words text-xl font-bold tabular-nums text-card-foreground">
        {typeof value === "number" ? nf.format(value) : value}
      </p>
    </div>
  )
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary"
      />
    </label>
  )
}

function RouteLink({
  to,
  label,
}: {
  to: "/approvals" | "/evidence-bundle" | "/enterprise-trust-center"
  label: string
}) {
  return (
    <Link
      to={to}
      className="inline-flex h-9 items-center justify-between rounded-lg border border-border bg-background px-3 text-sm font-semibold text-card-foreground transition hover:bg-accent"
    >
      <span>{label}</span>
      <FileText size={15} />
    </Link>
  )
}

function Badge({ tone, children }: { tone: "ok" | "danger" | "muted"; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center rounded-md px-2 py-1 text-xs font-semibold",
        tone === "ok" && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
        tone === "danger" && "bg-destructive/10 text-destructive",
        tone === "muted" && "bg-muted text-muted-foreground",
      )}
    >
      {children}
    </span>
  )
}

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("ru-RU")
}

function LoadingState() {
  return (
    <div className="flex min-h-[420px] items-center justify-center text-muted-foreground">
      <Loader2 size={24} className="mr-2 animate-spin" />
      Loading
    </div>
  )
}

function ErrorState({ text }: { text: string }) {
  return (
    <div className="flex min-h-[420px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
      <AlertTriangle size={38} />
      <p className="text-sm">{text}</p>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
      <History size={38} className="opacity-40" />
      <p className="text-sm">No audit events.</p>
    </div>
  )
}
