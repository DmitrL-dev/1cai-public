import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { Search, ArrowRight } from "lucide-react"
import { cn } from "@/lib/utils"

interface WikiArticle {
  id: string
  title: string
  description: string
  tags: { label: string; color: string }[]
  lastUpdated: string
}

const mockArticles: WikiArticle[] = [
  {
    id: "1",
    title: "Getting Started with 1C BSL",
    description: "Basics of BSL development — language fundamentals, IDE setup, and your first module.",
    tags: [
      { label: "BSL", color: "bg-blue-500/15 text-blue-500" },
      { label: "Beginner", color: "bg-green-500/15 text-green-500" },
    ],
    lastUpdated: "2026-02-20",
  },
  {
    id: "2",
    title: "Code Review Best Practices",
    description: "Standards for 1C code reviews — checklists, common pitfalls, and approval workflows.",
    tags: [
      { label: "Code Review", color: "bg-purple-500/15 text-purple-500" },
      { label: "Standards", color: "bg-orange-500/15 text-orange-500" },
      { label: "Quality", color: "bg-teal-500/15 text-teal-500" },
    ],
    lastUpdated: "2026-02-18",
  },
  {
    id: "3",
    title: "Performance Optimization",
    description: "Tips for optimizing 1C queries — indexing strategies, batch processing, and profiling tools.",
    tags: [
      { label: "Performance", color: "bg-red-500/15 text-red-500" },
      { label: "Queries", color: "bg-blue-500/15 text-blue-500" },
    ],
    lastUpdated: "2026-02-15",
  },
  {
    id: "4",
    title: "Testing Strategies",
    description: "Unit and integration testing for 1C — frameworks, mocking data, and CI integration.",
    tags: [
      { label: "Testing", color: "bg-yellow-500/15 text-yellow-500" },
      { label: "CI/CD", color: "bg-indigo-500/15 text-indigo-500" },
      { label: "Quality", color: "bg-teal-500/15 text-teal-500" },
    ],
    lastUpdated: "2026-02-12",
  },
  {
    id: "5",
    title: "Deployment Guide",
    description: "CI/CD for 1C configurations — automated builds, environment management, and rollback procedures.",
    tags: [
      { label: "DevOps", color: "bg-orange-500/15 text-orange-500" },
      { label: "CI/CD", color: "bg-indigo-500/15 text-indigo-500" },
    ],
    lastUpdated: "2026-02-10",
  },
]

function WikiPage() {
  const [search, setSearch] = useState("")

  const filteredArticles = mockArticles.filter(
    (a) =>
      a.title.toLowerCase().includes(search.toLowerCase()) ||
      a.description.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <div className="space-y-8 p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Knowledge Base
        </h1>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search articles..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 w-full rounded-md border border-border bg-background pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      <div className="space-y-4">
        {filteredArticles.map((article) => (
          <div
            key={article.id}
            className="flex flex-col gap-3 rounded-lg border bg-card p-6 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0 flex-1 space-y-2">
              <h3 className="text-lg font-semibold text-foreground">
                {article.title}
              </h3>
              <p className="text-sm text-muted-foreground">
                {article.description}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                {article.tags.map((tag) => (
                  <span
                    key={tag.label}
                    className={cn(
                      "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                      tag.color,
                    )}
                  >
                    {tag.label}
                  </span>
                ))}
                <span className="text-xs text-muted-foreground">
                  Updated {article.lastUpdated}
                </span>
              </div>
            </div>
            <button className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
              Read
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        ))}

        {filteredArticles.length === 0 && (
          <div className="rounded-lg border bg-card py-12 text-center">
            <p className="text-muted-foreground">
              No articles match your search.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export const Route = createFileRoute("/_authenticated/wiki")({
  component: WikiPage,
})
