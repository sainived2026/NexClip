/**
 * Nexearch & Arc Agent API client
 * Communicates with:
 *   - Nexearch Engine (port 8002) for data, pipelines, clients
 *   - Arc Agent (port 8003) for chat, tools, sub-agents
 */

const NEXEARCH_API = "http://localhost:8002";
const ARC_API = "http://localhost:8003";
const ARC_WS = "ws://localhost:8003/ws/chat";

// ── Nexearch API ──────────────────────────────────────────

export const nexearchAPI = {
  // Health
  health: async () => {
    const res = await fetch(`${NEXEARCH_API}/health`);
    return res.json();
  },
  status: async () => {
    const res = await fetch(`${NEXEARCH_API}/status`);
    return res.json();
  },

  // Clients
  listClients: async () => {
    const res = await fetch(`${NEXEARCH_API}/api/v1/clients`);
    return res.json();
  },
  getClient: async (clientId: string) => {
    const res = await fetch(`${NEXEARCH_API}/api/v1/clients/${clientId}`);
    return res.json();
  },

  // Pipeline
  triggerPipeline: async (
    clientId: string,
    platform: string,
    accountHandle: string,
    accountUrl: string,
  ) => {
    const res = await fetch(`${NEXEARCH_API}/api/v1/pipeline/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_id: clientId,
        platform,
        account_handle: accountHandle,
        account_url: accountUrl,
      }),
    });
    return res.json();
  },

  // Data
  clientData: async (clientId: string, platform: string) => {
    const res = await fetch(`${NEXEARCH_API}/api/v1/data/${clientId}/scrapes/${platform}`);
    return res.json();
  },
  universalPatterns: async () => {
    const res = await fetch(`${NEXEARCH_API}/api/v1/intelligence/universal`);
    return res.json();
  },
};

// ── Arc Agent API ─────────────────────────────────────────

export const arcAgentAPI = {
  health: async () => {
    const res = await fetch(`${ARC_API}/health`);
    return res.json();
  },
  status: async () => {
    const res = await fetch(`${ARC_API}/api/status`);
    return res.json();
  },
  chat: async (message: string, clientId: string = "") => {
    const res = await fetch(`${ARC_API}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, client_id: clientId }),
    });
    return res.json();
  },
  history: async (limit: number = 50) => {
    const res = await fetch(`${ARC_API}/api/history?limit=${limit}`);
    return res.json();
  },
  tools: async () => {
    const res = await fetch(`${ARC_API}/api/tools`);
    return res.json();
  },
  subAgents: async () => {
    const res = await fetch(`${ARC_API}/api/sub-agents`);
    return res.json();
  },
  subAgentTasks: async () => {
    const res = await fetch(`${ARC_API}/api/sub-agents/tasks`);
    return res.json();
  },
  sessions: async () => {
    const res = await fetch(`${ARC_API}/api/memory/sessions`);
    return res.json();
  },
  decisions: async () => {
    const res = await fetch(`${ARC_API}/api/memory/decisions`);
    return res.json();
  },
  pipelineRuns: async () => {
    const res = await fetch(`${ARC_API}/api/memory/pipeline-runs`);
    return res.json();
  },
  alerts: async () => {
    const res = await fetch(`${ARC_API}/api/memory/alerts`);
    return res.json();
  },
};

// ── WebSocket URL ─────────────────────────────────────────
export { ARC_WS };
