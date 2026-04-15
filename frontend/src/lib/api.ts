import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
    baseURL: API_BASE,
    headers: {
        "Content-Type": "application/json",
    },
});

const freshRequestConfig = () => ({
    headers: {
        "Cache-Control": "no-cache",
        Pragma: "no-cache",
    },
    params: {
        _ts: Date.now(),
    },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
    if (typeof window !== "undefined") {
        const token = localStorage.getItem("nexclip_token");
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
    }
    return config;
});

// Handle 401
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401 && typeof window !== "undefined") {
            localStorage.removeItem("nexclip_token");
            localStorage.removeItem("nexclip_user");
        }
        return Promise.reject(error);
    }
);

// ── Auth ─────────────────────────────────────────────────────────
export const authAPI = {
    register: (data: { email: string; username: string; password: string; full_name?: string }) =>
        api.post("/api/auth/register", data),

    login: (data: { email: string; password: string }) =>
        api.post("/api/auth/login", data),

    getProfile: () => api.get("/api/auth/me"),
};

// ── Projects ────────────────────────────────────────────────────
export const projectsAPI = {
    list: () => api.get("/api/projects/", freshRequestConfig()),

    get: (id: string) => api.get(`/api/projects/${id}`, freshRequestConfig()),

    getStatus: (id: string) => api.get(`/api/projects/${id}/status`, freshRequestConfig()),

    getClips: (id: string) => api.get(`/api/projects/${id}/clips`, freshRequestConfig()),

    uploadVideo: (formData: FormData) =>
        api.post("/api/projects/upload", formData, {
            headers: { "Content-Type": "multipart/form-data" },
            timeout: 0,
        }),

    submitURL: (data: { url: string; title?: string; clip_count?: number; client_id?: string }) =>
        api.post("/api/projects/url", data),

    delete: (id: string) => api.delete(`/api/projects/${id}`),
};

// ── Clips ───────────────────────────────────────────────────────
export const clipsAPI = {
    export: (clipId: string, presetId: string) =>
        api.post(`/api/clips/${clipId}/export`, { preset_id: presetId }),
};

// ── Captions ────────────────────────────────────────────────────
export const captionsAPI = {
    getStyles: () => api.get("/api/captions/styles"),
    applyStyle: (clipId: string, styleId: string, activeAspect: string = "9:16") =>
        api.post(`/api/clips/${clipId}/apply-caption-style`, { style_id: styleId, active_aspect: activeAspect }),
    getStatus: (clipId: string) => api.get(`/api/clips/${clipId}/caption-status`),
};

// ── Nexearch (Cross-Service) ────────────────────────────────────
// Connects to Nexearch backend (port 8002) for client DNA/data
const nexearchApi = axios.create({
    baseURL: process.env.NEXT_PUBLIC_NEXEARCH_API_URL || "http://localhost:8002",
});

export const nexearchAPI = {
    getClients: () => nexearchApi.get("/api/v1/clients"),
};

export default api;

// ── Nex Agent API (port 8001) ─────────────────────────────────
const NEX_API = "http://localhost:8001/api/nex";

function _getToken(): string {
    if (typeof window !== "undefined") {
        return localStorage.getItem("nexclip_token") || "";
    }
    return "";
}

function _nexHeaders(): Record<string, string> {
    const token = _getToken();
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (token) h["Authorization"] = `Bearer ${token}`;
    return h;
}

export const nexAgentAPI = {
    listConversations: () =>
        fetch(`${NEX_API}/conversations`, { headers: _nexHeaders() }).then(r => r.json()),

    createConversation: () =>
        fetch(`${NEX_API}/conversations`, { method: "POST", headers: _nexHeaders() }).then(r => r.json()),

    getMessages: (conversationId: string) =>
        fetch(`${NEX_API}/conversations/${conversationId}/messages`, { headers: _nexHeaders() }).then(r => r.json()),

    deleteConversation: (conversationId: string) =>
        fetch(`${NEX_API}/conversations/${conversationId}`, { method: "DELETE", headers: _nexHeaders() }).then(r => r.json()),

    getStatus: () =>
        fetch(`${NEX_API}/status`).then(r => r.json()).catch(() => null),

    getModel: () =>
        fetch(`${NEX_API}/model`).then(r => r.json()).catch(() => null),
};

// ── Arc Agent API (port 8003) ─────────────────────────────────
const ARC_API = "http://localhost:8003/api";

export const arcAgentAPI = {
    listConversations: () =>
        fetch(`${ARC_API}/conversations`).then(r => r.json()),

    createConversation: () =>
        fetch(`${ARC_API}/conversations`, { method: "POST", headers: { "Content-Type": "application/json" } }).then(r => r.json()),

    getMessages: (conversationId: string) =>
        fetch(`${ARC_API}/conversations/${conversationId}/messages`).then(r => r.json()),

    deleteConversation: (conversationId: string) =>
        fetch(`${ARC_API}/conversations/${conversationId}`, { method: "DELETE" }).then(r => r.json()),

    getStatus: () =>
        fetch(`${ARC_API}/status`).then(r => r.json()).catch(() => null),

    getModel: () =>
        fetch(`${ARC_API}/model`).then(r => r.json()).catch(() => null),

    listClients: () =>
        fetch(`${ARC_API}/clients`).then(r => r.json()).catch(() => ({ clients: [] })),

    createClient: (data: { name: string; platforms: Record<string, Record<string, string>> }) =>
        fetch(`${ARC_API}/clients`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        }).then(async r => {
            const body = await r.json();
            if (!r.ok) throw new Error(body?.detail || body?.error || `HTTP ${r.status}`);
            return body;
        }),

    /** Update an existing client's credentials or add a new platform */
    updateClient: (
        clientId: string,
        data: {
            platform?: string;
            credentials?: Record<string, string>;
            name?: string;
            add_platform?: string;
            add_credentials?: Record<string, string>;
        }
    ) =>
        fetch(`${ARC_API}/clients/${clientId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        }).then(async r => {
            const body = await r.json();
            if (!r.ok) throw new Error(body?.detail || body?.error || `HTTP ${r.status}`);
            return body;
        }),

    /** Verify credentials match their account URL(s) */
    verifyClient: (
        clientId: string,
        options?: { platform?: string; credentials?: Record<string, string> }
    ) =>
        fetch(`${ARC_API}/clients/${clientId}/verify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(options || {}),
        }).then(async r => {
            const body = await r.json();
            if (!r.ok) throw new Error(body?.detail || body?.error || `HTTP ${r.status}`);
            return body;
        }),

    deleteClient: (clientId: string) =>
        fetch(`${ARC_API}/clients/${clientId}`, { method: "DELETE" }).then(r => {
            if (!r.ok) throw new Error(`Delete failed: HTTP ${r.status}`);
            return r.json().catch(() => ({ success: true }));
        }),

    /** Fetch Account DNA for a client (all platforms or a specific one) */
    getClientDna: (clientId: string, platform?: string) => {
        const url = platform
            ? `${ARC_API}/clients/${clientId}/dna?platform=${platform}`
            : `${ARC_API}/clients/${clientId}/dna`;
        return fetch(url).then(async r => {
            const body = await r.json();
            if (!r.ok) throw new Error(body?.detail || `HTTP ${r.status}`);
            return body;
        });
    },

    updateClientDna: (clientId: string, platform: string, payload: any) =>
        fetch(`${ARC_API}/clients/${clientId}/dna/${platform}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        }).then(async r => {
            const body = await r.json();
            if (!r.ok) throw new Error(body?.detail || body?.error || `HTTP ${r.status}`);
            return body;
        }),
};
