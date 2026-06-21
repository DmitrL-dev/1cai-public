import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  FileCode,
  FolderSearch,
  GitBranch,
  Loader2,
  PlayCircle,
  ShieldCheck,
  Timer,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { managementApi, type IntakePlanResponse } from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/configurations")({
  component: ConfigurationsPage,
})

type SourceType = "auto" | "edt" | "git" | "xml"
type KnownRoute = "/metadata" | "/quality" | "/change" | "/release-readiness" | "/"

const nf = new Intl.NumberFormat("ru-RU")
const sourceTypes: Array<{ id: SourceType; label: string; icon: LucideIcon }> = [
  { id: "auto", label: "Auto", icon: FolderSearch },
  { id: "edt", label: "EDT/XML", icon: Database },
  { id: "git", label: "Git", icon: GitBranch },
  { id: "xml", label: "XML", icon: FileCode },
]
const knownRoutes: readonly KnownRoute[] = ["/metadata", "/quality", "/change", "/release-readiness", "/"]

function ConfigurationsPage() {
  const [sourcePath, setSourcePath] = useState("data/configs/unpacked")
  const [sourceType, setSourceType] = useState<SourceType>("auto")
  const mutation = useMutation({
    mutationFn: () =>
      managementApi
        .intakePlan({
          source_path: sourcePath.trim() || undefined,
          source_type: sourceType,
        })
        .then((r) => r.data),
  })

  const plan = mutation.data

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <Database size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Конфигурации
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Pre-flight для EDT/Git/XML источника: что найдено, что покрыто, где caveat и какой первый анализ запускать.
          </p>
        </div>
        {plan && <StatusBadge status={plan.decision.status} score={plan.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Источник</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Путь</span>
              <input
                value={sourcePath}
                onChange={(event) => setSourcePath(event.target.value)}
                className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary"
              />
            </label>

            <div className="grid grid-cols-2 gap-2">
              {sourceTypes.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setSourceType(item.id)}
                  className={cn(
                    "inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-semibold transition",
                    sourceType === item.id
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-background text-card-foreground hover:bg-accent",
                  )}
                >
                  <item.icon size={16} />
                  {item.label}
                </button>
              ))}
            </div>

            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <PlayCircle size={16} />}
              Проверить источник
            </button>
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          {!plan && !mutation.isError && (
            <div className="flex min-h-[360px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <FolderSearch size={42} className="opacity-30" />
              <p className="text-sm">Источник еще не проверен.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[360px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Pre-flight не выполнен. Проверьте backend и путь к источнику.</p>
            </div>
          )}

          {plan && <IntakePlan plan={plan} />}
        </section>
      </div>
    </div>
  )
}

function IntakePlan({ plan }: { plan: IntakePlanResponse }) {
  return (
    <div>
      <div className="flex flex-col gap-4 border-b border-border p-4 sm:p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <DecisionIcon status={plan.decision.status} />
            <h2 className="break-words text-lg font-bold text-card-foreground sm:text-xl">{plan.decision.headline}</h2>
          </div>
          <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{plan.source.path}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge tone="muted">{plan.source.detected_type}</Badge>
            <Badge tone={plan.source.exists ? "ok" : "danger"}>{plan.source.exists ? "path exists" : "path missing"}</Badge>
            <Badge tone={plan.inventory.scan_truncated ? "warn" : "muted"}>
              scanned {nf.format(plan.inventory.scanned_files)}
            </Badge>
            <Badge tone="muted">{new Date(plan.generated_at).toLocaleString("ru-RU")}</Badge>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:min-w-[280px]">
          <CompactFact label="Score" value={`${plan.decision.score}%`} />
          <CompactFact label="Estimate" value={`${plan.estimate.minutes} мин`} />
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-5">
        <Metric label="BSL" value={plan.inventory.bsl_files} icon={FileCode} />
        <Metric label="XML" value={plan.inventory.xml_files} icon={Database} />
        <Metric label="Forms" value={plan.inventory.form_files} icon={FolderSearch} />
        <Metric label="Rights" value={plan.inventory.rights_files} icon={ShieldCheck} />
        <Metric label="Tests" value={plan.inventory.test_files} icon={CheckCircle2} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Panel title="Покрытие источника" icon={Database}>
          <div className="space-y-3">
            {plan.coverage.map((item) => (
              <div key={item.id} className="rounded-lg border border-border bg-background/60 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                    {item.caveat && <p className="mt-1 break-words text-xs text-muted-foreground">{item.caveat}</p>}
                  </div>
                  <Badge tone={toneForStatus(item.status)}>{item.status} · {nf.format(item.count)}</Badge>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Следующие действия" icon={Timer}>
          <div className="space-y-3">
            {plan.next_actions.map((action) => (
              <Link
                key={action.label}
                to={toKnownRoute(action.to)}
                className={cn(
                  "block rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40",
                  !action.enabled && "opacity-60",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="break-words text-sm font-semibold text-card-foreground">{action.label}</p>
                  <Badge tone={action.enabled ? "ok" : "warn"}>{action.enabled ? "ready" : "caveat"}</Badge>
                </div>
                <p className="mt-1 break-words text-xs text-muted-foreground">{action.reason}</p>
              </Link>
            ))}
          </div>
        </Panel>
      </div>
    </div>
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
  if (status === "blocked" || status === "fail") return <XCircle size={size} className="text-red-500" />
  return <AlertTriangle size={size} className="text-amber-500" />
}

function Metric({ label, value, icon: Icon }: { label: string; value: number; icon: LucideIcon }) {
  return (
    <div className="border-b border-r border-border p-4 last:border-r-0 md:border-b-0">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
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
        <h2 className="text-sm font-semibold text-card-foreground">{title}</h2>
      </div>
      <div className="p-4">{children}</div>
    </section>
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

function Badge({ tone, children }: { tone: string; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold", badgeClass(tone))}>
      {children}
    </span>
  )
}

function toneForStatus(status: string): string {
  if (status === "ready") return "ok"
  if (status === "missing" || status === "blocked") return "danger"
  return "warn"
}

function statusClass(status: string): string {
  if (status === "ready") return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
  if (status === "blocked") return "bg-red-500/10 text-red-600 dark:text-red-400"
  return "bg-amber-500/10 text-amber-600 dark:text-amber-400"
}

function badgeClass(tone: string): string {
  if (tone === "ok") return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
  if (tone === "danger") return "bg-red-500/10 text-red-600 dark:text-red-400"
  if (tone === "warn") return "bg-amber-500/10 text-amber-600 dark:text-amber-400"
  return "bg-muted text-muted-foreground"
}

function toKnownRoute(value: string): KnownRoute {
  return (knownRoutes as readonly string[]).includes(value) ? (value as KnownRoute) : "/"
}
