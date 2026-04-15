"""
Nex Agent — Self Expander
============================
Runtime capability creation: new tools, skills, and workflows on demand.
"""

from __future__ import annotations

import ast
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("nex_agent.self_expander")

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)


class SelfExpander:
    """Enables Nex Agent to create new capabilities at runtime."""

    def __init__(self, tool_executor=None) -> None:
        self._executor = tool_executor
        self._custom_tools_dir = os.path.join(PROJECT_ROOT, "nex_agent", "tools", "custom")
        os.makedirs(self._custom_tools_dir, exist_ok=True)

    def create_tool(self, name: str, description: str, code: str, category: str = "custom") -> Dict[str, Any]:
        """Create and register a new tool from Python code."""
        # Validate syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            return {"created": False, "error": f"Syntax error: {e}"}

        # Write file
        tool_file = os.path.join(self._custom_tools_dir, f"{name}.py")
        Path(tool_file).write_text(code, encoding="utf-8")

        # Try to register
        try:
            namespace: Dict[str, Any] = {}
            exec(code, namespace)
            handler = namespace.get(name) or namespace.get(f"_{name}")

            if handler and callable(handler) and self._executor:
                self._executor.register(
                    name=name, description=description,
                    category=category, handler=handler,
                    parameters={"type": "object", "properties": {}},
                )
                return {"created": True, "registered": True, "file": tool_file}
            return {"created": True, "registered": False, "error": "No callable found"}
        except Exception as e:
            return {"created": True, "registered": False, "error": str(e)}

    def create_skill(self, name: str, description: str, content: str) -> Dict[str, Any]:
        """Create a new skill in .agent/skills/."""
        skill_dir = os.path.join(PROJECT_ROOT, ".agent", "skills", name)
        os.makedirs(skill_dir, exist_ok=True)
        skill_md = os.path.join(skill_dir, "SKILL.md")
        full = f"---\nname: {name}\ndescription: {description}\n---\n\n{content}"
        Path(skill_md).write_text(full, encoding="utf-8")
        return {"created": True, "path": skill_md}

    def create_workflow(self, name: str, description: str, steps: str) -> Dict[str, Any]:
        """Create a new workflow in .agent/workflows/."""
        wf_dir = os.path.join(PROJECT_ROOT, ".agent", "workflows")
        os.makedirs(wf_dir, exist_ok=True)
        wf_path = os.path.join(wf_dir, f"{name}.md")
        content = f"---\ndescription: {description}\n---\n\n{steps}"
        Path(wf_path).write_text(content, encoding="utf-8")
        return {"created": True, "path": wf_path}
