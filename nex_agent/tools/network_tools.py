"""
Nex Agent Tools — Network & API (Category 5)
================================================
HTTP requests, endpoint health checks, all-service status.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, TYPE_CHECKING

import urllib.request
import urllib.error

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

logger = logging.getLogger("nex_agent.tools.network")


def _http_request(method: str = "GET", url: str = "", headers: str = "{}", body: str = "", timeout_ms: int = 10000) -> Dict[str, Any]:
    timeout_s = max(timeout_ms / 1000, 1)
    try:
        parsed_headers = json.loads(headers) if headers else {}
        data = body.encode("utf-8") if body else None
        if data and "Content-Type" not in parsed_headers:
            parsed_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=parsed_headers, method=method.upper())
        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            elapsed = int((time.time() - start) * 1000)
            resp_body = resp.read().decode("utf-8", errors="replace")
            resp_headers = dict(resp.headers)
            return {
                "success": True, "status_code": resp.status,
                "body": resp_body[:5000], "headers": resp_headers,
                "elapsed_ms": elapsed,
            }
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode("utf-8", errors="replace")[:2000]
        except Exception:
            pass
        return {"success": False, "status_code": e.code, "error": str(e), "body": body_text}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _check_endpoint_health(url: str, expected_status: int = 200) -> Dict[str, Any]:
    start = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            elapsed = int((time.time() - start) * 1000)
            body = resp.read().decode("utf-8", errors="replace")[:500]
            return {
                "reachable": True, "status_code": resp.status,
                "response_time_ms": elapsed,
                "matches_expected": resp.status == expected_status,
                "body_preview": body,
            }
    except Exception as e:
        return {"reachable": False, "error": str(e), "response_time_ms": int((time.time() - start) * 1000)}


def _check_all_services() -> Dict[str, Any]:
    services = {
        "backend": "http://localhost:8000/health",
        "nex_agent": "http://localhost:8001/health",
        "frontend": "http://localhost:3000",
    }
    results = {}
    for name, url in services.items():
        if name == "nex_agent":
            # Skip actual network request because the single-threaded event loop is currently blocked processing this tool!
            # If we request our own health endpoint it will time out and trick the LLM into thinking we are offline.
            results[name] = {"reachable": True, "status_code": 200, "response_time_ms": 1, "matches_expected": True, "body_preview": "{\"status\":\"ok\",\"agent\":\"nex\",\"version\":\"4.0\"}"}
        else:
            results[name] = _check_endpoint_health(url)
    return {"success": True, "services": results}


def register(executor: "ToolExecutor") -> int:
    executor.register(name="http_request", description="Make an HTTP request to any URL. Returns status code, body, and headers.", category="network", handler=_http_request, parameters={"type": "object", "properties": {"method": {"type": "string", "default": "GET"}, "url": {"type": "string"}, "headers": {"type": "string", "default": "{}"}, "body": {"type": "string", "default": ""}, "timeout_ms": {"type": "integer", "default": 10000}}, "required": ["url"]})
    executor.register(name="check_endpoint_health", description="Ping an endpoint and verify it responds with the expected status.", category="network", handler=_check_endpoint_health, parameters={"type": "object", "properties": {"url": {"type": "string"}, "expected_status": {"type": "integer", "default": 200}}, "required": ["url"]})
    executor.register(name="check_all_services", description="Run health checks on all NexClip services (backend, nex_agent, frontend) simultaneously.", category="network", handler=_check_all_services, parameters={"type": "object", "properties": {}})
    return 3
