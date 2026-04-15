"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { projectsAPI } from "@/lib/api";
import { useLiveProjects } from "@/hooks/use-live-projects";
import {
    FolderOpen, Upload, Clock, CheckCircle2, AlertCircle,
    Loader2, Film, Sparkles, ArrowRight, Plus, Trash2
} from "lucide-react";

const statusConfig: Record<string, { color: string; icon: any; label: string }> = {
    UPLOADED: { color: "text-blue-400", icon: Upload, label: "Uploaded" },
    TRANSCRIBING: { color: "text-yellow-400", icon: Loader2, label: "Transcribing" },
    ANALYZING: { color: "text-purple-400", icon: Sparkles, label: "Analyzing" },
    GENERATING_CLIPS: { color: "text-indigo-400", icon: Film, label: "Generating" },
    COMPLETED: { color: "text-green-400", icon: CheckCircle2, label: "Completed" },
    FAILED: { color: "text-red-400", icon: AlertCircle, label: "Failed" },
};

export default function DashboardPage() {
    const { projects, setProjects, loading } = useLiveProjects({ intervalMs: 2000 });

    const activeProjects = projects.filter(p => !["COMPLETED", "FAILED"].includes(p.status));
    const completedProjects = projects.filter(p => p.status === "COMPLETED");

    const handleDelete = async (e: React.MouseEvent, projectId: string) => {
        e.preventDefault();
        e.stopPropagation();
        if (!confirm("Are you sure you want to delete this project?")) return;
        try {
            await projectsAPI.delete(projectId);
            setProjects(prev => prev.filter(p => p.id !== projectId));
        } catch (err) {
            console.error("Failed to delete project:", err);
            alert("Failed to delete project");
        }
    };

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-2xl font-bold text-white">Dashboard</h1>
                <p className="text-sm text-[var(--nc-text-muted)] mt-1">Overview of your clipping projects</p>
            </div>

            {/* Quick stats */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                    className="p-5 rounded-xl glass">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm text-[var(--nc-text-muted)]">Total Projects</p>
                            <p className="text-2xl font-bold text-white mt-1">{projects.length}</p>
                        </div>
                        <FolderOpen className="w-8 h-8 text-indigo-400/50" />
                    </div>
                </motion.div>
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
                    className="p-5 rounded-xl glass">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm text-[var(--nc-text-muted)]">Processing</p>
                            <p className="text-2xl font-bold text-white mt-1">{activeProjects.length}</p>
                        </div>
                        <Clock className="w-8 h-8 text-yellow-400/50" />
                    </div>
                </motion.div>
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
                    className="p-5 rounded-xl glass">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm text-[var(--nc-text-muted)]">Completed</p>
                            <p className="text-2xl font-bold text-white mt-1">{completedProjects.length}</p>
                        </div>
                        <CheckCircle2 className="w-8 h-8 text-green-400/50" />
                    </div>
                </motion.div>
            </div>

            {/* Projects list */}
            {loading ? (
                <div className="flex items-center justify-center py-20">
                    <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
                </div>
            ) : projects.length === 0 ? (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                    className="text-center py-20 rounded-2xl glass">
                    <Film className="w-12 h-12 text-[var(--nc-text-dim)] mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-white mb-2">No projects yet</h3>
                    <p className="text-sm text-[var(--nc-text-muted)] mb-6">Upload a video to start generating viral clips</p>
                    <Link
                        href="/dashboard/upload"
                        className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-white font-medium text-sm transition-all hover:shadow-lg hover:shadow-indigo-500/25"
                    >
                        <Plus className="w-4 h-4" /> Upload Video
                    </Link>
                </motion.div>
            ) : (
                <div className="space-y-3">
                    <h2 className="text-sm font-medium text-[var(--nc-text-muted)] uppercase tracking-wider mb-3">Recent Projects</h2>
                    {projects.map((project, i) => {
                        const cfg = statusConfig[project.status] || statusConfig.UPLOADED;
                        const StatusIcon = cfg.icon;
                        return (
                            <motion.div
                                key={project.id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: i * 0.05 }}
                                className="flex items-center gap-2 group relative"
                            >
                                <Link
                                    href={`/dashboard/projects/${project.id}`}
                                    className="flex-1 flex items-center justify-between p-4 rounded-xl glass hover:bg-[var(--nc-bg-elevated)] transition-all"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="w-10 h-10 rounded-lg bg-[var(--nc-bg)] flex items-center justify-center">
                                            <Film className="w-5 h-5 text-indigo-400" />
                                        </div>
                                        <div>
                                            <h3 className="text-sm font-medium text-white">{project.title}</h3>
                                            <div className="flex items-center gap-2 mt-0.5">
                                                <StatusIcon className={`w-3.5 h-3.5 ${cfg.color} ${project.status === "TRANSCRIBING" || project.status === "ANALYZING" || project.status === "GENERATING_CLIPS" ? "animate-spin" : ""}`} />
                                                <span className={`text-xs ${cfg.color}`}>{cfg.label}</span>
                                                {project.progress > 0 && project.progress < 100 && (
                                                    <span className="text-xs text-[var(--nc-text-dim)]">• {project.progress}%</span>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                    <ArrowRight className="w-4 h-4 text-[var(--nc-text-dim)] group-hover:text-white transition-colors" />
                                </Link>
                                <button
                                    onClick={(e) => handleDelete(e, project.id)}
                                    className="flex items-center justify-center p-3 rounded-xl glass hover:bg-red-500/10 text-[var(--nc-text-dim)] hover:text-red-400 transition-all"
                                    title="Delete Project"
                                >
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            </motion.div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
