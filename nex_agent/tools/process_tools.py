"""
Nex Agent Tools — Process Management (Category 1)
=====================================================
Start, stop, restart, health-check, and log-read for all NexClip services.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

logger = logging.getLogger("nex_agent.tools.process")

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)

# ── Service definitions ─────────────────────────────────────────

SERVICE_DEFS = {
    "backend": {
        "cmd": ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        "cwd": os.path.join(PROJECT_ROOT, "backend"),
        "health_url": "http://localhost:8000/health",
        "port": 8000,
    },
    "nex_agent": {
        "cmd": ["python", "-m", "nex_agent.server"],
        "cwd": PROJECT_ROOT,
        "health_url": "http://localhost:8001/health",
        "port": 8001,
    },

    "frontend": {
        "cmd": ["npm", "run", "dev"],
        "cwd": os.path.join(PROJECT_ROOT, "frontend"),
        "health_url": "http://localhost:3000",
        "port": 3000,
    },
}

_running_processes: Dict[str, subprocess.Popen] = {}


# ── Tool implementations ────────────────────────────────────────

def _start_process(service: str, wait_for_health: bool = True, timeout_seconds: int = 30) -> Dict[str, Any]:
    """Actually start a NexClip service via subprocess."""
    svc = SERVICE_DEFS.get(service)
    if not svc:
        return {"success": False, "error": f"Unknown service: {service}. Valid: {list(SERVICE_DEFS.keys())}"}

    # Check if already running
    health = _check_health(svc["health_url"])
    if health["online"]:
        return {
            "success": True, "already_running": True,
            "message": f"{service} is already running on port {svc['port']}",
            "pid": health.get("pid"), "health_confirmed": True,
        }

    try:
        env = os.environ.copy()
        proc = subprocess.Popen(
            svc["cmd"], cwd=svc["cwd"], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        _running_processes[service] = proc

        if wait_for_health:
            start_time = time.time()
            while time.time() - start_time < timeout_seconds:
                time.sleep(2)
                health = _check_health(svc["health_url"])
                if health["online"]:
                    elapsed = int((time.time() - start_time) * 1000)
                    return {
                        "success": True, "pid": proc.pid,
                        "health_confirmed": True, "elapsed_ms": elapsed,
                        "message": f"{service} started on port {svc['port']} (PID {proc.pid})",
                    }
                if proc.poll() is not None:
                    stdout = proc.stdout.read() if proc.stdout else ""
                    return {
                        "success": False,
                        "error": f"{service} process exited with code {proc.returncode}",
                        "startup_log": stdout[:2000],
                    }

            return {
                "success": False,
                "error": f"{service} started (PID {proc.pid}) but health check failed after {timeout_seconds}s",
                "pid": proc.pid,
            }
        else:
            time.sleep(1)
            return {"success": True, "pid": proc.pid, "health_confirmed": False}

    except Exception as e:
        return {"success": False, "error": f"Failed to start {service}: {e}"}


def _stop_process(service: str, graceful: bool = True, timeout_ms: int = 10000) -> Dict[str, Any]:
    """Stop a NexClip service."""
    if service == "nex_agent":
        return {"success": False, "error": "Nex Agent cannot stop/restart itself autonomously. This would crash the active conversation. Use the Admin Panel UI to restart."}

    proc = _running_processes.get(service)
    if proc and proc.poll() is None:
        try:
            if graceful:
                proc.terminate()
                try:
                    proc.wait(timeout=timeout_ms / 1000)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            else:
                proc.kill()
                proc.wait(timeout=5)

            del _running_processes[service]
            return {"success": True, "exit_code": proc.returncode, "message": f"{service} stopped"}
        except Exception as e:
            return {"success": False, "error": f"Failed to stop {service}: {e}"}

    # Try to find the process by port
    svc = SERVICE_DEFS.get(service)
    if svc:
        port = svc["port"]
        try:
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    pid = line.strip().split()[-1]
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        return {"success": True, "exit_code": 0, "message": f"{service} (PID {pid}) killed"}
                    except (ProcessLookupError, PermissionError) as e:
                        return {"success": False, "error": f"Cannot kill PID {pid}: {e}"}
        except Exception:
            pass

    return {"success": False, "error": f"No running process found for {service}"}


def _restart_process(service: str) -> Dict[str, Any]:
    """Stop and start a service, returning downtime."""
    if service == "nex_agent":
        return {"success": False, "error": "Nex Agent cannot stop/restart itself autonomously. This would crash the active conversation. Use the Admin Panel UI to restart."}

    stop_result = _stop_process(service)
    time.sleep(1)
    start_time = time.time()
    start_result = _start_process(service, wait_for_health=True)
    downtime_ms = int((time.time() - start_time) * 1000)
    return {
        "success": start_result.get("success", False),
        "stop_result": stop_result,
        "start_result": start_result,
        "downtime_ms": downtime_ms,
    }


def _check_health(url: str, timeout: int = 5) -> Dict[str, Any]:
    """Ping a health endpoint."""
    import urllib.request
    import urllib.error
    try:
        start = time.time()
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = int((time.time() - start) * 1000)
            body = resp.read().decode("utf-8")[:500]
            return {"online": True, "status_code": resp.status, "response_time_ms": elapsed, "body_preview": body}
    except Exception as e:
        return {"online": False, "error": str(e), "response_time_ms": -1}


def _check_process_health(service: str) -> Dict[str, Any]:
    """Check if a specific service is healthy."""
    svc = SERVICE_DEFS.get(service)
    if not svc:
        return {"online": False, "error": f"Unknown service: {service}"}
    result = _check_health(svc["health_url"])
    result["service"] = service
    result["port"] = svc["port"]
    return result


def _get_process_logs(service: str, lines: int = 50, filter_level: str = "") -> Dict[str, Any]:
    """Get recent logs from a service."""
    log_files = {
        "backend": ["backend/ai_response_debug.log", "backend/yt_dlp_out.txt"],
        "nex_agent": [],
    }
    files = log_files.get(service, [])
    all_lines: List[str] = []
    for lf in files:
        path = os.path.join(PROJECT_ROOT, lf)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    file_lines = f.readlines()
                    tail = file_lines[-lines:] if len(file_lines) > lines else file_lines
                    for line in tail:
                        stripped = line.strip()
                        if stripped:
                            if filter_level and filter_level.upper() not in stripped.upper():
                                continue
                            all_lines.append(stripped[:300])
            except Exception:
                continue
    return {"logs": all_lines[-lines:], "total_lines": len(all_lines), "service": service}


def _list_running_processes() -> Dict[str, Any]:
    """Check all NexClip services and report status."""
    processes = []
    for name, svc in SERVICE_DEFS.items():
        if name == "nex_agent":
            # Skip actual network request because the event loop is blocked processing this tool
            health = {"online": True, "response_time_ms": 1}
        else:
            health = _check_health(svc["health_url"], timeout=3)
            
        processes.append({
            "name": name,
            "port": svc["port"],
            "online": health.get("online", False),
            "response_time_ms": health.get("response_time_ms", -1),
        })
    return {"processes": processes}


# ── Registration ────────────────────────────────────────────────

def register(executor: "ToolExecutor") -> int:
    executor.register(
        name="start_process", description="Start a NexClip service (backend, nex_agent, frontend). Waits for health confirmation before reporting success.",
        category="process", handler=_start_process, timeout_seconds=60,
        parameters={"type": "object", "properties": {"service": {"type": "string", "enum": ["backend", "nex_agent", "frontend"]}, "wait_for_health": {"type": "boolean", "default": True}, "timeout_seconds": {"type": "integer", "default": 30}}, "required": ["service"]},
    )
    executor.register(
        name="stop_process", description="Stop a NexClip service gracefully or forcefully.",
        category="process", handler=_stop_process, danger_level="moderate",
        parameters={"type": "object", "properties": {"service": {"type": "string", "enum": ["backend", "nex_agent", "frontend"]}, "graceful": {"type": "boolean", "default": True}, "timeout_ms": {"type": "integer", "default": 10000}}, "required": ["service"]},
    )
    executor.register(
        name="restart_process", description="Restart a NexClip service: stop, wait, start, verify health.",
        category="process", handler=_restart_process, timeout_seconds=60,
        parameters={"type": "object", "properties": {"service": {"type": "string", "enum": ["backend", "nex_agent", "frontend"]}}, "required": ["service"]},
    )
    executor.register(
        name="check_process_health", description="Check if a NexClip service is online by pinging its health endpoint.",
        category="process", handler=_check_process_health,
        parameters={"type": "object", "properties": {"service": {"type": "string", "enum": ["backend", "nex_agent", "frontend"]}}, "required": ["service"]},
    )
    executor.register(
        name="get_process_logs", description="Get recent log lines from a service.",
        category="process", handler=_get_process_logs,
        parameters={"type": "object", "properties": {"service": {"type": "string"}, "lines": {"type": "integer", "default": 50}, "filter_level": {"type": "string", "default": ""}}, "required": ["service"]},
    )
    executor.register(
        name="list_running_processes", description="List all NexClip services with their online/offline status and response times.",
        category="process", handler=_list_running_processes,
        parameters={"type": "object", "properties": {}},
    )
    return 6
