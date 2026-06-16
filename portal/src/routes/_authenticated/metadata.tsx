import { useMemo, useState } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import {
  AlertTriangle,
  Boxes,
  Database,
  FileCode2,
  Gauge,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { metadataApi, rentgenApi, type MetadataObject, type MetadataPreview } from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/metadata")({
  component: MetadataPage,
})

const nf = new Intl.NumberFormat("ru-RU")
const typeFilters = ["all", "Document", "Catalog", "CommonModule", "Role", "Report"]

function MetadataPage() {
  const [query, setQuery] = useState("")
  const [type, setType] = useState("all")
  const [selected, setSelected] = useState<string | null>(null)
  const [securityEnabled, setSecurityEnabled] = useState(false)
  const [formReviewEnabled, setFormReviewEnabled] = useState(false)
  const [dataEnabled, setDataEnabled] = useState(false)

  const summaryQ = useQuery({
    queryKey: ["metadata-summary"],
    queryFn: () => metadataApi.summary().then((r) => r.data),
  })

  const inventoryQ = useQuery({
    queryKey: ["test-inventory"],
    queryFn: () => rentgenApi.testInventory().then((r) => r.data),
  })

  const searchQ = useQuery({
    queryKey: ["metadata-search", query, type],
    queryFn: () =>
      metadataApi
        .search({ q: query || undefined, type: type === "all" ? undefined : type, limit: 40 })
        .then((r) => r.data),
  })

  const items = searchQ.data?.items ?? []
  const selectedId = selected ?? items[0]?.ref ?? null

  const objectQ = useQuery({
    queryKey: ["metadata-object", selectedId],
    queryFn: () => metadataApi.object(selectedId as string).then((r) => r.data),
    enabled: Boolean(selectedId),
  })

  const impactQ = useQuery({
    queryKey: ["metadata-impact", selectedId],
    queryFn: () => metadataApi.objectImpact(selectedId as string).then((r) => r.data),
    enabled: Boolean(selectedId),
  })

  const securityQ = useQuery({
    queryKey: ["metadata-security-review"],
    queryFn: () => metadataApi.securityReview(200).then((r) => r.data),
    enabled: securityEnabled,
  })

  const dataQ = useQuery({
    queryKey: ["metadata-data-governance"],
    queryFn: () => metadataApi.dataGovernance(120).then((r) => r.data),
    enabled: dataEnabled,
  })

  const formReviewQ = useQuery({
    queryKey: ["metadata-form-review", selectedId],
    queryFn: () => metadataApi.formReview({ identifier: selectedId as string }).then((r) => r.data),
    enabled: Boolean(selectedId) && formReviewEnabled,
  })

  const topTypes = useMemo(() => {
    const byType = summaryQ.data?.summary.by_type ?? {}
    return Object.entries(byType)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
  }, [summaryQ.data])

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-2">
              <Database size={22} className="text-primary" />
            </div>
            <h1 className="text-2xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl">
              Metadata Explorer
            </h1>
          </div>
          <p className="mt-2 max-w-3xl text-muted-foreground">
            {summaryQ.data?.configuration.synonym ||
              summaryQ.data?.configuration.name ||
              "1C EDT metadata graph"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSecurityEnabled(true)}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-border bg-card px-3 text-sm font-medium text-card-foreground hover:bg-muted"
          >
            <ShieldCheck size={16} />
            Security
          </button>
          <button
            onClick={() => setDataEnabled(true)}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-border bg-card px-3 text-sm font-medium text-card-foreground hover:bg-muted"
          >
            <Database size={16} />
            Data
          </button>
          <button
            onClick={() => setFormReviewEnabled(true)}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-border bg-card px-3 text-sm font-medium text-card-foreground hover:bg-muted"
          >
            <Gauge size={16} />
            Forms
          </button>
          <button
            onClick={() => metadataApi.refresh().then(() => summaryQ.refetch())}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-border bg-card px-3 text-sm font-medium text-card-foreground hover:bg-muted"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </header>

      {summaryQ.isLoading && (
        <div className="flex min-h-[320px] items-center justify-center rounded-lg border border-border bg-card">
          <Loader2 size={34} className="animate-spin text-primary" />
        </div>
      )}

      {summaryQ.isError && (
        <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 rounded-lg border border-border bg-card text-destructive">
          <AlertTriangle size={34} />
          <p className="text-sm">Metadata graph is unavailable.</p>
        </div>
      )}

      {summaryQ.data && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-6">
            <Metric label="Objects" value={summaryQ.data.summary.total_objects} icon={Boxes} />
            <Metric label="Modules" value={summaryQ.data.summary.total_modules} icon={FileCode2} />
            <Metric label="Forms" value={summaryQ.data.summary.total_forms} icon={Database} />
            <Metric label="Rights" value={summaryQ.data.summary.total_rights} icon={ShieldCheck} />
            <Metric label="Roles" value={summaryQ.data.summary.total_roles} icon={ShieldCheck} />
            <Metric
              label="Tests"
              value={inventoryQ.data?.summary.test_cases ?? 0}
              icon={Gauge}
            />
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
            <section className="min-w-0 rounded-lg border border-border bg-card">
              <div className="border-b border-border p-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={17} />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search objects"
                    className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {typeFilters.map((item) => (
                    <button
                      key={item}
                      onClick={() => setType(item)}
                      className={cn(
                        "h-8 rounded-md border px-2.5 text-xs font-medium",
                        type === item
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-background text-muted-foreground hover:bg-muted",
                      )}
                    >
                      {item === "all" ? "All" : item}
                    </button>
                  ))}
                </div>
              </div>

              <div className="max-h-[680px] overflow-y-auto p-2">
                {searchQ.isLoading && (
                  <div className="flex h-40 items-center justify-center">
                    <Loader2 size={26} className="animate-spin text-primary" />
                  </div>
                )}
                {!searchQ.isLoading && items.length === 0 && (
                  <div className="p-6 text-center text-sm text-muted-foreground">No objects found.</div>
                )}
                {items.map((item) => (
                  <ObjectButton
                    key={item.ref}
                    item={item}
                    active={selectedId === item.ref}
                    onClick={() => setSelected(item.ref)}
                  />
                ))}
              </div>
            </section>

            <section className="min-w-0 space-y-4">
              <div className="rounded-lg border border-border bg-card p-4">
                <h2 className="text-base font-semibold text-card-foreground">Configuration Types</h2>
                <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                  {topTypes.map(([name, count]) => (
                    <div key={name} className="rounded-md border border-border bg-background p-3">
                      <p className="truncate text-xs text-muted-foreground">{name}</p>
                      <p className="mt-1 text-lg font-bold tabular-nums">{nf.format(count)}</p>
                    </div>
                  ))}
                </div>
              </div>

              <ObjectDetails
                isLoading={objectQ.isLoading || impactQ.isLoading}
                object={objectQ.data}
                impactEdges={impactQ.data?.total_impact_edges ?? 0}
                rentgenAvailable={impactQ.data?.rentgen_available ?? false}
              />
              <ReviewPanels
                securityEnabled={securityEnabled}
                securityLoading={securityQ.isLoading}
                security={securityQ.data}
                dataEnabled={dataEnabled}
                dataLoading={dataQ.isLoading}
                dataGovernance={dataQ.data}
                formEnabled={formReviewEnabled}
                formLoading={formReviewQ.isLoading}
                formReview={formReviewQ.data}
              />
            </section>
          </div>
        </>
      )}
    </div>
  )
}

function ReviewPanels({
  securityEnabled,
  securityLoading,
  security,
  dataEnabled,
  dataLoading,
  dataGovernance,
  formEnabled,
  formLoading,
  formReview,
}: {
  securityEnabled: boolean
  securityLoading: boolean
  security?: Awaited<ReturnType<typeof metadataApi.securityReview>>["data"]
  dataEnabled: boolean
  dataLoading: boolean
  dataGovernance?: Awaited<ReturnType<typeof metadataApi.dataGovernance>>["data"]
  formEnabled: boolean
  formLoading: boolean
  formReview?: Awaited<ReturnType<typeof metadataApi.formReview>>["data"]
}) {
  if (!securityEnabled && !dataEnabled && !formEnabled) return null

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {dataEnabled && (
        <section className="rounded-lg border border-border bg-card p-4 lg:col-span-2">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-card-foreground">Data Governance</h2>
            {dataLoading && <Loader2 size={18} className="animate-spin text-primary" />}
          </div>
          {dataGovernance && (
            <>
              <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
                <SmallStat label="Data" value={dataGovernance.summary.data_objects} />
                <SmallStat label="Registers" value={dataGovernance.summary.registers} />
                <SmallStat label="Exchanges" value={dataGovernance.summary.exchange_objects} />
                <SmallStat label="Danger" value={dataGovernance.summary.dangerous_rights} />
                <SmallStat label="Findings" value={dataGovernance.summary.migration_findings} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
                <FindingList
                  items={dataGovernance.migration_findings.map((item) => ({
                    code: item.code,
                    severity: item.severity,
                    message: `${item.ref}: ${item.message}`,
                  }))}
                />
                <FindingList
                  items={dataGovernance.rights.findings.map((item) => ({
                    code: String(item.right ?? "right"),
                    severity: String(item.severity ?? "medium"),
                    message: `${item.role ?? "role"}: ${item.object ?? "object"}`,
                  }))}
                />
              </div>
            </>
          )}
        </section>
      )}

      {securityEnabled && (
        <section className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-card-foreground">Security Review</h2>
            {securityLoading && <Loader2 size={18} className="animate-spin text-primary" />}
          </div>
          {security && (
            <>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <SmallStat label="Roles" value={security.summary.roles} />
                <SmallStat label="Danger" value={security.summary.dangerous_rights} />
              </div>
              <FindingList
                items={security.findings.map((item) => ({
                  code: item.code,
                  severity: item.severity,
                  message: `${item.role}: ${item.message}`,
                }))}
              />
            </>
          )}
        </section>
      )}

      {formEnabled && (
        <section className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-card-foreground">Form Review</h2>
            {formLoading && <Loader2 size={18} className="animate-spin text-primary" />}
          </div>
          {formReview && (
            <>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <SmallStat label="Forms" value={formReview.summary.forms_reviewed} />
                <SmallStat label="Findings" value={formReview.summary.findings} />
              </div>
              <FindingList
                items={formReview.forms.flatMap((form) =>
                  form.findings.map((finding) => ({
                    code: finding.code,
                    severity: finding.severity,
                    message: `${form.form.name}: ${finding.message}`,
                  })),
                )}
              />
            </>
          )}
        </section>
      )}
    </div>
  )
}

function FindingList({
  items,
}: {
  items: Array<{ code: string; severity: string; message: string }>
}) {
  return (
    <div className="mt-3 max-h-72 overflow-y-auto rounded-md border border-border bg-background">
      {items.length === 0 ? (
        <p className="p-3 text-sm text-muted-foreground">No findings.</p>
      ) : (
        items.slice(0, 40).map((item, index) => (
          <div key={`${index}-${item.code}-${item.message}`} className="border-b border-border p-3 last:border-0">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase",
                  item.severity === "high"
                    ? "bg-red-500/10 text-red-600"
                    : item.severity === "medium"
                      ? "bg-amber-500/10 text-amber-600"
                      : "bg-slate-500/10 text-slate-600",
                )}
              >
                {item.severity}
              </span>
              <span className="text-[11px] text-muted-foreground">{item.code}</span>
            </div>
            <p className="mt-2 break-words text-xs text-card-foreground">{item.message}</p>
          </div>
        ))
      )}
    </div>
  )
}

function Metric({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: number
  icon: LucideIcon
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <Icon size={17} className="text-primary" />
      </div>
      <p className="mt-3 text-xl font-bold tabular-nums text-card-foreground">
        {nf.format(value)}
      </p>
    </div>
  )
}

function ObjectButton({
  item,
  active,
  onClick,
}: {
  item: MetadataPreview
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "mb-2 w-full rounded-md border p-3 text-left transition",
        active ? "border-primary bg-primary/5" : "border-border bg-background hover:bg-muted/60",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="break-words text-sm font-semibold text-card-foreground">{item.name}</p>
          <p className="mt-1 break-words text-xs text-muted-foreground">
            {item.synonym || item.ref}
          </p>
        </div>
        <span className="shrink-0 rounded bg-muted px-2 py-1 text-[11px] font-medium text-muted-foreground">
          {item.type}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-[11px] text-muted-foreground">
        <span>{item.counts.modules} modules</span>
        <span>{item.counts.forms} forms</span>
        <span>{item.counts.rights} rights</span>
      </div>
    </button>
  )
}

function ObjectDetails({
  isLoading,
  object,
  impactEdges,
  rentgenAvailable,
}: {
  isLoading: boolean
  object?: MetadataObject
  impactEdges: number
  rentgenAvailable: boolean
}) {
  if (isLoading) {
    return (
      <div className="flex min-h-[360px] items-center justify-center rounded-lg border border-border bg-card">
        <Loader2 size={30} className="animate-spin text-primary" />
      </div>
    )
  }

  if (!object) {
    return (
      <div className="flex min-h-[360px] items-center justify-center rounded-lg border border-border bg-card text-sm text-muted-foreground">
        Select metadata object
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="border-b border-border p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {object.type}
            </p>
            <h2 className="mt-1 break-words text-xl font-bold text-card-foreground">
              {object.name}
            </h2>
            <p className="mt-1 break-words text-sm text-muted-foreground">
              {object.synonym || object.ref}
            </p>
          </div>
          <div className="rounded-md border border-border bg-background px-3 py-2">
            <p className="text-xs text-muted-foreground">Impact edges</p>
            <p className="mt-1 text-lg font-bold tabular-nums">
              {rentgenAvailable ? nf.format(impactEdges) : "offline"}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-px bg-border sm:grid-cols-4">
        <SmallStat label="Modules" value={object.counts.modules} />
        <SmallStat label="Forms" value={object.counts.forms} />
        <SmallStat label="Attrs" value={object.counts.attributes} />
        <SmallStat label="Rights" value={object.counts.rights} />
      </div>

      <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-2">
        <ListBlock title="Modules" items={object.modules.map((item) => item.path)} />
        <ListBlock title="Forms" items={object.forms.map((item) => item.name)} />
        <ListBlock title="Attributes" items={object.attributes.map((item) => item.name)} />
        <ListBlock
          title="Dangerous Rights"
          items={(object.rights?.dangerous ?? []).map((item) => `${item.right}: ${item.object}`)}
        />
      </div>
    </div>
  )
}

function SmallStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-card p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{nf.format(value)}</p>
    </div>
  )
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="min-w-0">
      <h3 className="text-sm font-semibold text-card-foreground">{title}</h3>
      <div className="mt-2 max-h-56 overflow-y-auto rounded-md border border-border bg-background">
        {items.length === 0 ? (
          <p className="p-3 text-sm text-muted-foreground">Empty</p>
        ) : (
          items.slice(0, 80).map((item) => (
            <p key={item} className="border-b border-border px-3 py-2 text-xs last:border-0">
              <span className="break-words">{item}</span>
            </p>
          ))
        )}
      </div>
    </div>
  )
}
