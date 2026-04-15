---
description: Start all NexClip + Nexearch services (Backend, Celery, Nex Agent, Nexearch, Arc Agent, Frontend)
---

// turbo-all

1. Start the Backend API (Port 8000)
powershell

cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip\backend'; .\venv\Scripts\activate; uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


2. Start the Nex Agent Backend (Port 8001)
powershell

cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip'; .\backend\venv\Scripts\activate; python -m nex_agent.server


3. Start the Nexearch Intelligence Engine (Port 8002)
powershell

cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip'; .\backend\venv\Scripts\activate; python -m uvicorn nexearch.main:app --reload --host 0.0.0.0 --port 8002


4. Start the Arc Agent Backend (Port 8003)
powershell

cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip'; .\backend\venv\Scripts\activate; python -m nexearch.arc.server


5. Start the Celery Worker (all queues, local-friendly)
powershell

cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip\backend'; .\venv\Scripts\activate; .\venv\Scripts\python.exe -m celery -A app.workers.celery_app worker -Q video,captions,nexearch,celery --loglevel=info --pool=threads --concurrency=8

6. Start the Frontend Next.js App (Port 3000)
powershell

cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip\frontend'; npm run dev

## Agent Bridge (No Extra Service)

The Agent Bridge (`nexearch/bridge.py`) is an HTTP-based communication layer built directly into both Nex Agent and Arc Agent. It does NOT require a separate process or terminal.

- **Nex Agent → Arc Agent**: Uses `ArcBridge` class (HTTP to port 8003)
- **Arc Agent → Nex Agent**: Uses `NexBridge` class (HTTP to port 8001)
- **Sub-agents**: Communicate through the same bridge layer automatically
- **Config**: Set `ARC_AGENT_URL` and `NEXEARCH_NEX_AGENT_URL` in `.env` to customize

### Service Port Map

| Service | Port | Purpose |
|---------|------|---------|
| Backend | 8000 | NexClip main API |
| Nex Agent | 8001 | Master intelligence agent |
| Nexearch | 8002 | Intelligence engine API |
| Arc Agent | 8003 | Execution agent (chat + tools) |
| Frontend | 3000 | Next.js dashboard |

### Production Mode

For production servers (128+ cores, 512 GB RAM), use `start_production.bat` instead.
It runs 3 dedicated Celery workers with isolated queues:

| Queue | Concurrency | Purpose |
|-------|-------------|---------|
| video | 100 | Video processing pipelines |
| captions | 600 | Caption rendering |
| nexearch | 50 | Nexearch analysis + upload pipelines |