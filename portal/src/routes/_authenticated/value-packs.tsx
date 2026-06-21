import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import {
  AlertTriangle,
  Boxes,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  PackageCheck,
  PlayCircle,
  RefreshCw,
  Route as RouteIcon,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  valuePacksApi,
  type ValuePack,
  type ValuePacksResponse,
  type EvidenceBundleRequest,
} from "@/lib/api-client"
import { BuyerRoomPacketControls } from "@/components/BuyerRoomPacketControls"
import { OpenFirstPathList } from "@/components/OpenFirstPathList"
import { VerificationPacketControls } from "@/components/VerificationPacketControls"

export const Route = createFileRoute("/_authenticated/value-packs")({
  component: ValuePacksPage,
})

type AppRoute =
  | "/"
  | "/buyer-concierge"
  | "/launch-room"
  | "/killer-demo"
  | "/board-pack"
  | "/commercial-offer-studio"
  | "/enterprise-trust-center"
  | "/scenario-hub"
  | "/guided-demo"
  | "/business-case"
  | "/productization"
  | "/change"
  | "/quality"
  | "/testing"
  | "/architecture"
  | "/metadata"
  | "/update-war-room"
  | "/rights-rls"
  | "/evidence-bundle"
  | "/approvals"
  | "/audit"
  | "/release-readiness"
  | "/platform-doctor"
  | "/lock-radar"
  | "/extension-safety"
  | "/operations"
  | "/vendor-portfolio"
  | "/configurations"
  | "/value-packs"
  | "/offline-readiness"
  | "/team-governance"
  | "/admin"

const appRoutes = [
  "/",
  "/buyer-concierge",
  "/launch-room",
  "/killer-demo",
  "/board-pack",
  "/commercial-offer-studio",
  "/enterprise-trust-center",
  "/scenario-hub",
  "/guided-demo",
  "/business-case",
  "/productization",
  "/change",
  "/quality",
  "/testing",
  "/architecture",
  "/metadata",
  "/update-war-room",
  "/rights-rls",
  "/evidence-bundle",
  "/approvals",
  "/audit",
  "/release-readiness",
  "/platform-doctor",
  "/lock-radar",
  "/extension-safety",
  "/operations",
  "/vendor-portfolio",
  "/configurations",
  "/value-packs",
  "/offline-readiness",
  "/team-governance",
  "/admin",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/value-packs"
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

function buildValuePacksVerificationPacketRequest(): EvidenceBundleRequest {
  return {
    client_name: "Demo client",
    config_path: "data/configs/unpacked",
    include_value_packs: true,
    include_killer_demo: true,
  }
}

function ValuePacksPage() {
  const query = useQuery({
    queryKey: ["value-packs"],
    queryFn: () => valuePacksApi.catalog().then((r) => r.data),
  })

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <Boxes size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Value Packs
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Покупаемые пакеты продукта: роли, outcomes, evidence, маршруты и лицензирование без обязательной токенной подписки.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {query.data && <StatusBadge status={query.data.decision.status} score={query.data.decision.score} />}
          <button
            onClick={() => query.refetch()}
            disabled={query.isFetching}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-medium text-card-foreground transition hover:bg-accent disabled:opacity-60"
          >
            {query.isFetching ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            Обновить
          </button>
        </div>
      </header>

      {query.isLoading && (
        <div className="flex min-h-[360px] items-center justify-center rounded-lg border border-border bg-card text-muted-foreground">
          <Loader2 size={22} className="mr-2 animate-spin" />
          Собираю пакеты
        </div>
      )}

      {query.isError && (
        <div className="flex min-h-[360px] flex-col items-center justify-center gap-3 rounded-lg border border-border bg-card px-8 text-center text-destructive">
          <AlertTriangle size={42} />
          <p className="text-sm">Value Packs не загрузились. Проверьте backend.</p>
        </div>
      )}

      {query.data && <PacksReport report={query.data} />}
    </div>
  )
}

function PacksReport({ report }: { report: ValuePacksResponse }) {
  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-border bg-card p-4 sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="ok">{report.summary.pilot_ready} pilot-ready</Badge>
              <Badge tone={report.summary.beta ? "warn" : "ok"}>{report.summary.beta} beta</Badge>
              <Badge tone="muted">coverage {report.summary.coverage_score ?? "n/a"}</Badge>
            </div>
            <h2 className="mt-3 break-words text-lg font-bold text-card-foreground sm:text-2xl">
              {report.decision.headline}
            </h2>
            <p className="mt-2 max-w-4xl break-words text-sm text-muted-foreground">
              {report.licensing_story}
            </p>
          </div>
          <button
            onClick={() => downloadMarkdown("rentgen-value-packs.md", report.markdown)}
            className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 text-sm font-semibold text-foreground transition hover:bg-accent"
          >
            <Download size={16} />
            Markdown
          </button>
        </div>
        <BuyerRoomPacketControls className="mt-4 max-w-md" />
        <VerificationPacketControls
          buildRequest={buildValuePacksVerificationPacketRequest}
          fallbackFilename="demo-client-archive-verification-packet.zip"
          className="mt-3 max-w-md"
        />
      </section>

      <ValueRoomBridge bridge={report.value_room_bridge} />

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {report.packs.map((pack) => (
          <PackCard key={pack.id} pack={pack} />
        ))}
      </section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Panel title="Licensing story" icon={ShieldCheck}>
          <p className="break-words text-sm text-muted-foreground">{report.licensing_story}</p>
        </Panel>
        <Panel title="Caveats" icon={AlertTriangle}>
          <ul className="space-y-2 text-sm text-muted-foreground">
            {report.caveats.map((item) => (
              <li key={item} className="break-words">{item}</li>
            ))}
          </ul>
        </Panel>
      </section>
    </div>
  )
}

function ValueRoomBridge({ bridge }: { bridge: ValuePacksResponse["value_room_bridge"] }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-card">
      <div className="flex flex-col gap-3 border-b border-border px-4 py-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Boxes size={17} className="text-primary" />
            <h2 className="break-words text-sm font-semibold text-card-foreground sm:text-base">Buyer room map</h2>
            <Badge tone={statusTone(bridge.status)}>{bridge.status}</Badge>
            <Badge tone="muted">{bridge.source}</Badge>
          </div>
          <p className="mt-2 break-words text-sm text-muted-foreground">{bridge.room_line}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link
            to={toAppRoute(bridge.primary_motion.route)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
          >
            <PlayCircle size={15} />
            {bridge.primary_motion.label}
          </Link>
          <Link
            to={toAppRoute(bridge.value_motion.route)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-sm font-semibold text-foreground transition hover:bg-accent"
          >
            <RouteIcon size={15} />
            Pack
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-3">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {bridge.role_cards.map((card) => (
              <Link
                key={`${card.role}-${card.route}`}
                to={toAppRoute(card.route)}
                className="rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={statusTone(card.status)}>{card.title}</Badge>
                  <span className="break-all font-mono text-[11px] text-muted-foreground">{card.proof_file}</span>
                </div>
                <p className="mt-2 break-words text-xs text-muted-foreground">{card.spark}</p>
              </Link>
            ))}
          </div>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {bridge.proof_readiness.map((item) => (
              <Link
                key={item.id}
                to={toAppRoute(item.route)}
                className="rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={statusTone(item.status)}>{item.status}</Badge>
                  <span className="break-all font-mono text-[11px] text-muted-foreground">{item.file}</span>
                </div>
                <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                <p className="mt-1 break-words text-xs text-muted-foreground">{item.signal}</p>
              </Link>
            ))}
          </div>
        </div>

        <div className="min-w-0 space-y-3">
          <OpenFirstPathList path={bridge.open_first_path} toAppRoute={toAppRoute} />
          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Meeting flow</p>
            <div className="mt-2 space-y-2">
              {bridge.meeting_flow.map((step) => (
                <Link
                  key={`${step.step}-${step.route}`}
                  to={toAppRoute(step.route)}
                  className="block rounded-md border border-border bg-card p-2 transition hover:bg-accent"
                >
                  <p className="break-words text-xs font-semibold text-card-foreground">
                    {step.step}. {step.label}
                  </p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{step.line}</p>
                </Link>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">First files</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {bridge.files.map((file) => (
                <span key={file} className="rounded-md bg-muted px-2 py-1 font-mono text-[11px] text-muted-foreground">
                  {file}
                </span>
              ))}
            </div>
            <p className="mt-3 break-words text-sm font-medium text-card-foreground">{bridge.close_question}</p>
          </div>
        </div>
      </div>
    </section>
  )
}

function PackCard({ pack }: { pack: ValuePack }) {
  return (
    <article className="min-w-0 rounded-lg border border-border bg-card p-4 transition hover:border-primary/40 hover:bg-accent/30">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={pack.maturity === "pilot-ready" ? "ok" : "warn"}>{pack.maturity}</Badge>
            <span className="text-xs font-medium uppercase text-muted-foreground">{pack.audience}</span>
          </div>
          <h2 className="mt-2 break-words text-lg font-bold text-card-foreground">{pack.title}</h2>
          <p className="mt-2 break-words text-sm text-muted-foreground">{pack.outcome}</p>
        </div>
        <PackageCheck size={22} className="shrink-0 text-primary" />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <ListBlock title="Deliverables" icon={FileText} items={pack.deliverables} />
        <ListBlock title="Proof" icon={Sparkles} items={pack.proof_points} />
      </div>

      <p className="mt-4 break-words rounded-lg border border-border bg-background/60 p-3 text-sm text-muted-foreground">
        {pack.price_story}
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {pack.routes.map((route) => (
          <Link
            key={`${pack.id}-${route.to}`}
            to={toAppRoute(route.to)}
            className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-3 text-sm font-semibold text-card-foreground transition hover:border-primary/40 hover:bg-accent"
          >
            {route.label}
          </Link>
        ))}
      </div>
    </article>
  )
}

function ListBlock({ title, icon: Icon, items }: { title: string; icon: LucideIcon; items: string[] }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-card-foreground">
        <Icon size={15} className="text-primary" />
        {title}
      </div>
      <ul className="mt-2 space-y-1.5 text-sm text-muted-foreground">
        {items.map((item) => (
          <li key={item} className="break-words">{item}</li>
        ))}
      </ul>
    </div>
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

function StatusBadge({ status, score }: { status: string; score: number }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2">
      <CheckCircle2 size={18} className="text-emerald-600" />
      <div>
        <p className="text-xs font-medium uppercase text-muted-foreground">{status}</p>
        <p className="text-sm font-bold text-card-foreground">Score {score}</p>
      </div>
    </div>
  )
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

function statusTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "ready" || status === "pass") return "ok"
  if (status === "risk" || status === "fail" || status === "blocked" || status === "critical") return "danger"
  if (status === "watch" || status === "review_required") return "warn"
  return "muted"
}
