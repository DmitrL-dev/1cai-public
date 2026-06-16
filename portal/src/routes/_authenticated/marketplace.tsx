import { useState, useMemo } from "react"
import { createFileRoute } from "@tanstack/react-router"
import { Search, Star, Download, Package, Sparkles, Shield } from "lucide-react"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_authenticated/marketplace")({
  component: MarketplacePage,
})

/* ── Mock Data ────────────────────────────────────────────── */

interface Plugin {
  id: string
  name: string
  author: string
  description: string
  stars: number
  installs: string
  category: string
  icon: React.ReactNode
}

const MOCK_PLUGINS: Plugin[] = [
  {
    id: "1",
    name: "BSL Linter Pro",
    author: "1cDev Tools",
    description: "Advanced linting and static analysis for BSL/1C:Enterprise code with customizable rules.",
    stars: 5,
    installs: "3.4k",
    category: "Code Quality",
    icon: <Shield className="size-5 text-blue-500" />,
  },
  {
    id: "2",
    name: "Git Flow Manager",
    author: "DevOps Hub",
    description: "Streamline your Git workflow with automated branching, merging, and release management.",
    stars: 4,
    installs: "2.1k",
    category: "DevOps",
    icon: <Package className="size-5 text-orange-500" />,
  },
  {
    id: "3",
    name: "AI Code Reviewer",
    author: "SmartCode AI",
    description: "Automated code reviews powered by AI. Get suggestions and improvements in real-time.",
    stars: 5,
    installs: "5.7k",
    category: "AI & ML",
    icon: <Sparkles className="size-5 text-purple-500" />,
  },
  {
    id: "4",
    name: "REST API Builder",
    author: "APIForge",
    description: "Visual REST API designer with automatic OpenAPI spec generation and mock server.",
    stars: 4,
    installs: "1.2k",
    category: "API",
    icon: <Package className="size-5 text-green-500" />,
  },
  {
    id: "5",
    name: "DB Schema Visualizer",
    author: "DataView Labs",
    description: "Interactive database schema visualization with ER diagrams and query builder.",
    stars: 4,
    installs: "1.8k",
    category: "Database",
    icon: <Package className="size-5 text-cyan-500" />,
  },
  {
    id: "6",
    name: "Performance Profiler",
    author: "PerfTools Inc",
    description: "Real-time performance monitoring and profiling for 1C:Enterprise applications.",
    stars: 5,
    installs: "2.9k",
    category: "Code Quality",
    icon: <Shield className="size-5 text-red-500" />,
  },
]

interface FeaturedPlugin {
  id: string
  name: string
  author: string
  description: string
  gradient: string
}

const FEATURED_PLUGINS: FeaturedPlugin[] = [
  {
    id: "f1",
    name: "1C:Enterprise AI Suite",
    author: "1cAI Official",
    description:
      "The ultimate AI toolkit for 1C:Enterprise development. Includes code generation, smart refactoring, automated documentation, and intelligent debugging — all in one package.",
    gradient: "from-blue-600 to-purple-600 dark:from-blue-500 dark:to-purple-500",
  },
  {
    id: "f2",
    name: "DevOps Pipeline Pro",
    author: "CloudForge",
    description:
      "End-to-end CI/CD pipeline management for 1C projects. Automated testing, deployment, and monitoring with built-in rollback and canary release support.",
    gradient: "from-emerald-600 to-teal-600 dark:from-emerald-500 dark:to-teal-500",
  },
]

const CATEGORIES = [
  "All",
  "Code Quality",
  "DevOps",
  "AI & ML",
  "API",
  "Database",
]

/* ── Component ────────────────────────────────────────────── */

function MarketplacePage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedCategory, setSelectedCategory] = useState("All")

  const filteredPlugins = useMemo(() => {
    return MOCK_PLUGINS.filter((plugin) => {
      const matchesSearch =
        !searchQuery ||
        plugin.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        plugin.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        plugin.author.toLowerCase().includes(searchQuery.toLowerCase())

      const matchesCategory =
        selectedCategory === "All" || plugin.category === selectedCategory

      return matchesSearch && matchesCategory
    })
  }, [searchQuery, selectedCategory])

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Marketplace
        </h1>
        <p className="mt-1 text-muted-foreground">
          Browse plugins and extensions
        </p>
      </div>

      {/* Search & Filter */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search plugins..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-border bg-background py-2 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <select
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          className="rounded-lg border border-border bg-background px-4 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {CATEGORIES.map((cat) => (
            <option key={cat} value={cat}>
              {cat}
            </option>
          ))}
        </select>
      </div>

      {/* Plugin Grid */}
      {filteredPlugins.length === 0 ? (
        <div className="py-12 text-center">
          <Package className="mx-auto size-12 text-muted-foreground/50" />
          <p className="mt-3 text-sm text-muted-foreground">
            No plugins found matching your criteria.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredPlugins.map((plugin) => (
            <PluginCard key={plugin.id} plugin={plugin} />
          ))}
        </div>
      )}

      {/* Featured Section */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-foreground">Featured</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {FEATURED_PLUGINS.map((plugin) => (
            <FeaturedCard key={plugin.id} plugin={plugin} />
          ))}
        </div>
      </div>
    </div>
  )
}

/* ── Plugin Card ──────────────────────────────────────────── */

function PluginCard({ plugin }: { plugin: Plugin }) {
  const [installed, setInstalled] = useState(false)

  return (
    <div className="flex flex-col rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-border bg-muted/50">
          {plugin.icon}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-foreground">
            {plugin.name}
          </h3>
          <p className="text-xs text-muted-foreground">{plugin.author}</p>
        </div>
      </div>

      <p className="mb-4 line-clamp-2 flex-1 text-sm text-muted-foreground">
        {plugin.description}
      </p>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Stars */}
          <div className="flex items-center gap-1">
            {Array.from({ length: 5 }).map((_, i) => (
              <Star
                key={i}
                className={cn(
                  "size-3.5",
                  i < plugin.stars
                    ? "fill-yellow-400 text-yellow-400"
                    : "text-muted-foreground/30",
                )}
              />
            ))}
          </div>

          {/* Install count */}
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Download className="size-3" />
            {plugin.installs}
          </span>
        </div>

        <button
          onClick={() => setInstalled((v) => !v)}
          className={cn(
            "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
            installed
              ? "border border-border bg-muted text-muted-foreground"
              : "bg-primary text-primary-foreground hover:bg-primary/90",
          )}
        >
          {installed ? "Installed" : "Install"}
        </button>
      </div>
    </div>
  )
}

/* ── Featured Card ────────────────────────────────────────── */

function FeaturedCard({ plugin }: { plugin: FeaturedPlugin }) {
  const [installed, setInstalled] = useState(false)

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-lg bg-gradient-to-br p-6 text-white",
        plugin.gradient,
      )}
    >
      {/* Background decoration */}
      <div className="pointer-events-none absolute -right-6 -top-6 size-32 rounded-full bg-white/10" />
      <div className="pointer-events-none absolute -bottom-4 -left-4 size-24 rounded-full bg-white/10" />

      <div className="relative space-y-3">
        <div>
          <span className="mb-2 inline-block rounded-full bg-white/20 px-2.5 py-0.5 text-xs font-medium">
            Featured
          </span>
          <h3 className="text-lg font-bold">{plugin.name}</h3>
          <p className="text-sm text-white/80">by {plugin.author}</p>
        </div>

        <p className="text-sm leading-relaxed text-white/90">
          {plugin.description}
        </p>

        <button
          onClick={() => setInstalled((v) => !v)}
          className={cn(
            "rounded-md px-4 py-2 text-sm font-medium transition-colors",
            installed
              ? "bg-white/20 text-white"
              : "bg-white text-gray-900 hover:bg-white/90",
          )}
        >
          {installed ? "Installed" : "Install"}
        </button>
      </div>
    </div>
  )
}
