import { Brain, Save, RotateCcw, AlertTriangle } from "lucide-react";
import { motion } from "framer-motion";

interface AiControlsTabProps {
  prompt: string;
  promptOriginal: string;
  setPrompt: React.Dispatch<React.SetStateAction<string>>;
  savePrompt: () => void;
  loading: boolean;
}

export default function AiControlsTab({ prompt, promptOriginal, setPrompt, savePrompt, loading }: AiControlsTabProps) {
  const isChanged = prompt !== promptOriginal;

  return (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        className="space-y-6 max-w-5xl mx-auto"
    >
        <div className="flex items-start gap-4 p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/20">
            <div className="mt-0.5">
                <Brain className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
                <h4 className="text-sm font-semibold text-white">System Prompt Master Control</h4>
                <p className="text-xs text-[var(--nc-text-muted)] mt-1 max-w-3xl leading-relaxed">
                    This prompt dictates how the Nex Agent evaluates transcripts, identifies viral moments, and crops the video. 
                    Changes here directly impact the quality and styling of all generated clips. <strong className="text-amber-400/80 font-medium">Please edit with extreme caution.</strong>
                </p>
            </div>
        </div>

        <div className="rounded-xl border border-[var(--nc-border)] bg-[var(--nc-bg-card)] overflow-hidden shadow-sm flex flex-col h-[600px]">
            <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--nc-border)] bg-[var(--nc-bg-elevated)]">
                <div className="flex items-center gap-2">
                    <div className="flex gap-1.5 mr-2">
                        <div className="w-2.5 h-2.5 rounded-full bg-red-400/50"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-amber-400/50"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-emerald-400/50"></div>
                    </div>
                    <span className="text-xs font-mono text-[var(--nc-text-dim)]">ai_scoring_service.py</span>
                </div>
                {isChanged && (
                    <span className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-md border border-amber-500/20">
                        <AlertTriangle className="w-3 h-3" />
                        Unsaved Changes
                    </span>
                )}
            </div>

            <div className="flex-1 relative bg-[#0d1117] group">
                 {/* Line Numbers Fake column for aesthetics */}
                <div className="absolute left-0 top-0 bottom-0 w-12 bg-[#0d1117] border-r border-white/5 pointer-events-none flex flex-col items-end py-4 pr-3 text-[10px] text-white/20 font-mono select-none overflow-hidden">
                    {Array.from({ length: 50 }).map((_, i) => (
                        <div key={i} className="leading-[22px] min-h-[22px]">{i + 1}</div>
                    ))}
                </div>

                <textarea
                    value={prompt}
                    onChange={e => setPrompt(e.target.value)}
                    className="w-full h-full pl-16 pr-6 py-4 bg-transparent text-[#c9d1d9] text-[13px] font-mono leading-[22px] focus:outline-none resize-none custom-scrollbar"
                    spellCheck={false}
                    placeholder="Enter system prompt here..."
                />
            </div>

            <div className="flex items-center justify-between px-5 py-4 border-t border-[var(--nc-border)] bg-[var(--nc-bg-elevated)] shrink-0">
                <div className="text-[11px] font-mono text-[var(--nc-text-dim)] flex items-center gap-4">
                    <span>Len: <span className="text-white">{prompt.length}</span></span>
                    <span>Lines: <span className="text-white">{prompt.split("\n").length}</span></span>
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => setPrompt(promptOriginal)}
                        disabled={!isChanged || loading}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--nc-bg)] border border-[var(--nc-border)] text-sm font-medium text-[var(--nc-text-muted)] hover:text-white hover:border-[var(--nc-border)] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                        <RotateCcw className="w-4 h-4" />
                        Revert
                    </button>
                    <button
                        onClick={savePrompt}
                        disabled={!isChanged || loading}
                        className="flex items-center gap-2 px-6 py-2 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 text-white text-sm font-medium shadow-lg shadow-indigo-500/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? (
                            <div className="animate-spin rounded-full h-4 w-4 border-2 border-white/20 border-t-white"></div>
                        ) : (
                            <Save className="w-4 h-4" />
                        )}
                        {loading ? "Saving..." : "Save Prompt"}
                    </button>
                </div>
            </div>
        </div>
    </motion.div>
  );
}
