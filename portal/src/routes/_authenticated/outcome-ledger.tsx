import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  Briefcase,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileCheck2,
  FileText,
  LineChart,
  Loader2,
  RefreshCw,
  Route as RouteIcon,
  ShieldCheck,
  Target,
  TrendingUp,
  Users,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  outcomeLedgerApi,
  type EvidenceBundleRequest,
  type OutcomeLedgerResponse,
} from "@/lib/api-client"
import { BuyerRoomPacketControls } from "@/components/BuyerRoomPacketControls"
import { OpenFirstPathList } from "@/components/OpenFirstPathList"
import { VerificationPacketControls } from "@/components/VerificationPacketControls"

export const Route = createFileRoute("/_authenticated/outcome-ledger")({
  component: OutcomeLedgerPage,
})

const nf = new Intl.NumberFormat("ru-RU")

type AppRoute =
  | "/"
  | "/outcome-ledger"
  | "/board-pack"
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
  | "/approvals"
  | "/audit"
  | "/evidence-bundle"

const appRoutes = [
  "/",
  "/outcome-ledger",
  "/board-pack",
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
  "/approvals",
  "/audit",
  "/evidence-bundle",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/outcome-ledger"
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

function OutcomeLedgerPage() {
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
      outcomeLedgerApi
        .build(buildRequest())
        .then((r) => r.data),
  })
  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <LineChart size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Outcome Ledger
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Adoption, measurable outcomes, risk burndown and expansion paths after the buying motion is selected.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} score={mutation.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Ledger inputs</h2>
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
              Build outcome ledger
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
              <LineChart size={42} className="opacity-30" />
              <p className="text-sm">Waiting for ledger inputs.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Outcome Ledger did not build. Check backend and inputs.</p>
            </div>
          )}

          {mutation.data && <OutcomeReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function OutcomeReport({ report }: { report: OutcomeLedgerResponse }) {
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
            {report.value_realization.recommended_motion} | {report.value_realization.commercial_frame}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-4 xl:grid-cols-10">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Value" value={report.value_realization.value_anchor} icon={Target} />
        <Metric label="AI rent" value={report.value_realization.ai_subscription_baseline} icon={TrendingUp} />
        <Metric label="Outcomes" value={report.summary.outcome_tiles} icon={ClipboardCheck} />
        <Metric label="Risks" value={report.summary.risk_items} icon={AlertTriangle} />
        <Metric label="Gov gates" value={report.summary.governance_gates} icon={ShieldCheck} />
        <Metric label="Windows" value={report.summary.governance_windows} icon={RouteIcon} />
        <Metric label="Expansion" value={report.summary.expansion_paths} icon={Briefcase} />
        <Metric label="Accept" value={report.summary.acceptance_rollup_ready ? "claim" : "hold"} icon={FileCheck2} />
        <Metric label="Day 0" value={report.summary.post_purchase_ready ? "ready" : "watch"} icon={FileCheck2} />
      </div>

      <OutcomeRoomBridge report={report} />
      <PostPurchaseProofSpine report={report} />

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Value realization" icon={TrendingUp}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <SnapshotCard label="Manual review" value={report.value_realization.manual_review_baseline} />
              <SnapshotCard label="Release exposure" value={report.value_realization.release_delay_baseline} />
              <SnapshotCard label="Risk exposure" value={report.value_realization.risk_exposure_baseline} />
              <SnapshotCard label="First window" value={report.value_realization.first_measurement_window} />
            </div>
            <p className="mt-3 break-words rounded-lg border border-border bg-background/60 p-3 text-sm text-card-foreground">
              {report.value_realization.proof_standard}
            </p>
          </Panel>

          <Panel title="Outcome tiles" icon={ClipboardCheck}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {report.outcome_tiles.map((item) => (
                <Link
                  key={item.id}
                  to={toAppRoute(item.route)}
                  className="rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex flex-wrap gap-2">
                    <Badge tone="muted">{item.role}</Badge>
                    <Badge tone="ok">{item.owner}</Badge>
                  </div>
                  <h3 className="mt-3 break-words text-sm font-semibold text-card-foreground">{item.outcome}</h3>
                  <p className="mt-2 break-words text-xs text-muted-foreground">Baseline: {item.baseline}</p>
                  <p className="mt-2 break-words text-sm text-card-foreground">{item.target}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.acceptance}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Adoption timeline" icon={RouteIcon}>
            <div className="space-y-3">
              {report.adoption_timeline.map((item, index) => (
                <Link
                  key={`${item.window}-${item.owner}`}
                  to={toAppRoute(item.route)}
                  className="grid min-w-0 grid-cols-[34px_minmax(0,1fr)] gap-3 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-xs font-bold text-primary">
                    {index + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap gap-2">
                      <Badge tone="muted">{item.window}</Badge>
                      <Badge tone="muted">{item.owner}</Badge>
                    </div>
                    <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{item.goal}</p>
                    <p className="mt-1 break-words text-xs text-muted-foreground">{item.exit_criteria}</p>
                    <p className="mt-1 break-words text-xs text-muted-foreground">{item.artifact}</p>
                  </div>
                </Link>
              ))}
            </div>
          </Panel>

          <AcceptanceRollup report={report} />
          <GovernanceRefresh report={report} />

          <Panel title="Success metrics" icon={LineChart}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {report.success_metrics.map((item) => (
                <Link
                  key={item.metric}
                  to={toAppRoute(item.route)}
                  className="rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.metric}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">Baseline: {item.baseline}</p>
                  <p className="mt-2 break-words text-sm text-card-foreground">{item.target}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.buyer_line}</p>
                </Link>
              ))}
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Role scorecards" icon={Users}>
            <div className="space-y-2">
              {report.role_scorecards.map((item) => (
                <Link
                  key={`${item.role}-${item.proof_route}`}
                  to={toAppRoute(item.proof_route)}
                  className="block rounded-lg border border-border bg-background/60 p-2 transition hover:bg-accent"
                >
                  <Badge tone="muted">{item.role}</Badge>
                  <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{item.spark}</p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{item.adoption_signal}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Risk burndown" icon={AlertTriangle}>
            <div className="space-y-3">
              {report.risk_burndown.map((item) => (
                <Link
                  key={`${item.route}-${item.risk}`}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
                >
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={riskTone(item.severity)}>{item.severity}</Badge>
                    <Badge tone="muted">{item.owner}</Badge>
                  </div>
                  <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{item.risk}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.day_30}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Expansion paths" icon={Briefcase}>
            <div className="space-y-2">
              {report.expansion_paths.map((item) => (
                <Link
                  key={item.id}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-2 transition hover:bg-accent"
                >
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{item.trigger}</p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{item.offer}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Proof packet" icon={FileCheck2}>
            <div className="space-y-2">
              {report.proof_packet.map((item) => (
                <Link
                  key={`${item.title}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-2 transition hover:bg-accent"
                >
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                  <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{item.filename}</p>
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

function PostPurchaseProofSpine({ report }: { report: OutcomeLedgerResponse }) {
  const spine = report.post_purchase_proof_spine

  return (
    <div className="border-b border-border p-4 sm:p-5">
      <Panel title="Day 0 proof spine" icon={FileCheck2}>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <div className="flex flex-wrap gap-2">
              <Badge tone={statusTone(spine.status)}>{spine.status}</Badge>
              <Badge tone={spine.ready_to_measure ? "ok" : "warn"}>
                {spine.ready_to_measure ? "measure" : "hold measure"}
              </Badge>
              <Badge tone={spine.ready_to_claim ? "ok" : "warn"}>
                {spine.ready_to_claim ? "claim" : "refresh claim"}
              </Badge>
            </div>
            <h3 className="mt-3 break-words text-base font-bold text-card-foreground">{spine.buyer_line}</h3>
            <p className="mt-2 break-words text-sm text-muted-foreground">{spine.measurement_rule}</p>
            <div className="mt-4 rounded-md border border-primary/30 bg-primary/10 p-3">
              <p className="break-words text-sm font-semibold text-card-foreground">
                {spine.buyer_room_packet.title}
              </p>
              <Link
                to={toAppRoute(spine.buyer_room_packet.route)}
                className="mt-2 block break-all font-mono text-xs font-semibold text-primary"
              >
                {spine.buyer_room_packet.filename}
              </Link>
              <p className="mt-2 break-all font-mono text-[11px] text-muted-foreground">
                {spine.buyer_room_packet.hash_header}
              </p>
              <p className="mt-2 break-words text-xs text-muted-foreground">{spine.buyer_room_packet.check}</p>
            </div>
            <div className="mt-4 rounded-md bg-muted p-3">
              <p className="break-words text-sm font-semibold text-card-foreground">
                {spine.archive_receipt.title}
              </p>
              <Link
                to={toAppRoute(spine.archive_receipt.route)}
                className="mt-2 block break-all font-mono text-xs font-semibold text-primary"
              >
                {spine.archive_receipt.filename}
              </Link>
              <p className="mt-2 break-words text-xs text-muted-foreground">{spine.archive_receipt.check}</p>
            </div>
            <div className="mt-3 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3">
              <p className="break-words text-sm font-semibold text-card-foreground">
                {spine.verification_packet.title}
              </p>
              <Link
                to={toAppRoute(spine.verification_packet.route)}
                className="mt-2 block break-all font-mono text-xs font-semibold text-emerald-700 dark:text-emerald-300"
              >
                {spine.verification_packet.filename}
              </Link>
              <p className="mt-2 break-all font-mono text-[11px] text-muted-foreground">
                {spine.verification_packet.hash_header}
              </p>
              <p className="mt-2 break-words text-xs text-muted-foreground">{spine.verification_packet.check}</p>
            </div>
          </div>

          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Activation gate</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge tone={spine.activation_gate.ready ? "ok" : "warn"}>
                {spine.activation_gate.ready ? "ready" : "watch"}
              </Badge>
              <Badge tone="muted">{spine.activation_gate.source}</Badge>
            </div>
            <p className="mt-3 break-words text-sm font-semibold text-card-foreground">
              {spine.activation_gate.invoice_trigger}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {spine.required_routes.slice(0, 8).map((route) => (
                <Link
                  key={route}
                  to={toAppRoute(route)}
                  className="rounded-md border border-border bg-card px-2 py-1 font-mono text-xs font-semibold text-card-foreground transition hover:bg-accent"
                >
                  {route}
                </Link>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {spine.files.map((item) => (
            <Link
              key={item.filename}
              to={toAppRoute(item.route)}
              className="min-w-0 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone="muted">{item.owner}</Badge>
                <Badge tone="ok">{item.route}</Badge>
              </div>
              <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{item.title}</p>
              <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{item.filename}</p>
              <p className="mt-2 break-words text-xs text-muted-foreground">{item.purpose}</p>
            </Link>
          ))}
        </div>
      </Panel>
    </div>
  )
}

function OutcomeRoomBridge({ report }: { report: OutcomeLedgerResponse }) {
  const bridge = report.outcome_room_bridge

  return (
    <div className="border-b border-border p-4 sm:p-5">
      <Panel title="Outcome room bridge" icon={RouteIcon}>
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
                className="rounded-lg border border-primary/30 bg-primary/10 p-3 transition hover:border-primary hover:bg-primary/15"
              >
                <Badge tone={statusTone(bridge.primary_motion.status)}>{bridge.primary_motion.status}</Badge>
                <p className="mt-3 break-words text-sm font-semibold text-card-foreground">
                  {bridge.primary_motion.label}
                </p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{bridge.primary_motion.ask}</p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{bridge.primary_motion.reason}</p>
              </Link>
              <Link
                to={toAppRoute(bridge.outcome_motion.route)}
                className="rounded-lg border border-border bg-muted p-3 transition hover:bg-accent"
              >
                <Badge tone={statusTone(bridge.outcome_motion.status)}>Outcome</Badge>
                <p className="mt-3 break-words text-sm font-semibold text-card-foreground">
                  {bridge.outcome_motion.label}
                </p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{bridge.outcome_motion.ask}</p>
                <p className="mt-2 break-words text-xs font-semibold text-card-foreground">
                  {bridge.outcome_motion.value_anchor}
                </p>
              </Link>
            </div>
          </div>

          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Files to claim with</p>
            <div className="mt-3 space-y-2">
              {bridge.files.map((file) => (
                <div key={file} className="break-all rounded-md bg-muted p-2 font-mono text-xs text-card-foreground">
                  {file}
                </div>
              ))}
            </div>
            <p className="mt-4 break-words text-sm font-semibold text-card-foreground">{bridge.outcome_question}</p>
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
                    <Badge tone={statusTone(item.status)}>{item.title || item.role}</Badge>
                    <Badge tone="muted">{item.proof_file}</Badge>
                  </div>
                  <p className="mt-2 break-words text-xs text-card-foreground">{item.spark}</p>
                  {item.owner_action && (
                    <p className="mt-2 break-words text-xs text-muted-foreground">{item.owner_action}</p>
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

function AcceptanceRollup({ report }: { report: OutcomeLedgerResponse }) {
  const rollup = report.acceptance_rollup

  return (
    <Panel title="Acceptance rollup" icon={FileCheck2}>
      <div className="rounded-lg border border-border bg-background/60 p-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={rollup.ready_to_claim ? "ok" : rollup.ready_to_continue ? "warn" : "danger"}>
                {rollup.ready_to_claim ? "ready to claim" : rollup.ready_to_continue ? "continue with caveats" : "blocked"}
              </Badge>
              <Badge tone="ok">{rollup.ready_items} ready</Badge>
              <Badge tone="warn">{rollup.watch_items} watch</Badge>
              <Badge tone={rollup.blocked_items ? "danger" : "muted"}>{rollup.blocked_items} blocked</Badge>
            </div>
            <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{rollup.owner_line}</p>
          </div>
          <div className="shrink-0 rounded-lg border border-border bg-card px-3 py-2 text-sm">
            <p className="font-bold text-card-foreground">{rollup.next_window}</p>
            <p className="text-xs text-muted-foreground">{rollup.next_owner}</p>
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
        {rollup.items.map((item) => (
          <div key={item.id} className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="muted">{item.window}</Badge>
              <Badge tone={statusTone(item.status)}>{item.status}</Badge>
              <span className="text-xs font-semibold uppercase text-muted-foreground">{item.owner}</span>
            </div>
            <h3 className="mt-3 break-words text-sm font-semibold text-card-foreground">{item.role}</h3>
            <p className="mt-2 break-words text-sm text-card-foreground">{item.decision}</p>
            <p className="mt-2 break-words text-xs text-muted-foreground">{item.acceptance}</p>
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <Link
                to={toAppRoute(item.evidence_route)}
                className="rounded-md bg-primary/10 px-2 py-1 font-mono text-xs font-semibold text-primary transition hover:bg-primary/15"
              >
                {item.evidence_route}
              </Link>
              <Link
                to={toAppRoute(item.outcome_route)}
                className="rounded-md border border-border bg-card px-2 py-1 font-mono text-xs font-semibold text-card-foreground transition hover:bg-accent"
              >
                {item.outcome_route}
              </Link>
            </div>
            <p className="mt-2 break-words text-xs text-muted-foreground">{item.outcome_signal}</p>
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

function GovernanceRefresh({ report }: { report: OutcomeLedgerResponse }) {
  const governance = report.governance_refresh

  return (
    <Panel title="Governance refresh" icon={ShieldCheck}>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
          <div className="flex flex-wrap gap-2">
            <Badge tone={governance.ready ? "ok" : "warn"}>
              {governance.ready ? "ready" : "refresh required"}
            </Badge>
          </div>
          <p className="mt-3 break-words text-base font-bold text-card-foreground">{governance.refresh_line}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {governance.proof_routes.slice(0, 8).map((route) => (
              <Link
                key={route}
                to={toAppRoute(route)}
                className="rounded-md border border-border bg-background px-2 py-1 text-xs font-semibold text-card-foreground transition hover:bg-accent"
              >
                {route.replace("/", "")}
              </Link>
            ))}
          </div>
        </div>

        <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Governance gates</p>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            {governance.gates.map((item) => (
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

      <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2">
        {governance.windows.map((item) => (
          <Link
            key={`${item.window}-${item.route}`}
            to={toAppRoute(item.route)}
            className="rounded-md bg-muted p-2 transition hover:bg-accent"
          >
            <div className="flex flex-wrap gap-2">
              <Badge tone="muted">{item.window}</Badge>
              <Badge tone="muted">{item.owner}</Badge>
            </div>
            <p className="mt-2 break-words text-xs text-muted-foreground">{item.acceptance}</p>
          </Link>
        ))}
      </div>
    </Panel>
  )
}

function SnapshotCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-2 break-words text-lg font-bold text-card-foreground">{value}</p>
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

function riskTone(severity: string): "ok" | "warn" | "danger" | "muted" {
  if (severity === "high" || severity === "critical") return "danger"
  if (severity === "medium") return "warn"
  if (severity === "low") return "ok"
  return "muted"
}

function statusTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "ready" || status === "accepted" || status === "pass") return "ok"
  if (status === "blocked" || status === "fail" || status === "critical") return "danger"
  if (status === "watch" || status === "review" || status === "warn") return "warn"
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
