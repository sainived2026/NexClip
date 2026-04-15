import React from 'react';
import { Cpu, AlertTriangle, ShieldCheck } from 'lucide-react';

interface ModelIndicatorProps {
    modelName: string;
}

export function ModelIndicator({ modelName }: ModelIndicatorProps) {
    const isPremium = modelName.toLowerCase().includes('gpt-4') || modelName.toLowerCase().includes('gemini-2.5-pro');
    const isStandard = modelName.toLowerCase().includes('gemini-3.1-flash-lite') || modelName.toLowerCase().includes('gemini-3.1-flash-lite-preview') || modelName.toLowerCase().includes('gpt-3.5') || modelName.toLowerCase().includes('claude-3-haiku');
    const isLocal = modelName.toLowerCase().includes('local') || (!isPremium && !isStandard && modelName !== 'Connecting...');

    if (modelName === 'Connecting...') {
        return (
            <span className="inline-flex items-center gap-1 text-[10px] text-gray-500 font-mono">
                {modelName}
            </span>
        );
    }

    if (isPremium) {
        return (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded border border-emerald-500/20 bg-emerald-500/10 text-[10px] text-emerald-400 font-mono tracking-wide" title="Premium Model: High reliability and advanced reasoning">
                <ShieldCheck size={12} />
                {modelName}
            </span>
        );
    }

    if (isStandard) {
        return (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded border border-blue-500/20 bg-blue-500/10 text-[10px] text-blue-400 font-mono tracking-wide" title="Standard Model: Good balance of speed and reasoning">
                <Cpu size={12} />
                {modelName}
            </span>
        );
    }

    // Local / Limited
    return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded border border-amber-500/20 bg-amber-500/10 text-[10px] text-amber-400 font-mono tracking-wide" title="Local Model: May not strictly follow instructions or provide accurate background facts without tool calls">
            <AlertTriangle size={12} />
            {modelName}
        </span>
    );
}

