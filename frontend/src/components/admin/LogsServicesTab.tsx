import { Server, Cpu, RefreshCw, FileText, Trash2, Zap } from "lucide-react";
import { motion } from "framer-motion";

interface LogsServicesTabProps {
  logs: string;
  fetchLogs: () => void;
  clearLogs: () => void;
  restartService: (service: string) => void;
  loading: Record<string, boolean>;
  servicesStatus: { backend: string; celery: string; redis: string } | undefined;
}

export default function LogsServicesTab({ logs, fetchLogs, clearLogs, restartService, loading, servicesStatus }: LogsServicesTabProps) {
  
  const services = [
    { key: "celery", label: "Celery Worker", desc: "Background task & video processing engine", icon: Cpu, status: servicesStatus?.celery },
    { key: "backend", label: "FastAPI Backend", desc: "Core API and request routing", icon: Server, status: servicesStatus?.backend },
    { key: "all", label: "Complete System", desc: "Restart both backend and background workers", icon: Zap, status: "online" },
  ];

  return (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        className="space-y-6"
    >
        {/* Service Controls Horizontal Layout */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {services.map((svc, idx) => (
                <motion.div 
                    key={svc.key} 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.1 }}
                    className="p-5 rounded-xl bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)] shadow-sm flex flex-col"
                >
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 flex items-center justify-center rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                                <svc.icon className="w-5 h-5" />
                            </div>
                            <div>
                                <h4 className="text-sm font-semibold text-white">{svc.label}</h4>
                                <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--nc-text-muted)] mt-0.5">
                                    <span className={`w-1.5 h-1.5 rounded-full ${svc.status === 'online' ? 'bg-emerald-400' : 'bg-red-400'}`}></span>
                                    {svc.status === 'online' ? 'Online' : 'Offline'}
                                </span>
                            </div>
                        </div>
                    </div>
                    <p className="text-xs text-[var(--nc-text-dim)] mb-5 flex-1">{svc.desc}</p>
                    <button
                        onClick={() => restartService(svc.key)}
                        disabled={loading[`restart_${svc.key}`]}
                        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-[var(--nc-bg)] border border-[var(--nc-border)] text-sm font-medium text-white hover:border-indigo-500/50 hover:bg-indigo-500/5 transition-all disabled:opacity-50"
                    >
                        <RefreshCw className={`w-4 h-4 text-indigo-400 ${loading[`restart_${svc.key}`] ? "animate-spin" : ""}`} />
                        {loading[`restart_${svc.key}`] ? "Restarting..." : `Restart ${svc.label.split(' ')[0]}`}
                    </button>
                </motion.div>
            ))}
        </div>

        {/* Console / Error Logs */}
        <div className="rounded-xl border border-[var(--nc-border)] bg-[#0d1117] overflow-hidden shadow-sm flex flex-col h-[500px]">
             <div className="flex items-center justify-between px-5 py-3 border-b border-white/10 bg-white/[0.02]">
                <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-[var(--nc-text-dim)]" />
                    <span className="text-xs font-mono font-medium text-white tracking-wide">celery_error.log</span>
                </div>
                <div className="flex items-center gap-2">
                    <button onClick={fetchLogs} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-medium text-[var(--nc-text-muted)] hover:text-white hover:bg-white/5 transition-colors">
                        <RefreshCw className="w-3 h-3" /> Refresh
                    </button>
                    <button onClick={clearLogs} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors">
                        <Trash2 className="w-3 h-3" /> Clear
                    </button>
                </div>
            </div>
            
            <div className="flex-1 p-4 overflow-auto custom-scrollbar relative">
                {logs ? (
                    <pre className="text-[12px] text-[#8b949e] font-mono leading-relaxed whitespace-pre-wrap">
                        {/* Simple syntax highlighting concept for logs */}
                        {logs.split('\n').map((line, i) => {
                            let color = "text-[#8b949e]";
                            if (line.includes("ERROR") || line.includes("Exception") || line.includes("Traceback")) {
                                color = "text-red-400";
                            } else if (line.includes("WARNING")) {
                                color = "text-amber-400";
                            } else if (line.includes("INFO")) {
                                color = "text-sky-400";
                            }
                            return <div key={i} className={`${color} break-words`}>{line}</div>
                        })}
                    </pre>
                ) : (
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-[var(--nc-text-dim)]">
                        <CheckCircleIcon className="w-8 h-8 mb-2 opacity-50 text-emerald-500" />
                        <span className="text-sm font-medium">No errors recorded</span>
                        <span className="text-xs">All systems are operational</span>
                    </div>
                )}
            </div>
        </div>
    </motion.div>
  );
}

function CheckCircleIcon(props: any) {
  return (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}
