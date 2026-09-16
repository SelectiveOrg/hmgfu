"""Phase 73.0 — per-turn stage timing and a ledger of every model call (no behaviour change).

Why: a turn on gemma4:12b takes 20–120 s and nothing said where. Every model call (chat, nano, embeddings) leaves the
process through an `httpx.Client.post(...)`, so ONE wrapper at that choke point sees them all — the Ollama client, the
Ollama provider and the OpenAI-compatible provider alike — with the model name from the payload and the token counts
Ollama reports (`prompt_eval_count`, `eval_count`). `TurnTimer` adds coarse stage marks along the agent turn and folds the
calls made on the turn's thread into a summary that is persisted with the turn and emitted as `turn_timings`.
Background threads (dreams) are counted separately so they never inflate a turn.
"""
from __future__ import annotations

import contextvars
import threading
import time
from typing import Any, Dict, List, Optional

_LOCK = threading.Lock()
TURN_OWNER: contextvars.ContextVar = contextvars.ContextVar("hmgfu_turn_owner", default=None)   # 73.2(a″)
_CALLS: List[dict] = []
_MAX_CALLS = 5000


def _kind(url: str) -> str:
    path = url.split("?", 1)[0].rstrip("/")
    if path.endswith("/api/chat") or path.endswith("/chat/completions"):
        return "chat"
    if path.endswith("/api/embed") or path.endswith("/api/embeddings") or path.endswith("/embeddings"):
        return "embed"
    return "other"


class LedgeredClient:
    """Wraps an `httpx.Client`: every `post()` is timed and recorded (kind, model, ms, tokens, thread)."""

    def __init__(self, inner: Any):
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def post(self, url: str, **kw: Any):
        t0 = time.perf_counter()
        resp, ok = None, True
        try:
            resp = self._inner.post(url, **kw)
            return resp
        except Exception:
            ok = False
            raise
        finally:
            payload = kw.get("json") or {}
            rec = {"kind": _kind(str(url)), "model": str(payload.get("model", "") or ""),
                   "ms": round((time.perf_counter() - t0) * 1000, 1), "ok": ok,
                   "thread": TURN_OWNER.get() or threading.current_thread().name, "t": time.time()}
            if resp is not None:
                try:
                    body = resp.json()
                    if isinstance(body, dict):
                        rec["prompt_tokens"] = body.get("prompt_eval_count")
                        rec["eval_tokens"] = body.get("eval_count")
                        usage = body.get("usage") or {}
                        if usage:                                   # OpenAI-compatible backends
                            rec["prompt_tokens"] = usage.get("prompt_tokens")
                            rec["eval_tokens"] = usage.get("completion_tokens")
                except Exception:
                    pass
            with _LOCK:
                _CALLS.append(rec)
                if len(_CALLS) > _MAX_CALLS:
                    del _CALLS[: len(_CALLS) - _MAX_CALLS]


def instrument(obj: Any, attr: str = "_client") -> bool:
    """Replace `obj.<attr>` with a LedgeredClient (idempotent). Returns True when a wrap happened."""
    inner = getattr(obj, attr, None)
    if inner is None or isinstance(inner, LedgeredClient):
        return False
    setattr(obj, attr, LedgeredClient(inner))
    return True


def instrument_engine(engine: Any) -> int:
    """Wrap every HTTP client the engine can reach: the Ollama client and each provider's own client."""
    wrapped = 0
    client = getattr(engine, "client", None)
    if client is not None:
        wrapped += instrument(client)
    registry = getattr(engine, "registry", None)
    seen: set = set()
    for value in list(vars(registry).values()) if registry is not None else []:
        candidates = list(value.values()) if isinstance(value, dict) else [value]
        for prov in candidates:
            if id(prov) in seen or prov is None:
                continue
            seen.add(id(prov))
            wrapped += instrument(prov)
            wrapped += instrument(getattr(prov, "client", None)) if getattr(prov, "client", None) is not None else 0
    return wrapped


def calls_since(index: int) -> List[dict]:
    with _LOCK:
        return list(_CALLS[index:])


def call_index() -> int:
    with _LOCK:
        return len(_CALLS)


class TurnTimer:
    """Coarse stage marks along one agent turn + the model calls made on the turn's thread."""

    def __init__(self, engine: Any):
        self.engine = engine
        self.t0 = self.last = time.perf_counter()
        self.stages: Dict[str, float] = {}
        self.reply_ms: Optional[float] = None
        self.start_index = call_index()
        self.thread = f"turn-{id(self)}"                # the owner token: every call made under this turn carries it
        self.threads = {self.thread}
        self._token = TURN_OWNER.set(self.thread)      # workers created with contextvars.copy_context() inherit it

    def adopt_thread(self) -> None:
        """73.2(a): the async tail runs on a worker — its model calls belong to this turn, not to 'background'."""
        TURN_OWNER.set(self.thread)
        self.threads.add(self.thread)

    def mark(self, stage: str) -> None:
        now = time.perf_counter()
        self.stages[stage] = round(self.stages.get(stage, 0.0) + (now - self.last) * 1000, 1)
        self.last = now

    def mark_reply(self) -> None:
        self.reply_ms = round((time.perf_counter() - self.t0) * 1000, 1)
        self.calls_before_reply = len([c for c in calls_since(self.start_index) if c["thread"] in self.threads])   # 80.2

    def _role(self, call: dict) -> str:
        if call["kind"] == "embed":
            return "embed"
        settings = getattr(self.engine, "settings", None)
        get = settings.get if settings is not None else (lambda k, d=None: d)
        model = call.get("model", "")
        if model and model == get("chat_model"):
            return "chat"
        if model and model in {get("nano_model"), get("dream_model"), get("grader_model")}:
            return "nano"
        return "chat" if call["kind"] == "chat" else "other"

    def finish(self) -> dict:
        total = round((time.perf_counter() - self.t0) * 1000, 1)
        try:
            TURN_OWNER.reset(self._token)              # this context no longer owns new calls
        except (ValueError, LookupError, AttributeError, RuntimeError):
            pass                                       # finish() from another context (the async tail): nothing to reset
        calls = calls_since(self.start_index)
        mine = [c for c in calls if c["thread"] in self.threads]
        counts: Dict[str, int] = {"chat": 0, "nano": 0, "embed": 0, "other": 0}
        ms: Dict[str, float] = {k: 0.0 for k in counts}
        tokens = {"prompt": 0, "eval": 0}
        for c in mine:
            role = self._role(c)
            counts[role] += 1
            ms[role] = round(ms[role] + c["ms"], 1)
            tokens["prompt"] += int(c.get("prompt_tokens") or 0)
            tokens["eval"] += int(c.get("eval_tokens") or 0)
        return {"total_ms": total, "reply_ms": self.reply_ms, "stages": dict(self.stages),
                "calls": counts, "calls_ms": ms, "tokens": tokens,
                "model_calls": len(mine), "background_calls": len(calls) - len(mine),
                "calls_before_reply": getattr(self, "calls_before_reply", None),      # 80.2: the user-visible cost
                "detail": [{k: c.get(k) for k in ("kind", "model", "ms", "ok", "prompt_tokens", "eval_tokens")}
                           for c in mine[:24]]}
