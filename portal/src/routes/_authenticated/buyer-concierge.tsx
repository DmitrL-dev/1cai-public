import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  Compass,
  DollarSign,
  Download,
  FileText,
  Loader2,
  Map,
  PlayCircle,
  RefreshCw,
  Route as RouteIcon,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { BuyerRoomPacketControls } from "@/components/BuyerRoomPacketControls"
import { OpenFirstPathList } from "@/components/OpenFirstPathList"
import { VerificationPacketControls } from "@/components/VerificationPacketControls"
import {
  buyerConciergeApi,
  type BuyerConciergeResponse,
  type EvidenceBundleRequest,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/buyer-concierge")({
  component: BuyerConciergePage,
})

const nf = new Intl.NumberFormat("ru-RU")

type AppRoute =
  | "/"
  | "/buyer-concierge"
  | "/launch-room"
  | "/killer-demo"
  | "/board-pack"
  | "/outcome-ledger"
  | "/commercial-offer-studio"
  | "/enterprise-trust-center"
  | "/demo-command-center"
  | "/pilot-launchpad"
  | "/scenario-hub"
  | "/guided-demo"
  | "/business-case"
  | "/productization"
  | "/quality"
  | "/change"
  | "/testing"
  | "/release-readiness"
  | "/architecture"
  | "/offline-readiness"
  | "/operations"
  | "/lock-radar"
  | "/platform-doctor"
  | "/vendor-portfolio"
  | "/rights-rls"
  | "/value-packs"
  | "/evidence-bundle"
  | "/approvals"
  | "/audit"

const appRoutes = [
  "/",
  "/buyer-concierge",
  "/launch-room",
  "/killer-demo",
  "/board-pack",
  "/outcome-ledger",
  "/commercial-offer-studio",
  "/enterprise-trust-center",
  "/demo-command-center",
  "/pilot-launchpad",
  "/scenario-hub",
  "/guided-demo",
  "/business-case",
  "/productization",
  "/quality",
  "/change",
  "/testing",
  "/release-readiness",
  "/architecture",
  "/offline-readiness",
  "/operations",
  "/lock-radar",
  "/platform-doctor",
  "/vendor-portfolio",
  "/rights-rls",
  "/value-packs",
  "/evidence-bundle",
  "/approvals",
  "/audit",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/buyer-concierge"
}

function downloadText(filename: string, content: string, type = "text/markdown;charset=utf-8") {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function BuyerConciergePage() {
  const [clientName, setClientName] = useState("Demo client")
  const [configPath, setConfigPath] = useState("data/configs/unpacked")
  const [targetVersion, setTargetVersion] = useState("")
  const [monthlyAiCost, setMonthlyAiCost] = useState("120000")
  const [hourlyRate, setHourlyRate] = useState("2500")
  const [reviewHours, setReviewHours] = useState("80")
  const [incidentCost, setIncidentCost] = useState("300000")
  const buildVerificationPacketRequest = (): EvidenceBundleRequest => ({
    client_name: clientName.trim() || "Demo client",
    config_path: configPath.trim() || undefined,
    target_platform_version: targetVersion.trim() || undefined,
    assumptions: {
      monthly_ai_subscription_cost: toNumber(monthlyAiCost),
      hourly_rate: toNumber(hourlyRate),
      manual_review_hours_month: toNumber(reviewHours),
      incident_cost: toNumber(incidentCost),
    },
    include_buyer_concierge: true,
    include_killer_demo: true,
  })

  const mutation = useMutation({
    mutationFn: () =>
      buyerConciergeApi
        .build({
          client_name: clientName.trim() || "Demo client",
          config_path: configPath.trim() || undefined,
          target_platform_version: targetVersion.trim() || undefined,
          assumptions: {
            monthly_ai_subscription_cost: toNumber(monthlyAiCost),
            hourly_rate: toNumber(hourlyRate),
            manual_review_hours_month: toNumber(reviewHours),
            incident_cost: toNumber(incidentCost),
          },
        })
        .then((r) => r.data),
  })

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <Compass size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Buyer Concierge
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            First-click guidance for role, pain, shortest demo route and buy-now path.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} score={mutation.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Concierge inputs</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <TextField label="Client" value={clientName} onChange={setClientName} />
            <TextField label="EDT/XML path" value={configPath} onChange={setConfigPath} mono />
            <TextField label="Target platform" value={targetVersion} onChange={setTargetVersion} placeholder="8.3.26.x" />
            <div className="grid grid-cols-1 gap-3 rounded-lg border border-border bg-background/60 p-3 sm:grid-cols-2">
              <NumberField label="AI / month" value={monthlyAiCost} onChange={setMonthlyAiCost} />
              <NumberField label="Hourly rate" value={hourlyRate} onChange={setHourlyRate} />
              <NumberField label="Review h/mo" value={reviewHours} onChange={setReviewHours} />
              <NumberField label="Incident cost" value={incidentCost} onChange={setIncidentCost} />
            </div>
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Build concierge
            </button>
            {mutation.data && (
              <button
                onClick={() => downloadText(mutation.data.download_name, mutation.data.markdown)}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:bg-accent"
              >
                <Download size={16} />
                Download markdown
              </button>
            )}
            <BuyerRoomPacketControls monthlyAiCost={monthlyAiCost} />
            <VerificationPacketControls
              buildRequest={buildVerificationPacketRequest}
              fallbackFilename={() => (clientName.trim() || "rentgen") + "-archive-verification-packet.zip"}
            />
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          {!mutation.data && !mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <Compass size={42} className="opacity-30" />
              <p className="text-sm">Waiting for concierge inputs.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Buyer Concierge did not build. Check backend and inputs.</p>
            </div>
          )}

          {mutation.data && <ConciergeReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function ConciergeReport({ report }: { report: BuyerConciergeResponse }) {
  return (
    <div>
      <div className="flex flex-col gap-4 border-b border-border p-4 sm:p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <DecisionIcon status={report.decision.status} />
            <h2 className="break-words text-lg font-bold text-card-foreground sm:text-xl">
              {report.decision.headline}
            </h2>
          </div>
          <p className="mt-2 break-words text-sm text-muted-foreground">{report.orientation.this_is}</p>
        </div>
        <Link
          to={toAppRoute(report.default_next_action.route)}
          className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
        >
          <PlayCircle size={16} />
          {report.default_next_action.label}
        </Link>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-6">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Roles" value={report.summary.persona_cards} icon={Users} />
        <Metric label="Pains" value={report.summary.pain_cards} icon={Map} />
        <Metric label="Paths" value={report.summary.shortest_paths} icon={RouteIcon} />
        <Metric label="Offers" value={report.summary.offer_packages} icon={Target} />
        <Metric label="Trust" value={report.summary.trust_controls} icon={ShieldCheck} />
      </div>

      <div className="border-b border-border p-4 sm:p-5">
        <ConciergeRoomBridge bridge={report.concierge_room_bridge} />
      </div>

      <div className="border-b border-border p-4 sm:p-5">
        <PurchaseRouterPanel router={report.purchase_router} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Role cards" icon={Users}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {report.persona_cards.map((card) => (
                <Link
                  key={card.id}
                  to={toAppRoute(card.start_route)}
                  className="min-w-0 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{card.role}</Badge>
                    <Badge tone="ok">{card.time_to_value_minutes} min</Badge>
                  </div>
                  <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{card.first_question}</p>
                  <p className="mt-2 break-words text-sm text-muted-foreground">{card.spark}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{card.proof}</p>
                  <p className="mt-2 break-words text-sm text-card-foreground">{card.buy_trigger}</p>
                  <p className="mt-2 break-words text-xs font-medium text-primary">{card.purchase_ask}</p>
                  <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{card.proof_file}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Pain picker" icon={Map}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.pain_picker.map((pain) => (
                <Link
                  key={pain.scenario_id}
                  to={toAppRoute(pain.route)}
                  className="rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="warn">{pain.role}</Badge>
                    <Badge tone="muted">{pain.minutes} min</Badge>
                  </div>
                  <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{pain.title}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{pain.pain}</p>
                  <p className="mt-2 break-words text-sm text-card-foreground">{pain.why_now}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Shortest paths" icon={RouteIcon}>
            <div className="space-y-3">
              {report.shortest_paths.map((path) => (
                <div key={path.id} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{path.audience}</Badge>
                    <Badge tone="ok">{path.total_minutes} min</Badge>
                  </div>
                  <h3 className="mt-3 break-words text-sm font-semibold text-card-foreground">{path.title}</h3>
                  <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
                    {path.steps.map((step) => (
                      <Link
                        key={`${path.id}-${step.label}`}
                        to={toAppRoute(step.route)}
                        className="rounded-md border border-border bg-background p-2 text-xs transition hover:bg-accent"
                      >
                        <span className="font-semibold text-card-foreground">{step.label}</span>
                        <span className="ml-2 text-muted-foreground">{step.minutes} min</span>
                        <p className="mt-1 break-words text-muted-foreground">{step.why}</p>
                      </Link>
                    ))}
                  </div>
                  <p className="mt-3 break-words text-sm text-card-foreground">{path.close}</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Default next" icon={Target}>
            <Link
              to={toAppRoute(report.default_next_action.route)}
              className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
            >
              <p className="break-words text-sm font-semibold text-card-foreground">{report.default_next_action.label}</p>
              <p className="mt-2 break-words text-xs text-muted-foreground">{report.default_next_action.reason}</p>
            </Link>
          </Panel>

          <Panel title="Guardrails" icon={AlertTriangle}>
            <div className="space-y-3">
              {report.confusion_guardrails.map((item) => (
                <Link
                  key={item.signal}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
                >
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.signal}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.response}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Exports" icon={Download}>
            <div className="space-y-2">
              {report.exports.map((item) => (
                <Link
                  key={`${item.title}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="flex items-start justify-between gap-3 rounded-lg border border-border bg-background/60 p-2 transition hover:bg-accent"
                >
                  <span className="break-words text-sm font-semibold text-card-foreground">{item.title}</span>
                  <span className="break-all font-mono text-xs text-muted-foreground">{item.filename}</span>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Source signals" icon={Sparkles}>
            <KeyValue values={stringifyValues(report.source_signals)} />
          </Panel>

          <Panel title="Caveats" icon={FileText}>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {report.caveats.map((item) => (
                <li key={item} className="break-words">{item}</li>
              ))}
            </ul>
          </Panel>
        </aside>
      </div>
    </div>
  )
}

function ConciergeRoomBridge({ bridge }: { bridge: BuyerConciergeResponse["concierge_room_bridge"] }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-background/60">
      <div className="flex flex-col gap-3 border-b border-border px-4 py-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Compass size={17} className="text-primary" />
            <h3 className="break-words text-sm font-semibold text-card-foreground sm:text-base">Buyer room map</h3>
            <Badge tone={statusTone(bridge.status)}>{bridge.status}</Badge>
            <Badge tone="muted">{bridge.source}</Badge>
          </div>
          <p className="mt-2 break-words text-sm text-muted-foreground">{bridge.room_line}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link
            to={toAppRoute(bridge.primary_motion.route)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
          >
            <PlayCircle size={15} />
            {bridge.primary_motion.label}
          </Link>
          <Link
            to={toAppRoute(bridge.concierge_motion.route)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-semibold text-card-foreground transition hover:bg-accent"
          >
            <RouteIcon size={15} />
            Concierge
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 p-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(260px,0.9fr)]">
        <div className="min-w-0 space-y-3">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {bridge.role_cards.map((card) => (
              <Link
                key={`${card.role}-${card.route}`}
                to={toAppRoute(card.route)}
                className="rounded-lg border border-border bg-card p-3 transition hover:bg-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={statusTone(card.status)}>{card.title}</Badge>
                  <span className="break-all font-mono text-[11px] text-muted-foreground">{card.proof_file}</span>
                </div>
                <p className="mt-2 break-words text-xs text-muted-foreground">{card.spark}</p>
                {card.purchase_ask && <p className="mt-2 break-words text-xs font-medium text-primary">{card.purchase_ask}</p>}
              </Link>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {bridge.proof_readiness.map((item) => (
              <Link
                key={item.id}
                to={toAppRoute(item.route)}
                className="rounded-lg border border-border bg-card p-3 transition hover:bg-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={statusTone(item.status)}>{item.status}</Badge>
                  <span className="break-all font-mono text-[11px] text-muted-foreground">{item.file}</span>
                </div>
                <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                <p className="mt-1 break-words text-xs text-muted-foreground">{item.signal}</p>
              </Link>
            ))}
          </div>
        </div>

        <div className="min-w-0 space-y-3">
          <OpenFirstPathList path={bridge.open_first_path} toAppRoute={toAppRoute} />
          <div className="rounded-lg border border-border bg-card p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Meeting flow</p>
            <div className="mt-2 space-y-2">
              {bridge.meeting_flow.map((step) => (
                <Link
                  key={`${step.step}-${step.route}`}
                  to={toAppRoute(step.route)}
                  className="block rounded-md border border-border bg-background p-2 transition hover:bg-accent"
                >
                  <p className="break-words text-xs font-semibold text-card-foreground">
                    {step.step}. {step.label}
                  </p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{step.line}</p>
                </Link>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">First files</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {bridge.files.map((file) => (
                <span key={file} className="rounded-md bg-muted px-2 py-1 font-mono text-[11px] text-muted-foreground">
                  {file}
                </span>
              ))}
            </div>
            <p className="mt-3 break-words text-sm font-medium text-card-foreground">{bridge.close_question}</p>
          </div>
        </div>
      </div>
    </section>
  )
}

function PurchaseRouterPanel({ router }: { router: BuyerConciergeResponse["purchase_router"] }) {
  const values = [
    { label: "AI / month", value: router.monthly_ai_rent },
    { label: "3-year AI rent", value: router.three_year_ai_rent },
    { label: "Local license", value: router.local_license_anchor },
    { label: "Break-even", value: router.break_even },
  ]

  return (
    <section className="min-w-0 rounded-lg border border-border bg-background/60">
      <div className="flex flex-col gap-3 border-b border-border px-4 py-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <DollarSign size={17} className="text-primary" />
            <h3 className="break-words text-sm font-semibold text-card-foreground sm:text-base">{router.headline}</h3>
            <Badge tone={router.status === "ready" ? "ok" : "warn"}>{router.status}</Badge>
          </div>
          <p className="mt-2 break-words text-sm text-muted-foreground">{router.buyer_line}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link
            to={toAppRoute(router.primary_route)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
          >
            <PlayCircle size={15} />
            {router.primary_label}
          </Link>
          <Link
            to={toAppRoute(router.recommended_route)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-semibold text-card-foreground transition hover:bg-accent"
          >
            <Target size={15} />
            Purchase
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-0 border-b border-border sm:grid-cols-2 lg:grid-cols-4">
        {values.map((item) => (
          <PurchaseValue key={item.label} label={item.label} value={item.value} />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {router.quick_actions.map((item) => (
              <Link
                key={`${item.label}-${item.route}`}
                to={toAppRoute(item.route)}
                className="rounded-lg border border-border bg-card p-3 transition hover:bg-accent"
              >
                <p className="break-words text-sm font-semibold text-card-foreground">{item.label}</p>
                <p className="mt-1 break-words text-xs text-muted-foreground">{item.why}</p>
              </Link>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2">
            {router.role_prompts.map((item) => (
              <Link
                key={`${item.role}-${item.route}`}
                to={toAppRoute(item.route)}
                className="rounded-lg border border-border bg-card p-3 transition hover:bg-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="muted">{item.role}</Badge>
                  <span className="break-all font-mono text-[11px] text-muted-foreground">{item.proof_file}</span>
                </div>
                <p className="mt-2 break-words text-xs text-muted-foreground">{item.ask}</p>
                <p className="mt-2 break-words text-sm font-medium text-card-foreground">{item.close}</p>
              </Link>
            ))}
          </div>
        </div>

        <div className="min-w-0 space-y-3">
          <div className="rounded-lg border border-border bg-card p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Recommended</p>
            <p className="mt-1 break-words text-sm font-semibold text-card-foreground">{router.recommended_purchase}</p>
            <p className="mt-2 break-words text-xs text-muted-foreground">{router.commercial_frame}</p>
            <p className="mt-2 break-words text-xs text-muted-foreground">{router.first_invoice_trigger}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Close sequence</p>
            <div className="mt-2 space-y-2">
              {router.close_sequence.map((item) => (
                <Link
                  key={`${item.window}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="block rounded-md border border-border bg-background p-2 transition hover:bg-accent"
                >
                  <p className="break-words text-xs font-semibold text-card-foreground">{item.window} - {item.owner}</p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{item.action}</p>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
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

function NumberField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value.replace(/[^\d]/g, ""))}
        inputMode="numeric"
        className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary"
      />
    </label>
  )
}

function Panel({ title, icon: Icon, children }: { title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Icon size={17} className="text-primary" />
        <h3 className="text-sm font-semibold text-card-foreground">{title}</h3>
      </div>
      <div className="p-4">{children}</div>
    </section>
  )
}

function Metric({ label, value, icon: Icon }: { label: string; value: number | string; icon: LucideIcon }) {
  return (
    <div className="min-w-0 border-b border-r border-border p-4 md:border-b-0">
      <div className="flex items-center gap-2 text-xs font-medium uppercase text-muted-foreground">
        <Icon size={15} />
        <span>{label}</span>
      </div>
      <div className="mt-1 break-words text-lg font-bold text-card-foreground sm:text-xl">
        {typeof value === "number" ? nf.format(value) : value}
      </div>
    </div>
  )
}

function PurchaseValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-b border-border p-3 last:border-b-0 sm:border-r sm:last:border-r-0 lg:border-b-0">
      <p className="text-[11px] font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-bold text-card-foreground sm:text-base">{value}</p>
    </div>
  )
}

function KeyValue({ values }: { values: Record<string, string> }) {
  return (
    <div className="space-y-2">
      {Object.entries(values).map(([key, value]) => (
        <div key={key} className="flex items-start justify-between gap-3 border-b border-border pb-2 last:border-b-0 last:pb-0">
          <span className="text-xs font-semibold uppercase text-muted-foreground">{key}</span>
          <span className="break-words text-right text-sm font-medium text-card-foreground">{value}</span>
        </div>
      ))}
    </div>
  )
}

function StatusBadge({ status, score }: { status: string; score: number }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2">
      <DecisionIcon status={status} />
      <div>
        <p className="text-xs font-medium uppercase text-muted-foreground">{status}</p>
        <p className="text-sm font-bold text-card-foreground">Score {score}</p>
      </div>
    </div>
  )
}

function DecisionIcon({ status }: { status: string }) {
  if (status === "ready") return <CheckCircle2 size={20} className="shrink-0 text-emerald-600" />
  if (status === "risk" || status === "fail" || status === "blocked") {
    return <XCircle size={20} className="shrink-0 text-destructive" />
  }
  return <AlertTriangle size={20} className="shrink-0 text-amber-600" />
}

function Badge({ tone, children }: { tone: "ok" | "warn" | "danger" | "muted"; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center rounded-md px-2 py-1 text-xs font-semibold",
        tone === "ok" && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
        tone === "warn" && "bg-amber-500/10 text-amber-700 dark:text-amber-300",
        tone === "danger" && "bg-destructive/10 text-destructive",
        tone === "muted" && "bg-muted text-muted-foreground",
      )}
    >
      {children}
    </span>
  )
}

function statusTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "ready" || status === "pass") return "ok"
  if (status === "risk" || status === "fail" || status === "blocked" || status === "critical") return "danger"
  if (status === "watch" || status === "review_required") return "warn"
  return "muted"
}

function toNumber(value: string): number | undefined {
  if (!value.trim()) return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function stringifyValues(values: Record<string, string | number | boolean | null>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(values).map(([key, value]) => [key, value === null ? "" : String(value)]),
  )
}
