"""
Nex Agent — Codebase Knowledge Index
========================================
Recursively scans the NexClip project tree, extracts file purposes,
functions, classes, imports, env vars, and API endpoints.
Builds a queryable in-memory index with JSON persistence.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import logging

logger = logging.getLogger("nex_agent.knowledge_index")

# Files/dirs to skip during indexing
SKIP_DIRS = {
    "__pycache__", "node_modules", ".next", "venv", ".venv", ".git",
    ".mypy_cache", ".pytest_cache", "dist", "build", ".agent",
    ".gemini", "env", ".env", ".tox", "egg-info",
}
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".dat",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
    ".ttf", ".otf", ".mp4", ".mp3", ".wav", ".db", ".sqlite",
}
INDEXABLE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".env", ".md", ".css", ".html",
    ".sh", ".bat", ".ps1", ".sql",
}


class FileEntry:
    """Represents a single file in the codebase index."""

    __slots__ = (
        "path", "relative_path", "extension", "size_bytes", "modified",
        "purpose", "functions", "classes", "imports", "exports",
        "env_vars", "api_endpoints", "dependencies", "content_hash",
    )

    def __init__(self, path: str, relative_path: str) -> None:
        self.path = path
        self.relative_path = relative_path
        self.extension = Path(path).suffix.lower()
        self.size_bytes = 0
        self.modified = ""
        self.purpose = ""
        self.functions: List[str] = []
        self.classes: List[str] = []
        self.imports: List[str] = []
        self.exports: List[str] = []
        self.env_vars: List[str] = []
        self.api_endpoints: List[str] = []
        self.dependencies: List[str] = []
        self.content_hash = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "relative_path": self.relative_path,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "modified": self.modified,
            "purpose": self.purpose,
            "functions": self.functions,
            "classes": self.classes,
            "imports": self.imports,
            "exports": self.exports,
            "env_vars": self.env_vars,
            "api_endpoints": self.api_endpoints,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileEntry":
        entry = cls(data["path"], data["relative_path"])
        entry.extension = data.get("extension", "")
        entry.size_bytes = data.get("size_bytes", 0)
        entry.modified = data.get("modified", "")
        entry.purpose = data.get("purpose", "")
        entry.functions = data.get("functions", [])
        entry.classes = data.get("classes", [])
        entry.imports = data.get("imports", [])
        entry.exports = data.get("exports", [])
        entry.env_vars = data.get("env_vars", [])
        entry.api_endpoints = data.get("api_endpoints", [])
        entry.dependencies = data.get("dependencies", [])
        return entry


class CodebaseKnowledgeIndex:
    """
    Scans, indexes, and queries the entire NexClip codebase.

    Capabilities:
    - Full recursive scan of all source files
    - Python AST parsing for functions, classes, imports
    - TypeScript/JS regex-based extraction
    - Environment variable detection
    - API endpoint detection
    - Keyword-based querying
    - JSON persistence for fast reloads
    """

    def __init__(self, project_root: str, index_path: Optional[str] = None) -> None:
        self.project_root = Path(project_root).resolve()
        _nex_agent_dir = str(Path(__file__).resolve().parent)
        self.index_path = Path(index_path or os.path.join(_nex_agent_dir, "nex_agent_memory", "codebase_index.json"))
        self.files: Dict[str, FileEntry] = {}
        self.last_scan: Optional[str] = None
        self.total_files = 0

    def build_index(self, force: bool = False) -> int:
        """
        Scan entire project tree and build the in-memory index.
        Returns count of files indexed.
        """
        start = time.time()
        self.files.clear()

        for root_dir, dirs, filenames in os.walk(str(self.project_root)):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

            for filename in filenames:
                filepath = os.path.join(root_dir, filename)
                ext = Path(filename).suffix.lower()

                if ext in SKIP_EXTENSIONS:
                    continue
                if ext not in INDEXABLE_EXTENSIONS:
                    continue

                rel_path = os.path.relpath(filepath, str(self.project_root))
                entry = FileEntry(filepath, rel_path)

                try:
                    stat = os.stat(filepath)
                    entry.size_bytes = stat.st_size
                    entry.modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
                except OSError:
                    continue

                # Skip large files (> 1MB, likely generated)
                if entry.size_bytes > 1_048_576:
                    continue

                # Parse based on extension
                try:
                    if ext == ".py":
                        self._parse_python(entry)
                    elif ext in (".ts", ".tsx", ".js", ".jsx"):
                        self._parse_typescript(entry)
                    elif ext == ".env":
                        self._parse_env(entry)
                    elif ext == ".json":
                        self._parse_json(entry)
                    elif ext in (".md", ".css", ".html"):
                        self._parse_text(entry)
                except Exception as e:
                    logger.debug(f"Parse error for {rel_path}: {e}")

                self.files[rel_path] = entry

        self.total_files = len(self.files)
        self.last_scan = datetime.utcnow().isoformat()
        elapsed = time.time() - start

        logger.info(f"Codebase index built: {self.total_files} files in {elapsed:.1f}s")

        # Persist to disk
        self.save_index()
        return self.total_files

    def _parse_python(self, entry: FileEntry) -> None:
        """Extract info from a Python file via AST."""
        try:
            with open(entry.path, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()

            tree = ast.parse(source)

            # Extract docstring as purpose
            if (isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant)):
                doc = tree.body[0].value.value
                if isinstance(doc, str):
                    entry.purpose = doc.strip().split("\n")[0][:200]

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    entry.functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    entry.classes.append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        entry.imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        entry.imports.append(node.module)

            # Detect API endpoints
            endpoint_patterns = [
                r'@\w+\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)',
                r'router\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)',
            ]
            for pattern in endpoint_patterns:
                for match in re.finditer(pattern, source, re.IGNORECASE):
                    method = match.group(1).upper()
                    path = match.group(2)
                    entry.api_endpoints.append(f"{method} {path}")

            # Detect env vars
            env_pattern = r'(?:os\.environ|os\.getenv|settings\.)\s*[\.\[\(]\s*["\']([A-Z_]+)'
            for match in re.finditer(env_pattern, source):
                entry.env_vars.append(match.group(1))

        except (SyntaxError, IndexError):
            pass

    def _parse_typescript(self, entry: FileEntry) -> None:
        """Extract info from TypeScript/JavaScript files."""
        try:
            with open(entry.path, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()

            # Functions
            for match in re.finditer(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', source):
                entry.functions.append(match.group(1))
            for match in re.finditer(r'(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(', source):
                entry.functions.append(match.group(1))

            # Components (React)
            for match in re.finditer(r'(?:export\s+default\s+)?function\s+([A-Z]\w+)', source):
                entry.classes.append(match.group(1))

            # Imports
            for match in re.finditer(r'import\s+.*?from\s+["\']([^"\']+)', source):
                entry.imports.append(match.group(1))

            # Exports
            for match in re.finditer(r'export\s+(?:default\s+)?(?:function|const|class)\s+(\w+)', source):
                entry.exports.append(match.group(1))

            # API routes (Next.js)
            for match in re.finditer(r'fetch\s*\(\s*[`"\']([^`"\']+)', source):
                entry.api_endpoints.append(match.group(1))

            # Env vars
            for match in re.finditer(r'process\.env\.(\w+)', source):
                entry.env_vars.append(match.group(1))

            # Purpose from first comment
            first_comment = re.search(r'^(?://|/\*)\s*(.+?)(?:\*/)?$', source, re.MULTILINE)
            if first_comment:
                entry.purpose = first_comment.group(1).strip()[:200]

        except Exception:
            pass

    def _parse_env(self, entry: FileEntry) -> None:
        """Parse .env files for variable names."""
        try:
            with open(entry.path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        var_name = line.split("=")[0].strip()
                        entry.env_vars.append(var_name)
            entry.purpose = "Environment configuration file"
        except Exception:
            pass

    def _parse_json(self, entry: FileEntry) -> None:
        """Parse JSON for package.json or config files."""
        try:
            with open(entry.path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            if "name" in data and "version" in data:
                entry.purpose = f"Package config: {data.get('name', '')} v{data.get('version', '')}"
                entry.dependencies = list(data.get("dependencies", {}).keys())[:20]
        except Exception:
            pass

    def _parse_text(self, entry: FileEntry) -> None:
        """Extract a purpose from text files."""
        try:
            with open(entry.path, "r", encoding="utf-8", errors="ignore") as f:
                first_lines = []
                for i, line in enumerate(f):
                    if i >= 3:
                        break
                    first_lines.append(line.strip())
            purpose = " ".join(first_lines).strip()
            if purpose:
                entry.purpose = purpose[:200]
        except Exception:
            pass

    # ── Querying ────────────────────────────────────────────────

    def query(self, question: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search the index for files matching a natural language query.
        Uses keyword matching against file paths, purposes, functions, and classes.
        """
        keywords = set(question.lower().split())
        scored_results: List[tuple] = []

        for rel_path, entry in self.files.items():
            score = 0
            # Match against various fields
            searchable = " ".join([
                rel_path.lower(),
                entry.purpose.lower(),
                " ".join(entry.functions).lower(),
                " ".join(entry.classes).lower(),
                " ".join(entry.api_endpoints).lower(),
            ])

            for keyword in keywords:
                if keyword in searchable:
                    score += 1
                # Boost for exact function/class name match
                if keyword in [f.lower() for f in entry.functions]:
                    score += 3
                if keyword in [c.lower() for c in entry.classes]:
                    score += 3

            if score > 0:
                scored_results.append((score, entry))

        # Sort by score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [e.to_dict() for _, e in scored_results[:limit]]

    def get_file_info(self, relative_path: str) -> Optional[Dict[str, Any]]:
        """Get full info about a specific file."""
        entry = self.files.get(relative_path)
        if entry:
            return entry.to_dict()
        # Try fuzzy match
        for key, entry in self.files.items():
            if relative_path in key or key.endswith(relative_path):
                return entry.to_dict()
        return None

    def get_all_env_vars(self) -> List[str]:
        """Get all environment variables found across the codebase."""
        all_vars: Set[str] = set()
        for entry in self.files.values():
            all_vars.update(entry.env_vars)
        return sorted(all_vars)

    def get_all_endpoints(self) -> List[str]:
        """Get all API endpoints found across the codebase."""
        endpoints = []
        for entry in self.files.values():
            for ep in entry.api_endpoints:
                if ep not in endpoints:
                    endpoints.append(ep)
        return endpoints

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the codebase."""
        py_files = sum(1 for e in self.files.values() if e.extension == ".py")
        ts_files = sum(1 for e in self.files.values() if e.extension in (".ts", ".tsx"))
        total_funcs = sum(len(e.functions) for e in self.files.values())
        total_classes = sum(len(e.classes) for e in self.files.values())

        return {
            "total_files": self.total_files,
            "python_files": py_files,
            "typescript_files": ts_files,
            "total_functions": total_funcs,
            "total_classes": total_classes,
            "total_endpoints": len(self.get_all_endpoints()),
            "total_env_vars": len(self.get_all_env_vars()),
            "last_scan": self.last_scan,
        }

    def get_context_for_query(self, query: str) -> str:
        """Build a context string for LLM enrichment based on a query."""
        results = self.query(query, limit=5)
        if not results:
            return ""

        parts = []
        for r in results:
            parts.append(f"**{r['relative_path']}**: {r['purpose']}")
            if r["functions"]:
                parts.append(f"  Functions: {', '.join(r['functions'][:8])}")
            if r["classes"]:
                parts.append(f"  Classes: {', '.join(r['classes'][:5])}")
            if r["api_endpoints"]:
                parts.append(f"  Endpoints: {', '.join(r['api_endpoints'][:5])}")
        return "\n".join(parts)

    # ── Persistence ─────────────────────────────────────────────

    def save_index(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_scan": self.last_scan,
            "total_files": self.total_files,
            "files": {k: v.to_dict() for k, v in self.files.items()},
        }
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_index(self) -> bool:
        if not self.index_path.exists():
            return False
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.last_scan = data.get("last_scan")
            self.total_files = data.get("total_files", 0)
            self.files = {
                k: FileEntry.from_dict(v) for k, v in data.get("files", {}).items()
            }
            logger.info(f"Loaded index: {self.total_files} files (scanned {self.last_scan})")
            return True
        except Exception as e:
            logger.warning(f"Failed to load index: {e}")
            return False
