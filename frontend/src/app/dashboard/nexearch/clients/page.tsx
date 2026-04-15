"use client";

import { useState, useEffect, useCallback } from "react";
import {
    Users, Globe, Brain, Activity, ChevronRight,
    RefreshCw, Search, Plus, X, Check, Loader2,
    Link2, Key, Lock, Eye, EyeOff, Upload, Search as SearchIcon, AlertTriangle,
    Zap, Shield, ExternalLink, CheckCircle2, XCircle, Info,
    Trash2, ArrowLeft, Copy, CheckCheck, BarChart3, Edit3, Save,
    ShieldCheck, ShieldAlert, ShieldX, BadgeCheck
} from "lucide-react";
import { arcAgentAPI } from "@/lib/api";

/* ════════════════════════════════════════════════════════════
   NEXEARCH CLIENTS — Full credential management + verification
   ════════════════════════════════════════════════════════════ */

const PLATFORMS = ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook", "threads"];
const PLATFORM_COLORS: Record<string, string> = {
    instagram: "#E4405F", tiktok: "#00F2EA", youtube: "#FF0000",
    linkedin: "#0A66C2", twitter: "#1DA1F2", facebook: "#1877F2",
    threads: "#AAAAAA",
};
const PLATFORM_LABELS: Record<string, string> = {
    instagram: "Instagram", tiktok: "TikTok", youtube: "YouTube",
    linkedin: "LinkedIn", twitter: "X / Twitter", facebook: "Facebook",
    threads: "Threads",
};
const URL_PLACEHOLDERS: Record<string, string> = {
    instagram: "https://instagram.com/username",
    tiktok: "https://tiktok.com/@username",
    youtube: "https://youtube.com/@channel",
    linkedin: "https://linkedin.com/in/username",
    twitter: "https://x.com/username",
    facebook: "https://facebook.com/pagename",
    threads: "https://threads.net/@username",
};
const LOGIN_LABEL_MAP: Record<string, string> = {
    instagram: "Instagram Username",
    tiktok: "TikTok Username",
    youtube: "Google Email",
    linkedin: "LinkedIn Email",
    twitter: "Twitter/X Username",
    facebook: "Facebook Email",
    threads: "Threads Username",
};

interface PlatformCreds {
    account_url: string;
    login_username: string;
    login_password: string;
    access_token: string;
    api_key: string;
    page_id: string;
    metricool_api_key: string;
    buffer_api_key: string;
}

const emptyCreds = (): PlatformCreds => ({
    account_url: "", login_username: "", login_password: "",
    access_token: "", api_key: "", page_id: "",
    metricool_api_key: "", buffer_api_key: "",
});

interface VerificationResult {
    verified: boolean;
    method: string;
    message?: string;
    error?: string;
}
interface PlatformVerification {
    overall_verified: boolean;
    overall_error_summary?: string;
    verifications: Record<string, VerificationResult>;
}

// ── Utility: mask secrets ────────────────────────────────────────────────────
function maskSecret(val: string) {
    if (!val) return "—";
    if (val.length <= 8) return "••••••••";
    return val.slice(0, 4) + "••••" + val.slice(-4);
}

// ── Copy button ──────────────────────────────────────────────────────────────
function CopyButton({ value }: { value: string }) {
    const [copied, setCopied] = useState(false);
    const copy = () => {
        navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };
    return (
        <button onClick={copy} className="p-1 rounded hover:bg-white/10 text-slate-500 hover:text-white transition-colors" title="Copy">
            {copied ? <CheckCheck size={12} style={{ color: "#10B981" }} /> : <Copy size={12} />}
        </button>
    );
}

// ── Editable credential row ──────────────────────────────────────────────────
function EditableCredRow({
    label, field, value, secret = false, editing, onChange, placeholder,
}: {
    label: string; field: string; value?: string; secret?: boolean;
    editing: boolean; onChange: (v: string) => void; placeholder?: string;
}) {
    const [show, setShow] = useState(false);
    if (!editing && !value) return null;
    const display = secret && !show ? maskSecret(value || "") : (value || "");

    return (
        <div className="flex items-start justify-between py-2 border-b border-white/5 last:border-0 gap-3">
            <span className="text-xs text-slate-500 font-semibold uppercase tracking-wider w-36 shrink-0 mt-1.5">{label}</span>
            {editing ? (
                <div className="relative flex-1">
                    <input
                        type={secret && !show ? "password" : "text"}
                        value={value || ""}
                        onChange={e => onChange(e.target.value)}
                        placeholder={placeholder || label}
                        className="w-full rounded-lg px-3 py-1.5 text-xs outline-none transition-all focus:ring-1 focus:ring-purple-500/30"
                        style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.12)", color: "#E2E8F0" }}
                    />
                    {secret && (
                        <button
                            onClick={() => setShow(!show)}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
                            type="button"
                        >
                            {show ? <EyeOff size={12} /> : <Eye size={12} />}
                        </button>
                    )}
                </div>
            ) : (
                <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className="text-xs text-slate-300 font-mono truncate">{display}</span>
                    {secret && (
                        <button onClick={() => setShow(!show)} className="p-1 rounded hover:bg-white/10 text-slate-500 hover:text-white transition-colors">
                            {show ? <EyeOff size={12} /> : <Eye size={12} />}
                        </button>
                    )}
                    {show && value && <CopyButton value={value} />}
                </div>
            )}
        </div>
    );
}

// ── Verification badge for a single method ───────────────────────────────────
function VerificationBadge({ result }: { result: VerificationResult }) {
    if (result.verified) {
        return (
            <div className="flex items-start gap-2 p-2 rounded-lg" style={{ background: "rgba(16,185,129,0.07)", border: "1px solid rgba(16,185,129,0.15)" }}>
                <CheckCircle2 size={13} className="shrink-0 mt-0.5" style={{ color: "#10B981" }} />
                <span className="text-[11px] text-emerald-300 leading-relaxed">{result.message}</span>
            </div>
        );
    }
    return (
        <div className="flex items-start gap-2 p-2 rounded-lg" style={{ background: "rgba(239,68,68,0.07)", border: "1px solid rgba(239,68,68,0.15)" }}>
            <XCircle size={13} className="shrink-0 mt-0.5" style={{ color: "#EF4444" }} />
            <span className="text-[11px] text-red-300 leading-relaxed">{result.error}</span>
        </div>
    );
}

// ── Client Detail Panel ──────────────────────────────────────────────────────
function ClientDetailPanel({
    client, onClose, onDelete, onRefresh,
}: {
    client: any; onClose: () => void; onDelete: () => void; onRefresh: () => Promise<void>;
}) {
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [deleting, setDeleting] = useState(false);

    // Edit state per platform
    const [editingPlatform, setEditingPlatform] = useState<string | null>(null);
    const [editCreds, setEditCreds] = useState<PlatformCreds>(emptyCreds());
    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState("");

    // Verification state per platform
    const [verifying, setVerifying] = useState<string | null>(null);
    const [verificationResults, setVerificationResults] = useState<Record<string, PlatformVerification>>({});
    const [verifyError, setVerifyError] = useState<Record<string, string>>({});

    // Add new platform state
    const [showAddPlatform, setShowAddPlatform] = useState(false);
    const [newPlatform, setNewPlatform] = useState("");
    const [newPlatformCreds, setNewPlatformCreds] = useState<PlatformCreds>(emptyCreds());
    const [addingPlatform, setAddingPlatform] = useState(false);
    const [addError, setAddError] = useState("");

    // DNA tab state
    const [activeTab, setActiveTab] = useState<"credentials" | "dna">("credentials");
    const [dnaData, setDnaData] = useState<any>(null);
    const [loadingDna, setLoadingDna] = useState(false);

    const fetchDna = useCallback(async () => {
        if (loadingDna) return;
        setLoadingDna(true);
        try {
            const res = await arcAgentAPI.getClientDna(client.client_id);
            setDnaData(res);
        } catch {
            setDnaData(null);
        }
        setLoadingDna(false);
    }, [client.client_id, loadingDna]);

    useEffect(() => {
        if (activeTab === "dna" && !dnaData && !loadingDna) {
            fetchDna();
        }
    }, [activeTab]);

    const platforms: string[] = client.platforms || [];
    const pd: Record<string, any> = client.platform_details || {};
    const caps = client.capabilities || {};

    const getCredsFromStore = (p: string): PlatformCreds => {
        const details = pd[p] || {};
        const creds = details.credentials || details || {};
        return {
            account_url: creds.account_url || details.account_url || "",
            login_username: creds.login_username || "",
            login_password: creds.login_password || "",
            access_token: creds.access_token || "",
            api_key: creds.api_key || "",
            page_id: creds.page_id || "",
            metricool_api_key: creds.metricool_api_key || "",
            buffer_api_key: creds.buffer_api_key || "",
        };
    };

    const startEdit = (p: string) => {
        setEditCreds(getCredsFromStore(p));
        setEditingPlatform(p);
        setSaveError("");
    };

    const cancelEdit = () => {
        setEditingPlatform(null);
        setSaveError("");
    };

    const saveEdit = async (p: string) => {
        setSaving(true);
        setSaveError("");
        try {
            const credentials: Record<string, string> = {};
            (Object.keys(editCreds) as Array<keyof PlatformCreds>).forEach(k => {
                if (editCreds[k].trim()) credentials[k] = editCreds[k].trim();
            });
            await arcAgentAPI.updateClient(client.client_id, { platform: p, credentials });
            setEditingPlatform(null);
            await onRefresh();
        } catch (err: any) {
            setSaveError(err?.message || "Failed to save credentials");
        }
        setSaving(false);
    };

    const verifySinglePlatform = async (p: string) => {
        setVerifying(p);
        setVerifyError(prev => ({ ...prev, [p]: "" }));
        try {
            const res = await arcAgentAPI.verifyClient(client.client_id, { platform: p });
            const platformResult = res.results?.[p];
            if (platformResult) {
                setVerificationResults(prev => ({ ...prev, [p]: platformResult }));
            }
        } catch (err: any) {
            setVerifyError(prev => ({ ...prev, [p]: err?.message || "Verification failed" }));
        }
        setVerifying(null);
    };

    const addNewPlatform = async () => {
        if (!newPlatform) return;
        const hasCreds = Object.values(newPlatformCreds).some(v => v.trim());
        if (!hasCreds) {
            setAddError("At least one credential (page URL, API key, or login) is required.");
            return;
        }
        setAddingPlatform(true);
        setAddError("");
        try {
            const credentials: Record<string, string> = {};
            (Object.keys(newPlatformCreds) as Array<keyof PlatformCreds>).forEach(k => {
                if (newPlatformCreds[k].trim()) credentials[k] = newPlatformCreds[k].trim();
            });
            await arcAgentAPI.updateClient(client.client_id, {
                add_platform: newPlatform,
                add_credentials: credentials,
            });
            setShowAddPlatform(false);
            setNewPlatform("");
            setNewPlatformCreds(emptyCreds());
            await onRefresh();
        } catch (err: any) {
            setAddError(err?.message || "Failed to add platform");
        }
        setAddingPlatform(false);
    };

    const handleDelete = async () => {
        setDeleting(true);
        try {
            await arcAgentAPI.deleteClient(client.client_id);
            onDelete();
        } catch (err) {
            console.error("Delete failed", err);
            setDeleting(false);
            setShowDeleteConfirm(false);
        }
    };

    const getMethodBadge = (pCreds: any) => {
        if (!pCreds) return null;
        if (pCreds.metricool_api_key) return { label: "Metricool API", color: "#EC4899" };
        if (pCreds.buffer_api_key) return { label: "Buffer API", color: "#3B82F6" };
        if (pCreds.access_token || pCreds.api_key) return { label: "Platform API", color: "#F59E0B" };
        if (pCreds.login_username) return { label: "Login Credentials", color: "#8B5CF6" };
        if (pCreds.account_url) return { label: "Page Link Only", color: "#06B6D4" };
        return null;
    };

    const getVerificationIcon = (p: string) => {
        const vr = verificationResults[p];
        if (!vr) return null;
        if (vr.overall_verified) return <span title="Credentials verified"><BadgeCheck size={14} style={{ color: "#10B981" }} /></span>;
        return <span title="Verification failed"><ShieldAlert size={14} style={{ color: "#EF4444" }} /></span>;
    };

    const inputStyle = {
        background: "rgba(255,255,255,0.05)",
        border: "1px solid rgba(255,255,255,0.1)",
        color: "#E2E8F0",
    };

    const availablePlatformsToAdd = PLATFORMS.filter(p => !platforms.includes(p));

    return (
        <div className="fixed inset-0 z-50 flex justify-end" style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(8px)" }}>
            <div
                className="h-full overflow-y-auto flex flex-col"
                style={{ width: "560px", background: "#0F0F18", borderLeft: "1px solid rgba(255,255,255,0.06)", boxShadow: "-24px 0 64px rgba(0,0,0,0.6)" }}
            >
                {/* ─── Header ─── */}
                <div className="flex items-center justify-between p-5 border-b sticky top-0 z-10" style={{ borderColor: "rgba(255,255,255,0.06)", background: "#0F0F18" }}>
                    <button onClick={onClose} className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors">
                        <ArrowLeft size={16} /> Back to Clients
                    </button>
                    <button
                        onClick={() => setShowDeleteConfirm(true)}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                        style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)", color: "#EF4444" }}
                    >
                        <Trash2 size={13} /> Delete Client
                    </button>
                </div>

                {/* ─── Client Identity ─── */}
                <div className="p-5 border-b" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                    <div className="flex items-center gap-4">
                        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-500/20 to-cyan-500/20 flex items-center justify-center text-2xl font-black text-white border border-white/10">
                            {(client.name || client.client_id || "?").slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                            <div className="text-lg font-bold text-white">{client.name || client.account_handle || client.client_id}</div>
                            <div className="text-xs text-slate-500 font-mono mt-0.5">{client.client_id}</div>
                            <div className="flex gap-2 mt-2">
                                {caps.total_researchable > 0 && (
                                    <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold" style={{ background: "rgba(6,182,212,0.1)", color: "#06B6D4" }}>
                                        {caps.total_researchable} Researchable
                                    </span>
                                )}
                                {caps.total_uploadable > 0 && (
                                    <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold" style={{ background: "rgba(16,185,129,0.1)", color: "#10B981" }}>
                                        {caps.total_uploadable} Uploadable
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* ─── Platform Configurations ─── */}
                <div className="p-5 space-y-4 flex-1">
                    <div className="flex items-center justify-between mb-1">
                        <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Platform Configuration</div>
                        {availablePlatformsToAdd.length > 0 && (
                            <button
                                onClick={() => { setShowAddPlatform(true); setNewPlatform(""); setNewPlatformCreds(emptyCreds()); setAddError(""); }}
                                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all"
                                style={{ background: "rgba(139,92,246,0.1)", border: "1px solid rgba(139,92,246,0.2)", color: "#8B5CF6" }}
                            >
                                <Plus size={12} /> Add Platform
                            </button>
                        )}
                    </div>

                    {/* Add New Platform Panel */}
                    {showAddPlatform && (
                        <div className="rounded-xl p-4 space-y-3" style={{ background: "rgba(139,92,246,0.05)", border: "1px solid rgba(139,92,246,0.2)" }}>
                            <div className="flex items-center justify-between">
                                <div className="text-xs font-bold text-purple-400">Add New Platform</div>
                                <button onClick={() => setShowAddPlatform(false)} className="text-slate-500 hover:text-white">
                                    <X size={14} />
                                </button>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {availablePlatformsToAdd.map(p => (
                                    <button key={p} onClick={() => setNewPlatform(p)}
                                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                                        style={{
                                            background: newPlatform === p ? `${PLATFORM_COLORS[p]}20` : "rgba(255,255,255,0.03)",
                                            border: `1px solid ${newPlatform === p ? PLATFORM_COLORS[p] + "60" : "rgba(255,255,255,0.06)"}`,
                                            color: newPlatform === p ? PLATFORM_COLORS[p] : "#64748B",
                                        }}>
                                        {newPlatform === p && <Check size={11} />}
                                        <Globe size={11} /> {PLATFORM_LABELS[p]}
                                    </button>
                                ))}
                            </div>
                            {newPlatform && (
                                <div className="space-y-4 pt-2">
                                    {/* Method 1: Page Link */}
                                    <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
                                        <div className="flex items-center gap-2 mb-2">
                                            <Link2 size={13} style={{ color: "#06B6D4" }} />
                                            <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 1: Account Link</span>
                                        </div>
                                        <input value={newPlatformCreds.account_url} onChange={e => setNewPlatformCreds(prev => ({ ...prev, account_url: e.target.value }))} placeholder={URL_PLACEHOLDERS[newPlatform]} className="w-full rounded-lg px-3 py-2 text-xs outline-none" style={inputStyle} />
                                    </div>

                                    {/* Method 2: Metricool */}
                                    <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
                                        <div className="flex items-center gap-2 mb-2">
                                            <BarChart3 size={13} style={{ color: "#EC4899" }} />
                                            <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 2: Metricool API</span>
                                        </div>
                                        <input value={newPlatformCreds.metricool_api_key} onChange={e => setNewPlatformCreds(prev => ({ ...prev, metricool_api_key: e.target.value }))} placeholder="Metricool API Key" className="w-full rounded-lg px-3 py-2 text-xs outline-none" style={inputStyle} />
                                    </div>

                                    {/* Method 3: Buffer */}
                                    <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
                                        <div className="flex items-center gap-2 mb-2">
                                            <Zap size={13} style={{ color: "#3B82F6" }} />
                                            <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 3: Buffer API</span>
                                        </div>
                                        <input value={newPlatformCreds.buffer_api_key} onChange={e => setNewPlatformCreds(prev => ({ ...prev, buffer_api_key: e.target.value }))} placeholder="Buffer API Key" className="w-full rounded-lg px-3 py-2 text-xs outline-none" style={inputStyle} />
                                    </div>

                                    {/* Method 4: Platform API */}
                                    <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
                                        <div className="flex items-center gap-2 mb-2">
                                            <Key size={13} style={{ color: "#F59E0B" }} />
                                            <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 4: Platform API</span>
                                        </div>
                                        <div className="grid grid-cols-2 gap-2">
                                            <input value={newPlatformCreds.access_token} onChange={e => setNewPlatformCreds(prev => ({ ...prev, access_token: e.target.value }))} placeholder="Access Token" className="rounded-lg px-3 py-2 text-xs outline-none" style={inputStyle} />
                                            <input value={newPlatformCreds.api_key} onChange={e => setNewPlatformCreds(prev => ({ ...prev, api_key: e.target.value }))} placeholder="API Key (optional)" className="rounded-lg px-3 py-2 text-xs outline-none" style={inputStyle} />
                                        </div>
                                    </div>

                                    {/* Method 5: Login */}
                                    <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
                                        <div className="flex items-center gap-2 mb-2">
                                            <Lock size={13} style={{ color: "#8B5CF6" }} />
                                            <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 5: Login Credentials</span>
                                        </div>
                                        <div className="grid grid-cols-2 gap-2">
                                            <input value={newPlatformCreds.login_username} onChange={e => setNewPlatformCreds(prev => ({ ...prev, login_username: e.target.value }))} placeholder={LOGIN_LABEL_MAP[newPlatform] || "Username"} className="rounded-lg px-3 py-2 text-xs outline-none" style={inputStyle} />
                                            <input type="password" value={newPlatformCreds.login_password} onChange={e => setNewPlatformCreds(prev => ({ ...prev, login_password: e.target.value }))} placeholder="Password" className="rounded-lg px-3 py-2 text-xs outline-none" style={inputStyle} />
                                        </div>
                                    </div>
                                    <p className="text-[10px] text-slate-500 text-center pb-2">Fill in at least ONE method above.</p>
                                </div>
                            )}
                            {addError && (
                                <div className="flex items-center gap-2 text-xs text-red-300 p-2 rounded-lg" style={{ background: "rgba(239,68,68,0.08)" }}>
                                    <AlertTriangle size={12} />{addError}
                                </div>
                            )}
                            {newPlatform && (
                                <button
                                    onClick={addNewPlatform}
                                    disabled={addingPlatform}
                                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold w-full justify-center transition-all"
                                    style={{ background: "linear-gradient(135deg, #8B5CF6, #06B6D4)", color: "#fff", opacity: addingPlatform ? 0.6 : 1 }}
                                >
                                    {addingPlatform ? <><Loader2 size={12} className="animate-spin" /> Adding...</> : <><Plus size={12} /> Add {PLATFORM_LABELS[newPlatform]}</>}
                                </button>
                            )}
                        </div>
                    )}

                    {platforms.length === 0 ? (
                        <div className="text-sm text-slate-500 text-center py-8 border border-dashed border-white/10 rounded-xl">
                            No platforms configured yet.
                        </div>
                    ) : (
                        platforms.map((p: string) => {
                            const details = pd[p] || {};
                            const creds = details.credentials || details || {};
                            const method = getMethodBadge(creds);
                            const canResearch = details.can_research || false;
                            const canUpload = details.can_upload || false;
                            const isEditing = editingPlatform === p;
                            const vr = verificationResults[p];
                            const isVerifying = verifying === p;

                            return (
                                <div key={p} className="rounded-xl overflow-hidden" style={{ background: "rgba(255,255,255,0.02)", border: `1px solid ${PLATFORM_COLORS[p] || "#8B5CF6"}20` }}>
                                    {/* Platform header */}
                                    <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "rgba(255,255,255,0.05)", background: `${PLATFORM_COLORS[p] || "#8B5CF6"}08` }}>
                                        <div className="flex items-center gap-2.5">
                                            <Globe size={15} style={{ color: PLATFORM_COLORS[p] }} />
                                            <span className="text-sm font-bold text-white">{PLATFORM_LABELS[p] || p}</span>
                                            {getVerificationIcon(p)}
                                            <div className="flex items-center gap-1.5">
                                                {canResearch && (
                                                    <span className="text-[9px] px-1.5 py-0.5 rounded-full font-bold" style={{ background: "rgba(6,182,212,0.1)", color: "#06B6D4" }}>Research</span>
                                                )}
                                                {canUpload && (
                                                    <span className="text-[9px] px-1.5 py-0.5 rounded-full font-bold" style={{ background: "rgba(16,185,129,0.1)", color: "#10B981" }}>Upload</span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {!isEditing && (
                                                <>
                                                    <button
                                                        onClick={() => verifySinglePlatform(p)}
                                                        disabled={isVerifying}
                                                        className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-semibold transition-all"
                                                        style={{ background: "rgba(6,182,212,0.08)", border: "1px solid rgba(6,182,212,0.2)", color: "#06B6D4", opacity: isVerifying ? 0.6 : 1 }}
                                                    >
                                                        {isVerifying ? <Loader2 size={10} className="animate-spin" /> : <ShieldCheck size={10} />}
                                                        Verify
                                                    </button>
                                                    <button
                                                        onClick={() => startEdit(p)}
                                                        className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-semibold transition-all"
                                                        style={{ background: "rgba(139,92,246,0.08)", border: "1px solid rgba(139,92,246,0.2)", color: "#8B5CF6" }}
                                                    >
                                                        <Edit3 size={10} /> Edit
                                                    </button>
                                                </>
                                            )}
                                            {isEditing && (
                                                <>
                                                    <button
                                                        onClick={() => saveEdit(p)}
                                                        disabled={saving}
                                                        className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-semibold transition-all"
                                                        style={{ background: "linear-gradient(135deg, #8B5CF6, #06B6D4)", color: "#fff", opacity: saving ? 0.7 : 1 }}
                                                    >
                                                        {saving ? <Loader2 size={10} className="animate-spin" /> : <Save size={10} />}
                                                        Save
                                                    </button>
                                                    <button onClick={cancelEdit} className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-semibold text-slate-400 hover:text-white border border-white/10 transition-all">
                                                        <X size={10} /> Cancel
                                                    </button>
                                                </>
                                            )}
                                        </div>
                                    </div>

                                    {/* Active method badge */}
                                    {method && !isEditing && (
                                        <div className="px-4 py-2 border-b" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
                                            <div className="flex items-center gap-2">
                                                <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Active Method:</span>
                                                <span className="text-[10px] px-2 py-0.5 rounded-full font-bold" style={{ background: `${method.color}15`, color: method.color }}>
                                                    {method.label}
                                                </span>
                                            </div>
                                        </div>
                                    )}

                                    {/* Credential rows (Categorized) */}
                                    <div className="px-4 py-3 space-y-4">
                                        {/* Method 1: Page Link */}
                                        <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)" }}>
                                            <div className="flex items-center gap-2 mb-2">
                                                <Link2 size={13} style={{ color: "#06B6D4" }} />
                                                <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 1: Account Link</span>
                                                <span className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold" style={{ background: "rgba(239,68,68,0.15)", color: "#EF4444" }}>Required</span>
                                            </div>
                                            <EditableCredRow label="Account URL" field="account_url" value={isEditing ? editCreds.account_url : (creds.account_url || details.account_url)} secret={false} editing={isEditing} onChange={v => setEditCreds(prev => ({ ...prev, account_url: v }))} placeholder={URL_PLACEHOLDERS[p]} />
                                        </div>

                                        {/* Method 2: Metricool */}
                                        <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)" }}>
                                            <div className="flex items-center gap-2 mb-2">
                                                <BarChart3 size={13} style={{ color: "#EC4899" }} />
                                                <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 2: Metricool API</span>
                                                <span className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold" style={{ background: "rgba(16,185,129,0.1)", color: "#10B981" }}>Research + Upload</span>
                                            </div>
                                            <EditableCredRow label="Metricool Key" field="metricool_api_key" value={isEditing ? editCreds.metricool_api_key : creds.metricool_api_key} secret editing={isEditing} onChange={v => setEditCreds(prev => ({ ...prev, metricool_api_key: v }))} />
                                        </div>

                                        {/* Method 3: Buffer */}
                                        <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)" }}>
                                            <div className="flex items-center gap-2 mb-2">
                                                <Zap size={13} style={{ color: "#3B82F6" }} />
                                                <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 3: Buffer API</span>
                                                <span className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold" style={{ background: "rgba(16,185,129,0.1)", color: "#10B981" }}>Research + Upload</span>
                                            </div>
                                            <EditableCredRow label="Buffer Key" field="buffer_api_key" value={isEditing ? editCreds.buffer_api_key : creds.buffer_api_key} secret editing={isEditing} onChange={v => setEditCreds(prev => ({ ...prev, buffer_api_key: v }))} />
                                        </div>

                                        {/* Method 4: Platform API */}
                                        <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)" }}>
                                            <div className="flex items-center gap-2 mb-2">
                                                <Key size={13} style={{ color: "#F59E0B" }} />
                                                <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 4: Platform API</span>
                                                <span className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold" style={{ background: "rgba(16,185,129,0.1)", color: "#10B981" }}>Research + Upload</span>
                                            </div>
                                            <EditableCredRow label="Access Token" field="access_token" value={isEditing ? editCreds.access_token : creds.access_token} secret editing={isEditing} onChange={v => setEditCreds(prev => ({ ...prev, access_token: v }))} />
                                            <EditableCredRow label="API Key" field="api_key" value={isEditing ? editCreds.api_key : creds.api_key} secret editing={isEditing} onChange={v => setEditCreds(prev => ({ ...prev, api_key: v }))} />
                                            <EditableCredRow label="Page ID" field="page_id" value={isEditing ? editCreds.page_id : creds.page_id} secret={false} editing={isEditing} onChange={v => setEditCreds(prev => ({ ...prev, page_id: v }))} />
                                        </div>

                                        {/* Method 5: Login */}
                                        <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)" }}>
                                            <div className="flex items-center gap-2 mb-2">
                                                <Lock size={13} style={{ color: "#8B5CF6" }} />
                                                <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 5: Login Credentials</span>
                                                <span className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold" style={{ background: "rgba(16,185,129,0.1)", color: "#10B981" }}>Research + Upload</span>
                                            </div>
                                            <EditableCredRow label="Username" field="login_username" value={isEditing ? editCreds.login_username : creds.login_username} secret={false} editing={isEditing} onChange={v => setEditCreds(prev => ({ ...prev, login_username: v }))} placeholder={LOGIN_LABEL_MAP[p]} />
                                            <EditableCredRow label="Password" field="login_password" value={isEditing ? editCreds.login_password : creds.login_password} secret editing={isEditing} onChange={v => setEditCreds(prev => ({ ...prev, login_password: v }))} />
                                        </div>
                                    </div>

                                    {saveError && isEditing && (
                                        <div className="px-4 pb-2 flex items-center gap-2 text-xs text-red-300">
                                            <AlertTriangle size={11} />{saveError}
                                        </div>
                                    )}

                                    {/* Verification Results */}
                                    {vr && (
                                        <div className="px-4 pb-4 space-y-2">
                                            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-2 mb-1">Verification Results</div>
                                            {Object.entries(vr.verifications || {}).map(([method, result]) => (
                                                <div key={method}>
                                                    <div className="text-[10px] text-slate-600 mb-0.5 font-semibold capitalize">{method.replace(/_/g, " ")}</div>
                                                    <VerificationBadge result={result as VerificationResult} />
                                                </div>
                                            ))}
                                            {vr.overall_error_summary && !vr.overall_verified && (
                                                <div className="flex items-start gap-2 p-2.5 rounded-lg mt-2" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
                                                    <ShieldX size={13} className="shrink-0 mt-0.5" style={{ color: "#EF4444" }} />
                                                    <div>
                                                        <div className="text-[10px] font-bold text-red-400 mb-0.5">Mismatch Detected</div>
                                                        <div className="text-[10px] text-red-300 leading-relaxed">{vr.overall_error_summary}</div>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                    {verifyError[p] && (
                                        <div className="px-4 pb-3 flex items-center gap-2 text-xs text-red-300">
                                            <AlertTriangle size={11} />{verifyError[p]}
                                        </div>
                                    )}
                                </div>
                            );
                        })
                    )}

                    {/* Upload Priority Note */}
                    <div className="rounded-xl p-4 mt-4" style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.15)" }}>
                        <div className="text-xs font-bold text-emerald-400 mb-2 flex items-center gap-1.5">
                            <Shield size={12} /> Upload Priority Waterfall
                        </div>
                        <div className="space-y-1 text-[11px] text-slate-400">
                            <div className="flex items-center gap-2"><span className="w-5 h-5 rounded-full bg-pink-500/20 text-pink-400 text-[9px] font-bold flex items-center justify-center shrink-0">1</span> Metricool API (Research + Upload)</div>
                            <div className="flex items-center gap-2"><span className="w-5 h-5 rounded-full bg-blue-500/20 text-blue-400 text-[9px] font-bold flex items-center justify-center shrink-0">2</span> Buffer API (Research + Upload)</div>
                            <div className="flex items-center gap-2"><span className="w-5 h-5 rounded-full bg-yellow-500/20 text-yellow-400 text-[9px] font-bold flex items-center justify-center shrink-0">3</span> Platform API / Access Token</div>
                            <div className="flex items-center gap-2"><span className="w-5 h-5 rounded-full bg-purple-500/20 text-purple-400 text-[9px] font-bold flex items-center justify-center shrink-0">4</span> Login Credentials (Playwright)</div>
                        </div>
                    </div>
                </div>

            {/* ── Delete Confirmation Modal ─────────────────────────────── */}
            {showDeleteConfirm && (
                <div className="absolute inset-0 flex items-center justify-center z-60" style={{ background: "rgba(0,0,0,0.5)" }}>
                    <div className="rounded-2xl p-8 w-full max-w-sm shadow-2xl" style={{ background: "#0F0F18", border: "1px solid rgba(239,68,68,0.3)" }}>
                        <div className="w-14 h-14 rounded-2xl bg-red-500/10 flex items-center justify-center mx-auto mb-5 border border-red-500/20">
                            <Trash2 size={24} style={{ color: "#EF4444" }} />
                        </div>
                        <h3 className="text-lg font-bold text-white text-center mb-2">Delete Client?</h3>
                        <p className="text-sm text-slate-400 text-center mb-1">You are about to permanently delete:</p>
                        <p className="text-base font-bold text-white text-center mb-5">{client.name || client.client_id}</p>
                        <div className="rounded-lg p-3 mb-6" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.15)" }}>
                            <div className="flex items-start gap-2 text-xs text-red-300">
                                <AlertTriangle size={13} className="shrink-0 mt-0.5" />
                                <span>This will permanently delete all client data, credentials, DNA profiles, evolution logs, and analysis history. <strong>This action cannot be undone.</strong></span>
                            </div>
                        </div>
                        <div className="flex gap-3">
                            <button onClick={() => setShowDeleteConfirm(false)} className="flex-1 py-2.5 rounded-lg text-sm font-semibold text-slate-400 hover:bg-white/5 transition-colors border border-white/10">
                                Cancel
                            </button>
                            <button onClick={handleDelete} disabled={deleting}
                                className="flex-1 py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 transition-all"
                                style={{ background: deleting ? "rgba(239,68,68,0.2)" : "#EF4444", color: "#fff" }}
                            >
                                {deleting ? <><Loader2 size={14} className="animate-spin" /> Deleting...</> : <><Trash2 size={14} /> Delete Permanently</>}
                            </button>
                        </div>
                    </div>
                </div>
            )}
            </div>
        </div>
    );
}

// ═══════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════

export default function NexearchClients() {
    const [clients, setClients] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [showModal, setShowModal] = useState(false);
    const [creating, setCreating] = useState(false);
    const [createError, setCreateError] = useState("");
    const [selectedClient, setSelectedClient] = useState<any | null>(null);

    // Form state
    const [formName, setFormName] = useState("");
    const [activePlatforms, setActivePlatforms] = useState<string[]>([]);
    const [platformCreds, setPlatformCreds] = useState<Record<string, PlatformCreds>>({});
    const [expandedPlatform, setExpandedPlatform] = useState<string | null>(null);
    const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});

    const fetchClients = useCallback(async () => {
        setLoading(true);
        try {
            const data = await arcAgentAPI.listClients();
            setClients(data.clients || []);
        } catch { setClients([]); }
        setLoading(false);
    }, []);

    useEffect(() => { fetchClients(); }, [fetchClients]);

    // Re-fetch a single client after editing and update selectedClient
    const refreshSelectedClient = useCallback(async () => {
        await fetchClients();
        // After refresh, obtain fresh client data
        setSelectedClient((prev: any) => {
            // Will be replaced by the new data in next render via clients state
            return prev;
        });
    }, [fetchClients]);

    // Keep selected client in sync with latest data
    useEffect(() => {
        if (selectedClient) {
            const fresh = clients.find(c => c.client_id === selectedClient.client_id);
            if (fresh) setSelectedClient(fresh);
        }
    }, [clients]);

    const togglePlatform = (p: string) => {
        setActivePlatforms(prev => {
            if (prev.includes(p)) {
                const n = prev.filter(x => x !== p);
                if (expandedPlatform === p) setExpandedPlatform(null);
                return n;
            }
            return [...prev, p];
        });
        if (!platformCreds[p]) {
            setPlatformCreds(prev => ({ ...prev, [p]: emptyCreds() }));
        }
    };

    const setCred = (platform: string, field: keyof PlatformCreds, value: string) => {
        setPlatformCreds(prev => ({
            ...prev,
            [platform]: { ...(prev[platform] || emptyCreds()), [field]: value },
        }));
    };

    const hasMinimumAccess = () => {
        return activePlatforms.some(p => {
            const c = platformCreds[p];
            return c && (c.account_url.trim() || c.login_username.trim() || c.access_token.trim() || c.api_key.trim() || c.buffer_api_key.trim() || c.metricool_api_key.trim());
        });
    };

    const getPlatformAccessLabel = (p: string): { label: string; color: string; icon: "research" | "full" | "none" } => {
        const c = platformCreds[p];
        if (!c) return { label: "No access", color: "#475569", icon: "none" };
        const hasLogin = !!c.login_username.trim() && !!c.login_password.trim();
        const hasApi = !!c.access_token.trim() || !!c.api_key.trim();
        const hasMetricool = !!c.metricool_api_key.trim();
        const hasBuffer = !!c.buffer_api_key.trim();
        const hasUrl = !!c.account_url.trim();
        if (hasLogin || hasApi || hasMetricool || hasBuffer) return { label: "Research + Upload", color: "#10B981", icon: "full" };
        if (hasUrl) return { label: "Research Only", color: "#F59E0B", icon: "research" };
        return { label: "No access", color: "#475569", icon: "none" };
    };

    const handleCreate = async () => {
        if (!formName.trim()) return;
        if (!hasMinimumAccess()) {
            setCreateError("At least 1 platform must have an account link, login credentials, API key, Metricool key, or Buffer key.");
            return;
        }
        setCreating(true);
        setCreateError("");
        try {
            const platforms: Record<string, Record<string, string>> = {};
            for (const p of activePlatforms) {
                const c = platformCreds[p];
                if (c) {
                    const creds: Record<string, string> = {};
                    if (c.account_url.trim()) creds.account_url = c.account_url.trim();
                    if (c.login_username.trim()) creds.login_username = c.login_username.trim();
                    if (c.login_password.trim()) creds.login_password = c.login_password.trim();
                    if (c.access_token.trim()) creds.access_token = c.access_token.trim();
                    if (c.api_key.trim()) creds.api_key = c.api_key.trim();
                    if (c.page_id.trim()) creds.page_id = c.page_id.trim();
                    if (c.metricool_api_key.trim()) creds.metricool_api_key = c.metricool_api_key.trim();
                    if (c.buffer_api_key.trim()) creds.buffer_api_key = c.buffer_api_key.trim();
                    if (Object.keys(creds).length > 0) platforms[p] = creds;
                }
            }
            await arcAgentAPI.createClient({ name: formName.trim(), platforms });
            resetModal();
            await fetchClients();
        } catch (err: any) {
            setCreateError(err?.message || "Failed to create client");
        }
        setCreating(false);
    };

    const resetModal = () => {
        setShowModal(false);
        setFormName("");
        setActivePlatforms([]);
        setPlatformCreds({});
        setExpandedPlatform(null);
        setCreateError("");
    };

    const filtered = clients.filter(c =>
        (c.name || c.account_handle || c.client_id || "").toLowerCase().includes(search.toLowerCase())
    );

    const inputStyle = {
        background: "rgba(255,255,255,0.05)",
        border: "1px solid rgba(255,255,255,0.1)",
        color: "#E2E8F0",
    };

    return (
        <div style={{ padding: "24px 32px", background: "#0A0A0F", minHeight: "calc(100vh - 64px)", color: "#E2E8F0" }}>
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-3">
                        <Users size={24} style={{ color: "#06B6D4" }} />
                        Nexearch Clients
                    </h1>
                    <p className="text-sm mt-1" style={{ color: "#94A3B8" }}>
                        Manage client accounts, credentials, and DNA profiles across 7 platforms
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="relative">
                        <Search size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "#64748B" }} />
                        <input value={search} onChange={e => setSearch(e.target.value)}
                            placeholder="Search clients..."
                            className="rounded-lg pl-9 pr-4 py-2 text-sm outline-none"
                            style={{ ...inputStyle, width: 200 }}
                        />
                    </div>
                    <button onClick={() => setShowModal(true)}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all hover:opacity-90"
                        style={{ background: "linear-gradient(135deg, #8B5CF6, #06B6D4)", color: "#fff" }}>
                        <Plus size={14} /> Add Client
                    </button>
                    <button onClick={fetchClients}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all hover:bg-white/5"
                        style={{ border: "1px solid rgba(6,182,212,0.3)", color: "#06B6D4" }}>
                        <RefreshCw size={14} /> Refresh
                    </button>
                </div>
            </div>

            {/* Clients Grid */}
            {loading ? (
                <div className="flex items-center justify-center py-20">
                    <RefreshCw size={24} className="animate-spin" style={{ color: "#64748B" }} />
                </div>
            ) : filtered.length === 0 ? (
                <div className="text-center py-20">
                    <Users size={48} style={{ color: "#1E293B", margin: "0 auto" }} />
                    <h3 className="mt-4 text-lg font-semibold" style={{ color: "#94A3B8" }}>No Clients Yet</h3>
                    <p className="text-sm mt-2" style={{ color: "#64748B" }}>
                        Click &quot;Add Client&quot; above or tell Nex/Arc Agent to add one.
                    </p>
                </div>
            ) : (
                <div className="grid grid-cols-2 gap-4">
                    {filtered.map((client: any) => {
                        const caps = client.capabilities || {};
                        const researchable = caps.total_researchable || 0;
                        const uploadable = caps.total_uploadable || 0;

                        return (
                            <div
                                key={client.client_id}
                                className="rounded-xl p-5 transition-all hover:bg-white/5 cursor-pointer group"
                                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}
                                onClick={() => setSelectedClient(client)}
                            >
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-3">
                                        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-purple-500/20 to-cyan-500/20 flex items-center justify-center text-sm font-black text-white border border-white/10">
                                            {(client.name || client.client_id || "?").slice(0, 2).toUpperCase()}
                                        </div>
                                        <div className="text-sm font-semibold" style={{ color: "#E2E8F0" }}>
                                            {client.name || client.account_handle || client.client_id}
                                        </div>
                                    </div>
                                    <ChevronRight size={16} style={{ color: "#475569" }} className="group-hover:text-white transition-colors" />
                                </div>

                                {/* Platform badges */}
                                <div className="flex flex-wrap gap-1.5 mb-3">
                                    {(client.platforms || []).map((p: string) => {
                                        const platDets = client.platform_details?.[p] || {};
                                        const canUpload = platDets.can_upload;
                                        const canResearch = platDets.can_research;
                                        return (
                                            <span key={p} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase"
                                                style={{ background: `${PLATFORM_COLORS[p] || "#8B5CF6"}15`, color: PLATFORM_COLORS[p] || "#8B5CF6" }}>
                                                <Globe size={10} /> {PLATFORM_LABELS[p] || p}
                                                {canUpload && <Upload size={8} />}
                                                {canResearch && !canUpload && <SearchIcon size={8} />}
                                            </span>
                                        );
                                    })}
                                </div>

                                {/* Capability badges */}
                                <div className="flex items-center gap-3 text-[11px]" style={{ color: "#64748B" }}>
                                    {researchable > 0 && (
                                        <span className="flex items-center gap-1">
                                            <SearchIcon size={10} style={{ color: "#06B6D4" }} />
                                            {researchable} researchable
                                        </span>
                                    )}
                                    {uploadable > 0 && (
                                        <span className="flex items-center gap-1">
                                            <Upload size={10} style={{ color: "#10B981" }} />
                                            {uploadable} uploadable
                                        </span>
                                    )}
                                    {client.stats?.evolution_cycles > 0 && (
                                        <span className="flex items-center gap-1">
                                            <Activity size={10} style={{ color: "#8B5CF6" }} />
                                            {client.stats.evolution_cycles} evolutions
                                        </span>
                                    )}
                                </div>

                                <div className="mt-3 pt-3 border-t border-white/5 text-[10px] text-slate-600 group-hover:text-slate-400 transition-colors flex items-center gap-1">
                                    <Eye size={10} /> Click to view credentials, verify &amp; modify
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Platform Overview */}
            <div className="mt-8">
                <h2 className="text-lg font-semibold mb-4" style={{ color: "#CBD5E1" }}>Supported Platforms</h2>
                <div className="grid grid-cols-7 gap-3">
                    {PLATFORMS.map(p => (
                        <div key={p} className="rounded-xl p-4 text-center transition-all hover:bg-white/5"
                            style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
                            <Globe size={20} style={{ color: PLATFORM_COLORS[p], margin: "0 auto" }} />
                            <div className="text-xs font-semibold mt-2 capitalize" style={{ color: "#94A3B8" }}>{PLATFORM_LABELS[p]}</div>
                        </div>
                    ))}
                </div>
            </div>

            {/* ═══════ CLIENT DETAIL PANEL ═══════ */}
            {selectedClient && (
                <ClientDetailPanel
                    client={selectedClient}
                    onClose={() => setSelectedClient(null)}
                    onDelete={() => { setSelectedClient(null); fetchClients(); }}
                    onRefresh={refreshSelectedClient}
                />
            )}

            {/* ═══════ ADD CLIENT MODAL ═══════ */}
            {showModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(8px)" }}>
                    <div className="rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto" style={{ background: "#0F0F18", border: "1px solid rgba(139,92,246,0.2)", boxShadow: "0 24px 64px rgba(139,92,246,0.15)" }}>
                        {/* Modal header */}
                        <div className="flex items-center justify-between p-5 border-b" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                            <div>
                                <h2 className="text-lg font-semibold" style={{ color: "#E2E8F0" }}>Add New Client</h2>
                                <p className="text-xs mt-0.5" style={{ color: "#64748B" }}>Page/Account Link + at least 1 method required per platform</p>
                            </div>
                            <button onClick={resetModal} className="p-1.5 rounded-lg hover:bg-white/5"><X size={18} style={{ color: "#64748B" }} /></button>
                        </div>

                        <div className="p-5 space-y-5">
                            {/* Client Name */}
                            <div>
                                <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "#94A3B8" }}>Client Name *</label>
                                <input value={formName} onChange={e => setFormName(e.target.value)}
                                    placeholder="e.g. Clip Aura"
                                    className="w-full rounded-lg px-4 py-2.5 text-sm outline-none transition-all focus:ring-1 focus:ring-purple-500/50"
                                    style={inputStyle}
                                />
                            </div>

                            {/* Platform Selection */}
                            <div>
                                <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "#94A3B8" }}>
                                    Select Platforms (min 1) *
                                </label>
                                <div className="flex flex-wrap gap-2">
                                    {PLATFORMS.map(p => (
                                        <button key={p} onClick={() => togglePlatform(p)}
                                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                                            style={{
                                                background: activePlatforms.includes(p) ? `${PLATFORM_COLORS[p]}20` : "rgba(255,255,255,0.03)",
                                                border: `1px solid ${activePlatforms.includes(p) ? PLATFORM_COLORS[p] + "60" : "rgba(255,255,255,0.06)"}`,
                                                color: activePlatforms.includes(p) ? PLATFORM_COLORS[p] : "#64748B",
                                            }}>
                                            {activePlatforms.includes(p) && <Check size={12} />}
                                            <Globe size={12} /> {PLATFORM_LABELS[p]}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Per-platform credential sections */}
                            {activePlatforms.length > 0 && (
                                <div>
                                    <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "#94A3B8" }}>
                                        Platform Credentials
                                    </label>
                                    <p className="text-[11px] mb-3" style={{ color: "#475569" }}>
                                        5 access methods per platform. Method 1 = research only. Methods 2–5 = research + upload.
                                    </p>
                                    <div className="space-y-2">
                                        {activePlatforms.map(p => {
                                            const isExpanded = expandedPlatform === p;
                                            const access = getPlatformAccessLabel(p);
                                            const creds = platformCreds[p] || emptyCreds();

                                            return (
                                                <div key={p} className="rounded-xl overflow-hidden transition-all"
                                                    style={{ background: "rgba(255,255,255,0.02)", border: `1px solid ${isExpanded ? PLATFORM_COLORS[p] + "40" : "rgba(255,255,255,0.04)"}` }}>
                                                    <button onClick={() => setExpandedPlatform(isExpanded ? null : p)}
                                                        className="w-full flex items-center justify-between p-3 hover:bg-white/3 transition-all">
                                                        <div className="flex items-center gap-2.5">
                                                            <Globe size={16} style={{ color: PLATFORM_COLORS[p] }} />
                                                            <span className="text-sm font-semibold" style={{ color: "#CBD5E1" }}>{PLATFORM_LABELS[p]}</span>
                                                            <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
                                                                style={{ background: `${access.color}15`, color: access.color }}>
                                                                {access.icon === "full" && <><Upload size={8} className="inline mr-1" /></>}
                                                                {access.icon === "research" && <><SearchIcon size={8} className="inline mr-1" /></>}
                                                                {access.label}
                                                            </span>
                                                        </div>
                                                        {isExpanded ? <X size={14} style={{ color: "#64748B" }} /> : <ChevronRight size={16} style={{ color: "#64748B" }} />}
                                                    </button>

                                                    {isExpanded && (
                                                        <div className="px-4 pb-4 space-y-3">
                                                            {/* Method 1: Page Link */}
                                                            <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)" }}>
                                                                <div className="flex items-center gap-2 mb-2">
                                                                    <Link2 size={13} style={{ color: "#06B6D4" }} />
                                                                    <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 1: Page/Account Link</span>
                                                                    <span className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold" style={{ background: "rgba(239,68,68,0.15)", color: "#EF4444" }}>Required</span>
                                                                    <span className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold" style={{ background: "rgba(245,158,11,0.1)", color: "#F59E0B" }}>Research Only</span>
                                                                </div>
                                                                <input value={creds.account_url} onChange={e => setCred(p, "account_url", e.target.value)}
                                                                    placeholder={URL_PLACEHOLDERS[p]}
                                                                    className="w-full rounded-lg px-3 py-2 text-xs outline-none transition-all focus:ring-1 focus:ring-cyan-500/30"
                                                                    style={inputStyle} />
                                                            </div>

                                                            {/* Method 2: Metricool */}
                                                            <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)" }}>
                                                                <div className="flex items-center gap-2 mb-2">
                                                                    <BarChart3 size={13} style={{ color: "#EC4899" }} />
                                                                    <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 2: Metricool API Key</span>
                                                                    <span className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold" style={{ background: "rgba(16,185,129,0.1)", color: "#10B981" }}>Research + Upload</span>
                                                                </div>
                                                                <div className="grid grid-cols-1 gap-2">
                                                                    <input value={creds.metricool_api_key} onChange={e => setCred(p, "metricool_api_key", e.target.value)} placeholder="Metricool API Key" className="rounded-lg px-3 py-2 text-xs outline-none" style={inputStyle} />
                                                                </div>
                                                            </div>

                                                            {/* Method 3: Buffer */}
                                                            <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)" }}>
                                                                <div className="flex items-center gap-2 mb-2">
                                                                    <Zap size={13} style={{ color: "#3B82F6" }} />
                                                                    <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 3: Buffer API Key</span>
                                                                    <span className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold" style={{ background: "rgba(16,185,129,0.1)", color: "#10B981" }}>Research + Upload</span>
                                                                </div>
                                                                <input value={creds.buffer_api_key} onChange={e => setCred(p, "buffer_api_key", e.target.value)} placeholder="Buffer Access Token" className="w-full rounded-lg px-3 py-2 text-xs outline-none" style={inputStyle} />
                                                            </div>

                                                            {/* Method 4: Platform API */}
                                                            <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)" }}>
                                                                <div className="flex items-center gap-2 mb-2">
                                                                    <Key size={13} style={{ color: "#F59E0B" }} />
                                                                    <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 4: Platform API / Access Key</span>
                                                                    <span className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold" style={{ background: "rgba(16,185,129,0.1)", color: "#10B981" }}>Research + Upload</span>
                                                                </div>
                                                                <div className="grid grid-cols-2 gap-2">
                                                                    <input value={creds.access_token} onChange={e => setCred(p, "access_token", e.target.value)} placeholder="Access Token" className="rounded-lg px-3 py-2 text-xs outline-none" style={inputStyle} />
                                                                    <input value={creds.api_key} onChange={e => setCred(p, "api_key", e.target.value)} placeholder="API Key (optional)" className="rounded-lg px-3 py-2 text-xs outline-none" style={inputStyle} />
                                                                </div>
                                                                {(p === "facebook" || p === "instagram" || p === "threads") && (
                                                                    <input value={creds.page_id} onChange={e => setCred(p, "page_id", e.target.value)} placeholder={p === "threads" ? "Threads User ID" : "Page ID"} className="w-full rounded-lg px-3 py-2 text-xs outline-none mt-2" style={inputStyle} />
                                                                )}
                                                            </div>

                                                            {/* Method 5: Login */}
                                                            <div className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.02)" }}>
                                                                <div className="flex items-center gap-2 mb-2">
                                                                    <Lock size={13} style={{ color: "#8B5CF6" }} />
                                                                    <span className="text-xs font-semibold" style={{ color: "#94A3B8" }}>Method 5: Login Credentials (Playwright)</span>
                                                                    <span className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold" style={{ background: "rgba(16,185,129,0.1)", color: "#10B981" }}>Research + Upload</span>
                                                                </div>
                                                                <div className="grid grid-cols-2 gap-2">
                                                                    <input value={creds.login_username} onChange={e => setCred(p, "login_username", e.target.value)} placeholder={LOGIN_LABEL_MAP[p] || "Username"} className="rounded-lg px-3 py-2 text-xs outline-none" style={inputStyle} />
                                                                    <div className="relative">
                                                                        <input value={creds.login_password} onChange={e => setCred(p, "login_password", e.target.value)} type={showPasswords[p] ? "text" : "password"} placeholder="Password" className="w-full rounded-lg px-3 py-2 pr-8 text-xs outline-none" style={inputStyle} />
                                                                        <button onClick={() => setShowPasswords(prev => ({ ...prev, [p]: !prev[p] }))} className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 hover:opacity-80" type="button">
                                                                            {showPasswords[p] ? <EyeOff size={12} style={{ color: "#64748B" }} /> : <Eye size={12} style={{ color: "#64748B" }} />}
                                                                        </button>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}

                            {/* Priority waterfall info */}
                            <div className="rounded-lg p-3" style={{ background: "rgba(6,182,212,0.05)", border: "1px solid rgba(6,182,212,0.15)" }}>
                                <div className="text-[11px] space-y-1" style={{ color: "#94A3B8" }}>
                                    <div className="font-semibold mb-1.5" style={{ color: "#06B6D4" }}>Upload Priority Waterfall</div>
                                    <div><span style={{ color: "#EC4899" }}>① Metricool API</span> → <span style={{ color: "#94A3B8" }}>Research &amp; Upload (highest priority)</span></div>
                                    <div><span style={{ color: "#3B82F6" }}>② Buffer API</span> → <span style={{ color: "#94A3B8" }}>Research &amp; Upload</span></div>
                                    <div><span style={{ color: "#F59E0B" }}>③ Platform API</span> → <span style={{ color: "#94A3B8" }}>Research &amp; Upload</span></div>
                                    <div><span style={{ color: "#8B5CF6" }}>④ Login Creds</span> → <span style={{ color: "#94A3B8" }}>Research &amp; Upload (via Playwright browser)</span></div>
                                    <div><span style={{ color: "#06B6D4" }}>⑤ Page Link</span> → <span style={{ color: "#94A3B8" }}>Research only</span></div>
                                </div>
                            </div>

                            {createError && (
                                <div className="flex items-center gap-2 p-3 rounded-lg" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)" }}>
                                    <AlertTriangle size={14} style={{ color: "#EF4444" }} />
                                    <span className="text-xs" style={{ color: "#FCA5A5" }}>{createError}</span>
                                </div>
                            )}
                        </div>

                        {/* Modal footer */}
                        <div className="flex items-center justify-between p-5 border-t" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                            <div className="text-[11px]" style={{ color: "#475569" }}>
                                {activePlatforms.length > 0 ? `${activePlatforms.length} platform${activePlatforms.length > 1 ? "s" : ""} selected` : "No platforms selected"}
                            </div>
                            <div className="flex items-center gap-3">
                                <button onClick={resetModal} className="px-4 py-2 rounded-lg text-sm transition-all hover:bg-white/5" style={{ color: "#94A3B8" }}>Cancel</button>
                                <button onClick={handleCreate}
                                    disabled={!formName.trim() || !hasMinimumAccess() || creating}
                                    className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all"
                                    style={{
                                        background: formName.trim() && hasMinimumAccess() && !creating ? "linear-gradient(135deg, #8B5CF6, #06B6D4)" : "rgba(139,92,246,0.2)",
                                        color: formName.trim() && hasMinimumAccess() && !creating ? "#fff" : "#64748B",
                                        cursor: formName.trim() && hasMinimumAccess() && !creating ? "pointer" : "not-allowed",
                                    }}>
                                    {creating ? <><Loader2 size={14} className="animate-spin" /> Creating...</> : <><Plus size={14} /> Create Client</>}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
