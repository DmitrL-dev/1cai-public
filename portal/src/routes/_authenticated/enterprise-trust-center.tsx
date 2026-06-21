import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  Archive,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileCheck2,
  FileText,
  Fingerprint,
  ListChecks,
  Loader2,
  LockKeyhole,
  PackageCheck,
  PlayCircle,
  RefreshCw,
  Route as RouteIcon,
  ServerCog,
  ShieldCheck,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { BuyerRoomPacketControls } from "@/components/BuyerRoomPacketControls"
import { OpenFirstPathList } from "@/components/OpenFirstPathList"
import { VerificationPacketControls } from "@/components/VerificationPacketControls"
import {
  enterpriseTrustCenterApi,
  type EnterpriseTrustCenterResponse,
  type EvidenceBundleRequest,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/enterprise-trust-center")({
  component: EnterpriseTrustCenterPage,
})

const nf = new Intl.NumberFormat("ru-RU")

type ScanDepth = "preview" | "standard" | "deep"

const depthProfiles: Record<
  ScanDepth,
  {
    governance_limit: number
    hotspot_limit: number
    security_limit: number
    security_module_limit: number
    rights_role_limit: number
    rights_object_limit: number
  }
> = {
  preview: {
    governance_limit: 10,
    hotspot_limit: 5,
    security_limit: 30,
    security_module_limit: 1,
    rights_role_limit: 10,
    rights_object_limit: 40,
  },
  standard: {
    governance_limit: 40,
    hotspot_limit: 12,
    security_limit: 120,
    security_module_limit: 1200,
    rights_role_limit: 60,
    rights_object_limit: 160,
  },
  deep: {
    governance_limit: 80,
    hotspot_limit: 24,
    security_limit: 300,
    security_module_limit: 3000,
    rights_role_limit: 120,
    rights_object_limit: 400,
  },
}

const depthLabels: Record<ScanDepth, string> = {
  preview: "Preview",
  standard: "Standard",
  deep: "Deep",
}

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
  | "/security"
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
  "/security",
  "/approvals",
  "/audit",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/enterprise-trust-center"
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

function EnterpriseTrustCenterPage() {
  const [clientName, setClientName] = useState("Demo client")
  const [configPath, setConfigPath] = useState("data/configs/unpacked")
  const [targetVersion, setTargetVersion] = useState("")
  const [scanDepth, setScanDepth] = useState<ScanDepth>("preview")
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
    include_enterprise_trust_center: true,
    include_killer_demo: true,
  })

  const mutation = useMutation({
    mutationFn: () =>
      enterpriseTrustCenterApi
        .build({
          client_name: clientName.trim() || "Demo client",
          config_path: configPath.trim() || undefined,
          target_platform_version: targetVersion.trim() || undefined,
          analysis_depth: scanDepth,
          ...depthProfiles[scanDepth],
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
              <ShieldCheck size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Enterprise Trust Center
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Security, CIO and procurement proof for local contour, SBOM/offline delivery, rights, platform caveats and approval artifacts.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} score={mutation.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Trust inputs</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <TextField label="Client" value={clientName} onChange={setClientName} />
            <TextField label="EDT/XML path" value={configPath} onChange={setConfigPath} mono />
            <TextField label="Target platform" value={targetVersion} onChange={setTargetVersion} placeholder="8.3.26.x" />
            <div className="space-y-1.5">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Analysis depth</span>
              <div className="grid grid-cols-3 gap-1 rounded-lg border border-border bg-background p-1">
                {(Object.keys(depthProfiles) as ScanDepth[]).map((depth) => (
                  <button
                    key={depth}
                    type="button"
                    onClick={() => setScanDepth(depth)}
                    className={cn(
                      "h-9 rounded-md px-2 text-xs font-semibold transition sm:text-sm",
                      scanDepth === depth
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-foreground",
                    )}
                  >
                    {depthLabels[depth]}
                  </button>
                ))}
              </div>
            </div>
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
              Build trust center
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
              <ShieldCheck size={42} className="opacity-30" />
              <p className="text-sm">Waiting for trust inputs.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Enterprise Trust Center did not build. Check backend and inputs.</p>
            </div>
          )}

          {mutation.data && <TrustCenterReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function TrustCenterReport({ report }: { report: EnterpriseTrustCenterResponse }) {
  const questionnaire = report.security_questionnaire

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

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-4 xl:grid-cols-8">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Controls" value={report.summary.controls} icon={ClipboardCheck} />
        <Metric label="Pass" value={report.summary.passed_controls} icon={CheckCircle2} />
        <Metric label="Warn" value={report.summary.warning_controls} icon={AlertTriangle} />
        <Metric label="Fail" value={report.summary.failed_controls} icon={XCircle} />
        <Metric label="Q ready" value={report.summary.questionnaire_ready} icon={FileCheck2} />
        <Metric label="Q block" value={report.summary.questionnaire_blocked} icon={AlertTriangle} />
        <Metric label="Procure" value={report.summary.procurement_items} icon={FileText} />
      </div>

      <div className="border-b border-border p-4 sm:p-5">
        <TrustRoomBridge bridge={report.trust_room_bridge} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Security questionnaire" icon={FileCheck2}>
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <div className="rounded-lg border border-border bg-background/60 p-3">
                  <Badge tone={controlTone(questionnaire.status)}>{questionnaire.status}</Badge>
                  <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{questionnaire.owner_line}</p>
                </div>
                <div className="rounded-lg border border-border bg-background/60 p-3">
                  <p className="text-xs font-semibold uppercase text-muted-foreground">Send</p>
                  <p className="mt-2 text-sm font-semibold text-card-foreground">
                    {questionnaire.ready_to_send ? "ready" : "blocked"}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Approve: {questionnaire.ready_to_approve ? "ready" : "needs review"}
                  </p>
                </div>
                <div className="rounded-lg border border-border bg-background/60 p-3">
                  <p className="text-xs font-semibold uppercase text-muted-foreground">Sections</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge tone="ok">{questionnaire.ready_sections} ready</Badge>
                    <Badge tone="warn">{questionnaire.watch_sections} watch</Badge>
                    <Badge tone="danger">{questionnaire.blocked_sections} blocked</Badge>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                {questionnaire.sections.map((section) => (
                  <Link
                    key={section.id}
                    to={toAppRoute(section.proof_routes[0] || "/enterprise-trust-center")}
                    className="min-w-0 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={controlTone(section.status)}>{section.status}</Badge>
                      <Badge tone="muted">{section.audience}</Badge>
                      <Badge tone="muted">{section.owner}</Badge>
                    </div>
                    <h3 className="mt-3 break-words text-sm font-semibold text-card-foreground">{section.title}</h3>
                    <p className="mt-2 break-words text-sm text-muted-foreground">{section.answer}</p>
                    <p className="mt-2 break-words text-xs text-card-foreground">{section.acceptance}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {section.evidence_files.map((file) => (
                        <span key={`${section.id}-${file}`} className="max-w-full break-all rounded-md bg-muted px-2 py-1 font-mono text-[11px] text-muted-foreground">
                          {file}
                        </span>
                      ))}
                    </div>
                    {section.blockers.length > 0 && (
                      <div className="mt-3 space-y-1">
                        {section.blockers.map((blocker) => (
                          <p key={`${section.id}-${blocker}`} className="break-words text-xs font-semibold text-destructive">
                            {blocker}
                          </p>
                        ))}
                      </div>
                    )}
                    {section.caveats.length > 0 && (
                      <div className="mt-3 space-y-1">
                        {section.caveats.map((caveat) => (
                          <p key={`${section.id}-${caveat}`} className="break-words text-xs text-amber-700 dark:text-amber-300">
                            {caveat}
                          </p>
                        ))}
                      </div>
                    )}
                  </Link>
                ))}
              </div>

              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                <div className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="mb-3 flex items-center gap-2">
                    <FileText size={15} className="text-primary" />
                    <p className="text-sm font-semibold text-card-foreground">Send files</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {questionnaire.send_files.map((file) => (
                      <span key={file} className="max-w-full break-all rounded-md bg-muted px-2 py-1 font-mono text-[11px] text-muted-foreground">
                        {file}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="mb-3 flex items-center gap-2">
                    <ListChecks size={15} className="text-primary" />
                    <p className="text-sm font-semibold text-card-foreground">Verification steps</p>
                  </div>
                  <div className="space-y-3">
                    {questionnaire.verification_steps.map((step) => (
                      <Link
                        key={`${step.owner}-${step.route}`}
                        to={toAppRoute(step.route)}
                        className="block rounded-md border border-border bg-background p-2 transition hover:bg-accent"
                      >
                        <Badge tone="muted">{step.owner}</Badge>
                        <p className="mt-2 break-words text-xs text-card-foreground">{step.action}</p>
                        <p className="mt-1 break-words text-xs text-muted-foreground">{step.expected}</p>
                      </Link>
                    ))}
                  </div>
                </div>
              </div>

              {questionnaire.high_risks.length > 0 && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <AlertTriangle size={15} className="text-destructive" />
                    <p className="text-sm font-semibold text-card-foreground">High risks in the pack</p>
                  </div>
                  <div className="mt-3 space-y-2">
                    {questionnaire.high_risks.map((risk) => (
                      <Link
                        key={`${risk.route}-${risk.risk}`}
                        to={toAppRoute(risk.route)}
                        className="block rounded-md border border-border bg-background/80 p-2 transition hover:bg-accent"
                      >
                        <div className="flex flex-wrap gap-2">
                          <Badge tone={severityTone(risk.severity)}>{risk.severity}</Badge>
                          <Badge tone="muted">{risk.owner}</Badge>
                        </div>
                        <p className="mt-2 break-words text-xs font-semibold text-card-foreground">{risk.risk}</p>
                        <p className="mt-1 break-words text-xs text-muted-foreground">{risk.next_action}</p>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Panel>

          <Panel title="Trust controls" icon={ShieldCheck}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {report.trust_controls.map((control) => (
                <Link
                  key={control.id}
                  to={toAppRoute(control.route)}
                  className="min-w-0 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={controlTone(control.status)}>{control.status}</Badge>
                    <Badge tone={severityTone(control.severity)}>{control.severity}</Badge>
                    <Badge tone="muted">{control.owner}</Badge>
                  </div>
                  <h3 className="mt-3 break-words text-sm font-semibold text-card-foreground">{control.title}</h3>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{control.evidence}</p>
                  <p className="mt-2 break-words text-sm text-card-foreground">{control.acceptance}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Security questions" icon={LockKeyhole}>
            <div className="space-y-3">
              {report.security_questions.map((item) => (
                <Link
                  key={item.question}
                  to={toAppRoute(item.proof_route)}
                  className="block rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <Badge tone="muted">{item.artifact}</Badge>
                  <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{item.question}</p>
                  <p className="mt-2 break-words text-sm text-muted-foreground">{item.answer}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Procurement pack" icon={PackageCheck}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.procurement_pack.map((item) => (
                <Link
                  key={`${item.owner}-${item.document}`}
                  to={toAppRoute(item.route)}
                  className="rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{item.owner}</Badge>
                    <Badge tone="muted">{item.document}</Badge>
                  </div>
                  <p className="mt-3 break-words text-xs text-muted-foreground">{item.why}</p>
                  <p className="mt-2 break-words text-sm font-medium text-card-foreground">{item.exit_criteria}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Risk register" icon={AlertTriangle}>
            <div className="space-y-3">
              {report.risk_register.map((item, index) => (
                <Link
                  key={`${item.route}-${index}-${item.risk}`}
                  to={toAppRoute(item.route)}
                  className="grid min-w-0 grid-cols-[34px_minmax(0,1fr)] gap-3 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted text-xs font-bold text-muted-foreground">
                    {index + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap gap-2">
                      <Badge tone={severityTone(item.severity)}>{item.severity}</Badge>
                      <Badge tone="muted">{item.owner}</Badge>
                    </div>
                    <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{item.risk}</p>
                    <p className="mt-2 break-words text-xs text-muted-foreground">{item.next_action}</p>
                  </div>
                </Link>
              ))}
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Install modes" icon={Building2}>
            <div className="space-y-3">
              {report.install_modes.map((mode) => (
                <div key={mode.id} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{mode.duration}</Badge>
                    <Badge tone="muted">{mode.buyer}</Badge>
                  </div>
                  <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{mode.title}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{mode.acceptance}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {mode.proof_routes.map((route) => (
                      <Link
                        key={`${mode.id}-${route}`}
                        to={toAppRoute(route)}
                        className="inline-flex h-7 items-center rounded-md border border-border bg-background px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
                      >
                        {route}
                      </Link>
                    ))}
                  </div>
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

          <Panel title="Proof routes" icon={Fingerprint}>
            <div className="flex flex-wrap gap-2">
              {report.proof_routes.map((route) => (
                <Link
                  key={route}
                  to={toAppRoute(route)}
                  className="inline-flex h-8 items-center rounded-md border border-border bg-background px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
                >
                  {route}
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Source signals" icon={ServerCog}>
            <KeyValue values={stringifyValues(report.source_signals)} />
          </Panel>

          <Panel title="Caveats" icon={Archive}>
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

function TrustRoomBridge({ bridge }: { bridge: EnterpriseTrustCenterResponse["trust_room_bridge"] }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-background/60">
      <div className="flex flex-col gap-3 border-b border-border px-4 py-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <ShieldCheck size={17} className="text-primary" />
            <h3 className="break-words text-sm font-semibold text-card-foreground sm:text-base">Buyer room map</h3>
            <Badge tone={controlTone(bridge.status)}>{bridge.status}</Badge>
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
            to={toAppRoute(bridge.trust_motion.route)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-semibold text-card-foreground transition hover:bg-accent"
          >
            <RouteIcon size={15} />
            Trust
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
                  <Badge tone={controlTone(card.status)}>{card.title}</Badge>
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
                  <Badge tone={controlTone(item.status)}>{item.status}</Badge>
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

function controlTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "pass" || status === "ready") return "ok"
  if (status === "fail" || status === "risk" || status === "blocked") return "danger"
  if (status === "warn" || status === "watch" || status === "review_required") return "warn"
  return "muted"
}

function severityTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "high") return "danger"
  if (status === "medium") return "warn"
  if (status === "low") return "ok"
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
