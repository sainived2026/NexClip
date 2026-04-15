"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { projectsAPI, nexearchAPI } from "@/lib/api";
import {
    Upload, Link2, Film, Loader2, CheckCircle2,
    AlertCircle, X, CloudUpload, Sparkles
} from "lucide-react";

export default function UploadPage() {
    const router = useRouter();
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [mode, setMode] = useState<"upload" | "url">("upload");
    const [dragOver, setDragOver] = useState(false);
    const [file, setFile] = useState<File | null>(null);
    const [url, setUrl] = useState("");
    const [title, setTitle] = useState("");
    const [clipCount, setClipCount] = useState(10);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [clients, setClients] = useState<any[]>([]);
    const [clientId, setClientId] = useState<string>("");

    useEffect(() => {
        const fetchClients = async () => {
            try {
                const res = await nexearchAPI.getClients();
                const list = res.data?.clients || res.data || [];
                const normalized = (Array.isArray(list) ? list : []).map((client: any, index: number) => ({
                    ...client,
                    id: String(client.client_id || client.id || client.name || `client-${index}`),
                    name: client.name || client.label || client.account_handle || client.client_id || `Client ${index + 1}`,
                }));
                setClients(normalized);
            } catch (err) {
                console.warn("Could not fetch clients for setup linking");
            }
        };
        fetchClients();
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
        const dropped = e.dataTransfer.files[0];
        if (dropped && dropped.type.startsWith("video/")) {
            setFile(dropped);
            if (!title) setTitle(dropped.name.replace(/\.[^/.]+$/, ""));
        }
    }, [title]);

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selected = e.target.files?.[0];
        if (selected) {
            setFile(selected);
            if (!title) setTitle(selected.name.replace(/\.[^/.]+$/, ""));
        }
    };

    const handleSubmit = async () => {
        setError("");
        setLoading(true);
        try {
            if (mode === "upload") {
                if (!file) { setError("Please select a video file"); setLoading(false); return; }
                const formData = new FormData();
                formData.append("file", file);
                formData.append("title", title || file.name);
                formData.append("clip_count", String(clipCount));
                if (clientId) formData.append("client_id", clientId);
                
                const res = await projectsAPI.uploadVideo(formData);
                router.push(`/dashboard/projects/${res.data.id}`);
            } else {
                if (!url) { setError("Please enter a video URL"); setLoading(false); return; }
                const payload: any = { url, title: title || "Untitled", clip_count: clipCount };
                if (clientId) payload.client_id = clientId;
                
                const res = await projectsAPI.submitURL(payload);
                router.push(`/dashboard/projects/${res.data.id}`);
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || "Upload failed. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    const formatSize = (bytes: number) => {
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
    };

    return (
        <div className="max-w-2xl mx-auto">
            <div className="mb-8">
                <h1 className="text-2xl font-bold text-white">Create New Project</h1>
                <p className="text-sm text-[var(--nc-text-muted)] mt-1">Upload a video or paste a URL to start clipping</p>
            </div>

            {/* Mode toggle */}
            <div className="flex gap-2 p-1 rounded-xl glass mb-6 w-fit">
                <button
                    onClick={() => setMode("upload")}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${mode === "upload" ? "bg-[var(--nc-bg-elevated)] text-white" : "text-[var(--nc-text-muted)] hover:text-white"
                        }`}
                >
                    <Upload className="w-4 h-4" /> Upload File
                </button>
                <button
                    onClick={() => setMode("url")}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${mode === "url" ? "bg-[var(--nc-bg-elevated)] text-white" : "text-[var(--nc-text-muted)] hover:text-white"
                        }`}
                >
                    <Link2 className="w-4 h-4" /> Paste URL
                </button>
            </div>

            {error && (
                <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
                    className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    {error}
                </motion.div>
            )}

            <AnimatePresence mode="wait">
                {mode === "upload" ? (
                    <motion.div key="upload" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
                        {/* Drop zone */}
                        <div
                            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                            onDragLeave={() => setDragOver(false)}
                            onDrop={handleDrop}
                            onClick={() => fileInputRef.current?.click()}
                            className={`
                relative rounded-2xl border-2 border-dashed p-12 text-center cursor-pointer transition-all
                ${dragOver
                                    ? "border-indigo-500 bg-indigo-500/5"
                                    : file
                                        ? "border-green-500/30 bg-green-500/5"
                                        : "border-[var(--nc-border)] hover:border-[var(--nc-border-hover)] hover:bg-[var(--nc-bg-card)]"
                                }
              `}
                        >
                            <input ref={fileInputRef} type="file" accept="video/*" onChange={handleFileSelect} className="hidden" />

                            {file ? (
                                <div>
                                    <CheckCircle2 className="w-12 h-12 text-green-400 mx-auto mb-4" />
                                    <p className="text-sm font-medium text-white mb-1">{file.name}</p>
                                    <p className="text-xs text-[var(--nc-text-dim)]">{formatSize(file.size)}</p>
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setFile(null); }}
                                        className="mt-3 text-xs text-red-400 hover:text-red-300 flex items-center gap-1 mx-auto"
                                    >
                                        <X className="w-3 h-3" /> Remove
                                    </button>
                                </div>
                            ) : (
                                <div>
                                    <CloudUpload className={`w-12 h-12 mx-auto mb-4 ${dragOver ? "text-indigo-400" : "text-[var(--nc-text-dim)]"}`} />
                                    <p className="text-sm font-medium text-white mb-1">
                                        {dragOver ? "Drop your video here" : "Drag & drop your video here"}
                                    </p>
                                    <p className="text-xs text-[var(--nc-text-dim)]">
                                        MP4, MOV, WebM, AVI • Max 4GB
                                    </p>
                                </div>
                            )}
                        </div>
                    </motion.div>
                ) : (
                    <motion.div key="url" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                        <div className="p-6 rounded-2xl glass">
                            <div className="flex items-center gap-3 mb-4">
                                <Link2 className="w-5 h-5 text-indigo-400" />
                                <span className="text-sm font-medium text-white">Video URL</span>
                            </div>
                            <input
                                type="url"
                                value={url}
                                onChange={(e) => setUrl(e.target.value)}
                                placeholder="https://youtube.com/watch?v=... or any public video URL"
                                className="w-full px-4 py-3 rounded-lg bg-[var(--nc-bg)] border border-[var(--nc-border)] text-white text-sm focus:outline-none focus:border-indigo-500 transition-colors"
                            />
                            <p className="text-xs text-[var(--nc-text-dim)] mt-2">Supports YouTube, Vimeo, and most public video URLs</p>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Settings */}
            <div className="mt-6 p-6 rounded-2xl glass space-y-4">
                <div>
                    <label className="block text-sm text-[var(--nc-text-muted)] mb-1.5">Project Title</label>
                    <input
                        type="text"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="My awesome podcast episode"
                        className="w-full px-4 py-2.5 rounded-lg bg-[var(--nc-bg)] border border-[var(--nc-border)] text-white text-sm focus:outline-none focus:border-indigo-500 transition-colors"
                    />
                </div>
                <div>
                    <label className="block text-sm text-[var(--nc-text-muted)] mb-1.5 flex justify-between items-center">
                        <span>Client Setup (Optional)</span>
                    </label>
                    <select
                        value={clientId}
                        onChange={(e) => setClientId(e.target.value)}
                        className="w-full px-4 py-2.5 rounded-lg bg-[var(--nc-bg)] border border-[var(--nc-border)] text-white text-sm focus:outline-none focus:border-indigo-500 transition-colors"
                    >
                        <option value="">Universal AI Setup (Default)</option>
                        {clients.map(c => (
                            <option key={c.id} value={c.id}>
                                {c.name}
                            </option>
                        ))}
                    </select>
                    <p className="text-xs text-[var(--nc-text-dim)] mt-1.5">
                        Select a client to use their custom AI rules (DNA) generated by Nexearch.
                    </p>
                </div>
                <div>
                    <label className="block text-sm text-[var(--nc-text-muted)] mb-1.5">Number of Clips: <span className="text-white font-medium">{clipCount}</span></label>
                    <input
                        type="range"
                        min={1} max={20} value={clipCount}
                        onChange={(e) => setClipCount(Number(e.target.value))}
                        className="w-full accent-indigo-500"
                    />
                    <div className="flex justify-between text-xs text-[var(--nc-text-dim)] mt-1">
                        <span>1</span>
                        <span>20</span>
                    </div>
                </div>
            </div>

            {/* Submit */}
            <button
                onClick={handleSubmit}
                disabled={loading || (mode === "upload" ? !file : !url)}
                className="w-full mt-6 flex items-center justify-center gap-2 py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 text-white font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-xl hover:shadow-indigo-500/20"
            >
                {loading ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Processing...</>
                ) : (
                    <><Sparkles className="w-4 h-4" /> Start Clipping</>
                )}
            </button>
        </div>
    );
}
