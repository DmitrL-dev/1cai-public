import { useState } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import { Loader2, Sparkles, Zap, TestTube2, Copy, Check, GitBranch, ShieldCheck, ClipboardList } from "lucide-react"
import { copilotApi, type GroundedGenerationResponse } from "@/lib/api-client"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_authenticated/copilot")({
  component: CopilotPage,
})

type Tab = "generate" | "optimize" | "tests"

function CopilotPage() {
  const [activeTab, setActiveTab] = useState<Tab>("generate")

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "generate", label: "Generate", icon: <Sparkles className="size-4" /> },
    { id: "optimize", label: "Optimize", icon: <Zap className="size-4" /> },
    { id: "tests", label: "Tests", icon: <TestTube2 className="size-4" /> },
  ]

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          AI Copilot
        </h1>
        <p className="mt-1 text-muted-foreground">
          Generate code, optimize performance, and create tests with AI
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg border border-border bg-muted/50 p-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex flex-1 items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors",
              activeTab === tab.id
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "generate" && <GenerateTab />}
      {activeTab === "optimize" && <OptimizeTab />}
      {activeTab === "tests" && <TestsTab />}
    </div>
  )
}

/* ── Generate Tab ─────────────────────────────────────────── */

function GenerateTab() {
  const [prompt, setPrompt] = useState("")
  const [codeType, setCodeType] = useState<"function" | "procedure" | "test">("function")
  const [modulePath, setModulePath] = useState("")
  const [metadataIdentifier, setMetadataIdentifier] = useState("")
  const [includeIts, setIncludeIts] = useState(true)
  const [includeImpact, setIncludeImpact] = useState(true)

  const mutation = useMutation({
    mutationFn: () =>
      copilotApi.generateGrounded({
        prompt,
        type: codeType,
        module_path: modulePath.trim() || undefined,
        metadata_identifier: metadataIdentifier.trim() || undefined,
        include_its_context: includeIts,
        include_requirement_impact: includeImpact,
      }).then((r) => r.data),
  })

  const data = mutation.data as GroundedGenerationResponse | undefined

  return (
    <div className="space-y-5">
      <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(260px,0.6fr)]">
        <div className="min-w-0 space-y-2">
          <label className="text-sm font-medium text-foreground">
            Requirement or change intent
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Create a posting helper for a sales document with safe validation and focused tests"
            rows={7}
            className="w-full resize-none rounded-lg border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div className="min-w-0 space-y-4 rounded-lg border border-border bg-muted/20 p-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Artifact</label>
            <div className="grid grid-cols-3 gap-1 rounded-lg border border-border bg-background p-1">
              {(["function", "procedure", "test"] as const).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setCodeType(type)}
                  className={cn(
                    "rounded-md px-2 py-2 text-xs font-medium capitalize transition-colors",
                    codeType === type
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Module path</label>
            <input
              value={modulePath}
              onChange={(e) => setModulePath(e.target.value)}
              placeholder="CommonModules/Sales/Ext/Module.bsl"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Metadata object</label>
            <input
              value={metadataIdentifier}
              onChange={(e) => setMetadataIdentifier(e.target.value)}
              placeholder="Document.SalesOrder"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={includeIts}
              onChange={(e) => setIncludeIts(e.target.checked)}
              className="size-4 rounded border-border"
            />
            ITS context
          </label>

          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={includeImpact}
              onChange={(e) => setIncludeImpact(e.target.checked)}
              className="size-4 rounded border-border"
            />
            Requirement impact
          </label>
        </div>
      </div>

      <button
        onClick={() => mutation.mutate()}
        disabled={!prompt.trim() || mutation.isPending}
        className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:pointer-events-none disabled:opacity-50"
      >
        {mutation.isPending ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Sparkles className="size-4" />
        )}
        Generate Code
      </button>

      {mutation.isError && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to generate code. Please try again.
        </div>
      )}

      {mutation.isSuccess && (
        <div className="space-y-5">
          <div className="grid min-w-0 gap-4 lg:grid-cols-3">
            <DetailPanel
              title="Plan"
              icon={<ClipboardList className="size-4" />}
              items={data?.plan}
              emptyLabel="No plan returned"
            />
            <DetailPanel
              title="Risk Controls"
              icon={<ShieldCheck className="size-4" />}
              items={data?.risk_controls}
              emptyLabel="No controls returned"
            />
            <DetailPanel
              title="Tests"
              icon={<TestTube2 className="size-4" />}
              items={data?.test_actions}
              emptyLabel="No test actions returned"
            />
          </div>

          <CodeBlock
            title="Generated Code"
            code={data?.code ?? JSON.stringify(data, null, 2)}
          />

          <div className="grid min-w-0 gap-4 lg:grid-cols-2">
            <JsonPanel title="Grounding" icon={<GitBranch className="size-4" />} value={data?.grounding} />
            <JsonPanel title="Diagnostics" icon={<Zap className="size-4" />} value={data?.diagnostics} />
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Optimize Tab ─────────────────────────────────────────── */

function OptimizeTab() {
  const [code, setCode] = useState("")

  const mutation = useMutation({
    mutationFn: (c: string) => copilotApi.optimize(c).then((r) => r.data),
  })

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">
          Paste your code to optimize
        </label>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="Paste your code here..."
          rows={8}
          className="w-full resize-none rounded-lg border border-border bg-background px-4 py-3 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      <button
        onClick={() => mutation.mutate(code)}
        disabled={!code.trim() || mutation.isPending}
        className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:pointer-events-none disabled:opacity-50"
      >
        {mutation.isPending ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Zap className="size-4" />
        )}
        Optimize
      </button>

      {mutation.isError && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to optimize code. Please try again.
        </div>
      )}

      {mutation.isSuccess && (
        <div className="space-y-4">
          {mutation.data?.summary && (
            <div className="rounded-lg border border-border bg-muted/50 px-4 py-3">
              <h3 className="mb-1 text-sm font-medium text-foreground">
                Optimization Summary
              </h3>
              <p className="text-sm text-muted-foreground">
                {mutation.data.summary}
              </p>
            </div>
          )}
          <CodeBlock
            title="Optimized Code"
            code={mutation.data?.code ?? mutation.data?.optimized_code ?? JSON.stringify(mutation.data, null, 2)}
          />
        </div>
      )}
    </div>
  )
}

/* ── Tests Tab ────────────────────────────────────────────── */

function TestsTab() {
  const [code, setCode] = useState("")

  const mutation = useMutation({
    mutationFn: (c: string) => copilotApi.generateTests(c).then((r) => r.data),
  })

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">
          Paste your code to generate tests for
        </label>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="Paste the code you want to test..."
          rows={8}
          className="w-full resize-none rounded-lg border border-border bg-background px-4 py-3 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      <button
        onClick={() => mutation.mutate(code)}
        disabled={!code.trim() || mutation.isPending}
        className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:pointer-events-none disabled:opacity-50"
      >
        {mutation.isPending ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <TestTube2 className="size-4" />
        )}
        Generate Tests
      </button>

      {mutation.isError && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to generate tests. Please try again.
        </div>
      )}

      {mutation.isSuccess && (
        <CodeBlock
          title="Generated Tests"
          code={mutation.data?.code ?? mutation.data?.test_code ?? JSON.stringify(mutation.data, null, 2)}
        />
      )}
    </div>
  )
}

/* ── Shared Code Block ────────────────────────────────────── */

function stringifyValue(value: unknown) {
  if (value === null || value === undefined || value === "") return null
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value)
  }
  return JSON.stringify(value, null, 2)
}

function detailTitle(item: Record<string, unknown>) {
  return String(item.title ?? item.control ?? item.selector ?? item.id ?? "Item")
}

function detailSubtitle(item: Record<string, unknown>) {
  return stringifyValue(item.reason ?? item.target ?? item.status ?? item.framework)
}

function DetailPanel({
  title,
  icon,
  items,
  emptyLabel,
}: {
  title: string
  icon: React.ReactNode
  items?: Array<Record<string, unknown>>
  emptyLabel: string
}) {
  return (
    <div className="min-w-0 rounded-lg border border-border bg-background">
      <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-4 py-2 text-sm font-medium text-foreground">
        {icon}
        {title}
      </div>
      <div className="max-h-72 space-y-3 overflow-auto p-4">
        {items?.length ? (
          items.slice(0, 6).map((item, index) => {
            const subtitle = detailSubtitle(item)
            const details = stringifyValue(item.details)
            return (
              <div key={`${title}-${index}`} className="min-w-0 border-b border-border/60 pb-3 last:border-0 last:pb-0">
                <div className="break-words text-sm font-medium text-foreground">
                  {detailTitle(item)}
                </div>
                {subtitle && (
                  <div className="mt-1 break-words text-xs text-muted-foreground">
                    {subtitle}
                  </div>
                )}
                {details && (
                  <pre className="mt-2 max-h-24 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted/50 p-2 text-xs text-muted-foreground">
                    {details}
                  </pre>
                )}
              </div>
            )
          })
        ) : (
          <div className="text-sm text-muted-foreground">{emptyLabel}</div>
        )}
      </div>
    </div>
  )
}

function JsonPanel({
  title,
  icon,
  value,
}: {
  title: string
  icon: React.ReactNode
  value: unknown
}) {
  return (
    <div className="min-w-0 overflow-hidden rounded-lg border border-border bg-background">
      <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-4 py-2 text-sm font-medium text-foreground">
        {icon}
        {title}
      </div>
      <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words p-4 text-xs leading-relaxed text-muted-foreground">
        {JSON.stringify(value ?? {}, null, 2)}
      </pre>
    </div>
  )
}

function CodeBlock({ title, code }: { title: string; code: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div className="flex items-center justify-between border-b border-border bg-muted/50 px-4 py-2">
        <span className="text-sm font-medium text-foreground">{title}</span>
        <button
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          {copied ? (
            <>
              <Check className="size-3.5" />
              Copied
            </>
          ) : (
            <>
              <Copy className="size-3.5" />
              Copy
            </>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto bg-background p-4 font-mono text-sm leading-relaxed text-foreground">
        {code}
      </pre>
    </div>
  )
}
