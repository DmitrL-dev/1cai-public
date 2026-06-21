import { createFileRoute, Link } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import type { ReactNode } from "react"
import {
  Activity,
  AlertTriangle,
  Archive,
  BarChart3,
  Bot,
  Boxes,
  Briefcase,
  CheckCircle2,
  Clock3,
  Compass,
  ClipboardCheck,
  Database,
  DollarSign,
  Download,
  FileDiff,
  FileText,
  Flame,
  GitBranch,
  Landmark,
  LineChart,
  Loader2,
  Map,
  Mic2,
  Network,
  PlayCircle,
  RefreshCw,
  Rocket,
  ScrollText,
  ServerCog,
  ShieldCheck,
  TestTube2,
  Users,
  Wrench,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  managementApi,
  type BuyerBriefResponse,
  type BuyerPulseResponse,
  type DemoStoryResponse,
  type EvidenceBundleRequest,
  type ExecutiveDashboardResponse,
  type RoleReport,
} from "@/lib/api-client"
import { BuyerRoomPacketControls } from "@/components/BuyerRoomPacketControls"
import { VerificationPacketControls } from "@/components/VerificationPacketControls"

export const Route = createFileRoute("/_authenticated/")({
  component: DashboardPage,
})

const nf = new Intl.NumberFormat("ru-RU")

type AppRoute =
  | "/"
  | "/killer-demo"
  | "/launch-room"
  | "/board-pack"
  | "/outcome-ledger"
  | "/buyer-concierge"
  | "/commercial-offer-studio"
  | "/enterprise-trust-center"
  | "/demo-command-center"
  | "/pilot-launchpad"
  | "/scenario-hub"
  | "/guided-demo"
  | "/business-case"
  | "/productization"
  | "/approvals"
  | "/audit"
  | "/configurations"
  | "/workbench"
  | "/quality"
  | "/change"
  | "/safe-autopilot"
  | "/testing"
  | "/release-readiness"
  | "/architecture"
  | "/metadata"
  | "/requirements"
  | "/team-governance"
  | "/offline-readiness"
  | "/operations"
  | "/lock-radar"
  | "/extension-safety"
  | "/edt-mcp"
  | "/platform-doctor"
  | "/vendor-portfolio"
  | "/update-war-room"
  | "/rights-rls"
  | "/value-packs"
  | "/evidence-bundle"

type HomeAction = {
  label: string
  to: AppRoute
}

type RoleCardModel = {
  title: string
  outcome: string
  signal: string
  icon: LucideIcon
  tone: "ok" | "warn" | "danger" | "muted"
  actions: HomeAction[]
}

const appRoutes = [
  "/",
  "/killer-demo",
  "/launch-room",
  "/board-pack",
  "/outcome-ledger",
  "/buyer-concierge",
  "/commercial-offer-studio",
  "/enterprise-trust-center",
  "/demo-command-center",
  "/pilot-launchpad",
  "/scenario-hub",
  "/guided-demo",
  "/business-case",
  "/productization",
  "/approvals",
  "/audit",
  "/configurations",
  "/workbench",
  "/quality",
  "/change",
  "/safe-autopilot",
  "/testing",
  "/release-readiness",
  "/architecture",
  "/metadata",
  "/requirements",
  "/team-governance",
  "/offline-readiness",
  "/operations",
  "/lock-radar",
  "/extension-safety",
  "/edt-mcp",
  "/platform-doctor",
  "/vendor-portfolio",
  "/update-war-room",
  "/rights-rls",
  "/value-packs",
  "/evidence-bundle",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/"
}

function downloadMarkdown(filename: string, markdown: string) {
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename || "rentgen-report.md"
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function firstScreenVerificationRequest(): EvidenceBundleRequest {
  return {
    client_name: "Demo client",
    config_path: "data/configs/unpacked",
    assumptions: {
      monthly_ai_subscription_cost: 120000,
    },
    include_killer_demo: true,
    include_launch_room: true,
    include_pilot_launchpad: true,
    include_outcome_ledger: true,
  }
}

function DashboardPage() {
  const query = useQuery({
    queryKey: ["management", "executive"],
    queryFn: () => managementApi.executive().then((r) => r.data),
    refetchInterval: 60_000,
  })
  const demoQuery = useQuery({
    queryKey: ["management", "demo"],
    queryFn: () => managementApi.demo().then((r) => r.data),
    refetchInterval: 120_000,
  })
  const buyerBriefQuery = useQuery({
    queryKey: ["management", "buyer-brief"],
    queryFn: () => managementApi.buyerBrief().then((r) => r.data),
    refetchInterval: 180_000,
  })

  const report = query.data
  const demo = demoQuery.data

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <BarChart3 size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              1С:Рентген
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Рабочий контур для правок, рисков, тестов, релизов, архитектуры и эксплуатации.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {report && <StatusBadge status={report.decision.status} score={report.decision.score} />}
          <button
            onClick={() => query.refetch()}
            disabled={query.isFetching}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-medium text-card-foreground transition hover:bg-accent disabled:opacity-60"
          >
            {query.isFetching ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            Обновить
          </button>
        </div>
      </header>

      <BuyerStart
        report={report}
        buyerBrief={buyerBriefQuery.data}
        buyerPulse={buyerBriefQuery.data?.pulse}
        isPulseLoading={buyerBriefQuery.isLoading}
      />

      <RoleStart report={report} isLoading={query.isLoading} />

      <DemoStory demo={demo} isLoading={demoQuery.isLoading} isError={demoQuery.isError} />

      {query.isLoading && (
        <div className="flex min-h-[180px] items-center justify-center rounded-lg border border-border bg-card text-muted-foreground">
          <Loader2 size={22} className="mr-2 animate-spin" />
          Собираю управленческие сигналы
        </div>
      )}

      {query.isError && (
        <div className="flex min-h-[180px] flex-col items-center justify-center rounded-lg border border-border bg-card px-6 text-center text-destructive">
          <AlertTriangle size={36} />
          <p className="mt-3 text-sm font-semibold">Не удалось загрузить управленческую сводку.</p>
        </div>
      )}

      {report && <ExecutiveDashboard report={report} />}
    </div>
  )
}

function BuyerStart({
  report,
  buyerBrief,
  buyerPulse,
  isPulseLoading,
}: {
  report?: ExecutiveDashboardResponse
  buyerBrief?: BuyerBriefResponse
  buyerPulse?: BuyerPulseResponse
  isPulseLoading: boolean
}) {
  const decisionStatus = buyerBrief?.status ?? report?.decision.status ?? "watch"
  const riskAreas = buyerBrief?.summary.red_areas ?? report?.kpis.red_areas ?? 0
  const reviewQueue = buyerBrief?.summary.review_queue ?? report?.kpis.review_queue ?? 0
  const highHotspots = buyerBrief?.summary.high_hotspots ?? report?.risk_summary.high_hotspots ?? 0
  const score = buyerBrief?.score ?? report?.decision.score
  const purchaseStatus = buyerBrief?.purchase_status ?? buyerPulse?.purchase_status
  const threeYearAiRent = buyerBrief?.commercial.three_year_ai_rent ?? buyerPulse?.commercial.three_year_ai_rent
  const items: Array<{
    title: string
    route: AppRoute
    outcome: string
    proof: string
    metric: string
    icon: LucideIcon
    tone: string
  }> = buyerBrief?.role_cards?.length
    ? buyerBrief.role_cards.map((item) => ({
        title: item.title,
        route: toAppRoute(item.route),
        outcome: item.proof_file,
        proof: item.spark,
        metric: item.status,
        icon: iconForBuyerRole(item.role),
        tone: toneForStatus(item.status),
      }))
    : [
        {
          title: "Launch Room",
          route: "/launch-room",
          outcome: "Close -> Activate -> Govern -> Realize",
          proof: "Single cockpit for next action, roles, routes and proof packet.",
          metric: purchaseStatus ? `purchase ${purchaseStatus}` : score === undefined ? "score ..." : `score ${score}`,
          icon: Rocket,
          tone: purchaseStatus ? toneForStatus(purchaseStatus) : toneForStatus(decisionStatus),
        },
        {
          title: "Killer Demo",
          route: "/killer-demo",
          outcome: "Role sparks, proof moments, paid ask",
          proof: "One presentation path for developer, architect, security and director.",
          metric: "buyer-ready",
          icon: Flame,
          tone: "ok",
        },
        {
          title: "Value Packs",
          route: "/value-packs",
          outcome: "Buyable packages by role",
          proof: "Role outcomes, evidence routes and licensing story stay in one product pack.",
          metric: "local asset",
          icon: Boxes,
          tone: "ok",
        },
        {
          title: "Board Pack",
          route: "/board-pack",
          outcome: "Director motion with checkout gates",
          proof: "Value, risk, governance and one-page paid order stay together.",
          metric: `${nf.format(reviewQueue)} reviews`,
          icon: Landmark,
          tone: reviewQueue ? "warn" : "ok",
        },
        {
          title: "Evidence Bundle",
          route: "/evidence-bundle",
          outcome: "Hashed artifacts for procurement",
          proof: "Markdown, JSON, manifest, governance proof and audit evidence.",
          metric: `${nf.format(riskAreas)} red`,
          icon: FileText,
          tone: riskAreas ? "danger" : "ok",
        },
      ]

  return (
    <section className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.35fr)]">
      <div className="min-w-0 rounded-lg border border-border bg-card p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={toneForStatus(decisionStatus)}>{decisionStatus}</Badge>
          <Badge tone="muted">local proof, no AI rent lock-in</Badge>
        </div>
        <h2 className="mt-3 break-words text-xl font-bold leading-tight text-card-foreground sm:text-2xl">
          {buyerBrief?.primary_motion.label ?? "Buyer path before deep workbench."}
        </h2>
        <p className="mt-2 break-words text-sm text-muted-foreground">
          {buyerBrief?.primary_motion.reason ??
            "The first screen starts from a purchase path, then lets specialists drill into code, platform, tests, security and operations when the meeting needs evidence."}
        </p>
        <OpenFirstRail buyerBrief={buyerBrief} purchaseStatus={purchaseStatus} score={score} />
        <div className="mt-4 grid grid-cols-3 gap-3">
          <CompactFact label="Score" value={score === undefined ? "..." : String(score)} />
          <CompactFact label="Red Areas" value={nf.format(riskAreas)} />
          <CompactFact label="Hotspots" value={nf.format(highHotspots)} />
        </div>
        <BuyerPulse
          buyerPulse={buyerPulse}
          isLoading={isPulseLoading}
          threeYearAiRent={threeYearAiRent}
        />
        {buyerBrief && <BuyerRoomPacketDownload />}
        {buyerBrief?.buyer_room_plan && <BuyerRoomPlan plan={buyerBrief.buyer_room_plan} />}
        {buyerBrief?.coverage_ledger && (
          <CoverageLedgerSummary ledger={buyerBrief.coverage_ledger} />
        )}
        {buyerBrief?.purchase_path && <BuyerPurchasePath path={buyerBrief.purchase_path} />}
        {buyerBrief && <BuyerBriefProof items={buyerBrief.proof_readiness} />}
        <div className="mt-5 grid grid-cols-2 gap-2">
          <BuyerStep label="Approve" to="/approvals" icon={ClipboardCheck} />
          <BuyerStep label="Audit" to="/audit" icon={ScrollText} />
          <BuyerStep label="Activate" to="/pilot-launchpad" icon={Rocket} />
          <BuyerStep label="Realize" to="/outcome-ledger" icon={LineChart} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {items.map((item) => (
          <Link
            key={item.route}
            to={item.route}
            className="min-w-0 rounded-lg border border-border bg-card p-4 transition hover:border-primary/40 hover:bg-accent/40"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                <div className="rounded-lg bg-primary/10 p-2">
                  <item.icon size={18} className="text-primary" />
                </div>
                <div className="min-w-0">
                  <h3 className="break-words text-base font-bold text-card-foreground">{item.title}</h3>
                  <p className="mt-0.5 break-words text-xs font-semibold uppercase text-muted-foreground">
                    {item.outcome}
                  </p>
                </div>
              </div>
              <Badge tone={item.tone}>{item.metric}</Badge>
            </div>
            <p className="mt-4 break-words text-sm text-muted-foreground">{item.proof}</p>
          </Link>
        ))}
      </div>
    </section>
  )
}

function OpenFirstRail({
  buyerBrief,
  purchaseStatus,
  score,
}: {
  buyerBrief?: BuyerBriefResponse
  purchaseStatus?: string
  score?: number
}) {
  const plan = buyerBrief?.buyer_room_plan
  const status = buyerBrief?.purchase_status ?? purchaseStatus ?? (score === undefined ? "watch" : score >= 80 ? "ready" : "watch")
  const apiPath = buyerBrief?.open_first_path?.length ? buyerBrief.open_first_path : undefined
  const items = apiPath
    ? apiPath.map((item) => ({
        key: `${item.step}-${item.stage}-${item.route}`,
        step: String(item.step).padStart(2, "0"),
        label: item.label,
        title: item.title,
        line: item.line,
        route: toAppRoute(item.route),
        file: item.file,
        icon: iconForOpenFirstStage(item.stage),
        tone: toneForStatus(item.status),
      }))
    : [
        {
          key: "launch",
          step: "01",
          label: "Orient",
          title: "Launch Room",
          line: "Start from the buyer cockpit and one next action.",
          route: "/launch-room" as AppRoute,
          file: "buyer-brief.md",
          icon: Compass,
          tone: toneForStatus(status),
        },
        {
          key: "demo",
          step: "02",
          label: "Prove",
          title: "Killer Demo",
          line: "Show the proof path for developer, architect, security and director.",
          route: "/killer-demo" as AppRoute,
          file: "OPEN_FIRST_KILLER_DEMO.md",
          icon: Flame,
          tone: "ok",
        },
        {
          key: "evidence",
          step: "03",
          label: "Package",
          title: "Evidence Bundle",
          line: "Package hashed artifacts for forwarding.",
          route: "/evidence-bundle" as AppRoute,
          file: "rentgen-evidence-bundle.zip",
          icon: Archive,
          tone: "ok",
        },
        {
          key: "activation",
          step: "04",
          label: "Activate",
          title: "Pilot Launchpad",
          line: "Turn the close into Day 0/7/30 acceptance.",
          route: "/pilot-launchpad" as AppRoute,
          file: "POST_DEMO_ACTIVATION_HANDOFF.md",
          icon: Rocket,
          tone: "ok",
        },
      ]

  return (
    <div className="mt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <PlayCircle size={15} className="text-primary" />
          <p className="break-words text-xs font-semibold uppercase text-muted-foreground">Open-first path</p>
        </div>
        <Badge tone={toneForStatus(status)}>purchase {status}</Badge>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {items.map((item) => (
          <Link
            key={item.key}
            to={item.route}
            className="grid min-w-0 grid-cols-[32px_minmax(0,1fr)] gap-2 rounded-md bg-background/70 p-2 transition hover:bg-accent"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10 text-[11px] font-bold text-primary">
              {item.step}
            </span>
            <span className="min-w-0">
              <span className="flex flex-wrap items-center gap-1.5">
                <item.icon size={13} className="shrink-0 text-primary" />
                <span className="break-words text-[11px] font-semibold uppercase text-muted-foreground">
                  {item.label}
                </span>
                <Badge tone={item.tone}>{item.title}</Badge>
              </span>
              <span className="mt-1 block break-words text-xs text-card-foreground">{item.line}</span>
              <span className="mt-1 block break-all font-mono text-[11px] text-muted-foreground">{item.file}</span>
            </span>
          </Link>
        ))}
      </div>
      {plan?.close_question && (
        <p className="mt-2 break-words text-xs font-semibold text-card-foreground">{plan.close_question}</p>
      )}
    </div>
  )
}

function iconForOpenFirstStage(stage: string): LucideIcon {
  if (stage === "prove") return Flame
  if (stage === "close") return ClipboardCheck
  if (stage === "verify") return ShieldCheck
  if (stage === "package") return Archive
  if (stage === "activate") return Rocket
  return Compass
}

function BuyerRoomPacketDownload() {
  return (
    <div className="mt-4 rounded-lg border border-primary/30 bg-primary/5 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Archive size={15} className="text-primary" />
          <p className="break-words text-xs font-semibold uppercase text-muted-foreground">Buyer Room Packet</p>
        </div>
        <Badge tone="ok">open first</Badge>
      </div>
      <BuyerRoomPacketControls monthlyAiCost={120000} className="mt-3" />
    </div>
  )
}

function BuyerRoomPlan({ plan }: { plan: BuyerBriefResponse["buyer_room_plan"] }) {
  return (
    <div className="mt-4 rounded-lg border border-primary/30 bg-primary/5 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Compass size={15} className="text-primary" />
          <p className="break-words text-xs font-semibold uppercase text-muted-foreground">Room plan</p>
        </div>
        <Badge tone={toneForStatus(plan.status)}>{plan.mode}</Badge>
      </div>
      <Link
        to={toAppRoute(plan.route)}
        className="mt-3 block min-w-0 rounded-md border border-border bg-card p-3 transition hover:border-primary/40 hover:bg-accent"
      >
        <div className="flex flex-wrap items-center gap-2">
          <Mic2 size={16} className="text-primary" />
          <p className="break-words text-sm font-bold text-card-foreground">{plan.title}</p>
          <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-semibold uppercase text-muted-foreground">
            {plan.role}
          </span>
        </div>
        <p className="mt-2 break-words text-xs text-muted-foreground">{plan.start_with}</p>
        <p className="mt-2 break-words text-xs font-semibold text-card-foreground">{plan.close_question}</p>
      </Link>
      <div className="mt-3 grid grid-cols-1 gap-2">
        {plan.sequence.slice(0, 3).map((item) => (
          <Link
            key={`${item.step}-${item.route}`}
            to={toAppRoute(item.route)}
            className="grid min-w-0 grid-cols-[24px_minmax(0,1fr)] gap-2 rounded-md border border-border bg-background/70 p-2 transition hover:border-primary/40 hover:bg-accent"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-[11px] font-bold text-primary">
              {item.step}
            </span>
            <span className="min-w-0">
              <span className="block break-words text-xs font-semibold text-card-foreground">{item.label}</span>
              <span className="block break-words text-[11px] text-muted-foreground">{item.line}</span>
            </span>
          </Link>
        ))}
      </div>
      <div className="mt-3 rounded-md border border-border bg-card p-2">
        <div className="flex items-center gap-2">
          <Archive size={14} className="text-primary" />
          <p className="text-[11px] font-semibold uppercase text-muted-foreground">Send after demo</p>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {plan.send_files.slice(0, 6).map((file) => (
            <span
              key={file}
              className="break-all rounded-md bg-muted px-2 py-1 font-mono text-[11px] text-muted-foreground"
            >
              {file}
            </span>
          ))}
        </div>
      </div>
      <p className="mt-2 break-words text-[11px] text-muted-foreground">{plan.why}</p>
    </div>
  )
}

function BuyerPulse({
  buyerPulse,
  isLoading,
  threeYearAiRent,
}: {
  buyerPulse?: BuyerPulseResponse
  isLoading: boolean
  threeYearAiRent?: string
}) {
  const launchStatus = buyerPulse?.launch.status ?? "..."
  const conciergeStatus = buyerPulse?.concierge.status ?? "..."
  const purchaseStatus = buyerPulse?.purchase_status ?? "..."

  return (
    <div className="mt-4 rounded-lg border border-border bg-background/70 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Activity size={15} className="text-primary" />
          <p className="text-xs font-semibold uppercase text-muted-foreground">Buyer pulse</p>
        </div>
        <Badge tone={isLoading ? "warn" : toneForStatus(purchaseStatus)}>
          {isLoading ? "loading" : `purchase ${purchaseStatus}`}
        </Badge>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <PulseLink
          to="/launch-room"
          label="Launch Room"
          value={launchStatus}
          detail={`${buyerPulse?.launch.journey_ready ?? "..."} / ${buyerPulse?.launch.journey_steps ?? "..."} journey ready`}
        />
        <PulseLink
          to="/buyer-concierge"
          label="Concierge"
          value={conciergeStatus}
          detail={`${buyerPulse?.concierge.persona_cards ?? "..."} roles, ${buyerPulse?.concierge.shortest_paths ?? "..."} paths`}
        />
        <PulseLink
          to="/commercial-offer-studio"
          label="AI rent line"
          value={threeYearAiRent ?? "..."}
          detail="three-year baseline for local-license story"
        />
        <PulseLink
          to="/evidence-bundle"
          label="Proof packet"
          value={buyerPulse?.evidence.proof_routes === undefined ? "..." : nf.format(buyerPulse.evidence.proof_routes)}
          detail={`${buyerPulse?.evidence.governance_gates ?? "..."} governance gates`}
        />
      </div>
    </div>
  )
}

function CoverageLedgerSummary({ ledger }: { ledger: BuyerBriefResponse["coverage_ledger"] }) {
  const summary = ledger.summary
  return (
    <div className="mt-4 rounded-lg border border-border bg-background/70 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <AlertTriangle size={15} className="text-primary" />
          <p className="text-xs font-semibold uppercase text-muted-foreground">Evidence coverage</p>
        </div>
        <Badge tone={toneForStatus(ledger.status)}>
          {ledger.status} {ledger.score}%
        </Badge>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <CompactFact label="Measured" value={`${summary.measured}/${summary.items}`} />
        <CompactFact label="Risk" value={nf.format(summary.risk)} />
        <CompactFact label="Caveats" value={nf.format(summary.caveats)} />
      </div>
      {ledger.caveats.length > 0 && (
        <div className="mt-3 space-y-1">
          {ledger.caveats.slice(0, 2).map((item) => (
            <p key={item} className="break-words text-xs text-muted-foreground">
              {item}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}

function BuyerPurchasePath({ path }: { path: BuyerBriefResponse["purchase_path"] }) {
  return (
    <div className="mt-4 rounded-lg border border-border bg-background/70 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Rocket size={15} className="text-primary" />
          <p className="break-words text-xs font-semibold uppercase text-muted-foreground">Purchase path</p>
        </div>
        <Badge tone={toneForStatus(path.status)}>{path.status}</Badge>
      </div>
      <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{path.headline}</p>
      <p className="mt-1 break-words text-xs text-muted-foreground">{path.buyer_line}</p>
      <div className="mt-3 grid grid-cols-1 gap-2">
        {path.steps.slice(0, 5).map((item) => (
          <Link
            key={`${item.step}-${item.route}-${item.file}`}
            to={toAppRoute(item.route)}
            className="grid min-w-0 grid-cols-[28px_minmax(0,1fr)] gap-2 rounded-md border border-border bg-card p-2 transition hover:border-primary/40 hover:bg-accent"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
              {item.step}
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="break-words text-xs font-semibold text-card-foreground">{item.label}</p>
                <span className="break-words rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                  {item.artifact}
                </span>
              </div>
              <p className="mt-1 break-words text-xs text-muted-foreground">{item.line}</p>
              <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">{item.file}</p>
            </div>
          </Link>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {path.buyer_room_packet_artifact && <MiniArtifact artifact={path.buyer_room_packet_artifact} />}
        <MiniArtifact artifact={path.close_artifact} />
        <MiniArtifact artifact={path.activation_artifact} />
        {path.archive_receipt_artifact && <MiniArtifact artifact={path.archive_receipt_artifact} />}
        {path.verification_packet_artifact && <MiniArtifact artifact={path.verification_packet_artifact} />}
      </div>
      {path.procurement_handoff && <ProcurementHandoff handoff={path.procurement_handoff} />}
      {path.send_files.length > 0 && (
        <div className="mt-3 rounded-md border border-border bg-card p-2">
          <p className="text-[11px] font-semibold uppercase text-muted-foreground">Files to forward</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {path.send_files.slice(0, 10).map((file) => (
              <span
                key={file}
                className="break-all rounded-md bg-muted px-2 py-1 font-mono text-[11px] text-muted-foreground"
              >
                {file}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ProcurementHandoff({ handoff }: { handoff: BuyerBriefResponse["purchase_path"]["procurement_handoff"] }) {
  return (
    <div className="mt-3 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <ShieldCheck size={14} className="text-emerald-700 dark:text-emerald-300" />
          <p className="break-words text-[11px] font-semibold uppercase text-emerald-700 dark:text-emerald-300">
            {handoff.title}
          </p>
        </div>
        <Badge tone={toneForStatus(handoff.status)}>{handoff.status}</Badge>
      </div>
      <p className="mt-2 break-words text-xs text-card-foreground">{handoff.owner_line}</p>
      <div className="mt-2 grid grid-cols-1 gap-2">
        {handoff.open_order.slice(0, 6).map((item) => (
          <Link
            key={`${item.step}-${item.route}-${item.file}`}
            to={toAppRoute(item.route)}
            className="grid min-w-0 grid-cols-[24px_minmax(0,1fr)] gap-2 rounded-md border border-emerald-500/20 bg-card p-2 transition hover:border-emerald-500/50 hover:bg-accent"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-500/10 text-[11px] font-bold text-emerald-700 dark:text-emerald-300">
              {item.step}
            </span>
            <span className="min-w-0">
              <span className="block break-words text-xs font-semibold text-card-foreground">{item.label}</span>
              <span className="mt-1 block break-all font-mono text-[11px] text-muted-foreground">{item.file}</span>
              {item.hash_header && (
                <span className="mt-1 block break-all font-mono text-[11px] text-emerald-700 dark:text-emerald-300">
                  {item.hash_header}
                </span>
              )}
              <span className="mt-1 block break-words text-[11px] text-muted-foreground">{item.check}</span>
            </span>
          </Link>
        ))}
      </div>
      <p className="mt-2 break-words text-[11px] font-semibold text-card-foreground">{handoff.acceptance}</p>
      {handoff.attachments.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {handoff.attachments.slice(0, 5).map((item) => (
            <Link
              key={`${item.route}-${item.file}`}
              to={toAppRoute(item.route)}
              className="max-w-full break-all rounded-md bg-card px-2 py-1 font-mono text-[11px] text-muted-foreground transition hover:bg-accent"
            >
              {item.file}
            </Link>
          ))}
        </div>
      )}
      <VerificationPacketControls
        buildRequest={firstScreenVerificationRequest}
        fallbackFilename="demo-client-archive-verification-packet.zip"
        className="mt-3"
        buttonClassName="bg-card hover:bg-accent"
        compact
        errorMessage="Verification Packet ZIP did not build."
        icon="download"
      />
    </div>
  )
}

function MiniArtifact({ artifact }: { artifact: BuyerBriefResponse["purchase_path"]["close_artifact"] }) {
  return (
    <Link
      to={toAppRoute(artifact.route)}
      className="block min-w-0 rounded-md border border-border bg-card p-2 transition hover:border-primary/40 hover:bg-accent"
    >
      <p className="break-words text-xs font-semibold text-card-foreground">{artifact.title}</p>
      <p className="mt-1 break-words text-[11px] text-muted-foreground">{artifact.line}</p>
      <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">{artifact.file}</p>
    </Link>
  )
}

function BuyerBriefProof({ items }: { items: BuyerBriefResponse["proof_readiness"] }) {
  return (
    <div className="mt-4 grid grid-cols-1 gap-2">
      {items.slice(0, 4).map((item) => {
        const Icon = iconForProof(item.id)
        return (
          <Link
            key={item.id}
            to={toAppRoute(item.route)}
            className="flex min-w-0 items-start gap-3 rounded-lg border border-border bg-background/70 p-3 transition hover:border-primary/40 hover:bg-accent"
          >
            <div className="rounded-md bg-primary/10 p-1.5">
              <Icon size={15} className="text-primary" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                <Badge tone={toneForStatus(item.status)}>{item.status}</Badge>
              </div>
              <p className="mt-1 break-words text-xs text-muted-foreground">{item.signal}</p>
              <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">{item.file}</p>
            </div>
          </Link>
        )
      })}
    </div>
  )
}

function PulseLink({
  to,
  label,
  value,
  detail,
}: {
  to: AppRoute
  label: string
  value: string | number
  detail: string
}) {
  return (
    <Link
      to={to}
      className="block min-w-0 rounded-md border border-border bg-card p-2 transition hover:border-primary/40 hover:bg-accent"
    >
      <p className="break-words text-[11px] font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-bold text-card-foreground">{value}</p>
      <p className="mt-0.5 break-words text-[11px] text-muted-foreground">{detail}</p>
    </Link>
  )
}

function iconForBuyerRole(role: string): LucideIcon {
  if (role === "developer") return GitBranch
  if (role === "architect") return Network
  if (role === "director") return Landmark
  if (role === "security") return ShieldCheck
  if (role === "vendor") return Briefcase
  return Compass
}

function iconForProof(id: string): LucideIcon {
  if (id === "audit-siem") return ScrollText
  if (id === "governance") return ClipboardCheck
  if (id === "trust") return ShieldCheck
  return FileText
}

function BuyerStep({ label, to, icon: Icon }: { label: string; to: AppRoute; icon: LucideIcon }) {
  return (
    <Link
      to={to}
      className="inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-semibold text-card-foreground transition hover:border-primary/40 hover:bg-accent"
    >
      <Icon size={15} />
      {label}
    </Link>
  )
}

function RoleStart({ report, isLoading }: { report?: ExecutiveDashboardResponse; isLoading: boolean }) {
  const cards = buildRoleCards(report)
  const score = report?.decision.score ?? 0
  const status = report?.decision.status ?? "watch"

  return (
    <>
      <section className="rounded-lg border border-border bg-card p-4 sm:p-5">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={report?.available ? "ok" : isLoading ? "warn" : "muted"}>
                {report?.available ? "стенд готов" : isLoading ? "сигналы грузятся" : "выберите сценарий"}
              </Badge>
              <Badge tone={status === "ready" ? "ok" : status === "critical" || status === "blocked" ? "danger" : "warn"}>
                решение {score || "?"}
              </Badge>
            </div>
            <h2 className="mt-3 break-words text-lg font-bold text-card-foreground sm:text-2xl">
              {report?.decision.headline ?? "Начните с роли, результата или конкретной правки"}
            </h2>
            <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground">
              {report?.decision.release_policy ??
                "Главная собрана как рабочий пульт: меньше пунктов меню, больше прямых входов в то, что человек хочет доказать или исправить."}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <CompactFact label="Score" value={report ? String(report.decision.score) : "..."} />
            <CompactFact label="Modules" value={report ? nf.format(report.kpis.modules) : "..."} />
            <CompactFact label="Risk Areas" value={report ? nf.format(report.kpis.red_areas) : "..."} />
            <CompactFact label="Offline" value={report ? `${report.kpis.offline_score}%` : "..."} />
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => (
          <RoleCard key={card.title} card={card} />
        ))}
      </section>

      <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <FastEntry icon={Flame} title="Killer Demo" text="stages, roles, close, proof" to="/killer-demo" />
        <FastEntry icon={Rocket} title="Launch Room" text="role, proof, trust, approval" to="/launch-room" />
        <FastEntry icon={Database} title="Подключить конфигурацию" text="EDT/Git/XML pre-flight" to="/configurations" />
        <FastEntry icon={FileText} title="Evidence Bundle" text="hashed reports, manifest, JSON" to="/evidence-bundle" />
      </section>

      <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-8">
        <FastEntry icon={Landmark} title="Board Pack" text="motion, risks, proof packet" to="/board-pack" />
        <FastEntry icon={LineChart} title="Outcomes" text="adoption, metrics, expansion" to="/outcome-ledger" />
        <FastEntry icon={Compass} title="Concierge" text="role, pain, shortest path" to="/buyer-concierge" />
        <FastEntry icon={Mic2} title="Demo Center" text="live stages, pivots, close" to="/demo-command-center" />
        <FastEntry icon={ShieldCheck} title="Trust Center" text="security, SBOM, procurement" to="/enterprise-trust-center" />
        <FastEntry icon={ClipboardCheck} title="Approvals" text="scope, actor, decision, constraints" to="/approvals" />
        <FastEntry icon={ScrollText} title="Audit Log" text="hash-chain, events, export" to="/audit" />
        <FastEntry icon={DollarSign} title="Offer Studio" text="packages, price anchors, proposal" to="/commercial-offer-studio" />
        <FastEntry icon={Map} title="Scenario Hub" text="pain routes, roles, proof" to="/scenario-hub" />
        <FastEntry icon={Rocket} title="Pilot Launchpad" text="offers, acceptance, procurement" to="/pilot-launchpad" />
        <FastEntry icon={PlayCircle} title="Guided Demo" text="buyer route, roles, proof, close" to="/guided-demo" />
        <FastEntry icon={Boxes} title="Value Packs" text="roles, packages, proof, licensing" to="/value-packs" />
        <FastEntry icon={FileDiff} title="Проверить правку" text="impact, риск, тесты" to="/change" />
        <FastEntry icon={Bot} title="Safe Autopilot" text="plan, diff, tests, approval" to="/safe-autopilot" />
        <FastEntry icon={Rocket} title="Собрать релиз" text="policy gates, evidence" to="/release-readiness" />
        <FastEntry icon={Network} title="Увидеть архитектуру" text="связи, ownership, blast radius" to="/architecture" />
        <FastEntry icon={ServerCog} title="Проверить платформу" text="upgrade, техжурнал, OpenMetrics" to="/platform-doctor" />
        <FastEntry icon={Activity} title="Разобрать блокировки" text="ТЖ, дедлоки, таймауты" to="/lock-radar" />
        <FastEntry icon={Wrench} title="Проверить расширения" text="CFE, права, hooks, impact" to="/extension-safety" />
        <FastEntry icon={Briefcase} title="Портфель клиента" text="pre-sale audit pack" to="/vendor-portfolio" />
        <FastEntry icon={DollarSign} title="Business Case" text="money map, objections, 30/60/90" to="/business-case" />
        <FastEntry icon={Archive} title="Productization" text="SBOM, offline bundle, verify" to="/productization" />
      </section>
    </>
  )
}

function DemoStory({ demo, isLoading, isError }: { demo?: DemoStoryResponse; isLoading: boolean; isError: boolean }) {
  if (isLoading) {
    return (
      <section className="flex min-h-[180px] items-center justify-center rounded-lg border border-border bg-card text-muted-foreground">
        <Loader2 size={20} className="mr-2 animate-spin" />
        Собираю demo story
      </section>
    )
  }

  if (isError || !demo) {
    return (
      <section className="rounded-lg border border-amber-500/25 bg-amber-500/10 p-4 text-sm text-amber-700 dark:text-amber-300">
        Demo story временно недоступна; рабочие страницы и executive-сводка остаются доступными.
      </section>
    )
  }

  return (
    <section className="space-y-4">
      <div className="rounded-lg border border-border bg-card p-4 sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="ok">demo за {demo.scenario.setup_minutes} мин</Badge>
              <Badge tone={demo.scenario.coverage.status === "ready" ? "ok" : "warn"}>
                coverage {demo.scenario.coverage.score ?? "n/a"}%
              </Badge>
            </div>
            <h2 className="mt-3 break-words text-lg font-bold text-card-foreground sm:text-2xl">
              {demo.scenario.title}
            </h2>
            <p className="mt-2 max-w-4xl break-words text-sm text-muted-foreground">
              {demo.scenario.subtitle}
            </p>
            <p className="mt-2 max-w-4xl break-words text-xs text-muted-foreground">
              {demo.scenario.coverage.caveat}
            </p>
          </div>
          <button
            onClick={() => downloadMarkdown(demo.export.download_name, demo.export.markdown)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-semibold text-card-foreground transition hover:border-primary/40 hover:bg-accent"
          >
            <Download size={16} />
            Скачать demo
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {demo.first_value.map((item) => (
          <Link
            key={item.title}
            to={toAppRoute(item.to)}
            className="min-w-0 rounded-lg border border-border bg-card p-4 transition hover:border-primary/40 hover:bg-accent/30"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="break-words text-xs font-semibold uppercase text-muted-foreground">{item.title}</p>
                <p className="mt-2 break-words text-xl font-bold text-card-foreground">{item.value}</p>
              </div>
              <Badge tone={item.tone}>{item.next_action}</Badge>
            </div>
            <p className="mt-3 break-words text-sm text-muted-foreground">{item.why}</p>
          </Link>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="Demo path" icon={PlayCircle}>
          <div className="space-y-3">
            {demo.demo_steps.map((step) => (
              <Link
                key={step.id}
                to={toAppRoute(step.to)}
                className="flex min-w-0 items-start gap-3 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
              >
                <div className="mt-0.5 rounded-lg bg-primary/10 p-2">
                  <PlayCircle size={16} className="text-primary" />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="break-words text-sm font-semibold text-card-foreground">{step.title}</p>
                    <Badge tone="muted">{step.role}</Badge>
                    <Badge tone="muted">{step.minutes} мин</Badge>
                  </div>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{step.evidence}</p>
                </div>
              </Link>
            ))}
          </div>
        </Panel>

        <Panel title="Query Surgeon" icon={FileDiff}>
          <div className="space-y-3">
            <div>
              <p className="text-sm font-semibold text-card-foreground">{demo.query_surgeon_case.title}</p>
              <p className="mt-1 break-words text-xs text-muted-foreground">{demo.query_surgeon_case.problem}</p>
            </div>
            <pre className="max-h-24 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {demo.query_surgeon_case.unsafe_pattern}
            </pre>
            <ul className="space-y-2">
              {demo.query_surgeon_case.safe_options.map((item) => (
                <li key={item} className="flex gap-2 text-xs text-muted-foreground">
                  <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-500" />
                  <span className="break-words">{item}</span>
                </li>
              ))}
            </ul>
            <p className="break-words text-xs text-muted-foreground">{demo.query_surgeon_case.test}</p>
          </div>
        </Panel>
      </div>

      <RoleReports reports={demo.role_reports} />
    </section>
  )
}

function RoleReports({ reports }: { reports: RoleReport[] }) {
  return (
    <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      {reports.map((report) => (
        <article key={report.role} className="min-w-0 rounded-lg border border-border bg-card p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="break-words text-base font-bold text-card-foreground">{report.title}</h2>
              <p className="mt-1 break-words text-sm text-muted-foreground">{report.headline}</p>
            </div>
            <Badge tone={report.tone}>{report.status}</Badge>
          </div>
          <ul className="mt-4 space-y-2">
            {report.proof_points.slice(0, 3).map((item) => (
              <li key={item} className="flex gap-2 text-xs text-muted-foreground">
                <FileText size={14} className="mt-0.5 shrink-0 text-primary" />
                <span className="break-words">{item}</span>
              </li>
            ))}
          </ul>
          <div className="mt-4 flex flex-wrap gap-2">
            {report.next_actions.slice(0, 2).map((action) => (
              <Link
                key={`${report.role}-${action.to}`}
                to={toAppRoute(action.to)}
                className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-3 text-sm font-semibold text-card-foreground transition hover:border-primary/40 hover:bg-accent"
              >
                {action.label}
              </Link>
            ))}
            <button
              onClick={() => downloadMarkdown(report.download_name, report.markdown)}
              className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-3 text-sm font-semibold text-card-foreground transition hover:border-primary/40 hover:bg-accent"
            >
              <Download size={15} />
            </button>
          </div>
        </article>
      ))}
    </section>
  )
}

function RoleCard({ card }: { card: RoleCardModel }) {
  return (
    <article className="min-w-0 rounded-lg border border-border bg-card p-4 transition hover:border-primary/40 hover:bg-accent/30">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <div className="rounded-lg bg-primary/10 p-2">
            <card.icon size={18} className="text-primary" />
          </div>
          <div className="min-w-0">
            <h2 className="break-words text-base font-bold text-card-foreground">{card.title}</h2>
            <p className="mt-0.5 break-words text-xs font-semibold uppercase text-muted-foreground">
              {card.outcome}
            </p>
          </div>
        </div>
        <Badge tone={card.tone}>{card.tone === "ok" ? "ready" : card.tone === "danger" ? "risk" : "watch"}</Badge>
      </div>
      <p className="mt-4 min-h-10 break-words text-sm text-muted-foreground">{card.signal}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {card.actions.map((action) => (
          <Link
            key={`${card.title}-${action.to}`}
            to={action.to}
            className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-3 text-sm font-semibold text-card-foreground transition hover:border-primary/40 hover:bg-accent"
          >
            {action.label}
          </Link>
        ))}
      </div>
    </article>
  )
}

function FastEntry({ icon: Icon, title, text, to }: { icon: LucideIcon; title: string; text: string; to: AppRoute }) {
  return (
    <Link
      to={to}
      className="flex min-w-0 items-center gap-3 rounded-lg border border-border bg-card p-4 transition hover:border-primary/40 hover:bg-accent/40"
    >
      <div className="rounded-lg bg-primary/10 p-2">
        <Icon size={18} className="text-primary" />
      </div>
      <div className="min-w-0">
        <p className="break-words text-sm font-bold text-card-foreground">{title}</p>
        <p className="mt-0.5 break-words text-xs text-muted-foreground">{text}</p>
      </div>
    </Link>
  )
}

function buildRoleCards(report?: ExecutiveDashboardResponse): RoleCardModel[] {
  const highRisk = report?.risk_summary.high_hotspots ?? 0
  const redAreas = report?.kpis.red_areas ?? 0
  const reviewQueue = report?.kpis.review_queue ?? 0
  const coverage = report?.kpis.coverage_score
  const offline = report?.kpis.offline_score

  return [
    {
      title: "Разработчик",
      outcome: "правка без сюрпризов",
      signal: highRisk
        ? `${nf.format(highRisk)} hotspots требуют проверки перед коммитом`
        : "impact, риск и тесты собраны в один маршрут",
      icon: GitBranch,
      tone: highRisk ? "danger" : "ok",
      actions: [
        { label: "Проверить правку", to: "/change" },
        { label: "Рентген кода", to: "/quality" },
        { label: "Тесты", to: "/testing" },
      ],
    },
    {
      title: "Архитектор",
      outcome: "связи и blast radius",
      signal: redAreas
        ? `${nf.format(redAreas)} красных зон влияют на архитектурное решение`
        : "карта модулей, метаданные и трассировка требований готовы к разбору",
      icon: Network,
      tone: redAreas ? "danger" : "ok",
      actions: [
        { label: "Архитектура", to: "/architecture" },
        { label: "Обновление", to: "/update-war-room" },
        { label: "Extensions", to: "/extension-safety" },
      ],
    },
    {
      title: "Директор",
      outcome: "решение по релизу",
      signal: report
        ? `${report.decision.headline}; очередь ревью: ${nf.format(reviewQueue)}`
        : "релизная готовность, ownership и offline-контур в одной сводке",
      icon: ShieldCheck,
      tone: report?.decision.status === "ready" ? "ok" : report ? "warn" : "muted",
      actions: [
        { label: "Scenarios", to: "/scenario-hub" },
        { label: "Demo", to: "/guided-demo" },
        { label: "Business", to: "/business-case" },
        { label: "Релиз", to: "/release-readiness" },
        { label: "Approvals", to: "/approvals" },
        { label: "Evidence", to: "/evidence-bundle" },
      ],
    },
    {
      title: "QA и релиз",
      outcome: "доказательства качества",
      signal: coverage !== undefined
        ? `покрытие ${coverage}%, gates и evidence доступны для релизного окна`
        : "тестовые прогоны, change impact и policy gates сведены вместе",
      icon: TestTube2,
      tone: coverage === undefined ? "muted" : coverage >= 90 ? "ok" : "warn",
      actions: [
        { label: "Тесты", to: "/testing" },
        { label: "Gates", to: "/release-readiness" },
        { label: "Audit", to: "/audit" },
        { label: "Evidence", to: "/evidence-bundle" },
      ],
    },
    {
      title: "Эксплуатация",
      outcome: "готовность контура",
      signal: offline !== undefined
        ? `offline score ${offline}%, инциденты и операционные риски под рукой`
        : "операционные сигналы, offline readiness и зоны риска готовы к проверке",
      icon: Clock3,
      tone: offline === undefined ? "muted" : offline >= 90 ? "ok" : "warn",
      actions: [
        { label: "Operations", to: "/operations" },
        { label: "Lock Radar", to: "/lock-radar" },
        { label: "Платформа", to: "/platform-doctor" },
      ],
    },
    {
      title: "Вендор / франчайзи",
      outcome: "демо и поставка",
      signal: "портфель клиента превращает риск, платформу и релизный gate в понятный пакет работ",
      icon: Briefcase,
      tone: "ok",
      actions: [
        { label: "Портфель", to: "/vendor-portfolio" },
        { label: "Business", to: "/business-case" },
        { label: "Evidence", to: "/evidence-bundle" },
        { label: "Пакеты", to: "/value-packs" },
      ],
    },
  ]
}

function ExecutiveDashboard({ report }: { report: ExecutiveDashboardResponse }) {
  return (
    <>
      <section className="rounded-lg border border-border bg-card p-4 sm:p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Decision</p>
            <h2 className="mt-1 break-words text-lg font-bold text-card-foreground sm:text-2xl">
              {report.decision.headline}
            </h2>
            <p className="mt-2 break-words text-sm text-muted-foreground">
              {report.decision.release_policy}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge tone={report.available ? "ok" : "danger"}>{report.available ? "store ready" : "store blocked"}</Badge>
            <Badge tone="muted">{new Date(report.generated_at).toLocaleString("ru-RU")}</Badge>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} tone={report.decision.status} />
        <Metric label="Modules" value={report.kpis.modules} icon={Database} />
        <Metric label="Red Areas" value={report.kpis.red_areas} icon={AlertTriangle} tone={report.kpis.red_areas ? "critical" : "ready"} />
        <Metric label="Review Queue" value={report.kpis.review_queue} icon={Users} tone={report.kpis.review_queue ? "watch" : "ready"} />
        <Metric label="Coverage" value={`${report.kpis.coverage_score}%`} icon={CheckCircle2} tone={report.kpis.coverage_score === 100 ? "ready" : "watch"} />
        <Metric label="Offline" value={`${report.kpis.offline_score}%`} icon={Clock3} tone={report.kpis.offline_score >= 90 ? "ready" : "watch"} />
        <Metric label="Call Edges" value={report.kpis.call_edges} icon={GitBranch} />
        <Metric label="High Risk" value={report.risk_summary.high_hotspots} icon={Activity} tone={report.risk_summary.high_hotspots ? "critical" : "ready"} />
      </section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <Panel title="Workstreams" icon={BarChart3}>
          <div className="space-y-3">
            {report.workstreams.map((item) => (
              <div key={item.id} className="rounded-lg border border-border bg-background/60 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                    <p className="mt-0.5 break-words text-xs text-muted-foreground">{item.signal}</p>
                  </div>
                  <Badge tone={toneForStatus(item.status)}>{item.score}%</Badge>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded bg-muted">
                  <div className={cn("h-full rounded", barTone(item.status))} style={{ width: `${Math.max(0, Math.min(100, item.score))}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Manager Actions" icon={AlertTriangle}>
          <div className="space-y-3">
            {report.manager_actions.map((item) => (
              <div key={`${item.severity}-${item.owner}-${item.title}`} className="rounded-lg border border-border bg-background/60 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={severityTone(item.severity)}>{item.severity}</Badge>
                  <span className="text-xs font-semibold uppercase text-muted-foreground">{item.owner}</span>
                </div>
                <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                <p className="mt-1 break-words text-xs text-muted-foreground">{item.impact}</p>
              </div>
            ))}
          </div>
        </Panel>
      </section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel title="Top Risks" icon={Activity}>
          {report.risk_summary.top_risks.length === 0 ? (
            <Empty text="No high-risk hotspots in the current store." />
          ) : (
            <ul className="space-y-3">
              {report.risk_summary.top_risks.map((item) => (
                <li key={`${item.module_path}-${item.risk}`} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge tone={item.risk >= 70 ? "danger" : "warn"}>risk {item.risk}</Badge>
                    <span className="text-xs text-muted-foreground">fan-in {nf.format(item.fan_in)}</span>
                  </div>
                  <p className="mt-2 break-all font-mono text-xs font-semibold text-card-foreground">{item.module_path}</p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{item.domain}</p>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Release Queue" icon={Users}>
          {report.governance.review_queue.length === 0 ? (
            <Empty text="No owner review queue." />
          ) : (
            <ul className="space-y-3">
              {report.governance.review_queue.map((item, index) => (
                <li key={`${String(item.module_path)}-${index}`} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="warn">SLA {String(item.sla ?? "review")}</Badge>
                    <span className="text-xs font-semibold uppercase text-muted-foreground">
                      {String((item.owner as Record<string, unknown> | undefined)?.name ?? "owner")}
                    </span>
                  </div>
                  <p className="mt-2 break-all font-mono text-xs text-card-foreground">{String(item.module_path ?? "")}</p>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </section>

      <section className="rounded-lg border border-border bg-card p-4 sm:p-5">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <CompactFact label="Product Coverage" value={`${report.coverage.done}/${report.coverage.total}`} />
          <CompactFact label="P0 Coverage" value={`${report.coverage.p0_score}%`} />
          <CompactFact label="Governance Snapshots" value={String(report.governance.trend.total ?? 0)} />
        </div>
      </section>
    </>
  )
}

function Metric({ label, value, icon: Icon, tone = "neutral" }: { label: string; value: number | string; icon: LucideIcon; tone?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="min-w-0 break-words text-xs font-semibold uppercase text-muted-foreground">{label}</p>
        <Icon size={17} className={iconTone(tone)} />
      </div>
      <p className="mt-3 break-words text-2xl font-bold tabular-nums text-card-foreground sm:text-3xl">
        {typeof value === "number" ? nf.format(value) : value}
      </p>
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
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  )
}

function StatusBadge({ status, score }: { status: ExecutiveDashboardResponse["decision"]["status"]; score: number }) {
  const Icon = status === "ready" ? CheckCircle2 : status === "blocked" || status === "critical" ? XCircle : AlertTriangle
  return (
    <span className={cn("inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-semibold", statusClass(status))}>
      <Icon size={16} />
      {status} · {score}
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

function CompactFact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-lg font-bold text-card-foreground">{value}</p>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">{text}</p>
}

function toneForStatus(status: string): string {
  if (status === "ready" || status === "pass") return "ok"
  if (status === "risk" || status === "critical" || status === "fail") return "danger"
  return "warn"
}

function severityTone(severity: string): string {
  if (severity === "critical" || severity === "high") return "danger"
  if (severity === "medium") return "warn"
  return "muted"
}

function barTone(status: string): string {
  if (status === "ready") return "bg-emerald-500"
  if (status === "risk" || status === "critical") return "bg-red-500"
  return "bg-amber-500"
}

function iconTone(tone: string): string {
  if (tone === "ready") return "text-emerald-500"
  if (tone === "critical" || tone === "risk") return "text-red-500"
  if (tone === "watch") return "text-amber-500"
  return "text-muted-foreground"
}

function statusClass(status: string): string {
  if (status === "ready") return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
  if (status === "blocked" || status === "critical") return "bg-red-500/10 text-red-600 dark:text-red-400"
  if (status === "risk") return "bg-orange-500/10 text-orange-600 dark:text-orange-400"
  return "bg-amber-500/10 text-amber-600 dark:text-amber-400"
}

function badgeClass(tone: string): string {
  if (tone === "ok") return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
  if (tone === "danger") return "bg-red-500/10 text-red-600 dark:text-red-400"
  if (tone === "warn") return "bg-amber-500/10 text-amber-600 dark:text-amber-400"
  return "bg-muted text-muted-foreground"
}
