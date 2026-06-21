import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileCheck2,
  FileText,
  Loader2,
  Map,
  PackageCheck,
  PlayCircle,
  RefreshCw,
  Rocket,
  ShieldCheck,
  Target,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  pilotLaunchpadApi,
  type EvidenceBundleRequest,
  type PilotLaunchpadResponse,
} from "@/lib/api-client"
import { BuyerRoomPacketControls } from "@/components/BuyerRoomPacketControls"
import { OpenFirstPathList } from "@/components/OpenFirstPathList"
import { VerificationPacketControls } from "@/components/VerificationPacketControls"

export const Route = createFileRoute("/_authenticated/pilot-launchpad")({
  component: PilotLaunchpadPage,
})

const nf = new Intl.NumberFormat("ru-RU")

type AppRoute =
  | "/"
  | "/buyer-concierge"
  | "/commercial-offer-studio"
  | "/enterprise-trust-center"
  | "/outcome-ledger"
  | "/demo-command-center"
  | "/killer-demo"
  | "/pilot-launchpad"
  | "/scenario-hub"
  | "/guided-demo"
  | "/business-case"
  | "/productization"
  | "/configurations"
  | "/quality"
  | "/change"
  | "/testing"
  | "/release-readiness"
  | "/architecture"
  | "/metadata"
  | "/team-governance"
  | "/offline-readiness"
  | "/operations"
  | "/lock-radar"
  | "/extension-safety"
  | "/platform-doctor"
  | "/vendor-portfolio"
  | "/update-war-room"
  | "/rights-rls"
  | "/value-packs"
  | "/approvals"
  | "/audit"
  | "/evidence-bundle"
  | "/security"

const appRoutes = [
  "/",
  "/buyer-concierge",
  "/commercial-offer-studio",
  "/enterprise-trust-center",
  "/outcome-ledger",
  "/demo-command-center",
  "/killer-demo",
  "/pilot-launchpad",
  "/scenario-hub",
  "/guided-demo",
  "/business-case",
  "/productization",
  "/configurations",
  "/quality",
  "/change",
  "/testing",
  "/release-readiness",
  "/architecture",
  "/metadata",
  "/team-governance",
  "/offline-readiness",
  "/operations",
  "/lock-radar",
  "/extension-safety",
  "/platform-doctor",
  "/vendor-portfolio",
  "/update-war-room",
  "/rights-rls",
  "/value-packs",
  "/approvals",
  "/audit",
  "/evidence-bundle",
  "/security",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/pilot-launchpad"
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

function PilotLaunchpadPage() {
  const [clientName, setClientName] = useState("Demo client")
  const [configPath, setConfigPath] = useState("data/configs/unpacked")
  const [targetVersion, setTargetVersion] = useState("")
  const [monthlyAiCost, setMonthlyAiCost] = useState("120000")
  const [hourlyRate, setHourlyRate] = useState("2500")
  const [reviewHours, setReviewHours] = useState("80")
  const [incidentCost, setIncidentCost] = useState("300000")
  const buildRequest = () => ({
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

  const buildVerificationPacketRequest = (): EvidenceBundleRequest => ({
    ...buildRequest(),
    include_killer_demo: true,
    include_pilot_launchpad: true,
    include_outcome_ledger: true,
  })

  const mutation = useMutation({
    mutationFn: () =>
      pilotLaunchpadApi
        .build(buildRequest())
        .then((r) => r.data),
  })
  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <Rocket size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Pilot Launchpad
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Buyer pilot offers, acceptance checks and procurement artifacts from local 1C Rentgen evidence.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} score={mutation.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Pilot inputs</h2>
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
              Build launchpad
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
              fallbackFilename={() =>
                `${mutation.data?.client.name || clientName.trim() || "rentgen"}-archive-verification-packet.zip`
              }
            />
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          {!mutation.data && !mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <Rocket size={42} className="opacity-30" />
              <p className="text-sm">Waiting for pilot inputs.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Pilot Launchpad did not build. Check backend and inputs.</p>
            </div>
          )}

          {mutation.data && <PilotLaunchpadReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function PilotLaunchpadReport({ report }: { report: PilotLaunchpadResponse }) {
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
            {report.client.name}
            {report.client.target_platform_version ? ` -> ${report.client.target_platform_version}` : ""}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-4 xl:grid-cols-9">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Days" value={report.summary.pilot_days} icon={Rocket} />
        <Metric label="Offers" value={report.summary.offers} icon={PackageCheck} />
        <Metric label="Stages" value={report.summary.stages} icon={PlayCircle} />
        <Metric label="Checks" value={report.summary.acceptance_checks} icon={ClipboardCheck} />
        <Metric label="Activate" value={report.summary.activation_ready ? "ready" : "hold"} icon={Target} />
        <Metric label="Gates" value={report.summary.activation_gates} icon={ShieldCheck} />
        <Metric label="Procure" value={report.summary.procurement_items} icon={FileText} />
        <Metric label="Sign" value={report.summary.acceptance_register_ready ? "ready" : "hold"} icon={FileCheck2} />
      </div>

      <PilotRoomBridge report={report} />

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Pilot offers" icon={PackageCheck}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {report.pilot_offers.map((offer) => (
                <Link
                  key={offer.id}
                  to={toAppRoute(offer.route)}
                  className="min-w-0 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{offer.duration}</Badge>
                    <Badge tone="muted">{offer.buyer}</Badge>
                  </div>
                  <h3 className="mt-3 break-words text-sm font-semibold text-card-foreground">{offer.title}</h3>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{offer.price_frame}</p>
                  <p className="mt-2 break-words text-sm text-card-foreground">{offer.acceptance}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{offer.why_buy}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <ActivationContract report={report} />
          <AcceptanceRegister report={report} />

          <Panel title="Day plan" icon={PlayCircle}>
            <div className="space-y-3">
              {report.day_plan.map((item) => (
                <div key={item.window} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="ok">{item.window}</Badge>
                    <span className="text-xs font-semibold uppercase text-muted-foreground">{item.owner}</span>
                  </div>
                  <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{item.goal}</p>
                  <ul className="mt-3 grid grid-cols-1 gap-1.5 text-sm text-muted-foreground md:grid-cols-2">
                    {item.actions.map((action) => (
                      <li key={action} className="break-words">{action}</li>
                    ))}
                  </ul>
                  <p className="mt-3 break-words text-xs text-muted-foreground">{item.exit_criteria}</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Acceptance matrix" icon={ClipboardCheck}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.acceptance_matrix.map((item) => (
                <Link
                  key={item.role}
                  to={toAppRoute(item.proof_route)}
                  className="rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{item.role}</Badge>
                    <Badge tone="muted">{item.scenario_id}</Badge>
                  </div>
                  <p className="mt-3 break-words text-sm text-card-foreground">{item.must_believe}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.pass_criteria}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Procurement pack" icon={ShieldCheck}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.procurement_pack.map((item) => (
                <Link
                  key={`${item.owner}-${item.artifact}`}
                  to={toAppRoute(item.route)}
                  className="rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{item.owner}</Badge>
                    <span className="text-xs font-semibold uppercase text-muted-foreground">{item.artifact}</span>
                  </div>
                  <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{item.question}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.answer}</p>
                </Link>
              ))}
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Risk burndown" icon={Target}>
            <div className="space-y-3">
              {report.risk_burndown.map((item) => (
                <Link
                  key={item.scenario_id}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
                >
                  <Badge tone="warn">{item.scenario_id}</Badge>
                  <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{item.buyer_risk}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.close_action}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Close script" icon={Map}>
            <ol className="space-y-2 text-sm text-muted-foreground">
              {report.close_script.map((item, index) => (
                <li key={item} className="grid grid-cols-[26px_minmax(0,1fr)] gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
                    {index + 1}
                  </span>
                  <span className="break-words">{item}</span>
                </li>
              ))}
            </ol>
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

          <Panel title="Source signals" icon={FileText}>
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

function PilotRoomBridge({ report }: { report: PilotLaunchpadResponse }) {
  const bridge = report.pilot_room_bridge

  return (
    <div className="border-b border-border p-4 sm:p-5">
      <Panel title="Pilot room bridge" icon={Map}>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <div className="flex flex-wrap gap-2">
              <Badge tone={registerStatusTone(bridge.status)}>{bridge.status}</Badge>
              <Badge tone="muted">Score {bridge.score}</Badge>
              <Badge tone="muted">{bridge.source}</Badge>
            </div>
            <h3 className="mt-3 break-words text-base font-bold text-card-foreground">{bridge.room_line}</h3>
            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
              <Link
                to={toAppRoute(bridge.primary_motion.route)}
                className="rounded-lg border border-primary/30 bg-primary/10 p-3 transition hover:border-primary hover:bg-primary/15"
              >
                <Badge tone={registerStatusTone(bridge.primary_motion.status)}>{bridge.primary_motion.status}</Badge>
                <p className="mt-3 break-words text-sm font-semibold text-card-foreground">
                  {bridge.primary_motion.label}
                </p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{bridge.primary_motion.ask}</p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{bridge.primary_motion.reason}</p>
              </Link>
              <Link
                to={toAppRoute(bridge.activation_motion.route)}
                className="rounded-lg border border-border bg-muted p-3 transition hover:bg-accent"
              >
                <Badge tone={registerStatusTone(bridge.activation_motion.status)}>Activation</Badge>
                <p className="mt-3 break-words text-sm font-semibold text-card-foreground">
                  {bridge.activation_motion.label}
                </p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{bridge.activation_motion.ask}</p>
                <p className="mt-2 break-words text-xs text-muted-foreground">
                  {bridge.activation_motion.invoice_trigger}
                </p>
              </Link>
            </div>
          </div>

          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Files to start with</p>
            <div className="mt-3 space-y-2">
              {bridge.files.map((file) => (
                <div key={file} className="break-all rounded-md bg-muted p-2 font-mono text-xs text-card-foreground">
                  {file}
                </div>
              ))}
            </div>
            <p className="mt-4 break-words text-sm font-semibold text-card-foreground">{bridge.activation_question}</p>
          </div>
        </div>

        <OpenFirstPathList path={bridge.open_first_path} toAppRoute={toAppRoute} className="mt-4" itemClassName="bg-muted" />

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
                    <Badge tone={registerStatusTone(item.status)}>{item.title || item.role}</Badge>
                    <Badge tone="muted">{item.proof_file}</Badge>
                  </div>
                  <p className="mt-2 break-words text-xs text-card-foreground">{item.spark}</p>
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
                    <Badge tone={registerStatusTone(item.status)}>{item.title}</Badge>
                    <Badge tone="muted">{item.file}</Badge>
                  </div>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.signal}</p>
                </Link>
              ))}
            </div>
          </div>
        </div>

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

function ActivationContract({ report }: { report: PilotLaunchpadResponse }) {
  const activation = report.activation_contract

  return (
    <Panel title="Activation contract" icon={Target}>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
          <div className="flex flex-wrap gap-2">
            <Badge tone={activation.ready_to_activate ? "ok" : "warn"}>
              {activation.ready_to_activate ? "ready to start" : "hold rollout"}
            </Badge>
            <Badge tone="muted">{activation.selected_offer_id || "selected offer"}</Badge>
          </div>
          <h3 className="mt-3 break-words text-base font-bold text-card-foreground">{activation.primary_ask}</h3>
          <Link
            to={toAppRoute(activation.start_route)}
            className="mt-3 inline-flex max-w-full items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
          >
            <PackageCheck size={15} />
            <span className="break-words">{activation.selected_offer_title}</span>
          </Link>
          <p className="mt-3 break-words text-sm text-card-foreground">{activation.activation_line}</p>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <SmallValue label="Frame" value={activation.commercial_frame} />
            <SmallValue label="Invoice trigger" value={activation.invoice_trigger} />
          </div>
        </div>

        <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Activation gates</p>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            {activation.gates.map((item) => (
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
          {activation.handoff_files.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-semibold uppercase text-muted-foreground">Post-demo handoff files</p>
              <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                {activation.handoff_files.map((item) => (
                  <Link
                    key={`${item.route}-${item.filename}`}
                    to={toAppRoute(item.route)}
                    className="rounded-md bg-card p-2 transition hover:bg-accent"
                  >
                    <p className="break-words text-xs font-semibold text-card-foreground">{item.title}</p>
                    <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">{item.filename}</p>
                    <p className="mt-1 break-words text-xs text-muted-foreground">{item.reason}</p>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Milestones</p>
          <div className="mt-3 space-y-2">
            {activation.milestones.map((item) => (
              <Link
                key={`${item.window}-${item.route}`}
                to={toAppRoute(item.route)}
                className="block rounded-md bg-muted p-2 transition hover:bg-accent"
              >
                <div className="flex flex-wrap gap-2">
                  <Badge tone="muted">{item.window}</Badge>
                  <Badge tone="muted">{item.owner}</Badge>
                </div>
                <p className="mt-2 break-words text-xs text-muted-foreground">{item.acceptance}</p>
              </Link>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Buyer commitments</p>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            {activation.buyer_commitments.map((item) => (
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
        </div>
      </div>
    </Panel>
  )
}

function AcceptanceRegister({ report }: { report: PilotLaunchpadResponse }) {
  const register = report.acceptance_register

  return (
    <Panel title="Acceptance register" icon={FileCheck2}>
      <div className="rounded-lg border border-border bg-background/60 p-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={register.ready_to_sign ? "ok" : "danger"}>
                {register.ready_to_sign ? "ready to sign" : "blocked"}
              </Badge>
              <Badge tone="ok">{register.ready_items} ready</Badge>
              <Badge tone="warn">{register.watch_items} watch</Badge>
              <Badge tone={register.blocked_items ? "danger" : "muted"}>{register.blocked_items} blocked</Badge>
            </div>
            <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{register.owner_line}</p>
          </div>
          <Link
            to="/evidence-bundle"
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm font-semibold text-card-foreground transition hover:bg-accent"
          >
            <Download size={15} />
            Evidence Bundle
          </Link>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
        {register.items.map((item) => (
          <div key={item.id} className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="muted">{item.window}</Badge>
              <Badge tone={registerStatusTone(item.status)}>{item.status}</Badge>
              <span className="text-xs font-semibold uppercase text-muted-foreground">{item.owner}</span>
            </div>
            <h3 className="mt-3 break-words text-sm font-semibold text-card-foreground">{item.role}</h3>
            <p className="mt-2 break-words text-sm text-card-foreground">{item.decision}</p>
            <p className="mt-2 break-words text-xs text-muted-foreground">{item.acceptance}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link
                to={toAppRoute(item.evidence_route)}
                className="inline-flex max-w-full items-center gap-1 rounded-md bg-primary/10 px-2 py-1 font-mono text-xs font-semibold text-primary transition hover:bg-primary/15"
              >
                {item.evidence_route}
              </Link>
              <span className="max-w-full break-all rounded-md bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
                {item.evidence_file}
              </span>
            </div>
            {item.blocker && (
              <p className="mt-3 break-words rounded-md bg-destructive/10 p-2 text-xs font-medium text-destructive">
                {item.blocker}
              </p>
            )}
            <p className="mt-3 break-words text-xs font-medium text-muted-foreground">{item.next_action}</p>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function SmallValue({ label, value }: { label: string; value: string }) {
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

function registerStatusTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "ready" || status === "accepted" || status === "pass") return "ok"
  if (status === "blocked" || status === "fail" || status === "critical") return "danger"
  if (status === "watch" || status === "review" || status === "warn") return "warn"
  return "muted"
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
