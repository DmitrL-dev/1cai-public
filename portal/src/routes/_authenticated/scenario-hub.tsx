import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  Layers3,
  Loader2,
  Map,
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
  scenarioHubApi,
  type ScenarioHubResponse,
  type ScenarioHubScenario,
  type EvidenceBundleRequest,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/scenario-hub")({
  component: ScenarioHubPage,
})

const nf = new Intl.NumberFormat("ru-RU")

type AppRoute =
  | "/"
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
  | "/security"

const appRoutes = [
  "/",
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
  "/security",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/scenario-hub"
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

function ScenarioHubPage() {
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
    include_scenario_hub: true,
    include_killer_demo: true,
  })

  const mutation = useMutation({
    mutationFn: () =>
      scenarioHubApi
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
              <Map size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Scenario Hub
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Pain-led buyer routes for developers, architects, directors, vendors, security and operations.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} score={mutation.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Scenario inputs</h2>
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
              Build scenario hub
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
              <Map size={42} className="opacity-30" />
              <p className="text-sm">Waiting for scenario inputs.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Scenario Hub did not build. Check backend and inputs.</p>
            </div>
          )}

          {mutation.data && <ScenarioHubReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function ScenarioHubReport({ report }: { report: ScenarioHubResponse }) {
  const scenariosById = Object.fromEntries(report.scenarios.map((item) => [item.id, item]))

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

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-6">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Scenarios" value={report.summary.scenarios} icon={Map} />
        <Metric label="Killer" value={report.summary.killer_scenarios} icon={Target} />
        <Metric label="Roles" value={report.summary.roles} icon={Users} />
        <Metric label="Proofs" value={report.summary.proof_routes} icon={RouteIcon} />
        <Metric label="Minutes" value={report.summary.total_minutes} icon={PlayCircle} />
      </div>

      <ScenarioRoomBridge report={report} />

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Recommended path" icon={Target}>
            <div className="space-y-3">
              {report.recommended_path.map((item) => (
                <Link
                  key={`${item.step}-${item.scenario_id}`}
                  to={toAppRoute(item.route)}
                  className="grid min-w-0 grid-cols-[42px_minmax(0,1fr)] gap-3 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-sm font-bold text-primary">
                    {item.step}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                      <Badge tone="muted">{item.role}</Badge>
                    </div>
                    <p className="mt-2 break-words text-xs text-muted-foreground">{item.why}</p>
                  </div>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Scenario gallery" icon={Layers3}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {report.scenarios.map((scenario) => (
                <ScenarioCard key={scenario.id} scenario={scenario} />
              ))}
            </div>
          </Panel>

          <Panel title="Role lenses" icon={Users}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.role_lenses.map((lens) => (
                <div key={lens.role} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{lens.role}</Badge>
                    <Link
                      to={toAppRoute(lens.first_route)}
                      className="inline-flex h-7 items-center rounded-md border border-border bg-background px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
                    >
                      First route
                    </Link>
                  </div>
                  <p className="mt-3 break-words text-sm text-muted-foreground">{lens.outcome}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {lens.scenario_ids.map((id) => {
                      const scenario = scenariosById[id]
                      return (
                        <Link
                          key={`${lens.role}-${id}`}
                          to={toAppRoute(scenario?.route ?? "/scenario-hub")}
                          className="inline-flex min-h-8 items-center rounded-md border border-border bg-background px-2 py-1 text-xs font-semibold text-card-foreground transition hover:bg-accent"
                        >
                          {scenario?.title ?? id}
                        </Link>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Objections" icon={AlertTriangle}>
            <div className="space-y-3">
              {report.objection_map.map((item) => (
                <div key={item.objection} className="rounded-lg border border-border bg-background/60 p-3">
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.objection}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.answer}</p>
                  <Link
                    to={toAppRoute(item.proof_route)}
                    className="mt-3 inline-flex h-8 items-center rounded-md border border-border bg-background px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
                  >
                    Proof route
                  </Link>
                </div>
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

          <Panel title="Source signals" icon={FileText}>
            <KeyValue values={stringifyValues(report.source_signals)} />
          </Panel>

          <Panel title="Caveats" icon={PackageCheck}>
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

function ScenarioRoomBridge({ report }: { report: ScenarioHubResponse }) {
  const bridge = report.scenario_room_bridge

  return (
    <div className="border-b border-border p-4 sm:p-5">
      <Panel title="Scenario room bridge" icon={Map}>
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
                to={toAppRoute(bridge.scenario_motion.route)}
                className="rounded-lg border border-border bg-muted p-3 transition hover:bg-accent"
              >
                <Badge tone={statusTone(bridge.scenario_motion.status)}>Scenario</Badge>
                <p className="mt-3 break-words text-sm font-semibold text-card-foreground">
                  {bridge.scenario_motion.label}
                </p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{bridge.scenario_motion.ask}</p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{bridge.scenario_motion.reason}</p>
              </Link>
            </div>
          </div>

          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Files to open first</p>
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
                  {(item.scenario_ids || []).length > 0 && (
                    <p className="mt-2 break-words text-xs text-muted-foreground">
                      {(item.scenario_ids || []).slice(0, 3).join(", ")}
                    </p>
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

function ScenarioCard({ scenario }: { scenario: ScenarioHubScenario }) {
  return (
    <Link
      to={toAppRoute(scenario.route)}
      className="min-w-0 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={scenario.severity >= 5 ? "danger" : scenario.severity >= 4 ? "warn" : "muted"}>
          S{scenario.severity}
        </Badge>
        <Badge tone="muted">{scenario.primary_role}</Badge>
        <Badge tone="muted">{scenario.minutes} min</Badge>
        <Badge tone={scenario.maturity === "live" ? "ok" : "warn"}>{scenario.maturity}</Badge>
      </div>
      <h3 className="mt-3 break-words text-sm font-semibold text-card-foreground">{scenario.title}</h3>
      <p className="mt-2 break-words text-xs text-muted-foreground">{scenario.pain}</p>
      <p className="mt-2 break-words text-sm text-card-foreground">{scenario.buyer_line}</p>
      <p className="mt-2 break-words text-xs text-muted-foreground">{scenario.success_signal}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {scenario.evidence_routes.map((route) => (
          <span
            key={`${scenario.id}-${route.to}`}
            className="inline-flex min-h-7 items-center rounded-md bg-muted px-2 py-1 text-xs font-semibold text-muted-foreground"
          >
            {route.label}
          </span>
        ))}
      </div>
    </Link>
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
