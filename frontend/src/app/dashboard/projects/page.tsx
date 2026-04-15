"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { projectsAPI } from "@/lib/api";
import { useLiveProjects } from "@/hooks/use-live-projects";
import {
    Film, ArrowRight, Loader2, CheckCircle2,
    AlertCircle, Upload, Sparkles, Clock, Plus, Trash2
} from "lucide-react";

const statusConfig: Record<string, { color: string; bg: string; icon: any; label: string }> = {
    UPLOADED: { color: "text-blue-400", bg: "bg-blue-500/10", icon: Upload, label: "Uploaded" },
    TRANSCRIBING: { color: "text-yellow-400", bg: "bg-yellow-500/10", icon: Clock, label: "Transcribing" },
    ANALYZING: { color: "text-purple-400", bg: "bg-purple-500/10", icon: Sparkles, label: "Analyzing" },
    GENERATING_CLIPS: { color: "text-indigo-400", bg: "bg-indigo-500/10", icon: Film, label: "Generating" },
    COMPLETED: { color: "text-green-400", bg: "bg-green-500/10", icon: CheckCircle2, label: "Completed" },
    FAILED: { color: "text-red-400", bg: "bg-red-500/10", icon: AlertCircle, label: "Failed" },
};

export default function ProjectsPage() {
    const { projects, setProjects, loading } = useLiveProjects({ intervalMs: 2000 });

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

    if (loading) return (
        <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
        </div>
    );

    return (
        <div>
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-bold text-white">Projects</h1>
                    <p className="text-sm text-[var(--nc-text-muted)] mt-1">{projects.length} project{projects.length !== 1 ? "s" : ""}</p>
                </div>
                <Link
                    href="/dashboard/upload"
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-medium transition-all hover:shadow-lg hover:shadow-indigo-500/25"
                >
                    <Plus className="w-4 h-4" /> New Project
                </Link>
            </div>

            {projects.length === 0 ? (
                <div className="text-center py-20 rounded-2xl glass">
                    <Film className="w-12 h-12 text-[var(--nc-text-dim)] mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-white mb-2">No projects yet</h3>
                    <p className="text-sm text-[var(--nc-text-muted)] mb-6">Create your first project to get started</p>
                    <Link href="/dashboard/upload" className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-white font-medium text-sm">
                        <Plus className="w-4 h-4" /> Upload Video
                    </Link>
                </div>
            ) : (
                <div className="grid gap-4">
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
                                    className="flex-1 flex items-center justify-between p-5 rounded-xl glass hover:bg-[var(--nc-bg-elevated)] transition-all"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 rounded-xl bg-[var(--nc-bg)] flex items-center justify-center">
                                            <Film className="w-6 h-6 text-indigo-400" />
                                        </div>
                                        <div>
                                            <h3 className="font-medium text-white">{project.title}</h3>
                                            <div className="flex items-center gap-3 mt-1">
                                                <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.color} ${cfg.bg}`}>
                                                    <StatusIcon className="w-3 h-3" />
                                                    {cfg.label}
                                                </span>
                                                {project.progress > 0 && project.progress < 100 && (
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-24 h-1.5 bg-[var(--nc-bg)] rounded-full overflow-hidden">
                                                            <div className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all" style={{ width: `${project.progress}%` }} />
                                                        </div>
                                                        <span className="text-xs text-[var(--nc-text-dim)]">{project.progress}%</span>
                                                    </div>
                                                )}
                                                <span className="text-xs text-[var(--nc-text-dim)]">
                                                    {new Date(project.created_at).toLocaleDateString()}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                    <ArrowRight className="w-5 h-5 text-[var(--nc-text-dim)] group-hover:text-white transition-colors" />
                                </Link>
                                <button
                                    onClick={(e) => handleDelete(e, project.id)}
                                    className="flex items-center justify-center p-4 rounded-xl glass hover:bg-red-500/10 text-[var(--nc-text-dim)] hover:text-red-400 transition-all"
                                    title="Delete Project"
                                >
                                    <Trash2 className="w-5 h-5" />
                                </button>
                            </motion.div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
