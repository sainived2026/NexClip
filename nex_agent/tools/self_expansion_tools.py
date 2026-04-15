"""
Nex Agent Tools — Self-Expansion (Category 10)
==================================================
Create new tools at runtime, self-diagnose, research solutions.
"""

from __future__ import annotations

import ast
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

logger = logging.getLogger("nex_agent.tools.self_expansion")

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)

# Reference set during registration
_executor_ref: "ToolExecutor | None" = None


def _create_new_tool(name: str, description: str, implementation_code: str, category: str = "custom") -> Dict[str, Any]:
    """Create a new tool at runtime from generated Python code."""
    # Validate syntax
    try:
        ast.parse(implementation_code)
    except SyntaxError as e:
        return {"created": False, "error": f"Syntax error in generated code: {e}"}

    # Write to a custom tools file
    custom_dir = os.path.join(PROJECT_ROOT, "nex_agent", "tools", "custom")
    os.makedirs(custom_dir, exist_ok=True)

    tool_file = os.path.join(custom_dir, f"{name}.py")
    try:
        Path(tool_file).write_text(implementation_code, encoding="utf-8")
    except Exception as e:
        return {"created": False, "error": f"Failed to write tool file: {e}"}

    # Try to load and register
    try:
        namespace: Dict[str, Any] = {}
        exec(implementation_code, namespace)

        handler = namespace.get(name) or namespace.get(f"_{name}")
        if handler and callable(handler):
            if _executor_ref:
                _executor_ref.register(
                    name=name, description=description,
                    category=category, handler=handler,
                    parameters={"type": "object", "properties": {}},
                )
            return {"created": True, "tool_name": name, "registered": True, "file": tool_file}
        else:
            return {"created": True, "tool_name": name, "registered": False, "error": f"No callable '{name}' found in code", "file": tool_file}
    except Exception as e:
        return {"created": True, "tool_name": name, "registered": False, "error": f"Registration failed: {e}", "file": tool_file}


def _self_diagnose() -> Dict[str, Any]:
    """Run a complete self-check on all tools and services."""
    if _executor_ref is None:
        return {"error": "Tool executor not available"}

    results = {
        "total_tools": _executor_ref.get_tool_count(),
        "tool_categories": _executor_ref.get_tool_categories(),
        "recent_executions": _executor_ref.get_recent_executions(10),
    }

    # Check all services
    try:
        service_health = _executor_ref.execute_sync("check_all_services", {})
        results["service_health"] = service_health.data
    except Exception as e:
        results["service_health"] = {"error": str(e)}

    # Check failed tools in recent executions
    failed = [e for e in results["recent_executions"] if not e.get("success")]
    results["failed_tools_recent"] = len(failed)
    results["healthy"] = len(failed) == 0

    return results


def _research_solution(problem_description: str) -> Dict[str, Any]:
    """Search the codebase and knowledge base for solutions."""
    if _executor_ref is None:
        return {"error": "Tool executor not available"}

    # Search codebase for relevant code
    search_result = _executor_ref.execute_sync("search_codebase", {
        "query": problem_description.split()[0] if problem_description.split() else "",
        "max_results": 10,
    })

    return {
        "relevant_files": search_result.data.get("matches", []) if search_result.success else [],
        "suggested_approach": f"Found {len(search_result.data.get('matches', []))} code matches related to: {problem_description[:100]}",
    }


def register(executor: "ToolExecutor") -> int:
    global _executor_ref
    _executor_ref = executor

    executor.register(name="create_new_tool", description="Create a new tool at runtime from Python code. Use when no existing tool can handle a task.", category="self_expansion", handler=_create_new_tool, danger_level="moderate", parameters={"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "implementation_code": {"type": "string"}, "category": {"type": "string", "default": "custom"}}, "required": ["name", "description", "implementation_code"]})
    executor.register(name="self_diagnose", description="Run a complete self-check: all tools, all services, recent execution history.", category="self_expansion", handler=_self_diagnose, parameters={"type": "object", "properties": {}})
    executor.register(name="research_solution", description="Search the codebase and knowledge base for solutions to a problem.", category="self_expansion", handler=_research_solution, parameters={"type": "object", "properties": {"problem_description": {"type": "string"}}, "required": ["problem_description"]})
    return 3
