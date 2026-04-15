"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
    Send, Plus, Trash2, RefreshCw, Download, MoreHorizontal,
    Zap, Activity, BarChart3, Bot, Wrench, ScrollText,
    FolderOpen, Copy, Check, ChevronRight, ChevronDown, X,
    AlertCircle, Wifi, WifiOff, RotateCcw
} from "lucide-react";
import { nexAgentAPI } from "@/lib/api";
import { MarkdownRenderer } from "@/components/nex/MarkdownRenderer";
import { ModelIndicator } from "@/components/nex/ModelIndicator";
import "./nex-styles.css";

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
    rawContent?: string; // raw buffer for <think> tag extraction
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

    const richData = message?.rich_data;
    if (!richData) return "";

    if (typeof richData === "object" && typeof richData.thinking_content === "string") {
        return richData.thinking_content;
    }

    if (typeof richData === "string") {
        try {
            const parsed = JSON.parse(richData);
            if (typeof parsed?.thinking_content === "string") return parsed.thinking_content;
        } catch { }
    }

    return "";
}

function appendThinkingEntry(existing: string | undefined, entry: string): string {
    const cleanEntry = String(entry || "").trim().replace(/\s+/g, " ");
    if (!cleanEntry) return existing || "";

    const current = (existing || "").trim();
    const nextLine = `- ${cleanEntry}`;
    const currentLines = current ? current.split("\n").map(line => line.trim()) : [];
    if (currentLines.includes(nextLine)) {
        return current;
    }
    return current ? `${current}\n${nextLine}` : nextLine;
}

function buildToolThinkingLabel(data: any): string {
    const toolName = String(data?.name || "").trim();
    if (!toolName) return "Running a tool";

    if (toolName === "nexearch_chat_with_arc") {
        return data?.status === "complete" ? "Arc Agent returned intelligence" : "Consulting Arc Agent";
    }
    if (toolName === "nex_process_pipeline") {
        return data?.status === "complete" ? "Full pipeline prepared" : "Preparing the full clip pipeline";
    }
    if (toolName === "nex_process_video") {
        return data?.status === "complete" ? "Video processing started" : "Starting video processing";
    }

    return data?.status === "complete" ? `Completed ${toolName}` : `Executing ${toolName}`;
}

const NEX_API = "http://localhost:8001/api/nex";
const NEX_WS = "ws://localhost:8001/ws/chat";

/* ═══════════════════════════════════════════════════════════════
   ANIMATED AVATAR (SVG)
   ═══════════════════════════════════════════════════════════════ */

function NexAvatar({ state = "idle", size = 48 }: { state?: string; size?: number }) {
    const cls = `nex-avatar-${state}`;
    return (
        <div className={cls} style={{ width: size, height: size, position: "relative", flexShrink: 0 }}>
            <svg viewBox="0 0 100 100" width={size} height={size}>
                <circle className="nex-ring" cx="50" cy="50" r="45" fill="none"
                    stroke="url(#ringGrad)" strokeWidth="2" strokeDasharray="12 6"
                    style={{ transformOrigin: "50% 50%" }} />
                <circle className="nex-glow" cx="50" cy="50" r="28"
                    fill="url(#coreGlow)" opacity="0.4" />
                <polygon className="nex-core" points="50,22 72,40 66,65 34,65 28,40"
                    fill="url(#crystalGrad)" stroke="rgba(99,102,241,0.5)" strokeWidth="1"
                    style={{ transformOrigin: "50% 50%" }} />
                <circle cx="50" cy="47" r="5" fill="#818CF8" opacity="0.9" />
                {state === "thinking" && (
                    <>
                        <circle className="nex-orbit" cx="50" cy="50" r="2" fill="#8B5CF6"
                            style={{ transformOrigin: "50% 50%" }} />
                        <circle className="nex-orbit" cx="50" cy="50" r="1.5" fill="#06B6D4"
                            style={{ transformOrigin: "50% 50%", animationDelay: "0.7s" }} />
                    </>
                )}
                {state === "responding" && (
                    <circle className="nex-wave" cx="50" cy="50" r="12"
                        fill="none" stroke="rgba(99,102,241,0.3)" strokeWidth="1"
                        style={{ transformOrigin: "50% 50%" }} />
                )}
                <defs>
                    <radialGradient id="coreGlow"><stop offset="0%" stopColor="#6366F1" /><stop offset="100%" stopColor="transparent" /></radialGradient>
                    <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#6366F1" /><stop offset="100%" stopColor="#8B5CF6" /></linearGradient>
                    <linearGradient id="crystalGrad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="rgba(99,102,241,0.3)" /><stop offset="100%" stopColor="rgba(139,92,246,0.2)" /></linearGradient>
                </defs>
            </svg>
        </div>
    );
}

/* ═══════════════════════════════════════════════════════════════
   THINKING BLOCK — collapsible reasoning disclosure
   ═══════════════════════════════════════════════════════════════ */

function ThinkingBlock({ thinking, accentColor = "#6366F1", isStreaming = false }: { thinking: string; accentColor?: string; isStreaming?: boolean }) {
    const [open, setOpen] = useState(isStreaming);

    useEffect(() => {
        if (isStreaming) {
            setOpen(true);
        } else if (!isStreaming && thinking.trim().length > 0) {
            const t = setTimeout(() => setOpen(false), 600);
            return () => clearTimeout(t);
        }
    }, [isStreaming, thinking]);

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
    { icon: Zap, label: "System Status", prompt: "/status" },
    { icon: Activity, label: "Database Stats", prompt: "How many clips have been generated?" },
    { icon: BarChart3, label: "Clip Stats", prompt: "How many clips have been generated?" },
    { icon: Bot, label: "View Agents", prompt: "/agents" },
    { icon: Wrench, label: "Recent Patches", prompt: "/patches" },
    { icon: ScrollText, label: "View Logs", prompt: "/logs" },
    { icon: FolderOpen, label: "Explore Codebase", prompt: "Give me a summary of the NexClip codebase." },
];

/* ═══════════════════════════════════════════════════════════════
   MAIN PAGE COMPONENT
   ═══════════════════════════════════════════════════════════════ */

export default function NexAgentPage() {
    /* ── State ─────────────────────────────────────────────────── */
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [activeConvId, setActiveConvId] = useState<string>("");
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isStreaming, setIsStreaming] = useState(false);
    const [avatarState, setAvatarState] = useState<string>("idle");
    const [nexStatus, setNexStatus] = useState<string>("online");
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
    const pendingMsgIdRef = useRef<string | null>(null);  // local placeholder before stream_start

    useEffect(() => {
        messagesRef.current = messages;
        convIdRef.current = activeConvId;
    }, [messages, activeConvId]);

    /* ── Helpers ────────────────────────────────────────────────── */
    const genId = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
    const now = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const getToken = () => typeof window !== "undefined" ? localStorage.getItem("nexclip_token") || "" : "";
    const getUserId = (): string => {
        try {
            const user = localStorage.getItem("nexclip_user");
            if (user) return JSON.parse(user).id || "anonymous";
        } catch { }
        return "anonymous";
    };

    const scrollToBottom = useCallback(() => {
        setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }, []);

    /* ── Load conversations from DB ──────────────────────────── */
    const loadConversations = useCallback(async () => {
        try {
            const res = await nexAgentAPI.listConversations();
            setConversations(res.conversations || []);
            return res.conversations || [];
        } catch {
            return [];
        }
    }, []);

    /* ── Load messages for a conversation ────────────────────── */
    const loadMessages = useCallback(async (convId: string) => {
        try {
            const res = await nexAgentAPI.getMessages(convId);
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
        } catch {
            setMessages([]);
        }
    }, [scrollToBottom]);

    /* ── Create new conversation ──────────────────────────────── */
    const newConversation = useCallback(async () => {
        try {
            const res = await nexAgentAPI.createConversation();
            const newId = res.id;
            if (newId) {
                setActiveConvId(newId);
                setMessages([]);
                setInput("");
                await loadConversations();
            }
        } catch {
            // Fallback: create local-only
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
        if (activeConvId) {
            loadMessages(activeConvId);
        }
    }, [activeConvId, loadMessages]);

    /* ── Fetch status and model ───────────────────────────────── */
    useEffect(() => {
        const fetchInfo = async () => {
            try {
                const [statusRes, modelRes] = await Promise.all([
                    nexAgentAPI.getStatus(),
                    nexAgentAPI.getModel(),
                ]);
                if (statusRes) {
                    setNexStatus(statusRes.nex_status || "online");
                    setStatusDesc(statusRes.status_description || "Fully operational");
                }
                if (modelRes?.active_model) {
                    setActiveModel(modelRes.active_model);
                }
            } catch { setNexStatus("offline"); setActiveModel("Disconnected"); }
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

        const userId = getUserId();
        const latestMsgs = messagesRef.current;
        const lastMsgId = (latestMsgs.length > 0 && convIdRef.current === activeConvId) ? latestMsgs[latestMsgs.length - 1].id : "";
        const url = `${NEX_WS}?user_id=${userId}&conversation_id=${activeConvId}&last_message_id=${lastMsgId}`;

        try {
            shouldReconnectRef.current = true;
            const ws = new WebSocket(url);
            wsRef.current = ws;

            ws.onopen = () => {
                setWsConnected(true);
                reconnectRef.current = 0;
                if (reconnectTimerRef.current) {
                    clearTimeout(reconnectTimerRef.current);
                    reconnectTimerRef.current = null;
                }
            };

            ws.onclose = () => {
                setWsConnected(false);
                if (wsRef.current === ws) {
                    wsRef.current = null;
                }
                if (!shouldReconnectRef.current || !activeConvId) {
                    return;
                }
                // Exponential backoff reconnection
                const delay = Math.min(1000 * Math.pow(2, reconnectRef.current), 30000);
                reconnectRef.current += 1;
                reconnectTimerRef.current = setTimeout(connectWs, delay);
            };

            ws.onerror = () => {
                ws.close();
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    handleWsMessage(data);
                } catch { }
            };
        } catch {
            // WS connection failed — schedule retry
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
            if (document.visibilityState === "visible" && !wsConnected) {
                connectWs();
            }
        };
        document.addEventListener("visibilitychange", handleVisibility);
        return () => document.removeEventListener("visibilitychange", handleVisibility);
    }, [connectWs, wsConnected]);

    /* ── Handle incoming WebSocket messages ───────────────────── */
    const handleWsMessage = useCallback((data: any) => {
        const type = data.type;
        const messageId = data.message_id;

        if (type === "stream_start") {
            // Promote the local placeholder to the server's assigned ID
            const serverId = data.assistant_message_id;
            const localId = pendingMsgIdRef.current;
            if (localId && serverId && localId !== serverId) {
                setMessages(prev => prev.map(m =>
                    m.id === localId ? { ...m, id: serverId, thinking: m.thinking || "- Preparing response" } : m
                ));
            } else if (!localId) {
                // No local placeholder — add fallback
                setMessages(prev => [...prev, {
                    id: serverId, role: "assistant" as const, content: "", timestamp: now(), status: "streaming" as const, thinking: "- Preparing response",
                }]);
            }
            pendingMsgIdRef.current = null;
            setAvatarState("responding");
            scrollToBottom();
        }
        else if (type === "token") {
            setMessages(prev => prev.map(m => {
                if (m.id === messageId) {
                    const raw = (m.rawContent || m.content) + data.token;
                    let newContent = raw;
                    let newThinking = m.thinking || "";
                    
                    const thinkMatch = raw.match(/<think>([\s\S]*?)(?:<\/think>|$)/i);
                    if (thinkMatch) {
                        newThinking = thinkMatch[1].trim();
                        newContent = raw.replace(/<think>[\s\S]*?(?:<\/think>|$)/i, "").trim();
                    }
                    
                    return { ...m, rawContent: raw, content: newContent, thinking: newThinking };
                }
                return m;
            }));
            scrollToBottom();
        }
        else if (type === "done") {
            setMessages(prev => prev.map(m => {
                if (m.id === messageId) {
                    return {
                        ...m,
                        status: "complete",
                        content: data.full_content || m.content,
                        thinking: data.thinking_content || m.thinking || "",
                    };
                }
                return m;
            }));
            setIsStreaming(false);
            setAvatarState("idle");
            scrollToBottom();
            // Refresh conversation list to get updated title
            loadConversations();
        }

        else if (type === "error") {
            setMessages(prev => prev.map(m => {
                if (m.id === messageId) {
                    return {
                        ...m,
                        status: "error",
                        error_detail: data.error || "Unknown error occurred",
                        content: m.content || "An error occurred while generating the response.",
                    };
                }
                return m;
            }));
            setIsStreaming(false);
            setAvatarState("idle");
        }

        else if (type === "replay") {
            // Reconnection replay — update message with full content
            setMessages(prev => {
                const exists = prev.find(m => m.id === messageId);
                if (exists) {
                    return prev.map(m => {
                        if (m.id === messageId) {
                            return {
                                ...m,
                                content: data.content || m.content,
                                status: data.status || m.status,
                                error_detail: data.error,
                                thinking: data.thinking_content || m.thinking || "",
                            };
                        }
                        return m;
                    });
                }
                // Message not in local state — add it
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
            if (data.status === "streaming") {
                setIsStreaming(true);
                setAvatarState("responding");
            } else {
                setIsStreaming(false);
                setAvatarState("idle");
            }
            scrollToBottom();
        }

        else if (type === "tool_call") {
            const thinkingLine = buildToolThinkingLabel(data);
            setMessages(prev => prev.map(m =>
                m.id === messageId ? { ...m, thinking: appendThinkingEntry(m.thinking, thinkingLine) } : m
            ));
        }

        else if (type === "status") {
            const statusText = data.content || data.message || data.status || "";
            setMessages(prev => prev.map(m =>
                m.id === messageId ? { ...m, thinking: appendThinkingEntry(m.thinking, statusText) } : m
            ));
        }

        else if (type === "proactive_message") {
            if (data.conversation_id && data.conversation_id !== activeConvId) {
                loadConversations();
                return;
            }
            const proactiveMsg: Message = {
                id: messageId || genId(),
                role: "assistant",
                content: data.content || data.notification?.message || "",
                timestamp: now(),
                status: "complete",
            };

            setMessages(prev => {
                const existing = prev.find(m => m.id === proactiveMsg.id);
                if (existing) {
                    return prev.map(m => m.id === proactiveMsg.id ? proactiveMsg : m);
                }
                return [...prev, proactiveMsg];
            });
            setIsStreaming(false);
            setAvatarState("idle");
            scrollToBottom();
            loadConversations();
        }
    }, [scrollToBottom, loadConversations, activeConvId]);

    /* ── Send message via WebSocket ───────────────────────────── */
    const sendMessage = async (text?: string) => {
        const msg = (text || input).trim();
        if (!msg || isStreaming) return;

        // Add user message locally immediately
        const userMsg: Message = {
            id: genId(),
            role: "user",
            content: msg,
            timestamp: now(),
            status: "complete",
        };
        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setIsStreaming(true);
        setAvatarState("thinking");
        scrollToBottom();

        // Inject thinking placeholder immediately
        const localPlaceholderId = genId();
        pendingMsgIdRef.current = localPlaceholderId;
        setMessages(prev => [...prev, {
            id: localPlaceholderId,
            role: "assistant" as const,
            content: "",
            timestamp: now(),
            status: "streaming" as const,
        }]);
        scrollToBottom();

        // Send via WebSocket if connected
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                message: msg,
                conversation_id: activeConvId,
            }));
        } else {
            // SSE fallback — remove placeholder, SSE creates its own
            setMessages(prev => prev.filter(m => m.id !== localPlaceholderId));
            pendingMsgIdRef.current = null;
            await sendViaSse(msg);
        }
    };

    /* ── SSE fallback ─────────────────────────────────────────── */
    const sendViaSse = async (msg: string) => {
        const assistantMsg: Message = {
            id: genId(),
            role: "assistant",
            content: "",
            timestamp: now(),
            status: "streaming",
            thinking: "- Preparing response",
        };
        setMessages(prev => [...prev, assistantMsg]);
        setAvatarState("responding");

        try {
            const token = getToken();
            const headers: Record<string, string> = { "Content-Type": "application/json" };
            if (token) headers["Authorization"] = `Bearer ${token}`;

            const res = await fetch(`${NEX_API}/chat`, {
                method: "POST",
                headers,
                body: JSON.stringify({ message: msg, conversation_id: activeConvId }),
            });

            if (!res.body) throw new Error("No response body");
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let fullContent = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const text = decoder.decode(value, { stream: true });
                const lines = text.split("\n");

                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.type === "token") {
                            fullContent += data.content;
                            setMessages(prev => prev.map(m =>
                                m.id === assistantMsg.id ? { ...m, content: fullContent } : m
                            ));
                            scrollToBottom();
                        } else if (data.type === "status") {
                            const statusText = data.content || data.message || data.status || "";
                            setMessages(prev => prev.map(m =>
                                m.id === assistantMsg.id ? { ...m, thinking: appendThinkingEntry(m.thinking, statusText) } : m
                            ));
                        } else if (data.type === "tool_call") {
                            setMessages(prev => prev.map(m =>
                                m.id === assistantMsg.id ? { ...m, thinking: appendThinkingEntry(m.thinking, buildToolThinkingLabel(data)) } : m
                            ));
                        } else if (data.type === "done") {
                            setMessages(prev => prev.map(m =>
                                m.id === assistantMsg.id ? {
                                    ...m,
                                    content: data.full_content || fullContent,
                                    thinking: data.thinking_content || m.thinking || "",
                                    status: "complete",
                                } : m
                            ));
                        } else if (data.type === "error") {
                            setMessages(prev => prev.map(m =>
                                m.id === assistantMsg.id ? {
                                    ...m,
                                    status: "error",
                                    error_detail: data.content,
                                    content: m.content || data.content,
                                } : m
                            ));
                        }
                    } catch { }
                }
            }
        } catch (err: any) {
            setMessages(prev => prev.map(m =>
                m.id === assistantMsg.id ? {
                    ...m,
                    status: "error",
                    content: m.content || `Connection error: ${err.message}`,
                    error_detail: err.message,
                } : m
            ));
        } finally {
            setIsStreaming(false);
            setAvatarState("idle");
            scrollToBottom();
            loadConversations();
        }
    };

    /* ── Handle keydown ───────────────────────────────────────── */
    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    /* ── Delete conversation ──────────────────────────────────── */
    const deleteConversation = async (id: string) => {
        try {
            await nexAgentAPI.deleteConversation(id);
        } catch { }
        const updated = conversations.filter(c => c.id !== id);
        setConversations(updated);
        if (id === activeConvId) {
            if (updated.length > 0) {
                setActiveConvId(updated[0].id);
            } else {
                newConversation();
            }
        }
    };

    /* ── Retry failed message ─────────────────────────────────── */
    const retryMessage = (messageId: string) => {
        // Find the user message before this error
        const idx = messages.findIndex(m => m.id === messageId);
        if (idx > 0 && messages[idx - 1].role === "user") {
            const userContent = messages[idx - 1].content;
            // Remove the failed message
            setMessages(prev => prev.filter(m => m.id !== messageId));
            // Re-send
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

        const todayItems: Conversation[] = [];
        const yesterdayItems: Conversation[] = [];
        const weekItems: Conversation[] = [];
        const olderItems: Conversation[] = [];

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

    /* ── Render markdown (basic) ──────────────────────────────── */
    // Removed old renderMarkdown regex parser - now using Universal MarkdownRenderer component

    /* ═══════════════════════════════════════════════════════════════
       RENDER
       ═══════════════════════════════════════════════════════════════ */

    return (
        <div
            className="flex"
            style={{
                height: "100vh",
                background: "var(--nex-bg-base)",
                overflow: "hidden",
            }}
        >
            {/* ── Conversation Sidebar ──────────────────────────── */}
            <div
                className="flex flex-col border-r nex-scroll"
                style={{
                    width: sidebarOpen ? 240 : 0,
                    minWidth: sidebarOpen ? 240 : 0,
                    background: "var(--nex-bg-surface)",
                    borderColor: "var(--nex-border-subtle)",
                    transition: "all 0.2s ease",
                    overflow: "hidden",
                }}
            >
                {/* New Chat button */}
                <div className="p-3 border-b" style={{ borderColor: "var(--nex-border-subtle)" }}>
                    <button
                        onClick={newConversation}
                        className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm font-medium transition-all"
                        style={{ color: "var(--nex-text-accent)", border: "1px solid rgba(99,102,241,0.2)", background: "rgba(99,102,241,0.06)" }}
                    >
                        <Plus size={16} />
                        New Chat
                    </button>
                </div>

                {/* Conversation list */}
                <div className="flex-1 overflow-y-auto nex-scroll p-2">
                    {groupByTime(conversations).map(group => (
                        <div key={group.label} className="mb-3">
                            <div className="px-3 py-1 text-xs font-medium uppercase tracking-wider" style={{ color: "var(--nex-text-tertiary)" }}>
                                {group.label}
                            </div>
                            {group.items.map(conv => (
                                <div
                                    key={conv.id}
                                    className={`nex-conv-item group flex items-center justify-between ${conv.id === activeConvId ? "active" : ""}`}
                                    onClick={() => setActiveConvId(conv.id)}
                                >
                                    <span className="text-sm truncate" style={{ color: conv.id === activeConvId ? "var(--nex-text-primary)" : "var(--nex-text-secondary)" }}>
                                        {conv.title || "New Chat"}
                                    </span>
                                    <button
                                        onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id); }}
                                        className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-red-500/10"
                                    >
                                        <X size={12} style={{ color: "var(--nex-accent-critical)" }} />
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
                <div
                    className="flex items-center justify-between px-5 nex-glass"
                    style={{
                        height: 64, minHeight: 64,
                        borderBottom: "1px solid rgba(99,102,241,0.15)",
                        boxShadow: "0 4px 24px rgba(99,102,241,0.06)",
                    }}
                >
                    <div className="flex items-center gap-3">
                        <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-1 rounded hover:bg-white/5 transition mr-1">
                            <ChevronRight size={16} style={{ color: "var(--nex-text-tertiary)", transform: sidebarOpen ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
                        </button>
                        <NexAvatar state={avatarState} size={40} />
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold" style={{ color: "var(--nex-text-primary)" }}>Nex Agent</span>
                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${nexStatus === "online" ? "nex-status-online" : ""}`}
                                    style={{
                                        background: nexStatus === "online" ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)",
                                        color: nexStatus === "online" ? "var(--nex-accent-success)" : "var(--nex-accent-critical)",
                                    }}>
                                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: nexStatus === "online" ? "var(--nex-accent-success)" : "var(--nex-accent-critical)" }} />
                                    {nexStatus.toUpperCase()}
                                </span>
                                {/* WebSocket connection indicator */}
                                <span className="inline-flex items-center gap-1 text-[10px]" style={{ color: wsConnected ? "#10B981" : "#F59E0B" }}>
                                    {wsConnected ? <Wifi size={10} /> : <WifiOff size={10} />}
                                </span>
                            </div>
                            <div className="flex items-center gap-2 text-xs" style={{ color: "var(--nex-text-tertiary)" }}>
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
                            <button
                                key={btn.label}
                                onClick={btn.action}
                                title={btn.label}
                                className="p-2 rounded-lg transition-all hover:bg-white/5"
                            >
                                <btn.icon size={16} style={{ color: "var(--nex-text-tertiary)" }} />
                            </button>
                        ))}
                    </div>
                </div>

                {/* Messages area */}
                <div className="flex-1 overflow-y-auto nex-scroll px-6 py-4" style={{ background: "var(--nex-bg-base)" }}>
                    {messages.length === 0 ? (
                        /* ── Empty State ─────────────────────────────── */
                        <div className="flex flex-col items-center justify-center h-full" style={{ paddingBottom: 40 }}>
                            <NexAvatar state="idle" size={80} />
                            <h2 className="mt-6 text-2xl font-semibold" style={{ color: "var(--nex-text-primary)" }}>Talk to Nex</h2>
                            <p className="mt-3 text-center max-w-md text-sm leading-relaxed" style={{ color: "var(--nex-text-secondary)" }}>
                                I am the master intelligence running NexClip. I have full visibility into every system, every file, and every agent. What would you like to know or do?
                            </p>
                            <div className="flex flex-wrap justify-center gap-2 mt-8">
                                {QUICK_ACTIONS.map(qa => (
                                    <button key={qa.label} className="nex-chip flex items-center gap-1.5" onClick={() => sendMessage(qa.prompt)}>
                                        <qa.icon size={14} />
                                        {qa.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                    ) : (
                        /* ── Message List ────────────────────────────── */
                        <>
                            {messages.map((msg) => (
                                <div key={msg.id} className={`flex gap-3 mb-5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                                    {msg.role === "assistant" && <NexAvatar state={msg.status === "streaming" ? "responding" : "idle"} size={32} />}
                                    <div className={`max-w-[75%] ${msg.role === "user" ? "ml-auto" : ""}`}>
                                        <div className="flex items-center gap-2 mb-1" style={{ flexDirection: msg.role === "user" ? "row-reverse" : "row" }}>
                                            <span className="text-xs font-semibold uppercase tracking-wider"
                                                style={{ color: msg.role === "assistant" ? "var(--nex-text-accent)" : "var(--nex-text-secondary)" }}>
                                                {msg.role === "assistant" ? "Nex Agent" : "You"}
                                            </span>
                                            <span className="text-[10px]" style={{ color: "var(--nex-text-tertiary)" }}>{msg.timestamp}</span>
                                        </div>
                                        <div
                                            className="relative group rounded-xl px-4 py-3"
                                            style={{
                                                background: msg.status === "error"
                                                    ? "rgba(239,68,68,0.08)"
                                                    : msg.role === "user"
                                                        ? "rgba(99,102,241,0.12)"
                                                        : "var(--nex-bg-elevated)",
                                                border: msg.status === "error"
                                                    ? "1px solid rgba(239,68,68,0.3)"
                                                    : msg.role === "user"
                                                        ? "1px solid rgba(99,102,241,0.25)"
                                                        : "1px solid var(--nex-border-subtle)",
                                                borderLeft: msg.role === "assistant" && msg.status !== "error" ? "2px solid var(--nex-accent)" : undefined,
                                            }}
                                        >
                                            {/* Content — never empty */}
                                            {msg.role === "assistant" && msg.status === "streaming" && !msg.content ? (
                                                /* Thinking indicator — never show empty bubble */
                                                <div className="flex items-center gap-2">
                                                    <span className="nex-dot w-2 h-2 rounded-full" style={{ background: "var(--nex-accent)" }} />
                                                    <span className="nex-dot w-2 h-2 rounded-full" style={{ background: "var(--nex-accent)" }} />
                                                    <span className="nex-dot w-2 h-2 rounded-full" style={{ background: "var(--nex-accent)" }} />
                                                    <span className="text-xs" style={{ color: "var(--nex-text-tertiary)" }}>Nex is thinking...</span>
                                                </div>
                                            ) : msg.status === "error" ? (
                                                /* Error state with retry */
                                                <div>
                                                    {msg.content && <div className="mb-2"><MarkdownRenderer content={msg.content} /></div>}
                                                    <div className="flex items-center gap-2 mt-2 pt-2" style={{ borderTop: "1px solid rgba(239,68,68,0.15)" }}>
                                                        <AlertCircle size={14} style={{ color: "#EF4444" }} />
                                                        <span className="text-xs" style={{ color: "#EF4444" }}>
                                                            {msg.error_detail || "Response generation failed"}
                                                        </span>
                                                        <button
                                                            onClick={() => retryMessage(msg.id)}
                                                            className="ml-auto flex items-center gap-1 text-xs px-2 py-1 rounded-lg transition-all hover:bg-white/5"
                                                            style={{ color: "#818CF8" }}
                                                        >
                                                            <RotateCcw size={12} /> Retry
                                                        </button>
                                                    </div>
                                                </div>
                                            ) : (
                                                /* Normal content */
                                                <div className="nex-markdown-container">
                                                    {msg.thinking && msg.thinking.trim() && (
                                                        <ThinkingBlock 
                                                            thinking={msg.thinking} 
                                                            accentColor="#6366F1" 
                                                            isStreaming={msg.status === "streaming"} 
                                                        />
                                                    )}
                                                    <MarkdownRenderer
                                                        content={msg.content || (msg.role === "assistant" ? "Response completed." : "")}
                                                        isStreaming={msg.status === "streaming"}
                                                    />
                                                </div>
                                            )}

                                            {/* Copy button */}
                                            {msg.content && msg.status !== "streaming" && (
                                                <button
                                                    onClick={() => copyMessage(msg.content, msg.id)}
                                                    className="absolute top-2 right-2 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white/10"
                                                >
                                                    {copied === msg.id ? <Check size={12} style={{ color: "var(--nex-accent-success)" }} /> : <Copy size={12} style={{ color: "var(--nex-text-tertiary)" }} />}
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
                <div className="px-5 pb-4 pt-2" style={{ background: "var(--nex-bg-base)" }}>
                    {/* Quick actions (when messages exist) */}
                    {messages.length > 0 && (
                        <div className="flex gap-2 mb-2 overflow-x-auto pb-1 nex-scroll" style={{ scrollbarWidth: "none" }}>
                            {QUICK_ACTIONS.slice(0, 4).map(qa => (
                                <button key={qa.label} className="nex-chip flex items-center gap-1 text-xs" onClick={() => sendMessage(qa.prompt)}>
                                    <qa.icon size={12} /> {qa.label}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Input bar */}
                    <div
                        className="flex items-end gap-2 rounded-2xl px-4 py-2.5 transition-all"
                        style={{
                            background: "var(--nex-bg-elevated)",
                            border: "1px solid var(--nex-border-default)",
                            boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
                        }}
                        onFocus={(e) => e.currentTarget.style.borderColor = "rgba(99,102,241,0.4)"}
                        onBlur={(e) => e.currentTarget.style.borderColor = "var(--nex-border-default)"}
                    >
                        <textarea
                            ref={inputRef}
                            value={input}
                            onChange={(e) => {
                                setInput(e.target.value);
                                // Auto-resize
                                e.target.style.height = "auto";
                                e.target.style.height = Math.min(e.target.scrollHeight, 200) + "px";
                            }}
                            onKeyDown={handleKeyDown}
                            placeholder="Talk to Nex... (try /status)"
                            rows={1}
                            className="flex-1 bg-transparent outline-none resize-none text-sm leading-relaxed"
                            style={{
                                color: "var(--nex-text-primary)",
                                minHeight: 24,
                                maxHeight: 200,
                                fontFamily: "Inter, sans-serif",
                                overflowY: "auto",
                                scrollbarWidth: "none",
                            }}
                            disabled={isStreaming}
                        />
                        <button
                            onClick={() => sendMessage()}
                            disabled={!input.trim() || isStreaming}
                            className="rounded-full p-2 transition-all flex-shrink-0 mb-0.5"
                            style={{
                                background: input.trim() ? "var(--nex-accent)" : "transparent",
                                opacity: input.trim() ? 1 : 0.3,
                            }}
                        >
                            <Send size={16} style={{ color: input.trim() ? "#fff" : "var(--nex-text-tertiary)" }} />
                        </button>
                    </div>

                    {/* Footer hint */}
                    <div className="flex justify-between mt-1.5 px-1">
                        <span className="text-[11px]" style={{ color: "var(--nex-text-tertiary)" }}>
                            Shift+Enter for new line · / for commands
                        </span>
                        <span className="text-[11px]" style={{ color: "var(--nex-text-tertiary)", fontFamily: "JetBrains Mono, monospace" }}>
                            {activeModel}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}
