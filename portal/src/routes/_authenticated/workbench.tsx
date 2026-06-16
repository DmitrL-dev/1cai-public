import { createFileRoute, Link } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import type { ReactNode } from "react"
import {
  Activity,
  AlertTriangle,
  Archive,
  BarChart3,
  CheckCircle2,
  ClipboardList,
  Database,
  FileDiff,
  GitBranch,
  Loader2,
  Network,
  RefreshCw,
  ShieldCheck,
  TestTube2,
  Users,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  artifactsApi,
  auditApi,
  changeSetsApi,
  enterpriseApi,
  metadataApi,
  policiesApi,
  requirementsApi,
  testingEvidenceApi,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/workbench")({
  component: WorkbenchPage,
})

const nf = new Intl.NumberFormat("ru-RU")

function WorkbenchPage() {
  const artifactsQ = useQuery({ queryKey: ["workbench", "artifacts-health"], queryFn: () => artifactsApi.health().then((r) => r.data) })
  const matrixQ = useQuery({ queryKey: ["workbench", "artifact-matrix"], queryFn: () => artifactsApi.matrix().then((r) => r.data) })
  const changesQ = useQuery({ queryKey: ["workbench", "change-sets"], queryFn: () => changeSetsApi.list({ limit: 20 }).then((r) => r.data) })
  const testsQ = useQuery({ queryKey: ["workbench", "test-runs"], queryFn: () => testingEvidenceApi.runs({ limit: 20 }).then((r) => r.data) })
  const policiesQ = useQuery({ queryKey: ["workbench", "policy-evaluations"], queryFn: () => policiesApi.evaluations(20).then((r) => r.data) })
  const metadataQ = useQuery({ queryKey: ["workbench", "canonical-snapshots"], queryFn: () => metadataApi.canonicalSnapshots().then((r) => r.data) })
  const auditQ = useQuery({ queryKey: ["workbench", "audit-events"], queryFn: () => auditApi.events({ limit: 20 }).then((r) => r.data) })
  const enterpriseQ = useQuery({ queryKey: ["workbench", "enterprise-readiness"], queryFn: () => enterpriseApi.readiness().then((r) => r.data) })
  const requirementsQ = useQuery({ queryKey: ["workbench", "requirements"], queryFn: () => requirementsApi.traces(20).then((r) => r.data) })

  const queries = [artifactsQ, matrixQ, changesQ, testsQ, policiesQ, metadataQ, auditQ, enterpriseQ, requirementsQ]
  const isFetching = queries.some((query) => query.isFetching)
  const hasError = queries.some((query) => query.isError)

  const latestPolicy = policiesQ.data?.items?.[0]
  const failedTests = testsQ.data?.items.filter((item) => item.status === "failed").length ?? 0
  const warningTests = testsQ.data?.items.filter((item) => item.status === "warning").length ?? 0
  const readyScore = score([
    matrixQ.data?.summary.gaps === 0,
    failedTests === 0,
    latestPolicy?.status !== "fail",
    enterpriseQ.data?.status !== "fail",
    Boolean(metadataQ.data?.total),
  ])

  const stages = [
    {
      title: "Needs",
      icon: ClipboardList,
      to: "/requirements",
      status: count(requirementsQ.data?.total) ? "ready" : "watch",
      primary: count(requirementsQ.data?.total),
      secondary: "requirements",
    },
    {
      title: "Architecture",
      icon: Network,
      to: "/architecture",
      status: matrixQ.data?.summary.gaps ? "watch" : "ready",
      primary: count(matrixQ.data?.summary.covered),
      secondary: `${count(matrixQ.data?.summary.gaps)} gaps`,
    },
    {
      title: "Metadata",
      icon: Database,
      to: "/metadata",
      status: metadataQ.data?.total ? "ready" : "watch",
      primary: count(metadataQ.data?.total),
      secondary: "snapshots",
    },
    {
      title: "Change Sets",
      icon: FileDiff,
      to: "/change",
      status: count(changesQ.data?.total) ? "watch" : "ready",
      primary: count(changesQ.data?.total),
      secondary: "active",
    },
    {
      title: "Testing",
      icon: TestTube2,
      to: "/testing",
      status: failedTests ? "risk" : warningTests ? "watch" : "ready",
      primary: count(testsQ.data?.total),
      secondary: `${failedTests} failed`,
    },
    {
      title: "Policy",
      icon: ShieldCheck,
      to: "/release-readiness",
      status: latestPolicy?.status === "fail" ? "risk" : latestPolicy?.status === "warn" ? "watch" : "ready",
      primary: count(policiesQ.data?.total),
      secondary: latestPolicy?.status ?? "no gates",
    },
    {
      title: "Release",
      icon: Archive,
      to: "/release-readiness",
      status: readyScore >= 80 ? "ready" : readyScore >= 50 ? "watch" : "risk",
      primary: readyScore,
      secondary: "readiness",
    },
    {
      title: "Enterprise",
      icon: Users,
      to: "/settings",
      status: enterpriseQ.data?.status === "fail" ? "risk" : enterpriseQ.data?.status === "warn" ? "watch" : "ready",
      primary: count(enterpriseQ.data?.summary.boundaries),
      secondary: enterpriseQ.data?.status ?? "unknown",
    },
  ] as const

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <BarChart3 size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Delivery Workbench
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Requirements, architecture, metadata, change sets, tests, policy gates, release and audit.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={readyScore >= 80 ? "ready" : readyScore >= 50 ? "watch" : "risk"} score={readyScore} />
          <button
            onClick={() => queries.forEach((query) => query.refetch())}
            disabled={isFetching}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-medium text-card-foreground transition hover:bg-accent disabled:opacity-60"
          >
            {isFetching ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            Refresh
          </button>
        </div>
      </header>

      {hasError && (
        <section className="rounded-lg border border-red-500/25 bg-red-500/10 p-4 text-sm text-red-600 dark:text-red-400">
          <div className="flex items-center gap-2 font-semibold">
            <AlertTriangle size={17} />
            Some workbench signals failed to load.
          </div>
        </section>
      )}

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Artifacts" value={count(artifactsQ.data?.artifacts)} icon={GitBranch} />
        <Metric label="Trace Gaps" value={count(matrixQ.data?.summary.gaps)} icon={AlertTriangle} tone={matrixQ.data?.summary.gaps ? "risk" : "ready"} />
        <Metric label="Test Runs" value={count(testsQ.data?.total)} icon={TestTube2} tone={failedTests ? "risk" : "ready"} />
        <Metric label="Audit Events" value={count(auditQ.data?.total)} icon={Activity} />
        <Metric label="Policy Gates" value={count(policiesQ.data?.total)} icon={ShieldCheck} tone={latestPolicy?.status === "fail" ? "risk" : "ready"} />
        <Metric label="Metadata Snapshots" value={count(metadataQ.data?.total)} icon={Database} />
        <Metric label="Change Sets" value={count(changesQ.data?.total)} icon={FileDiff} tone={changesQ.data?.total ? "watch" : "ready"} />
        <Metric label="IAM Findings" value={count(enterpriseQ.data?.summary.high) + count(enterpriseQ.data?.summary.medium)} icon={Users} tone={enterpriseQ.data?.status === "fail" ? "risk" : "watch"} />
      </section>

      <section className="rounded-lg border border-border bg-card">
        <div className="border-b border-border px-4 py-3 sm:px-5">
          <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Lifecycle</h2>
        </div>
        <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
          {stages.map((stage) => (
            <Link
              key={stage.title}
              to={stage.to}
              className="rounded-lg border border-border bg-background/60 p-4 transition hover:border-primary/40 hover:bg-accent/50"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <stage.icon size={17} className={iconTone(stage.status)} />
                    <p className="break-words text-sm font-semibold text-card-foreground">{stage.title}</p>
                  </div>
                  <p className="mt-3 text-2xl font-bold tabular-nums text-card-foreground">{nf.format(stage.primary)}</p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{stage.secondary}</p>
                </div>
                <Badge tone={stage.status}>{stage.status}</Badge>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <Panel title="Recent Gates" icon={ShieldCheck}>
          <ListEmpty show={!policiesQ.data?.items.length} text="No policy evaluations.">
            {policiesQ.data?.items.slice(0, 6).map((item) => (
              <Row key={item.id} title={item.scope_id || item.id} meta={item.generated_at || ""} badge={item.status} tone={item.status === "fail" ? "risk" : item.status === "warn" ? "watch" : "ready"} />
            ))}
          </ListEmpty>
        </Panel>

        <Panel title="Recent Evidence" icon={TestTube2}>
          <ListEmpty show={!testsQ.data?.items.length} text="No stored test runs.">
            {testsQ.data?.items.slice(0, 6).map((item) => (
              <Row key={item.id} title={item.title} meta={`${item.framework} - ${item.change_set_id ?? "no change set"}`} badge={item.status} tone={item.status === "failed" ? "risk" : item.status === "warning" ? "watch" : "ready"} />
            ))}
          </ListEmpty>
        </Panel>
      </section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel title="Enterprise Readiness" icon={Users}>
          <div className="grid grid-cols-3 gap-3">
            <Compact label="Providers" value={count(enterpriseQ.data?.summary.providers)} />
            <Compact label="Enabled" value={count(enterpriseQ.data?.summary.enabled_providers)} />
            <Compact label="Boundaries" value={count(enterpriseQ.data?.summary.boundaries)} />
          </div>
          <div className="mt-4 space-y-2">
            {enterpriseQ.data?.findings.slice(0, 5).map((finding, index) => (
              <Row
                key={`${String(finding.code)}-${index}`}
                title={String(finding.message ?? finding.code ?? "finding")}
                meta={String(finding.code ?? "")}
                badge={String(finding.severity ?? "info")}
                tone={String(finding.severity) === "high" ? "risk" : "watch"}
              />
            ))}
          </div>
        </Panel>

        <Panel title="Audit Trail" icon={Activity}>
          <ListEmpty show={!auditQ.data?.items.length} text="No audit events.">
            {auditQ.data?.items.slice(0, 6).map((item) => (
              <Row key={item.id} title={item.action} meta={`${item.category} - ${item.target ?? "no target"}`} badge={item.outcome} tone={item.outcome === "success" ? "ready" : "risk"} />
            ))}
          </ListEmpty>
        </Panel>
      </section>
    </div>
  )
}

function count(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0
}

function score(values: boolean[]): number {
  if (!values.length) return 0
  return Math.round((values.filter(Boolean).length / values.length) * 100)
}

function Metric({ label, value, icon: Icon, tone = "neutral" }: { label: string; value: number; icon: LucideIcon; tone?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="min-w-0 break-words text-xs font-semibold uppercase text-muted-foreground">{label}</p>
        <Icon size={17} className={iconTone(tone)} />
      </div>
      <p className="mt-3 break-words text-2xl font-bold tabular-nums text-card-foreground sm:text-3xl">{nf.format(value)}</p>
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
      <div className="space-y-3 p-4 sm:p-5">{children}</div>
    </section>
  )
}

function Row({ title, meta, badge, tone }: { title: string; meta: string; badge: string; tone: string }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="break-words text-sm font-semibold text-card-foreground">{title}</p>
          <p className="mt-1 break-words text-xs text-muted-foreground">{meta}</p>
        </div>
        <Badge tone={tone}>{badge}</Badge>
      </div>
    </div>
  )
}

function Compact({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-2 text-xl font-bold tabular-nums text-card-foreground">{nf.format(value)}</p>
    </div>
  )
}

function ListEmpty({ show, text, children }: { show: boolean; text: string; children: ReactNode }) {
  if (show) {
    return <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">{text}</p>
  }
  return <>{children}</>
}

function StatusBadge({ status, score }: { status: string; score: number }) {
  const Icon = status === "ready" ? CheckCircle2 : AlertTriangle
  return (
    <span className={cn("inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-semibold", statusClass(status))}>
      <Icon size={16} />
      {status} - {score}
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

function iconTone(tone: string): string {
  if (tone === "ready") return "text-emerald-500"
  if (tone === "risk") return "text-red-500"
  if (tone === "watch") return "text-amber-500"
  return "text-muted-foreground"
}

function statusClass(status: string): string {
  if (status === "ready") return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
  if (status === "risk") return "bg-red-500/10 text-red-600 dark:text-red-400"
  return "bg-amber-500/10 text-amber-600 dark:text-amber-400"
}

function badgeClass(tone: string): string {
  if (tone === "ready") return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
  if (tone === "risk") return "bg-red-500/10 text-red-600 dark:text-red-400"
  if (tone === "watch") return "bg-amber-500/10 text-amber-600 dark:text-amber-400"
  return "bg-muted text-muted-foreground"
}
