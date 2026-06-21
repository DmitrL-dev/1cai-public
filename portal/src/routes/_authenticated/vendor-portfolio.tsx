import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useMutation, useQuery } from "@tanstack/react-query"
import {
  AlertTriangle,
  Briefcase,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  PlayCircle,
  RefreshCw,
  Route as RouteIcon,
  ShieldCheck,
  TrendingUp,
  Wrench,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  vendorPortfolioApi,
  type VendorPortfolioBookResponse,
  type VendorPortfolioResponse,
  type VendorPortfolioSignal,
  type VendorPortfolioWorkPackage,
  type EvidenceBundleRequest,
} from "@/lib/api-client"
import { BuyerRoomPacketControls } from "@/components/BuyerRoomPacketControls"
import { OpenFirstPathList } from "@/components/OpenFirstPathList"
import { VerificationPacketControls } from "@/components/VerificationPacketControls"

export const Route = createFileRoute("/_authenticated/vendor-portfolio")({
  component: VendorPortfolioPage,
})

const nf = new Intl.NumberFormat("ru-RU")

type AppRoute =
  | "/"
  | "/buyer-concierge"
  | "/launch-room"
  | "/killer-demo"
  | "/board-pack"
  | "/outcome-ledger"
  | "/commercial-offer-studio"
  | "/enterprise-trust-center"
  | "/demo-command-center"
  | "/pilot-launchpad"
  | "/scenario-hub"
  | "/guided-demo"
  | "/business-case"
  | "/productization"
  | "/evidence-bundle"
  | "/value-packs"
  | "/change"
  | "/configurations"
  | "/platform-doctor"
  | "/release-readiness"
  | "/approvals"
  | "/audit"

const appRoutes = [
  "/",
  "/buyer-concierge",
  "/launch-room",
  "/killer-demo",
  "/board-pack",
  "/outcome-ledger",
  "/commercial-offer-studio",
  "/enterprise-trust-center",
  "/demo-command-center",
  "/pilot-launchpad",
  "/scenario-hub",
  "/guided-demo",
  "/business-case",
  "/productization",
  "/evidence-bundle",
  "/value-packs",
  "/change",
  "/configurations",
  "/platform-doctor",
  "/release-readiness",
  "/approvals",
  "/audit",
] as const satisfies readonly AppRoute[]

function toAppRoute(value: string): AppRoute {
  return (appRoutes as readonly string[]).includes(value) ? (value as AppRoute) : "/"
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

function VendorPortfolioPage() {
  const [clientName, setClientName] = useState("Demo client")
  const [configPath, setConfigPath] = useState("data/configs/unpacked")
  const [targetVersion, setTargetVersion] = useState("")
  const [portfolioName, setPortfolioName] = useState("Partner pipeline")
  const [portfolioText, setPortfolioText] = useState("Demo client|data/configs/unpacked|\nProspect without path||")
  const [auditParams, setAuditParams] = useState({
    clientName: "Demo client",
    configPath: "data/configs/unpacked",
    targetVersion: "",
  })
  const buildVerificationPacketRequest = (): EvidenceBundleRequest => ({
    client_name: clientName.trim() || "Demo client",
    config_path: configPath.trim() || undefined,
    target_platform_version: targetVersion.trim() || undefined,
    include_vendor: true,
    include_killer_demo: true,
  })
  const query = useQuery({
    queryKey: ["vendor-portfolio", auditParams],
    queryFn: () =>
      vendorPortfolioApi
        .audit({
          client_name: auditParams.clientName,
          config_path: auditParams.configPath || undefined,
          target_platform_version: auditParams.targetVersion || undefined,
        })
        .then((r) => r.data),
  })
  const runAudit = () => {
    const next = {
      clientName: clientName.trim() || "Demo client",
      configPath: configPath.trim(),
      targetVersion: targetVersion.trim(),
    }
    if (
      next.clientName === auditParams.clientName &&
      next.configPath === auditParams.configPath &&
      next.targetVersion === auditParams.targetVersion
    ) {
      void query.refetch()
      return
    }
    setAuditParams(next)
  }
  const portfolioMutation = useMutation({
    mutationFn: () =>
      vendorPortfolioApi
        .portfolio({
          portfolio_name: portfolioName.trim() || "Vendor portfolio",
          clients: parsePortfolioClients(portfolioText),
        })
        .then((r) => r.data),
  })

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-3 sm:space-y-6 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <Briefcase size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight text-foreground sm:text-3xl">
              Vendor Portfolio
            </h1>
          </div>
          <p className="mt-2 max-w-3xl break-words text-sm text-muted-foreground sm:text-base">
            Pre-sale audit pack: риск конфигурации, платформа, подключение, релизный gate и готовый markdown для КП.
          </p>
        </div>
        {query.data && <StatusBadge status={query.data.decision.status} score={query.data.decision.score} />}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 sm:px-5">
            <h2 className="text-sm font-semibold text-card-foreground sm:text-base">Клиент и контур</h2>
          </div>
          <div className="space-y-4 p-4 sm:p-5">
            <TextField label="Клиент" value={clientName} onChange={setClientName} />
            <TextField label="EDT/XML путь" value={configPath} onChange={setConfigPath} mono />
            <TextField
              label="Целевая платформа"
              value={targetVersion}
              onChange={setTargetVersion}
              placeholder="8.3.26.x"
            />
            <button
              onClick={runAudit}
              disabled={query.isFetching}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {query.isFetching ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Собрать audit pack
            </button>
            {query.data && (
              <button
                onClick={() => downloadMarkdown("rentgen-vendor-audit.md", query.data.markdown)}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:bg-accent"
              >
                <Download size={16} />
                Скачать markdown
              </button>
            )}
            <BuyerRoomPacketControls />
            <VerificationPacketControls
              buildRequest={buildVerificationPacketRequest}
              fallbackFilename={() => (clientName.trim() || "rentgen") + "-archive-verification-packet.zip"}
            />

            <div className="border-t border-border pt-4">
              <h3 className="text-sm font-semibold text-card-foreground">Portfolio mode</h3>
              <p className="mt-1 text-xs text-muted-foreground">Format: client|config path|target platform</p>
            </div>
            <TextField label="Portfolio" value={portfolioName} onChange={setPortfolioName} />
            <label className="block space-y-1.5">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Clients</span>
              <textarea
                value={portfolioText}
                onChange={(event) => setPortfolioText(event.target.value)}
                spellCheck={false}
                className="min-h-[120px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              />
            </label>
            <button
              onClick={() => portfolioMutation.mutate()}
              disabled={portfolioMutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60"
            >
              {portfolioMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Собрать portfolio
            </button>
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-border bg-card">
          {query.isError && (
            <div className="flex min-h-[420px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Vendor Portfolio не загрузился. Проверьте backend и параметры.</p>
            </div>
          )}

          {!query.data && !query.isError && (
            <div className="flex min-h-[420px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <Briefcase size={42} className="opacity-30" />
              <p className="text-sm">Собираю портфельный audit pack.</p>
            </div>
          )}

          {query.data && <PortfolioReport report={query.data} />}
        </section>
      </div>

      {portfolioMutation.isError && (
        <section className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          Portfolio mode не собрался. Проверьте backend и строки клиентов.
        </section>
      )}

      {portfolioMutation.data && <PortfolioBookReport report={portfolioMutation.data} />}
    </div>
  )
}

function PortfolioReport({ report }: { report: VendorPortfolioResponse }) {
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
          <p className="mt-2 break-words text-sm text-muted-foreground">
            {report.client.name}: {report.client.configuration}
            {report.client.configuration_version ? ` ${report.client.configuration_version}` : ""}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-5">
        <Metric label="Score" value={report.decision.score} icon={ShieldCheck} />
        <Metric label="Modules" value={report.portfolio.modules} icon={FileText} />
        <Metric label="Issues" value={report.portfolio.modules_with_issues} icon={AlertTriangle} />
        <Metric label="Red Areas" value={report.portfolio.red_areas} icon={XCircle} />
        <Metric label="Packages" value={report.work_packages.length} icon={Wrench} />
      </div>

      <div className="border-b border-border p-4 sm:p-5">
        <VendorRoomBridge bridge={report.vendor_room_bridge} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          <DealBoardPanel board={report.deal_board} />

          <Panel title="Commercial signals" icon={TrendingUp}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {report.commercial_signals.map((signal) => (
                <SignalCard key={signal.id} signal={signal} />
              ))}
            </div>
          </Panel>

          <Panel title="Work packages" icon={Briefcase}>
            <div className="space-y-3">
              {report.work_packages.map((item) => (
                <WorkPackageCard key={item.id} item={item} />
              ))}
            </div>
          </Panel>

          <Panel title="Top risks" icon={AlertTriangle}>
            {report.top_risks.length ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[620px] text-left text-sm">
                  <thead className="border-b border-border text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="py-2 pr-3 font-semibold">Module</th>
                      <th className="px-3 py-2 font-semibold">Domain</th>
                      <th className="px-3 py-2 font-semibold">Risk</th>
                      <th className="py-2 pl-3 font-semibold">Fan-in</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {report.top_risks.map((risk, index) => (
                      <tr key={`${risk.module_path ?? "risk"}-${index}`}>
                        <td className="py-3 pr-3">
                          <p className="break-all font-mono text-xs text-card-foreground">
                            {risk.module_path ?? "unknown"}
                          </p>
                        </td>
                        <td className="px-3 py-3 text-muted-foreground">{risk.domain ?? "Unassigned"}</td>
                        <td className="px-3 py-3 font-semibold text-card-foreground">{risk.risk ?? 0}</td>
                        <td className="py-3 pl-3 text-muted-foreground">{risk.fan_in ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Нет top-risk данных. Это caveat, а не зелёный статус.</p>
            )}
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Next actions" icon={CheckCircle2}>
            <div className="space-y-2">
              {report.next_actions.map((action) => (
                <Link
                  key={`${action.label}-${action.to}`}
                  to={toAppRoute(action.to)}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/60 px-3 py-2 text-sm font-medium text-card-foreground transition hover:bg-accent"
                >
                  <span className="break-words">{action.label}</span>
                  <CheckCircle2 size={16} className="shrink-0 text-primary" />
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Caveats" icon={AlertTriangle}>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {report.caveats.map((item) => (
                <li key={item} className="break-words">
                  {item}
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Markdown" icon={FileText}>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {report.markdown}
            </pre>
          </Panel>
        </aside>
      </div>
    </div>
  )
}

function VendorRoomBridge({ bridge }: { bridge: VendorPortfolioResponse["vendor_room_bridge"] }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-background/60">
      <div className="flex flex-col gap-3 border-b border-border px-4 py-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Briefcase size={17} className="text-primary" />
            <h3 className="break-words text-sm font-semibold text-card-foreground sm:text-base">Buyer room map</h3>
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
            to={toAppRoute(bridge.vendor_motion.route)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-semibold text-card-foreground transition hover:bg-accent"
          >
            <RouteIcon size={15} />
            Vendor
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
                className="rounded-lg border border-border bg-card p-3 transition hover:bg-accent"
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
                className="rounded-lg border border-border bg-card p-3 transition hover:bg-accent"
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
          <div className="rounded-lg border border-border bg-card p-3">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Meeting flow</p>
            <div className="mt-2 space-y-2">
              {bridge.meeting_flow.map((step) => (
                <Link
                  key={`${step.step}-${step.route}`}
                  to={toAppRoute(step.route)}
                  className="block rounded-md border border-border bg-background p-2 transition hover:bg-accent"
                >
                  <p className="break-words text-xs font-semibold text-card-foreground">
                    {step.step}. {step.label}
                  </p>
                  <p className="mt-1 break-words text-xs text-muted-foreground">{step.line}</p>
                </Link>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card p-3">
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

function PortfolioBookReport({ report }: { report: VendorPortfolioBookResponse }) {
  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="flex flex-col gap-4 border-b border-border p-4 sm:p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <DecisionIcon status={report.decision.status} />
            <h2 className="break-words text-lg font-bold text-card-foreground sm:text-xl">
              {report.portfolio.name}
            </h2>
          </div>
          <p className="mt-2 break-words text-sm text-muted-foreground">{report.decision.headline}</p>
        </div>
        <button
          onClick={() => downloadMarkdown("rentgen-vendor-portfolio.md", report.markdown)}
          className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 text-sm font-semibold text-foreground transition hover:bg-accent"
        >
          <Download size={16} />
          Markdown
        </button>
      </div>

      <div className="grid grid-cols-2 border-b border-border md:grid-cols-6">
        <Metric label="Avg Score" value={report.portfolio.avg_score} icon={ShieldCheck} />
        <Metric label="Clients" value={report.portfolio.clients} icon={Briefcase} />
        <Metric label="Ready" value={report.portfolio.ready} icon={CheckCircle2} />
        <Metric label="Watch" value={report.portfolio.watch} icon={AlertTriangle} />
        <Metric label="Risk" value={report.portfolio.risk} icon={XCircle} />
        <Metric label="Red Areas" value={report.portfolio.red_areas} icon={AlertTriangle} />
      </div>

      <div className="grid grid-cols-1 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <PortfolioDecisionBoardPanel board={report.decision_board} />

          <Panel title="Clients" icon={Briefcase}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-border text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3 font-semibold">Client</th>
                    <th className="px-3 py-2 font-semibold">Configuration</th>
                    <th className="px-3 py-2 font-semibold">Status</th>
                    <th className="px-3 py-2 font-semibold">Score</th>
                    <th className="py-2 pl-3 font-semibold">Issues</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {report.clients.map((client) => (
                    <tr key={`${client.name}-${client.configuration}`}>
                      <td className="py-3 pr-3 font-semibold text-card-foreground">{client.name}</td>
                      <td className="px-3 py-3 text-muted-foreground">{client.configuration}</td>
                      <td className="px-3 py-3"><Badge tone={statusTone(client.status)}>{client.status}</Badge></td>
                      <td className="px-3 py-3 text-card-foreground">{client.score}</td>
                      <td className="py-3 pl-3 text-muted-foreground">{client.modules_with_issues}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>

        <aside className="min-w-0 space-y-5">
          <Panel title="Opportunities" icon={TrendingUp}>
            <div className="space-y-3">
              {report.opportunities.slice(0, 8).map((item) => (
                <div key={item.id} className="rounded-lg border border-border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={item.priority === "P0" ? "danger" : "warn"}>{item.priority}</Badge>
                    <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{item.clients} clients</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Next actions" icon={CheckCircle2}>
            <div className="space-y-2">
              {report.next_actions.map((action) => (
                <Link
                  key={`${action.label}-${action.to}`}
                  to={toAppRoute(action.to)}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/60 px-3 py-2 text-sm font-medium text-card-foreground transition hover:bg-accent"
                >
                  <span className="break-words">{action.label}</span>
                  <CheckCircle2 size={16} className="shrink-0 text-primary" />
                </Link>
              ))}
            </div>
          </Panel>
        </aside>
      </div>
    </section>
  )
}

function SignalCard({ signal }: { signal: VendorPortfolioSignal }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <p className="break-words text-sm font-semibold text-card-foreground">{signal.title}</p>
      <p className="mt-1 text-xs font-semibold uppercase text-muted-foreground">{signal.value}</p>
      <p className="mt-2 break-words text-sm text-muted-foreground">{signal.offer}</p>
    </div>
  )
}

function WorkPackageCard({ item }: { item: VendorPortfolioWorkPackage }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Badge tone={item.priority === "P0" ? "danger" : "warn"}>{item.priority}</Badge>
          <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
        </div>
        <span className="shrink-0 text-xs font-medium text-muted-foreground">{item.effort}</span>
      </div>
      <p className="mt-2 break-words text-sm text-muted-foreground">{item.outcome}</p>
      <p className="mt-2 break-words text-xs text-muted-foreground">{item.evidence}</p>
    </div>
  )
}

function DealBoardPanel({ board }: { board: VendorPortfolioResponse["deal_board"] }) {
  return (
    <Panel title="Deal board" icon={Briefcase}>
      <div className="space-y-4">
        <div className="rounded-lg border border-border bg-background/60 p-3">
          <Badge tone={board.primary_package.priority === "P0" ? "danger" : "warn"}>
            {board.primary_package.priority}
          </Badge>
          <p className="mt-2 break-words text-sm font-semibold text-card-foreground">{board.recommended_motion}</p>
          <p className="mt-2 break-words text-xs text-muted-foreground">
            {board.primary_package.title}: {board.primary_package.evidence}
          </p>
        </div>
        <Link
          to={toAppRoute(board.next_step.to)}
          className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
        >
          <p className="break-words text-sm font-semibold text-card-foreground">{board.next_step.label}</p>
          <p className="mt-2 break-words text-xs text-muted-foreground">{board.next_step.reason}</p>
        </Link>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {board.role_sparks.map((item) => (
            <div key={item.role} className="rounded-lg border border-border bg-background/60 p-3">
              <p className="text-xs font-semibold uppercase text-muted-foreground">{item.role}</p>
              <p className="mt-2 break-words text-sm text-card-foreground">{item.spark}</p>
            </div>
          ))}
        </div>
        <ProofPacket items={board.proof_packet} />
      </div>
    </Panel>
  )
}

function PortfolioDecisionBoardPanel({ board }: { board: VendorPortfolioBookResponse["decision_board"] }) {
  return (
    <Panel title="Decision board" icon={TrendingUp}>
      <div className="space-y-4">
        <Link
          to={toAppRoute(board.next_commercial_move.to)}
          className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
        >
          <Badge tone={board.status === "risk" ? "danger" : "ok"}>{board.status}</Badge>
          <p className="mt-2 break-words text-sm font-semibold text-card-foreground">
            {board.next_commercial_move.label}
          </p>
          <p className="mt-2 break-words text-xs text-muted-foreground">{board.next_commercial_move.reason}</p>
        </Link>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {board.segments.map((segment) => (
            <Link
              key={segment.id}
              to={toAppRoute(segment.route)}
              className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
            >
              <p className="break-words text-sm font-semibold text-card-foreground">{segment.title}</p>
              <p className="mt-1 text-xs font-semibold uppercase text-muted-foreground">
                {nf.format(segment.clients.length)} clients
              </p>
              <p className="mt-2 break-words text-xs text-muted-foreground">{segment.motion}</p>
            </Link>
          ))}
        </div>

        <div className="space-y-2">
          {board.offer_sequence.map((item) => (
            <Link
              key={item.step}
              to={toAppRoute(item.route)}
              className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
            >
              <p className="text-xs font-semibold uppercase text-muted-foreground">Step {item.step}</p>
              <p className="mt-1 break-words text-sm font-semibold text-card-foreground">{item.title}</p>
              <p className="mt-2 break-words text-xs text-muted-foreground">{item.evidence}</p>
            </Link>
          ))}
        </div>

        <ProofPacket items={board.proof_packet} />
      </div>
    </Panel>
  )
}

function ProofPacket({ items }: { items: Array<{ title: string; route: string; artifact: string }> }) {
  return (
    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
      {items.map((item) => (
        <Link
          key={item.artifact}
          to={toAppRoute(item.route)}
          className="block rounded-lg border border-border bg-background/60 p-3 transition hover:bg-accent"
        >
          <p className="break-words text-sm font-semibold text-card-foreground">{item.title}</p>
          <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{item.artifact}</p>
        </Link>
      ))}
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

function StatusBadge({ status, score }: { status: string; score: number }) {
  const tone = status === "ready" ? "ok" : status === "risk" ? "danger" : "warn"
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2">
      <DecisionIcon status={status} />
      <div>
        <p className="text-xs font-medium uppercase text-muted-foreground">{status}</p>
        <p className="text-sm font-bold text-card-foreground">Score {score}</p>
      </div>
      <Badge tone={tone}>{tone}</Badge>
    </div>
  )
}

function DecisionIcon({ status }: { status: string }) {
  if (status === "ready") return <CheckCircle2 size={20} className="shrink-0 text-emerald-600" />
  if (status === "risk") return <XCircle size={20} className="shrink-0 text-destructive" />
  return <AlertTriangle size={20} className="shrink-0 text-amber-600" />
}

function statusTone(status: string): "ok" | "warn" | "danger" | "muted" {
  if (status === "ready" || status === "pass") return "ok"
  if (status === "risk" || status === "fail" || status === "critical" || status === "blocked") return "danger"
  if (status === "watch" || status === "warn" || status === "partial") return "warn"
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

function parsePortfolioClients(value: string) {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name, configPath, targetVersion] = line.split("|").map((part) => part.trim())
      return {
        name: name || "Client",
        config_path: configPath || undefined,
        target_platform_version: targetVersion || undefined,
      }
    })
}
