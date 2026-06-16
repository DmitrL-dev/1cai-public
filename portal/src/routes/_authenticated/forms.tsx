import { useMemo, useState, type ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  FileCode2,
  LayoutTemplate,
  ListChecks,
  Loader2,
  RefreshCw,
  Sparkles,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { metadataApi, type MetadataFormBlueprint } from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/forms")({
  component: FormsPage,
})

const nf = new Intl.NumberFormat("ru-RU")
const formKinds = ["auto", "object", "list", "choice"] as const

function FormsPage() {
  const [identifier, setIdentifier] = useState("Catalog.Номенклатура")
  const [intent, setIntent] = useState("Primary enterprise managed form")
  const [formKind, setFormKind] = useState<(typeof formKinds)[number]>("auto")
  const [request, setRequest] = useState({ identifier, intent, formKind })

  const blueprintQ = useQuery({
    queryKey: ["metadata-form-blueprint", request],
    queryFn: () =>
      metadataApi
        .formBlueprint({
          identifier: request.identifier,
          intent: request.intent,
          form_kind: request.formKind,
          include_review: true,
        })
        .then((r) => r.data),
    enabled: Boolean(request.identifier.trim()),
  })

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <LayoutTemplate size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl">
              Forms Blueprint
            </h1>
          </div>
          <p className="mt-2 break-words text-sm text-muted-foreground sm:text-base">
            {blueprintQ.data?.object.ref ?? "1C managed form blueprint and draft assets"}
          </p>
        </div>

        <button
          onClick={() => blueprintQ.refetch()}
          disabled={blueprintQ.isFetching}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-semibold text-card-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw size={16} className={blueprintQ.isFetching ? "animate-spin" : undefined} />
          Refresh
        </button>
      </header>

      <section className="rounded-lg border border-border bg-card p-4">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_auto]">
          <label className="block min-w-0 space-y-1.5">
            <span className="text-xs font-medium uppercase text-muted-foreground">Metadata Identifier</span>
            <textarea
              value={identifier}
              onChange={(event) => setIdentifier(event.target.value)}
              rows={2}
              className="min-h-10 w-full resize-y rounded-lg border border-border bg-background px-3 py-2 font-mono text-xs outline-none focus:border-primary sm:text-sm"
            />
          </label>
          <label className="block min-w-0 space-y-1.5">
            <span className="text-xs font-medium uppercase text-muted-foreground">Intent</span>
            <textarea
              value={intent}
              onChange={(event) => setIntent(event.target.value)}
              rows={2}
              className="min-h-10 w-full resize-y rounded-lg border border-border bg-background px-3 py-2 text-xs outline-none focus:border-primary sm:text-sm"
            />
          </label>
          <button
            onClick={() => setRequest({ identifier: identifier.trim(), intent: intent.trim(), formKind })}
            disabled={!identifier.trim() || blueprintQ.isFetching}
            className="inline-flex h-10 self-end items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {blueprintQ.isFetching ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            Generate
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {formKinds.map((kind) => (
            <button
              key={kind}
              onClick={() => setFormKind(kind)}
              className={cn(
                "h-8 rounded-md border px-3 text-xs font-semibold capitalize",
                formKind === kind
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-background text-muted-foreground hover:bg-muted",
              )}
            >
              {kind}
            </button>
          ))}
        </div>
      </section>

      {blueprintQ.isLoading && (
        <div className="flex min-h-[420px] items-center justify-center rounded-lg border border-border bg-card">
          <Loader2 size={34} className="animate-spin text-primary" />
        </div>
      )}

      {blueprintQ.isError && (
        <div className="flex min-h-[360px] flex-col items-center justify-center gap-3 rounded-lg border border-border bg-card px-6 text-center text-destructive">
          <AlertTriangle size={38} />
          <p className="text-sm">Form blueprint request failed.</p>
        </div>
      )}

      {blueprintQ.data && <BlueprintReport report={blueprintQ.data} />}
    </div>
  )
}

function BlueprintReport({ report }: { report: MetadataFormBlueprint }) {
  const sections = useMemo(() => layoutSections(report.layout), [report.layout])
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <Metric label="Fields" value={report.summary.fields} icon={LayoutTemplate} />
        <Metric label="Tables" value={report.summary.tabular_sections} icon={ListChecks} />
        <Metric label="Commands" value={report.summary.commands} icon={Sparkles} />
        <Metric label="Forms" value={report.summary.existing_forms} icon={LayoutTemplate} />
        <Metric label="Findings" value={report.summary.review_findings} icon={AlertTriangle} />
        <Metric label="UX Rules" value={report.summary.ux_rules} icon={CheckCircle2} />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="min-w-0 space-y-6">
          <Panel title="Layout" icon={LayoutTemplate}>
            <div className="space-y-3">
              {sections.map((section) => (
                <div key={section.id} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge>{section.type}</Badge>
                    <p className="font-semibold text-card-foreground">{section.title}</p>
                  </div>
                  <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
                    {section.items.slice(0, 18).map((item) => (
                      <div key={`${section.id}-${item.name}`} className="rounded-md border border-border bg-card px-3 py-2">
                        <p className="break-words text-sm font-medium text-card-foreground">{item.caption || item.name}</p>
                        <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">{item.binding || item.name}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Panel title="Commands" icon={Sparkles}>
              <SimpleList
                items={report.commands.map((command) => `${command.name} - ${command.placement}`)}
                empty="No commands."
              />
            </Panel>
            <Panel title="UX Rules" icon={CheckCircle2}>
              <RuleList rules={report.ux_rules} />
            </Panel>
          </div>

          <Panel title="Acceptance" icon={ListChecks}>
            <SimpleList items={report.acceptance_checks} empty="No checks." />
          </Panel>
        </section>

        <aside className="min-w-0 space-y-6">
          <Panel title="Object" icon={LayoutTemplate}>
            <KeyValue
              values={{
                Type: report.object.type,
                Kind: report.form_kind,
                Ready: report.summary.readiness,
                Import: report.generated_assets.import_ready ? "yes" : "draft",
              }}
            />
          </Panel>

          <Panel title="Form XML" icon={FileCode2}>
            <CodeBlock text={report.generated_assets.form_xml} />
          </Panel>

          <Panel title="Form Module" icon={FileCode2}>
            <CodeBlock text={report.generated_assets.form_module_bsl} />
          </Panel>
        </aside>
      </div>
    </div>
  )
}

function layoutSections(layout: Record<string, unknown>) {
  const rawSections = Array.isArray(layout.sections) ? layout.sections : []
  return rawSections.map((raw, index) => {
    const section = raw as Record<string, unknown>
    const fields = Array.isArray(section.fields) ? section.fields : []
    const columns = Array.isArray(section.columns) ? section.columns : []
    const tables = Array.isArray(section.tables) ? section.tables : []
    const items = [...fields, ...columns, ...tables].map((item) => item as Record<string, string>)
    return {
      id: String(section.id ?? index),
      title: String(section.title ?? "Section"),
      type: String(section.type ?? "Group"),
      items,
    }
  })
}

function Metric({ label, value, icon: Icon }: { label: string; value: number; icon: LucideIcon }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <Icon size={17} className="text-primary" />
      </div>
      <p className="mt-3 break-words text-xl font-bold tabular-nums text-card-foreground">
        {nf.format(value)}
      </p>
    </div>
  )
}

function Panel({ title, icon: Icon, children }: { title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Icon size={16} className="text-primary" />
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h2>
      </div>
      <div className="p-4">{children}</div>
    </section>
  )
}

function RuleList({ rules }: { rules: MetadataFormBlueprint["ux_rules"] }) {
  if (rules.length === 0) return <Empty text="No UX rules." />
  return (
    <ul className="space-y-3">
      {rules.map((rule) => (
        <li key={rule.code} className="rounded-lg border border-border bg-background/60 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{rule.severity}</Badge>
            <span className="font-mono text-[11px] text-muted-foreground">{rule.code}</span>
          </div>
          <p className="mt-2 break-words text-sm text-card-foreground">{rule.message}</p>
        </li>
      ))}
    </ul>
  )
}

function SimpleList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <Empty text={empty} />
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item} className="rounded-md border border-border bg-background/60 px-3 py-2 text-sm text-card-foreground">
          <span className="break-words">{item}</span>
        </li>
      ))}
    </ul>
  )
}

function KeyValue({ values }: { values: Record<string, string> }) {
  return (
    <ul className="space-y-2">
      {Object.entries(values).map(([key, value]) => (
        <li key={key} className="flex items-start justify-between gap-3 text-sm">
          <span className="text-muted-foreground">{key}</span>
          <span className="min-w-0 break-words text-right font-semibold text-card-foreground">{value}</span>
        </li>
      ))}
    </ul>
  )
}

function CodeBlock({ text }: { text: string }) {
  return (
    <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
      {text}
    </pre>
  )
}

function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary ring-1 ring-inset ring-primary/20">
      {children}
    </span>
  )
}

function Empty({ text }: { text: string }) {
  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <CheckCircle2 size={15} />
      {text}
    </p>
  )
}
