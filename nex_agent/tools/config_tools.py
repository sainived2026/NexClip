"""
Nex Agent Tools — Environment & Config (Category 9)
=======================================================
Read and modify .env files, get resolved NexClip config.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

logger = logging.getLogger("nex_agent.tools.config")

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)

SENSITIVE_KEYS = {"API_KEY", "SECRET", "PASSWORD", "TOKEN", "CREDENTIAL"}


def _is_sensitive(key: str) -> bool:
    return any(s in key.upper() for s in SENSITIVE_KEYS)


def _read_env(file_path: str = "backend/.env") -> Dict[str, Any]:
    abs_path = os.path.join(PROJECT_ROOT, file_path) if not os.path.isabs(file_path) else file_path
    if not os.path.exists(abs_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    try:
        envs = []
        for line in Path(abs_path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            is_sensitive = _is_sensitive(key)
            envs.append({
                "key": key,
                "value_preview": f"{value[:4]}...{value[-4:]}" if is_sensitive and len(value) > 8 else ("****" if is_sensitive else value),
                "is_sensitive": is_sensitive,
            })
        return {"success": True, "vars": envs, "count": len(envs)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _set_env_var(file_path: str = "backend/.env", key: str = "", value: str = "") -> Dict[str, Any]:
    abs_path = os.path.join(PROJECT_ROOT, file_path) if not os.path.isabs(file_path) else file_path
    if not os.path.exists(abs_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    try:
        content = Path(abs_path).read_text(encoding="utf-8")
        lines = content.splitlines()
        found = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in stripped:
                continue
            k, _, _ = stripped.partition("=")
            if k.strip() == key:
                lines[i] = f"{key}={value}"
                found = True
                break

        if not found:
            lines.append(f"{key}={value}")

        Path(abs_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"success": True, "was_existing": found, "key": key}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_nexclip_config() -> Dict[str, Any]:
    """Return the complete resolved config from backend/.env."""
    result = _read_env("backend/.env")
    if not result.get("success"):
        return result

    config = {}
    for v in result["vars"]:
        config[v["key"]] = v["value_preview"]

    return {
        "success": True,
        "config": config,
        "services": {
            "backend": {"port": 8000, "url": "http://localhost:8000"},
            "nex_agent": {"port": 8001, "url": "http://localhost:8001"},
            "frontend": {"port": 3000, "url": "http://localhost:3000"},
        },
    }


def register(executor: "ToolExecutor") -> int:
    executor.register(name="read_env", description="Read a .env file and return all key-value pairs (sensitive values are redacted).", category="config", handler=_read_env, parameters={"type": "object", "properties": {"file_path": {"type": "string", "default": "backend/.env"}}, "required": []})
    executor.register(name="set_env_var", description="Add or update a variable in a .env file.", category="config", handler=_set_env_var, danger_level="moderate", parameters={"type": "object", "properties": {"file_path": {"type": "string", "default": "backend/.env"}, "key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]})
    executor.register(name="get_nexclip_config", description="Get the complete resolved NexClip configuration including all services and ports.", category="config", handler=_get_nexclip_config, parameters={"type": "object", "properties": {}})
    return 3
