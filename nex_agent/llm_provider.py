"""
Nex Agent — Standalone LLM Provider v3.0
============================================
Self-contained LLM client with configurable priority waterfall.

Supports TWO modes:
  1. generate()           — plain text generation (legacy)
  2. generate_with_tools() — function calling loop (new)

Does NOT import from backend — reads .env directly.
Reports the active model name for UI display.
"""

from __future__ import annotations

import json
import os
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("nex_agent.llm_provider")

@dataclass
class ModelProfile:
    name: str
    is_local: bool
    strict_mode_required: bool


def _sanitize_env_value(value: Optional[str]) -> str:
    """Normalize env values loaded from process env or .env lines."""
    if value is None:
        return ""
    cleaned = str(value).strip()
    if " #" in cleaned:
        cleaned = cleaned.split(" #", 1)[0].rstrip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _load_env_value(key: str, default: str = "") -> str:
    """Read a value from os.environ or from backend/.env file."""
    val = os.environ.get(key, "")
    if val:
        return _sanitize_env_value(val)
    env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
    if not env_path.exists():
        return default
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == key:
                return _sanitize_env_value(v)
    except Exception:
        pass
    return default


# ── Response Types ──────────────────────────────────────────────

class LLMResponse:
    """Structured response from the LLM. Contains either text or tool calls."""

    def __init__(self):
        self.text: str = ""
        self.thinking: str = ""        # Native thought content from Gemini thinkingConfig API
        self.tool_calls: List[Dict[str, Any]] = []
        self.finish_reason: str = ""
        self.provider: str = ""
        self.model: str = ""

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    def __repr__(self) -> str:
        if self.has_tool_calls:
            names = [tc.get("name", "?") for tc in self.tool_calls]
            return f"LLMResponse(tool_calls={names})"
        return f"LLMResponse(text={self.text[:80]}...)"


# ── Provider ────────────────────────────────────────────────────

class LLMProvider:
    """
    Standalone LLM client for Nex Agent.
    Priority is driven by LLM_PROVIDER_PRIORITY.
    Supports function calling for agent tool use.
    """

    def __init__(self) -> None:
        self.providers: List[Dict[str, Any]] = []
        self.active_provider: Optional[str] = None
        self.active_model: str = "none"
        self._build_chain()

    def _build_chain(self) -> None:
        provider_map: Dict[str, Dict[str, Any]] = {}

        anthropic_key = _load_env_value("ANTHROPIC_API_KEY")
        anthropic_model = _load_env_value("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        if anthropic_key:
            provider_map["anthropic"] = {
                "name": "anthropic", "type": "anthropic",
                "api_key": anthropic_key, "model": anthropic_model,
                "label": f"Anthropic {anthropic_model}",
                "supports_tools": True,
                "strict_mode_required": False,
            }

        openai_key = _load_env_value("OPENAI_API_KEY")
        openai_model = _load_env_value("OPENAI_MODEL", "gpt-4o")
        if openai_key:
            provider_map["openai"] = {
                "name": "openai", "type": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key": openai_key, "model": openai_model,
                "label": f"OpenAI {openai_model}",
                "supports_tools": True,
                "strict_mode_required": False,
            }

        gemini_key = _load_env_value("GEMINI_API_KEY")
        gemini_model = _load_env_value("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
        if gemini_key:
            provider_map["gemini"] = {
                "name": "gemini", "type": "gemini",
                "api_key": gemini_key, "model": gemini_model,
                "label": f"Gemini {gemini_model}",
                "supports_tools": True,
                "strict_mode_required": False,
            }

        openrouter_key = _load_env_value("OPENROUTER_API_KEY")
        openrouter_model = _load_env_value("OPENROUTER_MODEL", "qwen/qwen3.6-plus:free")
        if openrouter_key:
            provider_map["openrouter"] = {
                "name": "openrouter", "type": "openai",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": openrouter_key,
                "model": openrouter_model, "label": f"OpenRouter ({openrouter_model})",
                "supports_tools": True,
                "strict_mode_required": False,
            }

        raw_priority = _load_env_value("LLM_PROVIDER_PRIORITY", "anthropic,openai,gemini,openrouter")
        priority = []
        for name in [item.strip().lower() for item in raw_priority.split(",") if item.strip()]:
            if name in {"gemini", "openrouter", "anthropic", "openai"} and name not in priority:
                priority.append(name)
        for name in ("anthropic", "openai", "gemini", "openrouter"):
            if name not in priority:
                priority.append(name)

        self.providers = [provider_map[name] for name in priority if name in provider_map]

        if self.providers:
            self.active_provider = self.providers[0]["name"]
            self.active_model = self.providers[0]["label"]
            for p in self.providers:
                key_preview = p.get("api_key", "")[:12] + "..." if p.get("api_key") else "none"
                logger.info(f"  Provider: {p['name']} | model={p['model']} | key={key_preview}")
            logger.info(f"LLM chain: {[p['name'] for p in self.providers]} — active: {self.active_provider}")
        else:
            logger.warning("No LLM providers configured!")
            
    def is_strict_mode(self) -> bool:
        """Returns True if the active provider requires strict anti-hallucination guardrails"""
        for p in self.providers:
            if p["name"] == self.active_provider:
                return p.get("strict_mode_required", False)
        return False

    # ── Plain text generation (legacy) ──────────────────────────

    def generate(self, system_prompt: str, user_message: str,
                 temperature: float = 0.7, max_tokens: int = 4096, timeout: int = 120) -> str:
        for provider in self.providers:
            try:
                if provider["type"] == "openai":
                    result = self._call_openai_text(provider, system_prompt, user_message, temperature, max_tokens, timeout)
                elif provider["type"] == "gemini":
                    result = self._call_gemini_text(provider, system_prompt, user_message, temperature, max_tokens, timeout)
                elif provider["type"] == "anthropic":
                    result = self._call_anthropic_text(provider, system_prompt, user_message, temperature, max_tokens, timeout)
                else:
                    continue
                if result:
                    self.active_provider = provider["name"]
                    self.active_model = provider["label"]
                    return result
            except Exception as e:
                logger.warning(f"Provider {provider['name']} failed: {e}")
                continue
        return "I'm unable to connect to any language model right now."

    # ── Function calling generation ─────────────────────────────

    def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> LLMResponse:
        """
        Generate a response that may contain tool calls.
        `messages` is a list of {role, content} or {role, content, tool_call_id, name}.
        `tools` is the tool schema list from ToolExecutor.get_tools_for_llm().
        """
        for provider in self.providers:
            try:
                if provider["type"] == "gemini" and provider.get("supports_tools"):
                    result = self._call_gemini_with_tools(provider, messages, tools, temperature, max_tokens, timeout)
                elif provider["type"] == "openai" and provider.get("supports_tools"):
                    result = self._call_openai_with_tools(provider, messages, tools, temperature, max_tokens, timeout)
                elif provider["type"] == "anthropic" and provider.get("supports_tools"):
                    result = self._call_anthropic_with_tools(provider, messages, tools, temperature, max_tokens, timeout)
                elif provider["type"] == "openai":
                    # Local model without tool support — fallback to text
                    result = self._call_openai_text_from_messages(provider, messages, temperature, max_tokens, timeout)
                else:
                    continue

                if result:
                    self.active_provider = provider["name"]
                    self.active_model = provider["label"]
                    result.provider = provider["name"]
                    result.model = provider["model"]
                    return result
            except Exception as e:
                # Log HTTP error body for API errors (Gemini/OpenAI return useful error messages)
                error_body = ""
                if hasattr(e, "read"):
                    try:
                        error_body = e.read().decode("utf-8", errors="replace")
                    except Exception:
                        pass
                elif hasattr(e, "reason") and hasattr(e, "code"):
                    error_body = f"HTTP {getattr(e, 'code', '?')}: {getattr(e, 'reason', '')}"
                logger.error(f"Provider {provider['name']} failed: {e} | body={error_body[:500]}")
                continue

        resp = LLMResponse()
        resp.text = "I'm unable to connect to any language model right now."
        return resp

    # ── OpenAI implementations ──────────────────────────────────

    def _call_openai_text(self, provider, system_prompt, user_message, temperature, max_tokens, timeout) -> str:
        import urllib.request
        url = f"{provider['base_url']}/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {provider['api_key']}"}
        payload = json.dumps({
            "model": provider["model"],
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
            "temperature": temperature, "max_tokens": max_tokens,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    def _call_openai_with_tools(self, provider, messages, tools, temperature, max_tokens, timeout) -> LLMResponse:
        import urllib.request
        url = f"{provider['base_url']}/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {provider['api_key']}"}

        body: Dict[str, Any] = {
            "model": provider["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        choice = data["choices"][0]
        msg = choice["message"]
        result = LLMResponse()
        result.finish_reason = choice.get("finish_reason", "")
        result.text = msg.get("content", "") or ""

        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                result.tool_calls.append({
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "arguments": args,
                })
        return result

    def _call_openai_text_from_messages(self, provider, messages, temperature, max_tokens, timeout) -> LLMResponse:
        import urllib.request
        url = f"{provider['base_url']}/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {provider['api_key']}"}
        payload = json.dumps({
            "model": provider["model"], "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        result = LLMResponse()
        content_text = data["choices"][0]["message"].get("content", "")
        
        # Fallback: Parse stringified tool calls if LLM returns a JSON array
        parsed_tools = False
        if content_text and content_text.strip().startswith("[") and content_text.strip().endswith("]"):
            try:
                # Need to match tool schema structure (name and arguments)
                arr = json.loads(content_text)
                if isinstance(arr, list) and all(isinstance(x, dict) and "name" in x for x in arr):
                    for tc in arr:
                        args = tc.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                pass
                        result.tool_calls.append({
                            "id": f"call_{tc['name']}_{int(time.time()*1000)}",
                            "name": tc["name"],
                            "arguments": args if isinstance(args, dict) else {},
                        })
                    parsed_tools = True
                    result.text = "" # Hide the raw JSON output from the chat
            except Exception:
                pass

        if not parsed_tools:
            result.text = content_text
        
        return result

    # ── Gemini implementations ──────────────────────────────────

    # Models that support native thinking via the Gemini API thinkingConfig parameter.
    # These return thought content in separate parts with `"thought": True`.
    _THINKING_CAPABLE_GEMINI_MODELS = {
        "gemma-4-31b-it",
        "gemma-4-9b-it",
        "gemini-2.5-pro-preview-05-06",
        "gemini-2.5-flash-preview-04-17",
        "gemini-2.5-pro-exp-03-25",
    }

    def _supports_thinking(self, model_name: str) -> bool:
        """Returns True if the model supports the Gemini API thinkingConfig."""
        return any(
            model_name.startswith(m) or m in model_name
            for m in self._THINKING_CAPABLE_GEMINI_MODELS
        )

    def _build_gemini_generation_config(self, model_name: str, temperature: float, max_tokens: int) -> Dict[str, Any]:
        """Build Gemini generationConfig, enabling thinkingConfig for supported models."""
        cfg: Dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if self._supports_thinking(model_name):
            # Enable dynamic thinking budget — the model decides how much to think.
            # Budget of -1 means dynamic (model chooses), 0 disables thinking.
            cfg["thinkingConfig"] = {"thinkingBudget": -1}
            logger.info(f"Enabled thinkingConfig for model: {model_name}")
        return cfg

    def _parse_gemini_parts(self, parts: list) -> tuple[str, str]:
        """
        Parse Gemini response parts, separating thought content from text content.
        Returns: (text, thinking)
          - text: the actual response text (parts without thought=True)
          - thinking: the thought content (parts with thought=True)
        """
        text_parts: list[str] = []
        thought_parts: list[str] = []
        for part in parts:
            if part.get("thought") is True:
                # This part is internal model reasoning (thinking)
                thought_parts.append(part.get("text", ""))
            elif "text" in part:
                text_parts.append(part["text"])
        return "".join(text_parts), "".join(thought_parts)

    def _call_gemini_text(self, provider, system_prompt, user_message, temperature, max_tokens, timeout) -> str:
        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{provider['model']}:generateContent?key={provider['api_key']}"
        payload = json.dumps({
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_message}]}],
            "generationConfig": self._build_gemini_generation_config(provider["model"], temperature, max_tokens),
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text, _ = self._parse_gemini_parts(parts)
                return text
        return ""

    def _call_gemini_with_tools(self, provider, messages, tools, temperature, max_tokens, timeout) -> LLMResponse:
        """Call Gemini with function calling support. Supports native thinking (thinkingConfig)."""
        import urllib.request

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{provider['model']}:generateContent?key={provider['api_key']}"

        # Convert messages to Gemini format
        gemini_contents = []
        system_text = ""

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_text = content
                continue
            elif role == "assistant":
                parts = []
                if content:
                    parts.append({"text": content})
                # Check for function calls in message
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        fn = tc.get("function", {})
                        args = fn.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {}
                        
                        fc_data = {
                            "name": fn.get("name", ""),
                            "args": args,
                        }
                        if "id" in tc:
                            fc_data["id"] = tc.get("id")
                            
                        part_obj = {"functionCall": fc_data}
                        if "gemini_part_data" in tc:
                            part_obj.update(tc["gemini_part_data"])
                            
                        parts.append(part_obj)
                if parts:
                    gemini_contents.append({"role": "model", "parts": parts})
            elif role == "tool":
                # Tool result message
                func_response = {
                    "name": msg.get("name", ""),
                    "response": {"result": content if isinstance(content, str) else json.dumps(content)},
                }
                if msg.get("tool_call_id"):
                    func_response["id"] = msg.get("tool_call_id")

                gemini_contents.append({
                    "role": "function",
                    "parts": [{
                        "functionResponse": func_response
                    }],
                })
            else:
                # User message
                gemini_contents.append({"role": "user", "parts": [{"text": content}]})

        # Build Gemini tool declarations
        gemini_tools = []
        if tools:
            declarations = []
            for t in tools:
                fn = t.get("function", {})
                decl = {"name": fn.get("name", ""), "description": fn.get("description", "")}
                params = fn.get("parameters", {})
                if params and params.get("properties"):
                    decl["parameters"] = params
                declarations.append(decl)
            gemini_tools = [{"function_declarations": declarations}]

        body: Dict[str, Any] = {
            "contents": gemini_contents,
            "generationConfig": self._build_gemini_generation_config(provider["model"], temperature, max_tokens),
        }
        if system_text:
            body["system_instruction"] = {"parts": [{"text": system_text}]}
        if gemini_tools:
            body["tools"] = gemini_tools

        payload = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        result = LLMResponse()
        candidates = data.get("candidates", [])
        if not candidates:
            result.text = ""
            return result

        parts = candidates[0].get("content", {}).get("parts", [])
        result.finish_reason = candidates[0].get("finishReason", "")

        for part in parts:
            if part.get("thought") is True:
                # Official Gemini thinking API — thought parts are marked with `thought: true`
                result.thinking += part.get("text", "")
            elif "text" in part:
                result.text += part["text"]
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_call = {
                    "id": fc.get("id") or f"call_{fc['name']}_{int(time.time()*1000)}",
                    "name": fc["name"],
                    "arguments": fc.get("args", {}),
                    "gemini_part_data": {k: v for k, v in part.items() if k != "functionCall"}
                }
                result.tool_calls.append(tool_call)

        return result

    # ── Anthropic implementations ──────────────────────────────────

    def _call_anthropic_text(self, provider, system_prompt, user_message, temperature, max_tokens, timeout) -> str:
        import urllib.request
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": provider["api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = json.dumps({
            "model": provider["model"],
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]

    def _call_anthropic_with_tools(self, provider, messages, tools, temperature, max_tokens, timeout) -> LLMResponse:
        import urllib.request
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": provider["api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        anthropic_messages = []
        system_text = ""
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_text = content
            elif role == "assistant":
                content_blocks = []
                if content:
                    content_blocks.append({"type": "text", "text": content})
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        fn = tc.get("function", {})
                        args = fn.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {}
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.get("id"),
                            "name": fn.get("name", ""),
                            "input": args
                        })
                anthropic_messages.append({"role": "assistant", "content": content_blocks})
            elif role == "tool":
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": content if isinstance(content, str) else json.dumps(content)
                    }]
                })
            else:
                anthropic_messages.append({"role": "user", "content": content})

        anthropic_tools = []
        if tools:
            for t in tools:
                fn = t.get("function", {})
                anthropic_tools.append({
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}})
                })

        body = {
            "model": provider["model"],
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        if system_text:
            body["system"] = system_text
        if anthropic_tools:
            body["tools"] = anthropic_tools

        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
        result = LLMResponse()
        result.finish_reason = data.get("stop_reason", "")
        
        for content in data.get("content", []):
            if content["type"] == "text":
                result.text += content["text"]
            elif content["type"] == "tool_use":
                result.tool_calls.append({
                    "id": content["id"],
                    "name": content["name"],
                    "arguments": content["input"],
                })
                
        return result

    # ── Accessors ───────────────────────────────────────────────

    def get_active_model(self) -> str:
        return self.active_model

    def get_provider_status(self) -> List[Dict[str, Any]]:
        return [
            {"name": p["name"], "model": p["model"], "label": p["label"], "supports_tools": p.get("supports_tools", False)}
            for p in self.providers
        ]


# ── Singleton ───────────────────────────────────────────────────

_provider_instance: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = LLMProvider()
    return _provider_instance
