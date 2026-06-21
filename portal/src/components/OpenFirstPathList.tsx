import { Link } from "@tanstack/react-router"
import { FileText, Route as RouteIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import type { OpenFirstPathItem } from "@/lib/api-client"

type OpenFirstPathListProps = {
  path?: OpenFirstPathItem[]
  toAppRoute: (route: string) => string
  className?: string
  itemClassName?: string
  title?: string
}

function statusClass(status: string) {
  const normalized = status.toLowerCase()
  if (["ready", "ok", "pass"].includes(normalized)) {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
  }
  if (["risk", "blocked", "critical", "fail"].includes(normalized)) {
    return "border-destructive/30 bg-destructive/10 text-destructive"
  }
  return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
}

export function OpenFirstPathList({
  path,
  toAppRoute,
  className,
  itemClassName,
  title = "Open-first path",
}: OpenFirstPathListProps) {
  const items = path?.slice(0, 4) ?? []
  if (!items.length) {
    return null
  }

  return (
    <div className={cn("rounded-lg border border-border bg-background/60 p-3", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <RouteIcon size={14} className="text-primary" />
        <p className="text-xs font-semibold uppercase text-muted-foreground">{title}</p>
        <span className="rounded-md border border-border px-1.5 py-0.5 text-[11px] font-semibold text-muted-foreground">
          {items.length} steps
        </span>
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2">
        {items.map((item) => (
          <Link
            key={`${item.step}-${item.stage}-${item.route}-${item.file}`}
            to={toAppRoute(item.route) as never}
            className={cn(
              "grid min-w-0 grid-cols-[28px_minmax(0,1fr)] gap-2 rounded-md border border-border bg-card p-2 transition hover:bg-accent",
              itemClassName,
            )}
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
              {item.step}
            </span>
            <span className="min-w-0">
              <span className="flex flex-wrap items-center gap-2">
                <span className="break-words text-xs font-semibold text-card-foreground">{item.label}</span>
                <span className={cn("rounded-md border px-1.5 py-0.5 text-[11px] font-semibold", statusClass(item.status))}>
                  {item.status}
                </span>
              </span>
              <span className="mt-1 block break-words text-xs text-muted-foreground">{item.line}</span>
              <span className="mt-1 flex min-w-0 items-center gap-1 text-[11px] text-muted-foreground">
                <FileText size={12} className="shrink-0" />
                <span className="break-all font-mono">{item.file}</span>
              </span>
            </span>
          </Link>
        ))}
      </div>
    </div>
  )
}
