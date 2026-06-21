import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  Briefcase,
  CheckCircle2,
  ClipboardCheck,
  DollarSign,
  Download,
  FileText,
  Loader2,
  PackageCheck,
  RefreshCw,
  ShieldCheck,
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
  commercialOfferStudioApi,
  type CommercialOfferStudioResponse,
  type EvidenceBundleRequest,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/commercial-offer-studio")({
  component: CommercialOfferStudioPage,
})

const nf = new Intl.NumberFormat("ru-RU")

type AppRoute =
  | "/"
  | "/board-pack"
  | "/outcome-ledger"
  | "/buyer-concierge"
  | "/commercial-offer-studio"
  | "/enterprise-trust-center"
  | "/demo-command-center"
  | "/killer-demo"
  | "/pilot-launchpad"
  | "/scenario-hub"
  | "/guided-demo"
  | "/business-case"
  | "/productization"
  | "/approvals"
  | "/audit"
  | "/quality"
  | "/release-readiness"
  | "/architecture"
  | "/offline-readiness"
  | "/platform-doctor"
  | "/vendor-portfolio"
  | "/rights-rls"
  | "/value-packs"
  | "/evidence-bundle"

const appRoutes = [
  "/",
  "/board-pack",
  "/outcome-ledger",
  "/buyer-concierge",
  "/commercial-offer-studio",
  "/enterprise-trust-center",
  "/demo-command-center",
  "/killer-demo",
  "/pilot-launchpad",
  "/scenario-hub",
  "/guided-demo",
  "/business-case",
  "/productization",
  "/approvals",
  "/audit",
  "/quality",
  "/release-readiness",
  "/architecture",
  "/offline-readiness",
  "/platform-doctor",
  "/vendor-portfolio",
  "/rights-rls",
  "/value-packs",
  "/evidence-bundle",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/commercial-offer-studio"
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

function CommercialOfferStudioPage() {
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
    include_commercial_offer_studio: true,
    include_killer_demo: true,
  })

  const mutation = useMutation({
    mutationFn: () =>
      commercialOfferStudioApi
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
              <Briefcase size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Commercial Offer Studio
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Buyable packages, value-based price anchors, stakeholder close lines and proposal artifacts for a local 1C product purchase.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} score={mutation.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Offer inputs</h2>
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
              Build offer studio
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
              <Briefcase size={42} className="opacity-30" />
              <p className="text-sm">Waiting for offer inputs.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Commercial Offer Studio did not build. Check backend and inputs.</p>
            </div>
          )}

          {mutation.data && <OfferReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function OfferReport({ report }: { report: CommercialOfferStudioResponse }) {
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
          <p className="mt-2 break-words text-sm text-muted-foreground">
            Value anchor: {nf.format(report.summary.first_year_visible_value)} {report.summary.currency}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-6">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Offers" value={report.summary.offers} icon={PackageCheck} />
        <Metric label="Tiers" value={report.summary.pricing_tiers} icon={DollarSign} />
        <Metric label="Value" value={report.summary.first_year_visible_value} icon={Target} />
        <Metric label="Trust" value={report.summary.trust_score} icon={ShieldCheck} />
        <Metric label="Pilot" value={report.summary.pilot_score} icon={ClipboardCheck} />
        <Metric label="Close" value={report.summary.close_ready ? "ready" : "hold"} icon={Target} />
        <Metric label="Checkout" value={report.summary.checkout_gates} icon={CheckCircle2} />
      </div>

      <OfferRoomBridge report={report} />
      <ProcurementDossier report={report} />
      <ClosePacket report={report} />

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Offers" icon={PackageCheck}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {report.offers.map((offer) => (
                <Link
                  key={offer.id}
                  to={toAppRoute(offer.route)}
                  className="min-w-0 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{offer.buyer}</Badge>
                    <Badge tone="ok">{offer.commercial_frame}</Badge>
                  </div>
                  <h3 className="mt-3 break-words text-sm font-semibold text-card-foreground">{offer.title}</h3>
                  <p className="mt-2 break-words text-sm text-card-foreground">{offer.why_buy}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{offer.acceptance}</p>
                  <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
                    {offer.includes.map((item) => (
                      <li key={item} className="break-words">{item}</li>
                    ))}
                  </ul>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Pricing ladder" icon={DollarSign}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.pricing_ladder.map((tier) => (
                <div key={tier.tier} className="rounded-lg border border-border bg-background/60 p-3">
                  <Badge tone="muted">{tier.tier}</Badge>
                  <p className="mt-3 break-words text-lg font-bold text-card-foreground">{tier.anchor}</p>
                  <p className="mt-2 break-words text-sm text-card-foreground">{tier.logic}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{tier.replaces}</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Buy-now path" icon={Target}>
            <div className="space-y-3">
              {report.buy_now_path.map((item, index) => (
                <Link
                  key={`${item.step}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="grid min-w-0 grid-cols-[34px_minmax(0,1fr)] gap-3 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-xs font-bold text-primary">
                    {index + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap gap-2">
                      <Badge tone="muted">{item.owner}</Badge>
                      <Badge tone="muted">{item.step}</Badge>
                    </div>
                    <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{item.exit}</p>
                  </div>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Stakeholder closers" icon={Users}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.stakeholder_closers.map((item) => (
                <Link
                  key={item.role}
                  to={toAppRoute(item.proof_route)}
                  className="rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <Badge tone="muted">{item.role}</Badge>
                  <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{item.buy_trigger}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.close_line}</p>
                </Link>
              ))}
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Deal risks" icon={AlertTriangle}>
            <div className="space-y-3">
              {report.deal_risks.map((item) => (
                <Link
                  key={`${item.route}-${item.risk}`}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
                >
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.risk}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.mitigation}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Proposal sections" icon={FileText}>
            <div className="space-y-2">
              {report.proposal_sections.map((item) => (
                <Link
                  key={item.title}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-2 transition hover:bg-accent"
                >
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{item.content}</p>
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

          <Panel title="Source signals" icon={Briefcase}>
            <KeyValue values={stringifyValues(report.source_signals)} />
          </Panel>

          <Panel title="Caveats" icon={AlertTriangle}>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {report.caveats.map((item) => (
                <li key={item} className="break-words">{item}</li>
              ))}
            </ul>
          </Panel>

          <Panel title="Markdown preview" icon={FileText}>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {report.markdown}
            </pre>
          </Panel>
        </aside>
      </div>
    </div>
  )
}

function OfferRoomBridge({ report }: { report: CommercialOfferStudioResponse }) {
  const bridge = report.offer_room_bridge

  return (
    <div className="border-b border-border p-4 sm:p-5">
      <Panel title="Offer room bridge" icon={Users}>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <div className="flex flex-wrap gap-2">
              <Badge tone={statusTone(bridge.status)}>{bridge.status}</Badge>
              <Badge tone="muted">Score {bridge.score}</Badge>
              <Badge tone="muted">{bridge.source}</Badge>
            </div>
            <h3 className="mt-3 break-words text-base font-bold text-card-foreground">{bridge.room_line}</h3>
            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
              <Link
                to={toAppRoute(bridge.primary_motion.route)}
                className="min-w-0 rounded-lg border border-primary/30 bg-primary/10 p-3 transition hover:border-primary hover:bg-primary/15"
              >
                <Badge tone={statusTone(bridge.primary_motion.status)}>{bridge.primary_motion.status}</Badge>
                <p className="mt-3 break-words text-sm font-semibold text-card-foreground">
                  {bridge.primary_motion.label}
                </p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{bridge.primary_motion.ask}</p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{bridge.primary_motion.reason}</p>
              </Link>
              <Link
                to={toAppRoute(bridge.recommended_purchase.route)}
                className="min-w-0 rounded-lg border border-border bg-muted p-3 transition hover:bg-accent"
              >
                <Badge tone="ok">Recommended purchase</Badge>
                <p className="mt-3 break-words text-sm font-semibold text-card-foreground">
                  {bridge.recommended_purchase.title}
                </p>
                <p className="mt-2 break-words text-xs text-muted-foreground">
                  {bridge.recommended_purchase.commercial_frame}
                </p>
                <p className="mt-2 break-words text-xs text-muted-foreground">
                  {bridge.recommended_purchase.acceptance}
                </p>
              </Link>
            </div>
          </div>

          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Files to forward first</p>
            <div className="mt-3 space-y-2">
              {bridge.files.map((file) => (
                <div key={file} className="break-all rounded-md bg-muted p-2 font-mono text-xs text-card-foreground">
                  {file}
                </div>
              ))}
            </div>
            <p className="mt-4 break-words text-sm font-semibold text-card-foreground">{bridge.close_question}</p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Role cards</p>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
              {bridge.role_cards.map((item) => (
                <Link
                  key={`${item.role}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="rounded-md bg-muted p-2 transition hover:bg-accent"
                >
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={statusTone(item.status)}>{item.title || item.role}</Badge>
                    <Badge tone="muted">{item.proof_file}</Badge>
                  </div>
                  <p className="mt-2 break-words text-xs text-card-foreground">{item.spark}</p>
                  {item.close_line && (
                    <p className="mt-2 break-words text-xs text-muted-foreground">{item.close_line}</p>
                  )}
                </Link>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Proof readiness</p>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
              {bridge.proof_readiness.map((item) => (
                <Link
                  key={`${item.id}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="rounded-md bg-muted p-2 transition hover:bg-accent"
                >
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={statusTone(item.status)}>{item.title}</Badge>
                    <Badge tone="muted">{item.file}</Badge>
                  </div>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.signal}</p>
                </Link>
              ))}
            </div>
          </div>
        </div>

        <OpenFirstPathList path={bridge.open_first_path} toAppRoute={toAppRoute} className="mt-4" itemClassName="bg-muted" />

        <div className="mt-4 rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Meeting flow</p>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
            {bridge.meeting_flow.map((item) => (
              <Link
                key={`${item.step}-${item.route}`}
                to={toAppRoute(item.route)}
                className="grid min-w-0 grid-cols-[30px_minmax(0,1fr)] gap-2 rounded-md bg-muted p-2 transition hover:bg-accent"
              >
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
                  {item.step}
                </div>
                <div className="min-w-0">
                  <p className="break-words text-xs font-semibold text-card-foreground">{item.label}</p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{item.line}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </Panel>
    </div>
  )
}

function ClosePacket({ report }: { report: CommercialOfferStudioResponse }) {
  const close = report.close_packet
  return (
    <div className="border-b border-border p-4 sm:p-5">
      <Panel title="Close packet" icon={Target}>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <div className="flex flex-wrap gap-2">
              <Badge tone={close.ready_to_close ? "ok" : "warn"}>{close.ready_to_close ? "ready to ask" : "hold quote"}</Badge>
              <Badge tone="muted">{close.close_mode}</Badge>
            </div>
            <h3 className="mt-3 break-words text-base font-bold text-card-foreground">{close.primary_ask}</h3>
            <Link
              to={toAppRoute(close.one_page_order.route)}
              className="mt-3 inline-flex max-w-full items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
            >
              <PackageCheck size={15} />
              <span className="break-words">{close.one_page_order.recommended_purchase}</span>
            </Link>
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Small label="Value anchor" value={close.one_page_order.value_anchor} />
              <Small label="AI rent" value={close.one_page_order.ai_rent_baseline} />
              <Small label="3-year rent" value={close.one_page_order.three_year_ai_rent || "n/a"} />
              <Small label="Local license" value={close.one_page_order.local_license_anchor || "n/a"} />
              <Small label="Break-even" value={close.one_page_order.break_even || "n/a"} />
              <Small label="Frame" value={close.one_page_order.commercial_frame} />
              <Small label="Invoice trigger" value={close.one_page_order.first_invoice_trigger} />
            </div>
          </div>

          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Checkout gates</p>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
              {close.checkout.map((item) => (
                <Link
                  key={`${item.gate}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="rounded-md bg-muted p-2 transition hover:bg-accent"
                >
                  <p className="break-words text-xs font-semibold text-card-foreground">{item.gate}</p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{item.evidence}</p>
                </Link>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Mutual action plan</p>
            <div className="mt-3 space-y-2">
              {close.mutual_action_plan.map((item, index) => (
                <Link
                  key={`${item.window}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="grid min-w-0 grid-cols-[30px_minmax(0,1fr)] gap-3 rounded-md bg-muted p-2 transition hover:bg-accent"
                >
                  <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
                    {index + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap gap-2">
                      <Badge tone="muted">{item.window}</Badge>
                      <Badge tone="muted">{item.owner}</Badge>
                    </div>
                    <p className="mt-2 break-words text-xs font-semibold text-card-foreground">{item.action}</p>
                    <p className="mt-1 break-words text-xs text-muted-foreground">{item.exit}</p>
                  </div>
                </Link>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Buyer commitments</p>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
              {close.buyer_commitments.map((item) => (
                <Link
                  key={`${item.role}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="rounded-md bg-muted p-2 transition hover:bg-accent"
                >
                  <Badge tone="warn">{item.role}</Badge>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.commitment}</p>
                </Link>
              ))}
            </div>
            <p className="mt-4 text-xs font-semibold uppercase text-muted-foreground">Close script</p>
            <div className="mt-3 space-y-2">
              {close.close_script.map((item) => (
                <div key={item} className="rounded-md bg-muted p-2 text-xs text-card-foreground">
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Evidence requirements</p>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            {close.evidence_requirements.map((item) => (
              <Link
                key={`${item.artifact}-${item.route}`}
                to={toAppRoute(item.route)}
                className="rounded-md bg-muted p-2 transition hover:bg-accent"
              >
                <p className="break-words text-xs font-semibold text-card-foreground">{item.artifact}</p>
                <p className="mt-1 break-words text-xs text-muted-foreground">{item.why}</p>
              </Link>
            ))}
          </div>
        </div>
      </Panel>
    </div>
  )
}

function ProcurementDossier({ report }: { report: CommercialOfferStudioResponse }) {
  const dossier = report.procurement_dossier

  return (
    <div className="border-b border-border p-4 sm:p-5">
      <Panel title="Procurement dossier" icon={Briefcase}>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <Badge tone="ok">Recommended</Badge>
            <p className="mt-3 break-words text-base font-bold text-card-foreground">
              {dossier.headline}
            </p>
            <Link
              to={toAppRoute(dossier.recommended_purchase.route)}
              className="mt-3 inline-flex max-w-full items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
            >
              <PackageCheck size={15} />
              <span className="break-words">{dossier.recommended_purchase.title}</span>
            </Link>
            <p className="mt-3 break-words text-sm text-card-foreground">
              {dossier.recommended_purchase.commercial_frame}
            </p>
            <p className="mt-2 break-words text-xs text-muted-foreground">
              {dossier.recommended_purchase.acceptance}
            </p>
          </div>
          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Local asset case</p>
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-md bg-muted p-3">
                <p className="text-xs font-semibold uppercase text-muted-foreground">Local value</p>
                <p className="mt-1 break-words text-lg font-bold text-card-foreground">
                  {dossier.subscription_escape.local_value_anchor}
                </p>
              </div>
              <div className="rounded-md bg-muted p-3">
                <p className="text-xs font-semibold uppercase text-muted-foreground">AI rent</p>
                <p className="mt-1 break-words text-lg font-bold text-card-foreground">
                  {dossier.subscription_escape.annual_ai_rent}
                </p>
              </div>
              <div className="rounded-md bg-muted p-3">
                <p className="text-xs font-semibold uppercase text-muted-foreground">3-year rent</p>
                <p className="mt-1 break-words text-lg font-bold text-card-foreground">
                  {dossier.subscription_escape.three_year_ai_rent || "n/a"}
                </p>
              </div>
              <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
                <p className="text-xs font-semibold uppercase text-primary">Local license</p>
                <p className="mt-1 break-words text-lg font-bold text-primary">
                  {dossier.subscription_escape.local_license_anchor || "n/a"}
                </p>
              </div>
            </div>
            <p className="mt-3 break-words text-sm text-muted-foreground">
              {dossier.subscription_escape.line}
            </p>
            {dossier.subscription_escape.decision_line && (
              <p className="mt-2 break-words text-sm font-medium text-card-foreground">
                {dossier.subscription_escape.decision_line}
              </p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge tone="muted">{dossier.subscription_escape.break_even_months ?? 0} month break-even</Badge>
              <Badge tone="muted">{dossier.subscription_escape.ai_rent_equivalent_months ?? 0} AI-rent months</Badge>
            </div>
            {(dossier.subscription_escape.guardrails || []).length > 0 && (
              <div className="mt-3 grid grid-cols-1 gap-2">
                {(dossier.subscription_escape.guardrails || []).map((item) => (
                  <div key={item} className="rounded-md bg-muted p-2 text-xs text-muted-foreground">
                    {item}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Procurement pack</p>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
              {dossier.procurement_pack.map((item) => (
                <Link
                  key={`${item.owner}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="rounded-md bg-muted p-2 transition hover:bg-accent"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{item.owner}</Badge>
                    <span className="break-words text-xs font-semibold text-card-foreground">{item.artifact}</span>
                  </div>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.exit_criteria}</p>
                </Link>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Red lines</p>
            <div className="mt-3 space-y-2">
              {dossier.red_lines.map((item) => (
                <div key={item} className="flex gap-2 rounded-md bg-muted p-2 text-xs text-muted-foreground">
                  <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-600" />
                  <span className="break-words">{item}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 break-words text-sm font-semibold text-card-foreground">
              {dossier.close_question}
            </p>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">License model</p>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
            {dossier.license_model.map((item) => (
              <div key={item.model} className="rounded-md bg-muted p-2">
                <p className="break-words text-xs font-semibold text-card-foreground">{item.model}</p>
                <p className="mt-1 break-words text-xs text-muted-foreground">{item.buyer}</p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{item.why}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          {dossier.approval_matrix.map((item) => (
            <Link
              key={`${item.role}-${item.route}`}
              to={toAppRoute(item.route)}
              className="rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
            >
              <Badge tone="warn">{item.role}</Badge>
              <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{item.must_accept}</p>
              <p className="mt-2 break-words text-xs text-muted-foreground">{item.blocker_if_missing}</p>
            </Link>
          ))}
        </div>
      </Panel>
    </div>
  )
}

function Small({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md bg-muted p-3">
      <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-card-foreground">{value}</p>
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
  if (status === "watch") return "warn"
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
