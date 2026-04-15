"""
Nex Agent — Conversation Engine v3.0
========================================
The core intelligence loop that transforms Nex Agent from a chatbot
into a true tool-calling agent.

Architecture:
  User message → LLM reasons → LLM calls tools → Tools execute →
  LLM verifies outcomes → LLM reports verified results → User sees truth

The Golden Rule: Every action statement is backed by a tool execution result.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger("nex_agent.conversation_engine")

# Maximum tool call iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 10


class ConversationEngine:
    """
    Manages multi-turn conversations with LLM function calling.
    The LLM can call real tools, receive verified results,
    and generate responses grounded in actual system state.
    """

    def __init__(
        self,
        llm_provider=None,
        tool_executor=None,
        personality_builder=None,
        knowledge_index=None,
        runtime_monitor=None,
        memory=None,
    ) -> None:
        self._llm = llm_provider
        self._tool_executor = tool_executor
        self._personality_builder = personality_builder
        self._knowledge = knowledge_index
        self._monitor = runtime_monitor
        self._memory = memory

        # Conversation state
        self._messages: List[Dict[str, Any]] = []
        self._session_id: str = ""

    # ── Public Interface ────────────────────────────────────────

    def chat(self, user_message: str) -> str:
        """Process a user message and return the final text response."""
        tokens: List[str] = []
        last_error = ""

        for chunk in self.chat_stream(user_message):
            try:
                parsed = json.loads(chunk) if isinstance(chunk, str) else chunk
            except (json.JSONDecodeError, TypeError):
                tokens.append(str(chunk))
                continue

            event_type = parsed.get("type")
            if event_type == "token":
                tokens.append(parsed.get("content", ""))
            elif event_type == "error":
                last_error = parsed.get("content", "") or parsed.get("error", "")

        response_text = "".join(tokens).strip()
        return response_text or last_error

    def chat_stream(self, user_message: str) -> Generator[str, None, None]:
        """
        Process a user message with streaming.
        Yields SSE-formatted events:
          - {"type": "status", "content": "..."} during tool execution
          - {"type": "tool_call", "name": "...", "result": {...}} for tool calls
          - {"type": "token", "content": "..."} for final text tokens
          - {"type": "done"} when complete
        """
        from nex_agent.llm_provider import get_llm_provider, LLMResponse
        from nex_agent.intent_classifier import IntentClassifier
        from nex_agent.response_validator import ResponseValidator

        llm = self._llm or get_llm_provider()
        classifier = IntentClassifier()
        validator = ResponseValidator()
        
        intent, skip_tools = classifier.classify(user_message)
        is_strict = llm.is_strict_mode()

        # Build the system prompt with live context or greeting override
        if skip_tools:
            system_prompt = classifier.get_greeting_prompt_override(user_message)
        else:
            system_prompt = self._build_system_prompt(strict_mode=is_strict)

        # Build messages for the LLM
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history (last 10 turns for context window management)
        for msg in self._messages[-20:]:
            # Heal old bloated messages on the fly
            clean_msg = dict(msg)
            if isinstance(clean_msg.get("content"), str) and len(clean_msg["content"]) > 15000:
                clean_msg["content"] = clean_msg["content"][:15000] + "... [TRUNCATED FOR HISTORY]"
            messages.append(clean_msg)

        # Add user message
        messages.append({"role": "user", "content": user_message})
        self._messages.append({"role": "user", "content": user_message})

        # Get tool definitions
        tools = []
        if self._tool_executor and not skip_tools:
            tools = self._tool_executor.get_tools_for_llm()

        # ── The Tool Calling Loop ───────────────────────────────
        iteration = 0
        tool_results_summary: List[str] = []

        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            try:
                response = llm.generate_with_tools(
                    messages=messages,
                    tools=tools,
                    temperature=0.7,
                    max_tokens=4096,
                    timeout=120,
                )
            except Exception as e:
                error_msg = f"LLM call failed: {e}"
                logger.error(error_msg, exc_info=True)
                yield json.dumps({"type": "token", "content": f"I encountered an error connecting to the language model: {e}"})
                yield json.dumps({"type": "done"})
                return

            # --- Tool Call Interception Layer (for Local Models Outputting Strings) ---
            if not response.has_tool_calls and response.text:
                from nex_agent.tool_call_interceptor import ToolCallInterceptor
                interceptor = ToolCallInterceptor()
                clean_text, extracted_tools = interceptor.extract_and_strip_tool_calls(response.text)
                
                if extracted_tools:
                    import uuid
                    for tc in extracted_tools:
                        response.tool_calls.append({
                            "id": f"call_{uuid.uuid4().hex[:8]}",
                            "name": tc["name"],
                            "arguments": tc["arguments"]
                        })
                    response.text = clean_text

            if response.has_tool_calls:
                # LLM wants to call tools — execute them
                assistant_msg: Dict[str, Any] = {"role": "assistant", "content": response.text or ""}

                # Format tool calls for message history
                formatted_calls = []
                for tc in response.tool_calls:
                    formatted_call = {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"], default=str),
                        },
                    }
                    if "gemini_part_data" in tc:
                        formatted_call["gemini_part_data"] = tc["gemini_part_data"]
                    formatted_calls.append(formatted_call)
                assistant_msg["tool_calls"] = formatted_calls
                messages.append(assistant_msg)

                # Execute each tool
                for tc in response.tool_calls:
                    tool_name = tc["name"]
                    tool_args = tc["arguments"]

                    # Yield status event
                    yield json.dumps({
                        "type": "status",
                        "content": f"Executing: {tool_name}",
                    })

                    # Execute the tool
                    if self._tool_executor:
                        result = self._tool_executor.execute_sync(tool_name, tool_args)
                        result_data = result.to_dict()
                    else:
                        result_data = {"success": False, "error": "Tool executor not available"}

                    # Yield tool result event
                    yield json.dumps({
                        "type": "tool_call",
                        "name": tool_name,
                        "arguments": tool_args,
                        "result": result_data,
                    })

                    tool_results_summary.append(
                        f"{tool_name}: {'✓' if result_data.get('success', False) else '✗'}"
                    )

                    # Add tool result to messages for next LLM call
                    result_str = json.dumps(result_data, default=str)
                    
                    # Prevent context explosion which causes massive latency
                    if len(result_str) > 15000:
                        logger.warning(f"Truncating massive tool result for {tool_name} (length: {len(result_str)})")
                        result_str = result_str[:15000] + "... [TRUNCATED DUE TO LENGTH]"
                        
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tool_name,
                        "content": result_str,
                    })

                # Yield status so the UI doesn't look frozen while waiting for the next LLM response
                yield json.dumps({
                    "type": "status",
                    "content": "Analyzing results...",
                })
                
                # Continue the loop — LLM will see tool results and either
                # call more tools or generate a final text response
                continue

            else:
                # LLM returned text — extract thinking and clean content
                raw_text = response.text or ""
                
                # Extract <think>...</think> blocks as thinking content
                import re as _re
                thinking_content = ""
                think_match = _re.search(r"<think>(.*?)</think>", raw_text, _re.DOTALL | _re.IGNORECASE)
                if think_match:
                    thinking_content = think_match.group(1).strip()
                    raw_text = _re.sub(r"<think>.*?</think>", "", raw_text, flags=_re.DOTALL | _re.IGNORECASE).strip()
                
                # Run the standard validator to strip any remaining leaked reasoning
                is_valid, final_text = validator.validate_and_fix(raw_text, tool_results_summary)
                
                # If validator stripped content that looks like thinking, capture it
                if not thinking_content and raw_text and final_text != raw_text:
                    thinking_content = raw_text.replace(final_text, "").strip()

                # Store in conversation history (clean text only)
                self._messages.append({"role": "assistant", "content": final_text})

                # Save to memory
                self._save_to_memory(user_message, final_text, tool_results_summary)

                # Emit thinking event first (if any)
                if thinking_content:
                    yield json.dumps({"type": "thinking", "content": thinking_content})

                # Stream the clean response
                yield json.dumps({"type": "token", "content": final_text})
                yield json.dumps({"type": "done", "thinking_content": thinking_content})
                return


        # If we hit max iterations, force a text response
        yield json.dumps({
            "type": "token",
            "content": f"I executed {len(tool_results_summary)} tool operations but hit the maximum iteration limit. Here's what I did: {', '.join(tool_results_summary)}",
        })
        yield json.dumps({"type": "done"})

    # ── System Prompt Builder ───────────────────────────────────

    def _build_system_prompt(self, strict_mode: bool = False) -> str:
        """Build system prompt with live context from monitoring."""
        from nex_agent.personality import build_system_prompt

        health_snapshot = "Not yet checked."
        recent_tools = "No recent tool executions."
        codebase_context = ""

        # Get health from runtime monitor
        if self._monitor:
            try:
                health = self._monitor.get_snapshot()
                health_lines = []
                for svc, data in health.get("services", {}).items():
                    status = "✓ online" if data.get("online") else "✗ offline"
                    health_lines.append(f"- **{svc}**: {status}")
                health_snapshot = "\n".join(health_lines) if health_lines else health_snapshot
            except Exception:
                pass

        # Get recent tool executions
        if self._tool_executor:
            try:
                recent = self._tool_executor.get_recent_executions(5)
                if recent:
                    lines = []
                    for e in recent:
                        status = "✓" if e.get("success") else "✗"
                        lines.append(f"- {status} `{e['tool']}` ({e['elapsed_ms']}ms)")
                    recent_tools = "\n".join(lines)
            except Exception:
                pass

        return build_system_prompt(
            health_snapshot=health_snapshot,
            recent_tools=recent_tools,
            codebase_context=codebase_context,
            strict_mode=strict_mode,
        )

    # ── Memory ──────────────────────────────────────────────────

    def _save_to_memory(self, user_msg: str, assistant_msg: str, tools_used: List[str]) -> None:
        if self._memory:
            try:
                self._memory.save_message(
                    role="user",
                    content=user_msg,
                    metadata={"tools_used": tools_used},
                )
                self._memory.save_message(
                    role="nex",
                    content=assistant_msg,
                    metadata={"tools_used": tools_used},
                )
            except Exception as e:
                logger.warning(f"Failed to save to memory: {e}")

    # ── Session Management ──────────────────────────────────────

    def clear_history(self) -> None:
        self._messages.clear()
        self._session_id = ""

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._messages[-limit:]

    def get_active_model(self) -> str:
        from nex_agent.llm_provider import get_llm_provider
        llm = self._llm or get_llm_provider()
        return llm.get_active_model()
