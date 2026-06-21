import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  KeyRound,
  Loader2,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Table2,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  rightsRlsApi,
  type RightsRlsMatrixRow,
  type RightsRlsResponse,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/rights-rls")({
  component: RightsRlsPage,
})

const nf = new Intl.NumberFormat("ru-RU")

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

function RightsRlsPage() {
  const [configPath, setConfigPath] = useState("data/configs/unpacked")
  const [baselinePath, setBaselinePath] = useState("")
  const [roleLimit, setRoleLimit] = useState(120)
  const [objectLimit, setObjectLimit] = useState(400)
  const [params, setParams] = useState({
    configPath: "data/configs/unpacked",
    baselinePath: "",
    roleLimit: 120,
    objectLimit: 400,
  })
  const query = useQuery({
    queryKey: ["rights-rls", params],
    queryFn: () =>
      rightsRlsApi
        .analyze({
          config_path: params.configPath || undefined,
          baseline_path: params.baselinePath || undefined,
          role_limit: params.roleLimit,
          object_limit: params.objectLimit,
        })
        .then((r) => r.data),
  })
  const run = () => {
    const next = {
      configPath: configPath.trim(),
      baselinePath: baselinePath.trim(),
      roleLimit,
      objectLimit,
    }
    if (
      next.configPath === params.configPath &&
      next.baselinePath === params.baselinePath &&
      next.roleLimit === params.roleLimit &&
      next.objectLimit === params.objectLimit
    ) {
      void query.refetch()
      return
    }
    setParams(next)
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <ShieldCheck size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Rights & RLS
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Матрица роль → объект → действие, опасные права, RLS-сигналы и security gate для релиза.
          </p>
        </div>
        {query.data && <StatusBadge status={query.data.decision.status} score={query.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Источник</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <TextField label="EDT/XML путь" value={configPath} onChange={setConfigPath} mono />
            <TextField label="Baseline path" value={baselinePath} onChange={setBaselinePath} mono />
            <NumberField label="Role limit" value={roleLimit} min={1} max={1000} onChange={setRoleLimit} />
            <NumberField label="Matrix rows" value={objectLimit} min={1} max={5000} onChange={setObjectLimit} />
            <button
              onClick={run}
              disabled={query.isFetching}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {query.isFetching ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Проверить права
            </button>
            {query.data && (
              <button
                onClick={() => downloadMarkdown("rentgen-rights-rls.md", query.data.markdown)}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:bg-accent"
              >
                <Download size={16} />
                Скачать markdown
              </button>
            )}
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          {query.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Rights & RLS не загрузился. Проверьте backend и путь.</p>
            </div>
          )}

          {!query.data && !query.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <ShieldCheck size={42} className="opacity-30" />
              <p className="text-sm">Собираю матрицу прав.</p>
            </div>
          )}

          {query.data && <RightsReport report={query.data} />}
        </section>
      </div>
    </div>
  )
}

function RightsReport({ report }: { report: RightsRlsResponse }) {
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
          <p className="mt-2 break-all text-sm text-muted-foreground">{report.config_path}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-5">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Roles" value={report.summary.roles} icon={KeyRound} />
        <Metric label="Rights" value={report.summary.total_rights} icon={Table2} />
        <Metric label="Danger" value={report.summary.dangerous_rights} icon={ShieldAlert} />
        <Metric label="RLS" value={report.summary.rls_rules} icon={CheckCircle2} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Security gate" icon={ShieldAlert}>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={report.gate.block_release ? "danger" : report.gate.status === "warn" ? "warn" : "ok"}>
                {report.gate.status}
              </Badge>
              <span className="text-sm text-muted-foreground">
                {report.gate.block_release ? "block release" : "release allowed with caveats"}
              </span>
            </div>
            {report.gate.reasons.length > 0 && (
              <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                {report.gate.reasons.map((item) => (
                  <li key={item} className="break-words">{item}</li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Rights diff" icon={Table2}>
            <RightsDiffPanel report={report} />
          </Panel>

          <Panel title="Matrix" icon={Table2}>
            <MatrixTable rows={report.matrix} />
          </Panel>

          <Panel title="Findings" icon={AlertTriangle}>
            <div className="space-y-3">
              {report.findings.length ? report.findings.slice(0, 20).map((finding) => (
                <div key={`${finding.role}-${finding.code}-${finding.message}`} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={severityTone(finding.severity)}>{finding.severity}</Badge>
                    <span className="font-mono text-xs text-muted-foreground">{finding.code}</span>
                  </div>
                  <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{finding.role}</p>
                  <p className="mt-1 break-words text-sm text-muted-foreground">{finding.message}</p>
                </div>
              )) : <p className="text-sm text-muted-foreground">Findings не найдены.</p>}
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Roles" icon={KeyRound}>
            <div className="space-y-2">
              {report.roles.slice(0, 12).map((role) => (
                <div key={role.role} className="rounded-lg border border-border bg-background/60 p-3">
                  <p className="break-words text-sm font-semibold text-card-foreground">{role.role}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {nf.format(role.rights)} rights · {nf.format(role.dangerous_rights)} dangerous · {nf.format(role.rls_rules)} RLS
                  </p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Actions" icon={CheckCircle2}>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {report.recommended_actions.map((item) => (
                <li key={`${item.owner}-${item.title}`} className="break-words">
                  <span className="font-semibold text-card-foreground">{item.owner}:</span> {item.title}
                </li>
              ))}
            </ul>
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

function MatrixTable({ rows }: { rows: RightsRlsMatrixRow[] }) {
  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">Матрица пуста: Rights.xml не найден или не содержит object rights.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="border-b border-border text-xs uppercase text-muted-foreground">
          <tr>
            <th className="py-2 pr-3 font-semibold">Role</th>
            <th className="px-3 py-2 font-semibold">Object</th>
            <th className="px-3 py-2 font-semibold">Rights</th>
            <th className="px-3 py-2 font-semibold">Danger</th>
            <th className="py-2 pl-3 font-semibold">RLS</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.slice(0, 120).map((row, index) => (
            <tr key={`${row.role}-${row.object}-${index}`}>
              <td className="py-3 pr-3 font-mono text-xs text-card-foreground">{row.role}</td>
              <td className="px-3 py-3 font-mono text-xs text-muted-foreground">{row.object}</td>
              <td className="px-3 py-3">
                <span className="break-words text-xs text-muted-foreground">{row.rights.slice(0, 8).join(", ") || "none"}</span>
              </td>
              <td className="px-3 py-3">
                <Badge tone={row.dangerous.length ? "danger" : "ok"}>{row.dangerous.length}</Badge>
              </td>
              <td className="py-3 pl-3">
                <Badge tone={row.rls.length ? "ok" : "warn"}>{row.rls.length}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RightsDiffPanel({ report }: { report: RightsRlsResponse }) {
  const diff = report.diff
  if (!diff.enabled) {
    return (
      <div className="space-y-2 text-sm text-muted-foreground">
        <Badge tone="muted">{diff.status}</Badge>
        <p className="break-words">{diff.caveat ?? "Baseline snapshot was not provided."}</p>
      </div>
    )
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={diff.status === "risk" ? "danger" : diff.status === "watch" ? "warn" : "ok"}>
          {diff.status}
        </Badge>
        <span className="break-all text-xs text-muted-foreground">{diff.baseline_path}</span>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <MiniFact label="Added" value={diff.summary.added_rights} />
        <MiniFact label="Removed" value={diff.summary.removed_rights} />
        <MiniFact label="Danger" value={diff.summary.added_dangerous_rights} />
        <MiniFact label="Roles" value={diff.summary.changed_roles} />
      </div>
      {diff.caveat && <p className="break-words text-sm text-muted-foreground">{diff.caveat}</p>}
      <div className="space-y-2">
        {diff.changes.slice(0, 10).map((item, index) => (
          <div key={`${item.change}-${item.role}-${item.object}-${item.right}-${index}`} className="rounded-lg border border-border bg-background/60 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={item.change === "added" && item.dangerous ? "danger" : item.change === "added" ? "warn" : "muted"}>
                {item.change}
              </Badge>
              <span className="font-mono text-xs text-muted-foreground">{item.right}</span>
            </div>
            <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{item.role}</p>
            <p className="mt-1 break-all text-xs text-muted-foreground">{item.object}</p>
          </div>
        ))}
        {!diff.changes.length && <p className="text-sm text-muted-foreground">No rights changes detected.</p>}
      </div>
    </div>
  )
}

function MiniFact({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <p className="text-[11px] font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-bold text-card-foreground">{nf.format(value)}</p>
    </div>
  )
}

function TextField({ label, value, onChange, mono }: { label: string; value: string; onChange: (value: string) => void; mono?: boolean }) {
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

function NumberField({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(Math.max(min, Math.min(max, Number(event.target.value) || min)))}
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
      <div className="mt-1 break-words text-xl font-bold text-card-foreground">{typeof value === "number" ? nf.format(value) : value}</div>
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

function severityTone(severity: string): "ok" | "warn" | "danger" | "muted" {
  if (severity === "high") return "danger"
  if (severity === "medium") return "warn"
  if (severity === "low") return "muted"
  return "ok"
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
