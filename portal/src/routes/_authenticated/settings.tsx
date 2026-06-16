import { createFileRoute } from "@tanstack/react-router"
import { Copy, RefreshCw, Sun, Moon, Monitor } from "lucide-react"
import { useAuthStore } from "@/stores/auth-store"
import { useUIStore } from "@/stores/ui-store"
import { cn } from "@/lib/utils"

function SettingsPage() {
  const user = useAuthStore((s) => s.user)
  const theme = useUIStore((s) => s.theme)
  const setTheme = useUIStore((s) => s.setTheme)

  const themeOptions = [
    { value: "light" as const, label: "Light", icon: Sun },
    { value: "dark" as const, label: "Dark", icon: Moon },
    { value: "system" as const, label: "System", icon: Monitor },
  ]

  return (
    <div className="space-y-8 p-6">
      <h1 className="text-3xl font-bold tracking-tight text-foreground">
        Settings
      </h1>

      {/* Profile Section */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Profile</h2>
        <div className="rounded-lg border bg-card p-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                Username
              </p>
              <p className="mt-1 text-foreground">
                {user?.username ?? "—"}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                Email
              </p>
              <p className="mt-1 text-foreground">
                {user?.email ?? "—"}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                Roles
              </p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {user?.roles?.length ? (
                  user.roles.map((role) => (
                    <span
                      key={role}
                      className="inline-flex items-center rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary"
                    >
                      {role}
                    </span>
                  ))
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Appearance Section */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Appearance</h2>
        <div className="rounded-lg border bg-card p-6">
          <p className="mb-4 text-sm text-muted-foreground">
            Choose your preferred theme
          </p>
          <div className="flex gap-3">
            {themeOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setTheme(opt.value)}
                className={cn(
                  "inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition-colors",
                  theme === opt.value
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-background text-foreground hover:bg-muted",
                )}
              >
                <opt.icon className="h-4 w-4" />
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* API Access Section */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">API Access</h2>
        <div className="rounded-lg border bg-card p-6">
          <p className="mb-4 text-sm text-muted-foreground">
            Your API key for programmatic access
          </p>
          <div className="flex items-center gap-3">
            <code className="flex-1 rounded-md border bg-muted px-4 py-2 font-mono text-sm text-foreground">
              ••••••••••abcd
            </code>
            <button className="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted">
              <Copy className="h-4 w-4" />
              Copy
            </button>
            <button className="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted">
              <RefreshCw className="h-4 w-4" />
              Regenerate
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

export const Route = createFileRoute("/_authenticated/settings")({
  component: SettingsPage,
})
