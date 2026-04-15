"""
Nex Agent Tools — File System (Category 2)
==============================================
Read, write, edit, delete, list, search, and inspect files.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

logger = logging.getLogger("nex_agent.tools.filesystem")

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
TRASH_DIR = os.path.join(PROJECT_ROOT, ".trash")


def _resolve(path: str) -> str:
    """Resolve a relative path to absolute within project root."""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(PROJECT_ROOT, path))


def _safe_path(path: str) -> bool:
    """Ensure path is within project root (prevent traversal)."""
    resolved = os.path.realpath(_resolve(path))
    return resolved.startswith(os.path.realpath(PROJECT_ROOT))


def _read_file(path: str, line_start: int = 0, line_end: int = 0) -> Dict[str, Any]:
    abs_path = _resolve(path)
    if not _safe_path(path):
        return {"success": False, "error": f"Path outside project root: {path}"}
    if not os.path.exists(abs_path):
        return {"success": False, "error": f"File not found: {path}"}
    try:
        content = Path(abs_path).read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        if line_start > 0 and line_end > 0:
            selected = lines[line_start - 1:line_end]
            content = "\n".join(selected)
            lines = selected
        return {
            "success": True, "content": content, "lines": len(lines),
            "size_bytes": os.path.getsize(abs_path),
            "last_modified": datetime.fromtimestamp(os.path.getmtime(abs_path)).isoformat(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _write_file(path: str, content: str, create_dirs: bool = True, backup_existing: bool = True) -> Dict[str, Any]:
    abs_path = _resolve(path)
    if not _safe_path(path):
        return {"success": False, "error": f"Path outside project root: {path}"}

    backup_path = None
    if os.path.exists(abs_path) and backup_existing:
        backup_path = abs_path + ".bak"
        shutil.copy2(abs_path, backup_path)

    try:
        if create_dirs:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        Path(abs_path).write_text(content, encoding="utf-8")
        return {
            "success": True, "path": path,
            "bytes_written": len(content.encode("utf-8")),
            "backup_path": backup_path,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _edit_file(path: str, target: str, replacement: str, backup: bool = True) -> Dict[str, Any]:
    abs_path = _resolve(path)
    if not _safe_path(path):
        return {"success": False, "error": f"Path outside project root: {path}"}
    if not os.path.exists(abs_path):
        return {"success": False, "error": f"File not found: {path}"}

    try:
        original = Path(abs_path).read_text(encoding="utf-8")
        if target not in original:
            return {"success": False, "error": f"Target string not found in {path}"}

        if backup:
            shutil.copy2(abs_path, abs_path + ".bak")

        new_content = original.replace(target, replacement, 1)
        Path(abs_path).write_text(new_content, encoding="utf-8")

        # Validate syntax for Python files
        validation = "skipped"
        if path.endswith(".py"):
            try:
                ast.parse(new_content)
                validation = "passed"
            except SyntaxError as e:
                validation = f"FAILED: {e}"

        return {
            "success": True, "edits_applied": 1,
            "validation": validation,
            "diff_preview": f"-{target[:100]}\n+{replacement[:100]}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _delete_file(path: str) -> Dict[str, Any]:
    abs_path = _resolve(path)
    if not _safe_path(path):
        return {"success": False, "error": f"Path outside project root: {path}"}
    if not os.path.exists(abs_path):
        return {"success": False, "error": f"File not found: {path}"}

    try:
        os.makedirs(TRASH_DIR, exist_ok=True)
        trash_name = f"{int(time.time())}_{os.path.basename(abs_path)}"
        trash_path = os.path.join(TRASH_DIR, trash_name)
        shutil.move(abs_path, trash_path)
        return {"success": True, "trash_path": trash_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _list_directory(path: str = ".", recursive: bool = False, filter_ext: str = "") -> Dict[str, Any]:
    abs_path = _resolve(path)
    if not os.path.isdir(abs_path):
        return {"success": False, "error": f"Not a directory: {path}"}

    entries = []
    try:
        if recursive:
            for root, dirs, files in os.walk(abs_path):
                dirs[:] = [d for d in dirs if d not in {"__pycache__", "node_modules", ".git", ".next", "venv"}]
                for f in files:
                    if filter_ext and not f.endswith(filter_ext):
                        continue
                    fp = os.path.join(root, f)
                    rel = os.path.relpath(fp, abs_path)
                    entries.append({"name": rel, "type": "file", "size_bytes": os.path.getsize(fp)})
                    if len(entries) >= 200:
                        break
                if len(entries) >= 200:
                    break
        else:
            for item in sorted(os.listdir(abs_path)):
                if item.startswith(".") and item not in {".env", ".agent"}:
                    continue
                fp = os.path.join(abs_path, item)
                if filter_ext and os.path.isfile(fp) and not item.endswith(filter_ext):
                    continue
                entry = {"name": item, "type": "dir" if os.path.isdir(fp) else "file"}
                if os.path.isfile(fp):
                    entry["size_bytes"] = os.path.getsize(fp)
                entries.append(entry)
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": True, "entries": entries, "total": len(entries)}


def _search_codebase(query: str, file_types: str = ".py,.tsx,.ts,.js", max_results: int = 20) -> Dict[str, Any]:
    """Full-text search across the codebase."""
    extensions = [ext.strip() for ext in file_types.split(",")]
    matches = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", "node_modules", ".git", ".next", "venv", ".trash"}]
        for f in files:
            if not any(f.endswith(ext) for ext in extensions):
                continue
            fp = os.path.join(root, f)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if query.lower() in line.lower():
                            matches.append({
                                "file": os.path.relpath(fp, PROJECT_ROOT),
                                "line": i,
                                "content": line.strip()[:200],
                            })
                            if len(matches) >= max_results:
                                return {"success": True, "matches": matches, "total": len(matches), "truncated": True}
            except Exception:
                continue

    return {"success": True, "matches": matches, "total": len(matches), "truncated": False}


def _get_file_info(path: str) -> Dict[str, Any]:
    abs_path = _resolve(path)
    if not os.path.exists(abs_path):
        return {"exists": False, "path": path}
    stat = os.stat(abs_path)
    return {
        "exists": True, "path": path,
        "size_bytes": stat.st_size,
        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "is_directory": os.path.isdir(abs_path),
    }


# ── Registration ────────────────────────────────────────────────

def register(executor: "ToolExecutor") -> int:
    executor.register(name="read_file", description="Read content of a file. Specify line_start and line_end to read a range.", category="filesystem", handler=_read_file, parameters={"type": "object", "properties": {"path": {"type": "string"}, "line_start": {"type": "integer", "default": 0}, "line_end": {"type": "integer", "default": 0}}, "required": ["path"]})
    executor.register(name="write_file", description="Write content to a file. Creates parent directories. Backs up existing file.", category="filesystem", handler=_write_file, danger_level="moderate", parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "create_dirs": {"type": "boolean", "default": True}, "backup_existing": {"type": "boolean", "default": True}}, "required": ["path", "content"]})
    executor.register(name="edit_file", description="Replace a target string in a file with a replacement. Validates Python syntax after edit.", category="filesystem", handler=_edit_file, danger_level="moderate", parameters={"type": "object", "properties": {"path": {"type": "string"}, "target": {"type": "string"}, "replacement": {"type": "string"}, "backup": {"type": "boolean", "default": True}}, "required": ["path", "target", "replacement"]})
    executor.register(name="delete_file", description="Delete a file (moves to .trash/ for safety).", category="filesystem", handler=_delete_file, danger_level="destructive", parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
    executor.register(name="list_directory", description="List files and directories at a path.", category="filesystem", handler=_list_directory, parameters={"type": "object", "properties": {"path": {"type": "string", "default": "."}, "recursive": {"type": "boolean", "default": False}, "filter_ext": {"type": "string", "default": ""}}, "required": []})
    executor.register(name="search_codebase", description="Full-text search across the NexClip codebase.", category="filesystem", handler=_search_codebase, parameters={"type": "object", "properties": {"query": {"type": "string"}, "file_types": {"type": "string", "default": ".py,.tsx,.ts,.js"}, "max_results": {"type": "integer", "default": 20}}, "required": ["query"]})
    executor.register(name="get_file_info", description="Get metadata about a file: size, last modified, existence.", category="filesystem", handler=_get_file_info, parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
    return 7
