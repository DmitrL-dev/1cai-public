import { useMemo, useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  FileCode,
  FileDiff,
  GitBranch,
  Loader2,
  Rocket,
  ShieldAlert,
  TestTube2,
  Users,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  releaseReadinessApi,
  type ReleaseReadinessRequest,
  type ReleaseReadinessResponse,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/release-readiness")({
  component: ReleaseReadinessPage,
})

type Mode = "modules" | "diff"

const sampleModule = "CommonModules/СводнаяТаблицаУХ/Ext/Module.bsl"
const nf = new Intl.NumberFormat("ru-RU")

function ReleaseReadinessPage() {
  const [mode, setMode] = useState<Mode>("modules")
  const [text, setText] = useState(sampleModule)
  const [releaseName, setReleaseName] = useState("ERP/UH candidate")
  const [includeForms, setIncludeForms] = useState(true)
  const [includeSecurity, setIncludeSecurity] = useState(false)
  const [riskThreshold, setRiskThreshold] = useState(70)
  const [impactThreshold, setImpactThreshold] = useState(300)

  const mutation = useMutation({
    mutationFn: async () => {
      const body: ReleaseReadinessRequest = {
        release_name: releaseName.trim() || undefined,
        include_forms: includeForms,
        include_security: includeSecurity,
        risk_threshold: riskThreshold,
        impact_threshold: impactThreshold,
      }
      if (mode === "modules") {
        body.changed_modules = text
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean)
      } else {
        body.diff = text
      }
      return releaseReadinessApi.analyze(body).then((r) => r.data)
    },
  })

  const report = mutation.data

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6 lg:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-2">
              <Rocket size={22} className="text-primary" />
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              Release Readiness
            </h1>
          </div>
          <p className="mt-2 text-muted-foreground">
            {"Diff/modules -> gate decision, impact, metadata, forms, tests and actions."}
          </p>
        </div>

        <div className="flex rounded-lg border border-border bg-card p-1">
          <ModeButton
            active={mode === "modules"}
            icon={FileCode}
            label="Modules"
            onClick={() => setMode("modules")}
          />
          <ModeButton
            active={mode === "diff"}
            icon={GitBranch}
            label="Diff"
            onClick={() => setMode("diff")}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-xl border border-border bg-card">
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-base font-semibold text-card-foreground">
              Release Candidate
            </h2>
          </div>
          <div className="space-y-4 p-5">
            <label className="block space-y-1.5">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Name
              </span>
              <input
                value={releaseName}
                onChange={(event) => setReleaseName(event.target.value)}
                className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary"
              />
            </label>

            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              spellCheck={false}
              className="min-h-[280px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              placeholder={
                mode === "modules"
                  ? "CommonModules/...\nDocuments/.../Ext/ObjectModule.bsl"
                  : "diff --git a/CommonModules/... b/CommonModules/..."
              }
            />

            <div className="grid grid-cols-2 gap-3">
              <NumberField
                label="Risk"
                value={riskThreshold}
                min={0}
                max={100}
                onChange={setRiskThreshold}
              />
              <NumberField
                label="Impact"
                value={impactThreshold}
                min={0}
                max={5000}
                onChange={setImpactThreshold}
              />
            </div>

            <div className="space-y-2 rounded-lg border border-border bg-background/50 p-3">
              <ToggleLine
                checked={includeForms}
                label="Forms review"
                onChange={setIncludeForms}
              />
              <ToggleLine
                checked={includeSecurity}
                label="Security rights review"
                onChange={setIncludeSecurity}
              />
            </div>

            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || !text.trim()}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {mutation.isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Rocket size={16} />
              )}
              Analyze
            </button>
          </div>
        </section>

        <section className="min-w-0 min-h-[620px] rounded-xl border border-border bg-card">
          {!report && !mutation.isError && (
            <div className="flex h-full min-h-[620px] flex-col items-center justify-center gap-3 text-muted-foreground">
              <Rocket size={42} className="opacity-30" />
              <p className="text-sm">Waiting for a release candidate.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex h-full min-h-[620px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">
                Release analysis failed. Check backend availability and input format.
              </p>
            </div>
          )}

          {report && <ReleaseReport report={report} />}
        </section>
      </div>
    </div>
  )
}

function ReleaseReport({ report }: { report: ReleaseReadinessResponse }) {
  const status = report.decision.status
  const StatusIcon = status === "pass" ? CheckCircle2 : status === "warn" ? AlertTriangle : XCircle
  const actions = useMemo(() => report.recommended_actions.slice(0, 12), [report])

  return (
    <div>
      <div className="flex flex-col gap-4 border-b border-border p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <StatusIcon className={statusTone(status)} size={24} />
            <h2 className="truncate text-xl font-bold text-card-foreground">
              {report.release_name}
            </h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {new Date(report.generated_at).toLocaleString("ru-RU")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={status === "fail" ? "danger" : status === "warn" ? "warn" : "ok"}>
            {status.toUpperCase()}
          </Badge>
          <Badge tone="muted">score {report.decision.score}</Badge>
          <Badge tone={report.gate.status === "fail" ? "danger" : report.gate.status === "warn" ? "warn" : "ok"}>
            gate {report.gate.status}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-5">
        <Metric label="Measured Impact" value={report.summary.total_impact_edges} icon={GitBranch} />
        <Metric label="Unknown Impact" value={report.summary.unmeasured_impact_modules ?? report.change_plan.unmeasured_modules.length} icon={AlertTriangle} />
        <Metric label="Violations" value={report.summary.gate_violations} icon={ShieldAlert} />
        <Metric label="Tests" value={report.summary.test_actions} icon={TestTube2} />
        <Metric label="Metadata" value={report.summary.metadata_objects} icon={ClipboardList} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-5">
          {(report.decision.blockers.length > 0 || report.decision.warnings.length > 0) && (
            <Panel title="Decision" icon={AlertTriangle}>
              <FindingLines items={[...report.decision.blockers, ...report.decision.warnings]} />
            </Panel>
          )}

          <Panel title="Actions" icon={ClipboardList}>
            {actions.length === 0 ? (
              <EmptyLine icon={CheckCircle2} text="No blocking actions." />
            ) : (
              <ul className="space-y-3">
                {actions.map((action, index) => (
                  <li key={`${action.kind}-${action.target}-${index}`} className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={action.severity === "high" ? "danger" : action.severity === "medium" ? "warn" : "muted"}>
                        {action.owner}
                      </Badge>
                      <span className="text-sm font-medium text-card-foreground">
                        {action.title}
                      </span>
                    </div>
                    {action.target && (
                      <p className="truncate font-mono text-xs text-muted-foreground">
                        {action.target}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Changed Modules" icon={FileDiff}>
            <ul className="space-y-2">
              {report.change_plan.modules.map((item) => (
                <li key={item.module_path} className="rounded-lg border border-border bg-background/50 p-3">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <p className="min-w-0 truncate font-mono text-sm font-semibold text-card-foreground">
                      {item.module_path}
                    </p>
                    <div className="flex shrink-0 gap-2">
                      <Badge tone={(item.quality?.risk ?? 0) >= 70 ? "danger" : "muted"}>
                        risk {item.quality?.risk ?? 0}
                      </Badge>
                      <Badge tone={item.impact_measured === false ? "danger" : item.impact_total >= 300 ? "warn" : "muted"}>
                        {item.impact_measured === false ? "impact unknown" : `impact ${nf.format(item.impact_total)}`}
                      </Badge>
                    </div>
                  </div>
                  {item.impact_measured === false && (
                    <p className="mt-2 break-words text-xs text-amber-600 dark:text-amber-400">
                      {item.coverage_caveat ?? "Impact is not measured; do not read impact_total=0 as safe."}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        <div className="min-w-0 space-y-5">
          <Panel title="Personas" icon={Users}>
            <PersonaList personas={report.personas} />
          </Panel>

          <Panel title="Test Plan" icon={TestTube2}>
            <div className="grid grid-cols-3 gap-2 text-center">
              <MiniStat label="total" value={report.tests.total} />
              <MiniStat label="high" value={report.tests.high_priority} />
              <MiniStat label="mapped" value={report.tests.mapped} />
            </div>
            <ul className="mt-3 space-y-2">
              {report.tests.items.slice(0, 5).map((item, index) => (
                <li key={`${item.selector}-${index}`} className="break-all text-xs text-muted-foreground">
                  <span className="font-mono text-card-foreground">{String(item.selector ?? "selector")}</span>
                  {" · "}
                  {String(item.status ?? "recommended")}
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Markdown" icon={FileCode}>
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {report.markdown}
            </pre>
          </Panel>
        </div>
      </div>
    </div>
  )
}

function ModeButton({
  active,
  icon: Icon,
  label,
  onClick,
}: {
  active: boolean
  icon: LucideIcon
  label: string
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition",
        active
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <Icon size={15} />
      {label}
    </button>
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

function ToggleLine({
  checked,
  label,
  onChange,
}: {
  checked: boolean
  label: string
  onChange: (checked: boolean) => void
}) {
  return (
    <label className="flex items-center justify-between gap-3 text-sm text-card-foreground">
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
      <p className="mt-2 text-2xl font-bold tabular-nums text-card-foreground">
        {nf.format(value)}
      </p>
    </div>
  )
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-background/50 p-2">
      <p className="text-lg font-bold tabular-nums text-card-foreground">{nf.format(value)}</p>
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
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

function FindingLines({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2">
      {items.map((item, index) => (
        <li key={`${item}-${index}`} className="text-sm text-card-foreground">
          {item}
        </li>
      ))}
    </ul>
  )
}

function PersonaList({ personas }: { personas: Record<string, Record<string, unknown>> }) {
  return (
    <ul className="space-y-3">
      {Object.entries(personas).map(([name, values]) => (
        <li key={name} className="min-w-0 space-y-1">
          <p className="text-sm font-semibold capitalize text-card-foreground">{name}</p>
          <p className="break-words text-xs text-muted-foreground">
            {Object.entries(values)
              .slice(0, 4)
              .map(([key, value]) => `${key}: ${formatPersonaValue(value)}`)
              .join(" · ")}
          </p>
        </li>
      ))}
    </ul>
  )
}

function formatPersonaValue(value: unknown) {
  if (Array.isArray(value)) return `${value.length} items`
  if (value && typeof value === "object") return `${Object.keys(value).length} fields`
  return String(value)
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

function statusTone(status: ReleaseReadinessResponse["decision"]["status"]) {
  if (status === "pass") return "text-emerald-500"
  if (status === "warn") return "text-amber-500"
  return "text-red-500"
}
