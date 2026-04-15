"""
Arc Agent — Self-Expander
============================
Runtime tool creation engine. Arc Agent can create custom tools,
skills, and sub-agents for itself when it encounters tasks
it cannot handle with existing capabilities.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


class ArcSelfExpander:
    """
    Allows Arc Agent to create custom tools at runtime.
    Tools are Python functions generated via LLM and dynamically loaded.
    """

    def __init__(self, tool_executor, memory_path: Optional[str] = None) -> None:
        self.tool_executor = tool_executor
        default_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "arc_agent_memory", "custom_tools"
        )
        self._custom_tools_dir = Path(memory_path or default_path)
        self._custom_tools_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self._custom_tools_dir / "manifest.json"
        self._loaded_tools: List[str] = []

    def create_tool(self, name: str, description: str,
                     code: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a custom tool from LLM-generated Python code.
        The code must define a function with the same name as the tool.
        """
        tool_id = f"custom_{name}_{uuid.uuid4().hex[:6]}"
        tool_file = self._custom_tools_dir / f"{tool_id}.py"

        # Save the tool code
        tool_file.write_text(code, encoding="utf-8")

        # Load and register the tool
        try:
            namespace = {}
            exec(compile(code, str(tool_file), "exec"), namespace)

            handler = namespace.get(name)
            if not handler or not callable(handler):
                return {"success": False, "error": f"Function '{name}' not found in code"}

            self.tool_executor.register(
                name=tool_id,
                description=f"[Custom] {description}",
                category="custom",
                handler=handler,
                parameters=parameters,
            )
            self._loaded_tools.append(tool_id)

            # Update manifest
            self._update_manifest(tool_id, name, description, str(tool_file))

            logger.info(f"Custom tool created: {tool_id}")
            return {"success": True, "tool_id": tool_id, "name": name}

        except Exception as e:
            tool_file.unlink(missing_ok=True)
            return {"success": False, "error": str(e)}

    def list_custom_tools(self) -> List[Dict[str, Any]]:
        """List all custom tools."""
        manifest = self._load_manifest()
        return manifest.get("tools", [])

    def remove_tool(self, tool_id: str) -> Dict[str, Any]:
        """Remove a custom tool."""
        manifest = self._load_manifest()
        tools = manifest.get("tools", [])
        manifest["tools"] = [t for t in tools if t["tool_id"] != tool_id]
        self._save_manifest(manifest)

        tool_file = self._custom_tools_dir / f"{tool_id}.py"
        tool_file.unlink(missing_ok=True)

        return {"success": True, "removed": tool_id}

    def load_all_custom_tools(self) -> int:
        """Load all previously created custom tools on startup."""
        manifest = self._load_manifest()
        loaded = 0
        for tool_info in manifest.get("tools", []):
            try:
                tool_file = Path(tool_info["file_path"])
                if tool_file.exists():
                    code = tool_file.read_text(encoding="utf-8")
                    namespace = {}
                    exec(compile(code, str(tool_file), "exec"), namespace)
                    handler = namespace.get(tool_info["original_name"])
                    if handler and callable(handler):
                        self.tool_executor.register(
                            name=tool_info["tool_id"],
                            description=f"[Custom] {tool_info['description']}",
                            category="custom",
                            handler=handler,
                            parameters=tool_info.get("parameters", {}),
                        )
                        loaded += 1
            except Exception as e:
                logger.warning(f"Failed to load custom tool {tool_info.get('tool_id')}: {e}")
        return loaded

    def _update_manifest(self, tool_id: str, name: str,
                          description: str, file_path: str) -> None:
        manifest = self._load_manifest()
        manifest.setdefault("tools", []).append({
            "tool_id": tool_id,
            "original_name": name,
            "description": description,
            "file_path": file_path,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save_manifest(manifest)

    def _load_manifest(self) -> Dict:
        if self._manifest_path.exists():
            with open(self._manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"tools": []}

    def _save_manifest(self, manifest: Dict) -> None:
        with open(self._manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)
