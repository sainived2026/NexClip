"use client";

import { useState, useEffect } from "react";
import { Database, Globe, Search, RefreshCw, ChevronDown, Layers, BarChart3 } from "lucide-react";

/* ════════════════════════════════════════════════════════════
   DATA EXPLORER — Browse scraped data, analysis, DNA, evolution
   ════════════════════════════════════════════════════════════ */

const PLATFORMS = ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook", "threads"];
type ClientOption = {
  id: string;
  label: string;
};

export default function NexearchData() {
  const [platform, setPlatform] = useState("all");
  const [dataType, setDataType] = useState<"scrapes" | "dna" | "evolution" | "universal">("universal");
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [selectedClient, setSelectedClient] = useState("");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchClients = async () => {
      try {
        const res = await fetch("http://localhost:8002/api/v1/clients/");
        if (!res.ok) {
          return;
        }

        const json = await res.json();
        const options = (json.clients || []).map((client: any) => ({
          id: client.client_id,
          label: client.name || client.account_handle || client.client_id,
        }));
        setClients(options);
        if (options.length > 0) {
          setSelectedClient(options[0].id);
        }
      } catch {
        setClients([]);
      }
    };

    fetchClients();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      let url = "";
      if (dataType === "universal") {
        url = "http://localhost:8002/api/v1/intelligence/universal";
      } else {
        if (!selectedClient) {
          setData({ error: "Select a client before querying client-specific Nexearch data." });
          setLoading(false);
          return;
        }

        if (platform === "all") {
          setData({ error: "Select a specific platform for client-specific Nexearch data." });
          setLoading(false);
          return;
        }

        url = `http://localhost:8002/api/v1/data/${selectedClient}/${dataType}/${platform}`;
      }
      const res = await fetch(url);
      const json = await res.json();

      if (dataType === "universal" && platform !== "all" && json?.dna?.[platform]) {
        setData({
          platform,
          dna: json.dna[platform],
          stats: json.stats?.[platform] || {},
          evolution_logs: (json.evolution_logs || []).filter((entry: any) => entry.platform === platform),
        });
      } else {
        setData(json);
      }
    } catch {
      setData({ error: "Could not reach Nexearch Engine. Is it running on port 8002?" });
    }
    setLoading(false);
  };

  return (
    <div style={{ padding: "24px 32px", background: "#0A0A0F", minHeight: "calc(100vh - 64px)", color: "#E2E8F0" }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <Database size={24} style={{ color: "#10B981" }} />
            Data Explorer
          </h1>
          <p className="text-sm mt-1" style={{ color: "#94A3B8" }}>
            Browse scraped data, analysis results, DNA profiles, and universal patterns
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        {/* Data type picker */}
        <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.1)" }}>
          {(["universal", "scrapes", "dna", "evolution"] as const).map(dt => (
            <button key={dt} onClick={() => setDataType(dt)}
              className="px-4 py-2 text-xs font-semibold uppercase transition-all"
              style={{
                background: dataType === dt ? "rgba(16,185,129,0.15)" : "transparent",
                color: dataType === dt ? "#10B981" : "#64748B",
              }}>
              {dt}
            </button>
          ))}
        </div>

        {/* Platform picker */}
        <select value={platform} onChange={e => setPlatform(e.target.value)}
          className="rounded-lg px-3 py-2 text-sm outline-none"
          style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", color: "#E2E8F0" }}>
          <option value="all">All Platforms</option>
          {PLATFORMS.map(p => <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>)}
        </select>

        {dataType !== "universal" && (
          <select value={selectedClient} onChange={e => setSelectedClient(e.target.value)}
            className="rounded-lg px-3 py-2 text-sm outline-none"
            style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", color: "#E2E8F0" }}>
            <option value="">Select Client</option>
            {clients.map(client => <option key={client.id} value={client.id}>{client.label}</option>)}
          </select>
        )}

        <button onClick={fetchData}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all hover:bg-white/5"
          style={{ border: "1px solid rgba(16,185,129,0.3)", color: "#10B981" }}>
          <Search size={14} /> Query
        </button>
      </div>

      {/* Results */}
      <div className="rounded-xl p-6" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", minHeight: 300 }}>
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <RefreshCw size={24} className="animate-spin" style={{ color: "#64748B" }} />
          </div>
        ) : data ? (
          data.error ? (
            <div className="text-center py-16">
              <p className="text-sm" style={{ color: "#EF4444" }}>{data.error}</p>
            </div>
          ) : (
            <pre className="text-xs overflow-auto" style={{ color: "#94A3B8", maxHeight: 500, lineHeight: 1.6 }}>
              {JSON.stringify(data, null, 2)}
            </pre>
          )
        ) : (
          <div className="text-center py-16">
            <Layers size={48} style={{ color: "#1E293B", margin: "0 auto" }} />
            <h3 className="mt-4 text-lg font-semibold" style={{ color: "#94A3B8" }}>Select data type and click Query</h3>
            <p className="text-sm mt-2" style={{ color: "#64748B" }}>
              Browse universal patterns, scraped posts, DNA profiles, or evolution history.
            </p>
          </div>
        )}
      </div>

      {/* Data storage info */}
      <div className="mt-6 grid grid-cols-3 gap-4">
        {[
          { title: "Client Data", path: "nexearch_data/clients/", desc: "Per-client scraped data, DNA, evolution logs" },
          { title: "Universal Data", path: "nexearch_data/universal/", desc: "Cross-client winning patterns per platform" },
          { title: "NexClip Data", path: "nexearch_data/nexclip_clients/", desc: "Clip enhancements and directive tracking" },
        ].map(item => (
          <div key={item.title} className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
            <div className="text-sm font-semibold" style={{ color: "#E2E8F0" }}>{item.title}</div>
            <div className="text-[10px] font-mono mt-1" style={{ color: "#06B6D4" }}>{item.path}</div>
            <div className="text-xs mt-2" style={{ color: "#64748B" }}>{item.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
