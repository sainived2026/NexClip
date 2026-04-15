"""
Nex Agent — Tools Package
============================
All executable tools organized by category.
Each module exposes a `register(executor)` function.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor


def register_all_tools(executor: "ToolExecutor") -> int:
    """Register every tool category with the executor. Returns count."""
    from nex_agent.tools import (
        process_tools,
        filesystem_tools,
        database_tools,
        network_tools,
        agent_tools,
        notification_tools,
        skill_tools,
        config_tools,
        self_expansion_tools,
        writing_tools,
        nexearch_tools,
        storage_tools,
        upload_tools,
        client_tools,
        video_tools,
    )

    modules = [
        process_tools,
        filesystem_tools,
        database_tools,
        network_tools,
        agent_tools,
        notification_tools,
        skill_tools,
        config_tools,
        self_expansion_tools,
        writing_tools,
        nexearch_tools,
        storage_tools,
        upload_tools,
        client_tools,
        video_tools,
    ]

    count = 0
    for mod in modules:
        registered = mod.register(executor)
        count += registered
    return count

