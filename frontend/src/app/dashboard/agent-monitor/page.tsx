"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
    Terminal, Pause, Play, Trash2, Filter,
    Maximize2, Minimize2, Wifi, WifiOff
} from "lucide-react";

/* ── Types ──────────────────────────────────────────────────── */
interface BusMessage {
    id: string;
    from_agent: string;
    from_name: string;
    from_color: string;
    from_icon: string;
    to_agent: string;
    to_name: string;
    to_color: string;
    message_type: string;
    content: string;
    metadata: Record<string, any>;
    timestamp: string;
}

const NEX_WS = "ws://localhost:8001/ws/agent-bus";

const MSG_TYPE_LABELS: Record<string, { label: string; color: string }> = {
    chat: { label: "CHAT", color: "#60A5FA" },
    task_delegation: { label: "TASK", color: "#F59E0B" },
    status_update: { label: "STATUS", color: "#10B981" },
    tool_call: { label: "TOOL▶", color: "#A78BFA" },
    tool_result: { label: "TOOL◀", color: "#8B5CF6" },
    pipeline_event: { label: "PIPE", color: "#EC4899" },
    notification: { label: "NOTIF", color: "#F97316" },
    error: { label: "ERROR", color: "#EF4444" },
};

export default function AgentMonitorPage() {
    const [messages, setMessages] = useState<BusMessage[]>([]);
    const [connected, setConnected] = useState(false);
    const [paused, setPaused] = useState(false);
    const [filter, setFilter] = useState("");
    const [expanded, setExpanded] = useState(false);
    const [autoScroll, setAutoScroll] = useState(true);

    const wsRef = useRef<WebSocket | null>(null);
    const terminalRef = useRef<HTMLDivElement>(null);
    const pausedRef = useRef(false);
    const queueRef = useRef<BusMessage[]>([]);

    useEffect(() => { pausedRef.current = paused; }, [paused]);

    /* ── Auto-scroll when new messages arrive ─────────────────── */
    useEffect(() => {
        if (autoScroll && terminalRef.current) {
            terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
        }
    }, [messages, autoScroll]);

    /* ── WebSocket connection ─────────────────────────────────── */
    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        try {
            const ws = new WebSocket(NEX_WS);

            ws.onopen = () => {
                setConnected(true);
                setMessages(prev => [...prev, {
                    id: "sys_" + Date.now(),
                    from_agent: "system", from_name: "System",
                    from_color: "#F59E0B", from_icon: "⚙️",
                    to_agent: "monitor", to_name: "Monitor", to_color: "#9CA3AF",
                    message_type: "status_update",
                    content: "Connected to Agent Bus — monitoring all inter-agent communication",
                    metadata: {}, timestamp: new Date().toISOString(),
                }]);
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    if (data.type === "bus_history") {
                        // Initial history load
                        setMessages(prev => [...prev, ...(data.messages || [])]);
                        return;
                    }

                    if (data.type === "bus_message") {
                        const msg: BusMessage = data;
                        if (pausedRef.current) {
                            queueRef.current.push(msg);
                        } else {
                            setMessages(prev => [...prev, msg]);
                        }
                    }
                } catch { }
            };

            ws.onclose = () => {
                setConnected(false);
                setTimeout(connect, 3000);
            };

            ws.onerror = () => {
                setConnected(false);
            };

            wsRef.current = ws;
        } catch { }
    }, []);

    useEffect(() => {
        connect();
        return () => { wsRef.current?.close(); };
    }, [connect]);

    /* ── Pause / Resume ───────────────────────────────────────── */
    const togglePause = () => {
        if (paused) {
            // Resume — flush queued messages
            setMessages(prev => [...prev, ...queueRef.current]);
            queueRef.current = [];
        }
        setPaused(!paused);
    };

    /* ── Filter messages ──────────────────────────────────────── */
    const filtered = filter
        ? messages.filter(m =>
            m.from_name.toLowerCase().includes(filter.toLowerCase()) ||
            m.to_name.toLowerCase().includes(filter.toLowerCase()) ||
            m.content.toLowerCase().includes(filter.toLowerCase()) ||
            m.message_type.includes(filter.toLowerCase())
        )
        : messages;

    /* ── Format timestamp ─────────────────────────────────────── */
    const fmtTime = (ts: string) => {
        try {
            const d = new Date(ts);
            return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        } catch { return "??:??:??"; }
    };

    return (
        <div
            style={{
                height: expanded ? "100vh" : "calc(100vh - 0px)",
                display: "flex",
                flexDirection: "column",
                background: "#0D1117",
                position: expanded ? "fixed" : "relative",
                inset: expanded ? 0 : undefined,
                zIndex: expanded ? 9999 : undefined,
            }}
        >
            {/* ── Header Bar ──────────────────────────────────────── */}
            <div style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "12px 20px",
                background: "linear-gradient(135deg, #1a1b2e 0%, #16171f 100%)",
                borderBottom: "1px solid rgba(99, 102, 241, 0.2)",
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <Terminal style={{ width: 20, height: 20, color: "#6366F1" }} />
                    <span style={{ fontSize: 16, fontWeight: 700, color: "#E5E7EB", letterSpacing: 0.5 }}>
                        Agent Monitor
                    </span>
                    <span style={{
                        fontSize: 11, padding: "2px 8px", borderRadius: 12,
                        background: connected ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
                        color: connected ? "#10B981" : "#EF4444",
                        display: "flex", alignItems: "center", gap: 4,
                    }}>
                        {connected ? <Wifi style={{ width: 12, height: 12 }} /> : <WifiOff style={{ width: 12, height: 12 }} />}
                        {connected ? "LIVE" : "DISCONNECTED"}
                    </span>
                    <span style={{ fontSize: 11, color: "#6B7280" }}>
                        {messages.length} messages
                        {paused && queueRef.current.length > 0 && ` (+${queueRef.current.length} queued)`}
                    </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    {/* Filter */}
                    <input
                        type="text"
                        placeholder="Filter..."
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                        style={{
                            background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
                            borderRadius: 6, padding: "4px 10px", fontSize: 12, color: "#E5E7EB",
                            width: 140, outline: "none",
                        }}
                    />
                    {/* Pause */}
                    <button
                        onClick={togglePause}
                        style={{
                            display: "flex", alignItems: "center", gap: 4,
                            padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600,
                            background: paused ? "rgba(245, 158, 11, 0.15)" : "rgba(99, 102, 241, 0.15)",
                            color: paused ? "#F59E0B" : "#818CF8",
                            border: "none", cursor: "pointer",
                        }}
                    >
                        {paused ? <Play style={{ width: 12, height: 12 }} /> : <Pause style={{ width: 12, height: 12 }} />}
                        {paused ? "Resume" : "Pause"}
                    </button>
                    {/* Clear */}
                    <button
                        onClick={() => setMessages([])}
                        style={{
                            display: "flex", alignItems: "center", gap: 4,
                            padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600,
                            background: "rgba(239, 68, 68, 0.1)", color: "#EF4444",
                            border: "none", cursor: "pointer",
                        }}
                    >
                        <Trash2 style={{ width: 12, height: 12 }} />
                        Clear
                    </button>
                    {/* Expand/Collapse */}
                    <button
                        onClick={() => setExpanded(!expanded)}
                        style={{
                            display: "flex", alignItems: "center",
                            padding: "4px 8px", borderRadius: 6,
                            background: "rgba(255,255,255,0.05)",
                            color: "#9CA3AF", border: "none", cursor: "pointer",
                        }}
                    >
                        {expanded ? <Minimize2 style={{ width: 14, height: 14 }} /> : <Maximize2 style={{ width: 14, height: 14 }} />}
                    </button>
                </div>
            </div>

            {/* ── Terminal Body ────────────────────────────────────── */}
            <div
                ref={terminalRef}
                onScroll={() => {
                    if (!terminalRef.current) return;
                    const { scrollTop, scrollHeight, clientHeight } = terminalRef.current;
                    setAutoScroll(scrollHeight - scrollTop - clientHeight < 60);
                }}
                style={{
                    flex: 1, overflow: "auto", padding: "12px 16px",
                    fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
                    fontSize: 12.5, lineHeight: 1.7,
                }}
            >
                {filtered.length === 0 && (
                    <div style={{ color: "#4B5563", textAlign: "center", padding: 40 }}>
                        {connected
                            ? "Waiting for inter-agent communication..."
                            : "Connecting to Agent Bus..."}
                    </div>
                )}

                {filtered.map((msg) => {
                    const typeInfo = MSG_TYPE_LABELS[msg.message_type] || { label: msg.message_type.toUpperCase(), color: "#9CA3AF" };
                    const isError = msg.message_type === "error";
                    const isPipeline = msg.message_type === "pipeline_event";

                    return (
                        <div
                            key={msg.id}
                            style={{
                                marginBottom: 2,
                                padding: "3px 0",
                                borderLeft: isPipeline ? `3px solid ${typeInfo.color}` : isError ? "3px solid #EF4444" : "none",
                                paddingLeft: isPipeline || isError ? 10 : 0,
                                opacity: isError ? 1 : 0.92,
                            }}
                        >
                            {/* Timestamp */}
                            <span style={{ color: "#4B5563", marginRight: 8 }}>
                                [{fmtTime(msg.timestamp)}]
                            </span>

                            {/* Message type badge */}
                            <span style={{
                                color: typeInfo.color, fontWeight: 700, fontSize: 10,
                                padding: "1px 5px", borderRadius: 3,
                                background: `${typeInfo.color}15`,
                                marginRight: 8,
                            }}>
                                {typeInfo.label}
                            </span>

                            {/* Agent names */}
                            <span style={{ color: msg.from_color, fontWeight: 600 }}>
                                {msg.from_icon} {msg.from_name}
                            </span>
                            <span style={{ color: "#4B5563", margin: "0 6px" }}>→</span>
                            <span style={{ color: msg.to_color, fontWeight: 600 }}>
                                {msg.to_name}
                            </span>

                            {/* Separator */}
                            <span style={{ color: "#374151", margin: "0 8px" }}>│</span>

                            {/* Content */}
                            <span style={{ color: isError ? "#FCA5A5" : "#D1D5DB" }}>
                                {msg.content}
                            </span>
                        </div>
                    );
                })}

                {/* Auto-scroll anchor */}
                <div style={{ height: 1 }} />
            </div>

            {/* ── Status Bar ──────────────────────────────────────── */}
            <div style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "6px 16px",
                background: "#161B22",
                borderTop: "1px solid rgba(255,255,255,0.06)",
                fontSize: 11, color: "#6B7280",
            }}>
                <span>
                    {connected ? "🟢 Connected to ws://localhost:8001/ws/agent-bus" : "🔴 Disconnected"}
                </span>
                <span>
                    {filtered.length} / {messages.length} messages
                    {filter && ` (filtered by "${filter}")`}
                </span>
            </div>
        </div>
    );
}
