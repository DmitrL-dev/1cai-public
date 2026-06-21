import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  FileCode,
  Loader2,
  RefreshCw,
  Save,
  ShieldAlert,
  Sparkles,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  qualityApi,
  type StandardsFinding,
  type StandardsReviewResponse,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/standards-review")({
  component: StandardsReviewPage,
})

const sampleCode = `Процедура Сформировать() Экспорт
    Запрос = Новый Запрос(
    "ВЫБРАТЬ
    |   Заказы.Ссылка,
    |   ЕстьNULL(Скидки.Процент, 0) КАК ПроцентСкидки,
    |   Скидки.Сумма КАК СуммаСкидки
    |ИЗ
    |   Документ.ЗаказПокупателя КАК Заказы
    |   ЛЕВОЕ СОЕДИНЕНИЕ РегистрСведений.Скидки КАК Скидки
    |   ПО Скидки.Номенклатура = Заказы.Номенклатура");
    Запрос.Выполнить();
КонецПроцедуры`

const nf = new Intl.NumberFormat("ru-RU")

function StandardsReviewPage() {
  const queryClient = useQueryClient()
  const [modulePath, setModulePath] = useState("CommonModules/Sales/Ext/Module.bsl")
  const [code, setCode] = useState(sampleCode)
  const [save, setSave] = useState(true)
  const [report, setReport] = useState<StandardsReviewResponse | null>(null)

  const stored = useQuery({
    queryKey: ["standards-findings"],
    queryFn: () => qualityApi.standardsFindings({ limit: 12 }).then((r) => r.data),
  })

  const mutation = useMutation({
    mutationFn: () =>
      qualityApi
        .standardsReview({
          code,
          module_path: modulePath.trim() || undefined,
          save,
        })
        .then((r) => r.data),
    onSuccess: (data) => {
      setReport(data)
      queryClient.invalidateQueries({ queryKey: ["standards-findings"] })
    },
  })

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <ShieldAlert size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl">
              Standards Review
            </h1>
          </div>
          <p className="mt-2 break-words text-sm text-muted-foreground sm:text-base">
            Catalog-aware BSL diagnostics with local auto-fix hints and stored findings.
          </p>
        </div>

        <button
          onClick={() => stored.refetch()}
          disabled={stored.isFetching}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-semibold text-card-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw size={16} className={stored.isFetching ? "animate-spin" : undefined} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="min-w-0 space-y-5">
          <Panel title="Code" icon={FileCode}>
            <div className="space-y-4">
              <label className="block space-y-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Module Path
                </span>
                <input
                  value={modulePath}
                  onChange={(event) => setModulePath(event.target.value)}
                  className="h-10 w-full rounded-lg border border-border bg-background px-3 font-mono text-xs text-foreground outline-none transition focus:border-primary"
                />
              </label>

              <textarea
                value={code}
                onChange={(event) => setCode(event.target.value)}
                spellCheck={false}
                className="min-h-[360px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              />

              <label className="flex h-10 items-center justify-between rounded-lg border border-border bg-background px-3 text-sm text-card-foreground">
                <span>Save findings</span>
                <input
                  type="checkbox"
                  checked={save}
                  onChange={(event) => setSave(event.target.checked)}
                  className="h-4 w-4 accent-primary"
                />
              </label>

              <button
                onClick={() => mutation.mutate()}
                disabled={mutation.isPending || !code.trim()}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : save ? <Save size={16} /> : <ShieldAlert size={16} />}
                Review Standards
              </button>
            </div>
          </Panel>

          <Panel title="Stored Findings" icon={Save}>
            {stored.data && stored.data.items.length === 0 && (
              <EmptyLine icon={CheckCircle2} text="No stored findings yet." />
            )}
            {stored.data && stored.data.items.length > 0 && (
              <ul className="space-y-2">
                {stored.data.items.map((item) => (
                  <li key={item.module_path} className="rounded-lg border border-border bg-background/50 p-3">
                    <p className="break-all font-mono text-xs font-semibold text-card-foreground">
                      {item.module_path}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge tone={item.summary.findings ? "warn" : "ok"}>
                        {item.summary.findings} findings
                      </Badge>
                      <Badge tone="muted">{item.summary.autofixable} autofix</Badge>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </section>

        <section className="min-w-0 min-h-[640px] rounded-xl border border-border bg-card">
          {mutation.isError && (
            <div className="flex min-h-[640px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Standards review failed. Check backend availability and code input.</p>
            </div>
          )}

          {!report && !mutation.isError && (
            <div className="flex min-h-[640px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <ShieldAlert size={42} className="opacity-30" />
              <p className="text-sm">Waiting for BSL standards review.</p>
            </div>
          )}

          {report && <StandardsReport report={report} />}
        </section>
      </div>
    </div>
  )
}

function StandardsReport({ report }: { report: StandardsReviewResponse }) {
  return (
    <div>
      <div className="flex flex-col gap-4 border-b border-border p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ShieldAlert size={24} className={report.summary.findings ? "text-amber-500" : "text-emerald-500"} />
            <h2 className="min-w-0 break-words text-lg font-bold text-card-foreground sm:text-xl">
              {report.module_path || "Pasted Code"}
            </h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {report.engine} - BSL LS {report.bsl_language_server.mode}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={report.summary.findings ? "warn" : "ok"}>{report.summary.findings} findings</Badge>
          <Badge tone="muted">{report.summary.autofixable} autofix</Badge>
          <Badge tone={report.bsl_language_server.available ? "ok" : "muted"}>
            {report.bsl_language_server.available ? "bsl-ls" : "fallback"}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 border-b border-border sm:grid-cols-2 md:grid-cols-4">
        <Metric label="LOC" value={report.summary.loc} icon={FileCode} />
        <Metric label="Findings" value={report.summary.findings} icon={AlertTriangle} />
        <Metric label="Autofix" value={report.summary.autofixable} icon={Sparkles} />
        <Metric label="Metadata" value={report.summary.metadata_refs} icon={ShieldAlert} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Findings" icon={AlertTriangle}>
            {report.findings.length === 0 ? (
              <EmptyLine icon={CheckCircle2} text="No standards findings." />
            ) : (
              <FindingList findings={report.findings} />
            )}
          </Panel>
        </div>

        <div className="min-w-0 space-y-5">
          <Panel title="Severity" icon={ShieldAlert}>
            <KeyValue values={report.summary.by_severity} />
          </Panel>

          <Panel title="Markdown" icon={FileCode}>
            <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {report.markdown}
            </pre>
          </Panel>
        </div>
      </div>
    </div>
  )
}

function FindingList({ findings }: { findings: StandardsFinding[] }) {
  return (
    <ul className="space-y-3">
      {findings.map((finding, index) => {
        const safeOptions = detailsList(finding.details, "safe_options")
        const testExpectations = detailsList(finding.details, "test_expectations")
        const fieldRef = detailsString(finding.details, "field_ref")
        const risk = detailsString(finding.details, "risk")
        return (
          <li key={`${finding.rule_id}-${finding.line}-${index}`} className="rounded-lg border border-border bg-background/50 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={finding.severity === "high" ? "danger" : finding.severity === "medium" ? "warn" : "muted"}>
                {finding.rule_id || finding.code}
              </Badge>
              <span className="text-sm font-semibold text-card-foreground">{finding.standard}</span>
              {finding.line && <span className="text-xs text-muted-foreground">line {finding.line}</span>}
            </div>
            <p className="mt-2 text-sm text-card-foreground">{finding.message}</p>
            {fieldRef && (
              <p className="mt-2 break-all font-mono text-xs text-primary">
                {fieldRef}
              </p>
            )}
            {risk && (
              <p className="mt-2 text-xs text-muted-foreground">{risk}</p>
            )}
            {finding.autofix && (
              <p className="mt-2 text-xs text-muted-foreground">
                {String(finding.autofix.description ?? "Review manually.")}
              </p>
            )}
            {safeOptions.length > 0 && <DetailList title="Safe options" values={safeOptions} />}
            {testExpectations.length > 0 && <DetailList title="Tests" values={testExpectations} />}
          </li>
        )
      })}
    </ul>
  )
}

function detailsList(details: Record<string, unknown> | undefined, key: string) {
  const value = details?.[key]
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : []
}

function detailsString(details: Record<string, unknown> | undefined, key: string) {
  const value = details?.[key]
  return value === undefined || value === null ? "" : String(value)
}

function DetailList({ title, values }: { title: string; values: string[] }) {
  return (
    <div className="mt-3 rounded-lg border border-border bg-card/70 p-3">
      <p className="text-xs font-semibold uppercase text-muted-foreground">{title}</p>
      <ul className="mt-2 space-y-1">
        {values.map((value) => (
          <li key={value} className="break-words text-xs text-card-foreground">
            {value}
          </li>
        ))}
      </ul>
    </div>
  )
}

function KeyValue({ values }: { values: Record<string, number> }) {
  const entries = Object.entries(values)
  if (entries.length === 0) return <EmptyLine icon={CheckCircle2} text="No items." />
  return (
    <ul className="space-y-2">
      {entries.map(([key, value]) => (
        <li key={key} className="flex items-center justify-between gap-3 text-sm">
          <span className="text-muted-foreground">{key}</span>
          <span className="font-semibold tabular-nums text-card-foreground">{nf.format(value)}</span>
        </li>
      ))}
    </ul>
  )
}

function Metric({ label, value, icon: Icon }: { label: string; value: number; icon: LucideIcon }) {
  return (
    <div className="border-b border-r border-border px-5 py-4 last:border-r-0 md:border-b-0">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <Icon size={16} className="text-primary" />
      </div>
      <p className="mt-2 break-words text-xl font-bold tabular-nums text-card-foreground sm:text-2xl">
        {nf.format(value)}
      </p>
    </div>
  )
}

function Panel({ title, icon: Icon, children }: { title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-background/50">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Icon size={15} className="text-primary" />
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {title}
        </h3>
      </div>
      <div className="p-3">{children}</div>
    </div>
  )
}

function Badge({
  tone,
  children,
}: {
  tone: "danger" | "warn" | "ok" | "muted"
  children: ReactNode
}) {
  const tones = {
    danger: "bg-red-500/10 text-red-600 dark:text-red-400 ring-red-500/25",
    warn: "bg-amber-500/10 text-amber-600 dark:text-amber-400 ring-amber-500/25",
    ok: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 ring-emerald-500/25",
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
