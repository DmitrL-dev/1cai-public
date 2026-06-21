import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation, useQuery } from "@tanstack/react-query"
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  ClipboardCheck,
  FileJson,
  Loader2,
  PackageCheck,
  RefreshCw,
  ShieldCheck,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  productizationApi,
  type OfflineBundleArchiveResponse,
  type OfflineDeliveryPassport,
  type OfflineBundleManifestResponse,
  type OfflineBundleVerifyResponse,
  type ProductizationReadinessResponse,
  type SbomResponse,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/productization")({
  component: ProductizationPage,
})

const nf = new Intl.NumberFormat("ru-RU")

function ProductizationPage() {
  const [profile, setProfile] = useState("pilot")
  const [includeDefaults, setIncludeDefaults] = useState(true)
  const [sign, setSign] = useState(false)
  const [pathsText, setPathsText] = useState("docs/productization/SUPPORT_MATRIX.md")
  const [archivePath, setArchivePath] = useState("")

  const readinessQuery = useQuery({
    queryKey: ["productization", "readiness"],
    queryFn: () => productizationApi.readiness().then((r) => r.data),
  })

  const bundleBody = () => ({
    profile,
    include_defaults: includeDefaults,
    include_paths: parsePaths(pathsText),
    sign,
  })

  const manifestMutation = useMutation({
    mutationFn: () => productizationApi.manifest({ ...bundleBody(), write: false }).then((r) => r.data),
  })
  const verifyManifestMutation = useMutation({
    mutationFn: () => productizationApi.verifyManifest().then((r) => r.data),
  })
  const archiveMutation = useMutation({
    mutationFn: () => productizationApi.archive(bundleBody()).then((r) => r.data),
    onSuccess: (result) => setArchivePath(result.archive_path),
  })
  const verifyArchiveMutation = useMutation({
    mutationFn: () => productizationApi.verifyArchive(archivePath.trim()).then((r) => r.data),
  })
  const sbomMutation = useMutation({
    mutationFn: () =>
      productizationApi
        .sbom({
          include_defaults: true,
          include_paths: parsePaths(pathsText),
          write: false,
        })
        .then((r) => r.data),
  })

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <Archive size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Productization
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Enterprise delivery console: readiness, SBOM, offline manifest, archive and verification for closed-contour installation.
          </p>
        </div>
        {readinessQuery.data && <StatusBadge status={readinessQuery.data.status} score={readinessQuery.data.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Bundle controls</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Profile</span>
              <select
                value={profile}
                onChange={(event) => setProfile(event.target.value)}
                className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary"
              >
                <option value="pilot">pilot</option>
                <option value="production">production</option>
                <option value="airgap">airgap</option>
              </select>
            </label>

            <div className="grid grid-cols-1 gap-2 rounded-lg border border-border bg-background/60 p-3">
              <Toggle checked={includeDefaults} label="Include product defaults" onChange={setIncludeDefaults} />
              <Toggle checked={sign} label="Request env-based signature" onChange={setSign} />
            </div>

            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Extra paths</span>
              <textarea
                value={pathsText}
                onChange={(event) => setPathsText(event.target.value)}
                spellCheck={false}
                className="min-h-[110px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              />
            </label>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <ActionButton
                icon={FileJson}
                label="Build manifest"
                loading={manifestMutation.isPending}
                onClick={() => manifestMutation.mutate()}
              />
              <ActionButton
                icon={Archive}
                label="Build archive"
                loading={archiveMutation.isPending}
                onClick={() => archiveMutation.mutate()}
              />
              <ActionButton
                icon={ShieldCheck}
                label="Verify manifest"
                loading={verifyManifestMutation.isPending}
                onClick={() => verifyManifestMutation.mutate()}
              />
              <ActionButton
                icon={ClipboardCheck}
                label="Generate SBOM"
                loading={sbomMutation.isPending}
                onClick={() => sbomMutation.mutate()}
              />
            </div>

            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Archive path</span>
              <input
                value={archivePath}
                onChange={(event) => setArchivePath(event.target.value)}
                className="h-10 w-full rounded-lg border border-border bg-background px-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              />
            </label>
            <ActionButton
              icon={ShieldCheck}
              label="Verify archive"
              loading={verifyArchiveMutation.isPending}
              disabled={!archivePath.trim()}
              onClick={() => verifyArchiveMutation.mutate()}
            />
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          {readinessQuery.isLoading && (
            <div className="flex min-h-[420px] items-center justify-center text-muted-foreground">
              <Loader2 size={22} className="mr-2 animate-spin" />
              Loading readiness
            </div>
          )}
          {readinessQuery.isError && (
            <div className="flex min-h-[420px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Productization readiness did not load.</p>
            </div>
          )}
          {readinessQuery.data && (
            <ProductizationReport
              readiness={readinessQuery.data}
              manifest={manifestMutation.data}
              archive={archiveMutation.data}
              manifestVerify={verifyManifestMutation.data}
              archiveVerify={verifyArchiveMutation.data}
              sbom={sbomMutation.data}
              refresh={() => readinessQuery.refetch()}
              refreshing={readinessQuery.isFetching}
            />
          )}
        </section>
      </div>
    </div>
  )
}

function ProductizationReport({
  readiness,
  manifest,
  archive,
  manifestVerify,
  archiveVerify,
  sbom,
  refresh,
  refreshing,
}: {
  readiness: ProductizationReadinessResponse
  manifest?: OfflineBundleManifestResponse
  archive?: OfflineBundleArchiveResponse
  manifestVerify?: OfflineBundleVerifyResponse
  archiveVerify?: OfflineBundleVerifyResponse
  sbom?: SbomResponse
  refresh: () => void
  refreshing: boolean
}) {
  const passport = archive?.delivery_passport ?? archiveVerify?.delivery_passport

  return (
    <div>
      <div className="flex flex-col gap-4 border-b border-border p-4 sm:p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <DecisionIcon status={readiness.status} />
            <h2 className="break-words text-lg font-bold text-card-foreground sm:text-xl">
              {readiness.product}
            </h2>
          </div>
          <p className="mt-2 break-words text-sm text-muted-foreground">
            Release decision: {readiness.release_decision}
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={refreshing}
          className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-semibold text-foreground transition hover:bg-accent disabled:opacity-60"
        >
          {refreshing ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-5">
        <Metric label="Score" value={readiness.score} icon={ShieldCheck} />
        <Metric label="Deliverables" value={readiness.summary.deliverables ?? 0} icon={PackageCheck} />
        <Metric label="Pass" value={readiness.summary.pass ?? 0} icon={CheckCircle2} />
        <Metric label="Findings" value={readiness.summary.findings ?? 0} icon={AlertTriangle} />
        <Metric label="Tests" value={readiness.summary.tests_total ?? 0} icon={ClipboardCheck} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Readiness findings" icon={AlertTriangle}>
            {readiness.findings.length ? (
              <div className="space-y-3">
                {readiness.findings.slice(0, 8).map((item, index) => (
                  <Finding key={`${String(item.code)}-${index}`} item={item} />
                ))}
              </div>
            ) : (
              <Empty text="No productization findings." />
            )}
          </Panel>

          {manifest && <ManifestPanel manifest={manifest} />}
          {archive && <ArchivePanel archive={archive} />}
          {passport && <DeliveryPassportPanel passport={passport} />}
          {manifestVerify && <VerifyPanel title="Manifest verify" result={manifestVerify} />}
          {archiveVerify && <VerifyPanel title="Archive verify" result={archiveVerify} />}
          {sbom && <SbomPanel sbom={sbom} />}
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Non-AI value" icon={ShieldCheck}>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {readiness.non_ai_value.map((item) => (
                <li key={item} className="break-words">{item}</li>
              ))}
            </ul>
          </Panel>

          <Panel title="Deliverables" icon={PackageCheck}>
            <div className="space-y-2">
              {readiness.deliverables.slice(0, 10).map((item, index) => (
                <div key={`${String(item.id)}-${index}`} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-background/60 p-2">
                  <div className="min-w-0">
                    <p className="break-words text-sm font-semibold text-card-foreground">{String(item.title ?? item.id ?? "deliverable")}</p>
                    <p className="break-all font-mono text-xs text-muted-foreground">{String(item.path ?? "")}</p>
                  </div>
                  <Badge tone={String(item.status) === "pass" ? "ok" : "warn"}>{String(item.status ?? "n/a")}</Badge>
                </div>
              ))}
            </div>
          </Panel>
        </aside>
      </div>
    </div>
  )
}

function ManifestPanel({ manifest }: { manifest: OfflineBundleManifestResponse }) {
  return (
    <Panel title="Offline manifest" icon={FileJson}>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Fact label="Profile" value={manifest.profile} />
        <Fact label="Files" value={nf.format(manifest.summary.files)} />
        <Fact label="Missing" value={nf.format(manifest.summary.missing)} />
        <Fact label="Signed" value={manifest.signature.signed ? "yes" : "no"} />
      </div>
      <p className="mt-3 break-all font-mono text-xs text-muted-foreground">{manifest.manifest_sha256}</p>
    </Panel>
  )
}

function ArchivePanel({ archive }: { archive: OfflineBundleArchiveResponse }) {
  return (
    <Panel title="Offline archive" icon={Archive}>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <Fact label="Status" value={archive.status} />
        <Fact label="Size" value={`${nf.format(archive.size_bytes)} bytes`} />
        <Fact label="Files" value={nf.format(archive.manifest.summary.files)} />
        <Fact label="Archive entries" value={nf.format(archive.archive_files.length)} />
      </div>
      <p className="mt-3 break-all font-mono text-xs text-card-foreground">{archive.archive_path}</p>
      <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{archive.archive_sha256}</p>
    </Panel>
  )
}

function DeliveryPassportPanel({ passport }: { passport: OfflineDeliveryPassport }) {
  const target = String(passport.install_profile.target ?? "closed contour")
  const services = Array.isArray(passport.install_profile.services) ? passport.install_profile.services : []

  return (
    <Panel title="Delivery passport" icon={PackageCheck}>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <Fact label="Decision" value={passport.decision.status} />
        <Fact label="Profile" value={passport.profile} />
        <Fact label="Signed" value={passport.package.signed ? "yes" : "no"} />
        <Fact label="Files" value={nf.format(passport.package.files)} />
      </div>
      <p className="mt-3 break-words text-sm font-medium text-card-foreground">{passport.decision.headline}</p>
      <p className="mt-2 break-words text-xs text-muted-foreground">{target}</p>
      {services.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {services.map((item) => (
            <Badge key={String(item)} tone="muted">{String(item)}</Badge>
          ))}
        </div>
      )}
      <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Acceptance gates</p>
          {passport.acceptance_gates.slice(0, 5).map((item, index) => (
            <div key={`${String(item.id)}-${index}`} className="rounded-lg border border-border bg-background/60 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={gateTone(String(item.status ?? "warn"))}>{String(item.status ?? "warn")}</Badge>
                <span className="break-all font-mono text-xs text-muted-foreground">{String(item.id ?? "gate")}</span>
              </div>
              <p className="mt-2 break-words text-xs text-card-foreground">{String(item.acceptance ?? "")}</p>
            </div>
          ))}
        </div>
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Role handoff</p>
          {passport.handoff_by_role.slice(0, 3).map((item, index) => (
            <div key={`${String(item.role)}-${index}`} className="rounded-lg border border-border bg-background/60 p-3">
              <p className="break-words text-sm font-semibold text-card-foreground">{String(item.role ?? "role")}</p>
              <p className="mt-1 break-words text-xs text-muted-foreground">{String(item.needs ?? "")}</p>
            </div>
          ))}
        </div>
      </div>
      <p className="mt-4 break-all font-mono text-xs text-muted-foreground">{passport.package.manifest_sha256}</p>
    </Panel>
  )
}

function VerifyPanel({ title, result }: { title: string; result: OfflineBundleVerifyResponse }) {
  return (
    <Panel title={title} icon={ShieldCheck}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={result.status === "pass" ? "ok" : result.status === "fail" ? "danger" : "warn"}>{result.status}</Badge>
        <Badge tone="muted">{nf.format(result.checked_files)} files</Badge>
      </div>
      {result.findings.length ? (
        <div className="mt-3 space-y-2">
          {result.findings.slice(0, 8).map((item, index) => (
            <Finding key={`${String(item.code)}-${index}`} item={item} />
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">Verification passed without findings.</p>
      )}
    </Panel>
  )
}

function SbomPanel({ sbom }: { sbom: SbomResponse }) {
  return (
    <Panel title="SBOM" icon={ClipboardCheck}>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Fact label="Components" value={nf.format(sbom.summary.components)} />
        <Fact label="Sources" value={nf.format(sbom.summary.sources)} />
        <Fact label="Missing" value={nf.format(sbom.summary.missing_sources)} />
        <Fact label="Format" value={sbom.bomFormat} />
      </div>
      {sbom.components.length ? (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="border-b border-border text-xs uppercase text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-semibold">Name</th>
                <th className="px-3 py-2 font-semibold">Version</th>
                <th className="py-2 pl-3 font-semibold">Type</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {sbom.components.slice(0, 10).map((component, index) => (
                <tr key={`${String(component.name)}-${index}`}>
                  <td className="py-3 pr-3 text-card-foreground">{String(component.name ?? "")}</td>
                  <td className="px-3 py-3 text-muted-foreground">{String(component.version ?? "")}</td>
                  <td className="py-3 pl-3 text-muted-foreground">{String(component.type ?? "")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">No components in the selected sources.</p>
      )}
    </Panel>
  )
}

function Finding({ item }: { item: Record<string, unknown> }) {
  const severity = String(item.severity ?? "medium")
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={severity === "high" ? "danger" : severity === "low" ? "muted" : "warn"}>{severity}</Badge>
        <span className="break-all font-mono text-xs text-muted-foreground">{String(item.code ?? "finding")}</span>
      </div>
      <p className="mt-2 break-words text-sm text-card-foreground">{String(item.message ?? item.path ?? "")}</p>
    </div>
  )
}

function Toggle({ checked, label, onChange }: { checked: boolean; label: string; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-3">
      <span className="text-sm font-medium text-card-foreground">{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 accent-primary"
      />
    </label>
  )
}

function ActionButton({
  icon: Icon,
  label,
  loading,
  disabled,
  onClick,
}: {
  icon: LucideIcon
  label: string
  loading?: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-semibold text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60"
    >
      {loading ? <Loader2 size={16} className="animate-spin" /> : <Icon size={16} />}
      {label}
    </button>
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

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-bold text-card-foreground">{value}</p>
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
  if (status === "pass" || status === "ready") return <CheckCircle2 size={20} className="shrink-0 text-emerald-600" />
  if (status === "fail" || status === "risk") return <XCircle size={20} className="shrink-0 text-destructive" />
  return <AlertTriangle size={20} className="shrink-0 text-amber-600" />
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

function Empty({ text }: { text: string }) {
  return <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">{text}</p>
}

function gateTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "pass" || status === "ready") return "ok"
  if (status === "fail" || status === "blocked" || status === "risk") return "danger"
  if (status === "warn") return "warn"
  return "muted"
}

function parsePaths(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
}
