import { useState, type ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  Code2,
  ExternalLink,
  FileCode2,
  Loader2,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { metadataApi, type MetadataSecurityPosture } from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/security")({
  component: SecurityPage,
})

const nf = new Intl.NumberFormat("ru-RU")

function SecurityPage() {
  const [moduleLimit, setModuleLimit] = useState(2500)

  const postureQ = useQuery({
    queryKey: ["metadata-security-posture", moduleLimit],
    queryFn: () =>
      metadataApi
        .securityPosture({ limit: 200, module_limit: moduleLimit })
        .then((r) => r.data),
  })

  const posture = postureQ.data

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <ShieldCheck size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl">
              Security Posture
            </h1>
          </div>
          <p className="mt-2 break-all text-sm text-muted-foreground sm:text-base">
            {posture?.config_path ?? "1C EDT metadata and BSL security scan"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex h-10 items-center gap-2 rounded-lg border border-border bg-card px-3 text-sm text-card-foreground">
            <span className="text-xs text-muted-foreground">Modules</span>
            <input
              type="number"
              min={100}
              max={30000}
              step={100}
              value={moduleLimit}
              onChange={(event) => setModuleLimit(Number(event.target.value) || 2500)}
              className="h-7 w-20 rounded-md border border-border bg-background px-2 text-right text-xs outline-none focus:border-primary"
            />
          </label>
          <button
            onClick={() => postureQ.refetch()}
            disabled={postureQ.isFetching}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-semibold text-card-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw size={16} className={postureQ.isFetching ? "animate-spin" : undefined} />
            Refresh
          </button>
        </div>
      </header>

      {postureQ.isLoading && (
        <div className="flex min-h-[420px] items-center justify-center rounded-lg border border-border bg-card">
          <Loader2 size={34} className="animate-spin text-primary" />
        </div>
      )}

      {postureQ.isError && (
        <div className="flex min-h-[420px] flex-col items-center justify-center gap-3 rounded-lg border border-border bg-card px-6 text-center text-destructive">
          <AlertTriangle size={40} />
          <p className="text-sm">Security posture request failed.</p>
        </div>
      )}

      {posture && <SecurityReport posture={posture} />}
    </div>
  )
}

function SecurityReport({ posture }: { posture: MetadataSecurityPosture }) {
  const roleDiff = posture.role_diff as {
    included?: boolean
    available_snapshots?: number
    summary?: Record<string, number>
    latest_snapshot?: { id?: string } | null
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <Metric label="Score" value={posture.decision.score} icon={ShieldCheck} tone={posture.decision.status} />
        <Metric label="Findings" value={posture.summary.findings} icon={AlertTriangle} />
        <Metric label="Danger Rights" value={posture.summary.dangerous_rights ?? 0} icon={ShieldAlert} />
        <Metric label="Privileged" value={posture.summary.privileged_code_paths ?? 0} icon={Code2} />
        <Metric label="Dynamic Exec" value={posture.summary.dynamic_execute_paths ?? 0} icon={FileCode2} />
        <Metric label="External" value={posture.summary.external_exposure ?? 0} icon={ExternalLink} />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="min-w-0 space-y-6">
          <Panel title="Release Actions" icon={ShieldAlert}>
            <ActionList items={posture.recommendations} />
          </Panel>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Panel title="Role Rights" icon={ShieldCheck}>
              <FindingList
                empty="No role findings."
                items={posture.role_review.findings.map((item) => ({
                  key: `${item.role}-${item.code}`,
                  severity: item.severity,
                  title: item.code,
                  target: item.role,
                  message: item.message,
                }))}
              />
            </Panel>

            <Panel title="Privileged Code" icon={Code2}>
              <FindingList
                empty="No privileged mode calls."
                items={posture.privileged_code_paths.map((item, index) => codeFinding(item, index))}
              />
            </Panel>

            <Panel title="Dynamic Execute" icon={FileCode2}>
              <FindingList
                empty="No dynamic execute calls."
                items={posture.dynamic_execute_paths.map((item, index) => codeFinding(item, index))}
              />
            </Panel>

            <Panel title="Integration Exposure" icon={ExternalLink}>
              <FindingList
                empty="No integration exposure."
                items={[
                  ...posture.integration_exposure.metadata_objects.map((item, index) => ({
                    key: `meta-${index}-${String(item.ref ?? item.path ?? "")}`,
                    severity: String(item.severity ?? "medium"),
                    title: String(item.type ?? "metadata"),
                    target: String(item.ref ?? item.path ?? ""),
                    message: String(item.message ?? "Exchange or integration metadata object."),
                  })),
                  ...posture.integration_exposure.code_paths.map((item, index) => codeFinding(item, index)),
                ]}
              />
            </Panel>
          </div>
        </section>

        <aside className="min-w-0 space-y-6">
          <Panel title="Scan" icon={FileCode2}>
            <KeyValue
              values={{
                Status: posture.decision.status,
                Modules: nf.format(posture.code_scan.scanned_modules),
                Limit: nf.format(posture.code_scan.scan_limit ?? 0),
                Truncated: posture.code_scan.truncated ? "yes" : "no",
                Roles: nf.format(posture.summary.roles ?? 0),
              }}
            />
          </Panel>

          <Panel title="Role Diff" icon={ShieldCheck}>
            {roleDiff.included ? (
              <KeyValue
                values={{
                  Added: nf.format(roleDiff.summary?.added_roles ?? 0),
                  Removed: nf.format(roleDiff.summary?.removed_roles ?? 0),
                  Changed: nf.format(roleDiff.summary?.changed_roles ?? 0),
                }}
              />
            ) : (
              <KeyValue
                values={{
                  Snapshots: nf.format(roleDiff.available_snapshots ?? 0),
                  Latest: roleDiff.latest_snapshot?.id ?? "none",
                }}
              />
            )}
          </Panel>

          <Panel title="Severity" icon={AlertTriangle}>
            <KeyValue values={Object.fromEntries(Object.entries(posture.summary.by_severity).map(([key, value]) => [key, nf.format(value)]))} />
          </Panel>

          <Panel title="Markdown" icon={FileCode2}>
            <pre className="max-h-[460px] overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {posture.markdown}
            </pre>
          </Panel>
        </aside>
      </div>
    </div>
  )
}

function codeFinding(item: Record<string, unknown>, index: number) {
  return {
    key: `code-${index}-${String(item.module_path ?? "")}-${String(item.line ?? "")}`,
    severity: String(item.severity ?? "medium"),
    title: String(item.rule_id ?? item.title ?? "code"),
    target: `${String(item.module_path ?? "")}${item.line ? `:${String(item.line)}` : ""}`,
    message: String(item.snippet ?? item.recommendation ?? ""),
  }
}

function severityTone(severity: string): "danger" | "warn" | "muted" {
  if (severity === "high") return "danger"
  if (severity === "medium") return "warn"
  return "muted"
}

function Metric({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string
  value: number
  icon: LucideIcon
  tone?: string
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <Icon
          size={17}
          className={cn(
            tone === "pass" && "text-emerald-500",
            tone === "warn" && "text-amber-500",
            tone === "fail" && "text-red-500",
            !tone && "text-primary",
          )}
        />
      </div>
      <p className="mt-3 break-words text-xl font-bold tabular-nums text-card-foreground">
        {nf.format(value)}
      </p>
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

function FindingList({
  items,
  empty,
}: {
  items: Array<{ key: string; severity: string; title: string; target: string; message: string }>
  empty: string
}) {
  if (items.length === 0) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <CheckCircle2 size={15} />
        {empty}
      </p>
    )
  }

  return (
    <ul className="max-h-[420px] space-y-3 overflow-auto">
      {items.slice(0, 80).map((item) => (
        <li key={item.key} className="rounded-lg border border-border bg-background/60 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={severityTone(item.severity)}>{item.title}</Badge>
            <span className="break-all font-mono text-[11px] text-muted-foreground">{item.target}</span>
          </div>
          <p className="mt-2 break-words text-sm text-card-foreground">{item.message}</p>
        </li>
      ))}
    </ul>
  )
}

function ActionList({
  items,
}: {
  items: MetadataSecurityPosture["recommendations"]
}) {
  return (
    <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      {items.map((item) => (
        <li key={`${item.owner}-${item.title}`} className="rounded-lg border border-border bg-background/60 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={severityTone(item.severity)}>{item.severity}</Badge>
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

function Badge({
  tone,
  children,
}: {
  tone: "danger" | "warn" | "muted"
  children: ReactNode
}) {
  const tones = {
    danger: "bg-red-500/10 text-red-600 dark:text-red-400 ring-red-500/25",
    warn: "bg-amber-500/10 text-amber-600 dark:text-amber-400 ring-amber-500/25",
    muted: "bg-muted text-muted-foreground ring-border",
  }
  return (
    <span className={cn("rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset", tones[tone])}>
      {children}
    </span>
  )
}
