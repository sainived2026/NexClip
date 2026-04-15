"""
Nex Agent Tools — Skills & Workflows (Category 8)
=====================================================
List, load, create skills and workflows.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

logger = logging.getLogger("nex_agent.tools.skill")

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".agent", "skills")
WORKFLOWS_DIR = os.path.join(PROJECT_ROOT, ".agent", "workflows")


def _list_skills() -> Dict[str, Any]:
    if not os.path.isdir(SKILLS_DIR):
        return {"skills": [], "error": "Skills directory not found"}
    skills = []
    for name in sorted(os.listdir(SKILLS_DIR)):
        skill_path = os.path.join(SKILLS_DIR, name)
        if os.path.isdir(skill_path):
            skill_md = os.path.join(skill_path, "SKILL.md")
            desc = ""
            if os.path.exists(skill_md):
                try:
                    content = Path(skill_md).read_text(encoding="utf-8")
                    for line in content.splitlines():
                        if line.startswith("description:"):
                            desc = line.split(":", 1)[1].strip()
                            break
                except Exception:
                    pass
            skills.append({"name": name, "path": skill_path, "description": desc})
    return {"skills": skills, "count": len(skills)}


def _load_skill(skill_name: str) -> Dict[str, Any]:
    skill_md = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
    if not os.path.exists(skill_md):
        return {"loaded": False, "error": f"Skill '{skill_name}' not found at {skill_md}"}
    try:
        content = Path(skill_md).read_text(encoding="utf-8")
        return {"loaded": True, "skill_name": skill_name, "content": content[:10000]}
    except Exception as e:
        return {"loaded": False, "error": str(e)}


def _create_skill(name: str, description: str, content: str) -> Dict[str, Any]:
    skill_dir = os.path.join(SKILLS_DIR, name)
    os.makedirs(skill_dir, exist_ok=True)
    skill_md = os.path.join(skill_dir, "SKILL.md")
    full_content = f"---\nname: {name}\ndescription: {description}\n---\n\n{content}"
    try:
        Path(skill_md).write_text(full_content, encoding="utf-8")
        return {"created": True, "path": skill_md}
    except Exception as e:
        return {"created": False, "error": str(e)}


def _list_workflows() -> Dict[str, Any]:
    if not os.path.isdir(WORKFLOWS_DIR):
        return {"workflows": [], "error": "Workflows directory not found"}
    workflows = []
    for name in sorted(os.listdir(WORKFLOWS_DIR)):
        if name.endswith(".md"):
            wf_path = os.path.join(WORKFLOWS_DIR, name)
            desc = ""
            try:
                content = Path(wf_path).read_text(encoding="utf-8")
                for line in content.splitlines():
                    if line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip()
                        break
            except Exception:
                pass
            workflows.append({"name": name.replace(".md", ""), "path": wf_path, "description": desc})
    return {"workflows": workflows, "count": len(workflows)}


def _create_workflow(name: str, description: str, steps: str) -> Dict[str, Any]:
    os.makedirs(WORKFLOWS_DIR, exist_ok=True)
    wf_path = os.path.join(WORKFLOWS_DIR, f"{name}.md")
    content = f"---\ndescription: {description}\n---\n\n{steps}"
    try:
        Path(wf_path).write_text(content, encoding="utf-8")
        return {"created": True, "path": wf_path}
    except Exception as e:
        return {"created": False, "error": str(e)}


def _execute_workflow(workflow_name: str) -> Dict[str, Any]:
    wf_path = os.path.join(WORKFLOWS_DIR, f"{workflow_name}.md")
    if not os.path.exists(wf_path):
        return {"started": False, "error": f"Workflow '{workflow_name}' not found"}
    try:
        content = Path(wf_path).read_text(encoding="utf-8")
        return {"started": True, "workflow": workflow_name, "content_preview": content[:2000]}
    except Exception as e:
        return {"started": False, "error": str(e)}


def register(executor: "ToolExecutor") -> int:
    executor.register(name="list_skills", description="List all available skills in the .agent/skills/ directory.", category="skill", handler=_list_skills, parameters={"type": "object", "properties": {}})
    executor.register(name="load_skill", description="Read and return the full content of a skill.", category="skill", handler=_load_skill, parameters={"type": "object", "properties": {"skill_name": {"type": "string"}}, "required": ["skill_name"]})
    executor.register(name="create_skill", description="Create a new skill in .agent/skills/.", category="skill", handler=_create_skill, parameters={"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "content": {"type": "string"}}, "required": ["name", "description", "content"]})
    executor.register(name="list_workflows", description="List all workflows in .agent/workflows/.", category="skill", handler=_list_workflows, parameters={"type": "object", "properties": {}})
    executor.register(name="create_workflow", description="Create a new workflow definition.", category="skill", handler=_create_workflow, parameters={"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "steps": {"type": "string"}}, "required": ["name", "description", "steps"]})
    executor.register(name="execute_workflow", description="Load and return a workflow's content for execution.", category="skill", handler=_execute_workflow, parameters={"type": "object", "properties": {"workflow_name": {"type": "string"}}, "required": ["workflow_name"]})
    return 6
