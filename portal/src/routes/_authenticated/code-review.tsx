import { createFileRoute } from "@tanstack/react-router"
import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { codeReviewApi } from "@/lib/api-client"
import { cn } from "@/lib/utils"
import {
  Play,
  Loader2,
  AlertCircle,
  AlertTriangle,
  Info,
  Wand2,
  FileCode,
  Sparkles,
  SearchCode,
} from "lucide-react"

export const Route = createFileRoute("/_authenticated/code-review")({
  component: CodeReviewPage,
})

/* ── Constants ─────────────────────────────────────────────── */

const DEFAULT_CODE = `Процедура ОбработкаПроведения(Отказ, РежимПроведения)
    Для Каждого СтрокаТабличнойЧасти Из ТабличнаяЧасть Цикл
        Если СтрокаТабличнойЧасти.Количество < 0 Тогда
            Сообщить("Отрицательное количество!");
        КонецЕсли;
    КонецЦикла;
КонецПроцедуры`

interface Suggestion {
  id: string
  severity: "error" | "warning" | "info"
  message: string
  line?: number
}

interface AnalysisResult {
  suggestions: Suggestion[]
}

const severityConfig = {
  error: {
    icon: AlertCircle,
    badge: "bg-red-500/10 text-red-600 dark:text-red-400 ring-red-500/20",
    bar: "bg-red-500",
    label: "Error",
  },
  warning: {
    icon: AlertTriangle,
    badge: "bg-amber-500/10 text-amber-600 dark:text-amber-400 ring-amber-500/20",
    bar: "bg-amber-500",
    label: "Warning",
  },
  info: {
    icon: Info,
    badge: "bg-blue-500/10 text-blue-600 dark:text-blue-400 ring-blue-500/20",
    bar: "bg-blue-500",
    label: "Info",
  },
} as const

/* ── Component ─────────────────────────────────────────────── */

function CodeReviewPage() {
  const [code, setCode] = useState(DEFAULT_CODE)

  const analyzeMutation = useMutation({
    mutationFn: async (sourceCode: string) => {
      const response = await codeReviewApi.analyze(sourceCode)
      return response.data as AnalysisResult
    },
  })

  const autoFixMutation = useMutation({
    mutationFn: async (suggestionId: string) => {
      const response = await codeReviewApi.autoFix(code, suggestionId)
      return response.data as { fixed_code: string }
    },
    onSuccess: (data) => {
      if (data.fixed_code) {
        setCode(data.fixed_code)
      }
    },
  })

  const suggestions = analyzeMutation.data?.suggestions ?? []
  const errorCount = suggestions.filter((s) => s.severity === "error").length
  const warningCount = suggestions.filter((s) => s.severity === "warning").length
  const infoCount = suggestions.filter((s) => s.severity === "info").length

  return (
    <div className="flex h-full flex-col">
      {/* ── Header ────────────────────────────────────── */}
      <div className="shrink-0 border-b border-border px-6 py-5 lg:px-8">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2">
              <SearchCode size={20} className="text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground">
                Code Review
              </h1>
              <p className="text-sm text-muted-foreground">
                Paste BSL code for AI-powered analysis
              </p>
            </div>
          </div>

          {/* Summary pills (shown after analysis) */}
          {analyzeMutation.isSuccess && suggestions.length > 0 && (
            <div className="flex items-center gap-2">
              {errorCount > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-600 ring-1 ring-inset ring-red-500/20 dark:text-red-400">
                  <AlertCircle size={12} />
                  {errorCount} {errorCount === 1 ? "error" : "errors"}
                </span>
              )}
              {warningCount > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-600 ring-1 ring-inset ring-amber-500/20 dark:text-amber-400">
                  <AlertTriangle size={12} />
                  {warningCount}
                </span>
              )}
              {infoCount > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 px-2.5 py-1 text-xs font-medium text-blue-600 ring-1 ring-inset ring-blue-500/20 dark:text-blue-400">
                  <Info size={12} />
                  {infoCount}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Split Panel ───────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden lg:flex-row">
        {/* Left: Code Input (60%) */}
        <div className="flex flex-col border-b border-border lg:w-[60%] lg:border-b-0 lg:border-r">
          {/* Editor toolbar */}
          <div className="flex items-center justify-between border-b border-border bg-muted/30 px-4 py-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <FileCode size={14} />
              <span className="font-medium">source.bsl</span>
              <span className="text-xs opacity-60">
                {code.split("\n").length} lines
              </span>
            </div>
            <button
              onClick={() => analyzeMutation.mutate(code)}
              disabled={analyzeMutation.isPending || !code.trim()}
              className={cn(
                "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold",
                "transition-all duration-200 active:scale-[0.97]",
                "bg-primary text-primary-foreground shadow-sm",
                "hover:opacity-90",
                "disabled:pointer-events-none disabled:opacity-50",
              )}
            >
              {analyzeMutation.isPending ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Play size={15} />
                  Analyze
                </>
              )}
            </button>
          </div>

          {/* Textarea */}
          <div className="relative flex-1 min-h-0">
            <textarea
              value={code}
              onChange={(e) => setCode(e.target.value)}
              spellCheck={false}
              className={cn(
                "h-full w-full resize-none p-5",
                "bg-zinc-950 text-zinc-100 caret-zinc-100",
                "font-mono text-sm leading-relaxed",
                "placeholder:text-zinc-600",
                "outline-none",
                "min-h-[400px]",
              )}
              placeholder="Paste your BSL code here..."
            />
            {/* Line numbers gutter effect */}
            <div className="pointer-events-none absolute inset-y-0 left-0 w-12 bg-gradient-to-r from-zinc-900/80 to-transparent" />
          </div>

          {/* Error banner */}
          {analyzeMutation.isError && (
            <div className="flex items-center gap-2 border-t border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
              <AlertCircle size={15} />
              <span>
                Analysis failed.{" "}
                {analyzeMutation.error instanceof Error
                  ? analyzeMutation.error.message
                  : "Please try again."}
              </span>
            </div>
          )}
        </div>

        {/* Right: Results (40%) */}
        <div className="flex flex-1 flex-col overflow-hidden lg:w-[40%]">
          <div className="flex items-center gap-2 border-b border-border bg-muted/30 px-4 py-2">
            <Sparkles size={14} className="text-muted-foreground" />
            <span className="text-sm font-medium text-muted-foreground">
              Analysis Results
            </span>
            {analyzeMutation.isSuccess && (
              <span className="ml-auto text-xs tabular-nums text-muted-foreground">
                {suggestions.length}{" "}
                {suggestions.length === 1 ? "suggestion" : "suggestions"}
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto">
            {/* Pending state */}
            {analyzeMutation.isPending && (
              <div className="flex flex-col items-center justify-center gap-4 p-12 text-center">
                <div className="relative">
                  <div className="absolute inset-0 animate-ping rounded-full bg-primary/20" />
                  <div className="relative rounded-full bg-primary/10 p-4">
                    <Loader2
                      size={24}
                      className="animate-spin text-primary"
                    />
                  </div>
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">
                    Analyzing code...
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    AI is reviewing your BSL for issues and improvements
                  </p>
                </div>
              </div>
            )}

            {/* Empty state */}
            {!analyzeMutation.isPending &&
              !analyzeMutation.isSuccess &&
              !analyzeMutation.isError && (
                <div className="flex flex-col items-center justify-center gap-3 p-12 text-center">
                  <div className="rounded-full bg-muted p-4">
                    <SearchCode size={24} className="text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      No results yet
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground/70">
                      Click <strong>Analyze</strong> to start the AI code review
                    </p>
                  </div>
                </div>
              )}

            {/* Success: no issues */}
            {analyzeMutation.isSuccess && suggestions.length === 0 && (
              <div className="flex flex-col items-center justify-center gap-3 p-12 text-center">
                <div className="rounded-full bg-emerald-500/10 p-4">
                  <Sparkles size={24} className="text-emerald-500" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">
                    Looks great!
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    No issues found in your code
                  </p>
                </div>
              </div>
            )}

            {/* Suggestion cards */}
            {analyzeMutation.isSuccess && suggestions.length > 0 && (
              <div className="divide-y divide-border">
                {suggestions.map((suggestion) => {
                  const config = severityConfig[suggestion.severity]
                  const SeverityIcon = config.icon

                  return (
                    <div
                      key={suggestion.id}
                      className="group relative transition-colors hover:bg-muted/30"
                    >
                      {/* Severity bar */}
                      <div
                        className={cn(
                          "absolute inset-y-0 left-0 w-0.5",
                          config.bar,
                        )}
                      />

                      <div className="px-4 py-4 pl-5">
                        <div className="flex items-start gap-3">
                          <span
                            className={cn(
                              "mt-0.5 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
                              config.badge,
                            )}
                          >
                            <SeverityIcon size={11} />
                            {config.label}
                          </span>

                          {suggestion.line != null && (
                            <span className="mt-0.5 rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                              L{suggestion.line}
                            </span>
                          )}
                        </div>

                        <p className="mt-2.5 text-sm leading-relaxed text-card-foreground">
                          {suggestion.message}
                        </p>

                        <div className="mt-3">
                          <button
                            onClick={() =>
                              autoFixMutation.mutate(suggestion.id)
                            }
                            disabled={
                              autoFixMutation.isPending &&
                              autoFixMutation.variables === suggestion.id
                            }
                            className={cn(
                              "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium",
                              "border border-border bg-card text-card-foreground",
                              "transition-all duration-150",
                              "hover:border-primary/30 hover:bg-accent",
                              "active:scale-[0.97]",
                              "disabled:pointer-events-none disabled:opacity-50",
                            )}
                          >
                            {autoFixMutation.isPending &&
                            autoFixMutation.variables === suggestion.id ? (
                              <>
                                <Loader2 size={12} className="animate-spin" />
                                Fixing...
                              </>
                            ) : (
                              <>
                                <Wand2 size={12} />
                                Auto Fix
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
