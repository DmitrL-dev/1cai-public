import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Download,
  FileText,
  GitCompare,
  Loader2,
  RefreshCw,
  Rocket,
  ServerCog,
  ShieldCheck,
  Wrench,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  updateWarRoomApi,
  type UpdateWarRoomCheck,
  type UpdateWarRoomResponse,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/update-war-room")({
  component: UpdateWarRoomPage,
})

const nf = new Intl.NumberFormat("ru-RU")
const sampleModule = "CommonModules/СводнаяТаблицаУХ/Ext/Module.bsl"

type AppRoute = "/update-war-room" | "/metadata" | "/platform-doctor" | "/extension-safety" | "/release-readiness" | "/team-governance"

const appRoutes = [
  "/update-war-room",
  "/metadata",
  "/platform-doctor",
  "/extension-safety",
  "/release-readiness",
  "/team-governance",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/update-war-room"
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

function UpdateWarRoomPage() {
  const [releaseName, setReleaseName] = useState("ERP/UH update window")
  const [configPath, setConfigPath] = useState("data/configs/unpacked")
  const [targetVersion, setTargetVersion] = useState("")
  const [modulesText, setModulesText] = useState(sampleModule)
  const [includeSecurity, setIncludeSecurity] = useState(false)

  const mutation = useMutation({
    mutationFn: () =>
      updateWarRoomApi
        .plan({
          release_name: releaseName.trim() || undefined,
          config_path: configPath.trim() || undefined,
          target_platform_version: targetVersion.trim() || undefined,
          changed_modules: modulesText
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter(Boolean),
          include_security: includeSecurity,
        })
        .then((r) => r.data),
  })

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <GitCompare size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Update War Room
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Окно обновления: платформа, расширения, impact, тесты, rollback и evidence в одном плане.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} score={mutation.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Update candidate</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <TextField label="Окно / релиз" value={releaseName} onChange={setReleaseName} />
            <TextField label="EDT/XML путь" value={configPath} onChange={setConfigPath} mono />
            <TextField
              label="Целевая платформа"
              value={targetVersion}
              onChange={setTargetVersion}
              placeholder="8.3.26.x"
            />
            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Changed modules</span>
              <textarea
                value={modulesText}
                onChange={(event) => setModulesText(event.target.value)}
                spellCheck={false}
                className="min-h-[180px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              />
            </label>
            <label className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/60 px-3 py-2">
              <span className="text-sm font-medium text-card-foreground">Security rights review</span>
              <input
                type="checkbox"
                checked={includeSecurity}
                onChange={(event) => setIncludeSecurity(event.target.checked)}
                className="h-4 w-4 accent-primary"
              />
            </label>
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Собрать update plan
            </button>
            {mutation.data && (
              <button
                onClick={() => downloadMarkdown("rentgen-update-war-room.md", mutation.data.markdown)}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:bg-accent"
              >
                <Download size={16} />
                Скачать markdown
              </button>
            )}
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          {!mutation.data && !mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <GitCompare size={42} className="opacity-30" />
              <p className="text-sm">Жду candidate, чтобы собрать update war room.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Update War Room не загрузился. Проверьте backend и параметры.</p>
            </div>
          )}

          {mutation.data && <WarRoomReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function WarRoomReport({ report }: { report: UpdateWarRoomResponse }) {
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
            {report.release_name}: {report.configuration.name}
            {report.configuration.version ? ` ${report.configuration.version}` : ""}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-5">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Checks" value={report.summary.checks} icon={ClipboardList} />
        <Metric label="Attention" value={report.summary.attention} icon={AlertTriangle} />
        <Metric label="Extensions" value={report.summary.extensions} icon={Wrench} />
        <Metric label="Modules" value={report.summary.changed_modules} icon={FileText} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Checks" icon={ShieldCheck}>
            <CheckTable checks={report.checks} />
          </Panel>

          <Panel title="Workstreams" icon={Rocket}>
            <div className="space-y-3">
              {report.workstreams.map((item) => (
                <Link
                  key={item.id}
                  to={toAppRoute(item.to)}
                  className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                      <p className="mt-0.5 text-xs font-medium uppercase text-muted-foreground">{item.owner}</p>
                    </div>
                    <Badge tone={toneForStatus(item.status)}>{item.status}</Badge>
                  </div>
                  <p className="mt-2 break-words text-sm text-muted-foreground">{item.action}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Release gate" icon={Rocket}>
            {report.release.included ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  {Object.entries(report.release.summary ?? {}).slice(0, 8).map(([key, value]) => (
                    <Fact key={key} label={key} value={String(value)} />
                  ))}
                </div>
                {(report.release.recommended_actions ?? []).slice(0, 6).map((action, index) => (
                  <div key={index} className="rounded-lg border border-border bg-background/60 p-3">
                    <p className="break-words text-sm font-semibold text-card-foreground">
                      {String(action.title ?? "Action")}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {String(action.owner ?? "owner")} · {String(action.severity ?? "severity")}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Release impact не измерен: {report.release.reason ?? "unknown"}. Это caveat, а не зелёный статус.
              </p>
            )}
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Extensions" icon={Wrench}>
            {report.extensions.items.length ? (
              <ul className="space-y-2">
                {report.extensions.items.map((item) => (
                  <li key={item.path} className="rounded-lg border border-border bg-background/60 p-3">
                    <p className="break-words text-sm font-semibold text-card-foreground">{item.name}</p>
                    <p className="mt-1 break-all text-xs text-muted-foreground">{item.kind} · {item.path}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Расширения не найдены в локальном источнике.</p>
            )}
          </Panel>

          <Panel title="Platform" icon={ServerCog}>
            <div className="space-y-2">
              <Fact label="status" value={String(report.platform.decision.status ?? "unknown")} />
              <Fact label="from" value={String(report.platform.upgrade.from ?? "unknown")} />
              <Fact label="to" value={String(report.platform.upgrade.to ?? report.summary.target_platform_version ?? "unknown")} />
              <Fact label="readiness" value={String(report.platform.upgrade.readiness ?? "unknown")} />
            </div>
          </Panel>

          <Panel title="Caveats" icon={AlertTriangle}>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {report.caveats.map((item) => (
                <li key={item} className="break-words">
                  {item}
                </li>
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

function CheckTable({ checks }: { checks: UpdateWarRoomCheck[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="border-b border-border text-xs uppercase text-muted-foreground">
          <tr>
            <th className="py-2 pr-3 font-semibold">Status</th>
            <th className="px-3 py-2 font-semibold">Check</th>
            <th className="px-3 py-2 font-semibold">Severity</th>
            <th className="py-2 pl-3 font-semibold">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {checks.map((check) => (
            <tr key={check.id}>
              <td className="py-3 pr-3">
                <Badge tone={toneForStatus(check.status)}>{check.status}</Badge>
              </td>
              <td className="px-3 py-3">
                <p className="font-semibold text-card-foreground">{check.title}</p>
                <p className="font-mono text-xs text-muted-foreground">{check.id}</p>
              </td>
              <td className="px-3 py-3 text-muted-foreground">{check.severity}</td>
              <td className="py-3 pl-3">
                <p className="max-w-[380px] break-words text-xs text-muted-foreground">{check.action}</p>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-card-foreground">{value}</p>
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
  if (status === "risk" || status === "fail") return <XCircle size={20} className="shrink-0 text-destructive" />
  return <AlertTriangle size={20} className="shrink-0 text-amber-600" />
}

function toneForStatus(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "pass" || status === "ready") return "ok"
  if (status === "fail" || status === "risk") return "danger"
  if (status === "warn" || status === "watch") return "warn"
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
