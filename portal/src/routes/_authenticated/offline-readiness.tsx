import { useMemo, useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Database,
  FileCode,
  GlobeLock,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  offlineReadinessApi,
  type OfflineReadinessCheck,
  type OfflineReadinessResponse,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/offline-readiness")({
  component: OfflineReadinessPage,
})

const nf = new Intl.NumberFormat("ru-RU")

function OfflineReadinessPage() {
  const [strict, setStrict] = useState(false)
  const query = useQuery({
    queryKey: ["offline-readiness", strict],
    queryFn: () => offlineReadinessApi.analyze(strict).then((r) => r.data),
  })

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <LockKeyhole size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl">
              Offline Readiness
            </h1>
          </div>
          <p className="mt-2 break-words text-sm text-muted-foreground sm:text-base">
            Closed-contour self-test for local stores, ITS context, model surface and external dependencies.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <label className="inline-flex h-10 items-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-medium text-card-foreground">
            <input
              type="checkbox"
              checked={strict}
              onChange={(event) => setStrict(event.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            Strict
          </label>
          <button
            onClick={() => query.refetch()}
            disabled={query.isFetching}
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw size={16} className={query.isFetching ? "animate-spin" : undefined} />
            Refresh
          </button>
        </div>
      </div>

      {query.isError && (
        <section className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-destructive">
          <div className="flex items-center gap-2">
            <AlertTriangle size={20} />
            <p className="font-semibold">Offline readiness failed to load.</p>
          </div>
        </section>
      )}

      {!query.data && !query.isError && (
        <section className="flex min-h-[480px] flex-col items-center justify-center gap-3 rounded-xl border border-border bg-card text-muted-foreground">
          <RefreshCw size={40} className="animate-spin opacity-40" />
          <p className="text-sm">Reading local contour signals.</p>
        </section>
      )}

      {query.data && <OfflineReport report={query.data} />}
    </div>
  )
}

function OfflineReport({ report }: { report: OfflineReadinessResponse }) {
  const status = report.decision.status
  const StatusIcon = status === "pass" ? CheckCircle2 : status === "warn" ? AlertTriangle : XCircle
  const externalLabel = report.external_env.length ? report.external_env.join(", ") : "No known external env vars"
  const failedChecks = useMemo(
    () => report.checks.filter((check) => check.status !== "pass"),
    [report.checks],
  )

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="min-w-0 rounded-xl border border-border bg-card">
        <div className="flex flex-col gap-4 border-b border-border p-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <StatusIcon size={24} className={statusTone(status)} />
              <h2 className="min-w-0 break-words text-base font-bold text-card-foreground sm:text-xl">
                {status.toUpperCase()} - score {report.decision.score}
              </h2>
            </div>
            <p className="mt-1 break-all text-xs text-muted-foreground">{report.root}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge tone={status === "fail" ? "danger" : status === "warn" ? "warn" : "ok"}>
              {report.strict ? "strict" : "relaxed"}
            </Badge>
            <Badge tone="muted">{report.summary.checks} checks</Badge>
            <Badge tone={report.summary.external_env ? "warn" : "ok"}>
              {report.summary.external_env} external
            </Badge>
          </div>
        </div>

        <div className="grid grid-cols-1 border-b border-border sm:grid-cols-2 md:grid-cols-4">
          <Metric label="Passes" value={report.summary.passes} icon={ShieldCheck} />
          <Metric label="Warnings" value={report.summary.warnings} icon={AlertTriangle} />
          <Metric label="Metadata" value={report.summary.metadata_objects} icon={Database} />
          <Metric label="ITS Docs" value={report.summary.its_docs} icon={ClipboardList} />
        </div>

        <div className="space-y-5 p-5">
          <Panel title="Checks" icon={ShieldCheck}>
            <CheckTable checks={report.checks} />
          </Panel>

          <Panel title="Attention" icon={AlertTriangle}>
            {failedChecks.length === 0 ? (
              <EmptyLine icon={CheckCircle2} text="All checks are green." />
            ) : (
              <ul className="space-y-3">
                {failedChecks.map((check) => (
                  <li key={check.id} className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={check.status === "fail" ? "danger" : "warn"}>
                        {check.status}
                      </Badge>
                      <span className="text-sm font-medium text-card-foreground">{check.title}</span>
                    </div>
                    <p className="break-all font-mono text-xs text-muted-foreground">
                      {formatEvidence(check.evidence)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </section>

      <aside className="min-w-0 space-y-5">
        <Panel title="External Surface" icon={GlobeLock}>
          <p className="break-words text-sm text-card-foreground">{externalLabel}</p>
          <div className="mt-3 space-y-1 text-xs text-muted-foreground">
            {Object.entries(report.runtime).map(([key, value]) => (
              <p key={key} className="flex items-center justify-between gap-3">
                <span className="font-mono">{key}</span>
                <span className="truncate text-card-foreground">{value || "unset"}</span>
              </p>
            ))}
          </div>
        </Panel>

        <Panel title="Caveats" icon={AlertTriangle}>
          <ul className="space-y-2 text-sm text-muted-foreground">
            {report.caveats.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Panel>

        <Panel title="Markdown" icon={FileCode}>
          <pre className="max-h-[480px] overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
            {report.markdown}
          </pre>
        </Panel>
      </aside>
    </div>
  )
}

function CheckTable({ checks }: { checks: OfflineReadinessCheck[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="py-2 pr-3 font-semibold">Status</th>
            <th className="px-3 py-2 font-semibold">Check</th>
            <th className="px-3 py-2 font-semibold">Severity</th>
            <th className="py-2 pl-3 font-semibold">Evidence</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {checks.map((check) => (
            <tr key={check.id}>
              <td className="py-3 pr-3">
                <Badge tone={check.status === "fail" ? "danger" : check.status === "warn" ? "warn" : "ok"}>
                  {check.status}
                </Badge>
              </td>
              <td className="px-3 py-3">
                <p className="font-medium text-card-foreground">{check.title}</p>
                <p className="font-mono text-xs text-muted-foreground">{check.id}</p>
              </td>
              <td className="px-3 py-3 text-muted-foreground">{check.severity}</td>
              <td className="py-3 pl-3">
                <p className="max-w-[360px] break-all font-mono text-xs text-muted-foreground">
                  {formatEvidence(check.evidence)}
                </p>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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

function formatEvidence(value: OfflineReadinessCheck["evidence"]) {
  if (value === null || value === undefined) return ""
  if (typeof value === "object") return JSON.stringify(value)
  return String(value)
}

function statusTone(status: OfflineReadinessResponse["decision"]["status"]) {
  if (status === "pass") return "text-emerald-500"
  if (status === "warn") return "text-amber-500"
  return "text-red-500"
}
