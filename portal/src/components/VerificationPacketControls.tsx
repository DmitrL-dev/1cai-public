import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Download, FileCheck2, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { evidenceBundleApi, type EvidenceBundleRequest } from "@/lib/api-client"

type VerificationPacketInfo = {
  filename: string
  sha256: string
  downloadSha256: string
  downloadHashMatches: boolean | null
  files: string
  status: string
}

type VerificationPacketControlsProps = {
  buildRequest: () => EvidenceBundleRequest
  fallbackFilename?: string | (() => string)
  disabled?: boolean
  className?: string
  buttonClassName?: string
  infoClassName?: string
  errorMessage?: string
  compact?: boolean
  icon?: "download" | "fileCheck"
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

function fallbackValue(value: string | (() => string) | undefined) {
  if (typeof value === "function") return value()
  return value || "rentgen-archive-verification-packet.zip"
}

export function VerificationPacketControls({
  buildRequest,
  fallbackFilename,
  disabled,
  className,
  buttonClassName,
  infoClassName,
  errorMessage = "Verification Packet ZIP did not build. Check backend and evidence inputs.",
  compact = false,
  icon = "fileCheck",
}: VerificationPacketControlsProps) {
  const [packetInfo, setPacketInfo] = useState<VerificationPacketInfo | null>(null)
  const Icon = icon === "download" ? Download : FileCheck2
  const iconSize = compact ? 14 : 16
  const textSize = compact ? "text-[11px]" : "text-xs"

  const packetMutation = useMutation({
    mutationFn: () =>
      evidenceBundleApi.verificationPacketArchive(buildRequest()).then(async (r) => {
        const filename = filenameFromDisposition(r.headers["content-disposition"], fallbackValue(fallbackFilename))
        const headerSha256 = String(r.headers["x-verification-packet-sha256"] ?? r.headers["x-archive-sha256"] ?? "")
        const downloadSha256 = await sha256Blob(r.data)
        downloadBlob(filename, r.data)
        return {
          filename,
          sha256: headerSha256,
          downloadSha256,
          downloadHashMatches: downloadSha256 && headerSha256 ? downloadSha256 === headerSha256 : null,
          files: String(r.headers["x-verification-packet-files"] ?? ""),
          status: String(r.headers["x-dual-verification-status"] ?? ""),
        }
      }),
    onSuccess: setPacketInfo,
  })

  return (
    <div className={cn("space-y-3", className)}>
      <button
        onClick={() => packetMutation.mutate()}
        disabled={packetMutation.isPending || disabled}
        className={cn(
          "inline-flex w-full items-center justify-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-60 dark:text-emerald-300",
          compact && "min-h-9 rounded-md px-3 py-2 text-xs",
          buttonClassName,
        )}
      >
        {packetMutation.isPending ? <Loader2 size={iconSize} className="animate-spin" /> : <Icon size={iconSize} />}
        Verification Packet ZIP
      </button>
      {packetInfo && (
        <div
          className={cn(
            "rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3",
            compact && "rounded-md border-emerald-500/20 bg-card p-2",
            infoClassName,
          )}
        >
          <p className={cn("break-all font-mono text-card-foreground", textSize)}>{packetInfo.filename}</p>
          <p className={cn("mt-1 break-all font-mono text-muted-foreground", textSize)}>{packetInfo.sha256}</p>
          {packetInfo.downloadSha256 && (
            <p className={cn("mt-1 break-all font-mono text-emerald-700 dark:text-emerald-300", textSize)}>
              local: {packetInfo.downloadSha256}
            </p>
          )}
          {packetInfo.downloadHashMatches !== null && (
            <p className={cn("mt-1 font-semibold text-muted-foreground", textSize)}>
              Download hash: {packetInfo.downloadHashMatches ? "match" : "mismatch"}
            </p>
          )}
          <p className={cn("mt-1 text-muted-foreground", textSize)}>
            {packetInfo.files} files / {packetInfo.status || "status unavailable"}
          </p>
        </div>
      )}
      {packetMutation.isError && (
        <p
          className={cn(
            "break-words rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs font-semibold text-destructive",
            compact && "rounded-md p-2 text-[11px]",
          )}
        >
          {errorMessage}
        </p>
      )}
    </div>
  )
}
