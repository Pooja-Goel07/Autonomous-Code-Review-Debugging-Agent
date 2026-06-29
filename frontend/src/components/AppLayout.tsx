/**
 * Sidebar layout — persistent nav matching the wireframe.
 * Shows: Repos, Reviews, Analytics links + user info.
 */

import { NavLink, Outlet } from "react-router-dom";
import {
  GitBranch,
  FileText,
  BarChart3,
  LogOut,
  Zap,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const navItems = [
  { to: "/dashboard", label: "Reviews", icon: FileText },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
];

export function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col border-r border-border bg-card">
        {/* Logo */}
        <div className="flex items-center gap-2 border-b border-border px-4 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Zap className="h-4 w-4 text-primary-foreground" />
          </div>
          <span className="text-sm font-semibold text-foreground">
            Code Review Agent
          </span>
        </div>

        {/* Nav links */}
        <nav className="flex-1 space-y-1 px-2 py-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                }`
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* User / Logout */}
        <div className="border-t border-border p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/20 text-xs font-bold text-primary">
                {user?.username?.charAt(0).toUpperCase() ?? "?"}
              </div>
              <div>
                <p className="text-xs font-medium text-foreground">
                  {user?.username ?? "User"}
                </p>
                <p className="text-[10px] text-muted-foreground">
                  {user?.role ?? "developer"}
                </p>
              </div>
            </div>
            <button
              onClick={logout}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              title="Logout"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
