import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  FileText,
  ShoppingCart,
  Package,
  Receipt,
  BarChart3,
  Database,
  Users,
  ChevronDown,
  LogOut,
  Bell,
  Menu,
  X,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import { authApi } from "@/api/auth";

interface NavItem {
  label: string;
  href?: string;
  icon: React.ReactNode;
  children?: { label: string; href: string }[];
  permission?: string;
}

const nav: NavItem[] = [
  { label: "Dashboard", href: "/", icon: <LayoutDashboard className="h-4 w-4" /> },
  {
    label: "Procurement",
    icon: <ShoppingCart className="h-4 w-4" />,
    children: [
      { label: "Requisitions", href: "/procurement/pr" },
      { label: "Purchase Orders", href: "/procurement/po" },
      { label: "Goods Receipts", href: "/procurement/grn" },
    ],
  },
  {
    label: "Inventory",
    icon: <Package className="h-4 w-4" />,
    children: [
      { label: "Stock Overview", href: "/inventory/stock" },
      { label: "Low Stock Alerts", href: "/inventory/alerts" },
      { label: "Movements", href: "/inventory/movements" },
    ],
  },
  { label: "Invoices", href: "/invoices", icon: <Receipt className="h-4 w-4" /> },
  {
    label: "Reports",
    icon: <BarChart3 className="h-4 w-4" />,
    children: [
      { label: "Dashboard KPIs", href: "/reports/dashboard" },
      { label: "PR Summary", href: "/reports/pr" },
      { label: "PO Summary", href: "/reports/po" },
      { label: "Vendor Performance", href: "/reports/vendor" },
      { label: "Invoice Aging", href: "/reports/aging" },
    ],
  },
  {
    label: "Master Data",
    icon: <Database className="h-4 w-4" />,
    children: [
      { label: "Materials", href: "/master/materials" },
      { label: "Vendors", href: "/master/vendors" },
      { label: "Warehouses", href: "/master/warehouses" },
    ],
  },
  { label: "Users", href: "/admin/users", icon: <Users className="h-4 w-4" /> },
];

function NavGroup({ item }: { item: NavItem }) {
  const location = useLocation();
  const isActive = item.children?.some((c) => location.pathname.startsWith(c.href)) ?? false;
  const [open, setOpen] = useState(isActive);

  if (item.href) {
    const active = location.pathname === item.href;
    return (
      <Link
        to={item.href}
        className={cn(
          "flex items-center gap-3 rounded px-3 py-2 text-sm transition-colors",
          active
            ? "bg-white/10 text-white font-medium"
            : "text-white/70 hover:bg-white/8 hover:text-white"
        )}
      >
        {item.icon}
        {item.label}
      </Link>
    );
  }

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "w-full flex items-center justify-between gap-3 rounded px-3 py-2 text-sm transition-colors",
          isActive
            ? "bg-white/10 text-white font-medium"
            : "text-white/70 hover:bg-white/8 hover:text-white"
        )}
      >
        <span className="flex items-center gap-3">
          {item.icon}
          {item.label}
        </span>
        <ChevronDown
          className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
        />
      </button>
      {open && (
        <div className="ml-7 mt-0.5 space-y-0.5 border-l border-white/10 pl-3">
          {item.children?.map((child) => {
            const active = location.pathname.startsWith(child.href);
            return (
              <Link
                key={child.href}
                to={child.href}
                className={cn(
                  "block rounded px-2 py-1.5 text-xs transition-colors",
                  active
                    ? "text-white font-medium"
                    : "text-white/60 hover:text-white"
                )}
              >
                {child.label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } finally {
      logout();
      navigate("/login");
    }
  };

  const Sidebar = (
    <aside className="flex flex-col h-full bg-brand-900 w-60 flex-shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-white/10">
        <div className="h-7 w-7 rounded bg-brand-500 flex items-center justify-center text-white font-bold text-xs">
          EP
        </div>
        <div>
          <div className="text-white font-semibold text-sm leading-tight">EPIMS</div>
          <div className="text-white/40 text-2xs">Procurement System</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-0.5">
        {nav.map((item) => (
          <NavGroup key={item.label} item={item} />
        ))}
      </nav>

      {/* User footer */}
      <div className="border-t border-white/10 p-3">
        <div className="flex items-center gap-2.5 rounded px-2 py-2">
          <div className="h-7 w-7 rounded-full bg-brand-500 flex items-center justify-center text-white text-xs font-semibold flex-shrink-0">
            {user?.full_name?.[0] ?? "?"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-white text-xs font-medium truncate">{user?.full_name}</div>
            <div className="text-white/50 text-2xs truncate">{user?.roles?.[0] ?? "user"}</div>
          </div>
          <button
            onClick={handleLogout}
            className="text-white/50 hover:text-white transition-colors"
            title="Sign out"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      {/* Desktop sidebar */}
      <div className="hidden md:flex">{Sidebar}</div>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div className="flex">{Sidebar}</div>
          <div
            className="flex-1 bg-black/40"
            onClick={() => setMobileOpen(false)}
          />
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="h-12 flex items-center justify-between px-4 border-b border-surface-border bg-white flex-shrink-0">
          <button
            className="md:hidden text-ink-muted"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex-1" />
          <div className="flex items-center gap-2">
            <button className="relative h-8 w-8 flex items-center justify-center rounded hover:bg-surface-hover text-ink-muted">
              <Bell className="h-4 w-4" />
              {/* Notification dot */}
              <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-red-500" />
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
