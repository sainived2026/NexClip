"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    Play, LayoutDashboard, FolderOpen, Upload, Settings,
    Shield, LogOut, ChevronLeft, Menu, Brain, Cpu, Bell, X, Terminal
} from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const NEX_AGENT_URL = process.env.NEXT_PUBLIC_NEX_AGENT_URL || "http://localhost:8001";

/* ── Nav items split by access level ─────────────────────────── */
const publicNavItems = [
    { icon: LayoutDashboard, label: "Dashboard", href: "/dashboard" },
    { icon: FolderOpen, label: "Projects", href: "/dashboard/projects" },
    { icon: Upload, label: "Upload", href: "/dashboard/upload" },
    { icon: Settings, label: "Settings", href: "/dashboard/settings" },
];

const adminNavItems = [
    { icon: Brain, label: "Nex Agent", href: "/dashboard/nex" },
    { icon: Cpu, label: "Nexearch", href: "/dashboard/nexearch" },
    { icon: Terminal, label: "Agent Monitor", href: "/dashboard/agent-monitor" },
    { icon: Shield, label: "Admin", href: "/dashboard/admin" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();
    const [collapsed, setCollapsed] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);
    const [user, setUser] = useState<any>(null);
    const [isAdmin, setIsAdmin] = useState(true);
    const [accessResolved, setAccessResolved] = useState(false);
    const [unreadNotifCount, setUnreadNotifCount] = useState(0);
    const [toasts, setToasts] = useState<any[]>([]);
    const lastNotifIdsRef = useRef<Set<string>>(new Set());

    useEffect(() => {
        let cancelled = false;
        const userData = localStorage.getItem("nexclip_user");
        if (userData) {
            try { setUser(JSON.parse(userData)); } catch { }
        }

        const hydrateAccess = async () => {
            try {
                const token = localStorage.getItem("nexclip_token") || "";
                const authHeaders: HeadersInit = token
                    ? { "Authorization": `Bearer ${token}` }
                    : {};

                const [meResult, adminResult] = await Promise.allSettled([
                    fetch(`${BACKEND_URL}/api/auth/me`, { headers: authHeaders }).then(res => res.json()),
                    fetch(`${BACKEND_URL}/api/auth/admin-check`, { headers: authHeaders }).then((r) => r.json()),
                ]);

                if (cancelled) return;

                if (meResult.status === "fulfilled" && meResult.value?.id) {
                    setUser(meResult.value);
                    localStorage.setItem("nexclip_user", JSON.stringify(meResult.value));
                }

                if (adminResult.status === "fulfilled" && adminResult.value?.is_admin) {
                    setIsAdmin(true);
                }
            } finally {
                if (!cancelled) {
                    setAccessResolved(true);
                }
            }
        };

        hydrateAccess();

        return () => {
            cancelled = true;
        };
    }, []);

    /* ── Notification polling ─────────────────────────────────── */
    const pollNotifications = useCallback(async () => {
        try {
            const res = await fetch(`${NEX_AGENT_URL}/api/nex/notifications?unread_only=true`);
            if (!res.ok) return;
            const data = await res.json();
            const notifs = data.notifications || [];
            setUnreadNotifCount(notifs.length);

            // Show toast for NEW notifications only
            for (const n of notifs) {
                if (!lastNotifIdsRef.current.has(n.id)) {
                    lastNotifIdsRef.current.add(n.id);
                    setToasts(prev => [...prev, { ...n, toastId: Date.now() + Math.random() }]);
                    // Auto-dismiss after 8s
                    setTimeout(() => {
                        setToasts(prev => prev.filter(t => t.id !== n.id));
                    }, 8000);
                }
            }
        } catch { /* Nex Agent might not be running */ }
    }, []);

    useEffect(() => {
        pollNotifications();
        const interval = setInterval(pollNotifications, 10000);
        return () => clearInterval(interval);
    }, [pollNotifications]);

    /* Auto-mark notifications as read when user opens Nex Agent tab */
    useEffect(() => {
        if (pathname.startsWith("/dashboard/nex") && !pathname.startsWith("/dashboard/nexearch") && unreadNotifCount > 0) {
            fetch(`${NEX_AGENT_URL}/api/nex/notifications/read-all`, { method: "PATCH" })
                .then(res => {
                    if (res.ok) {
                        setUnreadNotifCount(0);
                    }
                })
                .catch(() => {});
        }
    }, [pathname, unreadNotifCount]);

    const dismissToast = (toastId: number) => {
        setToasts(prev => prev.filter(t => t.toastId !== toastId));
    };

    const markNotifRead = async (notifId: string) => {
        try {
            await fetch(`${NEX_AGENT_URL}/api/nex/notifications/${notifId}/read`, { method: "PATCH" });
            setUnreadNotifCount(prev => Math.max(0, prev - 1));
        } catch { }
    };

    /* Redirect non-admin users away from protected pages */
    useEffect(() => {
        const protectedPrefixes = ["/dashboard/nex", "/dashboard/nexearch", "/dashboard/admin"];
        const isProtected = protectedPrefixes.some((p) => pathname.startsWith(p));
        if (!accessResolved) return;
        if (isProtected && !isAdmin && user) {
            router.push("/dashboard");
        }
    }, [pathname, isAdmin, user, router, accessResolved]);

    const handleLogout = () => {
        localStorage.removeItem("nexclip_token");
        localStorage.removeItem("nexclip_user");
        router.push("/dashboard");
    };

    /* Combine nav items based on admin status */
    const navItems = isAdmin ? [...publicNavItems, ...adminNavItems] : publicNavItems;

    return (
        <div className="min-h-screen bg-[var(--nc-bg)] flex">
            {/* ── Sidebar ──────────────────────────────────────────── */}
            <aside
                className={`
          fixed md:sticky top-0 z-40 h-screen flex flex-col shrink-0
          border-r border-[var(--nc-border)] bg-[var(--nc-bg-card)]
          transition-all duration-300 ease-in-out
          ${collapsed ? "w-[68px]" : "w-[240px]"}
          ${mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
        `}
            >
                {/* Logo */}
                <div className="h-16 flex items-center justify-between px-4 border-b border-[var(--nc-border)]">
                    <Link href="/dashboard" className="flex items-center gap-2.5 overflow-hidden">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shrink-0">
                            <Play className="w-4 h-4 text-white fill-white" />
                        </div>
                        {!collapsed && <span className="text-base font-bold text-white whitespace-nowrap">NexClip</span>}
                    </Link>
                    <button
                        onClick={() => setCollapsed(!collapsed)}
                        className="hidden md:flex w-6 h-6 items-center justify-center rounded hover:bg-[var(--nc-bg-elevated)] transition-colors"
                    >
                        <ChevronLeft className={`w-4 h-4 text-[var(--nc-text-dim)] transition-transform ${collapsed ? "rotate-180" : ""}`} />
                    </button>
                </div>

                {/* Navigation */}
                <nav className="flex-1 py-4 px-3 space-y-1">
                    {navItems.map((item, idx) => {
                        const isActive = pathname === item.href;
                        /* Add separator before admin items */
                        const isFirstAdmin = isAdmin && item === adminNavItems[0];
                        return (
                            <div key={item.href}>
                                {isFirstAdmin && (
                                    <div className="my-3 mx-2 border-t border-[var(--nc-border)] opacity-50" />
                                )}
                                <Link
                                    href={item.href}
                                    onClick={() => setMobileOpen(false)}
                                    className={`
                      flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all
                      ${isActive
                                            ? "bg-gradient-to-r from-indigo-500/10 to-purple-500/10 text-white border border-indigo-500/20"
                                            : "text-[var(--nc-text-muted)] hover:text-white hover:bg-[var(--nc-bg-elevated)]"
                                        }
                    `}
                                >
                                    <item.icon className={`w-4.5 h-4.5 shrink-0 ${isActive ? "text-indigo-400" : ""}`} />
                                    {!collapsed && <span className="whitespace-nowrap">{item.label}</span>}
                                    {/* Notification badge on Nex Agent */}
                                    {item.label === "Nex Agent" && unreadNotifCount > 0 && (
                                        <span className="ml-auto flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-gradient-to-r from-red-500 to-pink-500 text-white text-[10px] font-bold animate-pulse shadow-lg shadow-red-500/30">
                                            {unreadNotifCount}
                                        </span>
                                    )}
                                </Link>
                            </div>
                        );
                    })}
                </nav>

                {/* User */}
                <div className="p-3 border-t border-[var(--nc-border)]">
                    {!collapsed && user && (
                        <div className="px-3 py-2 mb-2">
                            <div className="text-sm font-medium text-white truncate">{user.full_name || user.username}</div>
                            <div className="text-xs text-[var(--nc-text-dim)] truncate">{user.email}</div>
                        </div>
                    )}
                    <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-[var(--nc-text-muted)] hover:text-red-400 hover:bg-red-500/5 transition-all"
                    >
                        <LogOut className="w-4.5 h-4.5 shrink-0" />
                        {!collapsed && <span>Logout</span>}
                    </button>
                </div>
            </aside>

            {/* ── Mobile overlay ───────────────────────────────────── */}
            {mobileOpen && (
                <div
                    className="fixed inset-0 z-30 bg-black/50 md:hidden"
                    onClick={() => setMobileOpen(false)}
                />
            )}

            {/* ── Main content ─────────────────────────────────────── */}
            <main className="flex-1 min-h-screen">
                {/* Top bar — hidden on agent/intel pages */}
                {!pathname.startsWith("/dashboard/nex") && !pathname.startsWith("/dashboard/nexearch") && !pathname.startsWith("/dashboard/admin") && (
                <header className="h-16 flex items-center justify-between px-6 border-b border-[var(--nc-border)] bg-[var(--nc-bg-card)]/50 backdrop-blur-xl sticky top-0 z-20">
                    <button
                        onClick={() => setMobileOpen(true)}
                        className="md:hidden w-8 h-8 flex items-center justify-center rounded-lg hover:bg-[var(--nc-bg-elevated)] transition-colors"
                    >
                        <Menu className="w-5 h-5 text-[var(--nc-text-muted)]" />
                    </button>
                    <div />
                    <div className="flex items-center gap-3">
                        <Link
                            href="/dashboard/upload"
                            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 text-white text-sm font-medium transition-all"
                        >
                            <Upload className="w-4 h-4" />
                            New Clip
                        </Link>
                    </div>
                </header>
                )}

                {/* Page content */}
                <div className={pathname.startsWith("/dashboard/nex") || pathname.startsWith("/dashboard/nexearch") || pathname.startsWith("/dashboard/admin") || pathname.startsWith("/dashboard/agent-monitor") ? "" : "p-6 md:p-8"}>
                    {children}
                </div>
            </main>

            {/* ── Toast Notifications ──────────────────────────────── */}
            {toasts.length > 0 && (
                <div className="fixed top-4 right-4 z-[100] flex flex-col gap-3 max-w-sm">
                    {toasts.map((toast) => (
                        <div
                            key={toast.toastId}
                            className={`
                                flex items-start gap-3 p-4 rounded-xl border backdrop-blur-xl shadow-2xl
                                animate-[slideIn_0.3s_ease-out]
                                ${toast.status === "completed"
                                    ? "bg-emerald-500/10 border-emerald-500/30 shadow-emerald-500/10"
                                    : "bg-red-500/10 border-red-500/30 shadow-red-500/10"
                                }
                            `}
                        >
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                                toast.status === "completed" ? "bg-emerald-500/20" : "bg-red-500/20"
                            }`}>
                                <Bell className={`w-4 h-4 ${
                                    toast.status === "completed" ? "text-emerald-400" : "text-red-400"
                                }`} />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-white">
                                    {toast.status === "completed" ? "Processing Complete" : "Processing Failed"}
                                </p>
                                <p className="text-xs text-[var(--nc-text-muted)] mt-0.5 truncate">
                                    {toast.message}
                                </p>
                            </div>
                            <button
                                onClick={() => {
                                    dismissToast(toast.toastId);
                                    markNotifRead(toast.id);
                                }}
                                className="w-5 h-5 flex items-center justify-center rounded hover:bg-white/10 transition-colors shrink-0"
                            >
                                <X className="w-3 h-3 text-[var(--nc-text-dim)]" />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
