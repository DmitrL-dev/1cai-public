import { useState } from "react"
import type { ReactNode } from "react"
import { useMutation } from "@tanstack/react-query"
import { Archive, Loader2, ShieldCheck } from "lucide-react"
import { cn } from "@/lib/utils"
import { managementApi, type BuyerRoomPacketVerifyResponse } from "@/lib/api-client"

type PacketInfo = {
  filename: string
  sha256: string
  downloadSha256: string
  downloadHashMatches: boolean | null
  files: string
  openFirst: string
}

type BuyerRoomPacketControlsProps = {
  monthlyAiCost?: number | string
  className?: string
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

function toNumber(value: number | string | undefined): number | undefined {
  if (typeof value === "number") return Number.isFinite(value) ? value : undefined
  if (!value?.trim()) return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function statusTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "ready" || status === "accepted" || status === "pass") return "ok"
  if (status === "blocked" || status === "fail" || status === "critical" || status === "missing") return "danger"
  if (status === "watch" || status === "review" || status === "warn") return "warn"
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

export function BuyerRoomPacketControls({ monthlyAiCost, className }: BuyerRoomPacketControlsProps) {
  const [packetInfo, setPacketInfo] = useState<PacketInfo | null>(null)
  const [verifyInfo, setVerifyInfo] = useState<BuyerRoomPacketVerifyResponse | null>(null)

  const params = () => ({ monthly_ai_subscription_cost: toNumber(monthlyAiCost) })

  const packetMutation = useMutation({
    mutationFn: () =>
      managementApi.buyerRoomPacket(params()).then(async (r) => {
        const filename = filenameFromDisposition(r.headers["content-disposition"], "rentgen-buyer-room-packet.zip")
        const headerSha256 = String(r.headers["x-buyer-room-packet-sha256"] ?? "")
        const downloadSha256 = await sha256Blob(r.data)
        downloadBlob(filename, r.data)
        return {
          filename,
          sha256: headerSha256,
          downloadSha256,
          downloadHashMatches: downloadSha256 && headerSha256 ? downloadSha256 === headerSha256 : null,
          files: String(r.headers["x-buyer-room-packet-files"] ?? ""),
          openFirst: String(r.headers["x-buyer-room-packet-open-first"] ?? "OPEN_FIRST_BUYER_ROOM.md"),
        }
      }),
    onSuccess: setPacketInfo,
  })

  const verifyMutation = useMutation({
    mutationFn: () => managementApi.buyerRoomPacketVerify(params()).then((r) => r.data),
    onSuccess: setVerifyInfo,
  })

  return (
    <div className={cn("space-y-3", className)}>
      <button
        onClick={() => packetMutation.mutate()}
        disabled={packetMutation.isPending}
        className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-primary/30 bg-primary/10 px-4 py-2.5 text-sm font-semibold text-primary transition hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {packetMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Archive size={16} />}
        Buyer Room Packet ZIP
      </button>
      <button
        onClick={() => verifyMutation.mutate()}
        disabled={verifyMutation.isPending}
        className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60"
      >
        {verifyMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
        Verify Buyer Room Packet
      </button>

      {packetInfo && (
        <div className="rounded-lg border border-primary/30 bg-primary/10 p-3">
          <p className="break-all font-mono text-xs text-card-foreground">{packetInfo.filename}</p>
          <p className="mt-1 break-all font-mono text-xs text-primary">{packetInfo.sha256}</p>
          {packetInfo.downloadSha256 && (
            <p className="mt-1 break-all font-mono text-xs text-emerald-700 dark:text-emerald-300">
              local: {packetInfo.downloadSha256}
            </p>
          )}
          {packetInfo.downloadHashMatches !== null && (
            <p className="mt-1 text-xs font-semibold text-muted-foreground">
              Download hash: {packetInfo.downloadHashMatches ? "match" : "mismatch"}
            </p>
          )}
          <p className="mt-1 break-all text-xs text-muted-foreground">
            {packetInfo.files} files / {packetInfo.openFirst}
          </p>
        </div>
      )}

      {verifyInfo && (
        <div className="rounded-lg border border-primary/30 bg-primary/10 p-3">
          <div className="flex flex-wrap gap-2">
            <Badge tone={statusTone(verifyInfo.status)}>{verifyInfo.status}</Badge>
            <Badge tone={verifyInfo.hash_table_status === "pass" ? "ok" : "warn"}>
              hash {verifyInfo.hash_table_status}
            </Badge>
            <Badge tone={verifyInfo.open_first_status === "pass" ? "ok" : "warn"}>
              open first {verifyInfo.open_first_status}
            </Badge>
          </div>
          <p className="mt-2 break-all font-mono text-xs text-card-foreground">{verifyInfo.filename}</p>
          <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{verifyInfo.archive_sha256}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {verifyInfo.checked_files} files / {verifyInfo.summary.findings} findings
          </p>
        </div>
      )}

      {packetMutation.isError && (
        <p className="break-words rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs font-semibold text-destructive">
          Buyer Room Packet ZIP did not build. Check backend and management inputs.
        </p>
      )}
      {verifyMutation.isError && (
        <p className="break-words rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs font-semibold text-destructive">
          Buyer Room Packet verification did not run. Check backend and management inputs.
        </p>
      )}
    </div>
  )
}
