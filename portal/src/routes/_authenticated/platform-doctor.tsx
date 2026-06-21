import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Database,
  FileCode,
  Loader2,
  RefreshCw,
  ServerCog,
  ShieldCheck,
  Timer,
  Wrench,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  platformDoctorApi,
  type PlatformDoctorCheck,
  type PlatformDoctorResponse,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/platform-doctor")({
  component: PlatformDoctorPage,
})

const nf = new Intl.NumberFormat("ru-RU")

function PlatformDoctorPage() {
  const [configPath, setConfigPath] = useState("data/configs/unpacked")
  const [targetVersion, setTargetVersion] = useState("")
  const query = useQuery({
    queryKey: ["platform-doctor", configPath, targetVersion],
    queryFn: () =>
      platformDoctorApi
        .analyze({
          config_path: configPath.trim() || undefined,
          target_platform_version: targetVersion.trim() || undefined,
        })
        .then((r) => r.data),
  })

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <ServerCog size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Platform Doctor
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Версия платформы, режим совместимости, СУБД, техжурнал, OpenMetrics, лицензии и upgrade checklist.
          </p>
        </div>
        {query.data && <StatusBadge status={query.data.decision.status} score={query.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Контур</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <TextField label="EDT/XML путь" value={configPath} onChange={setConfigPath} mono />
            <TextField label="Целевая версия платформы" value={targetVersion} onChange={setTargetVersion} placeholder="8.3.26.x" />
            <button
              onClick={() => query.refetch()}
              disabled={query.isFetching}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {query.isFetching ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Проверить платформу
            </button>
            <div className="rounded-lg border border-border bg-background/60 p-3 text-xs text-muted-foreground">
              Env-поля: `ONEC_PLATFORM_VERSION`, `ONEC_TARGET_PLATFORM_VERSION`, `ONEC_COMPATIBILITY_MODE`, `ONEC_DBMS`,
              `ONEC_TECH_JOURNAL_PATH`, `ONEC_OPENMETRICS_URL`.
            </div>
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          {query.isError && (
            <div className="flex min-h-[420px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Platform Doctor не загрузился. Проверьте backend и параметры.</p>
            </div>
          )}

          {!query.data && !query.isError && (
            <div className="flex min-h-[420px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <ServerCog size={42} className="opacity-30" />
              <p className="text-sm">Собираю платформенный inventory.</p>
            </div>
          )}

          {query.data && <PlatformReport report={query.data} />}
        </section>
      </div>
    </div>
  )
}

function PlatformReport({ report }: { report: PlatformDoctorResponse }) {
  const failed = report.checks.filter((item) => item.status !== "pass")
  return (
    <div>
      <div className="flex flex-col gap-4 border-b border-border p-4 sm:p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <DecisionIcon status={report.decision.status} />
            <h2 className="break-words text-lg font-bold text-card-foreground sm:text-xl">{report.decision.headline}</h2>
          </div>
          <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{report.config_path}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge tone="muted">from {report.upgrade.from || "unknown"}</Badge>
            <Badge tone="muted">to {report.upgrade.to || "unknown"}</Badge>
            <Badge tone={report.upgrade.readiness === "ready" ? "ok" : report.upgrade.readiness === "blocked" ? "danger" : "warn"}>
              {report.upgrade.readiness}
            </Badge>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-5">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Checks" value={report.checks.length} icon={ClipboardList} />
        <Metric label="Attention" value={failed.length} icon={AlertTriangle} />
        <Metric label="Extensions" value={report.inventory.extensions_count} icon={Wrench} />
        <Metric label="Capabilities" value={report.capabilities.filter((item) => item.available).length} icon={Activity} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Inventory" icon={Database}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Fact label="Конфигурация" value={report.inventory.configuration_name || "unknown"} />
              <Fact label="Версия конфигурации" value={report.inventory.configuration_version || "unknown"} />
              <Fact label="Платформа" value={report.inventory.platform_version || "unknown"} />
              <Fact label="Совместимость" value={report.inventory.compatibility_mode || "unknown"} />
              <Fact label="СУБД" value={report.inventory.dbms || "unknown"} />
              <Fact label="Кластер" value={report.inventory.cluster || report.inventory.infobase_mode || "unknown"} />
            </div>
          </Panel>

          <Panel title="Checks" icon={ShieldCheck}>
            <CheckTable checks={report.checks} />
          </Panel>

          <Panel title="Capabilities" icon={Activity}>
            <div className="space-y-3">
              {report.capabilities.map((item) => (
                <div key={item.id} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                    <Badge tone={item.available ? "ok" : "warn"}>{item.available ? "available" : "needs data"}</Badge>
                  </div>
                  <p className="mt-1 break-all text-xs text-muted-foreground">{formatEvidence(item.evidence)}</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Upgrade checklist" icon={Timer}>
            <ul className="space-y-2">
              {report.upgrade.checklist.map((item) => (
                <li key={item} className="flex gap-2 text-sm text-muted-foreground">
                  <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-primary" />
                  <span className="break-words">{item}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Caveats" icon={AlertTriangle}>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {report.caveats.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
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

function CheckTable({ checks }: { checks: PlatformDoctorCheck[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[780px] text-left text-sm">
        <thead className="border-b border-border text-xs uppercase text-muted-foreground">
          <tr>
            <th className="py-2 pr-3 font-semibold">Status</th>
            <th className="px-3 py-2 font-semibold">Check</th>
            <th className="px-3 py-2 font-semibold">Severity</th>
            <th className="py-2 pl-3 font-semibold">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {checks.map((check) => (
            <tr key={check.id}>
              <td className="py-3 pr-3">
                <Badge tone={check.status === "pass" ? "ok" : check.severity === "high" ? "danger" : "warn"}>{check.status}</Badge>
              </td>
              <td className="px-3 py-3">
                <p className="font-semibold text-card-foreground">{check.title}</p>
                <p className="font-mono text-xs text-muted-foreground">{check.id}</p>
              </td>
              <td className="px-3 py-3 text-muted-foreground">{check.severity}</td>
              <td className="py-3 pl-3">
                <p className="max-w-[360px] break-words text-xs text-muted-foreground">{check.action}</p>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  mono,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  mono?: boolean
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className={cn(
          "h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary",
          mono && "font-mono",
        )}
      />
    </label>
  )
}

function StatusBadge({ status, score }: { status: string; score: number }) {
  return (
    <span className={cn("inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-semibold", statusClass(status))}>
      <DecisionIcon status={status} size={16} />
      {status} · {score}
    </span>
  )
}

function DecisionIcon({ status, size = 20 }: { status: string; size?: number }) {
  if (status === "ready") return <CheckCircle2 size={size} className="text-emerald-500" />
  if (status === "risk" || status === "blocked") return <XCircle size={size} className="text-red-500" />
  return <AlertTriangle size={size} className="text-amber-500" />
}

function Metric({ label, value, icon: Icon }: { label: string; value: number; icon: LucideIcon }) {
  return (
    <div className="border-b border-r border-border p-4 last:border-r-0 md:border-b-0">
      <div className="flex items-center justify-between gap-2">
        <p className="break-words text-xs font-semibold uppercase text-muted-foreground">{label}</p>
        <Icon size={16} className="text-primary" />
      </div>
      <p className="mt-3 text-2xl font-bold tabular-nums text-card-foreground">{nf.format(value)}</p>
    </div>
  )
}

function Panel({ title, icon: Icon, children }: { title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Icon size={17} className="text-primary" />
        <h2 className="break-words text-sm font-semibold text-card-foreground">{title}</h2>
      </div>
      <div className="p-4">{children}</div>
    </section>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-card-foreground">{value}</p>
    </div>
  )
}

function Badge({ tone, children }: { tone: string; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold", badgeClass(tone))}>
      {children}
    </span>
  )
}

function formatEvidence(value: unknown): string {
  if (value === null || value === undefined) return "n/a"
  if (typeof value === "string") return value || "n/a"
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function statusClass(status: string): string {
  if (status === "ready") return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
  if (status === "risk" || status === "blocked") return "bg-red-500/10 text-red-600 dark:text-red-400"
  return "bg-amber-500/10 text-amber-600 dark:text-amber-400"
}

function badgeClass(tone: string): string {
  if (tone === "ok") return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
  if (tone === "danger") return "bg-red-500/10 text-red-600 dark:text-red-400"
  if (tone === "warn") return "bg-amber-500/10 text-amber-600 dark:text-amber-400"
  return "bg-muted text-muted-foreground"
}
