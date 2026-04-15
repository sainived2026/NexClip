"""
Nex Agent — Skill Loader
============================
Indexes and loads skills from .agent/skills/.
Provides skill discovery and content for LLM enrichment.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger("nex_agent.skill_loader")


class SkillLoader:
    """
    Index and load skills from the .agent/skills/ directory.
    """

    def __init__(self, project_root: str) -> None:
        self.root = Path(project_root).resolve()
        self.skills_dir = self.root / ".agent" / "skills"
        self._index: Dict[str, Dict[str, Any]] = {}
        self.build_index()

    def build_index(self) -> int:
        """Scan skills directory and build index."""
        self._index.clear()

        if not self.skills_dir.exists():
            logger.info("No .agent/skills/ directory found")
            return 0

        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            try:
                content = skill_file.read_text(encoding="utf-8", errors="replace")
                name, description = self._parse_frontmatter(content)

                self._index[name or skill_dir.name] = {
                    "id": skill_dir.name,
                    "name": name or skill_dir.name,
                    "description": description,
                    "path": str(skill_file),
                    "dir": str(skill_dir),
                    "content_preview": content[:500],
                }
            except Exception as e:
                logger.debug(f"Failed to index skill {skill_dir.name}: {e}")

        logger.info(f"Indexed {len(self._index)} skills")
        return len(self._index)

    def _parse_frontmatter(self, content: str) -> tuple:
        """Extract name and description from YAML frontmatter."""
        name = ""
        description = ""

        fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            fm = fm_match.group(1)
            name_match = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
            desc_match = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
            if name_match:
                name = name_match.group(1).strip()
            if desc_match:
                description = desc_match.group(1).strip()

        return name, description

    def list_skills(self) -> List[Dict[str, Any]]:
        """Return all indexed skills (metadata only)."""
        return [
            {"id": s["id"], "name": s["name"], "description": s["description"]}
            for s in self._index.values()
        ]

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """Get full skill data including content."""
        skill = self._index.get(name)
        if not skill:
            # Try fuzzy match
            for key, s in self._index.items():
                if name.lower() in key.lower() or name.lower() in s.get("id", "").lower():
                    skill = s
                    break
        if not skill:
            return None

        # Read full content
        try:
            content = Path(skill["path"]).read_text(encoding="utf-8", errors="replace")
            return {**skill, "content": content}
        except Exception:
            return skill

    def find_relevant_skills(self, query: str) -> List[Dict[str, Any]]:
        """Find skills relevant to a query."""
        query_lower = query.lower()
        scored = []

        for key, skill in self._index.items():
            score = 0
            searchable = f"{skill['name']} {skill['description']} {skill.get('content_preview', '')}".lower()

            for word in query_lower.split():
                if word in searchable:
                    score += 1

            if score > 0:
                scored.append((score, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"id": s["id"], "name": s["name"], "description": s["description"]} for _, s in scored[:5]]

    def get_skills_context(self) -> str:
        """Build a context string listing all available skills for LLM enrichment."""
        if not self._index:
            return "No skills available."
        lines = ["Available skills:"]
        for s in self._index.values():
            lines.append(f"- **{s['name']}**: {s['description']}")
        return "\n".join(lines)
