import { useMemo, useState, type ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  FileText,
  Loader2,
  RefreshCw,
  ShieldCheck,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { approvalsApi, type ApprovalRecord } from "@/lib/api-client"
import { useAuthStore } from "@/stores/auth-store"

export const Route = createFileRoute("/_authenticated/approvals")({
  component: ApprovalsPage,
})

const nf = new Intl.NumberFormat("ru-RU")
const statusOptions = ["", "requested", "approved", "rejected", "used", "expired"] as const

function ApprovalsPage() {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<(typeof statusOptions)[number]>("")
  const [toolName, setToolName] = useState("write_module_source")
  const [reason, setReason] = useState("Safe Autopilot reviewed scope, diff candidates, tests and rollback.")
  const [ticket, setTicket] = useState("CHG-")
  const [linkedType, setLinkedType] = useState("safe_autopilot_plan")
  const [linkedId, setLinkedId] = useState("")
  const [modulePath, setModulePath] = useState("CommonModules/Sales/Ext/Module.bsl")
  const [decisionReason, setDecisionReason] = useState("Reviewed scope, actor and evidence packet.")
  const currentUser = useAuthStore((state) => state.user)
  const currentActor = currentUser?.username || currentUser?.user_id || ""

  const approvalsQuery = useQuery({
    queryKey: ["approvals", status],
    queryFn: () =>
      approvalsApi
        .list({ status: status || undefined, kind: "edt_mcp_call", limit: 100 })
        .then((response) => response.data),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["approvals"] })
  const createMutation = useMutation({
    mutationFn: () =>
      approvalsApi.createEdtMcp({
        tool_name: toolName.trim() || "write_module_source",
        approval_reason: reason.trim(),
        approval_ticket: ticket.trim() || undefined,
        linked_record_type: linkedType.trim() || undefined,
        linked_record_id: linkedId.trim() || undefined,
        argument_constraints: {
          source: "approvals-page",
          ...(modulePath.trim() ? { modulePath: modulePath.trim() } : {}),
        },
        expires_in_hours: 24,
      }),
    onSuccess: invalidate,
  })
  const approveMutation = useMutation({
    mutationFn: (approvalId: string) =>
      approvalsApi.approve(approvalId, { decision_reason: decisionReason.trim() || undefined }),
    onSuccess: invalidate,
  })
  const rejectMutation = useMutation({
    mutationFn: (approvalId: string) =>
      approvalsApi.reject(approvalId, { decision_reason: decisionReason.trim() || undefined }),
    onSuccess: invalidate,
  })

  const items = approvalsQuery.data?.items ?? []
  const counts = useMemo(() => countStatuses(items), [items])

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <ClipboardCheck size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Approvals
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-all font-mono text-xs text-muted-foreground">
            {approvalsQuery.data?.path ?? "data/approval_records.json"}
          </p>
        </div>
        <button
          onClick={() => approvalsQuery.refetch()}
          disabled={approvalsQuery.isFetching}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-semibold text-card-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw size={16} className={approvalsQuery.isFetching ? "animate-spin" : undefined} />
          Refresh
        </button>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
        <Metric label="Total" value={approvalsQuery.data?.total ?? 0} icon={ClipboardCheck} />
        <Metric label="Requested" value={counts.requested} icon={Clock3} tone="warn" />
        <Metric label="Approved" value={counts.approved} icon={CheckCircle2} tone="ok" />
        <Metric label="Rejected" value={counts.rejected} icon={XCircle} tone="danger" />
        <Metric label="Used" value={counts.used} icon={ShieldCheck} />
        <Metric label="Expired" value={counts.expired} icon={AlertTriangle} tone="warn" />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <aside className="min-w-0 space-y-5">
          <Panel title="New EDT-MCP Approval" icon={ClipboardCheck}>
            <div className="space-y-3">
              <TextField label="Tool" value={toolName} onChange={setToolName} mono />
              <TextArea label="Reason" value={reason} onChange={setReason} />
              <TextField label="Ticket" value={ticket} onChange={setTicket} />
              <TextField label="Linked type" value={linkedType} onChange={setLinkedType} mono />
              <TextField label="Linked id" value={linkedId} onChange={setLinkedId} mono />
              <TextField label="Module constraint" value={modulePath} onChange={setModulePath} mono />
              <button
                onClick={() => createMutation.mutate()}
                disabled={createMutation.isPending || reason.trim().length < 12}
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {createMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <ClipboardCheck size={16} />}
                Create approval
              </button>
              {createMutation.isError && <ErrorBox text={mutationError(createMutation.error)} />}
            </div>
          </Panel>

          <Panel title="Decision" icon={ShieldCheck}>
            <TextArea label="Decision reason" value={decisionReason} onChange={setDecisionReason} />
            <p className="mt-3 text-xs text-muted-foreground">
              {approveMutation.isError || rejectMutation.isError
                ? mutationError(approveMutation.error ?? rejectMutation.error)
                : " "}
            </p>
          </Panel>

          <Panel title="Proof Routes" icon={FileText}>
            <div className="grid grid-cols-1 gap-2">
              <RouteLink to="/safe-autopilot" label="Safe Autopilot" />
              <RouteLink to="/audit" label="Audit Log" />
              <RouteLink to="/evidence-bundle" label="Evidence Bundle" />
            </div>
          </Panel>
        </aside>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-card-foreground">Records</h2>
              <p className="mt-1 text-xs text-muted-foreground">{nf.format(items.length)} shown</p>
            </div>
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value as (typeof statusOptions)[number])}
              className="h-9 rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary"
            >
              <option value="">all</option>
              {statusOptions.filter(Boolean).map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </div>

          {approvalsQuery.isLoading && <LoadingState />}
          {approvalsQuery.isError && <ErrorState text="Approval records did not load." />}
          {approvalsQuery.data && items.length === 0 && <EmptyState text="No approval records." />}
          {items.length > 0 && (
            <div className="divide-y divide-border">
              {items.map((item) => (
                <ApprovalCard
                  key={item.id}
                  record={item}
                  approvePending={approveMutation.isPending}
                  rejectPending={rejectMutation.isPending}
                  currentActor={currentActor}
                  onApprove={() => approveMutation.mutate(item.id)}
                  onReject={() => rejectMutation.mutate(item.id)}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function ApprovalCard({
  record,
  approvePending,
  rejectPending,
  currentActor,
  onApprove,
  onReject,
}: {
  record: ApprovalRecord
  approvePending: boolean
  rejectPending: boolean
  currentActor: string
  onApprove: () => void
  onReject: () => void
}) {
  const constraints = record.argument_constraints ?? {}
  const linked = record.linked_record ?? {}
  const isSelfApproval = Boolean(currentActor && (record.requested_by || record.actor) === currentActor)
  return (
    <article className="p-4 sm:p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={statusTone(record.status)}>{record.status}</Badge>
            <Badge tone={riskTone(record.risk)}>{record.risk}</Badge>
            <span className="break-all font-mono text-xs text-muted-foreground">{record.id}</span>
          </div>
          <h3 className="mt-2 break-words text-sm font-semibold text-card-foreground">{record.tool_name}</h3>
          <p className="mt-1 break-words text-sm text-muted-foreground">{record.approval_reason}</p>
        </div>
        {record.status === "requested" && (
          <div className="flex shrink-0 flex-wrap gap-2">
            <button
              onClick={onApprove}
              disabled={approvePending || isSelfApproval}
              title={isSelfApproval ? "Requester cannot approve their own request" : undefined}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {approvePending ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
              Approve
            </button>
            <button
              onClick={onReject}
              disabled={rejectPending}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-semibold text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60"
            >
              {rejectPending ? <Loader2 size={15} className="animate-spin" /> : <XCircle size={15} />}
              Reject
            </button>
          </div>
        )}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Small label="Actor" value={record.actor} />
        <Small label="Requested by" value={record.requested_by || "n/a"} />
        <Small label="Approved by" value={record.approved_by || "n/a"} />
        <Small label="Expires" value={formatDate(record.expires_at)} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
        <CodeBlock
          title="Linked"
          value={`${linked.type ?? "n/a"}:${linked.id ?? "n/a"}`}
        />
        <CodeBlock
          title="Constraints"
          value={JSON.stringify(constraints, null, 2)}
        />
      </div>
    </article>
  )
}

function countStatuses(items: ApprovalRecord[]) {
  return items.reduce(
    (acc, item) => {
      acc[item.status] = (acc[item.status] ?? 0) + 1
      return acc
    },
    { requested: 0, approved: 0, rejected: 0, used: 0, expired: 0 } as Record<string, number>,
  )
}

function Panel({ title, icon: Icon, children }: { title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Icon size={16} className="text-primary" />
        <h2 className="text-xs font-semibold uppercase text-muted-foreground">{title}</h2>
      </div>
      <div className="p-4">{children}</div>
    </section>
  )
}

function Metric({ label, value, icon: Icon, tone }: { label: string; value: number; icon: LucideIcon; tone?: "ok" | "warn" | "danger" }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium uppercase text-muted-foreground">{label}</p>
        <Icon
          size={17}
          className={cn(
            tone === "ok" && "text-emerald-600",
            tone === "warn" && "text-amber-600",
            tone === "danger" && "text-destructive",
            !tone && "text-primary",
          )}
        />
      </div>
      <p className="mt-3 break-words text-xl font-bold tabular-nums text-card-foreground">{nf.format(value)}</p>
    </div>
  )
}

function TextField({
  label,
  value,
  onChange,
  mono,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  mono?: boolean
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={cn(
          "h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary",
          mono && "font-mono",
        )}
      />
    </label>
  )
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-[90px] w-full resize-y rounded-lg border border-border bg-background p-3 text-sm text-foreground outline-none transition focus:border-primary"
      />
    </label>
  )
}

function RouteLink({ to, label }: { to: "/safe-autopilot" | "/audit" | "/evidence-bundle"; label: string }) {
  return (
    <Link
      to={to}
      className="inline-flex h-9 items-center justify-between rounded-lg border border-border bg-background px-3 text-sm font-semibold text-card-foreground transition hover:bg-accent"
    >
      <span>{label}</span>
      <FileText size={15} />
    </Link>
  )
}

function CodeBlock({ title, value }: { title: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
      <p className="text-xs font-semibold uppercase text-muted-foreground">{title}</p>
      <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-all font-mono text-xs text-card-foreground">
        {value}
      </pre>
    </div>
  )
}

function Small({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
      <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-all text-sm font-medium text-card-foreground">{value}</p>
    </div>
  )
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
  if (status === "approved" || status === "used") return "ok"
  if (status === "requested" || status === "expired") return "warn"
  if (status === "rejected") return "danger"
  return "muted"
}

function riskTone(risk: string): "ok" | "warn" | "danger" | "muted" {
  if (risk === "write" || risk === "execute" || risk === "mixed") return "danger"
  if (risk === "read" || risk === "read_only") return "ok"
  return "warn"
}

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("ru-RU")
}

function mutationError(error: unknown) {
  if (error instanceof Error) return error.message
  return "Request failed."
}

function ErrorBox({ text }: { text: string }) {
  return <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{text}</div>
}

function LoadingState() {
  return (
    <div className="flex min-h-[420px] items-center justify-center text-muted-foreground">
      <Loader2 size={24} className="mr-2 animate-spin" />
      Loading
    </div>
  )
}

function ErrorState({ text }: { text: string }) {
  return (
    <div className="flex min-h-[420px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
      <AlertTriangle size={38} />
      <p className="text-sm">{text}</p>
    </div>
  )
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
      <ClipboardCheck size={38} className="opacity-40" />
      <p className="text-sm">{text}</p>
    </div>
  )
}
