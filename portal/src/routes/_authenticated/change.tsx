import { useMemo, useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  FileCode,
  FileDiff,
  GitBranch,
  Loader2,
  Search,
  ShieldAlert,
  TestTube2,
  Zap,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  qualityApi,
  rentgenApi,
  type ChangeImpactItem,
  type ReviewDiffItem,
  type StandardsFinding,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/change")({
  component: ChangePage,
})

type Mode = "modules" | "diff"
type ReportItem = ChangeImpactItem | ReviewDiffItem

const sampleModule = "CommonModules/СводнаяТаблицаУХ/Ext/Module.bsl"
const nf = new Intl.NumberFormat("ru-RU")

function ChangePage() {
  const [mode, setMode] = useState<Mode>("modules")
  const [text, setText] = useState(sampleModule)

  const mutation = useMutation({
    mutationFn: async () => {
      if (mode === "modules") {
        const modules = text
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean)
        return rentgenApi.changeImpact(modules).then((r) => r.data)
      }
      return qualityApi.reviewDiff({ diff: text }).then((r) => r.data)
    },
  })

  const report = mutation.data
  const findingsTotal = useMemo(() => {
    if (!report) return 0
    return report.modules.reduce((sum, item) => sum + findingsOf(item).length, 0)
  }, [report])
  const unmeasuredTotal = useMemo(() => {
    if (!report) return 0
    return report.modules.filter((item) => !isImpactMeasured(item)).length
  }, [report])

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6 lg:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-2">
              <FileDiff size={22} className="text-primary" />
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              Change Impact
            </h1>
          </div>
          <p className="mt-2 text-muted-foreground">
            Правка → радиус поражения → риск по всей конфигурации.
          </p>
        </div>

        <div className="flex rounded-lg border border-border bg-card p-1">
          <ModeButton
            active={mode === "modules"}
            icon={FileCode}
            label="Модули"
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

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[420px_1fr]">
        <section className="rounded-xl border border-border bg-card">
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-base font-semibold text-card-foreground">
              {mode === "modules" ? "Изменённые модули" : "Unified diff"}
            </h2>
          </div>
          <div className="space-y-4 p-5">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              spellCheck={false}
              className="min-h-[320px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              placeholder={
                mode === "modules"
                  ? "CommonModules/...\nDocuments/.../Ext/ObjectModule.bsl"
                  : "diff --git a/CommonModules/... b/CommonModules/..."
              }
            />
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || !text.trim()}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {mutation.isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Search size={16} />
              )}
              Анализировать
            </button>
          </div>
        </section>

        <section className="min-h-[520px] rounded-xl border border-border bg-card">
          {!report && !mutation.isError && (
            <div className="flex h-full min-h-[520px] flex-col items-center justify-center gap-3 text-muted-foreground">
              <Activity size={42} className="opacity-30" />
              <p className="text-sm">Ожидаю входные данные.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex h-full min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">
                Не удалось выполнить анализ. Проверьте backend и формат входных данных.
              </p>
            </div>
          )}

          {report && (
            <div>
              <div className="grid grid-cols-2 gap-0 border-b border-border sm:grid-cols-5">
                <Metric label="Модулей" value={report.changed_modules.length} icon={FileCode} />
                <Metric label="Рёбер impact" value={report.total_impact_edges} icon={GitBranch} />
                <Metric label="Findings" value={findingsTotal} icon={ShieldAlert} />
                <Metric label="Не измерено" value={unmeasuredTotal} icon={AlertTriangle} />
                <Metric
                  label="Hotspots"
                  value={report.modules.reduce((sum, item) => sum + item.impacted_hotspots.length, 0)}
                  icon={AlertTriangle}
                />
              </div>

              <ul className="divide-y divide-border">
                {report.modules.map((item) => (
                  <ModuleReport key={item.module_path} item={item} />
                ))}
              </ul>

              {report.caveats.length > 0 && (
                <div className="border-t border-border bg-muted/30 px-5 py-4">
                  <ul className="space-y-1 text-xs text-muted-foreground">
                    {report.caveats.map((caveat) => (
                      <li key={caveat}>{caveat}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>
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

function Metric({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: number
  icon: LucideIcon
}) {
  return (
    <div className="border-b border-r border-border px-5 py-4 last:border-r-0 sm:border-b-0">
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

function ModuleReport({ item }: { item: ReportItem }) {
  const findings = findingsOf(item)
  const risk = item.quality?.risk ?? 0
  const impactMeasured = isImpactMeasured(item)
  const caveat = coverageCaveat(item)

  return (
    <li className="px-5 py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="truncate font-mono text-sm font-semibold text-card-foreground">
            {item.module_path}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {item.canonical.object_name || "не сопоставлен"} · {item.canonical.module_kind} ·{" "}
            {item.graph_modules.length} graph modules
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={risk >= 60 ? "danger" : risk >= 40 ? "warn" : "ok"}>
            риск {risk || "—"}
          </Badge>
          <Badge tone={!impactMeasured ? "danger" : item.impact_total > 0 ? "warn" : "muted"}>
            {impactMeasured ? `impact ${nf.format(item.impact_total)}` : "impact не измерен"}
          </Badge>
          <Badge tone={findings.length ? "danger" : "ok"}>
            findings {findings.length}
          </Badge>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel title="Blast radius" icon={GitBranch}>
          {!impactMeasured ? (
            <EmptyLine
              icon={AlertTriangle}
              text={caveat || "Граф не покрыл этот модуль; impact нельзя считать нулевым."}
            />
          ) : item.impacted_modules.length === 0 ? (
            <EmptyLine icon={CheckCircle2} text="Входящих зависимостей не найдено." />
          ) : (
            <ul className="space-y-2">
              {item.impacted_modules.slice(0, 6).map((m) => (
                <li key={m.module} className="flex items-center justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate font-mono text-card-foreground">
                    {m.module}
                  </span>
                  <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                    {m.edges}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Hotspots" icon={AlertTriangle}>
          {item.impacted_hotspots.length === 0 ? (
            <EmptyLine icon={CheckCircle2} text="Критичных пересечений нет." />
          ) : (
            <ul className="space-y-2">
              {item.impacted_hotspots.slice(0, 5).map((h) => (
                <li key={h.module_path} className="space-y-1">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="min-w-0 truncate font-mono text-card-foreground">
                      {h.module_path}
                    </span>
                    <span className="shrink-0 font-semibold tabular-nums text-orange-500">
                      {h.risk}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Risks" icon={Zap}>
          {riskLines(item, findings).length === 0 ? (
            <EmptyLine icon={TestTube2} text="Нет дополнительных сигналов." />
          ) : (
            <ul className="space-y-2">
              {riskLines(item, findings).map((line, index) => (
                <li key={`${line}-${index}`} className="text-sm text-card-foreground">
                  {line}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </li>
  )
}

function findingsOf(item: ReportItem): StandardsFinding[] {
  return "standards_findings" in item ? item.standards_findings : []
}

function isImpactMeasured(item: ReportItem): boolean {
  return !("impact_measured" in item) || item.impact_measured !== false
}

function coverageCaveat(item: ReportItem): string | undefined {
  if (!("coverage_caveat" in item)) return undefined
  return item.coverage_caveat || undefined
}

function riskLines(item: ReportItem, findings: StandardsFinding[]) {
  const lines = findings.map((finding) => finding.message)
  const caveat = coverageCaveat(item)
  if (!isImpactMeasured(item) && caveat) {
    lines.unshift(caveat)
  }
  if ("performance_risks" in item) {
    lines.push(...item.performance_risks.map((risk) => risk.detail))
  }
  return lines.slice(0, 5)
}

function Panel({
  title,
  icon: Icon,
  children,
}: {
  title: string
  icon: LucideIcon
  children: ReactNode
}) {
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

function EmptyLine({
  icon: Icon,
  text,
}: {
  icon: LucideIcon
  text: string
}) {
  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Icon size={15} />
      {text}
    </p>
  )
}
