#!/bin/bash
# ══════════════════════════════════════════════════════════════════════
#  NexClip — Full Server Recovery Script
#  Pulls latest code, patches IPs, rebuilds frontend, restarts services
#
#  Usage:
#    chmod +x server_recover.sh
#    ./server_recover.sh YOUR_SERVER_IP
#
#  Example:
#    ./server_recover.sh 10.240.1.246
# ══════════════════════════════════════════════════════════════════════
set -e

# ── Args ─────────────────────────────────────────────────────────────
SERVER_IP="${1:-}"
if [ -z "$SERVER_IP" ]; then
    # Try to auto-detect the public IP
    SERVER_IP=$(curl -sf --max-time 5 http://checkip.amazonaws.com || hostname -I | awk '{print $1}')
    echo "[AUTO] Detected server IP: $SERVER_IP"
fi

NEXCLIP_DIR="$HOME/NexClip"
VENV="$NEXCLIP_DIR/venv"

echo ""
echo "════════════════════════════════════════════════════"
echo "  NexClip Recovery  |  $(date)"
echo "  Server IP : $SERVER_IP"
echo "  Directory : $NEXCLIP_DIR"
echo "════════════════════════════════════════════════════"

cd "$NEXCLIP_DIR"

# ════════════════════════════════════
# STEP 1 — Pull latest code from GitHub
# ════════════════════════════════════
echo ""
echo "[1/7] Pulling latest code..."
git fetch origin main 2>&1
git reset --hard origin/main 2>&1
echo "    Latest commit: $(git log --oneline -1)"
echo "✓ Code updated"

# ════════════════════════════════════
# STEP 2 — Fix server IP in all source files
# ════════════════════════════════════
echo ""
echo "[2/7] Patching server IP ($SERVER_IP) into frontend source..."
bash fix_server.sh "$SERVER_IP"
echo "✓ Server IP patched"

# ════════════════════════════════════
# STEP 3 — Python dependencies
# ════════════════════════════════════
echo ""
echo "[3/7] Installing Python dependencies..."
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"
pip install -q --upgrade pip

# Requirements live in backend/requirements.txt
REQ_FILE="$NEXCLIP_DIR/backend/requirements.txt"
if [ -f "$REQ_FILE" ]; then
    pip install -q -r "$REQ_FILE"
    echo "✓ Python dependencies ready (from backend/requirements.txt)"
else
    echo "  WARNING: requirements file not found at $REQ_FILE"
    echo "  Trying to install core packages directly..."
    pip install -q fastapi uvicorn[standard] sqlalchemy aiosqlite celery[redis] \
        redis python-jose[cryptography] passlib[bcrypt] openai google-genai \
        anthropic python-dotenv pydantic pydantic-settings httpx requests \
        aiofiles aiohttp anyio psutil loguru rich tenacity PyYAML
    echo "✓ Core packages installed"
fi

# ════════════════════════════════════
# STEP 4 — Python syntax check
# ════════════════════════════════════
echo ""
echo "[4/7] Checking Python syntax..."
source "$VENV/bin/activate"
FAILED=0
for f in \
    nex_agent/response_validator.py \
    nex_agent/intent_classifier.py \
    nex_agent/personality.py \
    nex_agent/tools/agent_tools.py \
    nexearch/arc/conversation_engine.py \
    nexearch/arc/personality.py
do
    if python -m py_compile "$f" 2>&1; then
        echo "    ✓ $f"
    else
        echo "    ✗ SYNTAX ERROR in $f"
        FAILED=1
    fi
done
if [ "$FAILED" -eq 1 ]; then
    echo "ABORT: Syntax errors found. Fix before restarting services."
    exit 1
fi
echo "✓ All Python files OK"

# ════════════════════════════════════
# STEP 5 — Build frontend
# ════════════════════════════════════
echo ""
echo "[5/7] Building Next.js frontend (this takes ~2 min)..."
cd "$NEXCLIP_DIR/frontend"
npm install --legacy-peer-deps 2>&1 | tail -3
npm run build 2>&1 | tail -20
cd "$NEXCLIP_DIR"
echo "✓ Frontend built"

# ════════════════════════════════════
# STEP 6 — Restart all PM2 services
# ════════════════════════════════════
echo ""
echo "[6/7] Restarting PM2 services..."

# Stop everything cleanly
pm2 delete all 2>/dev/null || true
sleep 2

# Find and start the ecosystem config (server-only file)
ECOSYSTEM="$NEXCLIP_DIR/ecosystem.config.js"
if [ -f "$ECOSYSTEM" ]; then
    pm2 start "$ECOSYSTEM"
else
    echo "  WARNING: ecosystem.config.js not found — starting services manually"
    source "$VENV/bin/activate"

    # Backend
    pm2 start "uvicorn backend.app.main:app --host 0.0.0.0 --port 8000" \
        --name nexclip-backend --interpreter none \
        --cwd "$NEXCLIP_DIR"

    # Nex Agent
    pm2 start "python -m nex_agent.server" \
        --name nexclip-nex-agent --interpreter "$VENV/bin/python" \
        --cwd "$NEXCLIP_DIR"

    # Nexearch (port 8002)
    pm2 start "python -m nexearch.server" \
        --name nexclip-nexearch --interpreter "$VENV/bin/python" \
        --cwd "$NEXCLIP_DIR"

    # Arc Agent
    pm2 start "python -m nexearch.arc.server" \
        --name nexclip-arc-agent --interpreter "$VENV/bin/python" \
        --cwd "$NEXCLIP_DIR"

    # Celery Worker
    pm2 start "celery -A backend.app.celery_app worker --loglevel=info --concurrency=2" \
        --name nexclip-celery --interpreter "$VENV/bin/python" \
        --cwd "$NEXCLIP_DIR"

    # Frontend
    pm2 start "npm start" \
        --name nexclip-frontend \
        --cwd "$NEXCLIP_DIR/frontend"
fi

pm2 save
echo "✓ PM2 services started"

# ════════════════════════════════════
# STEP 7 — Health check
# ════════════════════════════════════
echo ""
echo "[7/7] Waiting 15s then checking health..."
sleep 15

check() {
    local name=$1
    local url=$2
    if curl -sf --max-time 6 "$url" > /dev/null 2>&1; then
        echo "    ✓  $name → ONLINE"
    else
        echo "    ✗  $name → OFFLINE  (check: pm2 logs nexclip-$(echo $name | tr ' ' '-' | tr '[:upper:]' '[:lower:]') --lines 50)"
    fi
}

check "Backend    (8000)" "http://localhost:8000/health"
check "Nex Agent  (8001)" "http://localhost:8001/health"
check "Nexearch   (8002)" "http://localhost:8002/health"
check "Arc Agent  (8003)" "http://localhost:8003/health"
check "Frontend   (3000)" "http://localhost:3000"

echo ""
echo "════════════════════════════════════════════════════"
pm2 list
echo "════════════════════════════════════════════════════"
echo ""
echo "  Your app: http://${SERVER_IP}:3000"
echo ""
echo "  If a service is still OFFLINE:"
echo "    pm2 logs nexclip-<service> --lines 50"
echo ""
