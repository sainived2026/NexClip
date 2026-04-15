import { Activity, Server, Clock, Users, FolderOpen, Film, CheckCircle, XCircle, Cpu, HardDrive } from "lucide-react";
import { motion } from "framer-motion";

// ── Types ────────────────────────────────────────────────────────
interface SystemStatus {
  services: { backend: string; celery: string; redis: string };
  active_tasks: number;
  uptime: string;
  disk: { total_gb: number; used_gb: number; free_gb: number; usage_percent: number };
  storage_sizes_mb: Record<string, number>;
  stats: { total_users: number; total_projects: number; total_clips: number; active_projects: number; completed_projects: number; failed_projects: number };
  restart_required: boolean;
  platform: { os: string; python: string; cpu_count: number; memory_gb: number };
}

// ── Helpers ──────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const isOnline = status === "online";
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${isOnline
      ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
      : "bg-red-500/15 text-red-400 border border-red-500/30"
      }`}>
      <span className={`w-2 h-2 rounded-full ${isOnline ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`} />
      {isOnline ? "Online" : "Offline"}
    </span>
  );
}

function StatCard({ icon: Icon, label, value, sub, color = "indigo" }: { icon: any; label: string; value: string | number; sub?: string; color?: string }) {
  const colors: Record<string, string> = {
    indigo: "from-indigo-500/10 to-indigo-600/5 border-indigo-500/20 text-indigo-400",
    emerald: "from-emerald-500/10 to-emerald-600/5 border-emerald-500/20 text-emerald-400",
    amber: "from-amber-500/10 to-amber-600/5 border-amber-500/20 text-amber-400",
    red: "from-red-500/10 to-red-600/5 border-red-500/20 text-red-400",
    purple: "from-purple-500/10 to-purple-600/5 border-purple-500/20 text-purple-400",
    sky: "from-sky-500/10 to-sky-600/5 border-sky-500/20 text-sky-400",
  };

  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -2 }}
      className={`rounded-xl bg-gradient-to-br ${colors[color]} border p-5 shadow-lg backdrop-blur-sm relative overflow-hidden group`}
    >
      <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 translate-x-4 -translate-y-4 transition-all duration-500 rotate-12 group-hover:rotate-0">
        <Icon className="w-24 h-24" />
      </div>
      <div className="flex items-center gap-3 mb-3 relative z-10">
        <div className={`p-2 rounded-lg bg-white/5 border border-white/10`}>
            <Icon className="w-5 h-5 opacity-90" />
        </div>
        <span className="text-xs font-medium text-[var(--nc-text-muted)] uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-3xl font-bold text-white relative z-10 tracking-tight">{value}</div>
      {sub && <div className="text-xs text-[var(--nc-text-dim)] mt-2 relative z-10">{sub}</div>}
    </motion.div>
  );
}

export default function SystemStatusTab({ status }: { status: SystemStatus | null }) {
  if (!status) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  return (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        className="space-y-8"
    >
        {/* Service Status Badges */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(status.services).map(([name, s]) => (
                <div key={name} className="flex items-center justify-between p-4 rounded-xl bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)]">
                    <div className="flex items-center gap-3">
                        <Server className={`w-5 h-5 ${s === "online" ? "text-emerald-400" : "text-red-400"}`} />
                        <span className="text-sm font-medium text-white capitalize">{name}</span>
                    </div>
                    <StatusBadge status={s} />
                </div>
            ))}
            <div className="flex items-center justify-between p-4 rounded-xl bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)]">
                <div className="flex items-center gap-3">
                    <Clock className="w-5 h-5 text-sky-400" />
                    <span className="text-sm font-medium text-[var(--nc-text-muted)]">Uptime</span>
                </div>
                <span className="text-sm text-white font-mono bg-white/5 px-2 py-1 rounded-md">{status.uptime}</span>
            </div>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
            <StatCard icon={Users} label="Users" value={status.stats.total_users} color="indigo" />
            <StatCard icon={FolderOpen} label="Projects" value={status.stats.total_projects} color="purple" />
            <StatCard icon={Film} label="Clips" value={status.stats.total_clips} color="emerald" />
            <StatCard icon={Activity} label="Active" value={status.stats.active_projects} color="amber" />
            <StatCard icon={CheckCircle} label="Completed" value={status.stats.completed_projects} color="sky" />
            <StatCard icon={XCircle} label="Failed" value={status.stats.failed_projects} color="red" />
        </div>

        {/* Platform & Disk */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-xl bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)] p-6">
                <h4 className="text-base font-semibold text-white mb-6 flex items-center gap-2">
                    <Cpu className="w-5 h-5 text-indigo-400" /> Platform Info
                </h4>
                <div className="grid grid-cols-2 gap-y-6 gap-x-4">
                    <div>
                        <div className="text-xs text-[var(--nc-text-dim)] uppercase tracking-wider mb-1">OS</div>
                        <div className="text-white font-medium">{status.platform.os}</div>
                    </div>
                    <div>
                        <div className="text-xs text-[var(--nc-text-dim)] uppercase tracking-wider mb-1">Python</div>
                        <div className="text-white font-medium">{status.platform.python}</div>
                    </div>
                    <div>
                        <div className="text-xs text-[var(--nc-text-dim)] uppercase tracking-wider mb-1">CPU Cores</div>
                        <div className="text-white font-medium">{status.platform.cpu_count} Logical Core(s)</div>
                    </div>
                    <div>
                        <div className="text-xs text-[var(--nc-text-dim)] uppercase tracking-wider mb-1">Total RAM</div>
                        <div className="text-white font-medium">{status.platform.memory_gb} GB</div>
                    </div>
                </div>
            </div>

            <div className="rounded-xl bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)] p-6">
                <h4 className="text-base font-semibold text-white mb-6 flex items-center gap-2">
                    <HardDrive className="w-5 h-5 text-indigo-400" /> Storage Capacity
                </h4>
                
                <div className="mb-6">
                    <div className="flex justify-between items-end mb-2">
                        <span className="text-sm font-medium text-white">Local Disk</span>
                        <span className="text-xs font-mono text-[var(--nc-text-muted)]">{status.disk?.usage_percent || 0}% Used</span>
                    </div>
                    <div className="h-3 rounded-full bg-[var(--nc-bg)] overflow-hidden shadow-inner">
                        <motion.div 
                            initial={{ width: 0 }}
                            animate={{ width: `${status.disk?.usage_percent || 0}%` }}
                            transition={{ duration: 1, ease: "easeOut" }}
                            className={`h-full rounded-full transition-colors ${(status.disk?.usage_percent || 0) > 85 ? "bg-red-500" : "bg-gradient-to-r from-indigo-500 to-purple-500"}`} 
                        />
                    </div>
                    <div className="flex justify-between text-xs text-[var(--nc-text-dim)] mt-2">
                        <span>{status.disk?.used_gb} GB Used</span>
                        <span>{status.disk?.free_gb} GB Free</span>
                    </div>
                </div>

                <div className="grid grid-cols-3 gap-3">
                    {status.storage_sizes_mb && Object.entries(status.storage_sizes_mb).map(([k, v]) => (
                        <div key={k} className="p-3 rounded-xl bg-[var(--nc-bg)] border border-[var(--nc-border)]/50 text-center transition-colors hover:border-indigo-500/30">
                            <div className="text-white font-semibold flex items-baseline justify-center gap-1">
                                {v} <span className="text-[10px] text-[var(--nc-text-dim)] font-normal">MB</span>
                            </div>
                            <div className="text-xs text-[var(--nc-text-dim)] capitalize mt-1">{k}</div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    </motion.div>
  );
}
