import { useState } from "react";
import { Users, FolderOpen, Trash2, Search, Filter } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

// ── Types ────────────────────────────────────────────────────────
interface UserInfo {
  id: string; email: string; username: string; full_name: string;
  is_active: boolean; created_at: string; project_count: number;
  clip_count: number; is_admin: boolean;
}

interface ProjectInfo {
  id: string; title: string; status: string; progress: number;
  status_message: string; error_message: string; clip_count: number;
  owner_email: string; owner_username: string; video_filename: string;
  video_source_url: string; video_duration: number; video_size_mb: number;
  created_at: string;
}

interface UsersProjectsTabProps {
  users: UserInfo[];
  projects: ProjectInfo[];
  toggleUser: (userId: string) => Promise<void>;
  deleteProject: (projectId: string, title: string) => Promise<void>;
}

export default function UsersProjectsTab({ users, projects, toggleUser, deleteProject }: UsersProjectsTabProps) {
  const [activeSubTab, setActiveSubTab] = useState<"users" | "projects">("users");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredUsers = users.filter(u => 
      u.username.toLowerCase().includes(searchQuery.toLowerCase()) || 
      u.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredProjects = projects.filter(p => 
      p.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
      p.owner_username.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const statusColors: Record<string, string> = {
    COMPLETED: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    FAILED: "bg-red-500/10 text-red-400 border-red-500/20",
    GENERATING_CLIPS: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    ANALYZING: "bg-sky-500/10 text-sky-400 border-sky-500/20",
    TRANSCRIBING: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    UPLOADED: "bg-gray-500/10 text-gray-400 border-gray-500/20",
  };

  return (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        className="space-y-6"
    >
        {/* Top specific controls */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex p-1 rounded-xl bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)] shadow-sm">
                <button
                    onClick={() => setActiveSubTab("users")}
                    className={`flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-medium transition-all ${
                        activeSubTab === "users" ? "bg-[var(--nc-bg-card)] text-white shadow-sm border border-[var(--nc-border)]" : "text-[var(--nc-text-muted)] hover:text-white"
                    }`}
                >
                    <Users className="w-4 h-4" /> Users ({users.length})
                </button>
                <button
                    onClick={() => setActiveSubTab("projects")}
                    className={`flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-medium transition-all ${
                        activeSubTab === "projects" ? "bg-[var(--nc-bg-card)] text-white shadow-sm border border-[var(--nc-border)]" : "text-[var(--nc-text-muted)] hover:text-white"
                    }`}
                >
                    <FolderOpen className="w-4 h-4" /> Projects ({projects.length})
                </button>
            </div>

            <div className="relative w-full sm:w-72">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--nc-text-dim)]" />
                <input 
                    type="text" 
                    placeholder={`Search ${activeSubTab}...`}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-[var(--nc-bg)] border border-[var(--nc-border)] text-sm text-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 outline-none transition-all"
                />
            </div>
        </div>

        {/* Data Tables */}
        <div className="rounded-xl border border-[var(--nc-border)] bg-[var(--nc-bg-card)] overflow-hidden shadow-sm">
            <AnimatePresence mode="wait">
                {activeSubTab === "users" ? (
                    <motion.div
                        key="users-table"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-x-auto"
                    >
                        <table className="w-full text-sm text-left">
                            <thead>
                                <tr className="bg-[var(--nc-bg-elevated)] border-b border-[var(--nc-border)]">
                                    <th className="px-5 py-4 font-semibold text-[var(--nc-text-muted)] uppercase tracking-wider text-[11px]">User Details</th>
                                    <th className="px-5 py-4 font-semibold text-[var(--nc-text-muted)] uppercase tracking-wider text-[11px] text-center">Status</th>
                                    <th className="px-5 py-4 font-semibold text-[var(--nc-text-muted)] uppercase tracking-wider text-[11px] text-center">Assets</th>
                                    <th className="px-5 py-4 font-semibold text-[var(--nc-text-muted)] uppercase tracking-wider text-[11px] text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[var(--nc-border)]">
                                {filteredUsers.length > 0 ? filteredUsers.map(u => (
                                    <tr key={u.id} className="hover:bg-white/[0.01] transition-colors group">
                                        <td className="px-5 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/20 flex items-center justify-center text-indigo-300 font-bold shrink-0">
                                                    {u.username.charAt(0).toUpperCase()}
                                                </div>
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-white font-medium">{u.username}</span>
                                                        {u.is_admin && <span className="text-[10px] px-1.5 py-0.5 rounded-sm bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 uppercase tracking-wide">Admin</span>}
                                                    </div>
                                                    <span className="text-xs text-[var(--nc-text-dim)]">{u.email}</span>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-5 py-4 text-center">
                                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${u.is_active ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"}`}>
                                                <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? "bg-emerald-400" : "bg-red-400"}`}></span>
                                                {u.is_active ? "Active" : "Disabled"}
                                            </span>
                                        </td>
                                        <td className="px-5 py-4">
                                            <div className="flex flex-col items-center justify-center gap-1">
                                                <span className="text-white tabular-nums">{u.project_count} <span className="text-[10px] text-[var(--nc-text-dim)] uppercase">Proj</span></span>
                                                <span className="text-white tabular-nums">{u.clip_count} <span className="text-[10px] text-[var(--nc-text-dim)] uppercase">Clip</span></span>
                                            </div>
                                        </td>
                                        <td className="px-5 py-4 text-right">
                                            {!u.is_admin && (
                                                <button
                                                    onClick={() => toggleUser(u.id)}
                                                    className={`text-[11px] font-medium px-3 py-1.5 rounded-lg border transition-all ${
                                                        u.is_active 
                                                        ? "border-red-500/30 text-red-400 hover:bg-red-500/10 hover:border-red-500/50" 
                                                        : "border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 hover:border-emerald-500/50"
                                                    }`}
                                                >
                                                    {u.is_active ? "Disable Auth" : "Enable Auth"}
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                )) : (
                                    <tr><td colSpan={4} className="px-5 py-12 text-center text-[var(--nc-text-dim)]">No users found</td></tr>
                                )}
                            </tbody>
                        </table>
                    </motion.div>
                ) : (
                    <motion.div
                        key="projects-table"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-x-auto"
                    >
                        <table className="w-full text-sm text-left">
                            <thead>
                                <tr className="bg-[var(--nc-bg-elevated)] border-b border-[var(--nc-border)]">
                                    <th className="px-5 py-4 font-semibold text-[var(--nc-text-muted)] uppercase tracking-wider text-[11px]">Project Name</th>
                                    <th className="px-5 py-4 font-semibold text-[var(--nc-text-muted)] uppercase tracking-wider text-[11px]">Owner</th>
                                    <th className="px-5 py-4 font-semibold text-[var(--nc-text-muted)] uppercase tracking-wider text-[11px] text-center">Status</th>
                                    <th className="px-5 py-4 font-semibold text-[var(--nc-text-muted)] uppercase tracking-wider text-[11px] text-center">Details</th>
                                    <th className="px-5 py-4 font-semibold text-[var(--nc-text-muted)] uppercase tracking-wider text-[11px] text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[var(--nc-border)]">
                                {filteredProjects.length > 0 ? filteredProjects.map(p => (
                                    <tr key={p.id} className="hover:bg-white/[0.01] transition-colors group">
                                        <td className="px-5 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-9 h-9 rounded-lg bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)] flex items-center justify-center text-[var(--nc-text-muted)] shrink-0">
                                                    <FolderOpen className="w-4 h-4" />
                                                </div>
                                                <div>
                                                    <div className="text-white font-medium truncate max-w-[250px]">{p.title}</div>
                                                    <div className="text-[11px] text-[var(--nc-text-dim)] mt-0.5">{new Date(p.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-5 py-4">
                                            <div className="flex items-center gap-2">
                                                <div className="w-5 h-5 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-[10px] text-white">
                                                    {p.owner_username.charAt(0).toUpperCase()}
                                                </div>
                                                <span className="text-[var(--nc-text-muted)] group-hover:text-white transition-colors">{p.owner_username}</span>
                                            </div>
                                        </td>
                                        <td className="px-5 py-4 text-center">
                                            <span className={`inline-flex px-2.5 py-1 rounded-full text-[11px] font-medium border ${statusColors[p.status] || "bg-gray-500/10 text-gray-400 border-gray-500/20"}`}>
                                                {p.status.replace("_", " ")}
                                            </span>
                                        </td>
                                        <td className="px-5 py-4 text-center">
                                            <div className="flex flex-col items-center justify-center gap-1">
                                                <span className="text-white text-xs tabular-nums">{p.clip_count} <span className="text-[10px] text-[var(--nc-text-dim)] uppercase">Clips</span></span>
                                                <span className="text-[var(--nc-text-muted)] text-[11px] tabular-nums">
                                                    {p.video_duration ? `${Math.round(p.video_duration / 60)}m` : "—"}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="px-5 py-4 text-right">
                                            <button
                                                onClick={() => deleteProject(p.id, p.title)}
                                                className="p-2 rounded-lg text-red-400/70 hover:text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 transition-all opacity-0 group-hover:opacity-100"
                                                title="Delete Project (Irreversible)"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </td>
                                    </tr>
                                )) : (
                                    <tr><td colSpan={5} className="px-5 py-12 text-center text-[var(--nc-text-dim)]">No projects found</td></tr>
                                )}
                            </tbody>
                        </table>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    </motion.div>
  );
}
