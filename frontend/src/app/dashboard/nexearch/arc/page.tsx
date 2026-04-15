"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
    Send, Plus, Trash2, RefreshCw, X,
    Zap, Activity, Brain, Bot, Wrench, Users,
    Database, Globe, Copy, Check, ChevronRight, ChevronDown,
    AlertCircle, Wifi, WifiOff, RotateCcw
} from "lucide-react";
import { arcAgentAPI } from "@/lib/api";
import { MarkdownRenderer } from "@/components/nex/MarkdownRenderer";
import { ModelIndicator } from "@/components/nex/ModelIndicator";
import "./arc-styles.css";

/* ═══════════════════════════════════════════════════════════════
   TYPES
   ═══════════════════════════════════════════════════════════════ */

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    timestamp: string;
    status: "streaming" | "complete" | "error";
    error_detail?: string;
    thinking?: string;  // collapsible reasoning content
}

interface Conversation {
    id: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
}

function extractThinkingPayload(message: any): string {
    if (typeof message?.thinking === "string") return message.thinking;
    if (typeof message?.thinking_content === "string") return message.thinking_content;
    if (typeof message?.message?.thinking_content === "string") return message.message.thinking_content;
    return "";
}

const ARC_API = "http://localhost:8003/api";
const ARC_WS = "ws://localhost:8003/ws/chat";

/* ═══════════════════════════════════════════════════════════════
   ANIMATED AVATAR (SVG — Purple Pentagon)
   ═══════════════════════════════════════════════════════════════ */

function ArcAvatar({ state = "idle", size = 48 }: { state?: string; size?: number }) {
    const cls = `arc-avatar-${state}`;
    return (
        <div className={cls} style={{ width: size, height: size, position: "relative", flexShrink: 0 }}>
            <svg viewBox="0 0 100 100" width={size} height={size}>
                <circle className="arc-ring" cx="50" cy="50" r="45" fill="none"
                    stroke="url(#arcRingGrad)" strokeWidth="2" strokeDasharray="8 4"
                    style={{ transformOrigin: "50% 50%" }} />
                <circle className="arc-glow" cx="50" cy="50" r="28"
                    fill="url(#arcCoreGlow)" opacity="0.4" />
                <polygon className="arc-core" points="50,22 72,40 66,65 34,65 28,40"
                    fill="url(#arcCrystalGrad)" stroke="rgba(139,92,246,0.5)" strokeWidth="1"
                    style={{ transformOrigin: "50% 50%" }} />
                <circle cx="50" cy="47" r="5" fill="#A78BFA" opacity="0.9" />
                {state === "thinking" && (
                    <>
                        <circle className="arc-orbit" cx="50" cy="50" r="2" fill="#8B5CF6"
                            style={{ transformOrigin: "50% 50%" }} />
                        <circle className="arc-orbit" cx="50" cy="50" r="1.5" fill="#06B6D4"
                            style={{ transformOrigin: "50% 50%", animationDelay: "0.7s" }} />
                    </>
                )}
                {state === "responding" && (
                    <circle className="arc-wave" cx="50" cy="50" r="12"
                        fill="none" stroke="rgba(139,92,246,0.3)" strokeWidth="1"
                        style={{ transformOrigin: "50% 50%" }} />
                )}
                <defs>
                    <radialGradient id="arcCoreGlow"><stop offset="0%" stopColor="#8B5CF6" /><stop offset="100%" stopColor="transparent" /></radialGradient>
                    <linearGradient id="arcRingGrad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#8B5CF6" /><stop offset="100%" stopColor="#06B6D4" /></linearGradient>
                    <linearGradient id="arcCrystalGrad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="rgba(139,92,246,0.3)" /><stop offset="100%" stopColor="rgba(6,182,212,0.2)" /></linearGradient>
                </defs>
            </svg>
        </div>
    );
}

/* ═══════════════════════════════════════════════════════════════
   THINKING BLOCK — collapsible reasoning disclosure
   ═══════════════════════════════════════════════════════════════ */

function ThinkingBlock({ thinking, accentColor = "#8B5CF6" }: { thinking: string; accentColor?: string }) {
    const [open, setOpen] = useState(false);
    if (!thinking || !thinking.trim()) return null;
    return (
        <div style={{
            marginBottom: 8,
            borderRadius: 8,
            border: `1px solid ${accentColor}28`,
            background: `${accentColor}08`,
            overflow: "hidden",
        }}>
            <button
                onClick={() => setOpen(o => !o)}
                style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    width: "100%",
                    padding: "6px 10px",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    color: accentColor,
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                    opacity: 0.85,
                }}
            >
                <span style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 14,
                    height: 14,
                    borderRadius: "50%",
                    background: `${accentColor}25`,
                    fontSize: 8,
                }}>💭</span>
                Thinking
                <ChevronDown
                    size={12}
                    style={{
                        marginLeft: "auto",
                        transform: open ? "rotate(180deg)" : "rotate(0deg)",
                        transition: "transform 0.2s ease",
                        opacity: 0.7,
                    }}
                />
            </button>
            {open && (
                <div style={{
                    padding: "0 10px 10px",
                    borderTop: `1px solid ${accentColor}18`,
                    maxHeight: 320,
                    overflowY: "auto",
                }}>
                    <pre style={{
                        margin: 0,
                        paddingTop: 8,
                        fontSize: 11,
                        lineHeight: 1.6,
                        color: "rgba(200,200,220,0.55)",
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                        fontFamily: "'SF Mono', 'Fira Code', monospace",
                    }}>{thinking}</pre>
                </div>
            )}
        </div>
    );
}

/* ═══════════════════════════════════════════════════════════════
   QUICK ACTIONS
   ═══════════════════════════════════════════════════════════════ */

const QUICK_ACTIONS = [
    { icon: Zap, label: "System Status", prompt: "Show me the full Nexearch system status." },
    { icon: Users, label: "List Clients", prompt: "List all clients with their platform configurations and upload methods." },
    { icon: Brain, label: "Universal Patterns", prompt: "What universal patterns have been discovered across all platforms?" },
    { icon: Database, label: "Pipeline Runs", prompt: "Show recent pipeline runs with their status." },
    { icon: Globe, label: "Sub-Agents", prompt: "Show all sub-agents and their current status." },
    { icon: Wrench, label: "Available Tools", prompt: "List all tools available to you with descriptions." },
    { icon: Activity, label: "Activity Log", prompt: "Show the activity log for today." },
];

/* ═══════════════════════════════════════════════════════════════
   MAIN PAGE COMPONENT
   ═══════════════════════════════════════════════════════════════ */

export default function ArcAgentPage() {
    /* ── State ─────────────────────────────────────────────────── */
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [activeConvId, setActiveConvId] = useState<string>("");
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isStreaming, setIsStreaming] = useState(false);
    const [avatarState, setAvatarState] = useState<string>("idle");
    const [arcStatus, setArcStatus] = useState<string>("online");
    const [statusDesc, setStatusDesc] = useState("Fully operational");
    const [activeModel, setActiveModel] = useState("Connecting...");
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [copied, setCopied] = useState<string | null>(null);
    const [wsConnected, setWsConnected] = useState(false);

    const chatEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectRef = useRef<number>(0);
    const reconnectTimerRef = useRef<any>(null);
    const shouldReconnectRef = useRef<boolean>(false);
    const messagesRef = useRef<Message[]>([]);
    const convIdRef = useRef<string | null>(null);
    const pendingMsgIdRef = useRef<string | null>(null);  // local placeholder ID before stream_start

    useEffect(() => {
        messagesRef.current = messages;
        convIdRef.current = activeConvId;
    }, [messages, activeConvId]);

    /* ── Helpers ────────────────────────────────────────────────── */
    const genId = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
    const now = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    const scrollToBottom = useCallback(() => {
        setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }, []);

    /* ── Load conversations ──────────────────────────────────── */
    const loadConversations = useCallback(async () => {
        try {
            const res = await arcAgentAPI.listConversations();
            setConversations(res.conversations || []);
            return res.conversations || [];
        } catch { return []; }
    }, []);

    /* ── Load messages for a conversation ────────────────────── */
    const loadMessages = useCallback(async (convId: string) => {
        try {
            const res = await arcAgentAPI.getMessages(convId);
            const msgs: Message[] = (res.messages || []).map((m: any) => ({
                id: m.id,
                role: m.role as "user" | "assistant",
                content: m.content || "",
                timestamp: m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "",
                status: m.status || "complete",
                error_detail: m.error_detail,
                thinking: extractThinkingPayload(m),
            }));
            setMessages(msgs);
            scrollToBottom();
        } catch { setMessages([]); }
    }, [scrollToBottom]);

    /* ── Create new conversation ──────────────────────────────── */
    const newConversation = useCallback(async () => {
        try {
            const res = await arcAgentAPI.createConversation();
            const newId = res.id;
            if (newId) {
                setActiveConvId(newId);
                setMessages([]);
                setInput("");
                await loadConversations();
            }
        } catch {
            const localId = genId();
            setActiveConvId(localId);
            setMessages([]);
            setInput("");
        }
    }, [loadConversations]);

    /* ── Initialize ────────────────────────────────────────────── */
    useEffect(() => {
        const init = async () => {
            const convs = await loadConversations();
            if (convs.length > 0) {
                setActiveConvId(convs[0].id);
                await loadMessages(convs[0].id);
            } else {
                newConversation();
            }
        };
        init();
    }, [loadConversations, loadMessages, newConversation]);

    /* ── When active conversation changes, load its messages ── */
    useEffect(() => {
        if (activeConvId) loadMessages(activeConvId);
    }, [activeConvId, loadMessages]);

    /* ── Fetch status and model ───────────────────────────────── */
    useEffect(() => {
        const fetchInfo = async () => {
            try {
                const [statusRes, modelRes] = await Promise.all([
                    arcAgentAPI.getStatus(),
                    arcAgentAPI.getModel(),
                ]);
                if (statusRes) {
                    setArcStatus(statusRes.status === "ok" || statusRes.status === "online" || statusRes.nex_status === "online" ? "online" : "offline");
                    setStatusDesc(statusRes.status_description || "Nexearch Intelligence Controller");
                }
                if (modelRes?.active_model) setActiveModel(modelRes.active_model);
            } catch { setArcStatus("offline"); setActiveModel("Disconnected"); }
        };
        fetchInfo();
        const interval = setInterval(fetchInfo, 30000);
        return () => clearInterval(interval);
    }, []);

    /* ── WebSocket connection with reconnection ───────────────── */
    const connectWs = useCallback(() => {
        if (!activeConvId) return;
        if (
            wsRef.current?.readyState === WebSocket.OPEN ||
            wsRef.current?.readyState === WebSocket.CONNECTING
        ) return;
        const latestMsgs = messagesRef.current;
        const lastMsgId = (latestMsgs.length > 0 && convIdRef.current === activeConvId) ? latestMsgs[latestMsgs.length - 1].id : "";
        const url = `${ARC_WS}?user_id=admin&conversation_id=${activeConvId}&last_message_id=${lastMsgId}`;

        try {
            shouldReconnectRef.current = true;
            const ws = new WebSocket(url);
            wsRef.current = ws;

            ws.onopen = () => {
                setWsConnected(true);
                reconnectRef.current = 0;
                if (reconnectTimerRef.current) { clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
            };
            ws.onclose = () => {
                setWsConnected(false);
                if (wsRef.current === ws) {
                    wsRef.current = null;
                }
                if (!shouldReconnectRef.current || !activeConvId) {
                    return;
                }
                const delay = Math.min(1000 * Math.pow(2, reconnectRef.current), 30000);
                reconnectRef.current += 1;
                reconnectTimerRef.current = setTimeout(connectWs, delay);
            };
            ws.onerror = () => ws.close();
            ws.onmessage = (event) => {
                try { handleWsMessage(JSON.parse(event.data)); } catch { }
            };
        } catch {
            const delay = Math.min(1000 * Math.pow(2, reconnectRef.current), 30000);
            reconnectRef.current += 1;
            reconnectTimerRef.current = setTimeout(connectWs, delay);
        }
    }, [activeConvId]);

    useEffect(() => {
        if (!activeConvId) return;
        shouldReconnectRef.current = true;
        connectWs();
        return () => {
            shouldReconnectRef.current = false;
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
            if (wsRef.current) wsRef.current.close();
        };
    }, [connectWs, activeConvId]);

    /* ── Reconnect on tab visibility change ──────────────────── */
    useEffect(() => {
        const handleVisibility = () => {
            if (document.visibilityState === "visible" && !wsConnected) connectWs();
        };
        document.addEventListener("visibilitychange", handleVisibility);
        return () => document.removeEventListener("visibilitychange", handleVisibility);
    }, [connectWs, wsConnected]);

    /* ── Handle incoming WebSocket messages ───────────────────── */
    const handleWsMessage = useCallback((data: any) => {
        const type = data.type;
        const messageId = data.message_id;

        if (type === "stream_start") {
            // Promote the local placeholder to the server's ID
            const serverId = data.assistant_message_id;
            const localId = pendingMsgIdRef.current;
            if (localId && serverId && localId !== serverId) {
                setMessages(prev => prev.map(m =>
                    m.id === localId ? { ...m, id: serverId } : m
                ));
            } else if (!localId) {
                // No local placeholder — create one (fallback)
                setMessages(prev => [...prev, {
                    id: serverId, role: "assistant", content: "", timestamp: now(), status: "streaming",
                }]);
            }
            pendingMsgIdRef.current = null;
            setAvatarState("responding");
            scrollToBottom();
        } else if (type === "token") {
            setMessages(prev => prev.map(m =>
                m.id === messageId ? { ...m, content: m.content + (data.token || data.content || "") } : m
            ));
            scrollToBottom();
        } else if (type === "done") {
            setMessages(prev => prev.map(m =>
                m.id === messageId ? {
                    ...m,
                    status: "complete",
                    content: data.full_content || m.content,
                    thinking: data.thinking_content || m.thinking || "",
                } : m
            ));
            setIsStreaming(false); setAvatarState("idle"); scrollToBottom();
            loadConversations();
        } else if (type === "error") {
            setMessages(prev => prev.map(m =>
                m.id === messageId ? { ...m, status: "error", error_detail: data.error || "Unknown error", content: m.content || "An error occurred." } : m
            ));
            setIsStreaming(false); setAvatarState("idle");
        } else if (type === "replay") {
            setMessages(prev => {
                const replayMessage = data.message;
                if (replayMessage?.id) {
                    const replayThinking = extractThinkingPayload(replayMessage);
                    const exists = prev.find(m => m.id === replayMessage.id);
                    if (exists) {
                        return prev.map(m => m.id === replayMessage.id ? {
                            ...m,
                            content: replayMessage.content || m.content,
                            status: replayMessage.status || m.status,
                            error_detail: replayMessage.error || m.error_detail,
                            thinking: replayThinking || m.thinking || "",
                        } : m);
                    }

                    return [...prev, {
                        id: replayMessage.id,
                        role: (replayMessage.role || "assistant") as "user" | "assistant",
                        content: replayMessage.content || "",
                        timestamp: replayMessage.created_at ? new Date(replayMessage.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : now(),
                        status: replayMessage.status || "complete",
                        error_detail: replayMessage.error,
                        thinking: replayThinking,
                    }];
                }

                const exists = prev.find(m => m.id === messageId);
                if (exists) {
                    return prev.map(m => m.id === messageId ? {
                        ...m,
                        content: data.content || m.content,
                        status: data.status || m.status,
                        error_detail: data.error,
                        thinking: data.thinking_content || m.thinking || "",
                    } : m);
                }
                return [...prev, {
                    id: messageId,
                    role: "assistant" as const,
                    content: data.content || "",
                    timestamp: now(),
                    status: data.status || "complete",
                    error_detail: data.error,
                    thinking: data.thinking_content || "",
                }];
            });
            if (data.status === "streaming") { setIsStreaming(true); setAvatarState("responding"); }
            else { setIsStreaming(false); setAvatarState("idle"); }
            scrollToBottom();
        }
    }, [scrollToBottom, loadConversations]);

    /* ── Send message via WebSocket ───────────────────────────── */
    const sendMessage = async (text?: string) => {
        const msg = (text || input).trim();
        if (!msg || isStreaming) return;

        setMessages(prev => [...prev, { id: genId(), role: "user", content: msg, timestamp: now(), status: "complete" }]);
        setInput(""); setIsStreaming(true); setAvatarState("thinking"); scrollToBottom();

        // Add a local thinking placeholder immediately so the bubble shows right away
        const localPlaceholderId = genId();
        pendingMsgIdRef.current = localPlaceholderId;
        setMessages(prev => [...prev, {
            id: localPlaceholderId,
            role: "assistant",
            content: "",
            timestamp: now(),
            status: "streaming",
        }]);
        scrollToBottom();

        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ message: msg, conversation_id: activeConvId }));
        } else {
            // For SSE fallback, remove the placeholder first
            setMessages(prev => prev.filter(m => m.id !== localPlaceholderId));
            pendingMsgIdRef.current = null;
            await sendViaSse(msg);
        }
    };

    /* ── SSE fallback ─────────────────────────────────────────── */
    const sendViaSse = async (msg: string) => {
        const aId = genId();
        setMessages(prev => [...prev, { id: aId, role: "assistant", content: "", timestamp: now(), status: "streaming" }]);
        setAvatarState("responding");
        try {
            const res = await fetch(`${ARC_API}/chat`, {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: msg, conversation_id: activeConvId }),
            });
            const data = await res.json();
            setMessages(prev => prev.map(m =>
                m.id === aId ? {
                    ...m,
                    content: data.response || JSON.stringify(data),
                    status: "complete",
                    thinking: extractThinkingPayload(data),
                } : m
            ));
        } catch (e: any) {
            setMessages(prev => prev.map(m =>
                m.id === aId ? { ...m, status: "error", error_detail: e.message, content: `Connection error: ${e.message}` } : m
            ));
        } finally {
            setIsStreaming(false); setAvatarState("idle"); scrollToBottom(); loadConversations();
        }
    };

    /* ── Keyboard ─────────────────────────────────────────────── */
    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    };

    /* ── Delete conversation ──────────────────────────────────── */
    const deleteConversation = async (id: string) => {
        try { await arcAgentAPI.deleteConversation(id); } catch { }
        const updated = conversations.filter(c => c.id !== id);
        setConversations(updated);
        if (id === activeConvId) {
            if (updated.length > 0) setActiveConvId(updated[0].id);
            else newConversation();
        }
    };

    /* ── Retry failed message ─────────────────────────────────── */
    const retryMessage = (messageId: string) => {
        const idx = messages.findIndex(m => m.id === messageId);
        if (idx > 0 && messages[idx - 1].role === "user") {
            const userContent = messages[idx - 1].content;
            setMessages(prev => prev.filter(m => m.id !== messageId));
            sendMessage(userContent);
        }
    };

    /* ── Copy message ─────────────────────────────────────────── */
    const copyMessage = (content: string, id: string) => {
        navigator.clipboard.writeText(content);
        setCopied(id);
        setTimeout(() => setCopied(null), 2000);
    };

    /* ── Time grouping ────────────────────────────────────────── */
    const groupByTime = (convs: Conversation[]) => {
        const groups: { label: string; items: Conversation[] }[] = [];
        const today = new Date(); today.setHours(0, 0, 0, 0);
        const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
        const weekAgo = new Date(today); weekAgo.setDate(weekAgo.getDate() - 7);

        const todayItems: Conversation[] = [], yesterdayItems: Conversation[] = [];
        const weekItems: Conversation[] = [], olderItems: Conversation[] = [];

        for (const c of convs) {
            const d = new Date(c.updated_at);
            if (d >= today) todayItems.push(c);
            else if (d >= yesterday) yesterdayItems.push(c);
            else if (d >= weekAgo) weekItems.push(c);
            else olderItems.push(c);
        }

        if (todayItems.length) groups.push({ label: "Today", items: todayItems });
        if (yesterdayItems.length) groups.push({ label: "Yesterday", items: yesterdayItems });
        if (weekItems.length) groups.push({ label: "Previous 7 Days", items: weekItems });
        if (olderItems.length) groups.push({ label: "Older", items: olderItems });
        return groups;
    };

    /* ═══════════════════════════════════════════════════════════════
       RENDER
       ═══════════════════════════════════════════════════════════════ */

    return (
        <div className="flex" style={{ height: "100vh", background: "var(--arc-bg-base)", overflow: "hidden" }}>

            {/* ── Conversation Sidebar ──────────────────────────── */}
            <div className="flex flex-col border-r arc-scroll"
                style={{ width: sidebarOpen ? 240 : 0, minWidth: sidebarOpen ? 240 : 0, background: "var(--arc-bg-surface)", borderColor: "var(--arc-border-subtle)", transition: "all 0.2s ease", overflow: "hidden" }}>

                {/* New Chat button */}
                <div className="p-3 border-b" style={{ borderColor: "var(--arc-border-subtle)" }}>
                    <button onClick={newConversation}
                        className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm font-medium transition-all"
                        style={{ color: "var(--arc-text-accent)", border: "1px solid rgba(139,92,246,0.2)", background: "rgba(139,92,246,0.06)" }}>
                        <Plus size={16} /> New Chat
                    </button>
                </div>

                {/* Conversation list */}
                <div className="flex-1 overflow-y-auto arc-scroll p-2">
                    {groupByTime(conversations).map(group => (
                        <div key={group.label} className="mb-3">
                            <div className="px-3 py-1 text-xs font-medium uppercase tracking-wider" style={{ color: "var(--arc-text-tertiary)" }}>
                                {group.label}
                            </div>
                            {group.items.map(conv => (
                                <div key={conv.id}
                                    className={`arc-conv-item group flex items-center justify-between ${conv.id === activeConvId ? "active" : ""}`}
                                    onClick={() => setActiveConvId(conv.id)}>
                                    <span className="text-sm truncate" style={{ color: conv.id === activeConvId ? "var(--arc-text-primary)" : "var(--arc-text-secondary)" }}>
                                        {conv.title || "New Chat"}
                                    </span>
                                    <button onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id); }}
                                        className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-red-500/10">
                                        <X size={12} style={{ color: "var(--arc-accent-critical)" }} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    ))}
                </div>
            </div>

            {/* ── Main Chat Area ────────────────────────────────── */}
            <div className="flex-1 flex flex-col" style={{ overflow: "hidden" }}>

                {/* Header */}
                <div className="flex items-center justify-between px-5 arc-glass"
                    style={{ height: 64, minHeight: 64, borderBottom: "1px solid rgba(139,92,246,0.15)", boxShadow: "0 4px 24px rgba(139,92,246,0.06)" }}>
                    <div className="flex items-center gap-3">
                        <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-1 rounded hover:bg-white/5 transition mr-1">
                            <ChevronRight size={16} style={{ color: "var(--arc-text-tertiary)", transform: sidebarOpen ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
                        </button>
                        <ArcAvatar state={avatarState} size={40} />
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold" style={{ color: "var(--arc-text-primary)" }}>Arc Agent</span>
                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${arcStatus === "online" ? "arc-status-online" : ""}`}
                                    style={{ background: arcStatus === "online" ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)", color: arcStatus === "online" ? "var(--arc-accent-success)" : "var(--arc-accent-critical)" }}>
                                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: arcStatus === "online" ? "var(--arc-accent-success)" : "var(--arc-accent-critical)" }} />
                                    {arcStatus.toUpperCase()}
                                </span>
                                <span className="inline-flex items-center gap-1 text-[10px]" style={{ color: wsConnected ? "#10B981" : "#F59E0B" }}>
                                    {wsConnected ? <Wifi size={10} /> : <WifiOff size={10} />}
                                </span>
                            </div>
                            <div className="flex items-center gap-2 text-xs" style={{ color: "var(--arc-text-tertiary)" }}>
                                {statusDesc} <span className="text-gray-600">·</span> <ModelIndicator modelName={activeModel} />
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-1">
                        {[
                            { icon: RefreshCw, label: "Refresh", action: () => { loadConversations(); if (activeConvId) loadMessages(activeConvId); } },
                            { icon: Trash2, label: "Clear", action: () => { if (activeConvId) deleteConversation(activeConvId); } },
                            { icon: Plus, label: "New", action: newConversation },
                        ].map(btn => (
                            <button key={btn.label} onClick={btn.action} title={btn.label} className="p-2 rounded-lg transition-all hover:bg-white/5">
                                <btn.icon size={16} style={{ color: "var(--arc-text-tertiary)" }} />
                            </button>
                        ))}
                    </div>
                </div>

                {/* Messages area */}
                <div className="flex-1 overflow-y-auto arc-scroll px-6 py-4" style={{ background: "var(--arc-bg-base)" }}>
                    {messages.length === 0 ? (
                        /* ── Empty State ─────────────────────────────── */
                        <div className="flex flex-col items-center justify-center h-full" style={{ paddingBottom: 40 }}>
                            <ArcAvatar state="idle" size={80} />
                            <h2 className="mt-6 text-2xl font-semibold" style={{ color: "var(--arc-text-primary)" }}>Talk to Arc</h2>
                            <p className="mt-3 text-center max-w-md text-sm leading-relaxed" style={{ color: "var(--arc-text-secondary)" }}>
                                I am Arc Agent — the intelligence controller of Nexearch. I manage clients, pipelines, evolution, and publishing across all 7 platforms. What would you like to do?
                            </p>
                            <div className="flex flex-wrap justify-center gap-2 mt-8">
                                {QUICK_ACTIONS.map(qa => (
                                    <button key={qa.label} className="arc-chip flex items-center gap-1.5" onClick={() => sendMessage(qa.prompt)}>
                                        <qa.icon size={14} /> {qa.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                    ) : (
                        /* ── Message List ────────────────────────────── */
                        <>
                            {messages.map((msg) => (
                                <div key={msg.id} className={`flex gap-3 mb-5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                                    {msg.role === "assistant" && <ArcAvatar state={msg.status === "streaming" ? "responding" : "idle"} size={32} />}
                                    <div className={`max-w-[75%] ${msg.role === "user" ? "ml-auto" : ""}`}>
                                        <div className="flex items-center gap-2 mb-1" style={{ flexDirection: msg.role === "user" ? "row-reverse" : "row" }}>
                                            <span className="text-xs font-semibold uppercase tracking-wider"
                                                style={{ color: msg.role === "assistant" ? "var(--arc-text-accent)" : "var(--arc-text-secondary)" }}>
                                                {msg.role === "assistant" ? "Arc Agent" : "You"}
                                            </span>
                                            <span className="text-[10px]" style={{ color: "var(--arc-text-tertiary)" }}>{msg.timestamp}</span>
                                        </div>
                                        <div className="relative group rounded-xl px-4 py-3"
                                            style={{
                                                background: msg.status === "error" ? "rgba(239,68,68,0.08)" : msg.role === "user" ? "rgba(139,92,246,0.12)" : "var(--arc-bg-elevated)",
                                                border: msg.status === "error" ? "1px solid rgba(239,68,68,0.3)" : msg.role === "user" ? "1px solid rgba(139,92,246,0.25)" : "1px solid var(--arc-border-subtle)",
                                                borderLeft: msg.role === "assistant" && msg.status !== "error" ? "2px solid var(--arc-accent)" : undefined,
                                            }}>
                                            {msg.role === "assistant" && msg.status === "streaming" && !msg.content ? (
                                                <div className="flex items-center gap-2">
                                                    <span className="arc-dot w-2 h-2 rounded-full" style={{ background: "var(--arc-accent)" }} />
                                                    <span className="arc-dot w-2 h-2 rounded-full" style={{ background: "var(--arc-accent)" }} />
                                                    <span className="arc-dot w-2 h-2 rounded-full" style={{ background: "var(--arc-accent)" }} />
                                                    <span className="text-xs" style={{ color: "var(--arc-text-tertiary)" }}>Arc is thinking...</span>
                                                </div>
                                            ) : msg.status === "error" ? (
                                                <div>
                                                    {msg.content && <div className="mb-2"><MarkdownRenderer content={msg.content} /></div>}
                                                    <div className="flex items-center gap-2 mt-2 pt-2" style={{ borderTop: "1px solid rgba(239,68,68,0.15)" }}>
                                                        <AlertCircle size={14} style={{ color: "#EF4444" }} />
                                                        <span className="text-xs" style={{ color: "#EF4444" }}>{msg.error_detail || "Response generation failed"}</span>
                                                        <button onClick={() => retryMessage(msg.id)} className="ml-auto flex items-center gap-1 text-xs px-2 py-1 rounded-lg transition-all hover:bg-white/5" style={{ color: "#A78BFA" }}>
                                                            <RotateCcw size={12} /> Retry
                                                        </button>
                                                    </div>
                                                </div>
                                            ) : (
                                                <div className="arc-markdown-container">
                                                    {msg.thinking && msg.thinking.trim() && (
                                                        <ThinkingBlock thinking={msg.thinking} accentColor="#8B5CF6" />
                                                    )}
                                                    <MarkdownRenderer
                                                        content={msg.content || (msg.role === "assistant" ? "Response completed." : "")}
                                                        isStreaming={msg.status === "streaming"}
                                                    />
                                                </div>
                                            )}
                                            {msg.content && msg.status !== "streaming" && (
                                                <button onClick={() => copyMessage(msg.content, msg.id)}
                                                    className="absolute top-2 right-2 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white/10">
                                                    {copied === msg.id ? <Check size={12} style={{ color: "var(--arc-accent-success)" }} /> : <Copy size={12} style={{ color: "var(--arc-text-tertiary)" }} />}
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                            <div ref={chatEndRef} />
                        </>
                    )}
                </div>

                {/* Input zone */}
                <div className="px-5 pb-4 pt-2" style={{ background: "var(--arc-bg-base)" }}>
                    {/* Quick actions (when messages exist) */}
                    {messages.length > 0 && (
                        <div className="flex gap-2 mb-2 overflow-x-auto pb-1 arc-scroll" style={{ scrollbarWidth: "none" }}>
                            {QUICK_ACTIONS.slice(0, 4).map(qa => (
                                <button key={qa.label} className="arc-chip flex items-center gap-1 text-xs" onClick={() => sendMessage(qa.prompt)}>
                                    <qa.icon size={12} /> {qa.label}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Input bar */}
                    <div className="flex items-end gap-3 rounded-xl px-4 py-3 transition-all"
                        style={{ background: "var(--arc-bg-elevated)", border: "1px solid var(--arc-border-default)" }}
                        onFocus={(e) => e.currentTarget.style.borderColor = "rgba(139,92,246,0.4)"}
                        onBlur={(e) => e.currentTarget.style.borderColor = "var(--arc-border-default)"}>
                        <textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
                            placeholder="Talk to Arc... (try: List all clients)"
                            rows={1}
                            className="flex-1 bg-transparent outline-none resize-none text-sm"
                            style={{ color: "var(--arc-text-primary)", maxHeight: 120, fontFamily: "Inter, sans-serif" }}
                            disabled={isStreaming} />
                        <button onClick={() => sendMessage()} disabled={!input.trim() || isStreaming} className="rounded-lg p-2 transition-all"
                            style={{ background: input.trim() ? "var(--arc-accent)" : "transparent", opacity: input.trim() ? 1 : 0.3 }}>
                            <Send size={16} style={{ color: input.trim() ? "#fff" : "var(--arc-text-tertiary)" }} />
                        </button>
                    </div>

                    {/* Footer hint */}
                    <div className="flex justify-between mt-2 px-1">
                        <span className="text-[11px]" style={{ color: "var(--arc-text-tertiary)" }}>
                            Shift+Enter for new line · / for commands
                        </span>
                        <span className="text-[11px]" style={{ color: "var(--arc-text-tertiary)", fontFamily: "JetBrains Mono, monospace" }}>
                            {activeModel}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}
