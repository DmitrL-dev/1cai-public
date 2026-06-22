import { useState, useMemo } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import {
  Activity,
  Boxes,
  GitFork,
  ShieldCheck,
  AlertTriangle,
  ChevronRight,
  Skull,
  Info,
  Layers,
  Loader2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  qualityApi,
  rentgenApi,
  type Hotspot,
  type HotspotReason,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/quality")({
  component: QualityPage,
})

/* ── Helpers ──────────────────────────────────────────────── */

const nf = new Intl.NumberFormat("ru-RU")
const fmt = (n: number | undefined | null) => (n == null ? "—" : nf.format(n))

/** Risk badge color buckets: red ≥80, orange 60-79, yellow 40-59, green <40 */
function riskTone(risk: number) {
  if (risk >= 80)
    return {
      badge: "bg-red-500/15 text-red-600 dark:text-red-400 ring-red-500/30",
      bar: "bg-red-500",
      dot: "bg-red-500",
    }
  if (risk >= 60)
    return {
      badge: "bg-orange-500/15 text-orange-600 dark:text-orange-400 ring-orange-500/30",
      bar: "bg-orange-500",
      dot: "bg-orange-500",
    }
  if (risk >= 40)
    return {
      badge: "bg-amber-500/15 text-amber-600 dark:text-amber-400 ring-amber-500/30",
      bar: "bg-amber-500",
      dot: "bg-amber-500",
    }
  return {
    badge: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 ring-emerald-500/30",
    bar: "bg-emerald-500",
    dot: "bg-emerald-500",
  }
}

/** Maintainability is higher=better — color the domain bars accordingly. */
function maintTone(score: number) {
  if (score >= 60) return "bg-emerald-500"
  if (score >= 50) return "bg-amber-500"
  if (score >= 40) return "bg-orange-500"
  return "bg-red-500"
}

/** Truncate a long path in the middle, keeping head + tail legible. */
function middleTruncate(path: string, max = 56) {
  if (path.length <= max) return path
  const keep = Math.floor((max - 1) / 2)
  return `${path.slice(0, keep)}…${path.slice(path.length - keep)}`
}

/**
 * Derive the source/config label from the store meta instead of hardcoding.
 * The build meta carries only counts + artifact paths (no friendly config name
 * today), so we use a name-like meta key if one ever appears, else a neutral
 * fallback — never a fabricated product name.
 */
function sourceLabel(meta: Record<string, string> | undefined) {
  const name =
    meta?.config_name ?? meta?.config ?? meta?.source_name ?? meta?.source
  return name && name.trim() ? name.trim() : "конфигурация"
}

/* ── Page ─────────────────────────────────────────────────── */

function QualityPage() {
  const [domain, setDomain] = useState<string>("")
  const [minFanIn, setMinFanIn] = useState(false)

  const statsQ = useQuery({
    queryKey: ["quality", "stats"],
    queryFn: () => qualityApi.stats().then((r) => r.data),
  })
  const summaryQ = useQuery({
    queryKey: ["quality", "summary"],
    queryFn: () => qualityApi.summary().then((r) => r.data),
  })
  const hotspotsQ = useQuery({
    queryKey: ["quality", "hotspots", domain, minFanIn],
    queryFn: () =>
      qualityApi
        .hotspots({
          limit: 30,
          domain: domain || undefined,
          min_fan_in: minFanIn ? 10 : undefined,
        })
        .then((r) => r.data),
  })
  const deadQ = useQuery({
    queryKey: ["rentgen", "dead-code", "common"],
    queryFn: () =>
      rentgenApi.deadCode({ scope: "common", limit: 15 }).then((r) => r.data),
  })

  const stats = statsQ.data
  const summary = summaryQ.data

  // The store endpoints answer 503 when the graph hasn't been built. Treat a
  // settled error on the core stats/summary queries as "store missing" so we
  // can show a banner instead of letting widgets render blank.
  const storeMissing =
    (statsQ.isError && !statsQ.isLoading) ||
    (summaryQ.isError && !summaryQ.isLoading)

  const kpis = useMemo(
    () => [
      {
        label: "Модулей оценено",
        value: stats?.quality_modules,
        icon: Boxes,
        accent: "text-blue-500 dark:text-blue-400",
        bg: "bg-blue-500/10 dark:bg-blue-500/15",
      },
      {
        label: "Подпрограмм",
        value: stats?.subroutines,
        icon: Layers,
        accent: "text-violet-500 dark:text-violet-400",
        bg: "bg-violet-500/10 dark:bg-violet-500/15",
      },
      {
        label: "Рёбер графа вызовов",
        value: stats?.call_edges,
        icon: GitFork,
        accent: "text-cyan-500 dark:text-cyan-400",
        bg: "bg-cyan-500/10 dark:bg-cyan-500/15",
      },
      {
        label: "Средняя поддерживаемость",
        value: summary?.avg_maintainability,
        suffix: "/100",
        icon: ShieldCheck,
        accent: "text-emerald-500 dark:text-emerald-400",
        bg: "bg-emerald-500/10 dark:bg-emerald-500/15",
      },
      {
        label: "Модулей с проблемами",
        value: summary?.modules_with_issues,
        icon: AlertTriangle,
        accent: "text-amber-500 dark:text-amber-400",
        bg: "bg-amber-500/10 dark:bg-amber-500/15",
      },
    ],
    [stats, summary],
  )

  const maxDomainCount = useMemo(
    () =>
      summary?.by_domain.reduce((m, d) => Math.max(m, d.count), 0) ?? 1,
    [summary],
  )

  return (
    <div className="mx-auto max-w-7xl space-y-8 p-6 lg:p-8">
      {/* ── Header ── */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-2">
              <Activity size={22} className="text-primary" />
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              Рентген качества
            </h1>
          </div>
          <p className="mt-2 text-muted-foreground">
            Карта рисков конфигурации 1С — где код труднее всего сопровождать и
            почему.
          </p>
        </div>
        <p className="text-xs text-muted-foreground tabular-nums">
          Источник: {sourceLabel(stats?.meta)} · {fmt(stats?.modules)} модулей
        </p>
      </div>

      {/* ── Missing-store banner ──
          When the Рентген store isn't built, the stats/summary endpoints answer
          503 and the widgets below would silently render "—"/blank — looking
          like sparse data rather than "no data". Surface it explicitly. */}
      {storeMissing && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-5 py-4 text-amber-700 dark:text-amber-300">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          <div className="text-sm">
            <p className="font-semibold">Хранилище Рентгена не построено</p>
            <p className="mt-0.5 text-amber-700/90 dark:text-amber-300/90">
              Метрики качества пока недоступны. Постройте граф вызовов
              (rentgen build), чтобы заполнить карту рисков — пустые виджеты ниже
              означают отсутствие данных, а не их нехватку.
            </p>
          </div>
        </div>
      )}

      {/* ── KPI Cards ── */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-5">
        {kpis.map((kpi) => (
          <div
            key={kpi.label}
            className="group relative overflow-hidden rounded-xl border border-border bg-card p-5 transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5"
          >
            <div
              className={cn(
                "absolute -right-4 -top-4 h-20 w-20 rounded-full opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-100",
                kpi.bg,
              )}
            />
            <div className="relative flex items-start justify-between">
              <p className="text-xs font-medium text-muted-foreground">
                {kpi.label}
              </p>
              <div className={cn("rounded-lg p-2", kpi.bg)}>
                <kpi.icon size={18} className={kpi.accent} />
              </div>
            </div>
            <p className="relative mt-3 text-3xl font-bold tracking-tight text-card-foreground tabular-nums">
              {statsQ.isLoading || summaryQ.isLoading ? (
                <span className="inline-block h-8 w-20 animate-pulse rounded bg-muted" />
              ) : (
                <>
                  {fmt(kpi.value)}
                  {kpi.suffix && (
                    <span className="text-base font-medium text-muted-foreground">
                      {kpi.suffix}
                    </span>
                  )}
                </>
              )}
            </p>
          </div>
        ))}
      </div>

      {/* ── Hotspots (hero) + Dead code ── */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Hotspots table */}
        <div className="xl:col-span-2 rounded-xl border border-border bg-card">
          <div className="flex flex-col gap-3 border-b border-border px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-base font-semibold text-card-foreground">
                <AlertTriangle size={17} className="text-orange-500" />
                Очаги риска
              </h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Самые опасные модули — нажмите строку, чтобы увидеть, из чего
                складывается риск.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">Все домены</option>
                {summary?.by_domain.map((d) => (
                  <option key={d.domain} value={d.domain}>
                    {d.domain} ({fmt(d.count)})
                  </option>
                ))}
              </select>
              <button
                onClick={() => setMinFanIn((v) => !v)}
                className={cn(
                  "rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                  minFanIn
                    ? "border-primary/30 bg-primary/10 text-primary"
                    : "border-border bg-background text-muted-foreground hover:text-foreground",
                )}
                title="Только модули с большим радиусом поражения (fan-in ≥ 10)"
              >
                Радиус ≥ 10
              </button>
            </div>
          </div>

          {/* Column header */}
          <div className="hidden grid-cols-[64px_1fr_auto_auto_auto] items-center gap-3 border-b border-border bg-muted/40 px-5 py-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground sm:grid">
            <span>Риск</span>
            <span>Модуль</span>
            <span className="text-right">Радиус</span>
            <span className="text-right" title="Сложность (больше = хуже)">
              Сложн.
            </span>
            <span className="text-right" title="Поддерживаемость (больше = лучше)">
              Поддерж.
            </span>
          </div>

          {hotspotsQ.isLoading ? (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
              <Loader2 size={16} className="animate-spin" />
              Загрузка очагов риска…
            </div>
          ) : hotspotsQ.isError ? (
            <div className="py-16 text-center text-sm text-destructive">
              Не удалось загрузить данные. Проверьте, запущен ли бэкенд.
            </div>
          ) : (hotspotsQ.data?.length ?? 0) === 0 ? (
            <div className="py-16 text-center text-sm text-muted-foreground">
              По выбранным фильтрам очагов не найдено.
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {hotspotsQ.data!.map((h) => (
                <HotspotRow key={h.module_path} h={h} />
              ))}
            </ul>
          )}
        </div>

        {/* Dead code panel */}
        <div className="rounded-xl border border-border bg-card">
          <div className="border-b border-border px-5 py-4">
            <h2 className="flex items-center gap-2 text-base font-semibold text-card-foreground">
              <Skull size={17} className="text-muted-foreground" />
              Возможный мёртвый код
            </h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Кандидатов:{" "}
              <span className="font-semibold tabular-nums text-foreground">
                {fmt(deadQ.data?.total)}
              </span>
            </p>
            <p className="mt-2 flex gap-1.5 text-[11px] leading-relaxed text-muted-foreground/80">
              <Info size={13} className="mt-0.5 shrink-0" />
              <span>
                Экспортные функции общих модулей без входящих вызовов. Не
                учитывает динамические вызовы (Выполнить()) и вызовы из других
                конфигураций — проверяйте перед удалением.
              </span>
            </p>
          </div>
          {deadQ.isLoading ? (
            <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
              <Loader2 size={16} className="animate-spin" />
              Загрузка…
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {deadQ.data?.candidates.map((c, i) => (
                <li key={`${c.module_path}.${c.name}.${i}`} className="px-5 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-sm font-medium text-card-foreground">
                        {c.name}
                      </p>
                      <p className="truncate font-mono text-xs text-muted-foreground">
                        {c.module}
                      </p>
                    </div>
                    <span
                      className="shrink-0 rounded-md bg-muted px-2 py-0.5 text-xs font-medium tabular-nums text-muted-foreground"
                      title="Цикломатическая сложность"
                    >
                      {fmt(c.complexity)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* ── Domains breakdown ── */}
      <div className="rounded-xl border border-border bg-card">
        <div className="border-b border-border px-5 py-4">
          <h2 className="flex items-center gap-2 text-base font-semibold text-card-foreground">
            <Layers size={17} className="text-primary" />
            Домены
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Количество модулей и средняя поддерживаемость по функциональным
            областям.
          </p>
        </div>
        <div className="space-y-3 p-5">
          {summaryQ.isLoading
            ? Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  className="h-7 animate-pulse rounded bg-muted"
                />
              ))
            : summary?.by_domain.map((d) => (
                <div key={d.domain} className="flex items-center gap-3">
                  <span className="w-40 shrink-0 truncate text-sm text-card-foreground">
                    {d.domain}
                  </span>
                  <div className="relative h-6 flex-1 overflow-hidden rounded-md bg-muted/60">
                    <div
                      className={cn(
                        "h-full rounded-md transition-all",
                        maintTone(d.avg_maintainability),
                      )}
                      style={{
                        width: `${Math.max(
                          2,
                          (d.count / maxDomainCount) * 100,
                        )}%`,
                      }}
                    />
                    <span className="absolute inset-y-0 left-2.5 flex items-center text-xs font-medium tabular-nums text-foreground/90">
                      {fmt(d.count)}
                    </span>
                  </div>
                  <span
                    className="w-24 shrink-0 text-right text-xs tabular-nums text-muted-foreground"
                    title="Средняя поддерживаемость (больше = лучше)"
                  >
                    поддерж.{" "}
                    <span className="font-semibold text-foreground">
                      {d.avg_maintainability.toFixed(1)}
                    </span>
                  </span>
                </div>
              ))}
        </div>
      </div>
    </div>
  )
}

/* ── Hotspot row (expandable) ─────────────────────────────── */

function HotspotRow({ h }: { h: Hotspot }) {
  const [open, setOpen] = useState(false)
  const tone = riskTone(h.risk)
  const reasons = useMemo(
    () =>
      [...h.reasons]
        .filter((r) => r.weight > 0)
        .sort((a, b) => b.weight - a.weight),
    [h.reasons],
  )
  const maxWeight = reasons[0]?.weight ?? 1

  return (
    <li>
      <button
        onClick={() => setOpen((v) => !v)}
        className="grid w-full grid-cols-[64px_1fr_auto] items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-muted/50 sm:grid-cols-[64px_1fr_auto_auto_auto]"
      >
        {/* Risk badge */}
        <span
          className={cn(
            "inline-flex h-9 w-12 items-center justify-center rounded-lg text-sm font-bold tabular-nums ring-1 ring-inset",
            tone.badge,
          )}
        >
          {Math.round(h.risk)}
        </span>

        {/* Module + domain */}
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ChevronRight
              size={14}
              className={cn(
                "shrink-0 text-muted-foreground transition-transform",
                open && "rotate-90",
              )}
            />
            <span
              className="truncate font-mono text-sm text-card-foreground"
              title={h.module_path}
            >
              {middleTruncate(h.module_path)}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-2 pl-6">
            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
              {h.domain}
            </span>
            <span className="text-[11px] text-muted-foreground sm:hidden">
              радиус: {fmt(h.fan_in)} · сложн. {fmt(h.complexity_score)} ·
              поддерж. {fmt(h.maintainability_score)}
            </span>
          </div>
        </div>

        {/* Fan-in (blast radius) */}
        <span className="hidden whitespace-nowrap text-right text-xs text-muted-foreground sm:block">
          радиус:{" "}
          <span className="font-semibold tabular-nums text-foreground">
            {fmt(h.fan_in)}
          </span>
        </span>

        {/* Complexity */}
        <span className="hidden text-right text-sm font-medium tabular-nums text-foreground sm:block">
          {fmt(h.complexity_score)}
        </span>

        {/* Maintainability */}
        <span className="hidden text-right text-sm font-medium tabular-nums text-foreground sm:block">
          {fmt(h.maintainability_score)}
        </span>
      </button>

      {/* Drill-down: explainable reasons */}
      {open && (
        <div className="border-t border-border bg-muted/30 px-5 py-4">
          <p className="mb-3 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Почему высокий риск
          </p>
          <ul className="space-y-2">
            {reasons.map((r, i) => (
              <ReasonBar key={i} reason={r} maxWeight={maxWeight} />
            ))}
          </ul>
        </div>
      )}
    </li>
  )
}

function ReasonBar({
  reason,
  maxWeight,
}: {
  reason: HotspotReason
  maxWeight: number
}) {
  // Reuse the risk palette to color reason weight by relative magnitude.
  const pct = Math.max(4, (reason.weight / maxWeight) * 100)
  const tone =
    reason.weight >= maxWeight * 0.66
      ? "bg-red-500"
      : reason.weight >= maxWeight * 0.33
        ? "bg-orange-500"
        : "bg-amber-500"

  return (
    <li className="flex items-center gap-3">
      <span className="min-w-0 flex-1 truncate text-sm text-card-foreground">
        {reason.detail}
      </span>
      <div className="hidden h-2 w-28 overflow-hidden rounded-full bg-muted sm:block">
        <div
          className={cn("h-full rounded-full", tone)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-10 shrink-0 text-right text-xs font-semibold tabular-nums text-muted-foreground">
        {reason.weight.toFixed(1)}
      </span>
    </li>
  )
}
