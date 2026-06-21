import { useEffect, useRef, useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileText,
  GitPullRequest,
  Loader2,
  LockKeyhole,
  RefreshCw,
  Route as RouteIcon,
  ShieldCheck,
  TestTube2,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  safeAutopilotApi,
  type SafeAutopilotApprovalResponse,
  type SafeAutopilotResponse,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/safe-autopilot")({
  component: SafeAutopilotPage,
})

const nf = new Intl.NumberFormat("ru-RU")
const sampleModule = "CommonModules/DemoProof/Ext/Module.bsl"

type AppRoute =
  | "/safe-autopilot"
  | "/change"
  | "/quality"
  | "/testing"
  | "/release-readiness"
  | "/evidence-bundle"

const appRoutes = [
  "/safe-autopilot",
  "/change",
  "/quality",
  "/testing",
  "/release-readiness",
  "/evidence-bundle",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/safe-autopilot"
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

function SafeAutopilotPage() {
  const [goal, setGoal] = useState("Fix LEFT JOIN NULL fields safely")
  const [modulesText, setModulesText] = useState(sampleModule)
  const [diff, setDiff] = useState("")
  const [allowWrite, setAllowWrite] = useState(false)
  const autoBuildStarted = useRef(false)

  const buildPlanBody = () => ({
    goal: goal.trim() || "Plan a safe 1C change",
    changed_modules: modulesText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean),
    diff: diff.trim() || undefined,
    allow_write: allowWrite,
  })

  const mutation = useMutation({
    mutationFn: () =>
      safeAutopilotApi
        .plan(buildPlanBody())
        .then((r) => r.data),
  })

  const approvalMutation = useMutation({
    mutationFn: () =>
      safeAutopilotApi
        .requestApproval({
          ...buildPlanBody(),
          allow_write: true,
          approval_reason: `Safe Autopilot approval for ${goal.trim() || "1C change"}`,
        })
        .then((r) => r.data),
  })

  useEffect(() => {
    if (autoBuildStarted.current) return
    autoBuildStarted.current = true
    mutation.mutate()
  }, [mutation.mutate])

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <Bot size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Safe Autopilot
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Read-only Ask/Plan/Impact/Diff/Test/Evidence route for 1C changes.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} score={mutation.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Change request</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <TextField label="Goal" value={goal} onChange={setGoal} />
            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Changed modules</span>
              <textarea
                value={modulesText}
                onChange={(event) => setModulesText(event.target.value)}
                spellCheck={false}
                className="min-h-[120px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Diff</span>
              <textarea
                value={diff}
                onChange={(event) => setDiff(event.target.value)}
                spellCheck={false}
                placeholder="Optional unified diff"
                className="min-h-[150px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              />
            </label>
            <label className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/60 px-3 py-2">
              <span className="text-sm font-medium text-card-foreground">Request write action</span>
              <input
                type="checkbox"
                checked={allowWrite}
                onChange={(event) => setAllowWrite(event.target.checked)}
                className="h-4 w-4 accent-primary"
              />
            </label>
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Build safe plan
            </button>
            {mutation.data && (
              <button
                onClick={() => downloadMarkdown(mutation.data.download_name, mutation.data.markdown)}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:bg-accent"
              >
                <Download size={16} />
                Download markdown
              </button>
            )}
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          {mutation.isPending && (
            <div className="flex min-h-[560px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <Loader2 size={42} className="animate-spin opacity-60" />
              <p className="text-sm">Building read-only change plan.</p>
            </div>
          )}

          {!mutation.data && !mutation.isError && !mutation.isPending && (
            <div className="flex min-h-[560px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <Bot size={42} className="opacity-30" />
              <p className="text-sm">Ready to build Safe Autopilot plan.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[560px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Safe Autopilot did not build. Check backend and inputs.</p>
            </div>
          )}

          {mutation.data && (
            <SafeAutopilotReport
              report={mutation.data}
              approvalRecord={approvalMutation.data?.record}
              approvalPending={approvalMutation.isPending}
              approvalError={approvalMutation.isError}
              onRequestApproval={() => approvalMutation.mutate()}
            />
          )}
        </section>
      </div>
    </div>
  )
}

function SafeAutopilotReport({
  report,
  approvalRecord,
  approvalPending,
  approvalError,
  onRequestApproval,
}: {
  report: SafeAutopilotResponse
  approvalRecord?: SafeAutopilotApprovalResponse["record"]
  approvalPending: boolean
  approvalError: boolean
  onRequestApproval: () => void
}) {
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
          <p className="mt-2 break-words text-sm text-muted-foreground">{report.scenario.why}</p>
        </div>
        <Link
          to={toAppRoute(report.scenario.route)}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
        >
          <RouteIcon size={16} />
          {report.scenario.title}
        </Link>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-7">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Modules" value={report.summary.changed_modules} icon={FileText} />
        <Metric label="Impact" value={report.summary.impact_edges} icon={GitPullRequest} />
        <Metric label="Violations" value={report.summary.violations} icon={AlertTriangle} />
        <Metric label="Tests" value={report.summary.tests} icon={TestTube2} />
        <Metric label="Diffs" value={report.summary.diff_candidates} icon={GitPullRequest} />
        <Metric label="Write" value={report.summary.write_allowed ? "allowed" : "blocked"} icon={LockKeyhole} />
      </div>

      <div className="border-b border-border p-4 sm:p-5">
        <Panel title="Safety policy" icon={LockKeyhole}>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
            <PolicyFact label="Mode" value={report.safety_policy.mode} />
            <PolicyFact label="Direct apply" value={report.safety_policy.direct_apply ? "yes" : "no"} />
            <PolicyFact label="Writes" value={report.safety_policy.writes_allowed ? "yes" : "no"} />
            <PolicyFact label="Approval" value={report.safety_policy.approval_required ? "required" : "not required"} />
          </div>
          <p className="mt-3 break-words text-sm text-muted-foreground">{report.safety_policy.audit_line}</p>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Flow" icon={RouteIcon}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.steps.map((step) => (
                <div key={step.id} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="break-words text-sm font-semibold text-card-foreground">{step.title}</p>
                      <p className="mt-0.5 text-xs font-medium uppercase text-muted-foreground">{step.owner}</p>
                    </div>
                    <Badge tone={toneForStatus(step.status)}>{step.status}</Badge>
                  </div>
                  <p className="mt-2 break-words text-sm text-muted-foreground">{step.action}</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Patch blueprint" icon={ClipboardCheck}>
            <div className="rounded-lg border border-border bg-background/60 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="muted">{report.patch_blueprint.mode}</Badge>
                <p className="break-words text-sm font-semibold text-card-foreground">{report.patch_blueprint.title}</p>
              </div>
              <div className="mt-3 space-y-2">
                {report.patch_blueprint.changes.map((item) => (
                  <div key={item} className="flex gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-600" />
                    <span className="break-words">{item}</span>
                  </div>
                ))}
              </div>
              <p className="mt-3 break-words text-xs text-muted-foreground">{report.patch_blueprint.risk}</p>
              <p className="mt-2 break-words text-xs font-semibold text-muted-foreground">{report.patch_blueprint.test}</p>
            </div>
          </Panel>

          <DiffProposalPanel proposal={report.diff_proposal} />

          <Panel title="Tests" icon={TestTube2}>
            {report.tests.length ? (
              <div className="space-y-3">
                {report.tests.map((test) => (
                  <div key={`${test.module_path}-${test.selector}`} className="rounded-lg border border-border bg-background/60 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={test.priority === "high" ? "danger" : "warn"}>{test.priority}</Badge>
                      <Badge tone="muted">{test.status}</Badge>
                      <span className="break-words text-xs font-semibold text-card-foreground">{test.framework}</span>
                    </div>
                    <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{test.module_path}</p>
                    <p className="mt-2 break-words text-sm text-card-foreground">{test.reason}</p>
                    <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{test.command}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No tests mapped yet; add changed modules or diff.</p>
            )}
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Impact gate" icon={ShieldCheck}>
            <div className="space-y-3">
              <PolicyFact label="Gate" value={report.impact.gate.status} />
              {Object.entries(report.impact.gate.summary ?? {}).map(([key, value]) => (
                <PolicyFact key={key} label={key} value={nf.format(Number(value) || 0)} />
              ))}
              {report.impact.unmeasured_modules.slice(0, 5).map((item) => (
                <div key={item} className="rounded-md bg-muted p-2">
                  <p className="break-all font-mono text-xs text-muted-foreground">{item}</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Approvals" icon={ClipboardCheck}>
            <div className="space-y-2">
              {report.approvals.map((item) => (
                <div key={item.role} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={item.required === "yes" ? "warn" : "muted"}>{item.required}</Badge>
                    <p className="break-words text-sm font-semibold text-card-foreground">{item.role}</p>
                  </div>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.reason}</p>
                </div>
              ))}
            </div>
          </Panel>

          <ApprovalHandoffPanel
            handoff={report.approval_handoff}
            approvalRecord={approvalRecord}
            approvalPending={approvalPending}
            approvalError={approvalError}
            onRequestApproval={onRequestApproval}
          />

          <AiIndependencePanel ai={report.ai_independence} />

          <Panel title="Evidence" icon={FileText}>
            <div className="space-y-2">
              {report.evidence.map((item) => (
                <Link
                  key={`${item.title}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
                >
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                  <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{item.artifact}</p>
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

          <Panel title="Markdown" icon={FileText}>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {report.markdown}
            </pre>
          </Panel>
        </aside>
      </div>
    </div>
  )
}

function TextField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
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

function PolicyFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-card-foreground">{value}</p>
    </div>
  )
}

function DiffProposalPanel({ proposal }: { proposal: SafeAutopilotResponse["diff_proposal"] }) {
  return (
    <Panel title="Diff proposal" icon={GitPullRequest}>
      <div className="space-y-3">
        <div className="rounded-lg border border-border bg-background/60 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={proposal.status === "manual_review" ? "warn" : "muted"}>{proposal.status}</Badge>
            <Badge tone={proposal.direct_apply ? "danger" : "ok"}>
              direct apply {proposal.direct_apply ? "on" : "off"}
            </Badge>
          </div>
          <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{proposal.title}</p>
          <p className="mt-2 break-words text-xs text-muted-foreground">{proposal.caveat}</p>
        </div>

        {proposal.candidates.length ? (
          proposal.candidates.map((candidate) => (
            <div key={candidate.id} className="rounded-lg border border-border bg-background/60 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="warn">{candidate.confidence}</Badge>
                <Badge tone={candidate.approval_required ? "warn" : "ok"}>
                  {candidate.approval_required ? "approval" : "ready"}
                </Badge>
              </div>
              <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{candidate.target}</p>
              <p className="mt-2 break-words text-sm text-card-foreground">{candidate.finding}</p>
              <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
                <CodeBlock label="Before" value={candidate.before} />
                <CodeBlock label="After" value={candidate.after} />
              </div>
              <pre className="mt-3 max-h-52 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 font-mono text-xs text-muted-foreground">
                {candidate.unified_diff}
              </pre>
              <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
                <Checklist title="Review" items={candidate.review_notes} />
                <Checklist title="Tests" items={candidate.tests} />
              </div>
            </div>
          ))
        ) : (
          <p className="rounded-lg border border-border bg-background/60 p-3 text-sm text-muted-foreground">
            No deterministic diff candidates for this scenario yet.
          </p>
        )}

        <Checklist title="Acceptance" items={proposal.acceptance} />
      </div>
    </Panel>
  )
}

function ApprovalHandoffPanel({
  handoff,
  approvalRecord,
  approvalPending,
  approvalError,
  onRequestApproval,
}: {
  handoff: SafeAutopilotResponse["approval_handoff"]
  approvalRecord?: SafeAutopilotApprovalResponse["record"]
  approvalPending: boolean
  approvalError: boolean
  onRequestApproval: () => void
}) {
  return (
    <Panel title="Approval handoff" icon={ClipboardCheck}>
      <div className="space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <PolicyFact label="Status" value={handoff.status} />
          <PolicyFact label="Approval" value={handoff.can_request_approval ? "requestable" : "needs scope"} />
          <PolicyFact label="Endpoint" value={handoff.request_endpoint} />
          <PolicyFact label="Record" value={handoff.approval_record_kind} />
        </div>
        <p className="break-words text-sm text-muted-foreground">{handoff.handoff_line}</p>
        <p className="break-words text-xs font-semibold text-card-foreground">{handoff.local_asset_line}</p>

        <button
          onClick={onRequestApproval}
          disabled={!handoff.can_request_approval || approvalPending}
          className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-semibold text-card-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60"
        >
          {approvalPending ? <Loader2 size={16} className="animate-spin" /> : <ClipboardCheck size={16} />}
          Request approval record
        </button>

        {approvalError && (
          <p className="rounded-lg border border-destructive/25 bg-destructive/10 p-3 text-sm text-destructive">
            Approval request failed. Check auth, scope and backend logs.
          </p>
        )}

        {approvalRecord && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="ok">{approvalRecord.status}</Badge>
              <Badge tone="muted">{approvalRecord.risk}</Badge>
            </div>
            <p className="mt-2 break-all font-mono text-xs text-card-foreground">{approvalRecord.id}</p>
            <p className="mt-2 break-words text-xs text-muted-foreground">
              {approvalRecord.tool_name} requested by {approvalRecord.requested_by}; expires {new Date(approvalRecord.expires_at).toLocaleString("ru-RU")}.
            </p>
          </div>
        )}

        <Checklist title="Blocked" items={handoff.blocked_actions} />

        <div className="space-y-2">
          {handoff.roles.map((item) => (
            <Link
              key={item.role}
              to={toAppRoute(item.route)}
              className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={item.required === "yes" ? "warn" : "muted"}>{item.required}</Badge>
                <p className="break-words text-sm font-semibold text-card-foreground">{item.role}</p>
              </div>
              <p className="mt-2 break-words text-xs text-muted-foreground">{item.decision}</p>
            </Link>
          ))}
        </div>

        <div className="space-y-2">
          {handoff.evidence_packet.map((item) => (
            <Link
              key={item.artifact}
              to={toAppRoute(item.route)}
              className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
            >
              <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
              <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{item.artifact}</p>
              <p className="mt-2 break-words text-xs text-muted-foreground">{item.why}</p>
            </Link>
          ))}
        </div>

        <Checklist title="Audit" items={handoff.audit_requirements} />
      </div>
    </Panel>
  )
}

function AiIndependencePanel({ ai }: { ai: SafeAutopilotResponse["ai_independence"] }) {
  return (
    <Panel title="AI independence" icon={Bot}>
      <div className="space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <PolicyFact label="Mode" value={ai.mode} />
          <PolicyFact label="External AI" value={ai.external_ai_required ? "required" : "optional"} />
        </div>
        <p className="break-words text-sm text-muted-foreground">{ai.buyer_line}</p>
        <p className="break-words text-xs font-semibold text-card-foreground">{ai.license_line}</p>

        <div className="space-y-2">
          {ai.local_sources.map((item) => (
            <div key={item.title} className="rounded-lg border border-border bg-background/60 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={item.available ? "ok" : "warn"}>{item.available ? "available" : "missing"}</Badge>
                <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
              </div>
              <p className="mt-2 break-words text-xs text-muted-foreground">{item.evidence}</p>
            </div>
          ))}
        </div>

        <Checklist title="Deterministic" items={ai.deterministic_rules} />
        <Checklist title="AI controls" items={ai.optional_ai_controls} />
      </div>
    </Panel>
  )
}

function CodeBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-border bg-background p-3">
      <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
      <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-xs text-card-foreground">{value}</pre>
    </div>
  )
}

function Checklist({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="min-w-0 rounded-lg border border-border bg-background p-3">
      <p className="text-xs font-semibold uppercase text-muted-foreground">{title}</p>
      <div className="mt-2 space-y-2">
        {items.map((item) => (
          <div key={item} className="flex gap-2 text-sm text-muted-foreground">
            <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-600" />
            <span className="break-words">{item}</span>
          </div>
        ))}
      </div>
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

function toneForStatus(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "ready" || status === "pass" || status === "planned") return "ok"
  if (status === "risk" || status === "fail" || status === "blocked") return "danger"
  if (status === "watch" || status === "warn" || status === "approval_required") return "warn"
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
