import { useEffect, useRef, useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileCheck2,
  FileText,
  Flame,
  Gauge,
  Landmark,
  Loader2,
  MessageSquare,
  Mic2,
  PackageCheck,
  RefreshCw,
  Route as RouteIcon,
  ShieldCheck,
  Sparkles,
  Target,
  Timer,
  Users,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  killerDemoApi,
  type ArchiveVerifyResponse,
  type EvidenceBundleRequest,
  type KillerDemoResponse,
  type RoleForwardingPacket,
} from "@/lib/api-client"
import { BuyerRoomPacketControls } from "@/components/BuyerRoomPacketControls"
import { OpenFirstPathList } from "@/components/OpenFirstPathList"
import { VerificationPacketControls } from "@/components/VerificationPacketControls"

export const Route = createFileRoute("/_authenticated/killer-demo")({
  component: KillerDemoPage,
})

const nf = new Intl.NumberFormat("ru-RU")
const sampleModule = "CommonModules/DemoProof/Ext/Module.bsl"

type AppRoute =
  | "/"
  | "/killer-demo"
  | "/launch-room"
  | "/testing"
  | "/safe-autopilot"
  | "/board-pack"
  | "/outcome-ledger"
  | "/buyer-concierge"
  | "/commercial-offer-studio"
  | "/enterprise-trust-center"
  | "/demo-command-center"
  | "/pilot-launchpad"
  | "/scenario-hub"
  | "/guided-demo"
  | "/business-case"
  | "/productization"
  | "/quality"
  | "/change"
  | "/release-readiness"
  | "/architecture"
  | "/offline-readiness"
  | "/platform-doctor"
  | "/vendor-portfolio"
  | "/rights-rls"
  | "/value-packs"
  | "/configurations"
  | "/operations"
  | "/lock-radar"
  | "/extension-safety"
  | "/update-war-room"
  | "/approvals"
  | "/audit"
  | "/evidence-bundle"

const appRoutes = [
  "/",
  "/killer-demo",
  "/launch-room",
  "/testing",
  "/safe-autopilot",
  "/board-pack",
  "/outcome-ledger",
  "/buyer-concierge",
  "/commercial-offer-studio",
  "/enterprise-trust-center",
  "/demo-command-center",
  "/pilot-launchpad",
  "/scenario-hub",
  "/guided-demo",
  "/business-case",
  "/productization",
  "/quality",
  "/change",
  "/release-readiness",
  "/architecture",
  "/offline-readiness",
  "/platform-doctor",
  "/vendor-portfolio",
  "/rights-rls",
  "/value-packs",
  "/configurations",
  "/operations",
  "/lock-radar",
  "/extension-safety",
  "/update-war-room",
  "/approvals",
  "/audit",
  "/evidence-bundle",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/killer-demo"
}

function readinessTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "ready" || status === "accepted" || status === "ready_to_ask" || status === "pass") return "ok"
  if (status === "risk" || status === "critical" || status === "blocked" || status === "scope_first" || status === "missing" || status === "fail") return "danger"
  return "warn"
}

function downloadText(filename: string, content: string, type = "text/markdown;charset=utf-8") {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

async function sha256Blob(blob: Blob): Promise<string> {
  try {
    const digest = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer())
    return Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("")
  } catch {
    return ""
  }
}

function filenameFromDisposition(value: unknown, fallback: string) {
  const header = String(value ?? "")
  const match = /filename="?([^";]+)"?/i.exec(header)
  return match?.[1] || fallback
}

function KillerDemoPage() {
  const [clientName, setClientName] = useState("Demo client")
  const [configPath, setConfigPath] = useState("data/configs/unpacked")
  const [targetVersion, setTargetVersion] = useState("")
  const [releaseName, setReleaseName] = useState("Killer demo release")
  const [monthlyAiCost, setMonthlyAiCost] = useState("120000")
  const [modulesText, setModulesText] = useState(sampleModule)
  const [evidenceProfile, setEvidenceProfile] = useState<"buyer" | "enterprise">("buyer")
  const [includeUpdate, setIncludeUpdate] = useState(false)
  const [includeRights, setIncludeRights] = useState(false)
  const [includeLockRadar, setIncludeLockRadar] = useState(false)
  const [includeExtensionSafety, setIncludeExtensionSafety] = useState(false)
  const [lockRadarLogPath, setLockRadarLogPath] = useState("")
  const [archiveInfo, setArchiveInfo] = useState<{
    filename: string
    sha256: string
    downloadSha256: string
    downloadHashMatches: boolean | null
    files: string
    manifest: string
    manifestSha256: string
    manifestFiles: string
  } | null>(null)
  const [archiveVerify, setArchiveVerify] = useState<ArchiveVerifyResponse | null>(null)
  const autoBuildStarted = useRef(false)

  const buildRequest = () => ({
    client_name: clientName.trim() || "Demo client",
    config_path: configPath.trim() || undefined,
    target_platform_version: targetVersion.trim() || undefined,
    release_name: releaseName.trim() || undefined,
    evidence_profile: evidenceProfile,
    include_update: includeUpdate,
    include_rights: includeRights,
    include_lock_radar: includeLockRadar,
    include_extension_safety: includeExtensionSafety,
    lock_radar_log_path: lockRadarLogPath.trim() || undefined,
    assumptions: {
      monthly_ai_subscription_cost: toNumber(monthlyAiCost),
    },
    changed_modules: modulesText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean),
  })
  const buildVerificationPacketRequest = (): EvidenceBundleRequest => ({
    client_name: clientName.trim() || "Demo client",
    config_path: configPath.trim() || undefined,
    target_platform_version: targetVersion.trim() || undefined,
    release_name: releaseName.trim() || undefined,
    lock_radar_log_path: lockRadarLogPath.trim() || undefined,
    assumptions: {
      monthly_ai_subscription_cost: toNumber(monthlyAiCost),
    },
    changed_modules: modulesText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean),
    include_update: includeUpdate,
    include_rights: includeRights,
    include_lock_radar: includeLockRadar,
    include_extension_safety: includeExtensionSafety,
    include_killer_demo: true,
  })

  const mutation = useMutation({
    mutationFn: () =>
      killerDemoApi
        .build(buildRequest())
        .then((r) => r.data),
  })
  const archiveMutation = useMutation({
    mutationFn: () =>
      killerDemoApi.archive(buildRequest()).then(async (r) => {
        const fallback = `${mutation.data?.proof_packet.bundle_id || "rentgen"}-killer-demo-archive.zip`
        const filename = filenameFromDisposition(r.headers["content-disposition"], fallback)
        const headerSha256 = String(r.headers["x-archive-sha256"] ?? "")
        const downloadSha256 = await sha256Blob(r.data)
        downloadBlob(filename, r.data)
        return {
          filename,
          sha256: headerSha256,
          downloadSha256,
          downloadHashMatches: downloadSha256 && headerSha256 ? downloadSha256 === headerSha256 : null,
          files: String(r.headers["x-archive-files"] ?? ""),
          manifest: String(r.headers["x-killer-demo-manifest"] ?? ""),
          manifestSha256: String(r.headers["x-killer-demo-manifest-sha256"] ?? ""),
          manifestFiles: String(r.headers["x-killer-demo-manifest-files"] ?? ""),
        }
      }),
    onSuccess: setArchiveInfo,
  })
  const archiveVerifyMutation = useMutation({
    mutationFn: () =>
      killerDemoApi.verifyArchive(buildRequest()).then((r) => r.data),
    onSuccess: setArchiveVerify,
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
              <Flame size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Killer Demo Path
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            One buyer-ready presentation route across developer spark, trust, board approval, outcomes and evidence.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} score={mutation.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Demo inputs</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <TextField label="Client" value={clientName} onChange={setClientName} />
            <TextField label="EDT/XML path" value={configPath} onChange={setConfigPath} mono />
            <TextField label="Target platform" value={targetVersion} onChange={setTargetVersion} placeholder="8.3.26.x" />
            <TextField label="Release" value={releaseName} onChange={setReleaseName} />
            <NumberField label="AI / month" value={monthlyAiCost} onChange={setMonthlyAiCost} />
            <div className="space-y-3 rounded-lg border border-border bg-background/60 p-3">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Evidence profile</span>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setEvidenceProfile("buyer")}
                  className={cn(
                    "min-h-9 rounded-md border px-3 py-2 text-sm font-semibold transition",
                    evidenceProfile === "buyer"
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-background text-card-foreground hover:bg-accent",
                  )}
                >
                  Buyer
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setEvidenceProfile("enterprise")
                    setIncludeUpdate(true)
                    setIncludeRights(true)
                    setIncludeLockRadar(true)
                    setIncludeExtensionSafety(true)
                  }}
                  className={cn(
                    "min-h-9 rounded-md border px-3 py-2 text-sm font-semibold transition",
                    evidenceProfile === "enterprise"
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-background text-card-foreground hover:bg-accent",
                  )}
                >
                  Enterprise
                </button>
              </div>
              <div className="grid grid-cols-1 gap-2">
                <Toggle checked={includeUpdate} label="Update war room" onChange={setIncludeUpdate} />
                <Toggle checked={includeRights} label="Rights/RLS" onChange={setIncludeRights} />
                <Toggle checked={includeLockRadar} label="Lock Radar" onChange={setIncludeLockRadar} />
                <Toggle checked={includeExtensionSafety} label="Extension Safety" onChange={setIncludeExtensionSafety} />
              </div>
              <TextField label="Tech journal path" value={lockRadarLogPath} onChange={setLockRadarLogPath} mono />
            </div>
            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Changed modules</span>
              <textarea
                value={modulesText}
                onChange={(event) => setModulesText(event.target.value)}
                spellCheck={false}
                className="min-h-[140px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              />
            </label>
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Build killer demo
            </button>
            {mutation.data && (
              <button
                onClick={() => downloadText(mutation.data.download_name, mutation.data.markdown)}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:bg-accent"
              >
                <Download size={16} />
                Download markdown
              </button>
            )}
            <button
              onClick={() => archiveMutation.mutate()}
              disabled={archiveMutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60"
            >
              {archiveMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <PackageCheck size={16} />}
              Killer ZIP archive
            </button>
            <button
              onClick={() => archiveVerifyMutation.mutate()}
              disabled={archiveVerifyMutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-60 dark:text-emerald-300"
            >
              {archiveVerifyMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
              Verify Killer ZIP
            </button>
            <BuyerRoomPacketControls monthlyAiCost={monthlyAiCost} />
            <VerificationPacketControls
              buildRequest={buildVerificationPacketRequest}
              fallbackFilename={() => `${mutation.data?.proof_packet.bundle_id || "rentgen"}-verification-packet.zip`}
            />
            {archiveInfo && (
              <div className="rounded-lg border border-border bg-background/60 p-3">
                <p className="break-all font-mono text-xs text-card-foreground">{archiveInfo.filename}</p>
                <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{archiveInfo.sha256}</p>
                {archiveInfo.downloadSha256 && (
                  <p className="mt-1 break-all font-mono text-xs text-emerald-700 dark:text-emerald-300">
                    local: {archiveInfo.downloadSha256}
                  </p>
                )}
                {archiveInfo.downloadHashMatches !== null && (
                  <p className="mt-1 text-xs font-semibold text-muted-foreground">
                    Download hash: {archiveInfo.downloadHashMatches ? "match" : "mismatch"}
                  </p>
                )}
                {archiveInfo.manifest && (
                  <p className="mt-1 break-all font-mono text-xs text-primary">{archiveInfo.manifest}</p>
                )}
                {archiveInfo.manifestSha256 && (
                  <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{archiveInfo.manifestSha256}</p>
                )}
                <p className="mt-1 text-xs text-muted-foreground">{archiveInfo.files} files</p>
                {archiveInfo.manifestFiles && (
                  <p className="mt-1 text-xs text-muted-foreground">{archiveInfo.manifestFiles} manifest entries</p>
                )}
              </div>
            )}
            {archiveVerify && <ArchiveVerifyCard result={archiveVerify} />}
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          {mutation.isPending && (
            <div className="flex min-h-[560px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <Loader2 size={42} className="animate-spin opacity-60" />
              <p className="text-sm">Building the buyer-ready demo path.</p>
            </div>
          )}

          {!mutation.data && !mutation.isError && !mutation.isPending && (
            <div className="flex min-h-[560px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <Flame size={42} className="opacity-30" />
              <p className="text-sm">Ready to build the demo path.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[560px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Killer Demo Path did not build. Check backend and inputs.</p>
            </div>
          )}

          {mutation.data && <KillerDemoReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function KillerDemoReport({ report }: { report: KillerDemoResponse }) {
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
          <p className="mt-2 break-words text-sm text-muted-foreground">{report.primary_route.reason}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to={toAppRoute(report.primary_route.route)}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
          >
            <Sparkles size={16} />
            {report.primary_route.label}
          </Link>
          <button
            onClick={() => downloadText("rentgen-proof-packet.json", JSON.stringify(report.proof_packet, null, 2), "application/json;charset=utf-8")}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-semibold text-foreground transition hover:bg-accent"
          >
            <Download size={16} />
            Proof packet
          </button>
          <button
            onClick={() =>
              downloadText(
                report.meeting_close_receipt.json_filename || "meeting-close-receipt.json",
                JSON.stringify(report.meeting_close_receipt, null, 2),
                "application/json;charset=utf-8",
              )
            }
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-semibold text-foreground transition hover:bg-accent"
          >
            <FileCheck2 size={16} />
            Close receipt
          </button>
          <button
            onClick={() =>
              downloadText(
                report.post_demo_activation_handoff.json_filename || "post-demo-activation-handoff.json",
                JSON.stringify(report.post_demo_activation_handoff, null, 2),
                "application/json;charset=utf-8",
              )
            }
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-semibold text-foreground transition hover:bg-accent"
          >
            <PackageCheck size={16} />
            Activation
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-4 xl:grid-cols-10">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Minutes" value={report.summary.total_minutes} icon={Timer} />
        <Metric label="Stages" value={report.summary.stages} icon={RouteIcon} />
        <Metric label="Roles" value={report.summary.role_sparks} icon={Users} />
        <Metric label="Role pkts" value={`${report.summary.role_packets_ready}/${report.proof_packet.role_packet_rollup.total}`} icon={Users} />
        <Metric label="Proof" value={report.summary.proof_moments} icon={FileCheck2} />
        <Metric label="Close" value={report.summary.close_ready ? "ready" : "hold"} icon={Target} />
        <Metric label="Checkout" value={report.summary.checkout_gates} icon={PackageCheck} />
        <Metric label="Test gaps" value={report.summary.test_gaps} icon={Gauge} />
        <Metric label="Objections" value={report.summary.objection_items} icon={MessageSquare} />
      </div>

      <div className="border-b border-border p-4 sm:p-5">
        <Panel title="Opening brief" icon={Sparkles}>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
              <Badge tone="ok">First click</Badge>
              <p className="mt-3 break-words text-base font-bold text-card-foreground">
                {report.opening_brief.headline}
              </p>
              <p className="mt-2 break-words text-sm text-muted-foreground">
                {report.opening_brief.one_sentence}
              </p>
              <Link
                to={toAppRoute(report.opening_brief.first_click.route)}
                className="mt-3 inline-flex max-w-full items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
              >
                <RouteIcon size={15} />
                <span className="break-words">{report.opening_brief.first_click.label}</span>
              </Link>
              <p className="mt-3 break-words text-xs text-muted-foreground">
                {report.opening_brief.first_click.reason}
              </p>
            </div>
            <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
              <p className="text-xs font-semibold uppercase text-muted-foreground">First 30 seconds</p>
              <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
                {report.opening_brief.first_30_seconds.map((item, index) => (
                  <div key={item} className="rounded-md bg-muted p-2">
                    <p className="text-xs font-semibold text-primary">{index + 1}</p>
                    <p className="mt-1 break-words text-xs text-muted-foreground">{item}</p>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex gap-2 rounded-md bg-muted p-2 text-sm text-muted-foreground">
                <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-600" />
                <span className="break-words">{report.opening_brief.success_signal}</span>
              </div>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
            <div className="rounded-lg border border-border bg-background/60 p-3">
              <p className="text-xs font-semibold uppercase text-muted-foreground">Role entry</p>
              <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
                {report.opening_brief.role_entries.slice(0, 6).map((item) => (
                  <Link
                    key={`${item.role}-${item.route}`}
                    to={toAppRoute(item.route)}
                    className="rounded-md bg-muted p-2 transition hover:bg-accent"
                  >
                    <Badge tone="muted">{item.role}</Badge>
                    <p className="mt-2 break-words text-xs font-semibold text-card-foreground">{item.question}</p>
                    <p className="mt-2 break-words text-xs text-muted-foreground">{item.proof}</p>
                  </Link>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-border bg-background/60 p-3">
              <p className="text-xs font-semibold uppercase text-muted-foreground">Anti-confusion</p>
              <div className="mt-3 space-y-2">
                {report.opening_brief.anti_confusion.map((item) => (
                  <Link
                    key={`${item.signal}-${item.route}`}
                    to={toAppRoute(item.route)}
                    className="block rounded-md bg-muted p-2 transition hover:bg-accent"
                  >
                    <p className="break-words text-xs font-semibold text-card-foreground">{item.signal}</p>
                    <p className="mt-1 break-words text-xs text-muted-foreground">{item.response}</p>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </Panel>
      </div>

      <div className="border-b border-border p-4 sm:p-5">
        <Panel title="Deal readiness" icon={Sparkles}>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
            <div className="rounded-lg border border-border bg-background/60 p-3">
              <Badge tone={readinessTone(report.deal_readiness.status)}>
                {report.deal_readiness.status}
              </Badge>
              <p className="mt-3 text-2xl font-bold text-card-foreground">{nf.format(report.deal_readiness.score)}</p>
              <p className="mt-2 break-words text-sm text-muted-foreground">{report.deal_readiness.decision_line}</p>
            </div>
            <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
              <p className="text-xs font-semibold uppercase text-muted-foreground">Next paid step</p>
              <Link
                to={toAppRoute(report.deal_readiness.next_paid_step.route)}
                className="mt-2 inline-flex max-w-full items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
              >
                <Sparkles size={15} />
                <span className="break-words">{report.deal_readiness.next_paid_step.label}</span>
              </Link>
              <p className="mt-3 break-words text-sm text-card-foreground">{report.deal_readiness.next_paid_step.acceptance}</p>
              <p className="mt-2 break-words text-xs text-muted-foreground">{report.deal_readiness.next_paid_step.owner}</p>
            </div>
          </div>
          {report.deal_readiness.blockers.length > 0 && (
            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.deal_readiness.blockers.map((item) => (
                <Link
                  key={item.id}
                  to={toAppRoute(item.route)}
                  className="rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
                >
                  <Badge tone={item.severity === "high" ? "danger" : "warn"}>{item.severity}</Badge>
                  <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.action}</p>
                </Link>
              ))}
            </div>
          )}
          <div className="mt-4 rounded-lg border border-border bg-background/60 p-3">
            <p className="break-words text-sm font-semibold text-card-foreground">
              {report.deal_readiness.local_asset_case.headline}
            </p>
            <p className="mt-2 break-words text-xs font-semibold text-muted-foreground">
              {report.deal_readiness.local_asset_case.value_anchor}
            </p>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
              <SmallValue label="AI rent" value={report.deal_readiness.local_asset_case.ai_rent_baseline || "optional"} />
              <SmallValue label="3-year rent" value={report.deal_readiness.local_asset_case.three_year_ai_rent || "n/a"} />
              <SmallValue label="Local license" value={report.deal_readiness.local_asset_case.local_license_anchor || "n/a"} />
              <SmallValue label="Break-even" value={report.deal_readiness.local_asset_case.break_even || "n/a"} />
            </div>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
              {report.deal_readiness.local_asset_case.why_it_is_asset.map((item) => (
                <div key={item} className="rounded-md bg-muted p-2 text-xs text-muted-foreground">
                  {item}
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {report.deal_readiness.local_asset_case.proof_routes.map((route) => (
                <LinkButton key={route} to={toAppRoute(route)}>
                  {route.replace("/", "")}
                </LinkButton>
              ))}
            </div>
            <p className="mt-3 break-words text-xs text-muted-foreground">{report.deal_readiness.local_asset_case.finance_line}</p>
            <p className="mt-2 break-words text-xs text-muted-foreground">{report.deal_readiness.local_asset_case.security_line}</p>
          </div>

          <div className="mt-4 rounded-lg border border-border bg-background/60 p-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase text-muted-foreground">Committee close board</p>
                <p className="mt-2 break-words text-sm font-semibold text-card-foreground">
                  {report.deal_readiness.committee_close_board.headline}
                </p>
                <p className="mt-2 break-words text-sm text-muted-foreground">
                  {report.deal_readiness.committee_close_board.final_question}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge tone={readinessTone(report.deal_readiness.committee_close_board.status)}>
                  {report.deal_readiness.committee_close_board.status}
                </Badge>
                <Badge tone="muted">
                  {report.deal_readiness.committee_close_board.accepted_roles}/{report.deal_readiness.committee_close_board.total_roles} accepted
                </Badge>
                <Badge tone={report.deal_readiness.committee_close_board.blocked_roles ? "danger" : "ok"}>
                  {report.deal_readiness.committee_close_board.blocked_roles} blocked
                </Badge>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-2">
              {report.deal_readiness.committee_close_board.roles.map((item) => (
                <Link
                  key={`${item.role}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="rounded-md bg-muted p-2 transition hover:bg-accent"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={readinessTone(item.status)}>{item.status}</Badge>
                    <p className="break-words text-xs font-semibold text-card-foreground">{item.role}</p>
                    {item.blocker && <Badge tone="warn">{item.blocker}</Badge>}
                  </div>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.accepted_proof}</p>
                  <p className="mt-2 break-words text-xs font-semibold text-card-foreground">{item.remaining_question}</p>
                  <p className="mt-2 break-words font-mono text-[11px] text-muted-foreground">{item.send.join(", ")}</p>
                </Link>
              ))}
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <div className="rounded-lg border border-border bg-background/60 p-3">
              <p className="text-xs font-semibold uppercase text-muted-foreground">Customer can repeat</p>
              <div className="mt-3 space-y-2">
                {report.deal_readiness.customer_can_repeat.map((item) => (
                  <div key={item} className="flex gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-600" />
                    <span className="break-words">{item}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-border bg-background/60 p-3">
              <p className="text-xs font-semibold uppercase text-muted-foreground">Role acceptance</p>
              <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
                {report.deal_readiness.role_acceptance.slice(0, 6).map((item) => (
                  <Link
                    key={`${item.role}-${item.route}`}
                    to={toAppRoute(item.route)}
                    className="rounded-md bg-muted p-2 transition hover:bg-accent"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={readinessTone(item.status)}>{item.status}</Badge>
                      <p className="break-words text-xs font-semibold text-card-foreground">{item.role}</p>
                    </div>
                    <p className="mt-2 break-words text-xs text-muted-foreground">{item.must_hear}</p>
                  </Link>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            {report.deal_readiness.close_checklist.map((item) => (
              <div key={item} className="flex gap-2 rounded-lg bg-muted p-3 text-sm text-muted-foreground">
                <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-600" />
                <span className="break-words">{item}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <ObjectionRouter report={report} />
      <CommercialClosePacket report={report} />

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Killer stages" icon={Flame}>
            <div className="space-y-3">
              {report.killer_stages.map((stage, index) => (
                <Link
                  key={stage.id}
                  to={toAppRoute(stage.route)}
                  className="grid min-w-0 grid-cols-[38px_minmax(0,1fr)] gap-3 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-sm font-bold text-primary">
                    {index + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap gap-2">
                      <p className="break-words text-sm font-semibold text-card-foreground">{stage.title}</p>
                      <Badge tone="muted">{stage.audience}</Badge>
                      <Badge tone="muted">{stage.minutes} min</Badge>
                    </div>
                    <p className="mt-2 break-words text-sm text-card-foreground">{stage.spark}</p>
                    <p className="mt-2 break-words text-xs text-muted-foreground">{stage.proof}</p>
                    <p className="mt-2 break-words text-xs font-semibold text-muted-foreground">{stage.close_question}</p>
                  </div>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Demo modes" icon={Mic2}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.demo_modes.map((mode) => (
                <div key={mode.id} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap gap-2">
                    <Badge tone="muted">{mode.minutes} min</Badge>
                    <Badge tone="ok">{mode.title}</Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {mode.steps.map((step) => (
                      <LinkButton key={`${mode.id}-${step.route}-${step.label}`} to={toAppRoute(step.route)}>
                        {step.label}
                      </LinkButton>
                    ))}
                  </div>
                  <p className="mt-3 break-words text-xs text-muted-foreground">{mode.close}</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Role sparks" icon={Users}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.role_sparks.map((item) => (
                <Link
                  key={`${item.role}-${item.first_route}`}
                  to={toAppRoute(item.first_route)}
                  className="rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <Badge tone="muted">{item.role}</Badge>
                  <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{item.spark}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.proof}</p>
                  <p className="mt-2 break-words text-xs font-semibold text-muted-foreground">{item.close}</p>
                </Link>
              ))}
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Proof moments" icon={Landmark}>
            <div className="space-y-2">
              {report.proof_moments.map((item) => (
                <Link
                  key={item.title}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
                >
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.signal}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Close scripts" icon={FileCheck2}>
            <div className="space-y-2">
              {report.close_scripts.map((item) => (
                <Link
                  key={`${item.audience}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
                >
                  <Badge tone="muted">{item.audience}</Badge>
                  <p className="mt-2 break-words text-sm text-card-foreground">{item.line}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Proof packet" icon={FileCheck2}>
            <div className="space-y-3">
              <KeyValue
                values={{
                  Bundle: report.proof_packet.bundle_id || "demo-checklist",
                  Files: String(report.proof_packet.file_count),
                  Forwardable: report.proof_packet.ready_to_forward ? "yes" : "needs bundle hash",
                }}
              />
              <OpenFirstPathList
                path={report.proof_packet.open_first_path}
                toAppRoute={toAppRoute}
                title="Open-first close path"
                itemClassName="bg-muted"
              />
              <div className="rounded-lg border border-border bg-background/60 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={readinessTone(report.proof_packet.role_packet_rollup.status)}>
                    {report.proof_packet.role_packet_rollup.status}
                  </Badge>
                  <p className="break-words text-sm font-semibold text-card-foreground">Role packet coverage</p>
                </div>
                <p className="mt-2 break-words text-xs text-muted-foreground">{report.proof_packet.role_packet_rollup.line}</p>
                {report.proof_packet.role_packet_rollup.missing_file_names.length > 0 && (
                  <p className="mt-3 break-words font-mono text-[11px] text-amber-700">
                    Missing: {report.proof_packet.role_packet_rollup.missing_file_names.join(", ")}
                  </p>
                )}
              </div>
              <ForwardingKitMini kit={report.proof_packet.forwarding_kit} />
              <Link
                to={toAppRoute(report.proof_packet.close_receipt.route)}
                className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={report.proof_packet.close_receipt.ready ? "ok" : readinessTone(report.proof_packet.close_receipt.status)}>
                    {report.proof_packet.close_receipt.status}
                  </Badge>
                  <p className="break-words text-sm font-semibold text-card-foreground">Meeting Close Receipt</p>
                </div>
                <p className="mt-2 break-words text-xs text-muted-foreground">{report.proof_packet.close_receipt.why}</p>
                <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <SmallValue label="Markdown" value={report.proof_packet.close_receipt.filename} />
                  <SmallValue label="JSON" value={report.proof_packet.close_receipt.json_filename} />
                  <SmallValue label="Paid step" value={report.proof_packet.close_receipt.next_paid_step || "n/a"} />
                  <SmallValue
                    label="Committee"
                    value={`${report.meeting_close_receipt.committee.accepted_roles}/${report.meeting_close_receipt.committee.total_roles} accepted`}
                  />
                </div>
                <ForwardingKitMini kit={report.meeting_close_receipt.forwarding_kit} compact className="mt-3" />
              </Link>
              <Link
                to={toAppRoute(report.proof_packet.activation_handoff.route)}
                className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={report.proof_packet.activation_handoff.ready ? "ok" : readinessTone(report.proof_packet.activation_handoff.status)}>
                    {report.proof_packet.activation_handoff.status}
                  </Badge>
                  <p className="break-words text-sm font-semibold text-card-foreground">Post-Demo Activation</p>
                </div>
                <p className="mt-2 break-words text-xs text-muted-foreground">{report.proof_packet.activation_handoff.why}</p>
                <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <SmallValue label="Markdown" value={report.proof_packet.activation_handoff.filename} />
                  <SmallValue label="JSON" value={report.proof_packet.activation_handoff.json_filename} />
                  <SmallValue label="Next window" value={report.proof_packet.activation_handoff.next_window} />
                  <SmallValue label="Start route" value={report.post_demo_activation_handoff.route} />
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {report.post_demo_activation_handoff.route_chain.slice(0, 5).map((route) => (
                    <span key={route} className="rounded-md bg-muted px-2 py-1 font-mono text-[11px] text-muted-foreground">
                      {route}
                    </span>
                  ))}
                </div>
                <ForwardingKitMini kit={report.post_demo_activation_handoff.forwarding_kit} compact className="mt-3" />
              </Link>
              <Link
                to={toAppRoute(report.proof_packet.room_map.route)}
                className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={report.proof_packet.room_map.ready ? "ok" : "warn"}>
                    {report.proof_packet.room_map.ready ? "room map ready" : "needs buyer brief"}
                  </Badge>
                  <p className="break-words text-sm font-semibold text-card-foreground">Buyer room map</p>
                </div>
                <p className="mt-2 break-words text-xs text-muted-foreground">{report.proof_packet.room_map.why}</p>
                <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                  {report.proof_packet.room_map.filename}
                </p>
                {report.proof_packet.room_map.sha256 && (
                  <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">
                    {report.proof_packet.room_map.sha256}
                  </p>
                )}
                <p className="mt-2 break-all font-mono text-[11px] text-muted-foreground">
                  Pulse: {report.proof_packet.room_map.pulse_filename || "buyer-pulse.md"}
                </p>
                <p className="mt-2 break-all font-mono text-[11px] text-muted-foreground">
                  Plan: {report.proof_packet.room_map.plan_filename || "buyer-room-plan.md"}
                </p>
                <p className="mt-2 break-all font-mono text-[11px] text-primary">
                  Path: {report.proof_packet.room_map.open_first_path_filename || "open-first-path.md"}
                </p>
                {report.proof_packet.room_map.open_first_path_sha256 && (
                  <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">
                    {report.proof_packet.room_map.open_first_path_sha256}
                  </p>
                )}
                <p className="mt-2 break-all font-mono text-[11px] text-primary">
                  {report.proof_packet.room_map.packet_filename || "rentgen-buyer-room-packet.zip"}
                </p>
                <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">
                  {report.proof_packet.room_map.packet_hash_header || "X-Buyer-Room-Packet-Sha256"}
                </p>
              </Link>
              <Link
                to={toAppRoute(report.proof_packet.archive.route)}
                className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={report.proof_packet.archive.ready ? "ok" : "warn"}>
                    {report.proof_packet.archive.ready ? "archive ready" : "needs bundle"}
                  </Badge>
                  <p className="break-words text-sm font-semibold text-card-foreground">ZIP proof archive</p>
                </div>
                <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                  {report.proof_packet.archive.filename}
                </p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{report.proof_packet.archive.why}</p>
                <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                  {report.proof_packet.archive.endpoint} · {report.proof_packet.archive.sha256_header}
                </p>
              </Link>
              <Link
                to={toAppRoute(report.proof_packet.killer_archive.route)}
                className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={report.proof_packet.killer_archive.ready ? "ok" : "warn"}>
                    {report.proof_packet.killer_archive.ready ? "killer zip ready" : "needs handoff"}
                  </Badge>
                  <p className="break-words text-sm font-semibold text-card-foreground">Killer Demo ZIP</p>
                </div>
                <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                  {report.proof_packet.killer_archive.filename}
                </p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{report.proof_packet.killer_archive.why}</p>
                <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                  {report.proof_packet.killer_archive.endpoint} / {report.proof_packet.killer_archive.sha256_header}
                </p>
                <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <SmallValue label="Open first" value={report.proof_packet.killer_archive.open_first} />
                  <SmallValue label="Manifest" value={report.proof_packet.killer_archive.manifest} />
                </div>
                <p className="mt-3 break-words font-mono text-[11px] text-muted-foreground">
                  {report.proof_packet.killer_archive.role_packets.join(", ")}
                </p>
              </Link>
              <Link
                to={toAppRoute(report.proof_packet.verification_packet.route)}
                className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={report.proof_packet.verification_packet.ready ? "ok" : "warn"}>
                    {report.proof_packet.verification_packet.ready ? "verify zip ready" : "needs archive"}
                  </Badge>
                  <p className="break-words text-sm font-semibold text-card-foreground">Verification Packet ZIP</p>
                </div>
                <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                  {report.proof_packet.verification_packet.filename}
                </p>
                <p className="mt-2 break-words text-xs text-muted-foreground">{report.proof_packet.verification_packet.why}</p>
                <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                  {report.proof_packet.verification_packet.endpoint} / {report.proof_packet.verification_packet.sha256_header}
                </p>
                <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <SmallValue label="Open first" value={report.proof_packet.verification_packet.open_first} />
                  <SmallValue label="Files" value={String(report.proof_packet.verification_packet.contains.length)} />
                </div>
              </Link>
              <Link
                to={toAppRoute("/evidence-bundle")}
                className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge
                    tone={
                      report.proof_packet.procurement_handoff.ready
                        ? "ok"
                        : report.proof_packet.procurement_handoff.blockers ||
                            report.proof_packet.procurement_handoff.missing_files
                          ? "danger"
                          : "warn"
                    }
                  >
                    {report.proof_packet.procurement_handoff.status || "handoff"}
                  </Badge>
                  <p className="break-words text-sm font-semibold text-card-foreground">Procurement handoff</p>
                </div>
                <p className="mt-2 break-words text-xs text-muted-foreground">
                  {report.proof_packet.procurement_handoff.why}
                </p>
                {report.proof_packet.procurement_handoff.open_order.length > 0 && (
                  <div className="mt-3 grid grid-cols-1 gap-2">
                    {report.proof_packet.procurement_handoff.open_order.slice(0, 6).map((item) => (
                      <div
                        key={`${item.step}-${item.route}-${item.file}`}
                        className="grid min-w-0 grid-cols-[26px_minmax(0,1fr)] gap-2 rounded-md border border-border bg-card p-2"
                      >
                        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-[11px] font-bold text-primary">
                          {item.step}
                        </span>
                        <span className="min-w-0">
                          <span className="block break-words text-xs font-semibold text-card-foreground">
                            {item.label}
                          </span>
                          <span className="mt-1 block break-all font-mono text-[11px] text-muted-foreground">
                            {item.file}
                          </span>
                          {item.hash_header && (
                            <span className="mt-1 block break-all font-mono text-[11px] text-primary">
                              {item.hash_header}
                            </span>
                          )}
                          <span className="mt-1 block break-words text-[11px] text-muted-foreground">
                            {item.check}
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <SmallValue label="Missing" value={String(report.proof_packet.procurement_handoff.missing_files)} />
                  <SmallValue label="Blockers" value={String(report.proof_packet.procurement_handoff.blockers)} />
                  <SmallValue label="Risk reviews" value={String(report.proof_packet.procurement_handoff.risk_review_items)} />
                  <SmallValue label="Recipients" value={String(report.proof_packet.procurement_handoff.recipients)} />
                  <SmallValue label="Verify steps" value={String(report.proof_packet.procurement_handoff.verification_steps)} />
                  <SmallValue label="Open first" value={report.proof_packet.procurement_handoff.open_first_file} />
                </div>
                {report.proof_packet.procurement_handoff.covered_by_current_demo.length > 0 && (
                  <p className="mt-3 break-words rounded-md bg-primary/10 p-2 text-xs font-semibold text-primary">
                    Current demo export covers: {report.proof_packet.procurement_handoff.covered_by_current_demo.join(", ")}
                  </p>
                )}
                <p className="mt-3 break-all font-mono text-xs text-muted-foreground">
                  {report.proof_packet.procurement_handoff.first_file} / {report.proof_packet.procurement_handoff.hash_header}
                </p>
                {report.proof_packet.procurement_handoff.attachments.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {report.proof_packet.procurement_handoff.attachments.slice(0, 5).map((item) => (
                      <span
                        key={`${item.route}-${item.file}`}
                        className="max-w-full break-all rounded-md bg-muted px-2 py-1 font-mono text-[11px] text-muted-foreground"
                      >
                        {item.file}
                      </span>
                    ))}
                  </div>
                )}
              </Link>
              <div className="space-y-2">
                {report.proof_packet.handoff.map((item) => (
                  <Link
                    key={item.recipient}
                    to={toAppRoute(item.route)}
                    className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone="muted">{item.recipient}</Badge>
                      <Badge tone={readinessTone(item.availability_status)}>{item.availability_status}</Badge>
                    </div>
                    <p className="mt-2 break-all font-mono text-xs font-semibold text-card-foreground">
                      {item.role_packet}
                    </p>
                    <p className="mt-2 break-words text-xs text-muted-foreground">{item.why}</p>
                    <p className="mt-2 break-words font-mono text-xs text-muted-foreground">
                      {item.available_files.join(", ")}
                    </p>
                    {item.missing_files.length > 0 && (
                      <p className="mt-2 break-words font-mono text-[11px] text-amber-700">
                        Missing: {item.missing_files.join(", ")}
                      </p>
                    )}
                  </Link>
                ))}
              </div>
              <div className="space-y-1">
                {report.proof_packet.files.slice(0, 12).map((item) => (
                  <Link
                    key={`${item.id}-${item.filename}`}
                    to={toAppRoute(item.route)}
                    className="block rounded-md bg-muted p-2 transition hover:bg-accent"
                  >
                    <p className="break-all font-mono text-xs text-card-foreground">{item.filename}</p>
                    <p className="mt-1 break-words text-[11px] text-muted-foreground">{item.id}</p>
                    {item.sha256 && <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">{item.sha256}</p>}
                  </Link>
                ))}
              </div>
            </div>
          </Panel>

          <Panel title="Exports" icon={Download}>
            <div className="space-y-2">
              {report.exports.map((item) => (
                <Link
                  key={item.filename}
                  to={toAppRoute(item.route)}
                  className="block rounded-lg border border-border bg-background/60 p-2 transition hover:bg-accent"
                >
                  <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                  <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{item.filename}</p>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Source signals" icon={FileText}>
            <KeyValue values={stringifyValues(report.source_signals)} />
          </Panel>

          <Panel title="Caveats" icon={AlertTriangle}>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {report.caveats.map((item) => (
                <li key={item} className="break-words">{item}</li>
              ))}
            </ul>
          </Panel>

          <Panel title="Markdown preview" icon={FileText}>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {report.markdown}
            </pre>
          </Panel>
        </aside>
      </div>
    </div>
  )
}

function ObjectionRouter({ report }: { report: KillerDemoResponse }) {
  const router = report.objection_router
  const primary = router.primary_objection

  return (
    <div className="border-b border-border p-4 sm:p-5">
      <Panel title="Objection router" icon={MessageSquare}>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={readinessTone(router.status)}>{router.status}</Badge>
              <Badge tone="ok">{router.ready_items} ready</Badge>
              <Badge tone="warn">{router.watch_items} watch</Badge>
              <Badge tone={router.blocked_items ? "danger" : "muted"}>{router.blocked_items} blocked</Badge>
            </div>
            <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{router.presenter_line}</p>
          </div>

          <Link
            to={toAppRoute(primary.route)}
            className="min-w-0 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={readinessTone(primary.status)}>{primary.status}</Badge>
              <Badge tone="muted">{primary.audience}</Badge>
            </div>
            <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{primary.objection}</p>
            <p className="mt-2 break-words text-sm text-muted-foreground">{primary.answer}</p>
            <p className="mt-3 break-words text-xs font-semibold text-card-foreground">{primary.close_question}</p>
          </Link>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          {router.items.map((item) => (
            <Link
              key={item.id}
              to={toAppRoute(item.route)}
              className="min-w-0 rounded-lg border border-border bg-background/60 p-3 transition hover:border-primary/40 hover:bg-accent/40"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={readinessTone(item.status)}>{item.status}</Badge>
                <Badge tone="muted">{item.audience}</Badge>
                <span className="text-xs font-semibold uppercase text-muted-foreground">{item.owner}</span>
              </div>
              <p className="mt-3 break-words text-sm font-semibold text-card-foreground">{item.objection}</p>
              <p className="mt-2 break-words text-xs text-muted-foreground">{item.answer}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="rounded-md bg-primary/10 px-2 py-1 font-mono text-xs font-semibold text-primary">
                  {item.route}
                </span>
                <span className="rounded-md bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
                  {item.proof_file}
                </span>
              </div>
              <p className="mt-3 break-words text-xs font-semibold text-muted-foreground">{item.close_question}</p>
            </Link>
          ))}
        </div>
      </Panel>
    </div>
  )
}

function CommercialClosePacket({ report }: { report: KillerDemoResponse }) {
  const close = report.commercial_close_packet
  const order = close.one_page_order

  return (
    <div className="border-b border-border p-4 sm:p-5">
      <Panel title="Commercial close packet" icon={Target}>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <div className="flex flex-wrap gap-2">
              <Badge tone={close.ready_to_ask ? "ok" : close.ready_to_close ? "warn" : "danger"}>
                {close.ready_to_ask ? "ready to ask" : close.ready_to_close ? "needs proof" : "hold quote"}
              </Badge>
              <Badge tone="muted">{close.close_mode}</Badge>
            </div>
            <h3 className="mt-3 break-words text-base font-bold text-card-foreground">{close.primary_ask}</h3>
            <Link
              to={toAppRoute(order.route)}
              className="mt-3 inline-flex max-w-full items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
            >
              <PackageCheck size={15} />
              <span className="break-words">{order.recommended_purchase}</span>
            </Link>
            <p className="mt-3 break-words text-sm text-muted-foreground">{close.buyer_line}</p>
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <SmallValue label="Value anchor" value={order.value_anchor} />
              <SmallValue label="AI rent" value={order.ai_rent_baseline} />
              <SmallValue label="3-year rent" value={order.three_year_ai_rent || "n/a"} />
              <SmallValue label="Local license" value={order.local_license_anchor || "n/a"} />
              <SmallValue label="Break-even" value={order.break_even || "n/a"} />
              <SmallValue label="Frame" value={order.commercial_frame} />
              <SmallValue label="Invoice trigger" value={order.first_invoice_trigger} />
            </div>
          </div>

          <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Checkout gates</p>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
              {close.checkout.map((item) => (
                <Link
                  key={`${item.gate}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="rounded-md bg-muted p-2 transition hover:bg-accent"
                >
                  <p className="break-words text-xs font-semibold text-card-foreground">{item.gate}</p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{item.evidence}</p>
                </Link>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Mutual action plan</p>
            <div className="mt-3 space-y-2">
              {close.mutual_action_plan.slice(0, 5).map((item, index) => (
                <Link
                  key={`${item.window}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="grid min-w-0 grid-cols-[30px_minmax(0,1fr)] gap-3 rounded-md bg-muted p-2 transition hover:bg-accent"
                >
                  <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
                    {index + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap gap-2">
                      <Badge tone="muted">{item.window}</Badge>
                      <Badge tone="muted">{item.owner}</Badge>
                    </div>
                    <p className="mt-2 break-words text-xs font-semibold text-card-foreground">{item.action}</p>
                    <p className="mt-1 break-words text-xs text-muted-foreground">{item.exit}</p>
                  </div>
                </Link>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Buyer commitments</p>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
              {close.buyer_commitments.map((item) => (
                <Link
                  key={`${item.role}-${item.route}`}
                  to={toAppRoute(item.route)}
                  className="rounded-md bg-muted p-2 transition hover:bg-accent"
                >
                  <Badge tone="warn">{item.role}</Badge>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{item.commitment}</p>
                </Link>
              ))}
            </div>
            <p className="mt-4 text-xs font-semibold uppercase text-muted-foreground">Close script</p>
            <div className="mt-3 space-y-2">
              {close.close_script.map((item) => (
                <div key={item} className="rounded-md bg-muted p-2 text-xs text-card-foreground">
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Evidence requirements</p>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3 xl:grid-cols-5">
            {close.evidence_requirements.map((item) => (
              <Link
                key={`${item.artifact}-${item.route}`}
                to={toAppRoute(item.route)}
                className="rounded-md bg-muted p-2 transition hover:bg-accent"
              >
                <p className="break-words text-xs font-semibold text-card-foreground">{item.artifact}</p>
                <p className="mt-1 break-words text-xs text-muted-foreground">{item.why}</p>
              </Link>
            ))}
          </div>
        </div>
      </Panel>
    </div>
  )
}

function ForwardingKitMini({
  kit,
  compact = false,
  className,
}: {
  kit?: {
    ready?: boolean
    source?: string
    packets?: RoleForwardingPacket[]
    packet_count?: number
    first_packet?: string
    why?: string
  }
  compact?: boolean
  className?: string
}) {
  if (!kit?.ready) return null

  const packets = (kit.packets || []).slice(0, compact ? 2 : 3)
  const packetCount = kit.packet_count || packets.length

  return (
    <div className={cn("rounded-lg border border-primary/25 bg-primary/5 p-3", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="ok">{packetCount} notes</Badge>
        {kit.source && <Badge tone="muted">{kit.source}</Badge>}
        <p className="break-words text-sm font-semibold text-card-foreground">Forwarding kit</p>
      </div>
      {kit.why && <p className="mt-2 break-words text-xs text-muted-foreground">{kit.why}</p>}
      {kit.first_packet && (
        <p className="mt-2 break-all font-mono text-xs text-primary">{kit.first_packet}</p>
      )}
      {packets.length > 0 && (
        <div className="mt-3 space-y-2">
          {packets.map((packet) => (
            <div key={`${packet.role}-${packet.filename}`} className="rounded-md bg-background/70 p-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="muted">{packet.role}</Badge>
                <span className="break-all font-mono text-[11px] text-primary">
                  {packet.forwarding_filename || packet.filename}
                </span>
              </div>
              <p className="mt-1 break-words text-xs font-medium text-card-foreground">
                {packet.forwarding_subject}
              </p>
              {!compact && packet.attachments?.length > 0 && (
                <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">
                  {packet.attachments.slice(0, 4).join(", ")}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SmallValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md bg-muted p-3">
      <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-card-foreground">{value}</p>
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

function NumberField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value.replace(/[^\d]/g, ""))}
        inputMode="numeric"
        className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary"
      />
    </label>
  )
}

function Toggle({ checked, label, onChange }: { checked: boolean; label: string; onChange: (value: boolean) => void }) {
  return (
    <label className="flex min-h-8 items-center justify-between gap-3 rounded-md bg-muted px-2 py-1.5">
      <span className="break-words text-sm font-medium text-card-foreground">{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 shrink-0 accent-primary"
      />
    </label>
  )
}

function ArchiveVerifyCard({ result }: { result: ArchiveVerifyResponse }) {
  const embedded = result.embedded_evidence_verify
  const headerHash = result.expected_headers?.["X-Killer-Demo-Archive-Sha256"] || result.expected_headers?.["X-Archive-Sha256"]
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="break-words text-sm font-semibold text-card-foreground">Archive verification</p>
        <Badge tone={archiveVerifyTone(result.status)}>{result.status}</Badge>
      </div>
      <div className="mt-3 space-y-1.5 font-mono text-xs">
        <p className="break-all text-card-foreground">{result.filename || "killer-demo-archive.zip"}</p>
        <p className="break-all text-primary">{result.archive_sha256}</p>
        {headerHash && <p className="break-all text-muted-foreground">header: {headerHash}</p>}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <SmallVerifyValue label="Checked" value={String(result.checked_files)} />
        <SmallVerifyValue label="High" value={String(result.summary.high)} />
        <SmallVerifyValue label="Findings" value={String(result.summary.findings)} />
      </div>
      {embedded && (
        <p className="mt-3 break-words rounded-md bg-primary/10 p-2 text-xs font-semibold text-primary">
          Embedded Evidence: {embedded.status}, {embedded.checked_files} files checked
        </p>
      )}
      {(result.verification_receipt || result.verification_receipt_markdown) && (
        <div className="mt-3 flex flex-wrap gap-2">
          {result.verification_receipt && (
            <button
              type="button"
              onClick={() =>
                downloadText(
                  result.verification_receipt?.receipt_files.json || "archive-verification-receipt.json",
                  JSON.stringify(result.verification_receipt, null, 2),
                  "application/json;charset=utf-8",
                )
              }
              className="inline-flex h-8 items-center rounded-md border border-border bg-card px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
            >
              Receipt JSON
            </button>
          )}
          {result.verification_receipt_markdown && (
            <button
              type="button"
              onClick={() =>
                downloadText(
                  result.verification_receipt?.receipt_files.markdown || "archive-verification-receipt.md",
                  result.verification_receipt_markdown || "",
                  "text/markdown;charset=utf-8",
                )
              }
              className="inline-flex h-8 items-center rounded-md border border-border bg-card px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
            >
              Receipt MD
            </button>
          )}
        </div>
      )}
      {result.findings.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {result.findings.slice(0, 4).map((item, index) => (
            <p key={`${item.code}-${item.filename || index}`} className="break-words text-xs text-muted-foreground">
              {item.severity}: {item.code}{item.filename ? ` / ${item.filename}` : ""}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}

function SmallVerifyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted p-2">
      <p className="text-[10px] font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-all text-xs font-bold text-card-foreground">{value}</p>
    </div>
  )
}

function archiveVerifyTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "pass") return "ok"
  if (status === "fail") return "danger"
  if (status === "warn") return "warn"
  return "muted"
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

function LinkButton({ to, children }: { to: AppRoute; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="inline-flex min-h-8 max-w-full items-center rounded-md border border-border bg-background px-2 py-1 text-xs font-semibold text-card-foreground transition hover:bg-accent"
    >
      <span className="break-words">{children}</span>
    </Link>
  )
}

function toNumber(value: string): number | undefined {
  if (!value.trim()) return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function KeyValue({ values }: { values: Record<string, string> }) {
  return (
    <div className="space-y-2">
      {Object.entries(values).map(([key, value]) => (
        <div key={key} className="flex items-start justify-between gap-3 border-b border-border pb-2 last:border-b-0 last:pb-0">
          <span className="text-xs font-semibold uppercase text-muted-foreground">{key}</span>
          <span className="break-words text-right text-sm font-medium text-card-foreground">{value}</span>
        </div>
      ))}
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

function stringifyValues(values: Record<string, string | number | boolean | null>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(values).map(([key, value]) => [key, value === null ? "" : String(value)]),
  )
}
