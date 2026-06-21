import { createFileRoute, Outlet, redirect, Link, useLocation } from "@tanstack/react-router"
import { useAuthStore } from "@/stores/auth-store"
import { useUIStore } from "@/stores/ui-store"
import {
  LayoutDashboard,
  Bot,
  Database,
  ShieldCheck,
  Workflow,
  FileDiff,
  Flame,
  Activity,
  AlertTriangle,
  Archive,
  Boxes,
  Briefcase,
  Compass,
  ClipboardCheck,
  DollarSign,
  Landmark,
  LineChart,
  PlayCircle,
  Map,
  Mic2,
  Rocket,
  Network,
  ScrollText,
  TestTube2,
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
  { to: "/launch-room", label: "Launch", icon: Rocket },
  { to: "/killer-demo", label: "Killer Demo", icon: Flame },
  { to: "/board-pack", label: "Board Pack", icon: Landmark },
  { to: "/outcome-ledger", label: "Outcomes", icon: LineChart },
  { to: "/buyer-concierge", label: "Concierge", icon: Compass },
  { to: "/demo-command-center", label: "Demo Center", icon: Mic2 },
  { to: "/enterprise-trust-center", label: "Trust Center", icon: ShieldCheck },
  { to: "/commercial-offer-studio", label: "Offer Studio", icon: DollarSign },
  { to: "/guided-demo", label: "Guided Demo", icon: PlayCircle },
  { to: "/scenario-hub", label: "Scenario Hub", icon: Map },
  { to: "/pilot-launchpad", label: "Pilot Launchpad", icon: Rocket },
  { to: "/", label: "Главная", icon: LayoutDashboard },
  { to: "/configurations", label: "Конфигурации", icon: Database },
  { to: "/quality", label: "Риски", icon: Activity },
  { to: "/change", label: "Изменения", icon: FileDiff },
  { to: "/testing", label: "Тесты", icon: TestTube2 },
  { to: "/release-readiness", label: "Релизы", icon: Rocket },
  { to: "/architecture", label: "Архитектура", icon: Network },
  { to: "/operations", label: "Эксплуатация", icon: AlertTriangle },
  { to: "/lock-radar", label: "Lock Radar", icon: Activity },
  { to: "/extension-safety", label: "Extensions", icon: Workflow },
  { to: "/value-packs", label: "Value Packs", icon: Boxes },
  { to: "/vendor-portfolio", label: "Vendor", icon: Briefcase },
  { to: "/business-case", label: "Business Case", icon: DollarSign },
  { to: "/productization", label: "Productization", icon: Archive },
  { to: "/edt-mcp", label: "AI-штаб", icon: Workflow },
] as const

const safeAutopilotNavItem = { to: "/safe-autopilot", label: "Safe Autopilot", icon: Bot } as const
const approvalsNavItem = { to: "/approvals", label: "Approvals", icon: ClipboardCheck } as const
const auditNavItem = { to: "/audit", label: "Audit Log", icon: ScrollText } as const

const navSections = [
  { label: "Start", items: [navItems[11], navItems[1], navItems[0]] },
  { label: "Deal", items: [navItems[4], navItems[9], navItems[5], navItems[8], navItems[21], navItems[22], navItems[7], navItems[23], navItems[2], navItems[3], navItems[10]] },
  { label: "Engineering", items: [navItems[12], navItems[14], safeAutopilotNavItem, navItems[13], navItems[15], navItems[16], navItems[17], navItems[25]] },
  { label: "Trust & Ops", items: [navItems[6], approvalsNavItem, auditNavItem, navItems[24], navItems[18], navItems[19], navItems[20]] },
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
  const isRouteActive = (to: string) => to === "/"
    ? location.pathname === "/"
    : location.pathname === to || location.pathname.startsWith(`${to}/`)

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
        <nav className="flex-1 space-y-4 overflow-y-auto p-2">
          {navSections.map((section) => (
            <div key={section.label} className="space-y-1">
              {sidebarOpen && (
                <div className="hidden px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-sidebar-foreground/45 sm:block">
                  {section.label}
                </div>
              )}
              {section.items.map((item) => {
                const isActive = isRouteActive(item.to)
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
            </div>
          ))}

          {isAdmin && (
            <>
              <div className="my-2 border-t border-sidebar-border" />
              {adminItems.map((item) => {
                const isActive = isRouteActive(item.to)
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
