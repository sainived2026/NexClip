"""
NexClip — Unified LLM Service with automatic, configurable provider priority.
Default order: Gemini 3.1 Flash → OpenRouter → Anthropic → OpenAI.
"""

import json
import re
from typing import Optional, Dict, Any, List
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class LLMService:
    """
    Unified LLM interface with automatic fallback chain.
    Tries providers in the configured priority order from Settings.
    All configuration comes from .env / Settings.
    """

    def __init__(self):
        self._providers = self._build_provider_chain()
        logger.info(f"LLMService initialized with providers: {[p['name'] for p in self._providers]}")

    def _build_provider_chain(self) -> List[Dict[str, Any]]:
        """Build ordered list of available LLM providers."""
        provider_map = {}

        if settings.has_anthropic:
            provider_map["anthropic"] = {
                "name": "Anthropic",
                "type": "anthropic",
                "api_key": settings.ANTHROPIC_API_KEY,
                "model": settings.ANTHROPIC_MODEL,
            }

        if settings.has_openai:
            provider_map["openai"] = {
                "name": "OpenAI",
                "type": "openai",
                "api_key": settings.OPENAI_API_KEY,
                "model": settings.OPENAI_MODEL,
                "base_url": None,  # Use default OpenAI endpoint
            }

        if settings.has_gemini:
            provider_map["gemini"] = {
                "name": "Gemini",
                "type": "gemini",
                "api_key": settings.GEMINI_API_KEY,
                "model": settings.GEMINI_MODEL,
            }

        if settings.has_openrouter:
            provider_map["openrouter"] = {
                "name": "OpenRouter",
                "type": "openai",
                "api_key": settings.OPENROUTER_API_KEY,
                "model": settings.OPENROUTER_MODEL,
                "base_url": "https://openrouter.ai/api/v1",
            }

        providers = [
            provider_map[name]
            for name in settings.llm_provider_priority_list
            if name in provider_map
        ]

        if not providers:
            raise RuntimeError(
                "No LLM provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
                "GEMINI_API_KEY, or OPENROUTER_API_KEY in .env"
            )

        return providers

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> str:
        """
        Generate a response using the LLM fallback chain.
        Returns raw text content from the LLM.
        Tries each provider in order; falls back on failure.
        """
        _temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        _max_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS
        _timeout = timeout if timeout is not None else settings.LLM_TIMEOUT

        last_error = None

        for provider in self._providers:
            try:
                logger.info(f"Attempting LLM call via {provider['name']} (model: {provider['model']})")

                if provider["type"] == "anthropic":
                    result = self._call_anthropic(
                        provider, system_prompt, user_message,
                        _temperature, _max_tokens, _timeout,
                    )
                elif provider["type"] == "openai":
                    result = self._call_openai(
                        provider, system_prompt, user_message,
                        _temperature, _max_tokens, _timeout,
                    )
                elif provider["type"] == "gemini":
                    result = self._call_gemini(
                        provider, system_prompt, user_message,
                        _temperature, _max_tokens, _timeout,
                    )
                else:
                    continue

                logger.info(f"LLM call succeeded via {provider['name']} — response length: {len(result)} chars")
                return result

            except Exception as e:
                last_error = e
                logger.warning(f"LLM provider {provider['name']} failed: {e}")
                continue

        raise RuntimeError(
            f"All LLM providers failed. Last error: {last_error}"
        )

    def _call_anthropic(
        self,
        provider: Dict,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
    ) -> str:
        """Call the Anthropic Messages API."""
        import anthropic

        client = anthropic.Anthropic(
            api_key=provider["api_key"],
            timeout=timeout,
        )

        response = client.messages.create(
            model=provider["model"],
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
        )

        return response.content[0].text or ""

    def _call_openai(
        self,
        provider: Dict,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
    ) -> str:
        """Call an OpenAI-compatible API (OpenAI or OpenRouter)."""
        import openai

        client_kwargs = {"api_key": provider["api_key"]}
        if provider.get("base_url"):
            client_kwargs["base_url"] = provider["base_url"]
        client_kwargs["timeout"] = timeout

        client = openai.OpenAI(**client_kwargs)

        request_kwargs: dict = {
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Only add response_format for real OpenAI (OpenRouter models may not support it)
        if not provider.get("base_url"):
            request_kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**request_kwargs)
        return response.choices[0].message.content or ""

    # Models that support native thinking via the Gemini API thinkingConfig.
    # The API returns thought content in separate parts with thought=True.
    _THINKING_CAPABLE_GEMINI_MODELS = {
        "gemma-4-31b-it", "gemma-4-9b-it",
        "gemini-2.5-pro-preview-05-06", "gemini-2.5-flash-preview-04-17",
        "gemini-2.5-pro-exp-03-25",
    }

    def _call_gemini(
        self,
        provider: Dict,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
    ) -> str:
        """Call Google Gemini API."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=provider["api_key"])

        model_name = provider["model"]
        gen_config_kwargs: dict = {
            "system_instruction": system_prompt,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            # NOTE: Do NOT set response_mime_type="application/json".
            # Gemini truncates large JSON responses when that flag is set,
            # causing clip extraction to fail silently.
        }

        # Enable native thinking for supported models (gemma-4-31b-it etc.)
        supports_thinking = any(
            model_name.startswith(m) or m in model_name
            for m in self._THINKING_CAPABLE_GEMINI_MODELS
        )
        if supports_thinking:
            try:
                gen_config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=-1)
            except Exception:
                pass  # Older google-genai SDK version may not have ThinkingConfig

        response = client.models.generate_content(
            model=model_name,
            contents=user_message,
            config=types.GenerateContentConfig(**gen_config_kwargs),
        )

        return response.text or ""

    # ── JSON Extraction Utilities ───────────────────────────────

    def generate_json(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Generate a response and extract structured JSON.
        Handles markdown fences, thinking tags, and malformed JSON.
        """
        raw = self.generate(system_prompt, user_message, temperature, max_tokens, timeout)
        return self.extract_json(raw)

    @staticmethod
    def _repair_truncated_json(text: str) -> dict:
        """Attempt to repair truncated JSON by closing open brackets/braces.

        LLMs sometimes return valid-looking JSON that is cut off mid-stream
        (e.g. Gemini max_output_tokens reached).  This method walks the string,
        tracks nesting depth, and appends the necessary closing characters so
        that json.loads can parse at least the *complete* top-level entries.
        """
        # Find the first '{' or '['
        start = -1
        for i, ch in enumerate(text):
            if ch in ('{', '['):
                start = i
                break
        if start == -1:
            return {}

        fragment = text[start:]

        # Walk through and track open/close stack (skip strings)
        stack: list[str] = []
        in_string = False
        escape = False
        last_complete_pos = start  # track position of last complete value

        for i, ch in enumerate(fragment):
            if escape:
                escape = False
                continue
            if ch == '\\':
                if in_string:
                    escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue

            if ch in ('{', '['):
                stack.append('}' if ch == '{' else ']')
            elif ch in ('}', ']'):
                if stack:
                    stack.pop()
                    if not stack:
                        last_complete_pos = i + 1

        if not stack:
            # Already complete — try parsing as-is
            try:
                return json.loads(fragment)
            except json.JSONDecodeError:
                return {}

        # Truncated — try to salvage.  
        # Step 1: Remove the last incomplete value (trailing partial string/number)
        repair = fragment.rstrip()
        # Strip trailing partial string (unterminated quote)
        if in_string:
            repair = repair + '"'

        # Remove a dangling object key like , "hook_" that was cut off mid-field.
        repair = re.sub(r',\s*"[^"]*"\s*$', '', repair)
        repair = re.sub(r'\{\s*"[^"]*"\s*$', '{', repair)

        # Remove trailing comma or colon that precedes incomplete value
        repair = repair.rstrip(' \t\n\r,')
        # If it ends with a key: (no value), remove the key too
        if repair.endswith(':'):
            last_quote = repair.rfind('"')
            if last_quote > 0:
                repair = repair[:last_quote - 1].rstrip(' \t\n\r,')

        # Recount stack for the repaired fragment
        stack2: list[str] = []
        in_str2 = False
        esc2 = False
        for ch in repair:
            if esc2:
                esc2 = False
                continue
            if ch == '\\':
                if in_str2:
                    esc2 = True
                continue
            if ch == '"':
                in_str2 = not in_str2
                continue
            if in_str2:
                continue
            if ch in ('{', '['):
                stack2.append('}' if ch == '{' else ']')
            elif ch in ('}', ']'):
                if stack2:
                    stack2.pop()

        # Close all open brackets
        closing = ''.join(reversed(stack2))
        repaired = repair + closing

        try:
            result = json.loads(repaired)
            logger.info(f"Truncated JSON repaired successfully — salvaged partial response")
            return result
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def extract_json(text: str) -> dict:
        """Extract JSON from LLM response, handling common formatting issues."""
        if not text:
            return {}

        text = text.strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strip <think>...</think> blocks (qwen3 thinking model)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # Try again after stripping think tags
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strip opening/closing markdown fences even if the closing fence is missing.
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*```$", "", text).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Extract from markdown code fences
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Last resort: find the first { ... } block
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        # ── Final fallback: repair truncated JSON ───────────────
        # LLM response may be valid JSON that was cut off by token limits.
        # Try to close open brackets/braces to salvage partial data.
        repaired = LLMService._repair_truncated_json(text)
        if repaired:
            logger.warning(f"Used truncated JSON repair — data may be partial")
            return repaired

        logger.error(f"Could not extract JSON from response: {text[:500]}")
        return {}


# ── Singleton ───────────────────────────────────────────────────

_llm_instance: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Factory — returns the LLM service singleton."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMService()
    return _llm_instance
