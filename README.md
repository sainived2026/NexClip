# 🎬 NexClip + Nexearch — AI Content Engine

**NexClip** is a production-grade SaaS that transforms long-form video into viral short-form clips using AI.
**Nexearch** is the autonomous intelligence engine that makes it self-evolving — scraping, analyzing, learning, and publishing across 6 social platforms.

---

## Architecture

```
NexClip/
├── backend/              # FastAPI + Celery + SQLAlchemy
│   ├── app/
│   │   ├── api/              # REST endpoints (auth, projects)
│   │   ├── core/             # Config, security (JWT)
│   │   ├── db/               # Database engine, ORM models
│   │   ├── services/         # Video processing, AI scoring, transcription
│   │   └── workers/          # Celery task definitions
│   ├── requirements.txt
│   └── .env
├── frontend/             # Next.js + Tailwind + Framer Motion
│   └── src/app/
│       ├── dashboard/        # Upload, projects, settings
│       └── ...
├── nex_agent/            # 🤖 Nex Agent — Master Intelligence
│   ├── core.py               # Singleton orchestrator
│   ├── conversation_engine.py
│   ├── command_bus.py         # Inter-agent communication
│   ├── self_expander.py       # Runtime tool creation
│   └── tools/                 # 65+ tools across 11 categories
│       ├── writing_tools.py       # Enterprise writing (6 platforms)
│       └── nexearch_tools.py      # Nexearch integration (10 tools)
├── nexearch/             # 🧠 Nexearch — Self-Evolving Intelligence
│   ├── agents/               # 6-stage pipeline + Arc Agent
│   │   ├── agent_scrape.py       # 3-method scraping
│   │   ├── agent_analyze.py      # LLM content analysis
│   │   ├── agent_score.py        # 5-dimension scoring + DNA
│   │   ├── agent_evolve.py       # Dual-mode evolution
│   │   ├── agent_bridge.py       # NexClip integration
│   │   ├── agent_publish.py      # Publishing agent
│   │   ├── arc_agent.py          # Arc Agent controller
│   │   └── pipeline.py           # Orchestrator
│   ├── data/                 # Per-client + universal data stores
│   │   ├── client_store.py       # Per-client per-platform data
│   │   ├── nexclip_client_store.py  # NexClip enhancement tracking
│   │   ├── universal_store.py    # Cross-client intelligence
│   │   ├── change_tracker.py     # Audit trail + revert system
│   │   └── system_meta.py        # System health
│   ├── tools/                # Scrapers, publishers, LLM, embeddings
│   ├── models/               # 10+ SQLAlchemy models
│   ├── schemas/              # 9 Pydantic schema modules
│   ├── api/                  # FastAPI routes
│   ├── tasks/                # Celery background tasks
│   ├── config.py             # Pydantic settings
│   └── main.py               # FastAPI app (port 8002)
├── start.bat             # One-click start (5 services)
├── start.ps1             # PowerShell start script
└── README.md
```

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- FFmpeg in PATH
- Redis (Docker or local)
- LLM API key (Anthropic, OpenAI, Gemini, or OpenRouter)

### One-Click Start
```bash
# Windows
start.bat

# PowerShell
./start.ps1
```

This starts 5 services:
| Service | Port | Description |
|---------|------|-------------|
| **Backend API** | 8000 | NexClip FastAPI server |
| **Nex Agent** | 8001 | Master AI agent |
| **Nexearch** | 8002 | Intelligence engine |
| **Celery Worker** | — | Background task processing |
| **Frontend** | 3000 | Next.js dashboard |

### Manual Setup

```bash
# 1. Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure
copy .env.example .env
# Edit .env — set API keys

# 3. Start services individually
uvicorn app.main:app --reload --port 8000          # Backend
python -m nex_agent.server                          # Nex Agent
uvicorn nexearch.main:app --reload --port 8002      # Nexearch
python -m nexearch.arc.server                       # Arc Agent
celery -A app.workers.celery_app worker --pool=threads  # Celery

# 4. Frontend
cd frontend
npm install && npm run dev
```

## Nexearch Intelligence Engine

### How It Works
1. **Scrape** — Collects 100+ posts from a client's social accounts (3 methods: Apify, Platform APIs, Crawlee+Playwright)
2. **Analyze** — LLM-powered content analysis with structured output
3. **Score + DNA** — 5-dimension scoring rubric → Account DNA synthesis
4. **Evolve** — Dual-mode: client-specific + universal evolution per platform
5. **Bridge** — Converts DNA into ClipDirectives for NexClip
6. **Publish** — Auto-publishes via Metricool, Platform APIs, or Crawlee

### Supported Platforms
Instagram · TikTok · YouTube · LinkedIn · Twitter/X · Facebook

### Dual-Mode Operation

| Mode | What It Does |
|------|-------------|
| **Client-Specific** | Per-client, per-platform DNA, evolution, and publishing |
| **Universal** | Cross-client patterns, global DNA, and benchmarks per platform |

### Data Tracking (Per Client)
- **Nexearch data**: Scrapes, analysis, DNA (versioned), evolution, directives, published posts
- **NexClip data**: System prompt injections, clip processing, style overrides, quality metrics
- **Change tracker**: Full audit trail with before/after snapshots and revert capability

### Agent Hierarchy
```
Nex Agent (Level 0 — Sovereign)
├── Controls everything in NexClip
├── 65+ tools, 11 categories (incl. writing + nexearch)
├── Full access to Arc Agent
└── Arc Agent (Level 1 — Director, inside Nexearch)
    ├── Controls Nexearch pipeline
    ├── 6 pipeline sub-agents
    └── Chat interface + action execution
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, Tailwind CSS, Framer Motion |
| Backend | FastAPI, SQLAlchemy, Pydantic |
| Task Queue | Celery + Redis |
| Database | SQLite (dev) / PostgreSQL (prod) |
| AI/LLM | Anthropic → OpenAI → Gemini → OpenRouter (fallback chain) |
| Video | FFmpeg, yt-dlp, OpenCV, MediaPipe |
| Intelligence | Nexearch (scraping, evolution, publishing) |
| Embeddings | sentence-transformers (local) or OpenAI |
| Scraping | Apify, Platform APIs, Crawlee + Playwright |

## Environment Variables

See `.env` for all configurable variables. Key sections:
- **LLM Configuration** — Fallback chain: Anthropic → OpenAI → Gemini → OpenRouter
- **Nexearch Configuration** — Scraping, publishing, evolution settings
- **Video Processing** — FFmpeg, caption, output settings

## License

Proprietary — All rights reserved.



Nex generate 12 clips out of this video: 'https://youtu.be/ULvplwBTbQk?si=ygqeRw0kpPP_b_Ny' and name the project ClipAura Test 1, after all clips generated successfully, take top 6 clips than apply any caption style to all of those 6 clips, than add a client named 'Ved_Saini-Clip_Aura', than upload those 6 clips on instagram one by one ( Upload via playwright, instagram username:'clipaura2026@gmail.com', and password:'ClipAura.com' )...!


This dashboard page that shows all the uploads it must livetime update the Projects pipeline, currently I need to refresh the page to see that Transcription is done Analyzing in progress ( Because before refreshing the page, it is still showing Transcription in the frontend )...!
And I want same with Projects Page livetime updating all the projects progress...!