"""Thin Ollama client: chat + embeddings, with timeouts, one retry, availability probe."""

from __future__ import annotations

import json
import logging
import time
from typing import List, Optional

import httpx

from . import config

log = logging.getLogger("hmgfu.ollama")


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or config.OLLAMA_URL).rstrip("/")
        self._client = httpx.Client(timeout=config.OLLAMA_TIMEOUT_S)

    def available(self) -> bool:
        try:
            r = self._client.get(f"{self.base_url}/api/tags", timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    def models(self) -> List[str]:
        r = self._client.get(f"{self.base_url}/api/tags")
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]

    def capabilities(self, model: str) -> List[str]:
        """Cached model capabilities from /api/show, e.g. ['completion','tools','thinking']
        (Phase 58) — lets the system drive native reasoning only on models that support it,
        model-agnostically. Fails soft to [] so a probe error never blocks a turn."""
        cache = getattr(self, "_caps_cache", None)
        if cache is None:
            cache = self._caps_cache = {}
        if model not in cache:
            try:
                r = self._client.post(f"{self.base_url}/api/show", json={"model": model}, timeout=15.0)
                r.raise_for_status()
                cache[model] = r.json().get("capabilities", []) or []
            except Exception:
                cache[model] = []
        return cache[model]

    def chat(self, model: str, messages: List[dict], json_mode: bool = False,
             temperature: float = 0.4, timeout: Optional[float] = None,
             num_ctx: Optional[int] = None, format_schema: Optional[dict] = None,
             think: Optional[bool] = None) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if think is not None:
            payload["think"] = think            # 73.2: native reasoning off for classification calls (mirrors providers)
        if format_schema is not None:
            payload["format"] = format_schema   # decode-time grammar constraint (Phase 57)
        elif json_mode:
            payload["format"] = "json"
        if num_ctx:
            payload["options"]["num_ctx"] = num_ctx
        last_err = None
        for attempt in range(3):
            try:
                r = self._client.post(
                    f"{self.base_url}/api/chat", json=payload,
                    timeout=timeout or config.OLLAMA_TIMEOUT_S,
                )
                r.raise_for_status()
                content = r.json().get("message", {}).get("content", "") or ""
                # Ollama under memory pressure answers 200 with EMPTY content — a silent
                # degradation that would zero nano routing/extraction signals (→ actions lost).
                # Treat as transient and retry with backoff, mirroring embed(); a nano JSON
                # reply is never legitimately empty.
                if not content:
                    raise OllamaError("empty chat response")
                return content
            except Exception as exc:  # retry on transient failures, including empty responses
                last_err = exc
                log.warning("ollama chat attempt %d failed (%s): %s", attempt + 1, model, exc)
                if attempt < 2:
                    time.sleep(0.6 * (attempt + 1))
        raise OllamaError(f"chat failed for {model}: {last_err}")

    def embed(self, text: str, model: Optional[str] = None) -> List[float]:
        payload = {"model": model or config.EMBED_MODEL, "input": text[:8000]}
        last_err = None
        for attempt in range(2):
            try:
                r = self._client.post(f"{self.base_url}/api/embed", json=payload, timeout=60.0)
                r.raise_for_status()
                embeddings = r.json().get("embeddings") or []
                if not embeddings:
                    raise OllamaError("empty embedding response")
                return embeddings[0]
            except Exception as exc:
                last_err = exc
                log.warning("ollama embed attempt %d failed: %s", attempt + 1, exc)
                if attempt == 0:
                    time.sleep(0.5)
        raise OllamaError(f"embed failed: {last_err}")

    def close(self) -> None:
        self._client.close()
