import { useMemo, useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  FileCode,
  FileDiff,
  GitBranch,
  Layers3,
  Loader2,
  Network,
  Radar,
  Route as RouteIcon,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  architectureApi,
  type ArchitectureFinding,
  type ArchitectureReviewRequest,
  type ArchitectureReviewResponse,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/architecture")({
  component: ArchitecturePage,
})

type Mode = "top" | "modules" | "diff"

const sampleModule = "CommonModules/СводнаяТаблицаУХ/Ext/Module.bsl"
const nf = new Intl.NumberFormat("ru-RU")

function ArchitecturePage() {
  const [mode, setMode] = useState<Mode>("top")
  const [text, setText] = useState(sampleModule)
  const [limit, setLimit] = useState(5000)
  const [minWeight, setMinWeight] = useState(1)
  const [denseThreshold, setDenseThreshold] = useState(250)
  const [includeCycles, setIncludeCycles] = useState(true)

  const mutation = useMutation({
    mutationFn: async () => {
      const body: ArchitectureReviewRequest = {
        limit,
        min_weight: minWeight,
        dense_threshold: denseThreshold,
        include_cycles: includeCycles,
      }
      if (mode === "modules") {
        body.changed_modules = text
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean)
      } else if (mode === "diff") {
        body.diff = text
      }
      return architectureApi.review(body).then((r) => r.data)
    },
  })

  const report = mutation.data

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6 lg:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-2">
              <Network size={22} className="text-primary" />
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              Architecture Cockpit
            </h1>
          </div>
          <p className="mt-2 text-muted-foreground">
            Module graph boundaries, layer leaks, cycles and dense coupling.
          </p>
        </div>

        <div className="flex rounded-lg border border-border bg-card p-1">
          <ModeButton active={mode === "top"} icon={Radar} label="Top" onClick={() => setMode("top")} />
          <ModeButton active={mode === "modules"} icon={FileCode} label="Modules" onClick={() => setMode("modules")} />
          <ModeButton active={mode === "diff"} icon={GitBranch} label="Diff" onClick={() => setMode("diff")} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-xl border border-border bg-card">
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-base font-semibold text-card-foreground">
              Review Scope
            </h2>
          </div>
          <div className="space-y-4 p-5">
            {mode !== "top" && (
              <textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                spellCheck={false}
                className="min-h-[260px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
                placeholder={
                  mode === "modules"
                    ? "CommonModules/...\nDocuments/.../Ext/ObjectModule.bsl"
                    : "diff --git a/CommonModules/... b/CommonModules/..."
                }
              />
            )}

            {mode === "top" && (
              <div className="rounded-lg border border-border bg-background/50 p-4 text-sm text-muted-foreground">
                Reviews the strongest module-level dependencies across the current Rentgen store.
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <NumberField label="Edges" value={limit} min={100} max={50000} onChange={setLimit} />
              <NumberField label="Min weight" value={minWeight} min={1} max={10000} onChange={setMinWeight} />
              <NumberField label="Dense" value={denseThreshold} min={10} max={10000} onChange={setDenseThreshold} />
              <ToggleBox checked={includeCycles} label="Cycles" onChange={setIncludeCycles} />
            </div>

            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || (mode !== "top" && !text.trim())}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {mutation.isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Network size={16} />
              )}
              Review
            </button>
          </div>
        </section>

        <section className="min-w-0 min-h-[620px] rounded-xl border border-border bg-card">
          {!report && !mutation.isError && (
            <div className="flex h-full min-h-[620px] flex-col items-center justify-center gap-3 text-muted-foreground">
              <Network size={42} className="opacity-30" />
              <p className="text-sm">Waiting for architecture review.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex h-full min-h-[620px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">
                Architecture review failed. Check backend availability and input format.
              </p>
            </div>
          )}

          {report && <ArchitectureReport report={report} />}
        </section>
      </div>
    </div>
  )
}

function ArchitectureReport({ report }: { report: ArchitectureReviewResponse }) {
  const topFindings = useMemo(() => report.findings.slice(0, 30), [report])
  const statusTone = report.summary.by_severity.high ? "danger" : report.summary.by_severity.medium ? "warn" : "ok"

  return (
    <div>
      <div className="flex flex-col gap-4 border-b border-border p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Layers3 size={24} className={statusTone === "danger" ? "text-red-500" : statusTone === "warn" ? "text-amber-500" : "text-emerald-500"} />
            <h2 className="truncate text-xl font-bold text-card-foreground">
              Boundary Review
            </h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {report.scope.mode} · {report.scope.focus_graph_modules.length || "whole graph"} focus modules
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={statusTone}>score {report.summary.score}</Badge>
          <Badge tone="muted">{nf.format(report.summary.edges_reviewed)} edges</Badge>
          <Badge tone={report.summary.findings ? "warn" : "ok"}>{nf.format(report.summary.findings)} findings</Badge>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-4">
        <Metric label="High" value={report.summary.by_severity.high ?? 0} icon={AlertTriangle} />
        <Metric label="Medium" value={report.summary.by_severity.medium ?? 0} icon={RouteIcon} />
        <Metric label="Cycles" value={report.summary.by_rule.cycle ?? 0} icon={GitBranch} />
        <Metric label="Dense" value={report.summary.by_rule.dense_coupling ?? 0} icon={Network} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Findings" icon={AlertTriangle}>
            {topFindings.length === 0 ? (
              <EmptyLine icon={CheckCircle2} text="No boundary violations in reviewed scope." />
            ) : (
              <FindingList findings={topFindings} />
            )}
          </Panel>

          <Panel title="Top Edges" icon={FileDiff}>
            <ul className="space-y-2">
              {report.top_edges.slice(0, 12).map((edge) => (
                <li key={`${edge.src}-${edge.dst}`} className="rounded-lg border border-border bg-background/50 p-3">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <p className="min-w-0 break-all font-mono text-sm font-semibold text-card-foreground">
                      {edge.src}
                      {" -> "}
                      {edge.dst}
                    </p>
                    <Badge tone="muted">w {nf.format(edge.weight)}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {edge.src_layer}
                    {" -> "}
                    {edge.dst_layer}
                  </p>
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        <div className="min-w-0 space-y-5">
          <Panel title="Rules" icon={Layers3}>
            <KeyValueList values={report.summary.by_rule} />
          </Panel>

          <Panel title="Layer Edges" icon={RouteIcon}>
            <KeyValueList values={report.summary.layer_edges} />
          </Panel>

          <Panel title="Hubs" icon={Network}>
            <ul className="space-y-2">
              {report.hubs.slice(0, 8).map((hub) => (
                <li key={hub.module} className="text-xs text-muted-foreground">
                  <p className="truncate font-mono text-card-foreground">{hub.module}</p>
                  <p>
                    {hub.layer} · {nf.format(hub.out_weight)} weight · {hub.edges} edges
                  </p>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  )
}

function FindingList({ findings }: { findings: ArchitectureFinding[] }) {
  return (
    <ul className="space-y-3">
      {findings.map((finding, index) => (
        <li key={`${finding.rule}-${finding.src}-${finding.dst}-${index}`} className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={finding.severity === "high" ? "danger" : finding.severity === "medium" ? "warn" : "muted"}>
              {finding.rule}
            </Badge>
            <span className="text-sm font-medium text-card-foreground">{finding.message}</span>
          </div>
          <p className="break-all font-mono text-xs text-muted-foreground">
            {finding.src}
            {" -> "}
            {finding.dst}
            {" · w "}
            {nf.format(finding.weight)}
          </p>
          <p className="text-xs text-muted-foreground">{finding.recommendation}</p>
        </li>
      ))}
    </ul>
  )
}

function KeyValueList({ values }: { values: Record<string, number> }) {
  const entries = Object.entries(values).slice(0, 10)
  if (entries.length === 0) return <EmptyLine icon={CheckCircle2} text="No items." />
  return (
    <ul className="space-y-2">
      {entries.map(([key, value]) => (
        <li key={key} className="flex items-center justify-between gap-3 text-xs">
          <span className="min-w-0 truncate text-muted-foreground">{key}</span>
          <span className="shrink-0 font-semibold tabular-nums text-card-foreground">{nf.format(value)}</span>
        </li>
      ))}
    </ul>
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
      <p className="mt-2 text-2xl font-bold tabular-nums text-card-foreground">
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
