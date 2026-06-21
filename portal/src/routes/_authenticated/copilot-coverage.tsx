import { useMemo, useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import {
  AlertTriangle,
  Boxes,
  CheckCircle2,
  CircleDot,
  Compass,
  Crosshair,
  GitBranch,
  Loader2,
  Radar,
  ShieldCheck,
  Sparkles,
  UsersRound,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  copilotCoverageApi,
  type CoverageItem,
  type CoverageResponse,
  type CoverageStatus,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/copilot-coverage")({
  component: CopilotCoveragePage,
})

const nf = new Intl.NumberFormat("ru-RU")

const statusMeta: Record<
  CoverageStatus,
  { label: string; icon: LucideIcon; badge: string; bar: string }
> = {
  done: {
    label: "Готово",
    icon: CheckCircle2,
    badge: "bg-emerald-500/10 text-emerald-600 ring-emerald-500/25",
    bar: "bg-emerald-500",
  },
  partial: {
    label: "Частично",
    icon: CircleDot,
    badge: "bg-amber-500/10 text-amber-600 ring-amber-500/25",
    bar: "bg-amber-500",
  },
  planned: {
    label: "План",
    icon: AlertTriangle,
    badge: "bg-slate-500/10 text-slate-600 ring-slate-500/25",
    bar: "bg-slate-400",
  },
}

const stageIcons: Record<string, LucideIcon> = {
  discover: Radar,
  requirements: UsersRound,
  architecture: GitBranch,
  coding: Sparkles,
  ui_forms: Boxes,
  data: Boxes,
  review: ShieldCheck,
  performance: Crosshair,
  testing: CheckCircle2,
  delivery: Compass,
  operations: Radar,
  governance: ShieldCheck,
}

function CopilotCoveragePage() {
  const [stageFilter, setStageFilter] = useState<string>("all")
  const [statusFilter, setStatusFilter] = useState<CoverageStatus | "all">("all")

  const coverageQ = useQuery({
    queryKey: ["copilot-coverage"],
    queryFn: () => copilotCoverageApi.get().then((r) => r.data),
  })

  const data = coverageQ.data
  const items = useMemo(() => {
    if (!data) return []
    return data.items.filter((item) => {
      const stageOk = stageFilter === "all" || item.stage === stageFilter
      const statusOk = statusFilter === "all" || item.status === statusFilter
      return stageOk && statusOk
    })
  }, [data, stageFilter, statusFilter])

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <Header data={data} isLoading={coverageQ.isLoading} />

      {coverageQ.isLoading && (
        <div className="flex min-h-[420px] items-center justify-center rounded-lg border border-border bg-card">
          <Loader2 size={36} className="animate-spin text-primary" />
        </div>
      )}

      {coverageQ.isError && (
        <div className="flex min-h-[420px] flex-col items-center justify-center gap-3 rounded-lg border border-border bg-card text-destructive">
          <AlertTriangle size={36} />
          <p className="text-sm">Карта покрытия недоступна.</p>
        </div>
      )}

      {data && (
        <>
          <SummaryGrid data={data} />

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
            <section className="min-w-0 space-y-4">
              <StageMatrix
                data={data}
                stageFilter={stageFilter}
                onStageFilter={setStageFilter}
              />
              <Filters
                statusFilter={statusFilter}
                onStatusFilter={setStatusFilter}
                shown={items.length}
                total={data.items.length}
              />
              <CoverageTable data={data} items={items} />
            </section>

            <aside className="min-w-0 space-y-4">
              <NextActions data={data} />
              <CompetitorPanel data={data} />
              <RuntimePanel data={data} />
            </aside>
          </div>
        </>
      )}
    </div>
  )
}

function Header({
  data,
  isLoading,
}: {
  data?: CoverageResponse
  isLoading: boolean
}) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <div className="flex items-center gap-2.5">
          <div className="rounded-lg bg-primary/10 p-2">
            <Compass size={22} className="text-primary" />
          </div>
          <h1 className="break-words text-2xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl">
            Rentgen Subscription Escape Map
          </h1>
        </div>
        <p className="mt-2 max-w-3xl text-muted-foreground">
          {data?.positioning ?? "Карта, где Rentgen заменяет вечную AI-подписку локальными evidence, gates and buyer-ready artifacts."}
        </p>
      </div>
      <div className="rounded-lg border border-border bg-card px-4 py-3">
        <p className="text-xs font-medium text-muted-foreground">Local asset coverage</p>
        <p className="mt-1 text-2xl font-bold tabular-nums text-card-foreground">
          {isLoading ? "—" : `${data?.summary.coverage_score ?? 0}%`}
        </p>
      </div>
    </div>
  )
}

function SummaryGrid({ data }: { data: CoverageResponse }) {
  const runtimeReady = Boolean(data.runtime.rentgen_store)
  const metrics = [
    {
      label: "Всего зон",
      value: data.summary.total_items,
      icon: Boxes,
      tone: "text-blue-600",
      bg: "bg-blue-500/10",
    },
    {
      label: "Готово",
      value: data.summary.done,
      icon: CheckCircle2,
      tone: "text-emerald-600",
      bg: "bg-emerald-500/10",
    },
    {
      label: "P0 покрытие",
      value: `${data.summary.p0_coverage_score}%`,
      icon: Crosshair,
      tone: "text-rose-600",
      bg: "bg-rose-500/10",
    },
    {
      label: "Граф Рентгена",
      value: runtimeReady ? "online" : "offline",
      icon: GitBranch,
      tone: runtimeReady ? "text-emerald-600" : "text-amber-600",
      bg: runtimeReady ? "bg-emerald-500/10" : "bg-amber-500/10",
    },
  ]

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <div key={metric.label} className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-start justify-between gap-3">
            <p className="text-xs font-medium text-muted-foreground">{metric.label}</p>
            <div className={cn("rounded-lg p-2", metric.bg)}>
              <metric.icon size={17} className={metric.tone} />
            </div>
          </div>
          <p className="mt-3 break-words text-xl font-bold tabular-nums text-card-foreground sm:text-2xl">
            {typeof metric.value === "number" ? nf.format(metric.value) : metric.value}
          </p>
        </div>
      ))}
    </div>
  )
}

function StageMatrix({
  data,
  stageFilter,
  onStageFilter,
}: {
  data: CoverageResponse
  stageFilter: string
  onStageFilter: (stage: string) => void
}) {
  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-base font-semibold text-card-foreground">Покрытие SDLC</h2>
      </div>
      <div className="grid grid-cols-1 gap-px bg-border sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
        {data.stages.map((stage) => {
          const count = data.summary.by_stage[stage.id] ?? 0
          const stageItems = data.items.filter((item) => item.stage === stage.id)
          const done = stageItems.filter((item) => item.status === "done").length
          const partial = stageItems.filter((item) => item.status === "partial").length
          const Icon = stageIcons[stage.id] ?? Boxes
          const selected = stageFilter === stage.id
          return (
            <button
              key={stage.id}
              onClick={() => onStageFilter(selected ? "all" : stage.id)}
              className={cn(
                "min-h-[122px] bg-card p-4 text-left transition hover:bg-muted/50",
                selected && "bg-primary/5 ring-1 ring-inset ring-primary",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <Icon size={18} className="text-primary" />
                <span className="text-xs font-semibold text-muted-foreground">
                  {count} зон
                </span>
              </div>
              <p className="mt-3 text-sm font-semibold text-card-foreground">{stage.title}</p>
              <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                {stage.description}
              </p>
              <div className="mt-3 flex h-1.5 overflow-hidden rounded-full bg-muted">
                <span
                  className="bg-emerald-500"
                  style={{ width: `${count ? (done / count) * 100 : 0}%` }}
                />
                <span
                  className="bg-amber-500"
                  style={{ width: `${count ? (partial / count) * 100 : 0}%` }}
                />
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}

function Filters({
  statusFilter,
  onStatusFilter,
  shown,
  total,
}: {
  statusFilter: CoverageStatus | "all"
  onStatusFilter: (status: CoverageStatus | "all") => void
  shown: number
  total: number
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-muted-foreground">
        Показано {shown} из {total}
      </p>
      <div className="flex flex-wrap gap-2">
        <FilterButton active={statusFilter === "all"} onClick={() => onStatusFilter("all")}>
          Все
        </FilterButton>
        {(["done", "partial", "planned"] as CoverageStatus[]).map((status) => (
          <FilterButton
            key={status}
            active={statusFilter === status}
            onClick={() => onStatusFilter(status)}
          >
            {statusMeta[status].label}
          </FilterButton>
        ))}
      </div>
    </div>
  )
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-md px-3 py-1.5 text-sm font-medium transition",
        active
          ? "bg-primary text-primary-foreground"
          : "bg-muted text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  )
}

function CoverageTable({
  data,
  items,
}: {
  data: CoverageResponse
  items: CoverageItem[]
}) {
  const stageTitle = (id: string) => data.stages.find((stage) => stage.id === id)?.title ?? id
  const personaTitle = (id: string) => data.personas.find((persona) => persona.id === id)?.title ?? id

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="hidden grid-cols-[120px_170px_96px_minmax(0,1fr)] border-b border-border bg-muted/40 px-4 py-2 text-xs font-semibold uppercase text-muted-foreground xl:grid">
        <span>Этап</span>
        <span>Зона</span>
        <span>Статус</span>
        <span>Enterprise delta</span>
      </div>
      <ul className="divide-y divide-border">
        {items.map((item) => {
          const meta = statusMeta[item.status]
          const StatusIcon = meta.icon
          return (
            <li
              key={item.id}
              className="grid gap-3 px-4 py-4 xl:grid-cols-[120px_170px_96px_minmax(0,1fr)]"
            >
              <div className="min-w-0">
                <p className="text-sm font-semibold text-card-foreground">
                  {stageTitle(item.stage)}
                </p>
                <p className="mt-1 text-xs font-medium text-muted-foreground">
                  {item.priority} · {item.moat}
                </p>
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-card-foreground">{item.title}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {item.personas.map(personaTitle).join(", ")}
                </p>
              </div>
              <div className="min-w-0">
                <span
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-semibold ring-1",
                    meta.badge,
                  )}
                >
                  <StatusIcon size={13} />
                  {meta.label}
                </span>
              </div>
              <div className="min-w-0 space-y-3">
                <DeltaBlock title="1С:Напарник" text={item.naparnik} />
                <DeltaBlock title="Rentgen сейчас" text={item.ours} />
                <DeltaBlock title="Local asset edge" text={item.target} strong />
                <div className="lg:col-span-3">
                  <p className="text-xs font-semibold uppercase text-muted-foreground">
                    Следующая сборка
                  </p>
                  <p className="mt-1 text-sm text-card-foreground">{item.next_build}</p>
                  <p className="mt-2 truncate font-mono text-xs text-muted-foreground">
                    {item.implementation_refs.join(" · ")}
                  </p>
                </div>
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function DeltaBlock({
  title,
  text,
  strong,
}: {
  title: string
  text: string
  strong?: boolean
}) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-muted-foreground">{title}</p>
      <p className={cn("mt-1 break-words text-sm", strong ? "text-primary" : "text-card-foreground")}>
        {text}
      </p>
    </div>
  )
}

function NextActions({ data }: { data: CoverageResponse }) {
  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-base font-semibold text-card-foreground">P0/P1 build queue</h2>
      </div>
      <ol className="divide-y divide-border">
        {data.next_actions.map((action, index) => (
          <li key={action.id} className="grid grid-cols-[28px_1fr] gap-3 px-4 py-3">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
              {index + 1}
            </span>
            <div>
              <p className="text-sm font-semibold text-card-foreground">{action.title}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {action.priority} · {action.stage}
              </p>
              <p className="mt-2 text-sm text-card-foreground">{action.next_build}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

function CompetitorPanel({ data }: { data: CoverageResponse }) {
  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-base font-semibold text-card-foreground">
          Контур {data.competitor.name}
        </h2>
      </div>
      <div className="space-y-4 p-4">
        <CompactList title="Сильные зоны" items={data.competitor.observed_strengths} tone="ok" />
        <CompactList title="Окна первенства" items={data.competitor.observed_gaps} tone="warn" />
      </div>
    </section>
  )
}

function CompactList({
  title,
  items,
  tone,
}: {
  title: string
  items: string[]
  tone: "ok" | "warn"
}) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-muted-foreground">{title}</p>
      <ul className="mt-2 space-y-2">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-sm text-card-foreground">
            <span
              className={cn(
                "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                tone === "ok" ? "bg-emerald-500" : "bg-amber-500",
              )}
            />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function RuntimePanel({ data }: { data: CoverageResponse }) {
  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-base font-semibold text-card-foreground">Runtime signals</h2>
      </div>
      <div className="grid grid-cols-1 gap-px bg-border sm:grid-cols-2">
        {Object.entries(data.runtime).map(([key, value]) => (
          <div key={key} className="bg-card p-3">
            <p className="truncate text-xs font-medium text-muted-foreground">{key}</p>
            <p className="mt-1 truncate text-sm font-semibold text-card-foreground">
              {typeof value === "number" ? nf.format(value) : String(value)}
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}
