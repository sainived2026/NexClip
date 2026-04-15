"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Brain, Bot, Users, Activity, BarChart3,
  Zap, Settings, ArrowRight, Globe, RefreshCw,
  ChevronRight, AlertCircle, CheckCircle,
  MessageSquare, Cpu, Database
} from "lucide-react";

/* ════════════════════════════════════════════════════════════
   NEXEARCH DASHBOARD — Main overview page
   ════════════════════════════════════════════════════════════ */

export default function NexearchDashboard() {
  const [nexearchStatus, setNexearchStatus] = useState<any>(null);
  const [arcStatus, setArcStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const NEXEARCH = process.env.NEXT_PUBLIC_NEXEARCH_API_URL || "http://localhost:8002";
    const ARC = process.env.NEXT_PUBLIC_ARC_AGENT_URL || "http://localhost:8003";
    const fetchStatus = async () => {
      try {
        const [nxRes, arcRes] = await Promise.allSettled([
          fetch(`${NEXEARCH}/health`).then(r => r.json()),
          fetch(`${ARC}/api/status`).then(r => r.json()),
        ]);
        setNexearchStatus(nxRes.status === "fulfilled" ? nxRes.value : { status: "offline" });
        setArcStatus(arcRes.status === "fulfilled" ? arcRes.value : { status: "offline" });
      } catch {
        setNexearchStatus({ status: "offline" });
        setArcStatus({ status: "offline" });
      }
      setLoading(false);
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  const isOnline = (s: any) => s && (s.status === "ok" || s.status === "online");

  return (
    <div style={{ padding: "24px 32px", background: "#0A0A0F", minHeight: "calc(100vh - 64px)", color: "#E2E8F0" }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold" style={{ background: "linear-gradient(135deg, #06B6D4, #8B5CF6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Nexearch Intelligence
          </h1>
          <p className="text-sm mt-1" style={{ color: "#94A3B8" }}>
            Self-evolving social media intelligence engine
          </p>
        </div>
        <button onClick={() => location.reload()} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all hover:bg-white/5" style={{ border: "1px solid rgba(139,92,246,0.3)", color: "#A78BFA" }}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Status Cards Row */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { title: "Nexearch Engine", port: 8002, status: nexearchStatus, icon: Brain, color: "#06B6D4" },
          { title: "Arc Agent", port: 8003, status: arcStatus, icon: Bot, color: "#8B5CF6" },
          { title: "Agent Bridge", port: null, status: { status: isOnline(nexearchStatus) || isOnline(arcStatus) ? "ok" : "offline" }, icon: Zap, color: "#F59E0B", builtIn: true },
        ].map((card: any) => (
          <div key={card.title} className="rounded-xl p-5" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <card.icon size={20} style={{ color: card.color }} />
                <span className="text-sm font-semibold">{card.title}</span>
              </div>
              {card.builtIn ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider"
                  style={{ background: isOnline(card.status) ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)", color: isOnline(card.status) ? "#10B981" : "#EF4444" }}>
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: isOnline(card.status) ? "#10B981" : "#EF4444" }} />
                  {loading ? "..." : isOnline(card.status) ? "ACTIVE" : "OFFLINE"}
                </span>
              ) : (
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider`}
                  style={{ background: isOnline(card.status) ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)", color: isOnline(card.status) ? "#10B981" : "#EF4444" }}>
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: isOnline(card.status) ? "#10B981" : "#EF4444" }} />
                  {loading ? "..." : isOnline(card.status) ? "ONLINE" : "OFFLINE"}
                </span>
              )}
            </div>
            <div className="text-xs" style={{ color: "#64748B" }}>
              {card.builtIn ? "Built-in HTTP · Nex ↔ Arc" : `Port ${card.port}`}
            </div>
            {card.status?.tool_count && (
              <div className="text-xs mt-1" style={{ color: "#94A3B8" }}>
                {card.status.tool_count} tools · {Object.keys(card.status.tool_categories || {}).length} categories
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Navigation Cards */}
      <h2 className="text-lg font-semibold mb-4" style={{ color: "#CBD5E1" }}>Quick Navigation</h2>
      <div className="grid grid-cols-2 gap-4">
        {[
          { title: "Universal Intelligence", desc: "Analyze global patterns across all 7 platforms & self-evolve", href: "/dashboard/nexearch/universal", icon: Globe, color: "#3B82F6" },
          { title: "Client Intelligence", desc: "Per-client analysis, post tiering (S/A/B/C) & deep DNA evolution", href: "/dashboard/nexearch/client-intelligence", icon: BarChart3, color: "#10B981" },
          { title: "Arc Agent Chat", desc: "Chat with Arc Agent — Nexearch's controller intelligence", href: "/dashboard/nexearch/arc", icon: MessageSquare, color: "#8B5CF6" },
          { title: "Clients Management", desc: "Manage client social accounts and system credentials", href: "/dashboard/nexearch/clients", icon: Users, color: "#06B6D4" },
          { title: "Data Explorer", desc: "Browse raw scraped data, analysis results, published posts", href: "/dashboard/nexearch/data", icon: Database, color: "#F43F5E" },
          { title: "Admin Panel", desc: "Service management, restart services, system health", href: "/dashboard/nexearch/admin", icon: Settings, color: "#F59E0B" },
        ].map(card => (
          <Link key={card.title} href={card.href}>
            <div className="rounded-xl p-5 transition-all hover:bg-white/5 cursor-pointer group h-full"
              style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg" style={{ background: `${card.color}15` }}>
                    <card.icon size={20} style={{ color: card.color }} />
                  </div>
                  <div>
                    <div className="text-sm font-semibold" style={{ color: "#E2E8F0" }}>{card.title}</div>
                    <div className="text-xs" style={{ color: "#64748B" }}>{card.desc}</div>
                  </div>
                </div>
                <ChevronRight size={16} style={{ color: "#475569" }} className="group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </Link>
        ))}
      </div>

      {/* Arc Agent Info */}
      {arcStatus && arcStatus.subsystems && (
        <div className="mt-8 rounded-xl p-6" style={{ background: "rgba(139,92,246,0.05)", border: "1px solid rgba(139,92,246,0.15)" }}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: "#A78BFA" }}>
            <Cpu size={16} /> Arc Agent Subsystems
          </h3>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(arcStatus.subsystems || {}).map(([key, val]) => (
              <div key={key} className="flex items-center gap-2 text-xs">
                {val ? <CheckCircle size={12} style={{ color: "#10B981" }} /> : <AlertCircle size={12} style={{ color: "#EF4444" }} />}
                <span style={{ color: val ? "#94A3B8" : "#EF4444" }}>{key.replace(/_/g, " ")}</span>
              </div>
            ))}
          </div>
          {arcStatus.sub_agents > 0 && (
            <div className="mt-3 text-xs" style={{ color: "#64748B" }}>
              {arcStatus.sub_agents} sub-agents · {arcStatus.tool_count} tools · {arcStatus.custom_tools} custom tools
            </div>
          )}
        </div>
      )}
    </div>
  );
}
