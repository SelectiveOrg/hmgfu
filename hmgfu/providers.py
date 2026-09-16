"""Multi-provider layer with per-role routing (PA3_LESSONS: simplified StreamChunk → chat()).

Roles: chat | nano | dream | grader | embed. Each role resolves to (provider, model) from
runtime settings (hmgfu.settings), falling back to config defaults. Unknown provider names
FAIL loudly (PA3 lesson 9 — no silent default).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, List, Optional

import httpx

from . import config
from .ollama_client import OllamaClient, OllamaError

log = logging.getLogger("hmgfu.providers")

ROLES = ("chat", "router", "nano", "dream", "grader", "embed")   # 73.2: router = the turn classifier (default: the chat model)

ROLE_DEFAULTS = {"chat": config.CHAT_MODEL, "router": config.ROUTER_MODEL, "nano": config.NANO_MODEL,
                 "dream": config.DREAM_MODEL, "grader": config.GRADER_MODEL, "embed": config.EMBED_MODEL}


def model_for_role(owner, role: str) -> str:
    """The model this role will ACTUALLY use. 95.77: /api/health named `config.CHAT_MODEL`, the
    compiled-in default, to a user who had chosen another chat model in Settings and whose every turn
    used the chosen one — the display contradicted the behaviour. The registry decides when there is
    one, the persisted setting when there is not, and the compiled-in default only when nothing is
    configured at all. `owner` is an engine (it carries .registry / .settings) or a registry itself."""
    registry = getattr(owner, "registry", None)
    if registry is None and hasattr(owner, "resolve"):
        registry = owner
    if registry is not None:
        try:
            return registry.resolve(role)[1]
        except Exception:                      # an unknown role or a settings store that cannot answer
            pass
    settings = getattr(owner, "settings", None)
    if settings is not None:
        try:
            chosen = settings.get(f"{role}_model")
        except Exception:
            chosen = None
        if chosen:
            return str(chosen)
    return ROLE_DEFAULTS.get(role, "")



class ProviderError(RuntimeError):
    pass


class BaseProvider:
    """Minimal contract: chat() returns the full assistant text (or raises ProviderError)."""

    name = "base"
    # Whether the backend emits structured tool_calls. When False, the agent drives tools
    # through a prompt-based JSON protocol instead (parse_protocol_tool_call in agent.py).
    supports_native_tools = False
    supports_embeddings = False

    def chat(self, model: str, messages: List[dict], json_mode: bool = False,
             temperature: float = 0.4, tools: Optional[List[dict]] = None,
             format_schema: Optional[dict] = None, think=None) -> dict:
        """Returns {"content": str, "tool_calls": [{"name","arguments"}], "thinking": str}.
        `format_schema` (Phase 57): a JSON Schema that grammar-CONSTRAINS decoding to a valid object.
        `think` (Phase 58): drive the model's NATIVE reasoning (True/False/level or None=omit); the
        reasoning trace comes back in `thinking` (separate from content). Ollama native only; other
        backends ignore it."""
        raise NotImplementedError

    def available(self) -> bool:
        return True

    def models(self) -> List[str]:
        return []

    def embed(self, model: str, text: str) -> List[float]:
        raise ProviderError(f"provider '{self.name}' does not support embeddings")


class OllamaProvider(BaseProvider):
    name = "ollama"
    # Verified live: gemma4:12b emits tool_calls through ollama's native tools payload
    # (content is empty on call turns — normal). The JSON prompt-protocol, by contrast,
    # yields empty content on gemma templates, so native is the correct mode here.
    supports_native_tools = True
    supports_embeddings = True

    def __init__(self, client: Optional[OllamaClient] = None):
        self.client = client or OllamaClient()

    def available(self) -> bool:
        return self.client.available()

    def models(self) -> List[str]:
        try:
            return self.client.models()
        except Exception:
            return []

    def embed(self, model: str, text: str) -> List[float]:
        return self.client.embed(text, model=model)

    def _thinks(self, model: str) -> bool:
        """Capability probe (/api/show), cached per model — 73.2: `think` is only sent to models that support it."""
        cache = self.__dict__.setdefault("_think_caps", {})
        if model not in cache:
            try:
                cache[model] = "thinking" in self.client.capabilities(model)
            except Exception:
                cache[model] = True           # unknown → pass the flag through unchanged (old behaviour)
        return cache[model]

    def chat(self, model, messages, json_mode=False, temperature=0.4, tools=None,
             format_schema=None, think=None) -> dict:
        if think is not None and not self._thinks(model):
            think = None                      # 73.2: a non-thinking model would reject the parameter
        payload = {
            "model": model, "messages": messages, "stream": False,
            "options": {"temperature": temperature},
        }
        if format_schema is not None:
            payload["format"] = format_schema   # decode-time grammar constraint (Ollama ≥0.5)
        elif json_mode:
            payload["format"] = "json"
        if tools:
            payload["tools"] = tools
        if think is not None:
            payload["think"] = think   # native reasoning (Phase 58); reasoning returns in message.thinking
        last_exc = None
        for attempt in range(3):
            try:
                r = self.client._client.post(
                    f"{self.client.base_url}/api/chat", json=payload,
                    timeout=config.OLLAMA_TIMEOUT_S,
                )
                r.raise_for_status()
                msg = r.json().get("message", {})
                tool_calls = [
                    {"name": tc.get("function", {}).get("name", ""),
                     "arguments": tc.get("function", {}).get("arguments", {}) or {}}
                    for tc in (msg.get("tool_calls") or [])
                ]
                content = msg.get("content", "") or ""
                # Empty content AND no tool call = Ollama degradation (a legitimate tool-only turn
                # carries tool_calls). Retry with backoff so a transient thrash cannot silently
                # drop the routing/action signal (mirrors OllamaClient.embed / .chat).
                if not content and not tool_calls:
                    raise ProviderError("empty chat response (ollama degraded)")
                return {"content": content, "tool_calls": tool_calls,
                        "thinking": msg.get("thinking", "") or ""}   # native reasoning trace
            except Exception as exc:
                last_exc = exc
                log.warning("ollama provider chat attempt %d failed (%s): %s",
                            attempt + 1, model, exc)
                if attempt < 2:
                    time.sleep(0.6 * (attempt + 1))
        raise ProviderError(f"ollama chat failed ({model}): {last_exc}") from last_exc


class OpenAICompatProvider(BaseProvider):
    """Any OpenAI-compatible endpoint (OpenAI, LM Studio, vLLM, OpenRouter…)."""

    name = "openai"
    supports_native_tools = True
    supports_embeddings = True

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL")
                         or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = httpx.Client(timeout=config.OLLAMA_TIMEOUT_S)

    def available(self) -> bool:
        return bool(self.api_key)

    def chat(self, model, messages, json_mode=False, temperature=0.4, tools=None,
             format_schema=None, think=None) -> dict:
        # `think` is Ollama-native; the OpenAI-compat endpoint ignores it (accepted for uniformity).
        payload = {"model": model, "messages": messages, "temperature": temperature}
        if format_schema is not None:   # OpenAI structured outputs (json_schema)
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "router", "strict": True, "schema": format_schema}}
        elif json_mode:
            payload["response_format"] = {"type": "json_object"}
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
        try:
            r = self._client.post(
                f"{self.base_url}/chat/completions", json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
            tool_calls = []
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                import json as _json
                try:
                    args = _json.loads(fn.get("arguments") or "{}")
                except _json.JSONDecodeError:
                    args = {}
                tool_calls.append({"name": fn.get("name", ""), "arguments": args})
            return {"content": msg.get("content") or "", "tool_calls": tool_calls}
        except httpx.HTTPError as exc:
            raise ProviderError(f"openai-compat chat failed ({model}): {exc}") from exc

    def embed(self, model: str, text: str) -> List[float]:
        try:
            r = self._client.post(f"{self.base_url}/embeddings", json={"model": model, "input": text[:8000]},
                                  headers={"Authorization": f"Bearer {self.api_key}"})
            r.raise_for_status()
            return r.json()["data"][0]["embedding"]
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise ProviderError(f"openai-compat embed failed ({model}): {exc}") from exc


class AnthropicProvider(BaseProvider):
    name = "anthropic"
    supports_native_tools = True

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = httpx.Client(timeout=config.OLLAMA_TIMEOUT_S)

    def available(self) -> bool:
        return bool(self.api_key)

    def chat(self, model, messages, json_mode=False, temperature=0.4, tools=None,
             format_schema=None, think=None) -> dict:
        # Anthropic has no json_schema `format` or Ollama `think`; both are no-ops here (the router/
        # native-thinking path runs on the local ollama role). Params accepted for a uniform contract.
        system = ""
        chat_messages = []
        for m in messages:
            if m["role"] == "system":
                system += m["content"] + "\n"
            else:
                chat_messages.append(m)
        payload = {
            "model": model, "max_tokens": 4096, "temperature": temperature,
            "messages": chat_messages,
        }
        if system:
            payload["system"] = system.strip()
        if tools:
            payload["tools"] = [
                {"name": t["name"], "description": t.get("description", ""),
                 "input_schema": t.get("parameters", {"type": "object", "properties": {}})}
                for t in tools
            ]
        try:
            r = self._client.post(
                "https://api.anthropic.com/v1/messages", json=payload,
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            )
            r.raise_for_status()
            data = r.json()
            content, tool_calls = "", []
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
                elif block.get("type") == "tool_use":
                    tool_calls.append({"name": block.get("name", ""),
                                       "arguments": block.get("input", {}) or {}})
            return {"content": content, "tool_calls": tool_calls}
        except httpx.HTTPError as exc:
            raise ProviderError(f"anthropic chat failed ({model}): {exc}") from exc


class ProviderRegistry:
    """Holds provider instances; resolves (role) → (provider, model) via settings."""

    def __init__(self, settings, ollama_client: Optional[OllamaClient] = None):
        self.settings = settings
        self._providers: Dict[str, BaseProvider] = {
            "ollama": OllamaProvider(ollama_client),
            "openai": OpenAICompatProvider(),
            "anthropic": AnthropicProvider(),
        }

    def get(self, name: str) -> BaseProvider:
        if name not in self._providers:
            raise ProviderError(
                f"unknown provider '{name}' (available: {sorted(self._providers)})"
            )
        return self._providers[name]

    def resolve(self, role: str) -> tuple:
        """role → (provider_instance, model_name)."""
        if role not in ROLES:
            raise ProviderError(f"unknown role '{role}' (roles: {ROLES})")
        provider_name = self.settings.get(f"{role}_provider")
        model = self.settings.get(f"{role}_model")
        return self.get(provider_name), model

    def chat_for_role(self, role: str, messages: List[dict], json_mode: bool = False,
                      temperature: float = 0.4, tools: Optional[List[dict]] = None,
                      format_schema: Optional[dict] = None, think=None) -> dict:
        provider, model = self.resolve(role)
        if think is not None and getattr(provider, "name", "") != "ollama":
            think = None                      # 73.2: only Ollama drives native reasoning; others use the prompt path
        return provider.chat(model, messages, json_mode=json_mode, temperature=temperature,
                             tools=tools, format_schema=format_schema, think=think)

    def embed_for_role(self, text: str) -> List[float]:
        provider, model = self.resolve("embed")
        return provider.embed(model, text)

    def status(self) -> dict:
        return {
            name: {"available": p.available(), "models": p.models()[:40],
                   "embeddings": p.supports_embeddings}
            for name, p in self._providers.items()
        }
