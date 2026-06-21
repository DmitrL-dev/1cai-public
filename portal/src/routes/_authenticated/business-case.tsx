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
  PlayCircle,
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
  businessCaseApi,
  type BusinessCaseLever,
  type BusinessCaseResponse,
  type EvidenceBundleRequest,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/business-case")({
  component: BusinessCasePage,
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
  "/evidence-bundle",
  "/approvals",
  "/audit",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/business-case"
}

function downloadMarkdown(filename: string, markdown: string) {
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function BusinessCasePage() {
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
    include_business_case: true,
    include_killer_demo: true,
  })

  const mutation = useMutation({
    mutationFn: () =>
      businessCaseApi
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
              <DollarSign size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Business Case
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Director value pack: money levers, buyer committee, objections, offer stack and 30/60/90 path from local Rentgen evidence.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} score={mutation.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Deal inputs</h2>
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
              Build business case
            </button>
            {mutation.data && (
              <button
                onClick={() => downloadMarkdown("rentgen-business-case.md", mutation.data.markdown)}
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
              <DollarSign size={42} className="opacity-30" />
              <p className="text-sm">Waiting for deal assumptions.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Business Case did not build. Check backend and inputs.</p>
            </div>
          )}

          {mutation.data && <CaseReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function CaseReport({ report }: { report: BusinessCaseResponse }) {
  const subscriptionEscape = report.subscription_escape_plan

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
            {report.client.name}: {report.client.configuration}
            {report.client.target_platform_version ? ` -> ${report.client.target_platform_version}` : ""}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-5">
        <Metric label="Visible value" value={money(report.summary.first_year_visible_value, report.assumptions.currency)} icon={DollarSign} />
        <Metric label="AI budget" value={money(report.summary.ai_subscription_year, report.assumptions.currency)} icon={ShieldCheck} />
        <Metric label="Manual review" value={money(report.summary.manual_review_year, report.assumptions.currency)} icon={ClipboardCheck} />
        <Metric label="Risk exposure" value={money(report.summary.risk_exposure, report.assumptions.currency)} icon={AlertTriangle} />
        <Metric label="Queue" value={report.summary.review_queue} icon={Users} />
      </div>

      <div className="border-b border-border p-4 sm:p-5">
        <BusinessRoomBridge bridge={report.business_room_bridge} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          {subscriptionEscape && <SubscriptionEscapePanel plan={subscriptionEscape} />}

          <Panel title="Money levers" icon={DollarSign}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.business_levers.map((lever) => (
                <LeverCard key={lever.id} lever={lever} />
              ))}
            </div>
          </Panel>

          <Panel title="Buyer committee" icon={Users}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.buyer_committee.map((item) => (
                <div key={item.role} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="break-words text-sm font-semibold text-card-foreground">{item.role}</p>
                    <Link
                      to={toAppRoute(item.route)}
                      className="inline-flex h-8 items-center rounded-md border border-border bg-background px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
                    >
                      Open
                    </Link>
                  </div>
                  <p className="mt-2 break-words text-sm text-muted-foreground">{item.wants}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.decision_trigger}</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Offer stack" icon={PackageCheck}>
            <div className="space-y-3">
              {report.offer_stack.map((item) => (
                <div key={item.id} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="ok">{item.target_buyer}</Badge>
                    <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                  </div>
                  <p className="mt-2 break-words text-sm text-muted-foreground">{item.commercial_note}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.routes.map((route) => (
                      <Link
                        key={`${item.id}-${route}`}
                        to={toAppRoute(route)}
                        className="inline-flex h-8 items-center rounded-md border border-border bg-background px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
                      >
                        {route}
                      </Link>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="30 / 60 / 90" icon={Target}>
            <div className="space-y-3">
              {report.plan_30_60_90.map((item) => (
                <div key={item.stage} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{item.stage}</Badge>
                    <p className="break-words text-sm font-semibold text-card-foreground">{item.goal}</p>
                  </div>
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
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Assumptions" icon={FileText}>
            <KeyValue
              values={{
                "AI / month": money(report.assumptions.monthly_ai_subscription_cost, report.assumptions.currency),
                "Review hours": nf.format(report.assumptions.manual_review_hours_month),
                "Hourly rate": money(report.assumptions.hourly_rate, report.assumptions.currency),
                "Incident": money(report.assumptions.incident_cost, report.assumptions.currency),
                "Modules": nf.format(report.summary.modules),
              }}
            />
          </Panel>

          <Panel title="Objections" icon={ShieldCheck}>
            <div className="space-y-3">
              {report.objections.map((item) => (
                <div key={item.question} className="rounded-lg border border-border bg-background/60 p-3">
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.question}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.answer}</p>
                  <Link
                    to={toAppRoute(item.proof_route)}
                    className="mt-3 inline-flex h-8 items-center rounded-md border border-border bg-background px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
                  >
                    Proof
                  </Link>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Evidence routes" icon={Briefcase}>
            <div className="flex flex-wrap gap-2">
              {report.evidence_routes.map((route) => (
                <Link
                  key={`${route.label}-${route.to}`}
                  to={toAppRoute(route.to)}
                  className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-3 text-sm font-semibold text-card-foreground transition hover:bg-accent"
                >
                  {route.label}
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Caveats" icon={AlertTriangle}>
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

function BusinessRoomBridge({ bridge }: { bridge: BusinessCaseResponse["business_room_bridge"] }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-background/60">
      <div className="flex flex-col gap-3 border-b border-border px-4 py-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <DollarSign size={17} className="text-primary" />
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
            to={toAppRoute(bridge.business_motion.route)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-semibold text-card-foreground transition hover:bg-accent"
          >
            <RouteIcon size={15} />
            Value
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_320px]">
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

function SubscriptionEscapePanel({ plan }: { plan: BusinessCaseResponse["subscription_escape_plan"] }) {
  return (
    <Panel title="Subscription escape" icon={ShieldCheck}>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">AI / year</p>
          <p className="mt-1 break-words text-lg font-bold text-card-foreground">
            {money(plan.annual_ai_rent, plan.currency)}
          </p>
        </div>
        <div className="rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">3-year rent</p>
          <p className="mt-1 break-words text-lg font-bold text-card-foreground">
            {money(plan.three_year_ai_rent, plan.currency)}
          </p>
        </div>
        <div className="rounded-lg border border-primary/30 bg-primary/10 p-3">
          <p className="text-xs font-semibold uppercase text-primary">Local anchor</p>
          <p className="mt-1 break-words text-lg font-bold text-primary">
            {money(plan.local_license_anchor, plan.currency)}
          </p>
        </div>
        <div className="rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Break-even</p>
          <p className="mt-1 break-words text-lg font-bold text-card-foreground">
            {nf.format(plan.break_even_months)} months
          </p>
        </div>
      </div>

      <p className="mt-4 break-words text-sm font-medium text-card-foreground">{plan.headline}</p>
      <p className="mt-2 break-words text-sm text-muted-foreground">{plan.decision_line}</p>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        {plan.stakeholder_lines.map((item) => (
          <Link
            key={item.role}
            to={toAppRoute(item.route)}
            className="rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
          >
            <p className="break-words text-sm font-semibold text-card-foreground">{item.role}</p>
            <p className="mt-1 break-words text-xs text-muted-foreground">{item.line}</p>
          </Link>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {plan.evidence_files.map((item) => (
          <Link
            key={`${item.title}-${item.filename}`}
            to={toAppRoute(item.route)}
            className="inline-flex max-w-full items-center rounded-md border border-border bg-background px-2 py-1 font-mono text-xs font-semibold text-card-foreground transition hover:bg-accent"
          >
            <span className="truncate">{item.filename}</span>
          </Link>
        ))}
      </div>

      <ul className="mt-4 grid grid-cols-1 gap-2 text-xs text-muted-foreground md:grid-cols-2">
        {plan.guardrails.map((item) => (
          <li key={item} className="break-words rounded-lg bg-muted px-3 py-2">{item}</li>
        ))}
      </ul>
    </Panel>
  )
}

function LeverCard({ lever }: { lever: BusinessCaseLever }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="break-words text-sm font-semibold text-card-foreground">{lever.title}</p>
          <p className="mt-1 text-xs font-semibold uppercase text-muted-foreground">{lever.audience}</p>
        </div>
        <Badge tone={lever.annual_value ? "ok" : "muted"}>
          {lever.annual_value ? money(lever.annual_value, lever.currency) : "strategic"}
        </Badge>
      </div>
      <p className="mt-3 break-words text-sm text-muted-foreground">{lever.why_buy_now}</p>
      <p className="mt-2 break-words text-xs text-muted-foreground">{lever.evidence}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Badge tone="muted">{lever.confidence}</Badge>
        <Link
          to={toAppRoute(lever.route)}
          className="inline-flex h-8 items-center rounded-md border border-border bg-background px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
        >
          Evidence
        </Link>
      </div>
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

function Metric({ label, value, icon: Icon }: { label: string; value: number | string; icon: LucideIcon }) {
  return (
    <div className="min-w-0 border-b border-r border-border p-4 md:border-b-0">
      <div className="flex items-center gap-2 text-xs font-medium uppercase text-muted-foreground">
        <Icon size={15} />
        <span>{label}</span>
      </div>
      <div className="mt-1 break-words text-lg font-bold text-card-foreground sm:text-xl">{typeof value === "number" ? nf.format(value) : value}</div>
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
  if (status === "risk") return <XCircle size={20} className="shrink-0 text-destructive" />
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

function money(value: number, currency: string): string {
  return `${nf.format(Math.round(value))} ${currency}`
}
