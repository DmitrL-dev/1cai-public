import { useState } from "react"
import type { ReactNode } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle2,
  FileCode,
  FileDiff,
  GitBranch,
  Loader2,
  Search,
  TestTube2,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  rentgenApi,
  type TestCoverageMatrixResponse,
} from "@/lib/api-client"

export const Route = createFileRoute("/_authenticated/testing")({
  component: TestingPage,
})

type Mode = "modules" | "diff"

const sampleModule = "CommonModules/СводнаяТаблицаУХ/Ext/Module.bsl"
const nf = new Intl.NumberFormat("ru-RU")

function TestingPage() {
  const [mode, setMode] = useState<Mode>("modules")
  const [text, setText] = useState(sampleModule)
  const [matchLimit, setMatchLimit] = useState(10)

  const mutation = useMutation({
    mutationFn: async () => {
      if (mode === "modules") {
        return rentgenApi
          .testCoverageMatrix({
            changed_modules: text
              .split(/\r?\n/)
              .map((line) => line.trim())
              .filter(Boolean),
            match_limit: matchLimit,
          })
          .then((r) => r.data)
      }
      return rentgenApi.testCoverageMatrix({ diff: text, match_limit: matchLimit }).then((r) => r.data)
    },
  })

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-1.5 sm:p-2">
              <TestTube2 size={20} className="text-primary sm:h-[22px] sm:w-[22px]" />
            </div>
            <h1 className="min-w-0 break-words text-xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl">
              Test Coverage Matrix
            </h1>
          </div>
          <p className="mt-2 break-words text-sm text-muted-foreground sm:text-base">
            Changed modules to exact tests, planned selectors, gaps, commands and test data.
          </p>
        </div>

        <div className="flex rounded-lg border border-border bg-card p-1">
          <ModeButton active={mode === "modules"} icon={FileCode} label="Modules" onClick={() => setMode("modules")} />
          <ModeButton active={mode === "diff"} icon={GitBranch} label="Diff" onClick={() => setMode("diff")} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-xl border border-border bg-card">
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-base font-semibold text-card-foreground">
              Scope
            </h2>
          </div>
          <div className="space-y-4 p-5">
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              spellCheck={false}
              className="min-h-[320px] w-full resize-y rounded-lg border border-border bg-background p-3 font-mono text-sm text-foreground outline-none transition focus:border-primary"
              placeholder={
                mode === "modules"
                  ? "CommonModules/...\nDocuments/.../Ext/ObjectModule.bsl"
                  : "diff --git a/CommonModules/... b/CommonModules/..."
              }
            />

            <NumberField label="Match limit" value={matchLimit} min={1} max={50} onChange={setMatchLimit} />

            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || !text.trim()}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
              Build Matrix
            </button>
          </div>
        </section>

        <section className="min-w-0 min-h-[640px] rounded-xl border border-border bg-card">
          {mutation.isError && (
            <div className="flex min-h-[640px] flex-col items-center justify-center gap-3 px-8 text-center text-destructive">
              <AlertTriangle size={42} />
              <p className="text-sm">Test matrix failed. Check backend availability and module paths.</p>
            </div>
          )}

          {!mutation.data && !mutation.isError && (
            <div className="flex min-h-[640px] flex-col items-center justify-center gap-3 px-8 text-center text-muted-foreground">
              <TestTube2 size={42} className="opacity-30" />
              <p className="text-sm">Waiting for changed modules or diff.</p>
            </div>
          )}

          {mutation.data && <CoverageReport report={mutation.data} />}
        </section>
      </div>
    </div>
  )
}

function CoverageReport({ report }: { report: TestCoverageMatrixResponse }) {
  return (
    <div>
      <div className="flex flex-col gap-4 border-b border-border p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <TestTube2 size={24} className={report.summary.gaps ? "text-amber-500" : "text-emerald-500"} />
            <h2 className="min-w-0 break-words text-lg font-bold text-card-foreground sm:text-xl">
              Risk-Driven Test Coverage
            </h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {report.inventory.summary.test_cases} local test cases - YAxUnit {report.inventory.summary.yaxunit_available ? "available" : "missing"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={report.summary.gaps ? "warn" : "ok"}>{report.summary.gaps} gaps</Badge>
          <Badge tone="muted">{report.summary.exact_tests} exact</Badge>
          <Badge tone="muted">{report.summary.planned_tests} planned</Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 border-b border-border sm:grid-cols-2 md:grid-cols-4">
        <Metric label="Covered" value={report.summary.covered} icon={CheckCircle2} />
        <Metric label="Planned" value={report.summary.planned} icon={FileDiff} />
        <Metric label="Gaps" value={report.summary.gaps} icon={AlertTriangle} />
        <Metric label="Impact" value={report.summary.total_impact_edges} icon={GitBranch} />
      </div>

      <div className="space-y-5 p-5">
        <Panel title="Matrix" icon={TestTube2}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[840px] text-left text-sm">
              <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="py-2 pr-3 font-semibold">Module</th>
                  <th className="px-3 py-2 font-semibold">Status</th>
                  <th className="px-3 py-2 font-semibold">Priority</th>
                  <th className="px-3 py-2 font-semibold">Risk</th>
                  <th className="px-3 py-2 font-semibold">Exact</th>
                  <th className="px-3 py-2 font-semibold">Planned</th>
                  <th className="py-2 pl-3 font-semibold">Command</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {report.modules.map((row) => (
                  <tr key={row.module_path}>
                    <td className="py-3 pr-3">
                      <p className="max-w-[260px] break-all font-mono text-xs text-card-foreground">{row.module_path}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{row.canonical.object_name || "unmapped"}</p>
                    </td>
                    <td className="px-3 py-3">
                      <Badge tone={row.coverage_status === "covered" ? "ok" : row.coverage_status === "planned" ? "warn" : "danger"}>
                        {row.coverage_status}
                      </Badge>
                    </td>
                    <td className="px-3 py-3 text-muted-foreground">{row.priority}</td>
                    <td className="px-3 py-3 tabular-nums text-card-foreground">{row.risk}</td>
                    <td className="px-3 py-3 tabular-nums text-card-foreground">{row.exact_tests.length}</td>
                    <td className="px-3 py-3 tabular-nums text-card-foreground">{row.planned_tests.length}</td>
                    <td className="py-3 pl-3">
                      <p className="max-w-[260px] break-all text-xs text-muted-foreground">{row.commands[0]}</p>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <Panel title="Test Data" icon={FileCode}>
            <ul className="space-y-3">
              {report.modules.flatMap((row) =>
                row.test_data_blueprint.slice(0, 2).map((item, index) => (
                  <li key={`${row.module_path}-${index}`} className="text-sm">
                    <p className="font-semibold text-card-foreground">{String(item.name)}</p>
                    <p className="text-muted-foreground">{String(item.purpose)}</p>
                  </li>
                )),
              )}
            </ul>
          </Panel>

          <Panel title="Markdown" icon={FileCode}>
            <pre className="max-h-[360px] overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {report.markdown}
            </pre>
          </Panel>
        </div>
      </div>
    </div>
  )
}

function ModeButton({ active, icon: Icon, label, onClick }: { active: boolean; icon: LucideIcon; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm font-medium transition sm:px-3",
        active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <Icon size={15} />
      <span className="hidden sm:inline">{label}</span>
    </button>
  )
}

function NumberField({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary"
      />
    </label>
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
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      </div>
      <div className="p-3">{children}</div>
    </div>
  )
}

function Badge({ tone, children }: { tone: "danger" | "warn" | "ok" | "muted"; children: ReactNode }) {
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
