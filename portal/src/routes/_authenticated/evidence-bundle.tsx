import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Download,
  Files,
  FileCheck2,
  FileJson,
  FileText,
  Fingerprint,
  Landmark,
  ListChecks,
  Loader2,
  PackageCheck,
  RefreshCw,
  Send,
  ShieldCheck,
  Users,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { BuyerRoomPacketControls } from "@/components/BuyerRoomPacketControls"
import { VerificationPacketControls } from "@/components/VerificationPacketControls"
import { cn } from "@/lib/utils"
import {
  evidenceBundleApi,
  killerDemoApi,
  type ArchiveVerifyResponse,
  type DualArchiveVerifyResponse,
  type EvidenceArtifact,
  type EvidenceBundleRequest,
  type EvidenceBundleResponse,
  type EvidenceProcurementHandoff,
  type EvidenceProcurementRecipient,
  type EvidenceRecipientPacket,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/evidence-bundle")({
  component: EvidenceBundlePage,
})

const sampleModule = "CommonModules/СводнаяТаблицаУХ/Ext/Module.bsl"
const nf = new Intl.NumberFormat("ru-RU")

type AppRoute =
  | "/"
  | "/change"
  | "/testing"
  | "/evidence-bundle"
  | "/killer-demo"
  | "/launch-room"
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
  | "/approvals"
  | "/audit"
  | "/platform-doctor"
  | "/configurations"
  | "/value-packs"
  | "/vendor-portfolio"
  | "/lock-radar"
  | "/extension-safety"
  | "/safe-autopilot"
  | "/update-war-room"
  | "/rights-rls"

const appRoutes = [
  "/",
  "/change",
  "/testing",
  "/evidence-bundle",
  "/killer-demo",
  "/launch-room",
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
  "/approvals",
  "/audit",
  "/platform-doctor",
  "/configurations",
  "/value-packs",
  "/vendor-portfolio",
  "/lock-radar",
  "/extension-safety",
  "/safe-autopilot",
  "/update-war-room",
  "/rights-rls",
] as const satisfies readonly AppRoute[]

const routeLabels: Partial<Record<AppRoute, string>> = {
  "/": "Home",
  "/change": "Change",
  "/testing": "Testing",
  "/evidence-bundle": "Evidence Bundle",
  "/killer-demo": "Killer Demo",
  "/launch-room": "Launch Room",
  "/board-pack": "Board Pack",
  "/business-case": "Business Case",
  "/enterprise-trust-center": "Trust Center",
  "/safe-autopilot": "Safe Autopilot",
  "/rights-rls": "Rights & RLS",
  "/approvals": "Approvals",
  "/audit": "Audit",
}

const prioritySendFiles = [
  "buyer-brief.md",
  "buyer-room-plan.md",
  "buyer-pulse.md",
  "rentgen-director-report.md",
  "rentgen-architect-report.md",
  "rentgen-developer-report.md",
  "rentgen-qa-report.md",
  "rentgen-security-questionnaire.md",
  "enterprise-trust-center.md",
  "board-pack.md",
  "commercial-offer-studio.md",
  "business-case.md",
  "safe-autopilot.md",
  "test-factory.md",
  "rights-rls.md",
]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/"
}

function routeLabel(value: string) {
  const route = toAppRoute(value)
  return routeLabels[route] || value.replace(/^\//, "") || "Home"
}

function recipientRank(role: string) {
  const value = role.toLowerCase()
  if (value.includes("director") || value.includes("sponsor")) return 0
  if (value.includes("architect") || value.includes("cto")) return 1
  if (value.includes("security") || value.includes("procurement")) return 2
  if (value.includes("developer") || value.includes("qa")) return 3
  return 9
}

function sendFileRank(file: string) {
  const index = prioritySendFiles.indexOf(file)
  return index === -1 ? prioritySendFiles.length + 1 : index
}

function isHighlightedSendFile(file: string) {
  return (
    file.startsWith("rentgen-") && file.endsWith("-report.md")
  ) || file === "buyer-brief.md" || file === "buyer-room-plan.md" || file === "buyer-pulse.md" || file === "rentgen-security-questionnaire.md" || file === "enterprise-trust-center.md"
}

type BuyerRoomPlanEvidence = {
  mode?: string
  role?: string
  title?: string
  route?: string
  status?: string
  start_with?: string
  show?: string
  why?: string
  proof_file?: string
  close_question?: string
  send_files?: string[]
  sequence?: Array<{
    step?: number
    label?: string
    route?: string
    line?: string
  }>
}

function parseBuyerRoomPlan(artifact?: EvidenceArtifact): BuyerRoomPlanEvidence | null {
  if (!artifact) return null
  try {
    const payload = JSON.parse(artifact.json) as { buyer_room_plan?: BuyerRoomPlanEvidence }
    return payload.buyer_room_plan || null
  } catch {
    return null
  }
}

function downloadText(filename: string, content: string, type = "text/plain;charset=utf-8") {
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

function EvidenceBundlePage() {
  const [clientName, setClientName] = useState("Demo client")
  const [configPath, setConfigPath] = useState("data/configs/unpacked")
  const [targetVersion, setTargetVersion] = useState("")
  const [lockRadarLogPath, setLockRadarLogPath] = useState("data/tj")
  const [releaseName, setReleaseName] = useState("Evidence approval pack")
  const [monthlyAiCost, setMonthlyAiCost] = useState("120000")
  const [modulesText, setModulesText] = useState(sampleModule)
  const [includeDemo, setIncludeDemo] = useState(true)
  const [includeVendor, setIncludeVendor] = useState(true)
  const [includeUpdate, setIncludeUpdate] = useState(true)
  const [includeLockRadar, setIncludeLockRadar] = useState(false)
  const [includeExtensionSafety, setIncludeExtensionSafety] = useState(false)
  const [includeTestFactory, setIncludeTestFactory] = useState(true)
  const [includeSafeAutopilot, setIncludeSafeAutopilot] = useState(true)
  const [includeRights, setIncludeRights] = useState(true)
  const [includeValuePacks, setIncludeValuePacks] = useState(true)
  const [includeBusinessCase, setIncludeBusinessCase] = useState(true)
  const [includeBoardPack, setIncludeBoardPack] = useState(true)
  const [includeOutcomeLedger, setIncludeOutcomeLedger] = useState(true)
  const [includeLaunchRoom, setIncludeLaunchRoom] = useState(true)
  const [includeKillerDemo, setIncludeKillerDemo] = useState(true)
  const [includeBuyerConcierge, setIncludeBuyerConcierge] = useState(true)
  const [includeCommercialOfferStudio, setIncludeCommercialOfferStudio] = useState(true)
  const [includeDemoCommandCenter, setIncludeDemoCommandCenter] = useState(true)
  const [includeEnterpriseTrustCenter, setIncludeEnterpriseTrustCenter] = useState(true)
  const [includeGuidedDemo, setIncludeGuidedDemo] = useState(true)
  const [includeScenarioHub, setIncludeScenarioHub] = useState(true)
  const [includePilotLaunchpad, setIncludePilotLaunchpad] = useState(true)
  const [includeProductization, setIncludeProductization] = useState(true)
  const [includeGovernanceProof, setIncludeGovernanceProof] = useState(true)
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
  const [killerArchiveInfo, setKillerArchiveInfo] = useState<{
    filename: string
    sha256: string
    downloadSha256: string
    downloadHashMatches: boolean | null
    files: string
    evidenceSha256: string
    manifest: string
    manifestSha256: string
    manifestFiles: string
  } | null>(null)
  const [archiveVerify, setArchiveVerify] = useState<ArchiveVerifyResponse | null>(null)
  const [killerArchiveVerify, setKillerArchiveVerify] = useState<ArchiveVerifyResponse | null>(null)
  const [dualArchiveVerify, setDualArchiveVerify] = useState<DualArchiveVerifyResponse | null>(null)

  const buildRequest = (): EvidenceBundleRequest => ({
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
    include_demo: includeDemo,
    include_vendor: includeVendor,
    include_update: includeUpdate,
    include_lock_radar: includeLockRadar,
    include_extension_safety: includeExtensionSafety,
    include_test_factory: includeTestFactory,
    include_safe_autopilot: includeSafeAutopilot,
    include_rights: includeRights,
    include_value_packs: includeValuePacks,
    include_business_case: includeBusinessCase,
    include_board_pack: includeBoardPack,
    include_outcome_ledger: includeOutcomeLedger,
    include_launch_room: includeLaunchRoom,
    include_killer_demo: includeKillerDemo,
    include_buyer_concierge: includeBuyerConcierge,
    include_commercial_offer_studio: includeCommercialOfferStudio,
    include_demo_command_center: includeDemoCommandCenter,
    include_enterprise_trust_center: includeEnterpriseTrustCenter,
    include_guided_demo: includeGuidedDemo,
    include_scenario_hub: includeScenarioHub,
    include_pilot_launchpad: includePilotLaunchpad,
    include_productization: includeProductization,
    include_governance_proof: includeGovernanceProof,
  })

  const buildKillerDemoArchiveRequest = () => {
    const request = buildRequest()
    return {
      client_name: request.client_name,
      config_path: request.config_path,
      target_platform_version: request.target_platform_version,
      release_name: request.release_name,
      changed_modules: request.changed_modules,
      lock_radar_log_path: request.lock_radar_log_path,
      evidence_profile: "buyer" as const,
      include_update: request.include_update,
      include_rights: request.include_rights,
      include_lock_radar: request.include_lock_radar,
      include_extension_safety: request.include_extension_safety,
      assumptions: request.assumptions,
    }
  }

  const mutation = useMutation({
    mutationFn: () =>
      evidenceBundleApi.build(buildRequest()).then((r) => r.data),
  })
  const archiveMutation = useMutation({
    mutationFn: () =>
      evidenceBundleApi.archive(buildRequest()).then(async (r) => {
        const fallback = `${mutation.data?.bundle_id ?? "rentgen"}-evidence-archive.zip`
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
          manifest: String(r.headers["x-archive-manifest"] ?? ""),
          manifestSha256: String(r.headers["x-archive-manifest-sha256"] ?? ""),
          manifestFiles: String(r.headers["x-archive-manifest-files"] ?? ""),
        }
      }),
    onSuccess: setArchiveInfo,
  })
  const archiveVerifyMutation = useMutation({
    mutationFn: () =>
      evidenceBundleApi.verifyArchive(buildRequest()).then((r) => r.data),
    onSuccess: setArchiveVerify,
  })
  const killerArchiveMutation = useMutation({
    mutationFn: () =>
      killerDemoApi.archive(buildKillerDemoArchiveRequest()).then(async (r) => {
        const fallback = `${mutation.data?.bundle_id ?? "rentgen"}-killer-demo-archive.zip`
        const filename = filenameFromDisposition(r.headers["content-disposition"], fallback)
        const headerSha256 = String(r.headers["x-killer-demo-archive-sha256"] ?? r.headers["x-archive-sha256"] ?? "")
        const downloadSha256 = await sha256Blob(r.data)
        downloadBlob(filename, r.data)
        return {
          filename,
          sha256: headerSha256,
          downloadSha256,
          downloadHashMatches: downloadSha256 && headerSha256 ? downloadSha256 === headerSha256 : null,
          files: String(r.headers["x-archive-files"] ?? ""),
          evidenceSha256: String(r.headers["x-evidence-archive-sha256"] ?? ""),
          manifest: String(r.headers["x-killer-demo-manifest"] ?? ""),
          manifestSha256: String(r.headers["x-killer-demo-manifest-sha256"] ?? ""),
          manifestFiles: String(r.headers["x-killer-demo-manifest-files"] ?? ""),
        }
      }),
    onSuccess: setKillerArchiveInfo,
  })
  const killerArchiveVerifyMutation = useMutation({
    mutationFn: () =>
      killerDemoApi.verifyArchive(buildKillerDemoArchiveRequest()).then((r) => r.data),
    onSuccess: setKillerArchiveVerify,
  })
  const dualArchiveVerifyMutation = useMutation({
    mutationFn: () =>
      evidenceBundleApi.verifyDualArchive(buildRequest()).then((r) => r.data),
    onSuccess: setDualArchiveVerify,
  })

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <PackageCheck size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Evidence Bundle
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Один переносимый пакет доказательств: reports, caveats, JSON/Markdown artifacts и SHA-256 manifest.
          </p>
        </div>
        {mutation.data && <StatusBadge status={mutation.data.decision.status} score={mutation.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Bundle inputs</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <TextField label="Клиент" value={clientName} onChange={setClientName} />
            <TextField label="EDT/XML путь" value={configPath} onChange={setConfigPath} mono />
            <TextField label="Целевая платформа" value={targetVersion} onChange={setTargetVersion} placeholder="8.3.26.x" />
            <TextField label="Релиз / approval" value={releaseName} onChange={setReleaseName} />
            <TextField label="TJ path for Lock Radar" value={lockRadarLogPath} onChange={setLockRadarLogPath} mono />
            <NumberField label="AI / month" value={monthlyAiCost} onChange={setMonthlyAiCost} />
            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Changed modules</span>
              <textarea
                value={modulesText}
                onChange={(event) => setModulesText(event.target.value)}
                spellCheck={false}
                className="min-h-[130px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              />
            </label>

            <div className="grid grid-cols-1 gap-2 rounded-lg border border-border bg-background/60 p-3">
              <Toggle checked={includeDemo} label="Demo story" onChange={setIncludeDemo} />
              <Toggle checked={includeValuePacks} label="Value packs" onChange={setIncludeValuePacks} />
              <Toggle checked={includeBusinessCase} label="Business Case" onChange={setIncludeBusinessCase} />
              <Toggle checked={includeLaunchRoom} label="Launch Room" onChange={setIncludeLaunchRoom} />
              <Toggle checked={includeKillerDemo} label="Killer Demo" onChange={setIncludeKillerDemo} />
              <Toggle checked={includeBoardPack} label="Board Pack" onChange={setIncludeBoardPack} />
              <Toggle checked={includeOutcomeLedger} label="Outcome Ledger" onChange={setIncludeOutcomeLedger} />
              <Toggle checked={includeBuyerConcierge} label="Buyer Concierge" onChange={setIncludeBuyerConcierge} />
              <Toggle checked={includeCommercialOfferStudio} label="Commercial Offer Studio" onChange={setIncludeCommercialOfferStudio} />
              <Toggle checked={includeDemoCommandCenter} label="Demo Command Center" onChange={setIncludeDemoCommandCenter} />
              <Toggle checked={includeEnterpriseTrustCenter} label="Enterprise Trust Center" onChange={setIncludeEnterpriseTrustCenter} />
              <Toggle checked={includeGuidedDemo} label="Guided Demo" onChange={setIncludeGuidedDemo} />
              <Toggle checked={includeScenarioHub} label="Scenario Hub" onChange={setIncludeScenarioHub} />
              <Toggle checked={includePilotLaunchpad} label="Pilot Launchpad" onChange={setIncludePilotLaunchpad} />
              <Toggle checked={includeProductization} label="Productization" onChange={setIncludeProductization} />
              <Toggle checked={includeGovernanceProof} label="Governance proof" onChange={setIncludeGovernanceProof} />
              <Toggle checked={includeVendor} label="Vendor audit" onChange={setIncludeVendor} />
              <Toggle checked={includeUpdate} label="Update war room" onChange={setIncludeUpdate} />
              <Toggle checked={includeLockRadar} label="Lock Radar" onChange={setIncludeLockRadar} />
              <Toggle checked={includeExtensionSafety} label="Extension Safety" onChange={setIncludeExtensionSafety} />
              <Toggle checked={includeTestFactory} label="Test Factory" onChange={setIncludeTestFactory} />
              <Toggle checked={includeSafeAutopilot} label="Safe Autopilot" onChange={setIncludeSafeAutopilot} />
              <Toggle checked={includeRights} label="Rights/RLS" onChange={setIncludeRights} />
            </div>

            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Собрать bundle
            </button>
            <button
              onClick={() => archiveMutation.mutate()}
              disabled={archiveMutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60"
            >
              {archiveMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
              ZIP archive
            </button>
            <button
              onClick={() => archiveVerifyMutation.mutate()}
              disabled={archiveVerifyMutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-60 dark:text-emerald-300"
            >
              {archiveVerifyMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <FileCheck2 size={16} />}
              Verify Evidence ZIP
            </button>
            <button
              onClick={() => killerArchiveMutation.mutate()}
              disabled={killerArchiveMutation.isPending || !includeKillerDemo}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-primary/30 bg-primary/10 px-4 py-2.5 text-sm font-semibold text-primary transition hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {killerArchiveMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <PackageCheck size={16} />}
              Linked Killer Demo ZIP
            </button>
            <button
              onClick={() => killerArchiveVerifyMutation.mutate()}
              disabled={killerArchiveVerifyMutation.isPending || !includeKillerDemo}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-60 dark:text-emerald-300"
            >
              {killerArchiveVerifyMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
              Verify Killer ZIP
            </button>
            <button
              onClick={() => dualArchiveVerifyMutation.mutate()}
              disabled={dualArchiveVerifyMutation.isPending || !includeKillerDemo}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-primary/30 bg-primary/10 px-4 py-2.5 text-sm font-semibold text-primary transition hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {dualArchiveVerifyMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
              Verify Both ZIPs
            </button>
            <BuyerRoomPacketControls monthlyAiCost={monthlyAiCost} />
            <VerificationPacketControls
              buildRequest={buildRequest}
              disabled={!includeKillerDemo}
              fallbackFilename={() => `${clientName.trim() || "rentgen"}-archive-verification-packet.zip`}
              icon="download"
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
            {archiveVerify && <ArchiveVerifyCard title="Evidence ZIP verification" result={archiveVerify} />}
            {killerArchiveInfo && (
              <div className="rounded-lg border border-primary/25 bg-primary/5 p-3">
                <p className="break-all font-mono text-xs text-card-foreground">{killerArchiveInfo.filename}</p>
                <p className="mt-1 break-all font-mono text-xs text-primary">{killerArchiveInfo.sha256}</p>
                {killerArchiveInfo.downloadSha256 && (
                  <p className="mt-1 break-all font-mono text-xs text-emerald-700 dark:text-emerald-300">
                    local: {killerArchiveInfo.downloadSha256}
                  </p>
                )}
                {killerArchiveInfo.downloadHashMatches !== null && (
                  <p className="mt-1 text-xs font-semibold text-muted-foreground">
                    Download hash: {killerArchiveInfo.downloadHashMatches ? "match" : "mismatch"}
                  </p>
                )}
                <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{killerArchiveInfo.evidenceSha256}</p>
                {killerArchiveInfo.manifest && (
                  <p className="mt-1 break-all font-mono text-xs text-primary">{killerArchiveInfo.manifest}</p>
                )}
                {killerArchiveInfo.manifestSha256 && (
                  <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{killerArchiveInfo.manifestSha256}</p>
                )}
                <p className="mt-1 text-xs text-muted-foreground">{killerArchiveInfo.files} files</p>
                {killerArchiveInfo.manifestFiles && (
                  <p className="mt-1 text-xs text-muted-foreground">{killerArchiveInfo.manifestFiles} manifest entries</p>
                )}
              </div>
            )}
            {killerArchiveVerify && <ArchiveVerifyCard title="Killer ZIP verification" result={killerArchiveVerify} />}
            {dualArchiveVerify && <DualArchiveVerifyCard result={dualArchiveVerify} />}
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          {!mutation.data && !mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <PackageCheck size={42} className="opacity-30" />
              <p className="text-sm">Жду параметры bundle.</p>
            </div>
          )}

          {mutation.isError && (
            <div className="flex min-h-[520px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Evidence Bundle не собрался. Проверьте backend и параметры.</p>
            </div>
          )}

          {mutation.data && <BundleReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function BundleReport({ report }: { report: EvidenceBundleResponse }) {
  const openFirstMarkdown =
    report.open_first_markdown ||
    `# Open First\n\nDownload ${report.procurement_handoff.open_first_file || "OPEN_FIRST.md"} from the ZIP archive.`
  const receipt = report.commercial_assumptions
  const buyerRoomPlanArtifact = report.artifacts.find((artifact) => artifact.id === "buyer-room-plan")
  const buyerRoomPlan = parseBuyerRoomPlan(buyerRoomPlanArtifact)

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
          <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
            {report.bundle_id} · {report.manifest.bundle_sha256}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => downloadText(report.download_name, report.markdown, "text/markdown;charset=utf-8")}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-semibold text-foreground transition hover:bg-accent"
          >
            <Download size={16} />
            Markdown
          </button>
          <button
            onClick={() => downloadText(`${report.bundle_id}-bundle.json`, JSON.stringify(report, null, 2), "application/json;charset=utf-8")}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-semibold text-foreground transition hover:bg-accent"
          >
            <FileJson size={16} />
            Bundle JSON
          </button>
          <button
            onClick={() => downloadText(`${report.bundle_id}-manifest.json`, JSON.stringify(report.manifest, null, 2), "application/json;charset=utf-8")}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-semibold text-foreground transition hover:bg-accent"
          >
            <FileJson size={16} />
            Manifest
          </button>
          <button
            onClick={() => downloadText("OPEN_FIRST.md", openFirstMarkdown, "text/markdown;charset=utf-8")}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-primary/30 bg-primary/10 px-3 text-sm font-semibold text-primary transition hover:bg-primary/15"
          >
            <FileText size={16} />
            OPEN_FIRST
          </button>
          {report.archive_acceptance_receipt?.markdown && (
            <button
              onClick={() => downloadText("archive-acceptance-receipt.md", report.archive_acceptance_receipt.markdown, "text/markdown;charset=utf-8")}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-semibold text-foreground transition hover:bg-accent"
            >
              <FileCheck2 size={16} />
              Archive receipt
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-6">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Artifacts" value={report.summary.artifacts} icon={ClipboardList} />
        <Metric label="Files" value={report.summary.files} icon={FileText} />
        <Metric label="Risk" value={report.summary.risk_artifacts} icon={XCircle} />
        <Metric label="Watch" value={report.summary.watch_artifacts} icon={AlertTriangle} />
        <Metric label="Missing" value={report.summary.procurement_missing_files} icon={FileCheck2} />
      </div>

      {buyerRoomPlanArtifact && (
        <div className="border-b border-border p-4 sm:p-5">
          <BuyerRoomPlanEvidencePanel artifact={buyerRoomPlanArtifact} plan={buyerRoomPlan} />
        </div>
      )}

      <div className="border-b border-border p-4 sm:p-5">
        <ProcurementHandoffPanel handoff={report.procurement_handoff} />
      </div>

      {report.archive_acceptance_receipt && (
        <div className="border-b border-border p-4 sm:p-5">
          <ArchiveAcceptanceReceiptPanel receipt={report.archive_acceptance_receipt} />
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Artifacts" icon={PackageCheck}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.artifacts.map((artifact) => (
                <ArtifactCard key={artifact.id} artifact={artifact} />
              ))}
            </div>
          </Panel>

          <Panel title="Manifest" icon={Fingerprint}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-border text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3 font-semibold">File</th>
                    <th className="px-3 py-2 font-semibold">Type</th>
                    <th className="py-2 pl-3 font-semibold">SHA-256</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {report.manifest.files.map((file) => (
                    <tr key={`${file.filename}-${file.sha256}`}>
                      <td className="py-3 pr-3 font-mono text-xs text-card-foreground">{file.filename}</td>
                      <td className="px-3 py-3 text-xs text-muted-foreground">{file.media_type}</td>
                      <td className="py-3 pl-3 font-mono text-xs text-muted-foreground">{file.sha256}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Client" icon={ShieldCheck}>
            <KeyValue
              values={{
                Client: report.client.name,
                Config: report.client.config_path || "default",
                Target: report.client.target_platform_version || "unknown",
                Generated: new Date(report.generated_at).toLocaleString("ru-RU"),
              }}
            />
          </Panel>

          <Panel title="Commercial Assumptions" icon={Landmark}>
            <div className="space-y-3">
              <KeyValue
                values={{
                  Source: receipt.source || report.summary.commercial_assumption_source || "unknown",
                  "AI / month": receipt.monthly_ai_rent_label || "not provided",
                  "3-year AI rent": receipt.three_year_ai_rent_label || "not provided",
                  "Local license": receipt.local_license_anchor_label || "not provided",
                  "Break-even": receipt.break_even_label || "not provided",
                }}
              />
              {receipt.decision_line && (
                <p className="break-words rounded-lg bg-muted p-3 text-xs text-muted-foreground">
                  {receipt.decision_line}
                </p>
              )}
            </div>
          </Panel>

          <Panel title="Caveats" icon={AlertTriangle}>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {report.caveats.map((item) => (
                <li key={item} className="break-words">{item}</li>
              ))}
            </ul>
          </Panel>

          <Panel title="Open First" icon={FileCheck2}>
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {openFirstMarkdown}
            </pre>
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

function BuyerRoomPlanEvidencePanel({
  artifact,
  plan,
}: {
  artifact: EvidenceArtifact
  plan: BuyerRoomPlanEvidence | null
}) {
  const route = plan?.route || artifact.route || "/"
  const sequence = plan?.sequence || []
  const sendFiles = plan?.send_files || []
  const proofFile = plan?.proof_file || "buyer-brief.md"

  return (
    <Panel title="Buyer room plan" icon={ClipboardList}>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-4">
          <div className="flex flex-col gap-3 rounded-lg border border-primary/20 bg-primary/5 p-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={statusTone(artifact.status)}>{artifact.status}</Badge>
                {plan?.mode && <Badge tone="muted">{plan.mode}</Badge>}
                {plan?.role && <Badge tone="muted">{plan.role}</Badge>}
              </div>
              <p className="mt-2 break-words text-sm font-semibold text-card-foreground">
                {plan?.title || artifact.title}
              </p>
              {plan?.why && (
                <p className="mt-2 break-words text-xs text-muted-foreground">{plan.why}</p>
              )}
            </div>
            <Link
              to={toAppRoute(route)}
              className="inline-flex h-9 shrink-0 items-center justify-center gap-1 rounded-md border border-primary/30 bg-card px-3 text-xs font-semibold text-primary transition hover:bg-accent"
            >
              <span>{routeLabel(route)}</span>
              <ArrowRight size={13} />
            </Link>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <EvidenceNote title="Start" value={plan?.start_with || "Open the selected buyer route."} />
            <EvidenceNote title="Proof" value={`${plan?.show || "Show the selected proof."} File: ${proofFile}`} />
            <EvidenceNote title="Close" value={plan?.close_question || "Name the next paid step."} />
          </div>

          {sequence.length > 0 && (
            <ol className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {sequence.map((step) => (
                <li key={`${step.step}-${step.label}`} className="rounded-lg border border-border bg-background/60 p-3">
                  <span className="text-xs font-semibold uppercase text-muted-foreground">
                    {step.step}. {step.label}
                  </span>
                  <Link
                    to={toAppRoute(step.route || "/")}
                    className="mt-2 inline-flex max-w-full items-center gap-1 text-xs font-semibold text-primary"
                  >
                    <span className="truncate">{routeLabel(step.route || "/")}</span>
                    <ArrowRight size={12} className="shrink-0" />
                  </Link>
                  <p className="mt-2 break-words text-xs text-muted-foreground">{step.line}</p>
                </li>
              ))}
            </ol>
          )}
        </div>

        <div className="min-w-0 rounded-lg border border-border bg-background/60 p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="break-words text-sm font-semibold text-card-foreground">{artifact.filename}.md</p>
              <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{artifact.markdown_sha256}</p>
            </div>
            <div className="flex shrink-0 gap-1.5">
              <button
                onClick={() => downloadText(`${artifact.filename}.md`, artifact.markdown, "text/markdown;charset=utf-8")}
                className="inline-flex h-8 items-center rounded-md border border-border bg-card px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
              >
                .md
              </button>
              <button
                onClick={() => downloadText(`${artifact.filename}.json`, artifact.json, "application/json;charset=utf-8")}
                className="inline-flex h-8 items-center rounded-md border border-border bg-card px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
              >
                .json
              </button>
            </div>
          </div>

          <div className="mt-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Send files</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {sendFiles.map((file) => (
                <span
                  key={file}
                  className={cn(
                    "inline-block max-w-full break-all rounded-md border px-2 py-1 font-mono text-[11px] leading-4",
                    isHighlightedSendFile(file)
                      ? "border-primary/30 bg-primary/10 text-primary"
                      : "border-transparent bg-muted text-muted-foreground",
                  )}
                >
                  {file}
                </span>
              ))}
              {sendFiles.length === 0 && (
                <span className="text-xs text-muted-foreground">No send files in artifact JSON.</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </Panel>
  )
}

function EvidenceNote({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <p className="text-xs font-semibold uppercase text-muted-foreground">{title}</p>
      <p className="mt-2 break-words text-sm text-card-foreground">{value}</p>
    </div>
  )
}

function ArchiveAcceptanceReceiptPanel({
  receipt,
}: {
  receipt: EvidenceBundleResponse["archive_acceptance_receipt"]
}) {
  return (
    <Panel title="Archive acceptance receipt" icon={FileCheck2}>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={statusTone(receipt.status)}>{receipt.status}</Badge>
            <span className="text-xs font-semibold uppercase text-muted-foreground">
              {receipt.acceptance_steps.length} acceptance steps
            </span>
          </div>
          <p className="mt-2 break-words text-sm text-card-foreground">{receipt.buyer_line}</p>
        </div>
        <button
          onClick={() => downloadText("archive-acceptance-receipt.md", receipt.markdown, "text/markdown;charset=utf-8")}
          className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-md border border-border bg-background px-3 text-xs font-semibold text-card-foreground transition hover:bg-accent"
        >
          <Download size={14} />
          .md
        </button>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
        {receipt.archives.map((archive) => (
          <div key={archive.id} className="rounded-lg border border-border bg-background/60 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="break-words text-sm font-semibold text-card-foreground">{archive.title}</p>
              <Badge tone={statusTone(archive.status)}>{archive.status}</Badge>
            </div>
            <p className="mt-2 break-words text-xs text-muted-foreground">{archive.boundary}</p>
            <div className="mt-3 space-y-1.5 font-mono text-xs">
              <p className="break-all text-primary">{archive.endpoint}</p>
              <p className="break-all text-muted-foreground">{archive.filename}</p>
              <p className="break-all text-muted-foreground">{archive.hash_header}</p>
              <p className="break-all text-card-foreground">{archive.open_first_file}</p>
              <p className="break-all text-muted-foreground">{archive.manifest_file}</p>
              {archive.archive_manifest_file && (
                <p className="break-all text-primary">{archive.archive_manifest_file}</p>
              )}
            </div>
            <div className="mt-3">
              <p className="text-xs font-semibold uppercase text-muted-foreground">Contains</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {archive.contains.slice(0, 10).map((file) => (
                  <span key={file} className="inline-block max-w-full break-all rounded-md bg-muted px-2 py-1 font-mono text-[11px] leading-4 text-muted-foreground">
                    {file}
                  </span>
                ))}
              </div>
            </div>
            {archive.excludes.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-semibold uppercase text-muted-foreground">Not standalone here</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {archive.excludes.map((file) => (
                    <span key={file} className="inline-block max-w-full break-all rounded-md bg-amber-500/10 px-2 py-1 font-mono text-[11px] leading-4 text-amber-700 dark:text-amber-300">
                      {file}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <ol className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        {receipt.acceptance_steps.map((step) => (
          <li key={step.id} className="rounded-lg border border-border bg-background/60 p-3">
            <span className="text-xs font-semibold uppercase text-muted-foreground">{step.owner}</span>
            <p className="mt-2 break-words text-sm text-card-foreground">{step.action}</p>
            <p className="mt-2 break-words text-xs text-muted-foreground">{step.expected}</p>
          </li>
        ))}
      </ol>
    </Panel>
  )
}

function DualArchiveVerifyCard({ result }: { result: DualArchiveVerifyResponse }) {
  return (
    <div className="rounded-lg border border-primary/25 bg-primary/5 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="break-words text-sm font-semibold text-card-foreground">Dual archive verification</p>
        <Badge tone={statusTone(result.status)}>{result.status}</Badge>
      </div>
      <p className="mt-2 break-words text-xs text-muted-foreground">
        Evidence ZIP and linked Killer Demo ZIP checked as one procurement packet.
      </p>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <SmallVerifyValue label="Archives" value={String(result.summary.archives)} />
        <SmallVerifyValue label="High" value={String(result.summary.high)} />
        <SmallVerifyValue label="Findings" value={String(result.summary.findings)} />
      </div>
      <div className="mt-3 space-y-1.5 font-mono text-xs">
        <p className="break-all text-card-foreground">Evidence: {result.pair.evidence_archive_sha256}</p>
        <p className="break-all text-primary">Killer: {result.pair.killer_archive_sha256}</p>
        <p className="break-all text-muted-foreground">
          Embedded Evidence: {result.pair.killer_embedded_evidence_sha256}
        </p>
      </div>
      <p className="mt-3 rounded-md bg-background/70 p-2 text-xs font-semibold text-card-foreground">
        Same Evidence source archive: {result.pair.same_evidence_archive_hash ? "yes" : "no"}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() =>
            downloadText(
              result.receipt_files.json || "dual-archive-verification-packet.json",
              JSON.stringify(result, null, 2),
              "application/json;charset=utf-8",
            )
          }
          className="inline-flex h-8 items-center rounded-md border border-border bg-card px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
        >
          Packet JSON
        </button>
        <button
          type="button"
          onClick={() =>
            downloadText(
              result.receipt_files.markdown || "dual-archive-verification-packet.md",
              result.verification_packet_markdown || "",
              "text/markdown;charset=utf-8",
            )
          }
          className="inline-flex h-8 items-center rounded-md border border-border bg-card px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
        >
          Packet MD
        </button>
      </div>
    </div>
  )
}

function ArchiveVerifyCard({ title, result }: { title: string; result: ArchiveVerifyResponse }) {
  const embedded = result.embedded_evidence_verify
  const headerHash = result.expected_headers?.["X-Archive-Sha256"] || result.expected_headers?.["X-Killer-Demo-Archive-Sha256"]
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="break-words text-sm font-semibold text-card-foreground">{title}</p>
        <Badge tone={statusTone(result.status)}>{result.status}</Badge>
      </div>
      <div className="mt-3 space-y-1.5 font-mono text-xs">
        <p className="break-all text-card-foreground">{result.filename || result.archive_type}</p>
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

function ProcurementHandoffPanel({ handoff }: { handoff: EvidenceProcurementHandoff }) {
  const presentCount = handoff.required_files.length - handoff.missing_files.length
  const archiveManifestFile = handoff.archive_contents.find((file) => file === "archive-manifest.json")
  return (
    <Panel title="Procurement handoff" icon={Send}>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_390px]">
        <div className="min-w-0 space-y-4">
          <div className="flex flex-col gap-3 rounded-lg border border-border bg-background/60 p-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={statusTone(handoff.status)}>{handoff.status}</Badge>
                <span className="text-xs font-semibold uppercase text-muted-foreground">
                  {handoff.ready_to_forward ? "Forwardable" : "Owner review"}
                </span>
              </div>
              <p className="mt-2 break-words text-sm font-medium text-card-foreground">{handoff.buyer_line}</p>
              <p className="mt-2 font-mono text-xs text-primary">open first: {handoff.open_first_file || "OPEN_FIRST.md"}</p>
              <p className="mt-2 font-mono text-xs text-primary">archive manifest: {archiveManifestFile || "archive-manifest.json"}</p>
              <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                {handoff.archive_filename} · {handoff.bundle_sha256}
              </p>
            </div>
            <div className="shrink-0 rounded-lg border border-border bg-card px-3 py-2 text-sm">
              <p className="font-bold text-card-foreground">
                {presentCount}/{handoff.required_files.length}
              </p>
              <p className="text-xs text-muted-foreground">required files</p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {handoff.gates.map((gate) => (
              <Link
                key={gate.id}
                to={toAppRoute(gate.route)}
                className="min-w-0 rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="break-words text-sm font-semibold text-card-foreground">{gate.label}</p>
                  <Badge tone={statusTone(gate.status)}>{gate.status}</Badge>
                </div>
                <p className="mt-2 break-words text-xs text-muted-foreground">{gate.detail}</p>
              </Link>
            ))}
          </div>

          {handoff.killer_demo_handoff && (
            <LinkedKillerDemoArchive handoff={handoff.killer_demo_handoff} />
          )}

          {(handoff.blockers.length > 0 || handoff.review_items.length > 0) && (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {handoff.blockers.length > 0 && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3">
                  <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-destructive">
                    <XCircle size={15} />
                    Blockers
                  </div>
                  <ul className="space-y-1.5 text-xs text-destructive">
                    {handoff.blockers.map((item) => (
                      <li key={item} className="break-words">{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {handoff.review_items.length > 0 && (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
                  <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-700 dark:text-amber-300">
                    <AlertTriangle size={15} />
                    Review items
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {handoff.review_items.slice(0, 8).map((item) => (
                      <Link
                        key={`${item.id}-${item.status}`}
                        to={toAppRoute(item.route)}
                        className="inline-flex max-w-full items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-xs font-semibold text-card-foreground transition hover:bg-accent"
                      >
                        <span className="truncate">{item.title}</span>
                        <Badge tone={statusTone(item.status)}>{item.status}</Badge>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="min-w-0 space-y-4">
          <RolePackets recipients={handoff.recipients} recipientPackets={handoff.recipient_packets || []} />

          <div className="rounded-lg border border-border bg-background/60 p-3">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-card-foreground">
              <ListChecks size={15} className="text-primary" />
              Verification
            </div>
            <ol className="space-y-3">
              {handoff.verification_steps.map((step, index) => (
                <li key={step.id} className="grid grid-cols-[24px_minmax(0,1fr)] gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
                    {index + 1}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-xs font-semibold uppercase text-muted-foreground">{step.owner}</span>
                    <span className="block break-words text-sm text-card-foreground">{step.action}</span>
                    <span className="mt-1 block break-words text-xs text-muted-foreground">{step.expected}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[820px] text-left text-sm">
          <thead className="border-b border-border bg-muted/40 text-xs uppercase text-muted-foreground">
            <tr>
              <th className="py-2 pl-3 pr-2 font-semibold">File</th>
              <th className="px-2 py-2 font-semibold">Role</th>
              <th className="px-2 py-2 font-semibold">Status</th>
              <th className="py-2 pl-2 pr-3 font-semibold">SHA-256</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {handoff.required_files.map((file) => (
              <tr key={file.id}>
                <td className="py-3 pl-3 pr-2">
                  <Link to={toAppRoute(file.route)} className="font-mono text-xs font-semibold text-card-foreground transition hover:text-primary">
                    {file.filename}
                  </Link>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{file.why}</p>
                </td>
                <td className="px-2 py-3 text-xs text-muted-foreground">{file.role}</td>
                <td className="px-2 py-3">
                  <Badge tone={statusTone(file.status)}>{file.status}</Badge>
                </td>
                <td className="py-3 pl-2 pr-3 font-mono text-xs text-muted-foreground">
                  {file.sha256 || "missing"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

function LinkedKillerDemoArchive({
  handoff,
}: {
  handoff: NonNullable<EvidenceProcurementHandoff["killer_demo_handoff"]>
}) {
  const overlays = [...(handoff.recipient_overlays || [])].sort(
    (left, right) => recipientRank(left.role) - recipientRank(right.role) || left.role.localeCompare(right.role),
  )

  return (
    <div className="rounded-lg border border-primary/25 bg-primary/5 p-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <PackageCheck size={15} className="text-primary" />
            <p className="break-words text-sm font-semibold text-card-foreground">{handoff.title}</p>
            <Badge tone={statusTone(handoff.status)}>{handoff.status}</Badge>
          </div>
          <p className="mt-2 break-words text-xs text-muted-foreground">{handoff.buyer_line}</p>
          <p className="mt-2 break-all font-mono text-xs text-primary">{handoff.archive_endpoint}</p>
          <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
            {handoff.archive_filename} / {handoff.archive_hash_header}
          </p>
        </div>
        <Link
          to={toAppRoute(handoff.route)}
          className="inline-flex h-9 shrink-0 items-center justify-center gap-1 rounded-md border border-border bg-card px-3 text-xs font-semibold text-card-foreground transition hover:bg-accent"
        >
          <span>Killer Demo</span>
          <ArrowRight size={13} className="text-muted-foreground" />
        </Link>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-[220px_minmax(0,1fr)]">
        <div className="rounded-lg border border-border bg-card p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Open first</p>
          <p className="mt-2 break-all font-mono text-xs text-card-foreground">{handoff.open_first_file}</p>
          <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{handoff.manifest_file}</p>
        </div>

        <div className="min-w-0 rounded-lg border border-border bg-card p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Post-demo overlays</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {handoff.post_demo_files.map((file) => (
              <span key={file} className="inline-block max-w-full break-all rounded-md bg-primary/10 px-2 py-1 font-mono text-[11px] leading-4 text-primary">
                {file}
              </span>
            ))}
          </div>
        </div>
      </div>

      {overlays.length > 0 && (
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
          {overlays.map((overlay) => (
            <div key={overlay.role} className="rounded-lg border border-border bg-card p-3">
              <p className="break-words text-xs font-semibold text-card-foreground">{overlay.role}</p>
              <p className="mt-1 break-words text-xs text-muted-foreground">{overlay.reason}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {overlay.send_files.map((file) => (
                  <span key={file} className="inline-block max-w-full break-all rounded-md bg-muted px-2 py-1 font-mono text-[11px] leading-4 text-muted-foreground">
                    {file}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function RolePackets({
  recipients,
  recipientPackets,
}: {
  recipients: EvidenceProcurementRecipient[]
  recipientPackets: EvidenceRecipientPacket[]
}) {
  const orderedRecipients = [...recipients].sort(
    (left, right) => recipientRank(left.role) - recipientRank(right.role) || left.role.localeCompare(right.role),
  )
  const packetByRole = new Map(recipientPackets.map((packet) => [packet.role, packet]))

  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-card-foreground">
            <Users size={15} className="shrink-0 text-primary" />
            <span>Role packets</span>
          </div>
          <p className="mt-1 break-words text-xs text-muted-foreground">
            Send-ready files by stakeholder.
          </p>
        </div>
        <Badge tone="muted">{orderedRecipients.length} packets</Badge>
      </div>

      {orderedRecipients.length === 0 && (
        <p className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-muted-foreground">
          No recipient packets.
        </p>
      )}

      <div className="space-y-3">
        {orderedRecipients.map((recipient) => {
          const files = [...recipient.send_files].sort(
            (left, right) => sendFileRank(left) - sendFileRank(right) || left.localeCompare(right),
          )
          const routes = [...recipient.routes].filter(Boolean)
          const packet = packetByRole.get(recipient.role)

          return (
            <div key={recipient.role} className="rounded-lg border border-border bg-card p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="break-words text-sm font-semibold text-card-foreground">{recipient.role}</p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{recipient.decision}</p>
                  {recipient.packet_file && (
                    <p className="mt-2 break-all font-mono text-xs text-primary">{recipient.packet_file}</p>
                  )}
                  {packet?.forwarding_subject && (
                    <p className="mt-2 break-words text-xs font-medium text-card-foreground">
                      {packet.forwarding_subject}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1.5">
                  <Badge tone={files.some(isHighlightedSendFile) ? "ok" : "muted"}>{files.length} files</Badge>
                  {packet?.markdown && (
                    <button
                      onClick={() => downloadText(packet.filename, packet.markdown, "text/markdown;charset=utf-8")}
                      className="inline-flex h-7 items-center rounded-md border border-border bg-background px-2 text-[11px] font-semibold text-card-foreground transition hover:bg-accent"
                    >
                      .md
                    </button>
                  )}
                  {packet?.forwarding_body && (
                    <button
                      onClick={() =>
                        downloadText(
                          packet.forwarding_filename || packet.filename.replace(/\.md$/i, "-forwarding-note.txt"),
                          `Subject: ${packet.forwarding_subject || ""}\n\n${packet.forwarding_body}`,
                          "text/plain;charset=utf-8",
                        )
                      }
                      className="inline-flex h-7 items-center rounded-md border border-border bg-background px-2 text-[11px] font-semibold text-card-foreground transition hover:bg-accent"
                    >
                      .txt
                    </button>
                  )}
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-1.5">
                {files.map((file) => (
                  <span
                    key={file}
                    className={cn(
                      "inline-block max-w-full break-all rounded-md border px-2 py-1 font-mono text-[11px] leading-4",
                      isHighlightedSendFile(file)
                        ? "border-primary/30 bg-primary/10 text-primary"
                        : "border-transparent bg-muted text-muted-foreground",
                    )}
                  >
                    {file}
                  </span>
                ))}
              </div>

              {routes.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {routes.map((route) => (
                    <Link
                      key={route}
                      to={toAppRoute(route)}
                      className="inline-flex max-w-full items-center gap-1 rounded-md border border-border bg-background px-2 py-1 text-xs font-semibold text-card-foreground transition hover:bg-accent"
                    >
                      <Files size={12} className="shrink-0 text-primary" />
                      <span className="truncate">{routeLabel(route)}</span>
                      <ArrowRight size={12} className="shrink-0 text-muted-foreground" />
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ArtifactCard({ artifact }: { artifact: EvidenceArtifact }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="break-words text-sm font-semibold text-card-foreground">{artifact.title}</p>
          <p className="mt-1 font-mono text-xs text-muted-foreground">{artifact.filename}</p>
        </div>
        <Badge tone={statusTone(artifact.status)}>{artifact.status}</Badge>
      </div>
      <p className="mt-3 break-all font-mono text-xs text-muted-foreground">{artifact.json_sha256}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          to={toAppRoute(artifact.route)}
          className="inline-flex h-8 items-center rounded-md border border-border bg-background px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
        >
          Открыть
        </Link>
        {artifact.markdown && (
          <button
            onClick={() => downloadText(`${artifact.filename}.md`, artifact.markdown, "text/markdown;charset=utf-8")}
            className="inline-flex h-8 items-center rounded-md border border-border bg-background px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
          >
            .md
          </button>
        )}
        <button
          onClick={() => downloadText(`${artifact.filename}.json`, artifact.json, "application/json;charset=utf-8")}
          className="inline-flex h-8 items-center rounded-md border border-border bg-background px-2 text-xs font-semibold text-card-foreground transition hover:bg-accent"
        >
          .json
        </button>
      </div>
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

function toNumber(value: string): number | undefined {
  if (!value.trim()) return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
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

function KeyValue({ values }: { values: Record<string, string> }) {
  return (
    <div className="space-y-2">
      {Object.entries(values).map(([key, value]) => (
        <div key={key} className="flex items-start justify-between gap-3 border-b border-border pb-2 last:border-b-0 last:pb-0">
          <span className="text-xs font-semibold uppercase text-muted-foreground">{key}</span>
          <span className="break-all text-right text-sm font-medium text-card-foreground">{value}</span>
        </div>
      ))}
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
  if (status === "risk") return <XCircle size={20} className="shrink-0 text-destructive" />
  return <AlertTriangle size={20} className="shrink-0 text-amber-600" />
}

function statusTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "ready" || status === "pass" || status === "present" || status === "ready_to_forward") return "ok"
  if (status === "risk" || status === "fail" || status === "critical" || status === "blocked" || status === "missing") return "danger"
  if (status === "watch" || status === "warn" || status === "partial" || status === "review" || status === "review_required") return "warn"
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
