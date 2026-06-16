import { useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation, useQuery } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Code2,
  KeyRound,
  Loader2,
  Plug,
  RefreshCw,
  ShieldCheck,
  TerminalSquare,
  Workflow,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  approvalsApi,
  edtMcpApi,
  type EdtMcpCatalogResponse,
  type EdtMcpLiveTool,
  type EdtMcpPlanResponse,
  type EdtMcpStatusResponse,
} from "@/lib/api-client"
import { useAuthStore } from "@/stores/auth-store"

export const Route = createFileRoute("/_authenticated/edt-mcp")({
  component: EdtMcpPage,
})

type BadgeTone = "danger" | "warn" | "ok" | "muted" | "info"

const defaultBaseUrl = "http://127.0.0.1:8765"
const nf = new Intl.NumberFormat("ru-RU")

function EdtMcpPage() {
  const user = useAuthStore((state) => state.user)
  const [baseUrl, setBaseUrl] = useState(defaultBaseUrl)
  const [authToken, setAuthToken] = useState("")
  const [task, setTask] = useState("validate query, review impacted module, then run affected YAxUnit tests")
  const [selectedTool, setSelectedTool] = useState("validate_query")
  const [argsText, setArgsText] = useState("{}")
  const [confirm, setConfirm] = useState(false)
  const [actor, setActor] = useState("")
  const [approvalReason, setApprovalReason] = useState("")
  const [approvalTicket, setApprovalTicket] = useState("")
  const [approvalId, setApprovalId] = useState("")
  const [timeoutS, setTimeoutS] = useState(30)
  const [argsError, setArgsError] = useState<string | null>(null)
  const hasAuthToken = Boolean(authToken)
  const defaultActor = user?.username || user?.user_id || ""

  const catalogQ = useQuery({
    queryKey: ["edt-mcp-catalog"],
    queryFn: () => edtMcpApi.catalog().then((r) => r.data),
  })
  const statusQ = useQuery({
    queryKey: ["edt-mcp-status", baseUrl, hasAuthToken],
    queryFn: () => edtMcpApi.status(baseUrl, authToken || undefined).then((r) => r.data),
    retry: false,
  })
  const liveToolsQ = useQuery({
    queryKey: ["edt-mcp-live-tools", baseUrl, hasAuthToken],
    queryFn: () => edtMcpApi.liveTools(baseUrl, authToken || undefined).then((r) => r.data),
    enabled: false,
    retry: false,
  })
  const planM = useMutation({
    mutationFn: () => edtMcpApi.plan({ task }).then((r) => r.data),
  })
  const callM = useMutation({
    mutationFn: (parsedArgs: Record<string, unknown>) =>
      edtMcpApi.call(
        {
          tool_name: selectedTool,
          arguments: parsedArgs,
          base_url: baseUrl,
          confirm,
          actor: effectiveActor || undefined,
          approval_reason: approvalReason.trim() || undefined,
          approval_ticket: approvalTicket.trim() || undefined,
          approval_id: approvalId.trim() || undefined,
          timeout_s: timeoutS,
        },
        authToken || undefined,
      ).then((r) => r.data),
  })

  const liveTools = liveToolsQ.data?.tools ?? []
  const selectedLiveTool = useMemo(
    () => liveTools.find((item) => item.name === selectedTool),
    [liveTools, selectedTool],
  )
  const status = statusQ.data
  const selectedRequiresApproval = selectedLiveTool?.classification.requires_confirmation ?? confirm
  const effectiveActor = actor.trim() || defaultActor
  const approvalReasonReady = approvalReason.trim().length >= 12
  const hasApprovalId = Boolean(approvalId.trim())
  const approvalContextMissing = Boolean(
    selectedRequiresApproval && confirm && (!effectiveActor || (!hasApprovalId && !approvalReasonReady)),
  )
  const createApprovalM = useMutation({
    mutationFn: () =>
      approvalsApi.createEdtMcp({
        tool_name: selectedTool,
        actor: effectiveActor || undefined,
        approval_reason: approvalReason.trim(),
        approval_ticket: approvalTicket.trim() || undefined,
        argument_constraints: parseApprovalConstraints(argsText),
        expires_in_hours: 24,
      }).then((r) => r.data),
    onSuccess: (data) => setApprovalId(data.record.id),
  })
  const approveM = useMutation({
    mutationFn: () =>
      approvalsApi.approve(approvalId.trim(), {
        actor: effectiveActor || undefined,
        decision_reason: approvalReason.trim() || undefined,
      }).then((r) => r.data),
  })

  useEffect(() => {
    if (!actor && defaultActor) setActor(defaultActor)
  }, [actor, defaultActor])

  function runCall() {
    try {
      const parsed = argsText.trim() ? JSON.parse(argsText) : {}
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setArgsError("Arguments must be a JSON object.")
        return
      }
      setArgsError(null)
      callM.mutate(parsed as Record<string, unknown>)
    } catch (error) {
      setArgsError(error instanceof Error ? error.message : "Invalid JSON.")
    }
  }

  function selectTool(tool: EdtMcpLiveTool) {
    setSelectedTool(tool.name)
    setConfirm(false)
    setApprovalReason("")
    setApprovalTicket("")
    setApprovalId("")
    if (argsText.trim() === "{}" || !argsText.trim()) {
      setArgsText(formatJson(defaultArguments(tool.name)))
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-2">
              <Plug size={22} className="text-primary" />
            </div>
            <h1 className="min-w-0 break-words text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              EDT-MCP Bridge
            </h1>
          </div>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground sm:text-base">
            Native EDT automation with 1cAI planning, Rentgen context and a write/execute safety gate.
          </p>
        </div>

        <div className="grid w-full grid-cols-1 gap-3 rounded-lg border border-border bg-card p-3 xl:w-[560px] sm:grid-cols-[minmax(0,1fr)_180px]">
          <label className="block min-w-0 space-y-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Endpoint</span>
            <input
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              className="h-10 w-full rounded-md border border-border bg-background px-3 font-mono text-sm text-foreground outline-none focus:border-primary"
            />
          </label>
          <label className="block min-w-0 space-y-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Token</span>
            <div className="flex h-10 items-center gap-2 rounded-md border border-border bg-background px-3">
              <KeyRound size={15} className="shrink-0 text-muted-foreground" />
              <input
                value={authToken}
                onChange={(event) => setAuthToken(event.target.value)}
                type="password"
                className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none"
              />
            </div>
          </label>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="min-w-0 space-y-6">
          <section className="rounded-xl border border-border bg-card">
            <div className="flex flex-col gap-4 border-b border-border p-5 lg:flex-row lg:items-start lg:justify-between">
              <StatusHeader status={status} loading={statusQ.isFetching} />
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => statusQ.refetch()}
                  disabled={statusQ.isFetching}
                  className="inline-flex h-10 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-semibold text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <RefreshCw size={16} className={statusQ.isFetching ? "animate-spin" : undefined} />
                  Status
                </button>
                <button
                  onClick={() => liveToolsQ.refetch()}
                  disabled={liveToolsQ.isFetching}
                  className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {liveToolsQ.isFetching ? <Loader2 size={16} className="animate-spin" /> : <Workflow size={16} />}
                  Tools
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 border-b border-border md:grid-cols-4">
              <Metric label="Catalog Tools" value={catalogQ.data?.summary.tools ?? 0} icon={ClipboardList} />
              <Metric label="Live Tools" value={liveToolsQ.data?.summary?.tools ?? 0} icon={Plug} />
              <Metric label="Confirm" value={liveToolsQ.data?.summary?.requires_confirmation ?? 0} icon={ShieldCheck} />
              <Metric label="Toolsets" value={catalogQ.data?.summary.toolsets ?? 0} icon={Workflow} />
            </div>

            <div className="grid grid-cols-1 gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_320px]">
              <Panel title="Planner" icon={Workflow}>
                <div className="space-y-3">
                  <textarea
                    value={task}
                    onChange={(event) => setTask(event.target.value)}
                    spellCheck={false}
                    className="min-h-[110px] w-full resize-y rounded-md border border-border bg-background p-3 text-sm text-foreground outline-none transition focus:border-primary"
                  />
                  <button
                    onClick={() => planM.mutate()}
                    disabled={planM.isPending || !task.trim()}
                    className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {planM.isPending ? <Loader2 size={16} className="animate-spin" /> : <Workflow size={16} />}
                    Plan
                  </button>
                  {planM.data && <PlanResult plan={planM.data} />}
                  {planM.isError && <ErrorLine text="Planner request failed." />}
                </div>
              </Panel>

              <Panel title="Catalog" icon={ClipboardList}>
                <CatalogSummary catalog={catalogQ.data} />
              </Panel>
            </div>
          </section>

          <section className="rounded-xl border border-border bg-card">
            <div className="flex flex-col gap-3 border-b border-border p-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-base font-semibold text-card-foreground">Live Tools</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {liveToolsQ.data?.available
                    ? `${nf.format(liveTools.length)} tools from ${liveToolsQ.data.mcp_url ?? baseUrl}`
                    : liveToolsQ.data
                      ? "EDT-MCP did not return a live tool list."
                      : "No live tools loaded yet."}
                </p>
              </div>
              {liveToolsQ.data?.status && <Badge tone={liveToolsQ.data.available ? "ok" : "warn"}>{liveToolsQ.data.status}</Badge>}
            </div>
            <LiveToolsTable tools={liveTools} selectedTool={selectedTool} onSelect={selectTool} />
          </section>
        </div>

        <aside className="min-w-0 space-y-6">
          <section className="rounded-xl border border-border bg-card">
            <div className="border-b border-border p-5">
              <div className="flex items-center gap-2">
                <TerminalSquare size={19} className="text-primary" />
                <h2 className="min-w-0 break-words text-base font-semibold text-card-foreground">Safe Call</h2>
              </div>
              <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{selectedTool}</p>
            </div>

            <div className="space-y-4 p-5">
              <label className="block space-y-1.5">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tool</span>
                <input
                  value={selectedTool}
                  onChange={(event) => setSelectedTool(event.target.value)}
                  className="h-10 w-full rounded-md border border-border bg-background px-3 font-mono text-sm text-foreground outline-none focus:border-primary"
                />
              </label>

              {selectedLiveTool && <ToolRisk tool={selectedLiveTool} />}

              <label className="block space-y-1.5">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Actor</span>
                <input
                  value={actor}
                  onChange={(event) => setActor(event.target.value)}
                  placeholder={defaultActor || "user.name"}
                  className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>

              <label className="block space-y-1.5">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Arguments JSON</span>
                <textarea
                  value={argsText}
                  onChange={(event) => setArgsText(event.target.value)}
                  spellCheck={false}
                  className="min-h-[190px] w-full resize-y rounded-md border border-border bg-background p-3 font-mono text-xs text-foreground outline-none focus:border-primary"
                />
              </label>

              <div className="grid grid-cols-[minmax(0,1fr)_110px] gap-3">
                <label className="flex h-10 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm text-card-foreground">
                  <input
                    type="checkbox"
                    checked={confirm}
                    onChange={(event) => setConfirm(event.target.checked)}
                    className="h-4 w-4 accent-primary"
                  />
                  Confirm write/execute
                </label>
                <input
                  type="number"
                  min={1}
                  max={300}
                  value={timeoutS}
                  onChange={(event) => setTimeoutS(Number(event.target.value))}
                  className="h-10 rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </div>

              {(selectedRequiresApproval || confirm) && (
                <div className="space-y-3 rounded-md border border-amber-500/25 bg-amber-500/5 p-3">
                  <label className="block space-y-1.5">
                    <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Approval ID</span>
                    <input
                      value={approvalId}
                      onChange={(event) => setApprovalId(event.target.value)}
                      className="h-10 w-full rounded-md border border-border bg-background px-3 font-mono text-xs text-foreground outline-none focus:border-primary"
                    />
                  </label>
                  <label className="block space-y-1.5">
                    <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Approval reason
                    </span>
                    <textarea
                      value={approvalReason}
                      onChange={(event) => setApprovalReason(event.target.value)}
                      spellCheck={false}
                      className="min-h-[72px] w-full resize-y rounded-md border border-border bg-background p-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                  <label className="block space-y-1.5">
                    <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Ticket</span>
                    <input
                      value={approvalTicket}
                      onChange={(event) => setApprovalTicket(event.target.value)}
                      className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => createApprovalM.mutate()}
                      disabled={createApprovalM.isPending || !selectedTool.trim() || !effectiveActor || !approvalReasonReady}
                      className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-background px-3 text-xs font-semibold text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {createApprovalM.isPending ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
                      Create
                    </button>
                    <button
                      onClick={() => approveM.mutate()}
                      disabled={approveM.isPending || !approvalId.trim() || !effectiveActor}
                      className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-3 text-xs font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {approveM.isPending ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                      Approve
                    </button>
                  </div>
                  {createApprovalM.data && <Badge tone="info">{createApprovalM.data.record.status}</Badge>}
                  {approveM.data && <Badge tone="ok">{approveM.data.record.status}</Badge>}
                  {(createApprovalM.isError || approveM.isError) && <ErrorLine text="Approval workflow request failed." />}
                </div>
              )}

              {argsError && <ErrorLine text={argsError} />}

              <button
                onClick={runCall}
                disabled={callM.isPending || !selectedTool.trim() || approvalContextMissing}
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {callM.isPending ? <Loader2 size={16} className="animate-spin" /> : <Code2 size={16} />}
                Call Through Gate
              </button>

              {callM.data && <CallResult value={callM.data} />}
              {callM.isError && <ErrorLine text="EDT-MCP call failed before a structured response was returned." />}
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
}

function StatusHeader({ status, loading }: { status?: EdtMcpStatusResponse; loading: boolean }) {
  const available = Boolean(status?.available)
  const StatusIcon = loading ? Loader2 : available ? CheckCircle2 : status?.auth_required ? KeyRound : XCircle
  const tone = available ? "text-emerald-500" : status?.auth_required ? "text-amber-500" : "text-red-500"

  return (
    <div className="min-w-0">
      <div className="flex items-center gap-2">
        <StatusIcon size={24} className={cn(tone, loading && "animate-spin")} />
        <h2 className="min-w-0 break-words text-lg font-bold text-card-foreground">
          {status?.status ?? "checking"}
        </h2>
      </div>
      <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
        {status?.mcp_url || `${defaultBaseUrl}/mcp`}
      </p>
      {status?.errors?.length ? (
        <p className="mt-2 break-words text-xs text-muted-foreground">{status.errors[0]}</p>
      ) : null}
    </div>
  )
}

function PlanResult({ plan }: { plan: EdtMcpPlanResponse }) {
  return (
    <div className="space-y-3 rounded-md border border-border bg-background/60 p-3">
      <div className="flex flex-wrap gap-2">
        {plan.matched_workflows.map((item) => (
          <Badge key={item} tone="info">{item}</Badge>
        ))}
        <Badge tone={plan.requires_confirmation ? "warn" : "ok"}>
          {plan.requires_confirmation ? "confirm" : "read-only"}
        </Badge>
      </div>
      <ChipList title="EDT tools" values={plan.edt_tools} />
      <ChipList title="1cAI tools" values={plan.one_cai_tools} />
      <ChipList title="Toolsets" values={plan.toolsets_to_enable} />
    </div>
  )
}

function CatalogSummary({ catalog }: { catalog?: EdtMcpCatalogResponse }) {
  if (!catalog) return <EmptyLine icon={Loader2} text="Loading catalog." />
  return (
    <div className="space-y-3">
      {catalog.toolsets.slice(0, 8).map((toolset) => (
        <div key={toolset.id} className="rounded-md border border-border bg-background/60 p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-card-foreground">{toolset.title}</p>
              <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{toolset.purpose}</p>
            </div>
            <Badge tone={riskTone(toolset.risk)}>{toolset.risk}</Badge>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{toolset.tools.length} tools</p>
        </div>
      ))}
    </div>
  )
}

function LiveToolsTable({
  tools,
  selectedTool,
  onSelect,
}: {
  tools: EdtMcpLiveTool[]
  selectedTool: string
  onSelect: (tool: EdtMcpLiveTool) => void
}) {
  if (!tools.length) {
    return (
      <div className="flex min-h-[220px] flex-col items-center justify-center gap-2 p-6 text-center text-muted-foreground">
        <Plug size={34} className="opacity-30" />
        <p className="text-sm">Live EDT-MCP inventory is empty.</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[780px] text-left text-sm">
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-5 py-3 font-semibold">Tool</th>
            <th className="px-3 py-3 font-semibold">Risk</th>
            <th className="px-3 py-3 font-semibold">Toolset</th>
            <th className="px-5 py-3 font-semibold">Description</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {tools.map((tool) => (
            <tr
              key={tool.name}
              className={cn(
                "cursor-pointer transition hover:bg-muted/50",
                selectedTool === tool.name && "bg-primary/5",
              )}
              onClick={() => onSelect(tool)}
            >
              <td className="px-5 py-3">
                <p className="break-all font-mono text-xs font-semibold text-card-foreground">{tool.name}</p>
              </td>
              <td className="px-3 py-3">
                <Badge tone={riskTone(tool.classification.risk)}>{tool.classification.risk}</Badge>
              </td>
              <td className="px-3 py-3 text-xs text-muted-foreground">
                {tool.classification.toolset_id ?? "unknown"}
              </td>
              <td className="px-5 py-3">
                <p className="line-clamp-2 text-xs text-muted-foreground">{tool.description || tool.classification.safety_note}</p>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ToolRisk({ tool }: { tool: EdtMcpLiveTool }) {
  const classification = tool.classification
  return (
    <div className="rounded-md border border-border bg-background/60 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={riskTone(classification.risk)}>{classification.risk}</Badge>
        <Badge tone={classification.requires_confirmation ? "warn" : "ok"}>
          {classification.requires_confirmation ? "confirmation required" : "no confirmation"}
        </Badge>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{classification.safety_note}</p>
    </div>
  )
}

function CallResult({ value }: { value: unknown }) {
  const status = typeof value === "object" && value && "status" in value ? String((value as { status?: unknown }).status) : "result"
  return (
    <div className="rounded-md border border-border bg-background/60">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Badge tone={status === "ok" ? "ok" : status === "blocked" ? "warn" : "danger"}>{status}</Badge>
      </div>
      <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap p-3 font-mono text-xs text-muted-foreground">
        {formatJson(value)}
      </pre>
    </div>
  )
}

function Metric({ label, value, icon: Icon }: { label: string; value: number; icon: LucideIcon }) {
  return (
    <div className="border-b border-r border-border px-5 py-4 last:border-r-0 md:border-b-0">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <Icon size={16} className="text-primary" />
      </div>
      <p className="mt-2 text-2xl font-bold tabular-nums text-card-foreground">{nf.format(value)}</p>
    </div>
  )
}

function Panel({ title, icon: Icon, children }: { title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-background/50">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Icon size={15} className="text-primary" />
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      </div>
      <div className="p-3">{children}</div>
    </div>
  )
}

function ChipList({ title, values }: { title: string; values: string[] }) {
  return (
    <div>
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>
      <div className="flex flex-wrap gap-2">
        {values.map((item) => (
          <span key={item} className="rounded-md bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
            {item}
          </span>
        ))}
      </div>
    </div>
  )
}

function Badge({ tone, children }: { tone: BadgeTone; children: ReactNode }) {
  const tones: Record<BadgeTone, string> = {
    danger: "bg-red-500/10 text-red-600 dark:text-red-400 ring-red-500/25",
    warn: "bg-amber-500/10 text-amber-600 dark:text-amber-400 ring-amber-500/25",
    ok: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 ring-emerald-500/25",
    info: "bg-sky-500/10 text-sky-600 dark:text-sky-400 ring-sky-500/25",
    muted: "bg-muted text-muted-foreground ring-border",
  }
  return (
    <span className={cn("rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset", tones[tone])}>
      {children}
    </span>
  )
}

function EmptyLine({ icon: Icon, text }: { icon: LucideIcon; text: string }) {
  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Icon size={15} />
      {text}
    </p>
  )
}

function ErrorLine({ text }: { text: string }) {
  return (
    <p className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
      <AlertTriangle size={15} />
      <span className="break-words">{text}</span>
    </p>
  )
}

function riskTone(risk: string): BadgeTone {
  if (risk === "read") return "ok"
  if (risk === "session") return "info"
  if (risk === "write" || risk === "mixed") return "warn"
  if (risk === "execute" || risk === "unknown") return "danger"
  return "muted"
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2)
}

function defaultArguments(toolName: string): Record<string, unknown> {
  if (toolName === "validate_query") return { queryText: "SELECT 1" }
  if (toolName === "read_module_source") return { modulePath: "CommonModules/Module/Ext/Module.bsl" }
  if (toolName === "get_project_errors") return { projectName: "" }
  return {}
}

function parseApprovalConstraints(text: string): Record<string, unknown> {
  try {
    const parsed = text.trim() ? JSON.parse(text) : {}
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as Record<string, unknown> : {}
  } catch {
    return {}
  }
}
