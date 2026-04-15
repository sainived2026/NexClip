"""
Arc Agent — Conversation Engine
===================================
LLM-powered conversation with tool calling loop.
Handles multi-step reasoning, tool execution, and response generation.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger("arc_agent.conversation_engine")


class ArcConversationEngine:
    """
    LLM conversation engine with function calling for Arc Agent.
    Uses the shared NexClip LLM fallback chain (Anthropic → OpenAI → Gemini → OpenRouter).
    """

    MAX_TOOL_ROUNDS = 8  # Max tool-call iterations per message

    def __init__(
        self,
        tool_executor,
        personality_builder=None,
        memory=None,
    ) -> None:
        self.tool_executor = tool_executor
        self.personality_builder = personality_builder
        self.memory = memory
        self._history: List[Dict[str, str]] = []

    def chat(self, message: str, context: Optional[Dict] = None) -> str:
        """Synchronous chat — returns final text response."""
        chunks = list(self.chat_stream(message, context))
        tokens = []
        for chunk in chunks:
            try:
                parsed = json.loads(chunk) if isinstance(chunk, str) else chunk
                if parsed.get("type") == "token":
                    tokens.append(parsed.get("content", ""))
            except (json.JSONDecodeError, TypeError):
                tokens.append(str(chunk))
        return "".join(tokens)

    def chat_stream(self, message: str,
                     context: Optional[Dict] = None) -> Generator[str, None, None]:
        """Streaming chat with tool calling loop."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

        from nexearch.tools.llm_router import get_nexearch_llm

        # Build system prompt
        system_prompt = self._build_system_prompt(context)

        # Save user message to memory
        if self.memory:
            self.memory.save_message("user", message)

        # Add to local history
        self._history.append({"role": "user", "content": message})

        # LLM call with function calling loop
        llm = get_nexearch_llm()
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._history[-20:])

        full_response = ""
        tool_calls_made = []

        def _stream_text_response(text: str) -> bool:
            emitted = False
            for word in (text or "").split(" "):
                if not word:
                    continue
                token = word + " "
                emitted = True
                nonlocal_full_response[0] += token
                yield json.dumps({"type": "token", "content": token})
            return emitted

        def _fallback_plain_text(error: Optional[Exception] = None):
            fallback_callable = getattr(llm, "chat", None) or getattr(llm, "generate", None)
            if not callable(fallback_callable):
                detail = str(error) if error else "No compatible plain-text LLM fallback available."
                yield json.dumps({"type": "error", "content": detail})
                return
            try:
                response_text = fallback_callable(
                    system_prompt=system_prompt,
                    user_message=message,
                    temperature=0.3,
                    max_tokens=4000,
                )
                emitted = False
                for item in _stream_text_response(response_text or ""):
                    emitted = True
                    yield item
                if not emitted and error:
                    yield json.dumps({"type": "error", "content": str(error)})
            except Exception as fallback_error:
                yield json.dumps({"type": "error", "content": str(fallback_error)})

        nonlocal_full_response = [full_response]

        for round_num in range(self.MAX_TOOL_ROUNDS):
            # Refresh available tools to include any custom tools created in previous rounds
            tools = self.tool_executor.get_tools_for_llm()
            
            try:
                response = llm.chat_with_tools(
                    messages=messages,
                    tools=tools,
                    temperature=0.3,
                    max_tokens=4000,
                )
            except Exception as e:
                logger.warning(f"Arc tool-calling path failed on round {round_num + 1}: {e}")
                for item in _fallback_plain_text(e):
                    yield item
                full_response = nonlocal_full_response[0]
                break

            # Check if response has tool calls
            if isinstance(response, dict):
                tool_calls = response.get("tool_calls", [])
                text_content = response.get("content", "")

                if text_content and not tool_calls:
                    # Pure text response — stream it
                    for item in _stream_text_response(text_content):
                        yield item
                    full_response = nonlocal_full_response[0]
                    break

                if tool_calls:
                    # Execute tools
                    for tc in tool_calls:
                        tool_name = tc.get("function", {}).get("name", tc.get("name", ""))
                        try:
                            args = json.loads(tc.get("function", {}).get("arguments", tc.get("arguments", "{}")))
                        except (json.JSONDecodeError, TypeError):
                            args = {}

                        yield json.dumps({
                            "type": "tool_call",
                            "name": tool_name,
                            "arguments": args,
                            "status": "executing",
                        })

                        result = self.tool_executor.execute(tool_name, args)
                        tool_calls_made.append({
                            "name": tool_name,
                            "arguments": args,
                            "result": result,
                        })

                        yield json.dumps({
                            "type": "tool_call",
                            "name": tool_name,
                            "arguments": args,
                            "result": result,
                            "status": "complete",
                        })

                        # Add tool result to messages for next round
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [tc],
                        })
                        messages.append({
                            "role": "tool",
                            "name": tool_name,
                            "tool_call_id": tc.get("id", ""),
                            "content": json.dumps(result, default=str)[:3000],
                        })

                    continue  # Next round with tool results

                if not text_content and not tool_calls:
                    for item in _fallback_plain_text():
                        yield item
                    full_response = nonlocal_full_response[0]
                    break
            else:
                # String response
                for item in _stream_text_response(str(response)):
                    yield item
                full_response = nonlocal_full_response[0]
                break

        full_response = nonlocal_full_response[0]

        if not full_response and tool_calls_made:
            tool_names = ", ".join(tc.get("name", "tool") for tc in tool_calls_made)
            synthesized = f"Completed {len(tool_calls_made)} tool call(s): {tool_names}."
            for item in _stream_text_response(synthesized):
                yield item
            full_response = nonlocal_full_response[0]

        # Save assistant response to memory
        if full_response and self.memory:
            self.memory.save_message("arc", full_response, {
                "tool_calls": len(tool_calls_made),
            })

        self._history.append({"role": "assistant", "content": full_response})

        yield json.dumps({"type": "done", "tool_calls": len(tool_calls_made)})

    def _build_system_prompt(self, context: Optional[Dict] = None) -> str:
        """Build system prompt with memory and context."""
        from nexearch.arc.personality import build_arc_system_prompt

        memory_context = ""
        if self.memory:
            memory_context = self.memory.get_memory_context()

        system_status = ""
        client_context = ""
        if context:
            if context.get("system_status"):
                system_status = json.dumps(context["system_status"], default=str)[:500]
            if context.get("client_context"):
                client_context = json.dumps(context["client_context"], default=str)[:500]

        active_tools = str(self.tool_executor.get_tool_count())

        return build_arc_system_prompt(
            memory_context=memory_context,
            system_status=system_status,
            client_context=client_context,
            active_tools=active_tools,
        )

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._history[-limit:]

    def clear_history(self) -> None:
        self._history.clear()
