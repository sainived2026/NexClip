#!/usr/bin/env bash
# ============================================================
#  NexClip — One-Command Deploy Script
#  Usage:  bash deploy.sh [SERVER_IP]
#  Example: bash deploy.sh 3.151.227.216
#
#  Run this on the Ubuntu server after every git push from
#  your local machine. It handles the full deploy cycle:
#    pull → patch IP → pip install → build frontend → restart PM2
# ============================================================

set -e

SERVER_IP="${1:-}"
NEXCLIP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$NEXCLIP_DIR/venv"

# ── Detect IP if not provided ────────────────────────────────
if [ -z "$SERVER_IP" ]; then
    SERVER_IP=$(curl -sf --max-time 4 http://checkip.amazonaws.com 2>/dev/null \
             || hostname -I 2>/dev/null | awk '{print $1}' \
             || echo "")
fi

if [ -z "$SERVER_IP" ]; then
    echo "ERROR: Could not detect server IP. Pass it as argument:"
    echo "  bash deploy.sh <IP>"
    exit 1
fi

echo ""
echo "============================================================"
echo "  NexClip — Deploy"
echo "  Server IP : $SERVER_IP"
echo "  Root      : $NEXCLIP_DIR"
echo "============================================================"
echo ""

# ── STEP 1: Git pull ─────────────────────────────────────────
echo "[1/5] Pulling latest code from GitHub..."
git -C "$NEXCLIP_DIR" fetch origin main
git -C "$NEXCLIP_DIR" reset --hard origin/main
echo "✓ Code updated"

# ── STEP 2: Patch server IP ──────────────────────────────────
echo ""
echo "[2/5] Patching server IP ($SERVER_IP) into frontend..."
if [ -f "$NEXCLIP_DIR/fix_server.sh" ]; then
    chmod +x "$NEXCLIP_DIR/fix_server.sh"
    bash "$NEXCLIP_DIR/fix_server.sh" "$SERVER_IP"
else
    echo "  WARNING: fix_server.sh not found — writing .env.local directly"
    cat > "$NEXCLIP_DIR/frontend/.env.local" <<EOF
NEXT_PUBLIC_API_URL=http://${SERVER_IP}:8000
NEXT_PUBLIC_NEX_AGENT_URL=http://${SERVER_IP}:8001
NEXT_PUBLIC_NEXEARCH_URL=http://${SERVER_IP}:8002
NEXT_PUBLIC_ARC_AGENT_URL=http://${SERVER_IP}:8003

NEXT_PUBLIC_NEX_WS_URL=ws://${SERVER_IP}:8001
NEXT_PUBLIC_ARC_WS_URL=ws://${SERVER_IP}:8003
EOF
    # Patch hardcoded localhost in source
    find "$NEXCLIP_DIR/frontend/src" -name "*.tsx" -o -name "*.ts" | \
        xargs sed -i "s|http://localhost:8000|http://${SERVER_IP}:8000|g; \
                      s|http://localhost:8001|http://${SERVER_IP}:8001|g; \
                      s|http://localhost:8002|http://${SERVER_IP}:8002|g; \
                      s|http://localhost:8003|http://${SERVER_IP}:8003|g; \
                      s|ws://localhost:8001|ws://${SERVER_IP}:8001|g; \
                      s|ws://localhost:8003|ws://${SERVER_IP}:8003|g" 2>/dev/null || true
    echo "✓ .env.local written and source patched"
fi

# ── STEP 3: Python dependencies ──────────────────────────────
echo ""
echo "[3/5] Installing Python dependencies..."
[ ! -d "$VENV" ] && python3 -m venv "$VENV"
source "$VENV/bin/activate"
pip install -q --upgrade pip yt-dlp
REQ="$NEXCLIP_DIR/backend/requirements.txt"
if [ -f "$REQ" ]; then
    pip install -q -r "$REQ"
    echo "✓ Python deps ready"
else
    echo "  WARN: requirements.txt not found at $REQ"
fi

# ── STEP 4: Frontend build ────────────────────────────────────
echo ""
echo "[4/5] Building frontend..."
cd "$NEXCLIP_DIR/frontend"
npm install --silent 2>/dev/null || true
npm run build 2>&1 | tail -8
cd "$NEXCLIP_DIR"
echo "✓ Frontend built"

# ── STEP 5: Restart PM2 ──────────────────────────────────────
echo ""
echo "[5/5] Restarting PM2 services..."
pm2 delete all 2>/dev/null || true
sleep 2
pm2 start "$NEXCLIP_DIR/ecosystem.config.js"
pm2 save
sleep 12

# ── Health checks ─────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Health Checks"
echo "============================================================"

# HTTP check for FastAPI services
check_http() {
    local label="$1" url="$2" pm2name="$3"
    if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
        echo "  ✓  $label"
    else
        echo "  ✗  $label  — run: pm2 logs $pm2name --lines 30"
    fi
}

# PM2 status check for background workers (no HTTP port)
check_pm2() {
    local label="$1" pm2name="$2"
    local status
    status=$(pm2 jlist 2>/dev/null | python3 -c "
import sys, json
try:
    procs = json.load(sys.stdin)
    for p in procs:
        if p.get('name') == '$pm2name':
            print(p.get('pm2_env', {}).get('status', 'unknown'))
            sys.exit(0)
    print('not_found')
except Exception as e:
    print('error')
" 2>/dev/null || echo "error")
    if [ "$status" = "online" ]; then
        echo "  ✓  $label (PM2: online)"
    else
        echo "  ✗  $label (PM2: $status) — run: pm2 logs $pm2name --lines 30"
    fi
}

check_http "Backend    " "http://localhost:8000/health"  "nexclip-backend"
check_http "Nex Agent  " "http://localhost:8001/health"  "nexclip-nex-agent"
check_http "Nexearch   " "http://localhost:8002/health"  "nexclip-nexearch"
check_http "Arc Agent  " "http://localhost:8003/health"  "nexclip-arc-agent"
check_http "Frontend   " "http://localhost:3000"          "nexclip-frontend"
check_pm2  "Celery     " "nexclip-celery"

echo ""
echo "  Open:  http://${SERVER_IP}:3000"
echo "============================================================"
echo ""
pm2 list
