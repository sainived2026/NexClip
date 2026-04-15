"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useParams } from "next/navigation";
import { projectsAPI } from "@/lib/api";
import {
    Loader2, CheckCircle2, AlertCircle, Download, Play, Pause,
    Sparkles, Film, Clock, Upload, X, BarChart3, ExternalLink, Volume2, VolumeX, Type
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

import { captionsAPI } from "@/lib/api";
import { isTerminalProjectStatus, mergeProjectStatus } from "@/lib/project-live";

const stages = [
    { key: "UPLOADED", label: "Uploaded", icon: Upload },
    { key: "TRANSCRIBING", label: "Transcribing", icon: Clock },
    { key: "ANALYZING", label: "AI Analysis", icon: Sparkles },
    { key: "GENERATING_CLIPS", label: "Generating Clips", icon: Film },
    { key: "COMPLETED", label: "Complete", icon: CheckCircle2 },
];

const stageOrder = ["UPLOADED", "TRANSCRIBING", "ANALYZING", "GENERATING_CLIPS", "COMPLETED"];

function dedupeClips(clips: any[] = []) {
    const seen = new Map<string, any>();

    for (const clip of clips) {
        const key = clip.rank ? `rank:${clip.rank}` : `path:${clip.file_path || clip.file_path_landscape || clip.id}`;
        const existing = seen.get(key);
        if (!existing) {
            seen.set(key, clip);
            continue;
        }

        const existingScore = Number(Boolean(existing.file_path)) + Number(Boolean(existing.file_path_landscape)) + Number(Boolean(existing.captioned_video_url));
        const nextScore = Number(Boolean(clip.file_path)) + Number(Boolean(clip.file_path_landscape)) + Number(Boolean(clip.captioned_video_url));
        if (nextScore >= existingScore) {
            seen.set(key, clip);
        }
    }

    return Array.from(seen.values()).sort((a, b) => (a.rank || 0) - (b.rank || 0));
}

/* ── Inline Video Card Component ─────────────────────────────── */
function ClipCard({ clip, index, onExpand, styles, onOpenGallery, globalAspect, onApplyStyle }: { clip: any; index: number; onExpand: () => void; styles: any[]; onOpenGallery: (clipId: string) => void; globalAspect?: string; onApplyStyle?: (clipId: string, styleId: string, aspect: string) => void }) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [isMuted, setIsMuted] = useState(true);
    const [hasError, setHasError] = useState(false);
    const [isLandscape, setIsLandscape] = useState(false);
    const [localCaptionStatus, setLocalCaptionStatus] = useState(clip.caption_status);
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);

    let activePath = clip.file_path;
    if (isLandscape) {
        activePath = clip.captioned_video_url_landscape || clip.file_path_landscape || clip.file_path;
    } else {
        activePath = clip.captioned_video_url || clip.file_path;
    }
    const videoUrl = activePath ? `${API_BASE}/static/storage/${activePath}` : "";

    useEffect(() => {
        setHasError(false);
    }, [isLandscape]);

    useEffect(() => {
        if (globalAspect === "16:9") setIsLandscape(true);
        else if (globalAspect === "9:16") setIsLandscape(false);
    }, [globalAspect]);

    const togglePlay = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (!videoRef.current) return;
        if (isPlaying) {
            videoRef.current.pause();
            setIsPlaying(false);
        } else {
            videoRef.current.play().catch(() => setHasError(true));
            setIsPlaying(true);
        }
    };

    const toggleMute = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (!videoRef.current) return;
        videoRef.current.muted = !videoRef.current.muted;
        setIsMuted(videoRef.current.muted);
    };

    // Keep local sync'd with polling
    useEffect(() => {
        if (clip.caption_status && clip.caption_status !== localCaptionStatus) {
            setLocalCaptionStatus(clip.caption_status);
        }
    }, [clip.caption_status]);

    return (
        <motion.div
            key={clip.id}
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ delay: index * 0.05, duration: 0.4, ease: "easeOut" }}
            className={`group relative rounded-2xl border border-[var(--nc-border)] hover:border-indigo-500/30 hover:shadow-[0_0_30px_rgba(99,102,241,0.15)] transition-all duration-500 cursor-pointer ${isLandscape ? "aspect-video" : "aspect-[9/16]"}`}
            onClick={onExpand}
        >
            {/* Background Video Layer */}
            <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none">
                {videoUrl && !hasError ? (
                    <video
                        ref={videoRef}
                        src={videoUrl}
                        muted={isMuted}
                        loop
                        playsInline
                        preload="metadata"
                        className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                        onEnded={() => setIsPlaying(false)}
                        onError={() => setHasError(true)}
                    />
                ) : (
                    <div className="absolute inset-0 w-full h-full bg-gradient-to-br from-gray-900 to-black flex items-center justify-center">
                        <Loader2 className="w-8 h-8 text-indigo-500 animate-spin opacity-50" />
                    </div>
                )}

                {/* Cinematic Gradient Overlays */}
                <div className="absolute inset-x-0 top-0 h-1/4 bg-gradient-to-b from-black/60 to-transparent z-10" />
                <div className="absolute inset-x-0 bottom-0 h-3/5 bg-gradient-to-t from-black via-black/60 to-transparent z-10" />
            </div>

            {/* Top Badges */}
            <div className="absolute top-4 left-4 flex items-center gap-2 z-20">
                <div className="px-2.5 py-1 rounded-lg bg-black/40 backdrop-blur-md border border-white/10 text-xs font-bold text-white shadow-lg">
                    #{clip.rank}
                </div>
            </div>
            <div className="absolute top-4 right-4 z-20">
                <div className="px-3 py-1 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 border border-white/20 text-xs font-bold text-white shadow-[0_0_15px_rgba(99,102,241,0.5)]">
                    ⭐ {clip.viral_score.toFixed(0)}
                </div>
            </div>

            {/* Center Play Button Overlay */}
            <div
                className="absolute inset-0 flex items-center justify-center z-20 transition-opacity"
                onClick={togglePlay}
            >
                {!isPlaying && (
                    <div className="w-16 h-16 rounded-full bg-white/10 backdrop-blur-xl border border-white/20 flex items-center justify-center shadow-2xl scale-90 group-hover:scale-100 transition-transform duration-500">
                        <Play className="w-6 h-6 text-white fill-white ml-1" />
                    </div>
                )}
            </div>

            {/* Bottom Content Layer */}
            <div className="absolute bottom-0 left-0 right-0 p-5 z-20 pointer-events-none">
                <h3 className="text-base font-bold text-white line-clamp-2 leading-snug mb-1 drop-shadow-md">
                    {clip.title_suggestion || `Clip ${clip.rank}`}
                </h3>
                <p className="text-sm font-medium text-white/80 line-clamp-2 leading-relaxed mb-4 drop-shadow">
                    {clip.hook_text}
                </p>

                {/* Interaction Row */}
                <div className="flex items-center justify-between gap-3 pointer-events-auto">
                    <div className="flex items-center gap-3 text-xs font-semibold text-white/70 bg-black/40 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10">
                        <span className="flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5 text-indigo-400" />
                            {clip.duration.toFixed(0)}s
                        </span>
                    </div>

                    <div className="flex items-center gap-2">
                        {/* Play/Pause Button */}
                        <button
                            onClick={togglePlay}
                            className={`p-2.5 rounded-xl backdrop-blur-md border transition-all ${isPlaying
                                ? "bg-white/20 border-white/30 text-white hover:bg-white/30"
                                : "bg-indigo-500/80 border-indigo-400/50 text-white hover:bg-indigo-500 hover:shadow-[0_0_15px_rgba(99,102,241,0.4)]"
                                }`}
                        >
                            {isPlaying ? <Pause className="w-4 h-4 fill-white" /> : <Play className="w-4 h-4 fill-white ml-0.5" />}
                        </button>

                        {/* Mute Button */}
                        <button
                            onClick={toggleMute}
                            className="p-2.5 rounded-xl bg-black/40 backdrop-blur-md border border-white/10 text-white hover:bg-black/60 transition-colors"
                        >
                            {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                        </button>

                        {/* Format Toggle Button */}
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setIsLandscape(prev => !prev);
                            }}
                            className="px-2.5 py-1.5 rounded-xl bg-black/40 backdrop-blur-md border border-white/10 text-white hover:bg-white/10 transition-colors text-xs font-bold font-mono tracking-tighter w-12 flex items-center justify-center shrink-0"
                            title={isLandscape ? "Switch to 9:16" : "Switch to 16:9"}
                        >
                            {isLandscape ? "16:9" : "9:16"}
                        </button>

                        {/* Captions Button (Opens Dropdown) */}
                        <div className="relative">
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setIsDropdownOpen(!isDropdownOpen);
                                }}
                                className={`p-2.5 rounded-xl backdrop-blur-md border transition-all ${
                                    localCaptionStatus === "processing" 
                                        ? "bg-indigo-500/80 border-indigo-400/50 text-white" 
                                        : (isLandscape ? clip.captioned_video_url_landscape : clip.captioned_video_url)
                                        ? "bg-green-500/80 border-green-400/50 text-white"
                                        : "bg-black/40 border-white/10 text-white hover:bg-white/10"
                                }`}
                                title="Add Captions"
                                disabled={localCaptionStatus === "processing"}
                            >
                                {localCaptionStatus === "processing" ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <Type className="w-4 h-4" />
                                )}
                            </button>
                            
                            {/* Tiny Dropdown Menu */}
                            <AnimatePresence>
                                {isDropdownOpen && (
                                    <motion.div
                                        initial={{ opacity: 0, y: 10, scale: 0.95 }}
                                        animate={{ opacity: 1, y: 0, scale: 1 }}
                                        exit={{ opacity: 0, y: 10, scale: 0.95 }}
                                        className="absolute bottom-full right-0 mb-3 w-48 max-h-[250px] overflow-y-auto custom-scrollbar bg-black/95 backdrop-blur-xl border border-white/20 rounded-xl shadow-2xl z-[100] flex flex-col p-1.5"
                                    >
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onApplyStyle?.(clip.id, "NONE", isLandscape ? "16:9" : "9:16");
                                                setIsDropdownOpen(false);
                                            }}
                                            className="px-3 py-2 text-sm text-left text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-lg font-medium transition-colors border-b border-white/10 mb-1"
                                        >
                                            Remove Caption
                                        </button>
                                        {styles.map(s => (
                                            <button
                                                key={s.style_id}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    onApplyStyle?.(clip.id, s.style_id, isLandscape ? "16:9" : "9:16");
                                                    setIsDropdownOpen(false);
                                                }}
                                                className="px-3 py-2 text-sm text-left text-white/90 hover:text-white hover:bg-white/10 rounded-lg transition-colors flex items-center justify-between group"
                                            >
                                                <span>{s.display_name}</span>
                                                {localCaptionStatus === 'done' && clip.caption_style_id === s.style_id && (
                                                    <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 opacity-100" />
                                                )}
                                            </button>
                                        ))}
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                        
                        {/* Download Button */}
                        {clip.file_path && (
                            <a
                                href={videoUrl}
                                download
                                onClick={(e) => e.stopPropagation()}
                                className="p-2.5 rounded-xl bg-black/40 backdrop-blur-md border border-white/10 text-white hover:bg-white/10 hover:border-white/30 transition-all"
                                title="Download"
                            >
                                <Download className="w-4 h-4" />
                            </a>
                        )}
                    </div>
                </div>
            </div>
        </motion.div>
    );
}

/* ── Main Page ───────────────────────────────────────────────── */
export default function ProjectDetailPage() {
    const params = useParams();
    const projectId = params.id as string;
    const [project, setProject] = useState<any>(null);
    const [clips, setClips] = useState<any[]>([]);
    const [captionStyles, setCaptionStyles] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [previewClip, setPreviewClip] = useState<any>(null);
    const [isGalleryOpen, setIsGalleryOpen] = useState(false);
    const [targetClipId, setTargetClipId] = useState<string | null>(null);
    const [globalAspect, setGlobalAspect] = useState("9:16");
    const projectRef = useRef<any>(null);
    const statusPollTickRef = useRef(0);

    const loadProject = useCallback(async () => {
        try {
            const [res, stylesRes] = await Promise.all([
                projectsAPI.get(projectId),
                captionsAPI.getStyles()
            ]);
            setProject(res.data);
            if (res.data.clips) setClips(dedupeClips(res.data.clips));
            setCaptionStyles(stylesRes.data);
        } catch (err) {
            console.error("Failed to load project:", err);
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        loadProject();
    }, [loadProject]);

    useEffect(() => {
        projectRef.current = project;
    }, [project]);

    // Listen for caption completion refresh
    useEffect(() => {
        const handler = () => loadProject();
        window.addEventListener("nexclip:refresh-clips", handler);
        return () => window.removeEventListener("nexclip:refresh-clips", handler);
    }, [loadProject]);

    // Poll status while processing
    useEffect(() => {
        let cancelled = false;
        let terminalRefreshTick = 0;

        const refreshLiveProject = async (forceFull = false) => {
            try {
                if (forceFull || !projectRef.current) {
                    statusPollTickRef.current = 0;
                    await loadProject();
                    return;
                }

                const statusRes = await projectsAPI.getStatus(projectId);
                if (cancelled) return;

                const nextProject = mergeProjectStatus(projectRef.current, statusRes.data);
                setProject(nextProject);
                projectRef.current = nextProject;
                statusPollTickRef.current += 1;

                const shouldRefreshFull =
                    isTerminalProjectStatus(statusRes.data?.status) ||
                    statusPollTickRef.current % 3 === 0;

                if (shouldRefreshFull) {
                    const fullRes = await projectsAPI.get(projectId);
                    if (cancelled) return;
                    setProject(fullRes.data);
                    projectRef.current = fullRes.data;
                    if (fullRes.data.clips) {
                        setClips(dedupeClips(fullRes.data.clips));
                    }
                }
            } catch (err) {
                if (!cancelled) {
                    console.error("Failed to refresh project status:", err);
                }
            }
        };

        refreshLiveProject(true);

        const interval = window.setInterval(() => {
            if (isTerminalProjectStatus(projectRef.current?.status)) {
                terminalRefreshTick += 1;
                if (terminalRefreshTick % 4 === 0) {
                    refreshLiveProject(true);
                }
                return;
            }

            terminalRefreshTick = 0;
            refreshLiveProject(false);
        }, 2000);

        const handleVisibility = () => {
            if (document.visibilityState === "visible") {
                refreshLiveProject(isTerminalProjectStatus(projectRef.current?.status));
            }
        };

        window.addEventListener("focus", handleVisibility);
        document.addEventListener("visibilitychange", handleVisibility);

        return () => {
            cancelled = true;
            window.clearInterval(interval);
            window.removeEventListener("focus", handleVisibility);
            document.removeEventListener("visibilitychange", handleVisibility);
        };
    }, [loadProject, projectId]);

    const handleApplyStyle = async (styleId: string, overrideClipId?: string, overrideAspect?: string) => {
        setIsGalleryOpen(false);
        
        try {
            const activeClipId = overrideClipId || targetClipId;
            const activeAspect = overrideAspect || globalAspect;
            if (activeClipId) {
                if (styleId === "NONE") {
                    // NONE removal is synchronous on the backend — update UI instantly
                    await captionsAPI.applyStyle(activeClipId, styleId, activeAspect);
                    setClips(prev => prev.map(c => c.id === activeClipId 
                        ? { ...c, caption_status: "none", caption_style_id: "", captioned_video_url: "", captioned_video_url_landscape: "" } 
                        : c
                    ));
                    return;
                }
                
                // Apply to single clip — set processing, then poll
                await captionsAPI.applyStyle(activeClipId, styleId, activeAspect);
                setClips(prev => prev.map(c => c.id === activeClipId ? { ...c, caption_status: "processing" } : c));
                
                let tries = 0;
                const poll = setInterval(async () => {
                    tries++;
                    if (tries > 60) { clearInterval(poll); return; }
                    try {
                        const res = await captionsAPI.getStatus(activeClipId);
                        if (res.data?.caption_status === "done" || res.data?.caption_status === "failed") {
                            clearInterval(poll);
                            // Refresh full project to get updated clip URLs
                            window.dispatchEvent(new CustomEvent("nexclip:refresh-clips"));
                        }
                    } catch {}
                }, 3000);
            } else {
                // Bulk apply to all clips using direct fetch
                const token = localStorage.getItem("nexclip_token");
                await fetch(`${API_BASE}/api/projects/${projectId}/apply-caption-all`, {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
                    },
                    body: JSON.stringify({ style_id: styleId, active_aspect: globalAspect })
                });
                
                if (styleId === "NONE") {
                    // NONE is synchronous — update UI instantly
                    setClips(prev => prev.map(c => ({ ...c, caption_status: "none", caption_style_id: "", captioned_video_url: "", captioned_video_url_landscape: "" })));
                    return;
                }
                
                // Set local status for all
                setClips(prev => prev.map(c => ({ ...c, caption_status: "processing" })));
                
                // Poll check all clips — update each clip as it finishes
                let tries = 0;
                const poll = setInterval(async () => {
                    tries++;
                    if (tries > 120) { clearInterval(poll); return; }
                    try {
                        const res = await projectsAPI.get(projectId);
                        const c = dedupeClips(res.data.clips || []);
                        setClips(c);
                        setProject(res.data);
                        const pendingCount = c.filter((x: any) => x.caption_status === "processing").length;
                        if (pendingCount === 0) {
                            clearInterval(poll);
                        }
                    } catch {}
                }, 3000);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const currentStageIndex = project ? stageOrder.indexOf(project.status) : 0;

    if (loading) return (
        <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
        </div>
    );

    if (!project) return (
        <div className="text-center py-20">
            <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-white">Project not found</h3>
        </div>
    );

    return (
        <div>
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-2xl font-bold text-white">{project.title}</h1>
                <p className="text-sm text-[var(--nc-text-muted)] mt-1">{project.status_message}</p>
            </div>

            {/* Processing stages */}
            {project.status !== "COMPLETED" && project.status !== "FAILED" && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                    className="p-6 rounded-2xl glass mb-8">
                    <h2 className="text-sm font-medium text-[var(--nc-text-muted)] uppercase tracking-wider mb-6">Processing Pipeline</h2>

                    <div className="flex items-center gap-4 overflow-x-auto pb-2">
                        {stages.map((stage, i) => {
                            const isActive = stage.key === project.status;
                            const isDone = i < currentStageIndex;
                            const StageIcon = stage.icon;
                            return (
                                <div key={stage.key} className="flex items-center gap-3 shrink-0">
                                    <div className={`
                    flex items-center gap-2 px-4 py-2 rounded-lg border transition-all
                    ${isActive
                                            ? "border-indigo-500/50 bg-indigo-500/10 text-indigo-400"
                                            : isDone
                                                ? "border-green-500/30 bg-green-500/5 text-green-400"
                                                : "border-[var(--nc-border)] text-[var(--nc-text-dim)]"
                                        }
                  `}>
                                        {isActive ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : isDone ? (
                                            <CheckCircle2 className="w-4 h-4" />
                                        ) : (
                                            <StageIcon className="w-4 h-4" />
                                        )}
                                        <span className="text-sm font-medium">{stage.label}</span>
                                    </div>
                                    {i < stages.length - 1 && (
                                        <div className={`w-8 h-0.5 ${isDone ? "bg-green-500/30" : "bg-[var(--nc-border)]"}`} />
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {/* Progress bar */}
                    <div className="mt-6">
                        <div className="flex items-center justify-between text-xs text-[var(--nc-text-dim)] mb-2">
                            <span>Progress</span>
                            <span>{project.progress}%</span>
                        </div>
                        <div className="w-full h-2 bg-[var(--nc-bg)] rounded-full overflow-hidden">
                            <motion.div
                                className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full"
                                initial={{ width: 0 }}
                                animate={{ width: `${project.progress}%` }}
                                transition={{ duration: 0.5, ease: "easeOut" }}
                            />
                        </div>
                    </div>
                </motion.div>
            )}

            {/* Error state */}
            {project.status === "FAILED" && (
                <div className="p-6 rounded-2xl bg-red-500/5 border border-red-500/20 mb-8">
                    <div className="flex items-center gap-3">
                        <AlertCircle className="w-5 h-5 text-red-400" />
                        <div>
                            <h3 className="text-sm font-medium text-red-400">Processing Failed</h3>
                            <p className="text-xs text-red-400/70 mt-1">{project.error_message || "An error occurred during processing."}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Clips grid */}
            {project.status === "COMPLETED" && clips.length > 0 && (
                <div>
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-xl font-bold text-white flex items-center gap-2">
                            <Sparkles className="w-5 h-5 text-indigo-400" />
                            Generated Clips ({clips.length})
                        </h2>

                        <div className="flex items-center gap-3">
                            <button
                                onClick={() => { setTargetClipId(null); setIsGalleryOpen(true); }}
                                className="px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-sm font-bold shadow-[0_0_20px_rgba(99,102,241,0.3)] transition-all flex items-center gap-2"
                            >
                                <Type className="w-4 h-4" />
                                Add Captions
                            </button>

                            {/* Global Aspect Ratio Toggle */}
                            <div className="flex items-center gap-1 bg-black/40 backdrop-blur-md border border-white/10 p-1 rounded-xl overflow-hidden">
                                <button
                                    onClick={() => setGlobalAspect("9:16")}
                                    className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-all ${globalAspect === "9:16" ? "bg-white/20 text-white" : "text-white/70 hover:text-white hover:bg-white/10"}`}
                                >
                                    9:16
                                </button>
                                <button
                                    onClick={() => setGlobalAspect("16:9")}
                                    className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-all ${globalAspect === "16:9" ? "bg-white/20 text-white" : "text-white/70 hover:text-white hover:bg-white/10"}`}
                                >
                                    16:9
                                </button>
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {clips.map((clip, i) => (
                            <ClipCard
                                key={clip.id}
                                clip={clip}
                                index={i}
                                styles={captionStyles}
                                onExpand={() => setPreviewClip(clip)}
                                onOpenGallery={(clipId: string) => {
                                    setTargetClipId(clipId);
                                    setIsGalleryOpen(true);
                                }}
                                onApplyStyle={(clipId: string, styleId: string, aspect: string) => {
                                    setTargetClipId(clipId);
                                    handleApplyStyle(styleId, clipId, aspect);
                                }}
                                globalAspect={globalAspect}
                            />
                        ))}
                    </div>
                </div>
            )}

            {/* Caption Gallery Modal */}
            <AnimatePresence>
                {isGalleryOpen && (
                    <motion.div
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[100] bg-black/90 backdrop-blur-md flex flex-col pt-10 px-8 pb-8 overflow-hidden"
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between mb-8 shrink-0">
                            <div>
                                <h1 className="text-3xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
                                    Caption Styles Gallery
                                </h1>
                                <p className="text-[var(--nc-text-muted)] mt-2">
                                    {targetClipId ? "Select a style for this clip" : "Select a style to apply to all clips"}
                                </p>
                            </div>
                            <button 
                                onClick={() => setIsGalleryOpen(false)}
                                className="p-3 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
                            >
                                <X className="w-6 h-6 text-white" />
                            </button>
                        </div>

                        {/* Grid */}
                        <div className="flex-1 overflow-y-auto custom-scrollbar pr-4">
                            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-6 pb-20">
                                {/* None Option */}
                                <div 
                                    className="group relative rounded-2xl border border-white/10 bg-white/5 hover:border-red-500/50 hover:bg-red-500/10 overflow-hidden cursor-pointer transition-all aspect-[4/3] flex flex-col items-center justify-center"
                                    onClick={() => handleApplyStyle("NONE")}
                                >
                                    <Type className="w-12 h-12 text-white/30 mb-4 group-hover:text-red-400/80 transition-colors" />
                                    <h3 className="text-xl font-bold text-white group-hover:text-red-400 mb-2">Original (No Captions)</h3>
                                    <p className="text-sm text-white/50 text-center px-4">Remove dynamically generated captions from the video</p>
                                </div>

                                {/* Dynamic Styles */}
                                {captionStyles.map(style => (
                                    <div 
                                        key={style.style_id}
                                        className="group relative rounded-2xl border border-white/10 bg-black overflow-hidden cursor-pointer transition-all hover:border-indigo-500/50 hover:shadow-[0_0_30px_rgba(99,102,241,0.2)] aspect-[4/3]"
                                        onClick={() => handleApplyStyle(style.style_id)}
                                    >
                                        {/* Video Preview loaded from API */}
                                        <div className="absolute inset-0 bg-gray-900 flex items-center justify-center overflow-hidden">
                                            <video 
                                                src={`${API_BASE}/api/captions/preview/${style.style_id}`}
                                                className="w-full h-full object-cover opacity-80 group-hover:opacity-100 group-hover:scale-105 transition-all duration-700"
                                                autoPlay
                                                muted
                                                loop
                                                playsInline
                                            />
                                        </div>
                                        
                                        {/* Overlay - subtle bottom gradient for text readability only */}
                                        <div className="absolute bottom-0 left-0 right-0 h-1/3 bg-gradient-to-t from-black/90 to-transparent pointer-events-none" />
                                        
                                        {/* Text Info */}
                                        <div className="absolute bottom-0 left-0 right-0 p-5 z-20">
                                            <h3 className="text-xl font-bold text-white mb-1 group-hover:text-indigo-400 transition-colors">{style.display_name}</h3>
                                            <div className="flex items-center gap-2">
                                                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-1 rounded bg-white/10 text-white/70">
                                                    Word-by-word
                                                </span>
                                                {style.glow && (
                                                    <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-1 rounded bg-indigo-500/20 text-indigo-300">
                                                        Glow Effect
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        
                                        {/* Hover Apply Button */}
                                        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center z-30">
                                            <div className="px-6 py-3 rounded-full bg-indigo-500 text-white font-bold tracking-wide transform translate-y-4 group-hover:translate-y-0 transition-all duration-300 flex items-center gap-2">
                                                <Sparkles className="w-4 h-4" />
                                                {targetClipId ? "Apply to this Clip" : "Apply to All Clips"}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Fullscreen Video Preview Modal */}
            <AnimatePresence>
                {previewClip && (
                    <motion.div
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-6"
                        onClick={() => setPreviewClip(null)}
                    >
                        <motion.div
                            initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
                            className="w-full max-w-5xl h-[85vh] relative flex items-center justify-center bg-black/50 rounded-2xl border border-white/10 overflow-hidden"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <button 
                                onClick={() => setPreviewClip(null)}
                                className="absolute top-4 right-4 z-50 p-2 rounded-xl bg-black/40 backdrop-blur-md border border-white/10 text-white hover:bg-white/10 transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                            <video 
                                src={previewClip.file_path_landscape ? `${API_BASE}/static/storage/${previewClip.file_path_landscape}` : `${API_BASE}/static/storage/${previewClip.file_path}`}
                                className="w-full h-full object-contain"
                                controls
                                autoPlay
                                playsInline
                            />
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
