"""
Nex Agent — File Operator
============================
Safe read/write/edit operations on the NexClip codebase.
All operations validate paths stay within the project root.
All mutations are logged to Nex Agent's memory.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger("nex_agent.file_operator")


class FileOperator:
    """
    Safe file system operations for Nex Agent.
    All paths are validated to stay within the project root.
    """

    def __init__(self, project_root: str) -> None:
        self.root = Path(project_root).resolve()
        self._backup_dir = Path(__file__).resolve().parent / "nex_agent_memory" / "backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def _validate_path(self, path: str) -> Path:
        """Resolve and validate a path is within the project root."""
        resolved = (self.root / path).resolve()
        if not str(resolved).startswith(str(self.root)):
            raise PermissionError(f"Path traversal blocked: {path}")
        return resolved

    def read_file(self, path: str) -> Dict[str, Any]:
        """Read a file and return its contents with metadata."""
        resolved = self._validate_path(path)
        if not resolved.exists():
            return {"error": f"File not found: {path}", "exists": False}
        if not resolved.is_file():
            return {"error": f"Not a file: {path}", "exists": True}

        try:
            content = resolved.read_text(encoding="utf-8", errors="replace")
            stat = resolved.stat()
            return {
                "path": str(resolved.relative_to(self.root)),
                "content": content,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "line_count": content.count("\n") + 1,
                "exists": True,
            }
        except Exception as e:
            return {"error": str(e), "path": path, "exists": True}

    def write_file(self, path: str, content: str, create_dirs: bool = True) -> Dict[str, Any]:
        """Write content to a file (creates or overwrites)."""
        resolved = self._validate_path(path)

        # Backup existing file
        if resolved.exists():
            self._backup(resolved)

        if create_dirs:
            resolved.parent.mkdir(parents=True, exist_ok=True)

        try:
            resolved.write_text(content, encoding="utf-8")
            logger.info(f"File written: {path} ({len(content)} bytes)")
            return {
                "path": str(resolved.relative_to(self.root)),
                "bytes_written": len(content),
                "created": not resolved.exists(),
            }
        except Exception as e:
            return {"error": str(e)}

    def edit_file(self, path: str, target: str, replacement: str) -> Dict[str, Any]:
        """Replace a target string in a file."""
        resolved = self._validate_path(path)
        if not resolved.exists():
            return {"error": f"File not found: {path}"}

        try:
            content = resolved.read_text(encoding="utf-8")
            if target not in content:
                return {"error": f"Target string not found in {path}", "target": target[:100]}

            # Backup
            self._backup(resolved)

            count = content.count(target)
            new_content = content.replace(target, replacement)
            resolved.write_text(new_content, encoding="utf-8")

            logger.info(f"File edited: {path} ({count} replacement(s))")
            return {
                "path": str(resolved.relative_to(self.root)),
                "replacements": count,
                "before_size": len(content),
                "after_size": len(new_content),
            }
        except Exception as e:
            return {"error": str(e)}

    def create_file(self, path: str, content: str = "") -> Dict[str, Any]:
        """Create a new file (fails if it already exists)."""
        resolved = self._validate_path(path)
        if resolved.exists():
            return {"error": f"File already exists: {path}"}

        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        logger.info(f"File created: {path}")
        return {"path": str(resolved.relative_to(self.root)), "created": True}

    def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete a file (with backup)."""
        resolved = self._validate_path(path)
        if not resolved.exists():
            return {"error": f"File not found: {path}"}

        # Never delete critical files
        protected = [".env", "main.py", "package.json", "allowed_users.json"]
        if resolved.name in protected:
            return {"error": f"Cannot delete protected file: {resolved.name}"}

        self._backup(resolved)
        resolved.unlink()
        logger.info(f"File deleted: {path}")
        return {"path": str(resolved.relative_to(self.root)), "deleted": True}

    def list_directory(self, path: str = ".") -> Dict[str, Any]:
        """List contents of a directory."""
        resolved = self._validate_path(path)
        if not resolved.exists():
            return {"error": f"Directory not found: {path}"}
        if not resolved.is_dir():
            return {"error": f"Not a directory: {path}"}

        items = []
        try:
            for item in sorted(resolved.iterdir()):
                if item.name.startswith(".") or item.name in ("__pycache__", "node_modules", ".next", "venv"):
                    continue
                items.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else None,
                })
        except Exception as e:
            return {"error": str(e)}

        return {
            "path": str(resolved.relative_to(self.root)),
            "items": items,
            "count": len(items),
        }

    def search_files(self, query: str, extensions: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search for files by name pattern."""
        results = []
        skip_dirs = {"__pycache__", "node_modules", ".next", "venv", ".git", ".venv"}

        for root_dir, dirs, files in os.walk(str(self.root)):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
            for filename in files:
                if query.lower() in filename.lower():
                    if extensions and not any(filename.endswith(ext) for ext in extensions):
                        continue
                    filepath = Path(root_dir) / filename
                    results.append({
                        "path": str(filepath.relative_to(self.root)),
                        "name": filename,
                        "size": filepath.stat().st_size,
                    })
                    if len(results) >= 20:
                        return results
        return results

    def _backup(self, filepath: Path) -> None:
        """Create a timestamped backup of a file."""
        try:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{filepath.stem}_{ts}{filepath.suffix}"
            backup_path = self._backup_dir / backup_name
            shutil.copy2(str(filepath), str(backup_path))
        except Exception as e:
            logger.debug(f"Backup failed for {filepath}: {e}")
