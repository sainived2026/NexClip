"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { 
    Shield, Activity, Settings, Users, Brain, Zap, 
    RefreshCw, AlertTriangle, CheckCircle, XCircle,
    Server, Type, Globe
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

// Import new Tab Components
import SystemStatusTab from "@/components/admin/SystemStatusTab";
import ConfigurationTab from "@/components/admin/ConfigurationTab";
import UsersProjectsTab from "@/components/admin/UsersProjectsTab";
import AiControlsTab from "@/components/admin/AiControlsTab";
import LogsServicesTab from "@/components/admin/LogsServicesTab";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const adminTabs = [
    { id: "status", label: "System Status", icon: Activity },
    { id: "config", label: "Configuration", icon: Settings },
    { id: "nexearch", label: "Nexearch Services", icon: Globe },
    { id: "captions", label: "Caption Styles", icon: Type },
    { id: "users", label: "Users & Projects", icon: Users },
    { id: "ai", label: "AI & Prompts", icon: Brain },
    { id: "services", label: "Logs & Services", icon: Zap },
];

export default function AdminPage() {
    const router = useRouter();
    const [token, setToken] = useState<string>("");
    const [activeTab, setActiveTab] = useState("status");
    const [accessDenied, setAccessDenied] = useState(false);
    const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);
    const [loading, setLoading] = useState<Record<string, boolean>>({});

    // Data states
    const [status, setStatus] = useState<any>(null);
    const [config, setConfig] = useState<any>(null);
    const [configEdits, setConfigEdits] = useState<Record<string, string>>({});
    const [prompt, setPrompt] = useState<string>("");
    const [promptOriginal, setPromptOriginal] = useState<string>("");
    const [users, setUsers] = useState<any[]>([]);
    const [projects, setProjects] = useState<any[]>([]);
    const [logs, setLogs] = useState<string>("");
    const [serviceHealth, setServiceHealth] = useState<any>(null);
    const [captionStyles, setCaptionStyles] = useState<any[]>([]);

    const showToast = (msg: string, type: "success" | "error" = "success") => {
        setToast({ msg, type });
        setTimeout(() => setToast(null), 4000);
    };

    const headers = useCallback(() => ({
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
    }), [token]);

    // ── Data Fetching ────────────────────────────────────────────
    const fetchStatus = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/admin/status`, { headers: headers() });
            if (res.status === 403) { setAccessDenied(true); return; }
            if (res.ok) setStatus(await res.json());
        } catch { }
    }, [headers]);

    const fetchConfig = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/admin/config`, { headers: headers() });
            if (res.ok) {
                const data = await res.json();
                setConfig(data.schema);
                setConfigEdits({}); 
            }
        } catch { }
    }, [headers]);

    const fetchPrompt = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/admin/prompt`, { headers: headers() });
            if (res.ok) {
                const data = await res.json();
                setPrompt(data.prompt);
                setPromptOriginal(data.prompt);
            }
        } catch { }
    }, [headers]);

    const fetchUsers = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/admin/users`, { headers: headers() });
            if (res.ok) {
                const data = await res.json();
                setUsers(data.users);
            }
        } catch { }
    }, [headers]);

    const fetchProjects = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/admin/projects`, { headers: headers() });
            if (res.ok) {
                const data = await res.json();
                setProjects(data.projects);
            }
        } catch { }
    }, [headers]);

    const fetchLogs = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/admin/logs`, { headers: headers() });
            if (res.ok) {
                const data = await res.json();
                setLogs(data.logs);
            }
        } catch { }
    }, [headers]);

    const refreshAll = useCallback(() => {
        fetchStatus();
        fetchConfig();
        fetchUsers();
        fetchProjects();
        fetchLogs();
        fetchServiceHealth();
        fetchCaptionStyles();
    }, [fetchStatus, fetchConfig, fetchUsers, fetchProjects, fetchLogs]);

    const fetchServiceHealth = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/admin/services/health`, { headers: headers() });
            if (res.ok) setServiceHealth(await res.json());
        } catch { }
    }, [headers]);

    const fetchCaptionStyles = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/admin/caption-styles`, { headers: headers() });
            if (res.ok) {
                const data = await res.json();
                setCaptionStyles(data.styles || []);
            }
        } catch { }
    }, [headers]);

    const [tokenLoaded, setTokenLoaded] = useState(false);

    useEffect(() => {
        const t = localStorage.getItem("nexclip_token");
        setToken(t || "");
        setTokenLoaded(true);
    }, [router]);

    useEffect(() => {
        if (!tokenLoaded) return;
        refreshAll();
        fetchPrompt();

        const interval = setInterval(fetchStatus, 15000);
        return () => clearInterval(interval);
    }, [tokenLoaded, token, refreshAll, fetchPrompt, fetchStatus]);

    // ── Actions ──────────────────────────────────────────────────
    const saveConfig = async () => {
        if (Object.keys(configEdits).length === 0) { showToast("No changes to save", "error"); return; }
        setLoading(p => ({ ...p, config: true }));
        try {
            const res = await fetch(`${API}/api/admin/config`, {
                method: "PUT", headers: headers(),
                body: JSON.stringify(configEdits),
            });
            const data = await res.json();
            if (res.ok) {
                showToast(data.message);
                fetchConfig();
                fetchStatus();
            } else {
                showToast(data.detail || "Failed to save", "error");
            }
        } catch { showToast("Network error", "error"); }
        setLoading(p => ({ ...p, config: false }));
    };

    const savePrompt = async () => {
        setLoading(p => ({ ...p, prompt: true }));
        try {
            const res = await fetch(`${API}/api/admin/prompt`, {
                method: "PUT", headers: headers(),
                body: JSON.stringify({ prompt }),
            });
            const data = await res.json();
            if (res.ok) {
                showToast(data.message);
                setPromptOriginal(prompt);
                fetchStatus();
            } else {
                showToast(data.detail || "Failed to save", "error");
            }
        } catch { showToast("Network error", "error"); }
        setLoading(p => ({ ...p, prompt: false }));
    };

    const toggleUser = async (userId: string) => {
        try {
            const res = await fetch(`${API}/api/admin/users/${userId}/toggle`, {
                method: "PUT", headers: headers(),
            });
            const data = await res.json();
            if (res.ok) {
                showToast(data.message);
                fetchUsers();
            } else {
                showToast(data.detail || "Failed", "error");
            }
        } catch { showToast("Network error", "error"); }
    };

    const deleteProject = async (projectId: string, title: string) => {
        if (!confirm(`Delete project "${title}" and all its files? This cannot be undone.`)) return;
        try {
            const res = await fetch(`${API}/api/admin/projects/${projectId}`, {
                method: "DELETE", headers: headers(),
            });
            const data = await res.json();
            if (res.ok) {
                showToast(data.message);
                fetchProjects();
                fetchStatus();
            } else {
                showToast(data.detail || "Failed", "error");
            }
        } catch { showToast("Network error", "error"); }
    };

    const restartService = async (service: string) => {
        if (!confirm(`Restart ${service}? This may cause brief downtime.`)) return;
        setLoading(p => ({ ...p, [`restart_${service}`]: true }));
        try {
            const res = await fetch(`${API}/api/admin/restart/${service}`, {
                method: "POST", headers: headers(),
            });
            const data = await res.json();
            if (res.ok) {
                showToast(data.message);
                setTimeout(fetchStatus, 3000);
            } else {
                showToast(data.detail || "Restart failed", "error");
            }
        } catch { showToast("Network error", "error"); }
        setLoading(p => ({ ...p, [`restart_${service}`]: false }));
    };

    const clearLogs = async () => {
        try {
            const res = await fetch(`${API}/api/admin/logs`, { method: "DELETE", headers: headers() });
            if (res.ok) { showToast("Logs cleared"); setLogs(""); }
        } catch { }
    };

    // ── Access Denied ────────────────────────────────────────────
    if (accessDenied) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[70vh]">
                <motion.div 
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="text-center p-10 rounded-3xl border border-red-500/20 bg-gradient-to-br from-red-500/10 to-transparent max-w-md shadow-2xl relative overflow-hidden"
                >
                    <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-red-500/0 via-red-500 to-red-500/0"></div>
                    <div className="w-20 h-20 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
                        <Shield className="w-10 h-10 text-red-500" />
                    </div>
                    <h2 className="text-2xl font-bold text-white mb-3">Access Denied</h2>
                    <p className="text-[var(--nc-text-muted)] leading-relaxed">Only the system administrator can access the command center panel. Please contact the owner for access.</p>
                </motion.div>
            </div>
        );
    }

    return (
        <div className="max-w-7xl mx-auto space-y-6 pb-20">
            {/* ── Header ────────────────────────────────────────── */}
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3 tracking-tight">
                        <div className="p-2 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30">
                            <Shield className="w-6 h-6 text-indigo-400" />
                        </div>
                        Command Center
                    </h1>
                    <p className="text-[var(--nc-text-muted)] mt-2 ml-1 text-sm">Complete system administration & monitoring</p>
                </div>
                <button
                    onClick={refreshAll}
                    className="flex items-center gap-2.5 px-5 py-2.5 rounded-xl bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)] text-sm font-medium text-[var(--nc-text-muted)] hover:text-white hover:border-indigo-500/30 transition-all shadow-sm active:scale-95"
                >
                    <RefreshCw className="w-4 h-4" />
                    Sync Data
                </button>
            </header>

            {/* ── Restart Required Banner ────────────────────────── */}
            <AnimatePresence>
                {status?.restart_required && (
                    <motion.div 
                        initial={{ opacity: 0, height: 0, scale: 0.95 }}
                        animate={{ opacity: 1, height: 'auto', scale: 1 }}
                        exit={{ opacity: 0, height: 0, scale: 0.95 }}
                        className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-2xl bg-gradient-to-r from-amber-500/10 to-amber-600/5 border border-amber-500/30 shadow-lg shadow-amber-500/5 mb-6 overflow-hidden relative"
                    >
                        <div className="absolute top-0 left-0 w-1 h-full bg-amber-500"></div>
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-amber-500/20 rounded-lg">
                                <AlertTriangle className="w-5 h-5 text-amber-400" />
                            </div>
                            <div>
                                <h4 className="text-sm font-semibold text-amber-300">Pending Changes</h4>
                                <span className="text-xs text-amber-400/80">System services must be restarted to apply newly saved configurations.</span>
                            </div>
                        </div>
                        <button
                            onClick={() => restartService("all")}
                            className="shrink-0 px-5 py-2 rounded-xl bg-amber-500/20 text-amber-300 text-sm font-semibold hover:bg-amber-500/30 border border-amber-500/30 transition-all active:scale-95"
                        >
                            Restart Services
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Toast Notifications ────────────────────────────── */}
            <AnimatePresence>
                {toast && (
                    <motion.div 
                        initial={{ opacity: 0, y: 50, scale: 0.9 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 20, scale: 0.9 }}
                        className={`fixed bottom-8 right-8 z-50 flex items-center gap-3 px-5 py-3.5 rounded-2xl shadow-2xl border text-sm font-medium backdrop-blur-xl ${
                            toast.type === "success"
                            ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-300"
                            : "bg-red-500/15 border-red-500/30 text-red-300"
                        }`}
                    >
                        {toast.type === "success" ? <CheckCircle className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
                        {toast.msg}
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Main Tab Navigation ────────────────────────────── */}
            <div className="sticky top-0 z-30 -mx-6 md:-mx-8 px-6 md:px-8 pt-4 pb-4 bg-[var(--nc-bg)] border-b border-[var(--nc-border)] shadow-[0_8px_30px_-12px_rgba(0,0,0,0.4)]">
                <nav className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
                    {adminTabs.map((tab) => {
                        const isActive = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`relative flex items-center gap-2.5 px-5 py-2.5 rounded-xl text-sm font-medium transition-all whitespace-nowrap shrink-0 group ${
                                    isActive 
                                    ? "text-white" 
                                    : "text-[var(--nc-text-muted)] hover:text-white hover:bg-white/[0.04]"
                                }`}
                            >
                                <tab.icon className={`w-4 h-4 transition-colors ${isActive ? "text-indigo-400" : "group-hover:text-indigo-400/60"}`} />
                                {tab.label}
                                {isActive && (
                                    <motion.div
                                        layoutId="adminTabIndicator"
                                        className="absolute inset-0 rounded-xl bg-indigo-500/10 border border-indigo-500/30 z-[-1]"
                                        transition={{ type: "spring", stiffness: 350, damping: 30 }}
                                    />
                                )}
                            </button>
                        );
                    })}
                </nav>
            </div>

            {/* ── Tab Content Area ──────────────────────────────── */}
            <div className="mt-4 min-h-[500px]">
                <AnimatePresence mode="wait">
                    {activeTab === "status" && <SystemStatusTab key="status" status={status} />}
                    {activeTab === "config" && (
                        <ConfigurationTab 
                            key="config" 
                            config={config} 
                            configEdits={configEdits} 
                            setConfigEdits={setConfigEdits} 
                            saveConfig={saveConfig} 
                            loading={loading.config || false} 
                        />
                    )}
                    {activeTab === "nexearch" && (
                        <motion.div key="nexearch" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="space-y-6">
                            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                                <Globe className="w-5 h-5 text-indigo-400" /> All Service Health
                            </h3>
                            {serviceHealth?.services ? (
                                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                                    {Object.entries(serviceHealth.services).map(([name, info]: [string, any]) => (
                                        <div key={name} className="rounded-xl bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)] p-4 hover:border-white/10 transition-all">
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="text-sm font-semibold text-white capitalize">{name.replace(/_/g, " ")}</span>
                                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                                                    info.status === "online" ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20" : "bg-red-500/15 text-red-400 border border-red-500/20"
                                                }`}>
                                                    <span className={`w-1.5 h-1.5 rounded-full ${info.status === "online" ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`} />
                                                    {info.status}
                                                </span>
                                            </div>
                                            {info.port && <div className="text-xs text-[var(--nc-text-dim)]">Port {info.port}</div>}
                                            {info.latency_ms !== undefined && <div className="text-xs text-[var(--nc-text-muted)]">Latency: <span className="text-white font-mono">{info.latency_ms}ms</span></div>}
                                            {info.workers && <div className="text-xs text-[var(--nc-text-muted)]">{info.workers} worker(s)</div>}
                                            {info.error && <div className="text-xs text-red-400 mt-1 truncate">{info.error}</div>}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="flex items-center justify-center p-12">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
                                </div>
                            )}
                        </motion.div>
                    )}
                    {activeTab === "captions" && (
                        <motion.div key="captions" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="space-y-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                                        <Type className="w-5 h-5 text-indigo-400" /> Caption Styles ({captionStyles.length})
                                    </h3>
                                    <p className="text-sm text-[var(--nc-text-muted)] mt-1">Premium word-by-word karaoke caption engine</p>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
                                {captionStyles.map((s: any, i: number) => (
                                    <div key={s.style_id} className="rounded-xl bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)] p-4 hover:border-indigo-500/30 transition-all">
                                        <div className="flex items-center gap-2 mb-2">
                                            <div className="w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-bold"
                                                style={{ background: `${s.active_color}20`, color: s.active_color, border: `1px solid ${s.active_color}40` }}>
                                                {String(i + 1).padStart(2, "0")}
                                            </div>
                                            <span className="text-sm font-semibold text-white">{s.display_name}</span>
                                        </div>
                                        <div className="text-xs text-[var(--nc-text-dim)] space-y-0.5">
                                            <div>Font: {s.font_family} ({s.font_size}px)</div>
                                            <div className="flex items-center gap-1">Active: <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: s.active_color }} /> {s.active_color}</div>
                                            {s.uppercase && <span className="inline-block text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 font-bold">UPPERCASE</span>}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </motion.div>
                    )}
                    {activeTab === "users" && (
                        <UsersProjectsTab 
                            key="users" 
                            users={users} 
                            projects={projects} 
                            toggleUser={toggleUser} 
                            deleteProject={deleteProject} 
                        />
                    )}
                    {activeTab === "ai" && (
                        <AiControlsTab 
                            key="ai" 
                            prompt={prompt} 
                            promptOriginal={promptOriginal} 
                            setPrompt={setPrompt} 
                            savePrompt={savePrompt} 
                            loading={loading.prompt || false} 
                        />
                    )}
                    {activeTab === "services" && (
                        <LogsServicesTab 
                            key="services" 
                            logs={logs} 
                            fetchLogs={fetchLogs} 
                            clearLogs={clearLogs} 
                            restartService={restartService} 
                            loading={loading} 
                            servicesStatus={status?.services} 
                        />
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}
