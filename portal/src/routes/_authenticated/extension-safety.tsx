import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  Network,
  RefreshCw,
  ShieldCheck,
  Wrench,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  extensionSafetyApi,
  type ExtensionSafetyExtension,
  type ExtensionSafetyResponse,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/extension-safety")({
  component: ExtensionSafetyPage,
})

const nf = new Intl.NumberFormat("ru-RU")
const sampleModule = "CommonModules/Sales/Ext/Module.bsl"

type AppRoute = "/extension-safety" | "/update-war-room" | "/platform-doctor" | "/evidence-bundle" | "/metadata"

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

function ExtensionSafetyPage() {
  const [configPath, setConfigPath] = useState("data/configs/unpacked")
  const [modulesText, setModulesText] = useState(sampleModule)
  const [extensionLimit, setExtensionLimit] = useState(40)
  const [maxFiles, setMaxFiles] = useState(1200)

  const mutation = useMutation({
    mutationFn: () =>
      extensionSafetyApi
        .analyze({
          config_path: configPath.trim() || undefined,
          changed_modules: modulesText
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter(Boolean),
          extension_limit: extensionLimit,
          max_files_per_extension: maxFiles,
        })
        .then((r) => r.data),
  })

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <Wrench size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Extension Safety
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Расширения, заимствованные объекты, права, привилегированный режим, write hooks, impact и тестовые gaps перед обновлением.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} risk={mutation.data.decision.risk_score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Configuration Source</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <TextField label="EDT/XML path" value={configPath} onChange={setConfigPath} mono />
            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Changed modules</span>
              <textarea
                value={modulesText}
                onChange={(event) => setModulesText(event.target.value)}
                spellCheck={false}
                className="min-h-[150px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <NumberField label="Extension limit" value={extensionLimit} min={1} max={200} onChange={setExtensionLimit} />
              <NumberField label="Files / ext" value={maxFiles} min={1} max={10000} onChange={setMaxFiles} />
            </div>
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Собрать Extension Safety
            </button>
            {mutation.data && (
              <button
                onClick={() => downloadMarkdown("rentgen-extension-safety.md", mutation.data.markdown)}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:bg-accent"
              >
                <Download size={16} />
                Markdown
              </button>
            )}
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          {!mutation.data && !mutation.isError && (
            <div className="flex min-h-[560px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <Wrench size={42} className="opacity-30" />
              <p className="text-sm">Жду EDT/XML источник для проверки расширений.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[560px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Extension Safety не загрузился. Проверьте backend и путь.</p>
            </div>
          )}

          {mutation.data && <ExtensionSafetyReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function ExtensionSafetyReport({ report }: { report: ExtensionSafetyResponse }) {
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
          <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{report.source.path}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <LinkButton to="/update-war-room" icon={Network}>Update</LinkButton>
          <LinkButton to="/platform-doctor" icon={ShieldCheck}>Platform</LinkButton>
          <LinkButton to="/evidence-bundle" icon={FileText}>Evidence</LinkButton>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-6">
        <Metric label="Risk" value={report.decision.risk_score} icon={AlertTriangle} />
        <Metric label="Extensions" value={report.summary.extensions} icon={Wrench} />
        <Metric label="Modules" value={report.summary.modules} icon={FileText} />
        <Metric label="Signals" value={report.summary.signals} icon={AlertTriangle} />
        <Metric label="Rights" value={report.summary.rights_files} icon={ShieldCheck} />
        <Metric label="Gaps" value={report.summary.test_gaps} icon={Network} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Extensions" icon={Wrench}>
            <ExtensionList items={report.extensions} />
          </Panel>

          <Panel title="Impact" icon={Network}>
            {report.impact.length ? (
              <div className="space-y-3">
                {report.impact.slice(0, 12).map((item) => (
                  <div key={String(item.module_ref)} className="rounded-lg border border-border bg-background/60 p-3">
                    <p className="break-words font-mono text-xs font-semibold text-card-foreground">{String(item.module_ref)}</p>
                    <div className="mt-2 grid grid-cols-3 gap-2">
                      <Fact label="Impact" value={String(item.impact_total ?? 0)} />
                      <Fact label="Risk" value={String((item.quality as Record<string, unknown> | undefined)?.risk ?? "n/a")} />
                      <Fact label="Graph" value={String((item.graph_modules as unknown[] | undefined)?.length ?? 0)} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Impact по расширениям не измерен.</p>
            )}
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Actions" icon={ShieldCheck}>
            <div className="space-y-3">
              {report.recommended_actions.map((action, index) => (
                <div key={`${action.kind}-${index}`} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={toneForSeverity(action.severity)}>{action.severity}</Badge>
                    <span className="text-xs font-medium uppercase text-muted-foreground">{action.owner}</span>
                  </div>
                  <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{action.title}</p>
                  {action.target && <p className="mt-1 break-words font-mono text-xs text-muted-foreground">{action.target}</p>}
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Checklist" icon={CheckCircle2}>
            <ul className="space-y-2">
              {report.checklist.map((item) => (
                <li key={item} className="flex gap-2 text-sm text-muted-foreground">
                  <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-primary" />
                  <span className="break-words">{item}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Caveats" icon={AlertTriangle}>
            {report.caveats.length ? (
              <ul className="space-y-2 text-sm text-muted-foreground">
                {report.caveats.map((item) => (
                  <li key={item} className="break-words">{item}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Caveats отсутствуют.</p>
            )}
          </Panel>
        </aside>
      </div>
    </div>
  )
}

function ExtensionList({ items }: { items: ExtensionSafetyExtension[] }) {
  if (!items.length) {
    return <p className="text-sm text-muted-foreground">Расширения не найдены.</p>
  }
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.path} className="rounded-lg border border-border bg-background/60 p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="break-words text-sm font-semibold text-card-foreground">{item.name}</p>
              <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{item.path}</p>
            </div>
            <Badge tone={item.severity_counts.high ? "danger" : item.signals.length ? "warn" : "muted"}>
              {item.signals.length} signals
            </Badge>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-5">
            <Fact label="Files" value={nf.format(item.files)} />
            <Fact label="BSL" value={nf.format(item.bsl_files)} />
            <Fact label="XML" value={nf.format(item.xml_files)} />
            <Fact label="Rights" value={nf.format(item.rights_files)} />
            <Fact label="Borrowed" value={nf.format(item.borrowed_objects)} />
          </div>
          {item.signals.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {item.signals.slice(0, 8).map((signal, index) => (
                <Badge key={`${signal.id}-${index}`} tone={toneForSeverity(signal.severity)}>
                  {signal.id}
                </Badge>
              ))}
            </div>
          )}
        </div>
      ))}
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
        onChange={(event) => onChange(Number(event.target.value))}
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

function Metric({ label, value, icon: Icon }: { label: string; value: string | number; icon: LucideIcon }) {
  return (
    <div className="min-w-0 border-b border-r border-border p-3 last:border-r-0 md:border-b-0 sm:p-4">
      <div className="flex items-center gap-2 text-xs font-medium uppercase text-muted-foreground">
        <Icon size={14} className="shrink-0" />
        <span className="truncate">{label}</span>
      </div>
      <p className="mt-2 break-words text-xl font-bold text-card-foreground">{value}</p>
    </div>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-card/70 p-2">
      <p className="text-[10px] font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-bold text-card-foreground">{value}</p>
    </div>
  )
}

function LinkButton({ to, icon: Icon, children }: { to: AppRoute; icon: LucideIcon; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-semibold text-card-foreground transition hover:bg-accent"
    >
      <Icon size={15} />
      {children}
    </Link>
  )
}

function StatusBadge({ status, risk }: { status: string; risk: number }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2">
      <DecisionIcon status={status} />
      <div>
        <p className="text-xs font-medium uppercase text-muted-foreground">{status}</p>
        <p className="text-sm font-bold text-card-foreground">Risk {risk}</p>
      </div>
    </div>
  )
}

function Badge({ tone, children }: { tone: "ok" | "warn" | "danger" | "muted"; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex min-h-6 max-w-full items-center rounded-md px-2 py-0.5 text-xs font-semibold uppercase",
        tone === "ok" && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
        tone === "warn" && "bg-amber-500/10 text-amber-700 dark:text-amber-300",
        tone === "danger" && "bg-red-500/10 text-red-700 dark:text-red-300",
        tone === "muted" && "bg-muted text-muted-foreground",
      )}
    >
      <span className="break-words">{children}</span>
    </span>
  )
}

function DecisionIcon({ status }: { status: string }) {
  if (status === "ready") {
    return <CheckCircle2 size={18} className="shrink-0 text-emerald-600" />
  }
  if (status === "risk" || status === "critical") {
    return <XCircle size={18} className="shrink-0 text-red-600" />
  }
  return <AlertTriangle size={18} className="shrink-0 text-amber-600" />
}

function toneForSeverity(severity: string): "ok" | "warn" | "danger" | "muted" {
  if (severity === "critical" || severity === "high") return "danger"
  if (severity === "medium") return "warn"
  if (severity === "low") return "muted"
  return "warn"
}
