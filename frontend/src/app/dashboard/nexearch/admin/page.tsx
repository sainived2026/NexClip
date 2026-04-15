"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Settings, RefreshCw, Power, CheckCircle, XCircle,
  Server, Bot, Brain, Cpu, Database, Activity, Zap,
  Users, Palette, Globe, Shield, Clock, Wifi, WifiOff,
  ChevronRight, AlertTriangle, ExternalLink, Type
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import ConfigurationTab from "@/components/admin/ConfigurationTab";

/* ════════════════════════════════════════════════════════════════
   NEXEARCH ADMIN PANEL — Complete System Management
   Service health, caption styles, platform registry, config viewer
   ════════════════════════════════════════════════════════════════ */

const NEX_API = "http://localhost:8002";
const ARC_API = "http://localhost:8003";
const BACKEND_API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ServiceInfo {
  name: string;
  key: string;
  port: number;
  url: string;
  status: "online" | "offline" | "loading";
  latency?: number;
  details?: any;
  icon: any;
  color: string;
}

interface CaptionStyle {
  style_id: string;
  display_name: string;
  font_family: string;
  font_weight: string;
  font_size: number;
  position: string;
  primary_color: string;
  active_color: string;
  uppercase: boolean;
  letter_spacing: number;
  scale_active: number;
}

const tabs = [
  { id: "services", label: "Services", icon: Server },
  { id: "captions", label: "Caption Styles", icon: Type },
  { id: "config", label: "Environment", icon: Settings },
  { id: "actions", label: "Quick Actions", icon: Zap },
];

export default function NexearchAdmin() {
  const [activeTab, setActiveTab] = useState("services");
  const [services, setServices] = useState<ServiceInfo[]>([
    { name: "NexClip Backend", key: "backend", port: 8000, url: `${BACKEND_API}/health`, status: "loading", icon: Server, color: "#3B82F6" },
    { name: "Nex Agent", key: "nex_agent", port: 8001, url: "http://localhost:8001/health", status: "loading", icon: Bot, color: "#6366F1" },
    { name: "Nexearch Engine", key: "nexearch", port: 8002, url: `${NEX_API}/health`, status: "loading", icon: Brain, color: "#06B6D4" },
    { name: "Arc Agent", key: "arc_agent", port: 8003, url: `${ARC_API}/health`, status: "loading", icon: Cpu, color: "#8B5CF6" },
  ]);
  const [captionStyles, setCaptionStyles] = useState<CaptionStyle[]>([]);
  const [envConfig, setEnvConfig] = useState<any>(null);
  const [configEdits, setConfigEdits] = useState<Record<string, string>>({});
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" | "info" } | null>(null);
  const [actionResult, setActionResult] = useState("");
  const [configSaving, setConfigSaving] = useState(false);

  const showToast = (msg: string, type: "success" | "error" | "info" = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  // ── Service Health Check ──────────────────────────────────────
  const checkServices = useCallback(async () => {
    const updated = await Promise.all(
      services.map(async (svc) => {
        try {
          const t0 = performance.now();
          const res = await fetch(svc.url, { signal: AbortSignal.timeout(5000) });
          if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
          }
          const latency = Math.round(performance.now() - t0);
          const data = await res.json();
          return { ...svc, status: "online" as const, latency, details: data };
        } catch {
          return { ...svc, status: "offline" as const, latency: undefined, details: null };
        }
      })
    );
    setServices(updated);
  }, []);

  // ── Caption Styles ────────────────────────────────────────────
  const fetchCaptionStyles = useCallback(async () => {
    try {
      const token = localStorage.getItem("nexclip_token");
      const res = await fetch(`${BACKEND_API}/api/admin/caption-styles`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setCaptionStyles(data.styles || []);
      }
    } catch { }
  }, []);

  // ── Environment Config ────────────────────────────────────────
  const fetchConfig = useCallback(async () => {
    try {
      const token = localStorage.getItem("nexclip_token");
      const res = await fetch(`${BACKEND_API}/api/admin/config`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setEnvConfig(data.schema);
        setConfigEdits({});
      }
    } catch { }
  }, []);

  const saveConfig = async () => {
    if (Object.keys(configEdits).length === 0) {
      showToast("No changes to save", "error");
      return;
    }

    setConfigSaving(true);
    try {
      const token = localStorage.getItem("nexclip_token");
      const res = await fetch(`${BACKEND_API}/api/admin/config`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(configEdits),
      });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message || "Configuration saved");
        await fetchConfig();
      } else {
        showToast(data.detail || "Failed to save configuration", "error");
      }
    } catch {
      showToast("Network error while saving configuration", "error");
    } finally {
      setConfigSaving(false);
    }
  };

  useEffect(() => {
    checkServices();
    fetchCaptionStyles();
    fetchConfig();
    const i = setInterval(checkServices, 20000);
    return () => clearInterval(i);
  }, []);

  // ── Service Actions ───────────────────────────────────────────
  const restartService = async (serviceName: string) => {
    showToast(`Restarting ${serviceName}...`, "info");
    try {
      const token = localStorage.getItem("nexclip_token");
      const res = await fetch(`${BACKEND_API}/api/admin/restart/${serviceName}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message || `${serviceName} restart initiated`);
        setTimeout(checkServices, 3000);
      } else {
        showToast(data.detail || "Restart failed", "error");
      }
    } catch {
      showToast(`Cannot reach backend. Use start.bat to restart ${serviceName}.`, "error");
    }
  };

  const onlineCount = services.filter(s => s.status === "online").length;

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-20">
      {/* ── Header ──────────────────────────────────────────── */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3 tracking-tight">
            <div className="p-2 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/30">
              <Settings className="w-6 h-6 text-amber-400" />
            </div>
            Nexearch Admin
          </h1>
          <p className="text-[var(--nc-text-muted)] mt-2 ml-1 text-sm">
            Service management, caption engine, and system configuration
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border ${
            onlineCount === services.length
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
              : "bg-amber-500/10 border-amber-500/30 text-amber-400"
          }`}>
            {onlineCount === services.length ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
            {onlineCount}/{services.length} Services
          </div>
          <button
            onClick={() => { checkServices(); fetchCaptionStyles(); fetchConfig(); }}
            className="flex items-center gap-2.5 px-5 py-2.5 rounded-xl bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)] text-sm font-medium text-[var(--nc-text-muted)] hover:text-white hover:border-amber-500/30 transition-all shadow-sm active:scale-95"
          >
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </header>

      {/* ── Toast ────────────────────────────────────────────── */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.9 }}
            className={`fixed bottom-8 right-8 z-50 flex items-center gap-3 px-5 py-3.5 rounded-2xl shadow-2xl border text-sm font-medium backdrop-blur-xl ${
              toast.type === "success" ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-300"
              : toast.type === "error" ? "bg-red-500/15 border-red-500/30 text-red-300"
              : "bg-sky-500/15 border-sky-500/30 text-sky-300"
            }`}
          >
            {toast.type === "success" ? <CheckCircle className="w-5 h-5" />
             : toast.type === "error" ? <XCircle className="w-5 h-5" />
             : <Activity className="w-5 h-5" />}
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Tab Navigation ───────────────────────────────────── */}
      <div className="sticky top-0 z-30 -mx-6 md:-mx-8 px-6 md:px-8 pt-4 pb-4 bg-[var(--nc-bg)] border-b border-[var(--nc-border)] shadow-[0_8px_30px_-12px_rgba(0,0,0,0.4)]">
        <nav className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative flex items-center gap-2.5 px-5 py-2.5 rounded-xl text-sm font-medium transition-all whitespace-nowrap shrink-0 group ${
                  isActive ? "text-white" : "text-[var(--nc-text-muted)] hover:text-white hover:bg-white/[0.04]"
                }`}
              >
                <tab.icon className={`w-4 h-4 transition-colors ${isActive ? "text-amber-400" : "group-hover:text-amber-400/60"}`} />
                {tab.label}
                {isActive && (
                  <motion.div
                    layoutId="nexAdminTabIndicator"
                    className="absolute inset-0 rounded-xl bg-amber-500/10 border border-amber-500/30 z-[-1]"
                    transition={{ type: "spring", stiffness: 350, damping: 30 }}
                  />
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* ── Tab Content ──────────────────────────────────────── */}
      <div className="mt-4 min-h-[500px]">
        <AnimatePresence mode="wait">
          {activeTab === "services" && (
            <motion.div key="services" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="space-y-6">
              {/* Service Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {services.map(svc => (
                  <div key={svc.key} className="rounded-2xl p-6 bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)] hover:border-white/10 transition-all">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl" style={{ background: `${svc.color}15`, border: `1px solid ${svc.color}30` }}>
                          <svc.icon size={22} style={{ color: svc.color }} />
                        </div>
                        <div>
                          <div className="text-base font-semibold text-white">{svc.name}</div>
                          <div className="text-xs text-[var(--nc-text-dim)]">Port {svc.port}</div>
                        </div>
                      </div>
                      <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                        svc.status === "online"
                          ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                          : svc.status === "loading"
                          ? "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                          : "bg-red-500/15 text-red-400 border border-red-500/30"
                      }`}>
                        <span className={`w-2 h-2 rounded-full ${
                          svc.status === "online" ? "bg-emerald-400 animate-pulse"
                          : svc.status === "loading" ? "bg-amber-400 animate-pulse"
                          : "bg-red-400"
                        }`} />
                        {svc.status}
                      </span>
                    </div>

                    {/* Details */}
                    {svc.status === "online" && (
                      <div className="mb-4 space-y-1">
                        {svc.latency !== undefined && (
                          <div className="flex items-center gap-2 text-xs text-[var(--nc-text-muted)]">
                            <Clock className="w-3 h-3" /> Latency: <span className="text-white font-mono">{svc.latency}ms</span>
                          </div>
                        )}
                        {svc.details?.tools && (
                          <div className="flex items-center gap-2 text-xs text-[var(--nc-text-muted)]">
                            <Zap className="w-3 h-3" /> Tools: <span className="text-white">{svc.details.tools}</span>
                          </div>
                        )}
                        {svc.details?.version && (
                          <div className="flex items-center gap-2 text-xs text-[var(--nc-text-muted)]">
                            <Shield className="w-3 h-3" /> Version: <span className="text-white">{svc.details.version}</span>
                          </div>
                        )}
                        {svc.details?.agent && (
                          <div className="flex items-center gap-2 text-xs text-[var(--nc-text-muted)]">
                            <Bot className="w-3 h-3" /> Agent: <span className="text-white">{svc.details.agent}</span>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => restartService(svc.key)}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-all hover:bg-amber-500/10 border border-amber-500/20 text-amber-400"
                      >
                        <Power size={14} /> Restart
                      </button>
                      <button
                        onClick={() => window.open(`http://localhost:${svc.port}/health`, "_blank")}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-all hover:bg-white/5 border border-[var(--nc-border)] text-[var(--nc-text-muted)]"
                      >
                        <ExternalLink size={14} /> Health JSON
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Redis & Celery Status */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-2xl p-5 bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)]">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                      <Database size={18} className="text-red-400" />
                    </div>
                    <span className="text-sm font-semibold text-white">Redis</span>
                    <span className="text-xs text-[var(--nc-text-dim)] ml-auto">Celery Broker</span>
                  </div>
                  <p className="text-xs text-[var(--nc-text-muted)]">
                    Redis is used as the message broker for Celery task queue. Required for video processing.
                  </p>
                </div>
                <div className="rounded-2xl p-5 bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)]">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 rounded-lg bg-purple-500/10 border border-purple-500/20">
                      <Activity size={18} className="text-purple-400" />
                    </div>
                    <span className="text-sm font-semibold text-white">Celery Workers</span>
                    <button 
                      onClick={() => restartService("celery")}
                      className="text-xs text-amber-400 ml-auto hover:text-amber-300 transition-colors"
                    >
                      Restart Workers
                    </button>
                  </div>
                  <p className="text-xs text-[var(--nc-text-muted)]">
                    Celery handles background video processing tasks (transcription, clipping, captioning).
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === "captions" && (
            <motion.div key="captions" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold text-white">Caption Styles Engine</h3>
                  <p className="text-sm text-[var(--nc-text-muted)]">{captionStyles.length} premium word-by-word karaoke styles</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {captionStyles.map((style, idx) => (
                  <motion.div
                    key={style.style_id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.03 }}
                    className="rounded-2xl p-5 bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)] hover:border-indigo-500/30 transition-all group"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold"
                          style={{ background: `${style.active_color}20`, color: style.active_color, border: `1px solid ${style.active_color}40` }}>
                          {String(idx + 1).padStart(2, "0")}
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-white">{style.display_name}</div>
                          <div className="text-xs text-[var(--nc-text-dim)]">{style.font_family}</div>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="p-2 rounded-lg bg-[var(--nc-bg)]">
                        <span className="text-[var(--nc-text-dim)]">Size</span>
                        <div className="text-white font-mono">{style.font_size}px</div>
                      </div>
                      <div className="p-2 rounded-lg bg-[var(--nc-bg)]">
                        <span className="text-[var(--nc-text-dim)]">Position</span>
                        <div className="text-white capitalize">{style.position}</div>
                      </div>
                      <div className="p-2 rounded-lg bg-[var(--nc-bg)]">
                        <span className="text-[var(--nc-text-dim)]">Active</span>
                        <div className="flex items-center gap-1.5">
                          <span className="w-3 h-3 rounded-full" style={{ background: style.active_color }} />
                          <span className="text-white font-mono">{style.active_color}</span>
                        </div>
                      </div>
                      <div className="p-2 rounded-lg bg-[var(--nc-bg)]">
                        <span className="text-[var(--nc-text-dim)]">Scale</span>
                        <div className="text-white font-mono">{style.scale_active}x</div>
                      </div>
                    </div>

                    {(style.uppercase || style.letter_spacing > 0) && (
                      <div className="flex gap-1.5 mt-3">
                        {style.uppercase && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 font-bold">UPPERCASE</span>
                        )}
                        {style.letter_spacing > 0 && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-400 font-bold">SPACING {style.letter_spacing}px</span>
                        )}
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}

          {activeTab === "config" && (
            <ConfigurationTab
              key="config"
              config={envConfig}
              configEdits={configEdits}
              setConfigEdits={setConfigEdits}
              saveConfig={saveConfig}
              loading={configSaving}
            />
          )}

          {activeTab === "actions" && (
            <motion.div key="actions" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="space-y-6">
              <div>
                <h3 className="text-lg font-bold text-white">Quick Actions</h3>
                <p className="text-sm text-[var(--nc-text-muted)]">System management shortcuts</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {[
                  {
                    label: "Restart Celery Workers",
                    desc: "Kill and restart background video processing workers",
                    icon: RefreshCw, color: "amber",
                    action: () => restartService("celery"),
                  },
                  {
                    label: "Restart Backend API",
                    desc: "Touch main.py to trigger uvicorn --reload",
                    icon: Server, color: "blue",
                    action: () => restartService("backend"),
                  },
                  {
                    label: "Restart All Services",
                    desc: "Restart celery + trigger backend reload",
                    icon: Zap, color: "purple",
                    action: () => restartService("all"),
                  },
                  {
                    label: "Check All Health",
                    desc: "Poll all 4 services for their health status",
                    icon: Activity, color: "emerald",
                    action: () => { checkServices(); showToast("Health check initiated"); },
                  },
                  {
                    label: "Open Backend Docs",
                    desc: "Open FastAPI Swagger docs in new tab",
                    icon: ExternalLink, color: "sky",
                    action: () => window.open(`${BACKEND_API}/docs`, "_blank"),
                  },
                  {
                    label: "Open Nexearch Docs",
                    desc: "Open Nexearch API docs in new tab",
                    icon: ExternalLink, color: "cyan",
                    action: () => window.open(`${NEX_API}/docs`, "_blank"),
                  },
                ].map(qa => {
                  const colorMap: Record<string, string> = {
                    amber: "from-amber-500/10 border-amber-500/20 text-amber-400",
                    blue: "from-blue-500/10 border-blue-500/20 text-blue-400",
                    purple: "from-purple-500/10 border-purple-500/20 text-purple-400",
                    emerald: "from-emerald-500/10 border-emerald-500/20 text-emerald-400",
                    sky: "from-sky-500/10 border-sky-500/20 text-sky-400",
                    cyan: "from-cyan-500/10 border-cyan-500/20 text-cyan-400",
                  };
                  return (
                    <button
                      key={qa.label}
                      onClick={qa.action}
                      className={`text-left rounded-2xl p-5 transition-all hover:scale-[1.02] active:scale-95 bg-gradient-to-br ${colorMap[qa.color]} to-transparent border`}
                    >
                      <div className="flex items-center gap-3 mb-2">
                        <qa.icon className="w-5 h-5" />
                        <span className="text-sm font-semibold text-white">{qa.label}</span>
                      </div>
                      <p className="text-xs text-[var(--nc-text-muted)]">{qa.desc}</p>
                    </button>
                  );
                })}
              </div>

              {/* Port Map */}
              <div className="rounded-2xl bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)] p-6 mt-6">
                <h4 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                  <Globe className="w-4 h-4 text-indigo-400" /> Service Port Map
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  {[
                    { name: "Backend", port: 8000, desc: "NexClip API" },
                    { name: "Nex Agent", port: 8001, desc: "Master Agent" },
                    { name: "Nexearch", port: 8002, desc: "Intelligence" },
                    { name: "Arc Agent", port: 8003, desc: "Execution Agent" },
                    { name: "Frontend", port: 3000, desc: "Next.js UI" },
                  ].map(s => (
                    <div key={s.port} className="p-3 rounded-xl bg-[var(--nc-bg)] border border-[var(--nc-border)]/50 text-center">
                      <div className="text-white font-semibold text-sm">:{s.port}</div>
                      <div className="text-xs text-[var(--nc-text-dim)] mt-0.5">{s.name}</div>
                      <div className="text-[10px] text-[var(--nc-text-dim)]">{s.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
