import { useState, useEffect } from "react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard, ListTree, Clock, Users, Server, Bot,
  ShieldCheck, BarChart3, FlaskConical, Settings,
  ChevronLeft, ChevronRight,
} from "lucide-react";

const STORAGE_KEY = "observal:sidebar";

const NAV_GROUPS = [
  {
    label: "Observability",
    items: [
      { to: "/", icon: LayoutDashboard, label: "Dashboard" },
      { to: "/traces", icon: ListTree, label: "Tracing" },
      { to: "/sessions", icon: Clock, label: "Sessions" },
      { to: "/users", icon: Users, label: "Users" },
    ],
  },
  {
    label: "Registry",
    items: [
      { to: "/mcps", icon: Server, label: "MCP Servers" },
      { to: "/agents", icon: Bot, label: "Agents" },
      { to: "/reviews", icon: ShieldCheck, label: "Reviews" },
    ],
  },
  {
    label: "Evaluation",
    items: [
      { to: "/scores", icon: BarChart3, label: "Scores" },
      { to: "/evals", icon: FlaskConical, label: "Evaluations" },
    ],
  },
  {
    label: "Management",
    items: [
      { to: "/settings", icon: Settings, label: "Settings" },
    ],
  },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(STORAGE_KEY) === "true");

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(collapsed));
  }, [collapsed]);

  return (
    <aside
      className="flex flex-col bg-sidebar border-r border-sidebar-border transition-all duration-200"
      style={{ width: collapsed ? "var(--sidebar-width-collapsed)" : "var(--sidebar-width)" }}
    >
      <div className="flex h-12 items-center px-3">
        {!collapsed && <span className="font-semibold text-sm">Observal</span>}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="ml-auto rounded p-1 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-1">
        {NAV_GROUPS.map((group, gi) => (
          <div key={group.label}>
            {!collapsed && (
              <p className={cn(
                "text-[10px] uppercase tracking-widest text-muted-foreground/60 px-3 py-1.5 mt-3",
                gi === 0 && "mt-0"
              )}>
                {group.label}
              </p>
            )}
            {group.items.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                title={collapsed ? label : undefined}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                      : "text-sidebar-foreground hover:bg-sidebar-accent/50",
                    collapsed && "justify-center px-0"
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span>{label}</span>}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border p-2">
        {!collapsed && <p className="text-xs text-muted-foreground">v0.1.0</p>}
      </div>
    </aside>
  );
}
