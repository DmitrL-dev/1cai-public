import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  Briefcase,
  CheckCircle2,
  Clock3,
  Download,
  FileCheck2,
  FileText,
  Landmark,
  Loader2,
  PackageCheck,
  RefreshCw,
  Route as RouteIcon,
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
  boardPackApi,
  type BoardPackResponse,
  type EvidenceBundleRequest,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/board-pack")({
  component: BoardPackPage,
})

const nf = new Intl.NumberFormat("ru-RU")

type AppRoute =
  | "/"
  | "/killer-demo"
  | "/board-pack"
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
  | "/approvals"
  | "/audit"
  | "/evidence-bundle"

const appRoutes = [
  "/",
  "/killer-demo",
  "/board-pack",
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
  "/approvals",
  "/audit",
  "/evidence-bundle",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/board-pack"
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

function BoardPackPage() {
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
    include_board_pack: true,
    include_killer_demo: true,
  })

  const mutation = useMutation({
    mutationFn: () =>
      boardPackApi
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
              <Landmark size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Board Pack
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Board-level buying motion with value, trust, committee answers, risks, proof packet and the next 72 hours.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} score={mutation.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Board inputs</h2>
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
              Build board pack
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
              <Landmark size={42} className="opacity-30" />
              <p className="text-sm">Waiting for board inputs.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Board Pack did not build. Check backend and inputs.</p>
            </div>
          )}

          {mutation.data && <BoardReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function BoardReport({ report }: { report: BoardPackResponse }) {
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
            {report.board_snapshot.recommended_motion} | {report.board_snapshot.commercial_frame}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-4 xl:grid-cols-8">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Minutes" value={report.summary.board_minutes} icon={Clock3} />
        <Metric label="Value" value={`${nf.format(report.summary.first_year_visible_value)} ${report.summary.currency}`} icon={Target} />
        <Metric label="Roles" value={report.summary.committee_roles} icon={Users} />
        <Metric label="Risks" value={report.summary.risks} icon={AlertTriangle} />
        <Metric label="Close" value={report.summary.close_ready ? "ready" : "hold"} icon={Target} />
        <Metric label="Checkout" value={report.summary.checkout_gates} icon={PackageCheck} />
        <Metric label="Proof" value={report.summary.proof_items} icon={FileCheck2} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <BoardRoomBridge report={report} />

          <Panel title="Board snapshot" icon={Landmark}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <SnapshotCard label="One line" value={report.board_snapshot.one_line} />
              <SnapshotCard label="Why now" value={report.board_snapshot.why_now} />
              <SnapshotCard label="Value anchor" value={report.board_snapshot.value_anchor} strong />
              <SnapshotCard label="3-year AI rent" value={report.board_snapshot.three_year_ai_rent || "n/a"} />
              <SnapshotCard label="Local license" value={report.board_snapshot.local_license_anchor || "n/a"} strong />
              <SnapshotCard label="Break-even" value={report.board_snapshot.break_even || "n/a"} />
              <SnapshotCard label="Trust position" value={report.board_snapshot.trust_position} />
            </div>
            <p className="mt-3 break-words text-sm text-muted-foreground">
              {report.board_snapshot.subscription_escape_line}
            </p>
          </Panel>

          <Panel title="Recommended motion" icon={Briefcase}>
            <Link
              to={toAppRoute(report.recommended_offer.route || "/commercial-offer-studio")}
              className="block rounded-lg border border-border bg-background/60 p-4 transition hover:border-primary/40 hover:bg-accent/40"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="ok">{report.recommended_offer.id || report.summary.recommended_offer || "selected"}</Badge>
                <Badge tone="muted">{report.recommended_offer.buyer || "board"}</Badge>
              </div>
              <h3 className="mt-3 break-words text-lg font-bold text-card-foreground">
                {report.recommended_offer.title || report.board_snapshot.recommended_motion}
              </h3>
              <p className="mt-2 break-words text-sm text-card-foreground">
                {report.recommended_offer.why_buy || report.board_snapshot.why_now}
              </p>
              <p className="mt-2 break-words text-xs text-muted-foreground">
                {report.recommended_offer.acceptance || report.board_snapshot.commercial_frame}
              </p>
            </Link>
          </Panel>

          <BoardClosePacket report={report} />

          <Panel title="Decision brief" icon={FileText}>
            <div className="space-y-3">
              {report.decision_brief.map((item) => (
                <Link
                  key={item.question}
                  to={toAppRoute(item.route)}
                  className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-3 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="min-w-0">
                    <p className="break-words text-sm font-semibold text-card-foreground">{item.question}</p>
                    <p className="mt-1 break-words text-sm text-muted-foreground">{item.answer}</p>
                  </div>
                  <Badge tone="muted">{item.owner}</Badge>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Committee map" icon={Users}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {report.committee_map.map((item) => (
                <Link
                  key={item.role}
                  to={toAppRoute(item.proof_route)}
                  className="rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <Badge tone="muted">{item.role}</Badge>
                  <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{item.first_question}</p>
                  <p className="mt-2 break-words text-sm text-card-foreground">{item.must_believe}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.close_line}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Next 72 hours" icon={RouteIcon}>
            <div className="space-y-3">
              {report.next_72_hours.map((item, index) => (
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
                    <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{item.action}</p>
                    <p className="mt-1 break-words text-xs text-muted-foreground">{item.output}</p>
                  </div>
                </Link>
              ))}
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Risks to decision" icon={AlertTriangle}>
            <div className="space-y-3">
              {report.risk_to_decision.map((item) => (
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
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.decision}</p>
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
                  <p className="mt-1 break-words text-xs text-muted-foreground">{item.reason}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Objections" icon={ShieldCheck}>
            <div className="space-y-2">
              {report.objection_answers.map((item) => (
                <Link
                  key={item.objection}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-2 transition hover:bg-accent"
                >
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.objection}</p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{item.answer}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Board script" icon={Clock3}>
            <div className="space-y-2">
              {report.board_room_script.map((item) => (
                <Link
                  key={`${item.minute}-${item.speaker}`}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-2 transition hover:bg-accent"
                >
                  <div className="flex flex-wrap gap-2">
                    <Badge tone="muted">{item.minute}</Badge>
                    <Badge tone="muted">{item.speaker}</Badge>
                  </div>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.line}</p>
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

function BoardRoomBridge({ report }: { report: BoardPackResponse }) {
  const bridge = report.board_room_bridge
  const primary = bridge.primary_motion
  return (
    <Panel title="Board room bridge" icon={Users}>
      <div className="space-y-4">
        <div className="rounded-lg border border-border bg-background/60 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={statusTone(bridge.status)}>{bridge.status}</Badge>
            <Badge tone="muted">{bridge.score}</Badge>
            <Badge tone="muted">{bridge.source}</Badge>
          </div>
          <h3 className="mt-3 break-words text-base font-bold text-card-foreground">{primary.label}</h3>
          <p className="mt-2 break-words text-sm text-card-foreground">{bridge.room_line}</p>
          <p className="mt-2 break-words text-xs text-muted-foreground">{bridge.board_question}</p>
          <Link
            to={toAppRoute(primary.route)}
            className="mt-4 inline-flex min-h-9 max-w-full items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
          >
            <PackageCheck size={15} className="shrink-0" />
            <span className="break-words">{primary.ask}</span>
          </Link>
        </div>

        <OpenFirstPathList path={bridge.open_first_path} toAppRoute={toAppRoute} />

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Committee roles</p>
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
            <p className="text-xs font-semibold uppercase text-muted-foreground">Board flow</p>
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

function BoardClosePacket({ report }: { report: BoardPackResponse }) {
  const close = report.board_close_packet
  const order = close.one_page_order

  return (
    <Panel title="Board close packet" icon={PackageCheck}>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
          <div className="flex flex-wrap gap-2">
            <Badge tone={close.ready_to_close ? "ok" : "warn"}>{close.ready_to_close ? "ready to approve" : "hold rollout"}</Badge>
            <Badge tone="muted">{close.close_mode}</Badge>
          </div>
          <h3 className="mt-3 break-words text-base font-bold text-card-foreground">{close.primary_ask}</h3>
          <Link
            to={toAppRoute(order.route)}
            className="mt-3 inline-flex max-w-full items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
          >
            <PackageCheck size={15} />
            <span className="break-words">{order.recommended_purchase}</span>
          </Link>
          <p className="mt-3 break-words text-sm text-muted-foreground">{close.board_line}</p>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <SmallValue label="Value anchor" value={order.value_anchor} />
            <SmallValue label="AI rent" value={order.ai_rent_baseline} />
            <SmallValue label="3-year rent" value={order.three_year_ai_rent || "n/a"} />
            <SmallValue label="Local license" value={order.local_license_anchor || "n/a"} />
            <SmallValue label="Break-even" value={order.break_even || "n/a"} />
            <SmallValue label="Frame" value={order.commercial_frame} />
            <SmallValue label="Invoice trigger" value={order.first_invoice_trigger} />
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
        </div>

        <div className="rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Evidence requirements</p>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
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
      </div>

      <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2">
        {close.close_script.map((item) => (
          <div key={item} className="rounded-md bg-muted p-2 text-xs text-card-foreground">
            {item}
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

function SnapshotCard({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
      <p className={cn("mt-2 break-words text-sm text-card-foreground", strong && "text-lg font-bold")}>{value}</p>
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
