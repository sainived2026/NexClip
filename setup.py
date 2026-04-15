#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
+==========================================================================+
|                  NexClip — Ultra-Reliable System Setup                   |
|                                                                          |
|  A single-file, zero-dependency installer for the complete NexClip       |
|  autonomous content engine. Sets up all subsystems in sequence:          |
|                                                                          |
|    ✦ NexClip Backend API    (FastAPI · SQLAlchemy · Celery)              |
|    ✦ Nex Agent              (LLM Persona · Memory · Tools)               |
|    ✦ Nexearch Engine        (Scraping · Analysis · DNA Evolution)        |
|    ✦ Arc Agent              (Client Intelligence · Chat)                 |
|    ✦ Frontend               (Next.js 16 · Turbopack)                    |
|                                                                          |
|  Usage:                                                                  |
|    python setup.py                   # Full setup                        |
|    python setup.py --check           # Check prerequisites only           |
|    python setup.py --skip-playwright # Skip browser install               |
|    python setup.py --skip-frontend   # Skip frontend npm install          |
|                                                                          |
|  Requirements:                                                           |
|    • Python 3.10 – 3.12                                                  |
|    • Node.js 18+                                                         |
|    • npm 9+                                                              |
|    • 10 GB+ free disk space (libraries + models)                        |
|                                                                          |
+==========================================================================+
"""

from __future__ import annotations

import os
import sys
import re
import json
import shutil
import socket
import platform
import subprocess
import traceback
import secrets
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional


# -- Force UTF-8 output on Windows (prevents cp1252 UnicodeEncodeError) ------
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ==========================================================================
# CONSTANTS & CONFIGURATION
# ==========================================================================

MIN_PYTHON = (3, 10)
MAX_PYTHON = (3, 12)
MIN_NODE_MAJOR = 18
MIN_NPM_MAJOR = 9

REQUIRED_PORTS = [3000, 8000, 8001, 8002, 8003]

SERVICE_MAP = {
    "Backend API":    {"port": 8000, "health": "/api/health"},
    "Nex Agent":      {"port": 8001, "health": "/health"},
    "Nexearch":       {"port": 8002, "health": "/health"},
    "Arc Agent":      {"port": 8003, "health": "/health"},
    "Frontend":       {"port": 3000, "health": "/"},
}

TOTAL_STEPS = 13


# ==========================================================================
# LOGGER
# ==========================================================================

class SetupLogger:
    """
    Dual-sink logger: prints to stdout with ANSI emoji flags,
    and appends to a UTF-8 log file. Tracks all warnings/errors.
    """

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(
            f"NexClip Setup Log\n"
            f"Started: {datetime.now().isoformat()}\n"
            f"Platform: {platform.system()} {platform.release()} | Python {platform.python_version()}\n"
            f"{'=' * 72}\n\n",
            encoding="utf-8",
        )

    # -- Internal sink --------------------------------------------------
    def _write(self, msg: str):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    # -- Public interface -----------------------------------------------
    def info(self, msg: str):
        print(f"    ✅  {msg}")
        self._write(f"[INFO]  {msg}")

    def warn(self, msg: str):
        print(f"    ⚠️   {msg}")
        self._write(f"[WARN]  {msg}")
        self.warnings.append(msg)

    def error(self, msg: str):
        print(f"    ❌  {msg}")
        self._write(f"[ERROR] {msg}")
        self.errors.append(msg)

    def success(self, msg: str):
        print(f"    🎉  {msg}")
        self._write(f"[OK]    {msg}")

    def detail(self, msg: str):
        print(f"         {msg}")
        self._write(f"        {msg}")

    def step(self, num: int, total: int, title: str):
        bar = "-" * 70
        print(f"\n{bar}")
        print(f"  [{num:02d}/{total}]  {title}")
        print(f"{bar}")
        self._write(f"\n{'-' * 72}\n[STEP {num:02d}/{total}]  {title}\n{'-' * 72}")

    def header(self, title: str):
        pad = max(0, 70 - len(title))
        left = pad // 2
        right = pad - left
        border = "=" * 72
        print(f"\n+{border}+")
        print(f"|  {' ' * left}{title}{' ' * right}  |")
        print(f"+{border}+\n")
        self._write(f"\n{'=' * 72}\n{title}\n{'=' * 72}")

    def save_exception(self, context: str, exc: Exception):
        tb = traceback.format_exc()
        self._write(f"\n[EXCEPTION in {context}]\n{tb}\n")
        self.errors.append(f"{context}: {str(exc)[:250]}")


# ==========================================================================
# UTILITY FUNCTIONS
# ==========================================================================

def run(
    cmd: list[str],
    cwd: Optional[str] = None,
    timeout: int = 300,
    env: Optional[dict] = None,
    encoding: str = "utf-8",
    shell: bool = False,
) -> tuple[bool, str, str]:
    """
    Run a shell command safely.

    Returns:
        (success, stdout, stderr)
    All text is decoded with the requested encoding, falling back to
    latin-1 on errors so we never raise on unexpected bytes.
    """
    try:
        merged_env = {**os.environ, **(env or {})}
        # Force UTF-8 output on Windows
        merged_env.setdefault("PYTHONUTF8", "1")
        merged_env.setdefault("PYTHONIOENCODING", "utf-8")

        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            timeout=timeout,
            env=merged_env,
            shell=shell,
        )
        stdout = result.stdout.decode(encoding, errors="replace")
        stderr = result.stderr.decode(encoding, errors="replace")
        return result.returncode == 0, stdout, stderr

    except subprocess.TimeoutExpired:
        return False, "", f"❌ Command timed out after {timeout}s: {' '.join(str(c) for c in cmd)}"
    except FileNotFoundError:
        return False, "", f"Command not found: {cmd[0]}"
    except Exception as exc:
        return False, "", str(exc)


def _node_cmd(name: str) -> list[str]:
    """
    Return the correct command list for node ecosystem tools (node, npm, npx).
    On Windows, npm/npx ship as .cmd batch scripts and must be invoked via cmd.exe
    or explicitly with the .cmd suffix. Using shell=True is the most reliable approach.
    """
    if platform.system() == "Windows":
        # Use cmd /c so .cmd files are found on PATH correctly
        return ["cmd", "/c", name]
    return [name]


def port_free(port: int) -> bool:
    """Return True if nothing is listening on the given TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) != 0


def parse_semver(version_str: str) -> tuple[int, ...]:
    """Extract the first N dotted integers from a version string."""
    nums = re.findall(r"\d+", version_str)
    return tuple(int(n) for n in nums[:3]) if nums else (0,)


def find_python_interpreter() -> str:
    """
    Locate a Python interpreter in the allowed version window.

    Tries `python`, `python3`, and `py` (Windows launcher).
    Returns the command string that works, or "" if none found.
    """
    candidates = ["python", "python3", "py"]
    for cmd in candidates:
        ok, out, err = run([cmd, "--version"], timeout=10)
        raw = (out or err).strip()
        ver = parse_semver(raw)
        if ok and len(ver) >= 2 and MIN_PYTHON <= ver[:2] <= MAX_PYTHON:
            return cmd
    return ""


def _venv_python(venv_dir: Path, is_windows: bool) -> Path:
    """Return the absolute path to the venv Python binary."""
    if is_windows:
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


# ==========================================================================
# MAIN SETUP CLASS
# ==========================================================================

class NexClipSetup:
    """
    Orchestrates the full NexClip install sequence.

    Stores install-time state so each step can safely read results produced
    by earlier steps (e.g., step 2 sets self.venv_py so steps 3–12 can use it).
    """

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.root = Path(__file__).resolve().parent
        self.backend_dir = self.root / "backend"
        self.frontend_dir = self.root / "frontend"
        self.nexearch_dir = self.root / "nexearch"
        self.nex_agent_dir = self.root / "nex_agent"
        self.venv_dir = self.backend_dir / "venv"
        self.env_file = self.backend_dir / ".env"
        self.is_windows = platform.system() == "Windows"

        self.log = SetupLogger(self.root / "setup_log.txt")
        self.sys_python: str = ""          # e.g. "python3"
        self.venv_py: Path = Path()        # absolute path to venv python

        # Step registry — order matters
        self._steps: list[tuple[int, str, callable]] = [
            ( 1,  "Checking System Prerequisites",          self._step_prerequisites),
            ( 2,  "Creating Python Virtual Environment",    self._step_venv),
            ( 3,  "Installing Backend & Engine Dependencies", self._step_deps),
            ( 4,  "Configuring Environment (.env)",         self._step_env),
            ( 5,  "Initialising Database Schema",           self._step_database),
            ( 6,  "Installing Frontend (Node) Dependencies",self._step_frontend),
            ( 7,  "Creating Storage & Data Directories",    self._step_storage),
            ( 8,  "Writing Start Scripts",                  self._step_start_scripts),
            ( 9,  "Verifying Agent Skills & Workflows",     self._step_agent_skills),
            (10,  "Installing Playwright Browsers",         self._step_playwright),
            (11,  "Verifying Caption Font Assets",          self._step_fonts),
            (12,  "Running Module Import Checks",           self._step_import_checks),
            (13,  "Final System Validation",                self._step_final_validation),
        ]

    # -- Public entry point ---------------------------------------------
    def run(self):
        self.log.header("NexClip — Full System Setup")
        print(f"  Platform : {platform.system()} {platform.release()} ({platform.machine()})")
        print(f"  Python   : {platform.python_version()}")
        print(f"  Root     : {self.root}")
        print(f"  Time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        for step_num, step_name, step_fn in self._steps:
            self.log.step(step_num, TOTAL_STEPS, step_name)
            try:
                step_fn()
            except Exception as exc:
                self.log.save_exception(step_name, exc)
                print(f"\n  ⚠️  Step {step_num} encountered an error — continuing...\n")

        self._print_summary()

    # ==================================================================
    # STEP 1 — Prerequisites
    # ==================================================================
    def _step_prerequisites(self):
        all_ok = True

        # Python
        self.sys_python = find_python_interpreter()
        if self.sys_python:
            ok, out, _ = run([self.sys_python, "--version"])
            self.log.info(f"Python interpreter : {(out or '').strip()} ({self.sys_python})")
        else:
            self.log.error(
                f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}–{MAX_PYTHON[0]}.{MAX_PYTHON[1]} not found. "
                "Download from https://python.org"
            )
            all_ok = False

        # Node.js — use cmd /c on Windows so .cmd scripts are resolved
        ok, out, _ = run(_node_cmd("node") + ["--version"])
        if ok:
            ver = parse_semver(out.strip())
            if ver and ver[0] >= MIN_NODE_MAJOR:
                self.log.info(f"Node.js            : {out.strip()}")
            else:
                self.log.warn(
                    f"Node.js {out.strip()} found but v{MIN_NODE_MAJOR}+ recommended. "
                    "Upgrade at https://nodejs.org"
                )
        else:
            self.log.error(
                f"Node.js not found (need v{MIN_NODE_MAJOR}+). Install from https://nodejs.org"
            )
            all_ok = False

        # npm — try cmd /c npm on Windows
        ok, out, _ = run(_node_cmd("npm") + ["--version"])
        if ok:
            ver = parse_semver(out.strip())
            if ver and ver[0] >= MIN_NPM_MAJOR:
                self.log.info(f"npm                : v{out.strip().strip()}")
            else:
                self.log.warn(
                    f"npm v{out.strip()} found, v{MIN_NPM_MAJOR}+ preferred. Run: npm install -g npm"
                )
        else:
            self.log.error("npm not found — required for the Next.js frontend.")
            all_ok = False

        # Git (optional)
        ok, out, _ = run(["git", "--version"])
        if ok:
            self.log.info(f"Git                : {out.strip()}")
        else:
            self.log.warn("Git not found. Not required but recommended for updates.")

        # Redis (optional, needed for Celery)
        redis_ok = False
        try:
            import importlib
            redis_mod = importlib.import_module("redis")
            r = redis_mod.from_url("redis://localhost:6379/0", socket_timeout=2)
            r.ping()
            redis_ok = True
        except Exception:
            pass

        if redis_ok:
            self.log.info("Redis              : accessible on localhost:6379")
        else:
            self.log.warn(
                "Redis not reachable on port 6379. "
                "Celery task queue will not work without Redis. "
                "Windows: install Memurai (https://www.memurai.com) or WSL Redis."
            )

        # Port availability
        for port in REQUIRED_PORTS:
            if port_free(port):
                self.log.info(f"Port {port}           : free ✓")
            else:
                self.log.warn(
                    f"Port {port} is already in use. "
                    "A conflicting process may prevent the matching service from starting."
                )

        # Disk space
        try:
            total, used, free = shutil.disk_usage(self.root)
            free_gb = free / (1024 ** 3)
            if free_gb < 5:
                self.log.warn(
                    f"Low disk space: {free_gb:.1f} GB free. "
                    "NexClip needs ~10 GB for models, libraries, and media storage."
                )
            elif free_gb < 10:
                self.log.warn(f"Disk space: {free_gb:.1f} GB free (10 GB+ recommended for models).")
            else:
                self.log.info(f"Disk space         : {free_gb:.1f} GB free")
        except Exception as exc:
            self.log.warn(f"Disk space check failed: {exc}")

        if all_ok:
            self.log.success("All mandatory prerequisites satisfied.")

    # ==================================================================
    # STEP 2 — Virtual Environment
    # ==================================================================
    def _step_venv(self):
        if not self.sys_python:
            self.log.error("Cannot create venv — no valid Python interpreter found in Step 1.")
            return

        if self.venv_dir.exists():
            self.log.info("Virtual environment already exists — skipping creation.")
        else:
            self.log.detail("Creating virtualenv, this may take ~30 s…")
            ok, _, err = run(
                [self.sys_python, "-m", "venv", str(self.venv_dir)],
                cwd=str(self.backend_dir),
                timeout=120,
            )
            if ok:
                self.log.info("Virtual environment created.")
            else:
                self.log.error(f"venv creation failed: {err[:300]}")
                return

        # Resolve the Python binary inside the venv
        candidate = _venv_python(self.venv_dir, self.is_windows)
        if candidate.exists():
            self.venv_py = candidate
            self.log.info(f"Venv Python        : {self.venv_py}")
        else:
            self.log.error(
                f"Venv Python binary not found at {candidate}. "
                "The venv may be corrupt — delete backend/venv and re-run setup."
            )

    # ==================================================================
    # STEP 3 — Python Dependencies
    # ==================================================================
    def _step_deps(self):
        if not self.venv_py.exists():
            self.log.error("No venv Python available. Skipping dependency install.")
            return

        py = str(self.venv_py)
        req_file = self.backend_dir / "requirements.txt"

        if not req_file.exists():
            self.log.error(f"requirements.txt not found at {req_file}")
            return

        # 1. Upgrade pip + setuptools + wheel in one shot
        self.log.detail("Upgrading pip, setuptools, wheel…")
        ok, _, err = run(
            [py, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
            cwd=str(self.backend_dir),
            timeout=120,
        )
        if ok:
            self.log.info("pip / setuptools / wheel are up to date.")
        else:
            self.log.warn(f"pip upgrade warning: {err[:200]}")

        # 2. Install all requirements
        self.log.detail("Installing requirements.txt (≈5–15 min first time, mostly PyTorch)…")
        start = time.time()
        ok, out, err = run(
            [py, "-m", "pip", "install", "-r", str(req_file), "--prefer-binary"],
            cwd=str(self.backend_dir),
            timeout=1200,  # 20 min — torch can be very slow
        )
        elapsed = time.time() - start

        if ok:
            self.log.success(f"All dependencies installed in {elapsed:.0f}s.")
        else:
            # Surface only real errors, not the spam of messages pip prints
            error_lines = [
                line.strip() for line in (err or "").splitlines()
                if any(kw in line.upper() for kw in ("ERROR", "FAILED", "COULD NOT"))
            ]
            for line in error_lines[:10]:
                self.log.warn(f"pip: {line[:160]}")
            self.log.warn(
                "Some packages may have failed. Check setup_log.txt → "
                "pip errors are often optional extras (e.g. GPU-only packages on CPU machines)."
            )
            self.log._write(f"\n[PIP FULL STDERR]\n{err}\n")

    # ==================================================================
    # STEP 4 — Environment Configuration (.env)
    # ==================================================================
    def _step_env(self):
        env_example = self.backend_dir / ".env.example"

        if self.env_file.exists():
            self.log.info(".env already exists — leaving user values intact.")
            self._ensure_env_keys()
            return

        # Prefer example file if present
        if env_example.exists():
            shutil.copy2(env_example, self.env_file)
            self.log.info(".env created from .env.example.")
        else:
            self._generate_env()
            self.log.info(".env generated with auto-defaults.")

        self.log.detail("Edit backend/.env to add your API keys before first run.")

    def _generate_env(self):
        """Write a complete, annotated .env with secure random secrets."""
        secret_key = secrets.token_urlsafe(48)
        fernet_key = secrets.token_urlsafe(32)
        db_url = f"sqlite:///{(self.backend_dir / 'nexclip.db').resolve().as_posix()}"
        storage_root = (self.backend_dir / "storage").resolve().as_posix()
        nexearch_data = self.root.resolve().as_posix() + "/nexearch_data"

        content = f"""\
# =========================================================
# NexClip — Environment Configuration
# Generated by setup.py  on  {datetime.now().strftime('%Y-%m-%d %H:%M')}
#
# Fill in your API keys below before starting the services.
# Do NOT commit this file to version control.
# =========================================================

# -- Database ---------------------------------------------
DATABASE_URL={db_url}

# -- Redis (Celery Broker + Result Backend) ----------------
REDIS_URL=redis://localhost:6379/0

# -- File Storage -----------------------------------------
STORAGE_MODE=local
STORAGE_LOCAL_ROOT={storage_root}
MAX_UPLOAD_SIZE_MB=4000

# -- LLM Provider Chain ------------------------------------
# NexClip tries each provider in order until one succeeds.
# Leave blank to skip a provider. At least ONE must be set.
#
# 1 ▸ Anthropic Claude (primary — best reasoning)
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-haiku-4-5-20250315
#
# 2 ▸ Google Gemini (secondary)
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash-lite
#
# 3 ▸ OpenAI / OpenRouter (tertiary / free-tier fallback)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENROUTER_API_KEY=
OPENROUTER_MODEL=qwen/qwen3.6-plus:free

# -- LLM Tuning -------------------------------------------
LLM_TIMEOUT=600
LLM_MAX_TOKENS=32000
LLM_TEMPERATURE=0.3
LLM_MAX_TRANSCRIPT_LENGTH=360000

# -- Speech-to-Text ----------------------------------------
# ElevenLabs Scribe is the preferred cloud STT.
# If the key is missing, faster-whisper (local GPU) is used.
ELEVENLABS_API_KEY=
ELEVENLABS_STT_MODEL=scribe_v2
#
# Local Whisper fallback settings
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16

# -- Timeouts (seconds) ------------------------------------
FFMPEG_CLIP_TIMEOUT=600
FFMPEG_AUDIO_TIMEOUT=600
AUDIO_LOAD_TIMEOUT=1800
DOWNLOAD_TIMEOUT=1800
FFPROBE_TIMEOUT=30
FFMPEG_DURATION_TIMEOUT=30

# -- Video Output ------------------------------------------
OUTPUT_VIDEO_WIDTH=1080
OUTPUT_VIDEO_HEIGHT=1920
VIDEO_CODEC=libx264
VIDEO_PRESET=ultrafast
VIDEO_CRF=23
AUDIO_CODEC=aac
AUDIO_BITRATE=128k
AUDIO_SAMPLE_RATE=44100
CAPTION_FONT_SIZE=42
CAPTION_MAX_LENGTH=80

# -- Application -------------------------------------------
APP_NAME=NexClip
APP_ENV=production
SECRET_KEY={secret_key}
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ALLOW_DEV_AUTH_BYPASS=false
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# -- Clip Generation Defaults ------------------------------
DEFAULT_CLIP_COUNT=10
MIN_CLIP_DURATION=30
MAX_CLIP_DURATION=90

# -- Performance / Concurrency -----------------------------
FFMPEG_PARALLEL_CLIPS=2
FFMPEG_THREADS_PER_CLIP=1
SPEAKER_DETECTION_SAMPLE_FPS=3
SPEAKER_DETECTION_FRAME_WIDTH=640
CELERY_VIDEO_CONCURRENCY=8
CELERY_CAPTION_CONCURRENCY=16
CELERY_NEXEARCH_CONCURRENCY=4

# -- Caption Engine ----------------------------------------
CAPTION_ENGINE_ENABLED=true
CAPTION_DEFAULT_STYLE=opus_classic
CAPTION_WORDS_PER_SEGMENT=4
CAPTION_FONT_SEARCH_PATHS=./fonts

# -- Nex Agent ---------------------------------------------
NEX_AGENT_ENABLED=true
NEX_AGENT_PORT=8001
NEX_AGENT_MEMORY_PATH=./nex_agent_memory

# -- Nexearch Intelligence Engine -------------------------
NEXEARCH_ENABLED=true
NEXEARCH_APP_ENV=production
NEXEARCH_LOG_LEVEL=INFO
NEXEARCH_CLIENTS_DIR={nexearch_data}
NEXEARCH_APIFY_TOKEN=
NEXEARCH_EVOLUTION_MAX_CHANGE_PERCENT=15
NEXEARCH_EVOLUTION_MIN_POSTS_FOR_PATTERN=3
NEXEARCH_ENABLE_UNIVERSAL_EVOLUTION=true
NEXEARCH_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# -- Arc Agent (Client Intelligence) ----------------------
NEXEARCH_ARC_AGENT_ENABLED=true
NEXEARCH_ARC_AGENT_MODEL=claude-haiku-4-5-20250315
ARC_AGENT_PORT=8003
ARC_AGENT_MEMORY_PATH=./arc_agent_memory
ARC_AGENT_URL=http://localhost:8003

# -- Agent Bridge (Nexearch ↔ Nex Agent) ------------------
NEXEARCH_NEX_AGENT_ENABLED=true
NEXEARCH_NEX_AGENT_URL=http://localhost:8001
AGENT_BRIDGE_ENABLED=true
AGENT_BRIDGE_TIMEOUT_SECONDS=30

# -- Encryption (Credential Storage) ----------------------
NEXEARCH_FERNET_KEY={fernet_key}
"""
        self.env_file.write_text(content, encoding="utf-8")

    def _ensure_env_keys(self):
        """
        Add any keys that are missing from an existing .env
        without touching values already set.
        """
        existing = self.env_file.read_text(encoding="utf-8")
        additions: list[str] = []

        # Quick membership check — only add if key is completely absent
        must_have = {
            "NEXEARCH_CLIENTS_DIR": f"{(self.root / 'nexearch_data').resolve().as_posix()}",
            "ARC_AGENT_URL":        "http://localhost:8003",
            "AGENT_BRIDGE_ENABLED": "true",
        }
        for key, default in must_have.items():
            if not re.search(rf"^{key}\s*=", existing, re.MULTILINE):
                additions.append(f"{key}={default}")
                self.log.info(f"Added missing .env key: {key}")

        if additions:
            with open(self.env_file, "a", encoding="utf-8") as f:
                f.write("\n# -- Added by setup.py --\n")
                f.write("\n".join(additions) + "\n")

    # ==================================================================
    # STEP 5 — Database
    # ==================================================================
    def _step_database(self):
        if not self.venv_py.exists():
            self.log.warn("No venv Python — skipping DB init.")
            return

        py = str(self.venv_py)
        script = (
            "import sys; sys.path.insert(0, '.'); "
            "from app.db.database import init_db; init_db(); "
            "print('DB initialised')"
        )
        ok, out, err = run([py, "-c", script], cwd=str(self.backend_dir), timeout=60)

        if ok:
            self.log.info("Database schema initialised (all tables ready).")
        else:
            self.log.warn(
                f"DB init returned warnings: {(err or '')[:250]}\n"
                "The database will be created automatically on first server boot."
            )
            self.log._write(f"\n[DB INIT STDERR]\n{err}\n")

    # ==================================================================
    # STEP 6 — Frontend Dependencies
    # ==================================================================
    def _step_frontend(self):
        if self.args.skip_frontend:
            self.log.warn("--skip-frontend flag set — skipping npm install.")
            return

        if not self.frontend_dir.exists():
            self.log.error(f"Frontend directory not found: {self.frontend_dir}")
            return

        pkg_json = self.frontend_dir / "package.json"
        if not pkg_json.exists():
            self.log.error("frontend/package.json not found. The frontend cannot be installed.")
            return

        # Read expected next.js version for reporting
        try:
            with open(pkg_json, encoding="utf-8") as f:
                pkg = json.load(f)
            next_ver = pkg.get("dependencies", {}).get("next", "?")
            self.log.detail(f"Next.js version   : {next_ver}")
        except Exception:
            pass

        node_modules = self.frontend_dir / "node_modules"
        if node_modules.exists() and any(node_modules.iterdir()):
            self.log.detail("node_modules present — running npm install to sync any additions…")
        else:
            self.log.detail("Installing frontend packages (≈1–3 min)…")

        ok, out, err = run(_node_cmd("npm") + ["install"], cwd=str(self.frontend_dir), timeout=300)

        if ok:
            self.log.success("Frontend dependencies installed.")
        else:
            self.log.warn(f"npm install warnings: {(err or '')[:300]}")
            self.log._write(f"\n[NPM STDERR]\n{err}\n")

    # ==================================================================
    # STEP 7 — Storage & Data Directories
    # ==================================================================
    def _step_storage(self):
        storage_root = self.backend_dir / "storage"
        nexearch_data = self.root / "nexearch_data"

        directories = [
            # Backend storage buckets
            storage_root / "uploads",
            storage_root / "clips",
            storage_root / "transcripts",
            storage_root / "audio",
            storage_root / "temp",
            storage_root / "previews",
            storage_root / "thumbnails",
            # Agent memory stores
            self.root / "nex_agent_memory",
            self.root / "arc_agent_memory",
            # Nexearch data directories
            nexearch_data / "clients",
            nexearch_data / "universal",
            nexearch_data / "_meta",
        ]

        created = 0
        for d in directories:
            if not d.exists():
                d.mkdir(parents=True, exist_ok=True)
                created += 1

        total = len(directories)
        self.log.info(
            f"Storage tree verified: {total} directories "
            f"({created} newly created, {total - created} already existed)."
        )

        # Write .gitkeep so git tracks empty directories
        for d in directories:
            git_keep = d / ".gitkeep"
            if not git_keep.exists():
                git_keep.write_text("", encoding="utf-8")

    # ==================================================================
    # STEP 8 — Start Scripts
    # ==================================================================
    def _step_start_scripts(self):
        root_w = str(self.root).replace("/", "\\")
        backend_w = str(self.backend_dir).replace("/", "\\")
        frontend_w = str(self.frontend_dir).replace("/", "\\")

        # -- start.bat ------------------------------------------------
        bat = f"""\
@echo off
chcp 65001 >nul 2>&1
title NexClip — All Services
echo.
echo ======================================================
echo   NexClip — Starting Full Ecosystem
echo   Backend API  : http://localhost:8000
echo   Nex Agent    : http://localhost:8001
echo   Nexearch     : http://localhost:8002
echo   Arc Agent    : http://localhost:8003
echo   Frontend     : http://localhost:3000
echo ======================================================
echo.

:: [1/6] Backend API
echo [1/6] Starting Backend API (port 8000)...
start "NexClip Backend" cmd /k "cd /d {backend_w} && .\\venv\\Scripts\\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 4 /nobreak >nul

:: [2/6] Nex Agent
echo [2/6] Starting Nex Agent (port 8001)...
start "Nex Agent" cmd /k "cd /d {root_w} && .\\backend\\venv\\Scripts\\activate && python -m nex_agent.server --port 8001"
timeout /t 3 /nobreak >nul

:: [3/6] Nexearch Engine
echo [3/6] Starting Nexearch Engine (port 8002)...
start "Nexearch Engine" cmd /k "cd /d {root_w} && .\\backend\\venv\\Scripts\\activate && python -m uvicorn nexearch.main:app --reload --host 0.0.0.0 --port 8002"
timeout /t 3 /nobreak >nul

:: [4/6] Arc Agent
echo [4/6] Starting Arc Agent (port 8003)...
start "Arc Agent" cmd /k "cd /d {root_w} && .\\backend\\venv\\Scripts\\activate && python -m nexearch.arc.server --port 8003"
timeout /t 3 /nobreak >nul

:: [5/6] Celery Worker
echo [5/6] Starting Celery Worker...
start "Celery Worker" cmd /k "cd /d {backend_w} && .\\venv\\Scripts\\activate && .\\venv\\Scripts\\python.exe -m celery -A app.workers.celery_app worker --loglevel=info --pool=threads --concurrency=8"
timeout /t 3 /nobreak >nul

:: [6/6] Frontend
echo [6/6] Starting Frontend (port 3000)...
start "NexClip Frontend" cmd /k "cd /d {frontend_w} && npm run dev"
timeout /t 6 /nobreak >nul

echo.
echo ======================================================
echo   All services launched!
echo   Open your browser at http://localhost:3000
echo ======================================================
echo.
pause
"""

        # -- start.ps1 ------------------------------------------------
        ps1 = f"""\
# NexClip — Start All Services (PowerShell)
# Generated by setup.py

$Root     = '{root_w}'
$Backend  = '{backend_w}'
$Frontend = '{frontend_w}'

Write-Host ""
Write-Host ("=" * 56) -ForegroundColor Cyan
Write-Host "  NexClip — Launching Full Ecosystem" -ForegroundColor Cyan
Write-Host ("=" * 56) -ForegroundColor Cyan
Write-Host ""

# 1. Backend API
Write-Host "[1/6] Backend API  → http://localhost:8000" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$Backend'; .\\venv\\Scripts\\Activate.ps1; uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
Start-Sleep -Seconds 4

# 2. Nex Agent
Write-Host "[2/6] Nex Agent    → http://localhost:8001" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$Root'; .\\backend\\venv\\Scripts\\Activate.ps1; python -m nex_agent.server --port 8001"
Start-Sleep -Seconds 3

# 3. Nexearch Engine
Write-Host "[3/6] Nexearch     → http://localhost:8002" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$Root'; .\\backend\\venv\\Scripts\\Activate.ps1; python -m uvicorn nexearch.main:app --reload --host 0.0.0.0 --port 8002"
Start-Sleep -Seconds 3

# 4. Arc Agent
Write-Host "[4/6] Arc Agent    → http://localhost:8003" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$Root'; .\\backend\\venv\\Scripts\\Activate.ps1; python -m nexearch.arc.server --port 8003"
Start-Sleep -Seconds 3

# 5. Celery Worker
Write-Host "[5/6] Celery Worker → background tasks" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$Backend'; .\\venv\\Scripts\\Activate.ps1; python -m celery -A app.workers.celery_app worker --loglevel=info --pool=threads --concurrency=8"
Start-Sleep -Seconds 3

# 6. Frontend
Write-Host "[6/6] Frontend     → http://localhost:3000" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$Frontend'; npm run dev"
Start-Sleep -Seconds 6

Write-Host ""
Write-Host ("=" * 56) -ForegroundColor Cyan
Write-Host "  All services launched!" -ForegroundColor Green
Write-Host "  Open http://localhost:3000 in your browser" -ForegroundColor Green
Write-Host ("=" * 56) -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close this window"
"""

        bat_path = self.root / "start.bat"
        ps1_path = self.root / "start.ps1"
        bat_path.write_text(bat, encoding="utf-8")
        ps1_path.write_text(ps1, encoding="utf-8")

        self.log.info(f"start.bat written  → {bat_path}")
        self.log.info(f"start.ps1 written  → {ps1_path}")

    # ==================================================================
    # STEP 9 — Agent Skills & Workflows
    # ==================================================================
    def _step_agent_skills(self):
        agent_dir = self.root / ".agent"
        if not agent_dir.exists():
            self.log.warn(".agent/ directory missing — Nex Agent skills will not load.")
            return

        # Count skills
        skills_dir = agent_dir / "skills"
        skill_count = 0
        if skills_dir.exists():
            skill_count = sum(1 for d in skills_dir.iterdir() if d.is_dir())
            self.log.info(f"Skills directory   : {skill_count} skills found.")
        else:
            self.log.warn("No .agent/skills directory found.")

        # Verify START workflow
        workflow_file = agent_dir / "workflows" / "START.md"
        if workflow_file.exists():
            self.log.info("START.md workflow  : present ✓")
        else:
            self.log.warn("START.md workflow missing. /START slash command will not function.")

        # SOUL.md
        soul = self.nex_agent_dir / "SOUL.md"
        if soul.exists():
            self.log.info("SOUL.md            : present ✓")
        else:
            self.log.warn("nex_agent/SOUL.md missing — agent persona will be generic.")

    # ==================================================================
    # STEP 10 — Playwright Browsers
    # ==================================================================
    def _step_playwright(self):
        if self.args.skip_playwright:
            self.log.warn("--skip-playwright flag set — skipping browser install.")
            return

        if not self.venv_py.exists():
            self.log.warn("No venv Python — skipping Playwright install.")
            return

        py = str(self.venv_py)

        # Check playwright package is importable first
        ok, _, _ = run([py, "-c", "import playwright; print('ok')"], timeout=15)
        if not ok:
            self.log.warn("playwright package not installed — browser install skipped.")
            return

        self.log.detail("Downloading Chromium for Nexearch scraping (~200 MB)…")
        ok, out, err = run(
            [py, "-m", "playwright", "install", "chromium"],
            cwd=str(self.root),
            timeout=600,
        )
        if ok:
            self.log.success("Playwright Chromium browser installed.")
        else:
            self.log.warn(
                "Playwright browser install failed. "
                "Nexearch scraping features require Chromium. "
                "Manually run: python -m playwright install chromium"
            )
            self.log._write(f"\n[PLAYWRIGHT STDERR]\n{err}\n")

    # ==================================================================
    # STEP 11 — Font Assets
    # ==================================================================
    def _step_fonts(self):
        fonts_dir = self.backend_dir / "fonts"
        if not fonts_dir.exists():
            self.log.warn(
                "backend/fonts/ directory not found. "
                "Caption styles that use custom fonts will fall back to system fonts."
            )
            return

        # Expected font families used by the caption renderer
        expected = ["Montserrat", "PlayfairDisplay", "NunitoSans", "Inter", "Roboto"]
        found: list[str] = []

        for ttf in fonts_dir.rglob("*.ttf"):
            for family in expected:
                if family.lower() in ttf.name.lower() and family not in found:
                    found.append(family)

        if set(expected).issubset(set(found)):
            self.log.success(f"All {len(expected)} font families verified.")
        else:
            missing = sorted(set(expected) - set(found))
            self.log.warn(
                f"Font families missing: {', '.join(missing)}. "
                "Caption styles requiring these fonts will use system fallbacks."
            )
            self.log.info(f"Font families found: {', '.join(found) or 'none'}")

    # ==================================================================
    # STEP 12 — Module Import Checks
    # ==================================================================
    def _step_import_checks(self):
        if not self.venv_py.exists():
            self.log.warn("No venv Python — skipping import checks.")
            return

        py = str(self.venv_py)

        checks = [
            # (description, python expression)
            ("FastAPI config",        "from app.core.config import get_settings; s=get_settings(); print(f'APP_NAME={s.APP_NAME}')"),
            ("SQLAlchemy engine",     "from app.db.database import init_db; print('db ok')"),
            ("Caption style registry","from app.captions.style_registry import get_all_styles; print(f'{len(get_all_styles())} styles')"),
            ("Nexearch config",       "import sys; sys.path.insert(0, '..'); from nexearch.config import get_nexearch_settings; print('nexearch config ok')"),
            ("Nexearch client store", "import sys; sys.path.insert(0, '..'); from nexearch.data.client_store import ClientDataStore; print('client_store ok')"),
            ("Arc Agent router",      "import sys; sys.path.insert(0, '..'); from nexearch.arc.api import router; print(f'{len(router.routes)} routes registered')"),
            ("Nex Agent LLM",         "import sys; sys.path.insert(0, '..'); from nex_agent.llm_provider import LLMProvider; print('llm_provider ok')"),
        ]

        passed = 0
        failed = []
        for label, expr in checks:
            full_cmd = f"import sys; sys.path.insert(0, '.'); {expr}"
            ok, out, err = run([py, "-c", full_cmd], cwd=str(self.backend_dir), timeout=30)
            if ok:
                result = out.strip().split("\n")[-1]  # last line
                self.log.info(f"✓  {label:<32}  {result}")
                passed += 1
            else:
                problem = (err or "unknown error").strip().split("\n")[-1][:100]
                self.log.warn(f"✗  {label:<32}  {problem}")
                failed.append(label)

        if not failed:
            self.log.success(f"All {passed} module checks passed.")
        else:
            self.log.warn(
                f"{passed}/{passed+len(failed)} checks passed. "
                f"Failed: {', '.join(failed)}"
            )

    # ==================================================================
    # STEP 13 — Final Validation
    # ==================================================================
    def _step_final_validation(self):
        """Cross-check that the expected critical files are in place."""
        critical_files = [
            # Backend
            self.backend_dir / "app" / "main.py",
            self.backend_dir / "app" / "core" / "config.py",
            self.backend_dir / "app" / "db" / "database.py",
            self.backend_dir / "app" / "admin" / "routes.py",
            self.backend_dir / "app" / "captions" / "style_registry.py",
            self.backend_dir / "requirements.txt",
            self.env_file,
            # Nex Agent
            self.nex_agent_dir / "server.py",
            self.nex_agent_dir / "core.py",
            self.nex_agent_dir / "llm_provider.py",
            self.nex_agent_dir / "SOUL.md",
            # Nexearch
            self.nexearch_dir / "main.py",
            self.nexearch_dir / "config.py",
            self.nexearch_dir / "data" / "client_store.py",
            # Arc Agent
            self.nexearch_dir / "arc" / "api.py",
            self.nexearch_dir / "arc" / "server.py",
            self.nexearch_dir / "arc" / "core.py",
            # Frontend
            self.frontend_dir / "package.json",
            self.frontend_dir / "src" / "app" / "dashboard" / "nexearch" / "clients" / "page.tsx",
            self.frontend_dir / "src" / "app" / "dashboard" / "nexearch" / "client-intelligence" / "page.tsx",
        ]

        missing = [f for f in critical_files if not f.exists()]
        present = len(critical_files) - len(missing)

        self.log.info(f"Critical file check: {present}/{len(critical_files)} files present.")
        for f in missing:
            self.log.error(f"Missing: {f.relative_to(self.root)}")

        # Caption renderers
        renderers_dir = self.backend_dir / "app" / "captions" / "renderers"
        if renderers_dir.exists():
            py_files = [f for f in renderers_dir.glob("*.py") if not f.name.startswith("__")]
            self.log.info(f"Caption renderers  : {len(py_files)} found (expected ≥ 15).")
        else:
            self.log.warn("Caption renderers directory not found.")

        # Database
        db = self.backend_dir / "nexclip.db"
        if db.exists():
            self.log.info(f"nexclip.db         : {db.stat().st_size / 1024:.0f} KB")
        else:
            self.log.warn("nexclip.db not yet created (created automatically at first boot).")

        # nexearch_data
        nd = self.root / "nexearch_data" / "clients"
        if nd.exists():
            client_dirs = [d for d in nd.iterdir() if d.is_dir()]
            self.log.info(f"nexearch_data      : {len(client_dirs)} client(s) stored.")
        else:
            self.log.warn("nexearch_data/clients/ directory not found.")

    # ==================================================================
    # SUMMARY
    # ==================================================================
    def _print_summary(self):
        self.log.header("Setup Complete — Summary")

        print(f"  📂  Installation  : {self.root}")
        print(f"  📋  Setup log     : {self.log.log_path}")
        print()

        if self.log.errors:
            print(f"  ❌  {len(self.log.errors)} Error(s) — review before starting:")
            for e in self.log.errors[:15]:
                print(f"       • {e}")
            print()
        if self.log.warnings:
            print(f"  ⚠️   {len(self.log.warnings)} Warning(s):")
            for w in self.log.warnings[:10]:
                print(f"       • {w}")
            if len(self.log.warnings) > 10:
                print(f"       … and {len(self.log.warnings) - 10} more (see setup_log.txt)")
            print()

        if not self.log.errors:
            self.log.success("NexClip is ready to launch!")
        else:
            print("  ⚠️   Setup finished with errors.")
            print("       Fix the items above then re-run `python setup.py`.")

        print()
        print("  -- How to Start ------------------------------------------")
        if self.is_windows:
            print("   Option A:  Double-click     start.bat")
            print("   Option B:  In PowerShell →  .\\start.ps1")
        else:
            print("   Run:       bash start.sh")
        print()
        print("  -- Service URLs ------------------------------------------")
        print("   Frontend       →  http://localhost:3000")
        print("   Backend API    →  http://localhost:8000  (Swagger: /docs)")
        print("   Nex Agent      →  http://localhost:8001")
        print("   Nexearch       →  http://localhost:8002")
        print("   Arc Agent      →  http://localhost:8003")
        print()
        print("  -- Next Steps --------------------------------------------")
        print("   1. Fill in API keys in backend/.env")
        print("   2. Start Redis or Memurai (for Celery task queue)")
        print("   3. Run the start script above")
        print("   4. Open http://localhost:3000")
        print()

        # Persist summary to log
        self.log._write(
            f"\n{'=' * 72}\n"
            f"SETUP SUMMARY\n"
            f"Errors   : {len(self.log.errors)}\n"
            f"Warnings : {len(self.log.warnings)}\n"
            f"Status   : {'READY' if not self.log.errors else 'NEEDS ATTENTION'}\n"
            f"{'=' * 72}\n"
        )


# ==========================================================================
# ARGUMENT PARSER & ENTRY POINT
# ==========================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NexClip — Full System Setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python setup.py                       Full install\n"
            "  python setup.py --check               Prerequisites check only\n"
            "  python setup.py --skip-playwright     Skip Chromium download\n"
            "  python setup.py --skip-frontend       Skip npm install\n"
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run prerequisite checks only, then exit.",
    )
    parser.add_argument(
        "--skip-playwright",
        action="store_true",
        help="Skip Playwright browser download (saves ~200 MB).",
    )
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Skip npm install for the Next.js frontend.",
    )
    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    try:
        setup = NexClipSetup(args)

        if args.check:
            # Run prerequisites check only
            log = setup.log
            log.header("NexClip — Prerequisites Check")
            log.step(1, 1, "Checking System Prerequisites")
            setup._step_prerequisites()
            log._print_summary = lambda: None  # suppress full summary
            print()
            if not log.errors:
                print("  ✅  All prerequisites satisfied. Run `python setup.py` for full install.")
            else:
                print("  ❌  Fix the errors above then re-run.")
            sys.exit(0 if not log.errors else 1)

        setup.run()
        sys.exit(0 if not setup.log.errors else 1)

    except KeyboardInterrupt:
        print("\n\n  ⚠️   Setup cancelled by user (Ctrl+C).")
        sys.exit(130)
    except Exception as exc:
        print(f"\n  ❌  Fatal setup error: {exc}")
        traceback.print_exc()
        sys.exit(1)
