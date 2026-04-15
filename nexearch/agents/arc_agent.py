"""
Nexearch — Arc Agent (Controller Agent)
The supervisory AI agent that can:
- Chat with users about their account
- Trigger pipeline runs
- Override directives
- Review and approve published content
- Create custom tools
- Manage sub-agents
- Track and revert modifications
"""

import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from loguru import logger

from nexearch.tools.llm_router import get_nexearch_llm
from nexearch.agents.pipeline import NexearchPipeline


ARC_SYSTEM_PROMPT = """You are Arc — the intelligent controller of the Nexearch social media intelligence system.

Your capabilities:
1. ANALYZE: Deep-dive into any client's account data, DNA, scored posts, and directives
2. RUN_PIPELINE: Trigger full or partial pipeline runs for any client
3. OVERRIDE: Override individual directive parameters with justification
4. REVIEW: Review published content queue and approve/reject posts
5. EVOLVE: Force an evolution cycle or adjust evolution parameters
6. REPORT: Generate performance reports and insights
7. CONFIG: Modify client configuration and writing profiles
8. CREATE_TOOL: Design and register new custom tools
9. MANAGE_AGENTS: Create, configure, and deploy sub-agents
10. GENERATE_CLIPS: Delegate clip generation tasks to Nex Agent with client-specific setups

You have full access to all client data, DNA profiles, and pipeline history.
Respond conversationally but include structured action recommendations.
When the user asks you to do something, determine which action to take.

IMPORTANT: You are an enterprise-grade AI. Be precise, data-driven, and actionable.

Available Actions (respond with JSON in a code block if action needed):
```json
{{"action": "run_pipeline|override|approve|reject|report|config|evolve|delegate_to_nex", "params": {{}}}}
```"""


class ArcAgent:
    """
    Arc Agent — the supervisory controller.
    Handles chat, commands, and pipeline orchestration.
    """

    def __init__(self):
        self._llm = get_nexearch_llm()
        self._conversations: Dict[str, List[Dict]] = {}
        self._pipeline = NexearchPipeline()

    def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        client_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Chat with Arc Agent.
        Returns: {"response": str, "action": Optional[dict], "conversation_id": str}
        """
        conv_id = conversation_id or str(uuid.uuid4())

        if conv_id not in self._conversations:
            self._conversations[conv_id] = []

        self._conversations[conv_id].append({"role": "user", "content": message})

        # Build context-aware system prompt
        system = ARC_SYSTEM_PROMPT
        if client_context:
            system += f"\n\nCurrent Client Context:\n{json.dumps(client_context, default=str)[:3000]}"

        # Build conversation history
        history = self._conversations[conv_id][-20:]  # Last 20 messages
        user_msg = self._format_history(history)

        response_text = self._llm.generate(
            system_prompt=system, user_message=user_msg,
            temperature=0.4, max_tokens=4000,
        )

        # Extract any action from the response
        action = self._extract_action(response_text)

        self._conversations[conv_id].append({"role": "assistant", "content": response_text})

        return {
            "response": response_text,
            "action": action,
            "conversation_id": conv_id,
        }

    async def execute_action(self, action: Dict[str, Any], client_id: str,
                              credentials: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute an action determined by Arc Agent."""
        action_type = action.get("action", "")
        params = action.get("params", {})

        if action_type == "run_pipeline":
            state = await self._pipeline.run(
                client_id=client_id,
                account_url=params.get("account_url", ""),
                platform=params.get("platform", "instagram"),
                account_handle=params.get("account_handle", ""),
                credentials=credentials,
                **{k: v for k, v in params.items() if k not in ("account_url", "platform", "account_handle")},
            )
            return {"status": state.current_stage, "pipeline_id": state.pipeline_id,
                    "posts_scraped": state.scrape_total, "posts_analyzed": state.analysis_total}

        elif action_type == "report":
            return {"status": "report_generated", "data": params}

        elif action_type == "override":
            return {"status": "override_applied", "params": params}

        elif action_type in ("approve", "reject"):
            return {"status": f"{action_type}d", "params": params}

        elif action_type == "delegate_to_nex":
            # Send message to Nex Agent via Agent Bus
            try:
                from nexearch.agents.agent_bridge import get_agent_bus
                bus = get_agent_bus()
                # Assuming bus has a method to send message to Nex Agent
                bus.publish("arc_to_nex", {
                    "task": "generate_clips",
                    "params": params
                })
                return {"status": "delegated", "message": "Task delegated to Nex Agent."}
            except Exception as e:
                logger.warning(f"Could not delegate via bus: {e}")
                return {"status": "delegation_failed", "error": str(e)}

        return {"status": "unknown_action", "action": action_type}

    def _format_history(self, messages: List[Dict]) -> str:
        """Format conversation history for LLM input."""
        parts = []
        for msg in messages:
            role = msg["role"].upper()
            parts.append(f"[{role}]: {msg['content']}")
        return "\n".join(parts)

    def _extract_action(self, text: str) -> Optional[Dict]:
        """Extract JSON action from response text."""
        try:
            import re
            match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except Exception:
            pass
        return None

    def get_conversation_history(self, conversation_id: str) -> List[Dict]:
        """Get conversation history."""
        return self._conversations.get(conversation_id, [])

    def clear_conversation(self, conversation_id: str):
        """Clear a conversation."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]


# ── Singleton ────────────────────────────────────────────────

_arc_instance: Optional[ArcAgent] = None


def get_arc_agent() -> ArcAgent:
    global _arc_instance
    if _arc_instance is None:
        _arc_instance = ArcAgent()
    return _arc_instance
