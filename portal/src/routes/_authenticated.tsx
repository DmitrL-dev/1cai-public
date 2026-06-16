import { createFileRoute, Outlet, redirect, Link, useLocation } from "@tanstack/react-router"
import { useAuthStore } from "@/stores/auth-store"
import { useUIStore } from "@/stores/ui-store"
import {
  LayoutDashboard,
  Code,
  Code2,
  Compass,
  Database,
  ClipboardList,
  Sparkles,
  Store,
  ShieldCheck,
  ShieldAlert,
  Workflow,
  BookOpen,
  GitBranch,
  FileDiff,
  Activity,
  AlertTriangle,
  Rocket,
  Network,
  LockKeyhole,
  TestTube2,
  Users,
  Settings,
  LogOut,
  Sun,
  Moon,
  Monitor,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_authenticated")({
  beforeLoad: () => {
    if (!useAuthStore.getState().isAuthenticated) {
      throw redirect({ to: "/login" })
    }
  },
  component: AuthenticatedLayout,
})

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/workbench", label: "Workbench", icon: Workflow },
  { to: "/code-review", label: "Code Review", icon: Code2 },
  { to: "/standards-review", label: "Standards", icon: ShieldAlert },
  { to: "/security", label: "Security", icon: ShieldCheck },
  { to: "/copilot", label: "Copilot", icon: Sparkles },
  { to: "/copilot-coverage", label: "Copilot Map", icon: Compass },
  { to: "/edt-mcp", label: "EDT MCP", icon: Workflow },
  { to: "/team-governance", label: "Governance", icon: Users },
  { to: "/requirements", label: "Requirements", icon: ClipboardList },
  { to: "/metadata", label: "Metadata", icon: Database },
  { to: "/forms", label: "Forms", icon: ClipboardList },
  { to: "/marketplace", label: "Marketplace", icon: Store },
  { to: "/bpmn", label: "BPMN", icon: Workflow },
  { to: "/wiki", label: "Wiki", icon: BookOpen },
  { to: "/quality", label: "Рентген качества", icon: Activity },
  { to: "/change", label: "Change Impact", icon: FileDiff },
  { to: "/testing", label: "Testing", icon: TestTube2 },
  { to: "/release-readiness", label: "Release", icon: Rocket },
  { to: "/operations", label: "Operations", icon: AlertTriangle },
  { to: "/architecture", label: "Architecture", icon: Network },
  { to: "/rentgen", label: "Рентген", icon: GitBranch },
  { to: "/offline-readiness", label: "Offline", icon: LockKeyhole },
  { to: "/ide", label: "IDE", icon: Code },
] as const

const adminItems = [
  { to: "/admin", label: "Admin", icon: ShieldCheck },
] as const

function AuthenticatedLayout() {
  const { sidebarOpen, toggleSidebar, theme, setTheme } = useUIStore()
  const { user, logout } = useAuthStore()
  const location = useLocation()
  const isAdmin = user?.roles?.includes("admin")

  const themeIcons = { light: Sun, dark: Moon, system: Monitor }
  const nextTheme = { light: "dark", dark: "system", system: "light" } as const
  const ThemeIcon = themeIcons[theme]

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside
        className={cn(
          "flex flex-col border-r border-sidebar-border bg-sidebar transition-all duration-200",
          sidebarOpen ? "w-14 sm:w-56" : "w-14",
        )}
      >
        {/* Logo */}
        <div className="flex h-14 items-center border-b border-sidebar-border px-3">
          {sidebarOpen && (
            <span className="hidden text-lg font-bold text-sidebar-foreground sm:inline">1cAI</span>
          )}
          <button
            onClick={toggleSidebar}
            className={cn(
              "rounded-md p-1.5 text-sidebar-foreground hover:bg-sidebar-accent",
              sidebarOpen ? "mx-auto sm:ml-auto sm:mr-0" : "mx-auto",
            )}
          >
            {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-1 p-2">
          {navItems.map((item) => {
            const isActive = item.to === "/"
              ? location.pathname === "/"
              : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`)
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/50",
                  !sidebarOpen && "justify-center px-0",
                )}
                title={!sidebarOpen ? item.label : undefined}
              >
                <item.icon size={18} />
                {sidebarOpen && <span className="hidden sm:inline">{item.label}</span>}
              </Link>
            )
          })}

          {isAdmin && (
            <>
              <div className="my-2 border-t border-sidebar-border" />
              {adminItems.map((item) => {
                const isActive = location.pathname.startsWith(item.to)
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                        : "text-sidebar-foreground hover:bg-sidebar-accent/50",
                      !sidebarOpen && "justify-center px-0",
                    )}
                    title={!sidebarOpen ? item.label : undefined}
                  >
                    <item.icon size={18} />
                      {sidebarOpen && <span className="hidden sm:inline">{item.label}</span>}
                    </Link>
                )
              })}
            </>
          )}
        </nav>

        {/* Bottom */}
        <div className="border-t border-sidebar-border p-2 space-y-1">
          <Link
            to="/settings"
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent/50 transition-colors",
              location.pathname === "/settings" && "bg-sidebar-accent text-sidebar-accent-foreground",
              !sidebarOpen && "justify-center px-0",
            )}
            title={!sidebarOpen ? "Settings" : undefined}
          >
            <Settings size={18} />
            {sidebarOpen && <span className="hidden sm:inline">Settings</span>}
          </Link>

          <button
            onClick={() => setTheme(nextTheme[theme])}
            className={cn(
              "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent/50 transition-colors",
              !sidebarOpen && "justify-center px-0",
            )}
            title={!sidebarOpen ? `Theme: ${theme}` : undefined}
          >
            <ThemeIcon size={18} />
            {sidebarOpen && <span className="hidden capitalize sm:inline">{theme}</span>}
          </button>

          <button
            onClick={() => { logout(); window.location.href = "/login" }}
            className={cn(
              "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-destructive hover:bg-destructive/10 transition-colors",
              !sidebarOpen && "justify-center px-0",
            )}
            title={!sidebarOpen ? "Logout" : undefined}
          >
            <LogOut size={18} />
            {sidebarOpen && <span className="hidden sm:inline">Logout</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="min-w-0 flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
