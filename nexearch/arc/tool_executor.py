"""
Arc Agent — Tool Executor
============================
Manages tool registration, discovery, and execution.
All tools are callable by the conversation engine via function calling.
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("arc_agent.tool_executor")


class ToolDefinition:
    """A registered tool."""

    def __init__(self, name: str, description: str, category: str,
                 handler: Callable, parameters: Dict[str, Any]) -> None:
        self.name = name
        self.description = description
        self.category = category
        self.handler = handler
        self.parameters = parameters
        self.call_count = 0
        self.total_time_ms = 0
        self.last_error: Optional[str] = None

    def to_openai_function(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": self.parameters,
            "call_count": self.call_count,
            "avg_time_ms": round(self.total_time_ms / max(self.call_count, 1)),
        }


class ArcToolExecutor:
    """
    Tool registration, discovery, and execution engine for Arc Agent.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._categories: Dict[str, int] = {}

    def register(self, name: str, description: str, category: str,
                  handler: Callable, parameters: Dict[str, Any]) -> None:
        """Register a tool."""
        self._tools[name] = ToolDefinition(name, description, category, handler, parameters)
        self._categories[category] = self._categories.get(category, 0) + 1

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with arguments."""
        tool = self._tools.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}", "available": list(self._tools.keys())}

        start = time.time()
        try:
            result = tool.handler(**arguments)
            elapsed = int((time.time() - start) * 1000)
            tool.call_count += 1
            tool.total_time_ms += elapsed
            logger.info(f"Tool '{tool_name}' executed in {elapsed}ms")

            if isinstance(result, dict):
                return result
            return {"result": result}

        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            tool.last_error = str(e)
            logger.error(f"Tool '{tool_name}' failed ({elapsed}ms): {e}")
            return {
                "error": str(e),
                "tool": tool_name,
                "traceback": traceback.format_exc()[-500:],
            }

    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Get all tools in OpenAI function calling format."""
        return [t.to_openai_function() for t in self._tools.values()]

    def get_tool_count(self) -> int:
        return len(self._tools)

    def get_tool_categories(self) -> Dict[str, int]:
        return dict(self._categories)

    def get_tool_names(self) -> List[str]:
        return list(self._tools.keys())

    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        tool = self._tools.get(name)
        return tool.to_dict() if tool else None

    def get_all_tools(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._tools.values()]

    def search_tools(self, query: str) -> List[Dict[str, Any]]:
        """Search tools by name or description."""
        q = query.lower()
        return [
            t.to_dict() for t in self._tools.values()
            if q in t.name.lower() or q in t.description.lower()
        ]
