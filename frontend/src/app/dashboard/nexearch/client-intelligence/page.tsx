"use client";

import { useState, useEffect, useRef } from "react";
import {
    BarChart3, Fingerprint, GitCommit, Search, Shield, ChevronDown,
    CheckCircle2, Loader2, AlertTriangle, RefreshCw, Play, X,
    TrendingUp, TrendingDown, Users, Eye, Sparkles, Clock, Zap,
    Save, Edit3, Settings
} from "lucide-react";
import { arcAgentAPI } from "@/lib/api";

type ClientOption = {
    id: string;
    label: string;
    accountHandle: string;
    platformDetails: Record<string, { account_url?: string; can_research?: boolean }>;
};

// ── Render any value as readable JSX ──────────────────────────────────────────
function RenderValue({ value }: { value: any }) {
    if (value === null || value === undefined) return <span className="text-slate-500 italic">—</span>;
    if (typeof value === "string") return <span>{value}</span>;
    if (typeof value === "number" || typeof value === "boolean") return <span>{String(value)}</span>;
    if (Array.isArray(value)) {
        if (value.length === 0) return <span className="text-slate-500 italic">Empty</span>;
        return (
            <ul className="space-y-1 mt-1">
                {value.map((item, i) => (
                    <li key={i} className="flex gap-2 items-start">
                        <span className="text-emerald-500 mt-0.5">•</span>
                        <span className="text-slate-300 text-sm">{typeof item === "object" ? JSON.stringify(item, null, 2) : String(item)}</span>
                    </li>
                ))}
            </ul>
        );
    }
    if (typeof value === "object") {
        return (
            <div className="space-y-2 mt-1">
                {Object.entries(value).map(([k, v]) => (
                    <div key={k} className="pl-2 border-l border-emerald-500/20">
                        <span className="text-emerald-300 text-[10px] font-bold uppercase tracking-wider">{k.replace(/_/g, " ")}: </span>
                        <RenderValue value={v} />
                    </div>
                ))}
            </div>
        );
    }
    return <span>{String(value)}</span>;
}

// ── Section label → icon map ───────────────────────────────────────────────
function SectionIcon({ label }: { label: string }) {
    const l = label.toLowerCase();
    if (l.includes("winning")) return <TrendingUp className="w-4 h-4 text-emerald-400" />;
    if (l.includes("avoid")) return <TrendingDown className="w-4 h-4 text-red-400" />;
    if (l.includes("audience")) return <Users className="w-4 h-4 text-blue-400" />;
    if (l.includes("writing")) return <Sparkles className="w-4 h-4 text-yellow-400" />;
    if (l.includes("style")) return <Eye className="w-4 h-4 text-purple-400" />;
    if (l.includes("deep") || l.includes("structural")) return <Zap className="w-4 h-4 text-cyan-400" />;
    if (l.includes("summary")) return <BarChart3 className="w-4 h-4 text-slate-400" />;
    return <Fingerprint className="w-4 h-4 text-slate-400" />;
}

// ── Analysis progress log line ─────────────────────────────────────────────
interface LogLine { time: string; msg: string; type: "info" | "success" | "error" | "step"; }

export default function ClientIntelligencePage() {
    const [clients, setClients] = useState<ClientOption[]>([]);
    const [selectedClient, setSelectedClient] = useState("");
    const [loading, setLoading] = useState(true);
    const [triggering, setTriggering] = useState(false);
    const [data, setData] = useState<any>(null);
    const [error, setError] = useState("");
    const [dropdownOpen, setDropdownOpen] = useState(false);

    // In-page analysis state
    const [analysisRunning, setAnalysisRunning] = useState(false);
    const [analysisLogs, setAnalysisLogs] = useState<LogLine[]>([]);
    const [analysisDone, setAnalysisDone] = useState(false);
    const logRef = useRef<HTMLDivElement>(null);
    const pollRef = useRef<NodeJS.Timeout | null>(null);

    const addLog = (msg: string, type: LogLine["type"] = "info") => {
        const time = new Date().toLocaleTimeString();
        setAnalysisLogs(prev => [...prev, { time, msg, type }]);
        setTimeout(() => {
            if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
        }, 50);
    };

    // Fetch list of clients on mount
    useEffect(() => {
        const fetchClients = async () => {
            try {
                const res = await fetch("http://localhost:8002/api/v1/clients/");
                if (res.ok) {
                    const json = await res.json();
                    if (json.clients && json.clients.length > 0) {
                        const mappedClients = json.clients.map((client: any) => ({
                            id: client.client_id,
                            label: client.name || client.account_handle || client.client_id,
                            accountHandle: client.account_handle || client.client_id,
                            platformDetails: client.platform_details || {},
                        }));
                        setClients(mappedClients);
                        setSelectedClient(mappedClients[0].id);
                    }
                }
            } catch (err) {
                console.error("Failed to fetch clients", err);
            }
        };
        fetchClients();
    }, []);

    const [dnaData, setDnaData] = useState<any>(null);
    const [activeDnaTab, setActiveDnaTab] = useState<string>("");
    
    // Editor State
    const [editingPlatform, setEditingPlatform] = useState<string | null>(null);
    const [editingDnaContent, setEditingDnaContent] = useState<string>("");
    const [savingDna, setSavingDna] = useState(false);

    // Fetch intelligence data when client changes
    const fetchData = async () => {
        if (!selectedClient) { setLoading(false); return; }
        setLoading(true);
        setError("");
        try {
            const [intelRes, dnaRes] = await Promise.all([
                fetch(`http://localhost:8002/api/v1/intelligence/client/${selectedClient}`),
                arcAgentAPI.getClientDna(selectedClient).catch(() => null)
            ]);
            if (!intelRes.ok) throw new Error("Failed to fetch client intelligence data");
            const json = await intelRes.json();
            setData(json);

            if (dnaRes && dnaRes.platforms_with_dna) {
                setDnaData(dnaRes);
                if (dnaRes.platforms_with_dna.length > 0 && !activeDnaTab) {
                    setActiveDnaTab(dnaRes.platforms_with_dna[0]);
                }
            } else {
                setDnaData(null);
            }
        } catch (err: any) {
            setError(err.message || "An unknown error occurred.");
            setData(null);
            setDnaData(null);
        } finally {
            setLoading(false);
        }
    };

    const handleSaveDna = async () => {
        if (!editingPlatform) return;
        setSavingDna(true);
        try {
            const payload = JSON.parse(editingDnaContent);
            await arcAgentAPI.updateClientDna(selectedClient, editingPlatform, { dna: payload });
            setEditingPlatform(null);
            await fetchData();
        } catch (err: any) {
            alert("Invalid JSON or Save Failed: " + err.message);
        }
        setSavingDna(false);
    };

    useEffect(() => { fetchData(); }, [selectedClient]);

    const triggerEvolution = async () => {
        if (!selectedClient) return;
        setTriggering(true);
        try {
            await fetch(`http://localhost:8002/api/v1/intelligence/client/${selectedClient}/evolve`, { method: "POST" });
            await fetchData();
        } catch (err) { console.error(err); }
        setTriggering(false);
    };

    // ── Run Full Analysis — real-time in-page log ─────────────────────────
    const triggerAnalysis = async () => {
        if (!selectedClient) return;
        const selectedClientData = clients.find(c => c.id === selectedClient);
        const platformEntry = Object.entries(selectedClientData?.platformDetails || {})
            .find(([, details]) => details?.can_research && details?.account_url);

        if (!selectedClientData || !platformEntry) {
            addLog(`No research-ready platform configured for ${selectedClient}.`, "error");
            setAnalysisRunning(true);
            setAnalysisDone(true);
            return;
        }

        const [platform, details] = platformEntry;

        setAnalysisLogs([]);
        setAnalysisRunning(true);
        setAnalysisDone(false);

        addLog(`Starting full pipeline analysis for ${selectedClientData.label}...`, "info");
        addLog(`Platform: ${platform.toUpperCase()}`, "step");
        addLog(`Account: ${details.account_url}`, "step");

        try {
            addLog("Connecting to Nexearch pipeline...", "info");
            const res = await fetch("http://localhost:8002/api/v1/pipeline/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    client_id: selectedClient,
                    platform,
                    account_handle: selectedClientData.accountHandle,
                    account_url: details.account_url,
                }),
            });

            if (!res.ok) throw new Error(`Pipeline rejected request: HTTP ${res.status}`);

            const json = await res.json();
            addLog("Pipeline accepted — analysis started in Nexearch engine.", "success");
            addLog(`Task ID: ${json.task_id || "—"}`, "info");
            addLog("Fetching posts & running tier scoring...", "step");
            addLog("Extracting winning patterns → DNA generation...", "step");
            addLog("Writing evolution directives...", "step");

            // Poll status if task_id returned
            if (json.task_id) {
                let attempts = 0;
                const maxAttempts = 30;
                if (pollRef.current) clearInterval(pollRef.current);
                pollRef.current = setInterval(async () => {
                    attempts++;
                    try {
                        const statusRes = await fetch(
                            `http://localhost:8002/api/v1/pipeline/status/${json.task_id}`
                        );
                        if (statusRes.ok) {
                            const status = await statusRes.json();
                            if (status.message) addLog(status.message, "info");
                            if (status.status === "complete" || status.status === "done") {
                                clearInterval(pollRef.current!);
                                addLog("✓ Analysis complete! DNA updated.", "success");
                                setAnalysisDone(true);
                                await fetchData();
                            } else if (status.status === "error") {
                                clearInterval(pollRef.current!);
                                addLog(`Pipeline error: ${status.error || "unknown"}`, "error");
                                setAnalysisDone(true);
                            }
                        }
                    } catch { /* silent poll failures */ }
                    if (attempts >= maxAttempts) {
                        clearInterval(pollRef.current!);
                        addLog("Pipeline is running in background. Check back in a few minutes.", "info");
                        addLog("✓ Request submitted successfully.", "success");
                        setAnalysisDone(true);
                        await fetchData();
                    }
                }, 3000);
            } else {
                addLog("✓ Analysis submitted. Check results after pipeline completes.", "success");
                setAnalysisDone(true);
                setTimeout(() => fetchData(), 5000);
            }
        } catch (err: any) {
            addLog(`Error: ${err.message}`, "error");
            setAnalysisDone(true);
        }
    };

    const closeAnalysis = () => {
        if (pollRef.current) clearInterval(pollRef.current);
        setAnalysisRunning(false);
        setAnalysisLogs([]);
        setAnalysisDone(false);
    };

    useEffect(() => {
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, []);

    const stats = data?.stats || { s_tier: 0, a_tier: 0, b_tier: 0, c_tier: 0 };
    const totalPosts = stats.s_tier + stats.a_tier + stats.b_tier + stats.c_tier;
    const getPercent = (val: number) => totalPosts > 0 ? ((val / totalPosts) * 100).toFixed(1) : "0.0";

    const dna = data?.dna || { version: "1.0.0", brand_guidelines: {}, winning_patterns: [], avoid_patterns: [] };
    const selectedClientData = clients.find(c => c.id === selectedClient);

    // Build a readable sections map from whatever the API returns
    const dnaSections: { key: string; label: string; value: any }[] = [];
    if (dna.winning_patterns?.length) dnaSections.push({ key: "winning_patterns", label: "Winning Patterns", value: dna.winning_patterns });
    if (dna.avoid_patterns?.length) dnaSections.push({ key: "avoid_patterns", label: "Avoid Patterns", value: dna.avoid_patterns });
    if (dna.audience_profile) dnaSections.push({ key: "audience_profile", label: "Audience Profile", value: dna.audience_profile });
    if (dna.writing_dna) dnaSections.push({ key: "writing_dna", label: "Writing DNA", value: dna.writing_dna });
    if (dna.content_dna_summary) dnaSections.push({ key: "content_dna_summary", label: "Content DNA Summary", value: dna.content_dna_summary });
    if (dna.nexclip_style_recommendation) dnaSections.push({ key: "nexclip_style_recommendation", label: "NexClip Style Recommendation", value: dna.nexclip_style_recommendation });
    if (dna.deep_sti_structural_insights) dnaSections.push({ key: "deep_sti_structural_insights", label: "Deep STI Structural Insights", value: dna.deep_sti_structural_insights });
    // Also render any brand_guidelines sub-fields
    if (dna.brand_guidelines && typeof dna.brand_guidelines === "object") {
        Object.entries(dna.brand_guidelines).forEach(([key, val]) => {
            if (!dnaSections.find(s => s.key === key)) {
                dnaSections.push({ key, label: key.replace(/_/g, " "), value: val });
            }
        });
    }
    // Fallback: render all keys we haven't shown yet
    if (dnaSections.length === 0) {
        Object.entries(dna).forEach(([key, val]) => {
            if (!["version", "brand_guidelines", "winning_patterns", "avoid_patterns"].includes(key)) {
                dnaSections.push({ key, label: key.replace(/_/g, " "), value: val });
            }
        });
    }

    const logTypeStyles: Record<LogLine["type"], string> = {
        info: "text-slate-300",
        success: "text-emerald-400",
        error: "text-red-400",
        step: "text-cyan-300",
    };
    const logTypePrefix: Record<LogLine["type"], string> = {
        info: "ℹ",
        success: "✓",
        error: "✗",
        step: "→",
    };

    return (
        <div style={{ padding: "24px 32px", background: "#0A0A0F", minHeight: "calc(100vh - 64px)", color: "#E2E8F0" }}>
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-3xl font-bold flex items-center gap-3" style={{ background: "linear-gradient(135deg, #10B981, #06B6D4)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                        <BarChart3 className="w-8 h-8 text-emerald-500" />
                        Client Intelligence
                    </h1>
                    <p className="text-sm mt-1" style={{ color: "#94A3B8" }}>
                        Per-client content tiering, brand DNA generation, and audience-specific self-evolution.
                    </p>
                </div>

                {/* Client Selector */}
                <div className="flex gap-3 relative">
                    <button onClick={fetchData} className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 transition-all">
                        <RefreshCw size={16} className={loading && !triggering ? "animate-spin" : ""} />
                    </button>

                    <div className="relative">
                        <button
                            onClick={() => setDropdownOpen(!dropdownOpen)}
                            className="flex items-center gap-3 px-5 py-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors h-full"
                        >
                            <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold text-xs uppercase">
                                {selectedClientData ? selectedClientData.label.substring(0, 2) : "--"}
                            </div>
                            <span className="font-semibold text-white">{selectedClientData?.label || "No Clients Yet"}</span>
                            <ChevronDown className="w-4 h-4 text-slate-400" />
                        </button>

                        {dropdownOpen && clients.length > 0 && (
                            <div className="absolute right-0 top-full mt-2 w-48 bg-slate-900 border border-white/10 rounded-xl shadow-xl overflow-hidden z-50">
                                {clients.map(c => (
                                    <button
                                        key={c.id}
                                        className="w-full text-left px-4 py-3 hover:bg-white/5 text-sm font-semibold border-b border-white/5 last:border-0"
                                        onClick={() => { setSelectedClient(c.id); setDropdownOpen(false); }}
                                    >
                                        {c.label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* ── In-page Analysis Console ─────────────────────────────────── */}
            {analysisRunning && (
                <div className="mb-6 rounded-2xl border border-emerald-500/30 overflow-hidden" style={{ background: "#0D1117" }}>
                    {/* Console header */}
                    <div className="flex items-center justify-between px-5 py-3 border-b border-white/5" style={{ background: "rgba(16,185,129,0.06)" }}>
                        <div className="flex items-center gap-3">
                            {analysisDone
                                ? <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                                : <Loader2 className="w-5 h-5 text-emerald-400 animate-spin" />}
                            <span className="text-sm font-bold text-emerald-300">
                                {analysisDone ? "Analysis Complete" : "Running Full Analysis..."}
                            </span>
                            <span className="text-xs text-slate-500 font-mono">
                                {selectedClientData?.label}
                            </span>
                        </div>
                        <button onClick={closeAnalysis} className="p-1 rounded-lg hover:bg-white/5 text-slate-400 hover:text-white transition-colors">
                            <X size={16} />
                        </button>
                    </div>

                    {/* Log stream */}
                    <div ref={logRef} className="p-4 space-y-1.5 font-mono text-xs max-h-64 overflow-y-auto" style={{ background: "#0D1117" }}>
                        {analysisLogs.map((log, i) => (
                            <div key={i} className="flex gap-3 items-start">
                                <span className="text-slate-600 shrink-0">{log.time}</span>
                                <span className={`shrink-0 ${logTypeStyles[log.type]}`}>{logTypePrefix[log.type]}</span>
                                <span className={logTypeStyles[log.type]}>{log.msg}</span>
                            </div>
                        ))}
                        {!analysisDone && (
                            <div className="flex gap-3 items-center text-slate-600">
                                <span className="text-slate-700">—</span>
                                <span className="animate-pulse">waiting for pipeline...</span>
                            </div>
                        )}
                    </div>

                    {analysisDone && (
                        <div className="px-5 py-3 border-t border-white/5 flex justify-end gap-3">
                            <button onClick={closeAnalysis} className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20 transition-all">
                                Close Console
                            </button>
                            <button onClick={fetchData} className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10 transition-all flex items-center gap-1.5">
                                <RefreshCw size={12} /> Refresh Data
                            </button>
                        </div>
                    )}
                </div>
            )}

            {!selectedClient ? (
                <div className="flex items-center justify-center p-20 text-emerald-500/50 border border-dashed border-emerald-500/20 rounded-xl">
                    Waiting for clients to be added into Nexearch...
                </div>
            ) : loading ? (
                <div className="flex items-center justify-center p-20 text-emerald-400">
                    <Loader2 className="w-10 h-10 animate-spin" />
                </div>
            ) : error ? (
                <div className="p-6 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400">
                    <AlertTriangle className="w-6 h-6 mb-2" />
                    <strong>Failed to load Intelligence Data:</strong> {error}
                </div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                    {/* Left Column: DNA Profile */}
                    <div className="lg:col-span-1 space-y-4">
                        {dnaData && dnaData.platforms_with_dna && dnaData.platforms_with_dna.length > 0 ? (
                            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-5">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-base font-bold text-emerald-400 flex items-center gap-2">
                                        <Fingerprint className="w-4 h-4" /> Account DNA
                                    </h3>
                                    {activeDnaTab && (
                                        <button 
                                            onClick={() => {
                                                setEditingPlatform(activeDnaTab);
                                                setEditingDnaContent(JSON.stringify(dnaData.dna[activeDnaTab].dna, null, 2));
                                            }}
                                            className="text-xs px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded-lg flex items-center gap-1.5 transition-colors border border-emerald-500/20"
                                        >
                                            <Edit3 size={12} /> Edit JSON
                                        </button>
                                    )}
                                </div>
                                
                                <div className="flex gap-2 border-b border-emerald-500/20 pb-0 mb-4 px-1 overflow-x-auto">
                                    {dnaData.platforms_with_dna.map((plat: string) => (
                                        <button
                                            key={plat}
                                            onClick={() => setActiveDnaTab(plat)}
                                            className={`px-3 py-2 text-sm font-bold uppercase tracking-wider whitespace-nowrap transition-colors border-b-2 ${
                                                activeDnaTab === plat
                                                    ? "text-emerald-400 border-emerald-400"
                                                    : "text-slate-500 border-transparent hover:text-slate-300"
                                            }`}
                                        >
                                            {plat}
                                        </button>
                                    ))}
                                </div>

                                {activeDnaTab && dnaData.dna[activeDnaTab] ? (
                                    <div className="space-y-4">
                                        <div className="flex items-center justify-between text-xs text-slate-400 font-mono bg-black/20 p-2 rounded-lg border border-white/5">
                                            <span>v{dnaData.dna[activeDnaTab].version}</span>
                                            <span>{new Date(dnaData.dna[activeDnaTab].updated_at || Date.now()).toLocaleDateString()}</span>
                                        </div>
                                        {Object.entries(dnaData.dna[activeDnaTab].dna).map(([k, v]) => (
                                            <div key={k} className="bg-black/30 rounded-lg p-3 border border-white/5">
                                                <div className="flex items-center gap-1.5 mb-2">
                                                    <SectionIcon label={k.replace(/_/g, " ")} />
                                                    <div className="text-[10px] text-emerald-300 font-bold uppercase tracking-wider">
                                                        {k.replace(/_/g, " ")}
                                                    </div>
                                                </div>
                                                <div className="text-sm text-slate-300 leading-relaxed">
                                                    <RenderValue value={v} />
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-sm text-emerald-500/40 text-center py-8">Select a platform</div>
                                )}
                                
                                <div className="mt-5 pt-4 border-t border-white/5">
                                    <button onClick={triggerEvolution} disabled={triggering} className="w-full py-2 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 rounded-lg text-sm font-semibold hover:bg-emerald-500/20 transition-all flex items-center justify-center gap-2 disabled:opacity-50">
                                        {triggering ? <Loader2 className="w-4 h-4 animate-spin" /> : <GitCommit className="w-4 h-4" />} Force Target Evolution
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-5">
                                <h3 className="text-base font-bold text-emerald-400 flex items-center gap-2 mb-4">
                                    <Fingerprint className="w-4 h-4" /> Account DNA
                                </h3>
                                <div className="text-sm text-emerald-500/40 text-center py-8 border border-dashed border-emerald-500/20 rounded-lg">
                                    No Brand DNA yet.<br /><br />Run analysis pipeline to generate.
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Right Area: Stats + Logs + Run Analysis */}
                    <div className="lg:col-span-3 space-y-6">
                        {/* Stats Row */}
                        <div className="grid grid-cols-4 gap-4">
                            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                                <div className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">Posts Analyzed</div>
                                <div className="text-2xl font-black text-white">{totalPosts}</div>
                            </div>
                            <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-xl p-4">
                                <div className="text-indigo-400 text-xs font-bold uppercase tracking-wider mb-1">S-Tier Posts</div>
                                <div className="text-2xl font-black text-indigo-300 flex items-center gap-2">
                                    {stats.s_tier} <span className="text-xs font-normal text-indigo-400/60">({getPercent(stats.s_tier)}%)</span>
                                </div>
                            </div>
                            <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4">
                                <div className="text-emerald-400 text-xs font-bold uppercase tracking-wider mb-1">A-Tier Posts</div>
                                <div className="text-2xl font-black text-emerald-300 flex items-center gap-2">
                                    {stats.a_tier} <span className="text-xs font-normal text-emerald-400/60">({getPercent(stats.a_tier)}%)</span>
                                </div>
                            </div>
                            <div className="bg-white/5 border border-white/10 rounded-xl p-4 flex items-center justify-center">
                                <button
                                    onClick={triggerAnalysis}
                                    disabled={analysisRunning && !analysisDone}
                                    className="flex items-center gap-2 px-4 py-2 bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded-lg hover:bg-blue-500/30 transition-all font-semibold text-sm disabled:opacity-50 w-full justify-center"
                                >
                                    {analysisRunning && !analysisDone
                                        ? <><Loader2 className="w-4 h-4 animate-spin" /> Running...</>
                                        : <><Play className="w-4 h-4" /> Run Full Analysis</>
                                    }
                                </button>
                            </div>
                        </div>

                        {/* B/C Tier quick stats */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
                                <div className="text-blue-400 text-xs font-bold uppercase tracking-wider mb-1">B-Tier Posts</div>
                                <div className="text-2xl font-black text-blue-300 flex items-center gap-2">
                                    {stats.b_tier} <span className="text-xs font-normal text-blue-400/60">({getPercent(stats.b_tier)}%)</span>
                                </div>
                            </div>
                            <div className="bg-slate-500/10 border border-slate-500/20 rounded-xl p-4">
                                <div className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">C-Tier Posts</div>
                                <div className="text-2xl font-black text-slate-300 flex items-center gap-2">
                                    {stats.c_tier} <span className="text-xs font-normal text-slate-400/60">({getPercent(stats.c_tier)}%)</span>
                                </div>
                            </div>
                        </div>

                        {/* Evolution Logs */}
                        <div className="bg-white/5 border border-white/10 rounded-xl p-6">
                            <div className="flex items-center justify-between mb-5">
                                <h3 className="text-base font-bold text-white flex items-center gap-2">
                                    <Shield className="w-4 h-4 text-slate-400" /> Client Evolution Records
                                </h3>
                                <div className="flex items-center gap-2">
                                    <span className="text-[10px] text-emerald-400/70 border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 rounded-full uppercase tracking-wider font-bold">DNA Injected to Pipeline</span>
                                    <span className="text-xs text-slate-500">{data?.evolution_logs?.length || 0} records</span>
                                </div>
                            </div>

                            <div className="space-y-4">
                                {data?.evolution_logs && data.evolution_logs.length > 0 ? (
                                    data.evolution_logs.slice(0, 8).map((log: any, i: number) => (
                                        <div key={i} 
                                            className="flex items-start gap-4 p-4 bg-black/40 rounded-lg border border-indigo-500/20 hover:border-indigo-500/40 transition-colors cursor-pointer"
                                            onClick={() => {
                                                if (dnaData && dnaData.platforms_with_dna.includes(log.platform)) {
                                                    setActiveDnaTab(log.platform);
                                                    window.scrollTo({ top: 0, behavior: 'smooth' });
                                                }
                                            }}
                                        >
                                            <div className="w-9 h-9 bg-indigo-500/20 rounded flex items-center justify-center border border-indigo-500/50 shrink-0">
                                                <Fingerprint className="w-4 h-4 text-indigo-400" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="text-sm font-bold text-white mb-1 break-words">{log.change_summary}</div>
                                                <div className="text-xs text-slate-400">Triggered by <span className="text-slate-300 font-semibold capitalize">{log.platform}</span> insights</div>
                                                {log.patterns_added?.length > 0 && (
                                                    <div className="mt-2 flex flex-wrap gap-1">
                                                        {log.patterns_added.slice(0, 3).map((p: string, j: number) => (
                                                            <span key={j} className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">+{p}</span>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                            <div className="text-right shrink-0">
                                                <div className="text-xs text-indigo-400 font-bold flex items-center justify-end gap-1">
                                                    <CheckCircle2 className="w-3 h-3" /> DNA Updated
                                                </div>
                                                <div className="text-[10px] text-slate-500 mt-1 uppercase">
                                                    {new Date(log.timestamp).toLocaleDateString()}
                                                </div>
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <div className="flex items-center gap-4 p-6 bg-black/20 rounded-lg border border-dashed border-white/10 text-center justify-center">
                                        <div>
                                            <Clock className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                                            <div className="text-sm font-bold text-slate-400">No evolution records yet</div>
                                            <div className="text-xs text-slate-600 mt-1">Run Full Analysis to generate the first DNA evolution cycle.</div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Editor Modal */}
            {editingPlatform && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
                    <div className="bg-[#0D1117] border border-emerald-500/30 rounded-2xl w-full max-w-4xl shadow-2xl flex flex-col mx-auto" style={{ maxHeight: "90vh" }}>
                        <div className="flex items-center justify-between p-5 border-b border-white/10">
                            <div>
                                <h3 className="text-lg font-bold text-emerald-400 flex items-center gap-2">
                                    <Settings size={18} /> Edit Account DNA
                                </h3>
                                <p className="text-xs text-emerald-500/60 mt-1 uppercase tracking-wider font-bold">
                                    {selectedClient} • {editingPlatform} • Modify with precautions
                                </p>
                            </div>
                            <button onClick={() => setEditingPlatform(null)} className="text-slate-400 hover:text-white transition-colors p-2 rounded-lg hover:bg-white/5">
                                <X size={20} />
                            </button>
                        </div>
                        <div className="p-5 flex-1 overflow-hidden flex flex-col">
                            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 mb-4 flex items-start gap-3 shrink-0">
                                <AlertTriangle className="text-red-400 shrink-0 mt-0.5" size={16} />
                                <div className="text-xs text-red-300 leading-relaxed">
                                    <strong>Warning:</strong> You are directly modifying the generated Account DNA JSON signature. Nexearch AI relies on these structural insights to architect content. Invalid JSON or malformed patterns can cause generation failures.
                                </div>
                            </div>
                            <textarea
                                value={editingDnaContent}
                                onChange={(e) => setEditingDnaContent(e.target.value)}
                                className="w-full flex-1 bg-black/50 border border-white/10 rounded-xl p-4 text-emerald-300 font-mono text-xs leading-relaxed focus:outline-none focus:border-emerald-500/50 resize-none"
                                spellCheck={false}
                            />
                        </div>
                        <div className="p-5 border-t border-white/10 flex justify-end gap-3 bg-white/5 shrink-0">
                            <button onClick={() => setEditingPlatform(null)} className="px-5 py-2.5 rounded-lg text-sm font-semibold text-slate-300 hover:bg-white/5 transition-colors border border-white/10">
                                Cancel
                            </button>
                            <button 
                                onClick={handleSaveDna}
                                disabled={savingDna}
                                className="px-5 py-2.5 rounded-lg text-sm font-semibold flex items-center gap-2 transition-all bg-emerald-500 text-black hover:bg-emerald-400 disabled:opacity-50"
                            >
                                {savingDna ? <><Loader2 size={16} className="animate-spin" /> Saving...</> : <><Save size={16} /> Save Changes</>}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
