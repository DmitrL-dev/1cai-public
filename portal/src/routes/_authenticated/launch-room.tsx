import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  Compass,
  Download,
  FileCheck2,
  FileText,
  Gauge,
  Landmark,
  Layers3,
  LineChart,
  Loader2,
  RefreshCw,
  Route as RouteIcon,
  Rocket,
  ShieldCheck,
  Sparkles,
  Timer,
  Users,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  launchRoomApi,
  type EvidenceBundleRequest,
  type LaunchRoomResponse,
} from "@/lib/api-client"
import { BuyerRoomPacketControls } from "@/components/BuyerRoomPacketControls"
import { OpenFirstPathList } from "@/components/OpenFirstPathList"
import { VerificationPacketControls } from "@/components/VerificationPacketControls"

export const Route = createFileRoute("/_authenticated/launch-room")({
  component: LaunchRoomPage,
})

const nf = new Intl.NumberFormat("ru-RU")

type AppRoute =
  | "/"
  | "/launch-room"
  | "/killer-demo"
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
  | "/quality"
  | "/change"
  | "/testing"
  | "/release-readiness"
  | "/architecture"
  | "/offline-readiness"
  | "/platform-doctor"
  | "/vendor-portfolio"
  | "/rights-rls"
  | "/value-packs"
  | "/configurations"
  | "/metadata"
  | "/operations"
  | "/lock-radar"
  | "/extension-safety"
  | "/update-war-room"
  | "/evidence-bundle"
  | "/approvals"
  | "/audit"

const appRoutes = [
  "/",
  "/launch-room",
  "/killer-demo",
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
  "/quality",
  "/change",
  "/testing",
  "/release-readiness",
  "/architecture",
  "/offline-readiness",
  "/platform-doctor",
  "/vendor-portfolio",
  "/rights-rls",
  "/value-packs",
  "/configurations",
  "/metadata",
  "/operations",
  "/lock-radar",
  "/extension-safety",
  "/update-war-room",
  "/evidence-bundle",
  "/approvals",
  "/audit",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/launch-room"
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

function LaunchRoomPage() {
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
    include_launch_room: true,
    include_pilot_launchpad: true,
    include_outcome_ledger: true,
  })

  const mutation = useMutation({
    mutationFn: () =>
      launchRoomApi
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
              Launch Room
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            One cockpit for the buyer path: orient, prove, trust, approve, adopt and export.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} score={mutation.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Launch inputs</h2>
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
              Build launch room
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
              <p className="text-sm">Waiting for launch inputs.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Launch Room did not build. Check backend and inputs.</p>
            </div>
          )}

          {mutation.data && <LaunchReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function LaunchReport({ report }: { report: LaunchRoomResponse }) {
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
            {report.launch_summary.one_line}
          </p>
        </div>
        <Link
          to={toAppRoute(report.next_best_action.route)}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
        >
          <Sparkles size={16} />
          {report.next_best_action.label}
        </Link>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-6">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Value" value={report.launch_summary.value_anchor} icon={Landmark} />
        <Metric label="Phases" value={report.summary.phases} icon={RouteIcon} />
        <Metric label="Journey" value={`${report.summary.journey_ready}/${report.summary.journey_steps}`} icon={Rocket} />
        <Metric
          label="Gates"
          value={report.summary.checkout_gates + report.summary.activation_gates + report.summary.governance_gates}
          icon={FileCheck2}
        />
        <Metric label="Proof" value={report.summary.proof_routes} icon={FileCheck2} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Next best action" icon={Compass}>
            <div className="rounded-lg border border-border bg-background/60 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={statusTone(report.decision.status)}>{report.decision.status}</Badge>
                <Badge tone={statusTone(report.launch_summary.trust_status)}>trust {report.launch_summary.trust_status}</Badge>
                <Badge tone={statusTone(report.launch_summary.board_status)}>board {report.launch_summary.board_status}</Badge>
              </div>
              <h3 className="mt-3 break-words text-base font-bold text-card-foreground">
                {report.next_best_action.label}
              </h3>
              <p className="mt-2 break-words text-sm text-muted-foreground">{report.next_best_action.reason}</p>
              <Link
                to={toAppRoute(report.next_best_action.route)}
                className="mt-4 inline-flex min-h-9 items-center rounded-lg border border-border bg-background px-3 py-2 text-sm font-semibold text-card-foreground transition hover:bg-accent"
              >
                Open route
              </Link>
            </div>
          </Panel>

          <BuyerRoomBridge report={report} />

          <PurchaseSpinePanel report={report} />

          <BuyerJourney report={report} />

          <Panel title="Launch path" icon={Layers3}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {report.path_phases.map((item, index) => (
                <Link
                  key={item.id}
                  to={toAppRoute(item.route)}
                  className="grid min-w-0 grid-cols-[36px_minmax(0,1fr)] gap-3 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-xs font-bold text-primary">
                    {index + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="break-words text-sm font-semibold text-card-foreground">{item.title}</h3>
                      <Badge tone={statusTone(item.status)}>{item.status}</Badge>
                      <Badge tone="muted">{item.score}</Badge>
                    </div>
                    <p className="mt-2 break-words text-xs font-semibold text-muted-foreground">{item.question}</p>
                    <p className="mt-2 break-words text-sm text-card-foreground">{item.exit_criteria}</p>
                    <p className="mt-2 break-words text-xs text-muted-foreground">{item.proof}</p>
                  </div>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Role switchboard" icon={Users}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[780px] text-left text-sm">
                <thead className="border-b border-border text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3 font-semibold">Role</th>
                    <th className="px-3 py-2 font-semibold">First</th>
                    <th className="px-3 py-2 font-semibold">Spark</th>
                    <th className="py-2 pl-3 font-semibold">Close</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {report.role_switchboard.map((item) => (
                    <tr key={`${item.role}-${item.first_click}`}>
                      <td className="py-3 pr-3 font-semibold text-card-foreground">{item.role}</td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-2">
                          <LinkButton to={toAppRoute(item.first_click)}>{item.first_click}</LinkButton>
                          <LinkButton to={toAppRoute(item.second_click)}>{item.second_click}</LinkButton>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-xs text-muted-foreground">{item.spark}</td>
                      <td className="py-3 pl-3 text-xs text-muted-foreground">{item.close || item.must_believe}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="Meeting modes" icon={Timer}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {report.meeting_modes.map((mode) => (
                <div key={mode.id} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{mode.minutes} min</Badge>
                    <Badge tone="muted">{mode.audience}</Badge>
                  </div>
                  <h3 className="mt-3 break-words text-sm font-semibold text-card-foreground">{mode.title}</h3>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {mode.steps.map((step) => (
                      <LinkButton key={`${mode.id}-${step.route}-${step.label}`} to={toAppRoute(step.route)}>
                        {step.label}
                      </LinkButton>
                    ))}
                  </div>
                  <p className="mt-3 break-words text-xs text-muted-foreground">{mode.close}</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Route health" icon={Gauge}>
            <div className="space-y-2">
              {report.route_health.map((item) => (
                <Link
                  key={`${item.title}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                    <Badge tone={statusTone(item.status)}>{item.status} {item.score}</Badge>
                  </div>
                  {item.headline && <p className="mt-2 break-words text-xs text-muted-foreground">{item.headline}</p>}
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Anti-confusion" icon={AlertTriangle}>
            <div className="space-y-2">
              {report.anti_confusion_cards.map((item) => (
                <Link
                  key={`${item.signal}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
                >
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.signal}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.response}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Proof packet" icon={FileCheck2}>
            <div className="space-y-2">
              {report.proof_packet.map((item) => (
                <Link
                  key={`${item.title}-${item.filename}`}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-2 transition hover:bg-accent"
                >
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                  <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{item.filename}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Source signals" icon={LineChart}>
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

function BuyerRoomBridge({ report }: { report: LaunchRoomResponse }) {
  const bridge = report.buyer_room_bridge
  const primary = bridge.primary_motion
  return (
    <Panel title="Buyer room bridge" icon={Users}>
      <div className="space-y-4">
        <div className="rounded-lg border border-border bg-background/60 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={statusTone(bridge.status)}>{bridge.status}</Badge>
            <Badge tone="muted">{bridge.score}</Badge>
            <Badge tone="muted">{bridge.source}</Badge>
          </div>
          <h3 className="mt-3 break-words text-base font-bold text-card-foreground">{primary.label}</h3>
          <p className="mt-2 break-words text-sm text-card-foreground">{bridge.room_line}</p>
          <p className="mt-2 break-words text-xs text-muted-foreground">{primary.reason}</p>
          <Link
            to={toAppRoute(primary.route)}
            className="mt-4 inline-flex min-h-9 max-w-full items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
          >
            <Sparkles size={15} className="shrink-0" />
            <span className="break-words">{primary.ask}</span>
          </Link>
        </div>

        <OpenFirstPathList path={bridge.open_first_path} toAppRoute={toAppRoute} itemClassName="bg-muted" />

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Role cards</p>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
              {bridge.role_cards.map((item) => (
                <Link
                  key={`${item.role}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="rounded-md bg-muted p-2 transition hover:bg-accent"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={statusTone(item.status)}>{item.status}</Badge>
                    <span className="break-words text-xs font-semibold text-card-foreground">{item.title}</span>
                  </div>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.spark}</p>
                  <p className="mt-2 break-all font-mono text-[11px] text-muted-foreground">{item.proof_file}</p>
                </Link>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Meeting flow</p>
            <div className="mt-3 space-y-2">
              {bridge.meeting_flow.map((item) => (
                <Link
                  key={`${item.step}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="grid min-w-0 grid-cols-[28px_minmax(0,1fr)] gap-2 rounded-md bg-muted p-2 transition hover:bg-accent"
                >
                  <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
                    {item.step}
                  </span>
                  <span className="min-w-0">
                    <span className="block break-words text-xs font-semibold text-card-foreground">{item.label}</span>
                    <span className="mt-1 block break-words text-xs text-muted-foreground">{item.line}</span>
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Proof readiness</p>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            {bridge.proof_readiness.map((item) => (
              <Link
                key={item.id}
                to={toAppRoute(item.route)}
                className="rounded-md bg-muted p-2 transition hover:bg-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={statusTone(item.status)}>{item.status}</Badge>
                  <span className="break-words text-xs font-semibold text-card-foreground">{item.title}</span>
                </div>
                <p className="mt-2 break-words text-xs text-muted-foreground">{item.signal}</p>
                <p className="mt-2 break-all font-mono text-[11px] text-muted-foreground">{item.file}</p>
              </Link>
            ))}
          </div>
          <p className="mt-3 break-all font-mono text-[11px] text-muted-foreground">{bridge.files.join(", ")}</p>
        </div>
      </div>
    </Panel>
  )
}

function BuyerJourney({ report }: { report: LaunchRoomResponse }) {
  return (
    <Panel title="Buyer journey" icon={Rocket}>
      <div className="space-y-3">
        <div className="rounded-lg border border-border bg-background/60 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={report.buyer_journey.risk_steps ? "danger" : "ok"}>
              {report.buyer_journey.ready_steps}/{report.buyer_journey.steps.length} ready
            </Badge>
            <Badge tone="muted">{report.buyer_journey.checkout_gates} checkout</Badge>
            <Badge tone="muted">{report.buyer_journey.activation_gates} activation</Badge>
            <Badge tone="muted">{report.buyer_journey.governance_gates} governance</Badge>
            <Badge tone={report.buyer_journey.claim_ready ? "ok" : report.buyer_journey.acceptance_blocked ? "danger" : "warn"}>
              {report.buyer_journey.claim_ready ? "claim ready" : "claim pending"}
            </Badge>
            <Badge tone="muted">{report.buyer_journey.acceptance_items} acceptance</Badge>
            {report.buyer_journey.acceptance_watch > 0 && (
              <Badge tone="warn">{report.buyer_journey.acceptance_watch} watch</Badge>
            )}
            {report.buyer_journey.acceptance_blocked > 0 && (
              <Badge tone="danger">{report.buyer_journey.acceptance_blocked} blocked</Badge>
            )}
          </div>
          <p className="mt-3 break-words text-sm text-card-foreground">{report.buyer_journey.buyer_line}</p>
          <Link
            to={toAppRoute(report.buyer_journey.next_route)}
            className="mt-4 inline-flex min-h-9 items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-semibold text-card-foreground transition hover:bg-accent"
          >
            <RouteIcon size={15} />
            Next journey route
          </Link>
        </div>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {report.buyer_journey.steps.map((item, index) => (
            <Link
              key={item.id}
              to={toAppRoute(item.route)}
              className="grid min-w-0 grid-cols-[34px_minmax(0,1fr)] gap-3 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-xs font-bold text-primary">
                {index + 1}
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="break-words text-sm font-semibold text-card-foreground">{item.title}</h3>
                  <Badge tone={statusTone(item.status)}>{item.status}</Badge>
                </div>
                <p className="mt-2 break-words text-xs font-semibold text-muted-foreground">{item.signal}</p>
                <p className="mt-2 break-words text-sm text-card-foreground">{item.action}</p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{item.proof}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </Panel>
  )
}

function PurchaseSpinePanel({ report }: { report: LaunchRoomResponse }) {
  const purchase = report.purchase_spine
  return (
    <Panel title="Purchase spine" icon={Landmark}>
      <div className="space-y-4">
        <div className="rounded-lg border border-border bg-background/60 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={statusTone(purchase.status)}>{purchase.status}</Badge>
            <Badge tone="muted">{purchase.commercial_frame}</Badge>
          </div>
          <h3 className="mt-3 break-words text-base font-bold text-card-foreground">{purchase.headline}</h3>
          <p className="mt-2 break-words text-sm text-card-foreground">{purchase.buyer_line}</p>
          <Link
            to={toAppRoute(purchase.route)}
            className="mt-4 inline-flex min-h-9 items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
          >
            <Landmark size={15} />
            {purchase.recommended_purchase}
          </Link>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <SmallValue label="AI / month" value={purchase.monthly_ai_rent} />
          <SmallValue label="3-year AI rent" value={purchase.three_year_ai_rent} />
          <SmallValue label="Local license" value={purchase.local_license_anchor} />
          <SmallValue label="Break-even" value={purchase.break_even} />
        </div>

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Invoice trigger</p>
            <p className="mt-2 break-words text-sm text-card-foreground">{purchase.first_invoice_trigger}</p>
          </div>
          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Proof routes</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {purchase.proof_routes.map((route) => (
                <LinkButton key={route} to={toAppRoute(route)}>{route}</LinkButton>
              ))}
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Purchase artifacts</p>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            {purchase.evidence_files.map((item) => (
              <Link
                key={`${item.route}-${item.filename}`}
                to={toAppRoute(item.route)}
                className="min-w-0 rounded-md bg-muted p-2 transition hover:bg-accent"
              >
                <p className="break-words text-xs font-semibold text-card-foreground">{item.title}</p>
                <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">{item.filename}</p>
              </Link>
            ))}
          </div>
        </div>

        {purchase.procurement_handoff && <PurchaseProcurementHandoff handoff={purchase.procurement_handoff} />}

        {purchase.guardrails.length > 0 && (
          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Guardrails</p>
            <ul className="mt-2 space-y-1.5 text-xs text-muted-foreground">
              {purchase.guardrails.map((item) => (
                <li key={item} className="break-words">{item}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Panel>
  )
}

function PurchaseProcurementHandoff({
  handoff,
}: {
  handoff: LaunchRoomResponse["purchase_spine"]["procurement_handoff"]
}) {
  return (
    <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <ShieldCheck size={15} className="text-emerald-700 dark:text-emerald-300" />
          <p className="break-words text-xs font-semibold uppercase text-emerald-700 dark:text-emerald-300">
            {handoff.title}
          </p>
        </div>
        <Badge tone={statusTone(handoff.status)}>{handoff.status}</Badge>
      </div>
      <p className="mt-2 break-words text-sm text-card-foreground">{handoff.owner_line}</p>
      <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
        {handoff.open_order.slice(0, 5).map((item) => (
          <Link
            key={`${item.step}-${item.route}-${item.file}`}
            to={toAppRoute(item.route)}
            className="grid min-w-0 grid-cols-[28px_minmax(0,1fr)] gap-2 rounded-md border border-emerald-500/20 bg-card p-2 transition hover:border-emerald-500/50 hover:bg-accent"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-500/10 text-xs font-bold text-emerald-700 dark:text-emerald-300">
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
      <p className="mt-3 break-words text-xs font-semibold text-card-foreground">{handoff.acceptance}</p>
      {handoff.attachments.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {handoff.attachments.slice(0, 4).map((item) => (
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
    </div>
  )
}

function SmallValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
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

function LinkButton({ to, children }: { to: AppRoute; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="inline-flex min-h-8 max-w-full items-center rounded-md border border-border bg-background px-2 py-1 text-xs font-semibold text-card-foreground transition hover:bg-accent"
    >
      <span className="break-words">{children}</span>
    </Link>
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
  if (status === "risk" || status === "fail" || status === "critical" || status === "blocked") return "danger"
  if (status === "watch" || status === "warn" || status === "partial") return "warn"
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
