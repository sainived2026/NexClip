"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Globe, TrendingUp, AlertTriangle, GitCommit, RefreshCw, BarChart, LayoutGrid, Loader2, Undo2, Play, X, CheckCircle, Clock, Zap } from "lucide-react";

export default function UniversalIntelligencePage() {
    const [activeTab, setActiveTab] = useState("instagram");
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<any>(null);
    const [error, setError] = useState("");

    // Evolution state
    const [evolving, setEvolving] = useState(false);
    const [taskId, setTaskId] = useState<string | null>(null);
    const [progress, setProgress] = useState<any>(null);
    const pollRef = useRef<NodeJS.Timeout | null>(null);

    // Evolution logs
    const [logs, setLogs] = useState<any[]>([]);
    const [reverting, setReverting] = useState<string | null>(null);

    const platforms = [
        { id: "instagram", name: "Instagram", color: "#E4405F" },
        { id: "tiktok", name: "TikTok", color: "#00F2EA" },
        { id: "youtube", name: "YouTube", color: "#FF0000" },
        { id: "linkedin", name: "LinkedIn", color: "#0A66C2" },
        { id: "twitter", name: "Twitter", color: "#1DA1F2" },
        { id: "facebook", name: "Facebook", color: "#1877F2" },
        { id: "threads", name: "Threads", color: "#000000" },
    ];

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError("");
        try {
            const res = await fetch("http://localhost:8002/api/v1/intelligence/universal");
            if (!res.ok) throw new Error("Failed to fetch Universal Intelligence");
            const json = await res.json();
            setData(json);
        } catch (err: any) {
            setError(err.message || "Unknown error");
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchLogs = useCallback(async () => {
        try {
            const res = await fetch("http://localhost:8002/api/v1/intelligence/universal/evolution-logs");
            if (res.ok) {
                const json = await res.json();
                setLogs(json.logs || []);
            }
        } catch (e) { /* silent */ }
    }, []);

    useEffect(() => {
        fetchData();
        fetchLogs();
    }, [fetchData, fetchLogs]);

    // Start evolution
    const startEvolution = async () => {
        setEvolving(true);
        setProgress(null);
        try {
            const res = await fetch("http://localhost:8002/api/v1/intelligence/universal/evolve", { method: "POST" });
            const json = await res.json();
            if (json.task_id) {
                setTaskId(json.task_id);
                startPolling(json.task_id);
            }
        } catch (err) {
            setEvolving(false);
        }
    };

    // Poll for progress
    const startPolling = (tid: string) => {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(async () => {
            try {
                const res = await fetch(`http://localhost:8002/api/v1/intelligence/universal/evolve/status/${tid}`);
                if (res.ok) {
                    const p = await res.json();
                    setProgress(p);
                    if (p.status === "complete" || p.status === "error" || p.status === "cancelled") {
                        if (pollRef.current) clearInterval(pollRef.current);
                        setTimeout(() => {
                            fetchData();
                            fetchLogs();
                        }, 1000);
                    }
                }
            } catch (e) { /* silent */ }
        }, 2000);
    };

    // Cancel evolution
    const cancelEvolution = async () => {
        if (taskId) {
            await fetch(`http://localhost:8002/api/v1/intelligence/universal/evolve/cancel/${taskId}`, { method: "POST" });
        }
        if (pollRef.current) clearInterval(pollRef.current);
        setEvolving(false);
        setProgress(null);
        setTaskId(null);
    };

    // Close modal
    const closeModal = () => {
        setEvolving(false);
        setProgress(null);
        setTaskId(null);
        if (pollRef.current) clearInterval(pollRef.current);
    };

    // Revert
    const revertLog = async (logId: string) => {
        setReverting(logId);
        try {
            const res = await fetch(`http://localhost:8002/api/v1/intelligence/universal/revert/${logId}`, { method: "POST" });
            if (res.ok) {
                await fetchData();
                await fetchLogs();
            }
        } catch (e) { /* silent */ }
        setReverting(null);
    };

    // Cleanup polling on unmount
    useEffect(() => {
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, []);

    const stats = data?.stats?.[activeTab] || { s_tier: 0, a_tier: 0, b_tier: 0, c_tier: 0 };
    const totalPosts = stats.s_tier + stats.a_tier + stats.b_tier + stats.c_tier;
    const getPercent = (val: number) => totalPosts > 0 ? Math.round((val / totalPosts) * 100) : 0;
    const dna = data?.dna?.[activeTab] || { version: "1.0", winning_patterns: [], avoid_patterns: [], directives: {} };

    return (
        <div style={{ padding: "24px 32px", background: "#0A0A0F", minHeight: "calc(100vh - 64px)", color: "#E2E8F0" }}>
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-3xl font-bold flex items-center gap-3" style={{ background: "linear-gradient(135deg, #3B82F6, #8B5CF6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                        <Globe className="w-8 h-8 text-blue-500" />
                        Universal Intelligence
                    </h1>
                    <p className="text-sm mt-1" style={{ color: "#94A3B8" }}>
                        Global platform analysis, universal post tiering, and self-evolution engine.
                    </p>
                </div>
                <div className="flex gap-3">
                    <button onClick={fetchData} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm bg-blue-500/10 border border-blue-500/30 text-blue-400 hover:bg-blue-500/20 transition-all">
                        <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Refresh
                    </button>
                    <button onClick={startEvolution} disabled={evolving} className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-500 hover:to-blue-500 transition-all disabled:opacity-50 shadow-lg shadow-purple-500/20">
                        {evolving ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                        {evolving ? "Running..." : "Run Universal Analysis"}
                    </button>
                </div>
            </div>

            {/* ── Progress Modal ─────────────────────────────────────── */}
            {evolving && progress && (
                <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-[#12121A] border border-white/10 rounded-2xl shadow-2xl w-full max-w-xl p-8">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-white flex items-center gap-3">
                                {progress.status === "complete" ? <CheckCircle className="text-emerald-400" /> :
                                 progress.status === "error" ? <AlertTriangle className="text-red-400" /> :
                                 <Loader2 className="animate-spin text-purple-400" />}
                                Universal Analysis
                            </h2>
                            <button onClick={progress.status === "complete" || progress.status === "error" ? closeModal : cancelEvolution} className="text-slate-400 hover:text-white"><X size={20} /></button>
                        </div>

                        {/* Progress bar */}
                        <div className="mb-6">
                            <div className="flex justify-between text-sm mb-2">
                                <span className="text-slate-400">{progress.message}</span>
                                <span className="text-purple-400 font-mono font-bold">{progress.progress_percent}%</span>
                            </div>
                            <div className="w-full h-3 bg-white/5 rounded-full overflow-hidden">
                                <div className="h-full rounded-full transition-all duration-500 ease-out" style={{
                                    width: `${progress.progress_percent}%`,
                                    background: progress.status === "complete" ? "linear-gradient(90deg, #10B981, #059669)" :
                                               progress.status === "error" ? "#EF4444" :
                                               "linear-gradient(90deg, #8B5CF6, #3B82F6)"
                                }} />
                            </div>
                        </div>

                        {/* Details */}
                        <div className="grid grid-cols-2 gap-4 mb-6">
                            <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Current Platform</div>
                                <div className="text-sm font-bold text-white">{progress.current_platform?.toUpperCase() || "—"}</div>
                            </div>
                            <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Current Client</div>
                                <div className="text-sm font-bold text-white truncate">{progress.current_client || "—"}</div>
                            </div>
                            <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Stage</div>
                                <div className="text-sm font-bold text-purple-300 capitalize">{progress.current_stage || "—"}</div>
                            </div>
                            <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Platforms Done</div>
                                <div className="text-sm font-bold text-emerald-400">{progress.platforms_completed?.length || 0} / 7</div>
                            </div>
                        </div>

                        {/* Completed platforms */}
                        {progress.platforms_completed?.length > 0 && (
                            <div className="mb-4">
                                <div className="text-xs text-slate-500 mb-2">Completed:</div>
                                <div className="flex flex-wrap gap-2">
                                    {progress.platforms_completed.map((p: string) => (
                                        <span key={p} className="text-xs px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">{p}</span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Errors */}
                        {progress.errors?.length > 0 && (
                            <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-300 max-h-24 overflow-y-auto">
                                {progress.errors.map((e: string, i: number) => <div key={i}>• {e}</div>)}
                            </div>
                        )}

                        {/* Actions */}
                        <div className="flex gap-3 mt-6">
                            {progress.status !== "complete" && progress.status !== "error" && (
                                <button onClick={cancelEvolution} className="flex-1 py-2.5 rounded-lg text-sm font-semibold bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20">
                                    Cancel
                                </button>
                            )}
                            {(progress.status === "complete" || progress.status === "error") && (
                                <button onClick={closeModal} className="flex-1 py-2.5 rounded-lg text-sm font-semibold bg-purple-500/10 border border-purple-500/30 text-purple-400 hover:bg-purple-500/20">
                                    Close
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Platform Tabs */}
            <div className="flex space-x-2 mb-8 p-1 bg-white/5 inline-flex rounded-xl border border-white/10 overflow-x-auto max-w-full">
                {platforms.map(p => (
                    <button key={p.id} onClick={() => setActiveTab(p.id)} className={`px-6 py-2 rounded-lg text-sm transition-all whitespace-nowrap ${activeTab === p.id ? "bg-white/10 text-white font-semibold" : "text-slate-400 hover:text-white hover:bg-white/5"}`}>
                        {p.name}
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="flex items-center justify-center p-20 text-blue-400"><Loader2 className="w-10 h-10 animate-spin" /></div>
            ) : error ? (
                <div className="p-6 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400">
                    <AlertTriangle className="w-6 h-6 mb-2" />
                    <strong>Failed to load Intelligence Data:</strong> {error}
                </div>
            ) : (
                <div className="space-y-6">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6" style={{ minWidth: 0 }}>
                        {/* Column 1 & 2: Data & Trends */}
                        <div className="lg:col-span-2 space-y-6">
                            <div className="grid grid-cols-2 gap-6">
                                {/* Winning Patterns */}
                                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-6 min-h-[250px]">
                                    <h3 className="text-lg font-bold text-emerald-400 flex items-center gap-2 mb-4">
                                        <TrendingUp className="w-5 h-5" /> Winning Patterns
                                    </h3>
                                    {dna.winning_patterns?.length > 0 ? (
                                        <ul className="space-y-3">
                                            {dna.winning_patterns.map((pat: string, i: number) => (
                                                <li key={i} className="text-sm text-slate-300 flex gap-2"><span className="text-emerald-500">•</span> {pat}</li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <div className="text-sm text-emerald-500/50 italic flex h-full pb-8 items-center justify-center">Click "Run Universal Analysis" to discover winning patterns</div>
                                    )}
                                </div>

                                {/* Avoid Patterns */}
                                <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 min-h-[250px]">
                                    <h3 className="text-lg font-bold text-red-400 flex items-center gap-2 mb-4">
                                        <AlertTriangle className="w-5 h-5" /> Avoid Patterns
                                    </h3>
                                    {dna.avoid_patterns?.length > 0 ? (
                                        <ul className="space-y-3">
                                            {dna.avoid_patterns.map((pat: string, i: number) => (
                                                <li key={i} className="text-sm text-slate-300 flex gap-2"><span className="text-red-500">•</span> {pat}</li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <div className="text-sm text-red-500/50 italic flex h-full pb-8 items-center justify-center">Click "Run Universal Analysis" to identify patterns to avoid</div>
                                    )}
                                </div>
                            </div>

                            {/* Tier Distribution */}
                            <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                                <h3 className="text-lg font-bold text-white flex items-center gap-2 mb-6">
                                    <BarChart className="w-5 h-5 text-blue-400" /> Tier Distribution (Analyzed Posts: {totalPosts})
                                </h3>
                                <div className="flex items-center gap-4">
                                    {[
                                        { label: "S Tier", count: stats.s_tier, pct: getPercent(stats.s_tier), color: "indigo" },
                                        { label: "A Tier", count: stats.a_tier, pct: getPercent(stats.a_tier), color: "emerald" },
                                        { label: "B Tier", count: stats.b_tier, pct: getPercent(stats.b_tier), color: "blue" },
                                        { label: "C Tier", count: stats.c_tier, pct: getPercent(stats.c_tier), color: "slate" },
                                    ].map(t => (
                                        <div key={t.label} className={`flex-1 bg-white/5 rounded-lg p-4 border border-${t.color}-500/30 text-center relative overflow-hidden`}>
                                            <div className={`absolute inset-x-0 bottom-0 bg-${t.color}-500/20 opacity-50`} style={{ height: `${t.pct}%` }} />
                                            <div className="relative z-10">
                                                <div className={`text-3xl font-black text-${t.color}-400 mb-1`}>{t.pct}%</div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-widest">{t.label} <span className="text-slate-500 font-normal">({t.count})</span></div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* Column 3: Universal DNA */}
                        <div className="space-y-6" style={{ minWidth: 0 }}>
                            <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-6 min-h-[500px]" style={{ minWidth: 0, overflow: "hidden" }}>
                                <div className="flex items-center justify-between mb-6">
                                    <h3 className="text-lg font-bold text-purple-400 flex items-center gap-2">
                                        <LayoutGrid className="w-5 h-5" /> Universal DNA
                                    </h3>
                                    <span className="text-xs px-2 py-1 bg-purple-500/20 rounded text-purple-300 font-mono">v{dna.version || "1.0"}</span>
                                </div>
                                <div className="space-y-3">
                                    {Object.keys(dna.directives || {}).length > 0 ? (
                                        Object.entries(dna.directives).map(([key, value]: [string, any]) => (
                                            <div key={key} className="p-3 bg-black/40 rounded border border-white/5" style={{ minWidth: 0 }}>
                                                <div className="text-xs text-purple-300 font-bold mb-2 uppercase tracking-wider">{key.replace(/_/g, " ")}</div>
                                                {Array.isArray(value) ? (
                                                    <ul className="space-y-1">
                                                        {value.map((item: any, i: number) => (
                                                            <li key={i} className="text-xs text-slate-300 flex gap-1.5 items-start" style={{ wordBreak: "break-word", overflowWrap: "anywhere" }}>
                                                                <span className="text-purple-500 shrink-0">›</span>
                                                                <span>{typeof item === "object" ? JSON.stringify(item) : String(item)}</span>
                                                            </li>
                                                        ))}
                                                    </ul>
                                                ) : typeof value === "object" && value !== null ? (
                                                    <div className="space-y-1">
                                                        {Object.entries(value).map(([k, v]) => (
                                                            <div key={k} className="text-xs" style={{ wordBreak: "break-word", overflowWrap: "anywhere" }}>
                                                                <span className="text-purple-400 font-semibold">{k.replace(/_/g, " ")}: </span>
                                                                <span className="text-slate-300">{String(v)}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                ) : (
                                                    <div className="text-xs text-slate-300" style={{ wordBreak: "break-word", overflowWrap: "anywhere" }}>{String(value)}</div>
                                                )}
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-sm text-purple-500/40 text-center py-10 border border-dashed border-purple-500/20 rounded-lg">
                                            Click &quot;Run Universal Analysis&quot; to generate Universal DNA.<br /><br />The engine will analyze best-performing content across all platforms.
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* ── Evolution Logs ─────────────────────────────────── */}
                    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="text-lg font-bold text-white flex items-center gap-2">
                                <Clock className="w-5 h-5 text-purple-400" /> Evolution History
                            </h3>
                            <button onClick={fetchLogs} className="text-xs text-slate-400 hover:text-white transition-colors">Refresh Logs</button>
                        </div>

                        {logs.length > 0 ? (
                            <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
                                {logs.map((log: any, i: number) => (
                                    <div key={log.log_id || i} className="p-4 bg-black/30 rounded-lg border border-white/5 hover:border-white/10 transition-colors">
                                        <div className="flex items-start justify-between gap-4">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-3 mb-2">
                                                    <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-semibold uppercase">{log.platform}</span>
                                                    <span className="text-xs text-slate-500">{new Date(log.timestamp).toLocaleString()}</span>
                                                    {log.reverted && <span className="text-xs px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-300">Reverted</span>}
                                                </div>
                                                {log.changes_summary?.length > 0 ? (
                                                    <ul className="space-y-1">
                                                        {log.changes_summary.slice(0, 3).map((s: string, j: number) => (
                                                            <li key={j} className="text-xs text-slate-400 flex gap-2 items-start">
                                                                <span className="text-purple-400 mt-0.5">›</span>
                                                                <span className="truncate">{s}</span>
                                                            </li>
                                                        ))}
                                                        {log.changes_summary.length > 3 && (
                                                            <li className="text-xs text-slate-500 italic pl-4">+{log.changes_summary.length - 3} more changes</li>
                                                        )}
                                                    </ul>
                                                ) : (
                                                    <div className="text-xs text-slate-500 italic">
                                                        {log.changes_count || 0} client(s) contributed to this evolution cycle
                                                    </div>
                                                )}
                                            </div>
                                            {log.has_before_snapshot && !log.reverted && (
                                                <button
                                                    onClick={() => revertLog(log.log_id)}
                                                    disabled={reverting === log.log_id}
                                                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 hover:bg-yellow-500/20 transition-all disabled:opacity-50 whitespace-nowrap"
                                                >
                                                    {reverting === log.log_id ? <Loader2 size={12} className="animate-spin" /> : <Undo2 size={12} />}
                                                    Revert
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-12 text-slate-500">
                                <Clock className="w-10 h-10 mx-auto mb-3 opacity-30" />
                                <div className="text-sm">No evolution cycles recorded yet.</div>
                                <div className="text-xs mt-1 text-slate-600">Click &quot;Run Universal Analysis&quot; to start the first cycle.</div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
