"""
Nexearch — LLM Router
Reuses NexClip's LLMService with Nexearch-specific helpers.
Same fallback chain: Anthropic → OpenAI → Gemini → OpenRouter
"""

import json
import re
import sys
from typing import Optional, List, Dict, Any
from pathlib import Path
from loguru import logger

# Add NexClip backend to path for importing LLMService
_backend_path = str(Path(__file__).resolve().parent.parent.parent / "backend")
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

from app.services.llm_service import LLMService, get_llm_service


class NexearchLLMRouter:
    """
    Enhanced LLM router for Nexearch operations.
    Wraps NexClip's LLMService with batch processing,
    structured output parsing, and Nexearch-specific prompt templates.
    """

    def __init__(self):
        self._llm = get_llm_service()
        logger.info("NexearchLLMRouter initialized (using NexClip LLM fallback chain)")

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> str:
        """Generate a raw text response using the LLM fallback chain."""
        return self._llm.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> str:
        """Compatibility wrapper used by Arc conversation flows."""
        return self.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def generate_json(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """Generate and parse a JSON response."""
        return self._llm.generate_json(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def generate_json_batch(
        self,
        system_prompt: str,
        messages: List[str],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> List[dict]:
        """
        Generate JSON responses for a batch of messages.
        Processes sequentially to respect rate limits.
        Returns list of parsed JSON dicts (empty dict on failure).
        """
        results = []
        for i, msg in enumerate(messages):
            try:
                result = self.generate_json(
                    system_prompt=system_prompt,
                    user_message=msg,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                results.append(result)
                logger.debug(f"Batch item {i+1}/{len(messages)} completed")
            except Exception as e:
                logger.warning(f"Batch item {i+1}/{len(messages)} failed: {e}")
                results.append({})
        return results

    def generate_structured(
        self,
        system_prompt: str,
        user_message: str,
        schema_class: Any,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Any:
        """
        Generate a response and validate it against a Pydantic model.
        Returns the validated Pydantic instance or None on failure.
        """
        raw_json = self.generate_json(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not raw_json:
            return None
        try:
            return schema_class.model_validate(raw_json)
        except Exception as e:
            logger.warning(f"Schema validation failed for {schema_class.__name__}: {e}")
            return None

    def generate_with_retry(
        self,
        system_prompt: str,
        user_message: str,
        max_retries: int = 2,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> dict:
        """Generate JSON with retry on parse failure."""
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                result = self.generate_json(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if result:
                    return result
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}")

        logger.error(f"All {max_retries + 1} attempts failed. Last error: {last_error}")
        return {}

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Tool-calling compatibility wrapper for Arc Agent.
        Reuses Nex Agent's tool-capable LLM provider instead of falling back to plain chat.
        """
        from nex_agent.llm_provider import get_llm_provider

        provider = get_llm_provider()
        response = provider.generate_with_tools(
            messages=messages,
            tools=tools,
            temperature=temperature if temperature is not None else 0.3,
            max_tokens=max_tokens if max_tokens is not None else 4000,
            timeout=timeout if timeout is not None else 120,
        )

        tool_calls = []
        for tool_call in getattr(response, "tool_calls", []) or []:
            tool_calls.append({
                "id": tool_call.get("id", ""),
                "type": "function",
                "function": {
                    "name": tool_call.get("name", ""),
                    "arguments": json.dumps(tool_call.get("arguments", {}), ensure_ascii=False),
                },
            })

        return {
            "content": getattr(response, "text", "") or "",
            "tool_calls": tool_calls,
            "finish_reason": getattr(response, "finish_reason", ""),
            "provider": getattr(response, "provider", ""),
            "model": getattr(response, "model", ""),
        }


# ── Singleton ────────────────────────────────────────────────

_router_instance: Optional[NexearchLLMRouter] = None


def get_nexearch_llm() -> NexearchLLMRouter:
    """Factory — returns the Nexearch LLM router singleton."""
    global _router_instance
    if _router_instance is None:
        _router_instance = NexearchLLMRouter()
    return _router_instance
