"""
Nex Agent — Workflow Manager
================================
CRUD for .agent/workflows/.
Can list, read, create, and execute workflows.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger("nex_agent.workflow_manager")


class WorkflowManager:
    """
    Manage workflow files in .agent/workflows/.
    """

    def __init__(self, project_root: str) -> None:
        self.root = Path(project_root).resolve()
        self.workflows_dir = self.root / ".agent" / "workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all workflow files with their descriptions."""
        workflows = []
        for f in sorted(self.workflows_dir.glob("*.md")):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                desc = self._extract_description(content)
                workflows.append({
                    "name": f.stem,
                    "filename": f.name,
                    "description": desc,
                    "path": str(f.relative_to(self.root)),
                })
            except Exception:
                continue
        return workflows

    def get_workflow(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a workflow by name."""
        filepath = self.workflows_dir / f"{name}.md"
        if not filepath.exists():
            # Try case-insensitive
            for f in self.workflows_dir.glob("*.md"):
                if f.stem.lower() == name.lower():
                    filepath = f
                    break
            else:
                return None

        content = filepath.read_text(encoding="utf-8", errors="replace")
        return {
            "name": filepath.stem,
            "filename": filepath.name,
            "description": self._extract_description(content),
            "content": content,
            "path": str(filepath.relative_to(self.root)),
        }

    def create_workflow(self, name: str, description: str, steps: str) -> Dict[str, Any]:
        """Create a new workflow file."""
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        filepath = self.workflows_dir / f"{safe_name}.md"

        content = f"---\ndescription: {description}\n---\n\n{steps}\n"

        if filepath.exists():
            return {"error": f"Workflow '{safe_name}' already exists"}

        filepath.write_text(content, encoding="utf-8")
        logger.info(f"Workflow created: {safe_name}")
        return {
            "name": safe_name,
            "filename": filepath.name,
            "description": description,
            "created": True,
        }

    def delete_workflow(self, name: str) -> Dict[str, Any]:
        """Delete a workflow file."""
        filepath = self.workflows_dir / f"{name}.md"
        if not filepath.exists():
            return {"error": f"Workflow '{name}' not found"}

        # Protect START.md
        if filepath.name.upper() == "START.MD":
            return {"error": "Cannot delete the START workflow"}

        filepath.unlink()
        logger.info(f"Workflow deleted: {name}")
        return {"deleted": True, "name": name}

    def _extract_description(self, content: str) -> str:
        """Extract description from YAML frontmatter."""
        match = re.search(r"^description:\s*(.+)$", content, re.MULTILINE)
        return match.group(1).strip() if match else ""
