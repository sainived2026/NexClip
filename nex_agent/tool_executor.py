"""
Nex Agent — Tool Executor
============================
Central engine for registering, validating, and executing all Nex Agent tools.
Every tool call is logged, timed, and verified before results are returned.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger("nex_agent.tool_executor")


# ── Data Structures ─────────────────────────────────────────────

@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    elapsed_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = {"success": self.success, "data": self.data, "elapsed_ms": self.elapsed_ms}
        if self.error:
            d["error"] = self.error
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass
class ToolDef:
    """Definition of a registered tool."""
    name: str
    description: str
    category: str
    parameters: Dict[str, Any]  # JSON Schema
    handler: Callable[..., Any]  # sync or async function
    is_async: bool = False
    timeout_seconds: int = 60
    danger_level: str = "safe"  # safe | moderate | destructive

    def to_llm_schema(self) -> Dict[str, Any]:
        """Export in OpenAI / Gemini function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolExecution:
    """Logged record of a tool execution."""
    tool_name: str
    params: Dict[str, Any]
    result: ToolResult
    timestamp: str
    elapsed_ms: int


# ── Tool Executor ───────────────────────────────────────────────

class ToolExecutor:
    """
    Manages registration, validation, and execution of all Nex Agent tools.
    All tool calls are logged, timed, and verified.
    """

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = project_root
        self.tools: Dict[str, ToolDef] = {}
        self.execution_log: List[ToolExecution] = []
        self._max_log_size = 500

    # ── Registration ────────────────────────────────────────────

    def register(
        self,
        name: str,
        description: str,
        category: str,
        parameters: Dict[str, Any],
        handler: Callable,
        is_async: bool = False,
        timeout_seconds: int = 60,
        danger_level: str = "safe",
    ) -> None:
        """Register a tool."""
        self.tools[name] = ToolDef(
            name=name,
            description=description,
            category=category,
            parameters=parameters,
            handler=handler,
            is_async=is_async,
            timeout_seconds=timeout_seconds,
            danger_level=danger_level,
        )

    # Alias: many tool modules use register_tool() instead of register()
    register_tool = register

    # ── Execution ───────────────────────────────────────────────

    def execute_sync(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """Execute a tool synchronously."""
        tool = self.tools.get(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found")

        start = time.time()
        try:
            if tool.is_async:
                # Run async handler in event loop
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        result_data = pool.submit(
                            asyncio.run, tool.handler(**params)
                        ).result(timeout=tool.timeout_seconds)
                else:
                    result_data = asyncio.run(tool.handler(**params))
            else:
                result_data = tool.handler(**params)

            elapsed = int((time.time() - start) * 1000)

            if isinstance(result_data, ToolResult):
                result_data.elapsed_ms = elapsed
                result = result_data
            elif isinstance(result_data, dict):
                result = ToolResult(success=True, data=result_data, elapsed_ms=elapsed)
            else:
                result = ToolResult(
                    success=True,
                    data={"result": result_data},
                    elapsed_ms=elapsed,
                )

        except TimeoutError:
            result = ToolResult(
                success=False,
                error=f"Tool '{tool_name}' timed out after {tool.timeout_seconds}s",
                elapsed_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            result = ToolResult(
                success=False,
                error=f"{type(e).__name__}: {str(e)}",
                elapsed_ms=int((time.time() - start) * 1000),
            )
            logger.error(f"Tool '{tool_name}' failed: {e}", exc_info=True)

        # Log execution
        self._log(tool_name, params, result)
        return result

    async def execute_async(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """Execute a tool asynchronously."""
        tool = self.tools.get(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found")

        start = time.time()
        try:
            if tool.is_async:
                result_data = await asyncio.wait_for(
                    tool.handler(**params),
                    timeout=tool.timeout_seconds,
                )
            else:
                loop = asyncio.get_running_loop()
                result_data = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: tool.handler(**params)),
                    timeout=tool.timeout_seconds,
                )

            elapsed = int((time.time() - start) * 1000)

            if isinstance(result_data, ToolResult):
                result_data.elapsed_ms = elapsed
                result = result_data
            elif isinstance(result_data, dict):
                result = ToolResult(success=True, data=result_data, elapsed_ms=elapsed)
            else:
                result = ToolResult(success=True, data={"result": result_data}, elapsed_ms=elapsed)

        except asyncio.TimeoutError:
            result = ToolResult(
                success=False,
                error=f"Tool '{tool_name}' timed out after {tool.timeout_seconds}s",
                elapsed_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            result = ToolResult(
                success=False,
                error=f"{type(e).__name__}: {str(e)}",
                elapsed_ms=int((time.time() - start) * 1000),
            )
            logger.error(f"Tool '{tool_name}' failed: {e}", exc_info=True)

        self._log(tool_name, params, result)
        return result

    # ── LLM Integration ─────────────────────────────────────────

    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Export all tools in OpenAI/Gemini function calling format."""
        return [t.to_llm_schema() for t in self.tools.values()]

    def get_tools_for_gemini(self) -> List[Dict[str, Any]]:
        """Export tools in Gemini-native format."""
        defs = []
        for t in self.tools.values():
            defs.append({
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            })
        return [{"function_declarations": defs}]

    def get_tool_names(self) -> List[str]:
        return list(self.tools.keys())

    def get_tool_count(self) -> int:
        return len(self.tools)

    def get_tool_categories(self) -> Dict[str, int]:
        cats: Dict[str, int] = {}
        for t in self.tools.values():
            cats[t.category] = cats.get(t.category, 0) + 1
        return cats

    # ── Logging ─────────────────────────────────────────────────

    def _log(self, tool_name: str, params: Dict[str, Any], result: ToolResult) -> None:
        entry = ToolExecution(
            tool_name=tool_name,
            params=params,
            result=result,
            timestamp=datetime.utcnow().isoformat(),
            elapsed_ms=result.elapsed_ms,
        )
        self.execution_log.append(entry)
        if len(self.execution_log) > self._max_log_size:
            self.execution_log = self.execution_log[-self._max_log_size:]

        status = "✓" if result.success else "✗"
        logger.info(
            f"  {status} {tool_name}({json.dumps(params, default=str)[:120]}) "
            f"→ {result.elapsed_ms}ms"
        )

    def get_recent_executions(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [
            {
                "tool": e.tool_name,
                "params": e.params,
                "success": e.result.success,
                "elapsed_ms": e.elapsed_ms,
                "timestamp": e.timestamp,
                "error": e.result.error,
            }
            for e in self.execution_log[-limit:]
        ]
