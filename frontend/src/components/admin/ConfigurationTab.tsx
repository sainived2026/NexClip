import { useState } from "react";
import { Save, Eye, EyeOff } from "lucide-react";
import { motion } from "framer-motion";

// ── Types ────────────────────────────────────────────────────────
interface ConfigField {
  type: string; label: string; value: string; is_set: boolean;
  options?: string[]; step?: number;
}

interface ConfigCategory {
  label: string;
  fields: Record<string, ConfigField>;
}

interface ConfigurationTabProps {
  config: Record<string, ConfigCategory> | null;
  configEdits: Record<string, string>;
  setConfigEdits: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  saveConfig: () => void;
  loading: boolean;
}

export default function ConfigurationTab({ config, configEdits, setConfigEdits, saveConfig, loading }: ConfigurationTabProps) {
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});

  if (!config) {
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
        className="space-y-6"
    >
        {Object.entries(config).map(([catKey, category], idx) => (
            <motion.div 
                key={catKey}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="rounded-xl bg-[var(--nc-bg-elevated)] border border-[var(--nc-border)] overflow-hidden shadow-sm"
            >
                <div className="px-5 py-3.5 bg-gradient-to-r from-white/[0.03] to-transparent border-b border-[var(--nc-border)]">
                    <h4 className="text-sm font-semibold text-white uppercase tracking-wider">{category.label}</h4>
                </div>
                <div className="p-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-5">
                    {Object.entries(category.fields).map(([fieldKey, field]) => (
                        <div key={fieldKey} className="group flex flex-col justify-end">
                            <label className="block text-xs font-medium text-[var(--nc-text-dim)] mb-1.5 group-focus-within:text-indigo-400 transition-colors">
                                {field.label}
                            </label>
                            <div className="relative">
                                {field.type === "select" ? (
                                    <div className="relative">
                                        <select
                                            value={configEdits[fieldKey] ?? field.value}
                                            onChange={e => setConfigEdits(p => ({ ...p, [fieldKey]: e.target.value }))}
                                            className="w-full px-3 py-2.5 rounded-lg bg-[var(--nc-bg)] border border-[var(--nc-border)] text-white text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 outline-none transition-all appearance-none cursor-pointer"
                                        >
                                            {field.options?.map(opt => (
                                                <option key={opt} value={opt}>{opt}</option>
                                            ))}
                                        </select>
                                        <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-[var(--nc-text-muted)]">
                                            <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z"/></svg>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex items-center gap-2">
                                        <input
                                            type={field.type === "password" && !showPasswords[fieldKey] ? "password" : (field.type === "number" ? "number" : "text")}
                                            value={configEdits[fieldKey] ?? field.value}
                                            onChange={e => setConfigEdits(p => ({ ...p, [fieldKey]: e.target.value }))}
                                            step={field.step}
                                            className="w-full px-3 py-2.5 rounded-lg bg-[var(--nc-bg)] border border-[var(--nc-border)] text-white text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 outline-none transition-all"
                                        />
                                        {field.type === "password" && (
                                            <button
                                                onClick={() => setShowPasswords(p => ({ ...p, [fieldKey]: !p[fieldKey] }))}
                                                className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md hover:bg-[var(--nc-bg-elevated)] text-[var(--nc-text-dim)] hover:text-white transition-colors"
                                            >
                                                {showPasswords[fieldKey] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                            </button>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </motion.div>
        ))}

        {/* Sticky Save Bar */}
        {Object.keys(configEdits).length > 0 && (
            <motion.div 
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 30 }}
                className="sticky bottom-6 z-10 flex justify-end"
            >
                <div className="bg-[var(--nc-bg-card)] border border-[var(--nc-border)] p-3 rounded-2xl shadow-[0_-8px_30px_-5px_rgba(0,0,0,0.5)] flex items-center gap-4">
                   <span className="text-sm text-[var(--nc-text-muted)] font-medium px-2">
                       {Object.keys(configEdits).length} unsaved change{Object.keys(configEdits).length > 1 ? 's' : ''}
                   </span>
                   <button
                        onClick={() => setConfigEdits({})}
                        disabled={loading}
                        className="px-4 py-2 rounded-xl text-sm font-medium text-[var(--nc-text-muted)] hover:text-white hover:bg-[var(--nc-bg-elevated)] transition-colors disabled:opacity-50"
                    >
                        Discard
                    </button>
                    <button
                        onClick={saveConfig}
                        disabled={loading}
                        className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 text-white text-sm font-semibold shadow-lg shadow-indigo-500/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? (
                            <div className="animate-spin rounded-full h-4 w-4 border-2 border-white/20 border-t-white"></div>
                        ) : (
                            <Save className="w-4 h-4" />
                        )}
                        {loading ? "Saving..." : "Save Configuration"}
                    </button>
                </div>
            </motion.div>
        )}
    </motion.div>
  );
}
