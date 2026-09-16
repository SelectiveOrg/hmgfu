"""Memory sensitizer — nano-model signal extraction with deterministic fallback.

THEORY §11 step 2 ('extract entities, topics, intent and emotion') and issue 8:
the pipeline must NEVER fail because a 1.5B model emitted broken JSON. Three-stage parse,
then a heuristic fallback. Every extraction is tagged extractor="nano"|"fallback".
"""

from __future__ import annotations

import json
import json
import logging
import re
from typing import List, Optional

from . import config
from .models import MemoryPoint
from .ollama_client import OllamaClient, OllamaError
from .runtime_context import router_prompt as _router_time   # 93.R3: no seconds for the classifier
from .runtime_context import runtime_prompt as _time_context

log = logging.getLogger("hmgfu.sensitizer")


def _cluster_bullets(points: List["MemoryPoint"]) -> str:
    from .fu_math import age_label
    return "\n".join(f"- ({age_label(p.timestamp)}) {p.summary or p.content[:120]}"
                     for p in points[:15])


# grounding + tense rules shared by the dream-worker prompts (P1: "must not make assumptions")
_GROUNDING_RULES = (
    " Use ONLY what the memories explicitly state — do not infer, invent or generalise beyond"
    " them. Each memory shows its age in parentheses. PRESERVE TIME: a past observation must be"
    " phrased as past (e.g. \"as of 3 days ago\" / \"was\"), NEVER as 'currently' or 'is now'."
)




# pure schema/sanitisation half lives in extraction_schema.py (400-line rule); re-exported
# here so existing imports (`from hmgfu.sensitizer import _sanitise, Extraction`) keep working.
from .extraction_schema import (Extraction, _DEFAULTS, _as_str_list,  # noqa: F401  (Rule 11)
                                _clamped, _sanitise)


# 92.E5R: one rule for "our own defect", owned by turn_router and imported rather than copied --
# parse_nano_json is json plus regex, so nothing here can turn model output into one of these either.
from .turn_router import reraise_if_ours as _reraise_if_ours   # noqa: E402


def parse_nano_json(text: str) -> Optional[dict]:
    """Three-stage tolerant parse (THEORY issue 8)."""
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)   # stage 2: first {...} block
    if match:
        try:
            obj = json.loads(match.group(0))
            return obj if isinstance(obj, dict) else None
        except (json.JSONDecodeError, ValueError):
            pass
    out = {}                                        # stage 3: per-field scavenging
    for key in ("title", "summary", "type", "intent"):
        m = re.search(rf'"{key}"\s*:\s*"([^"]*)"', text)
        if m:
            out[key] = m.group(1)
    for key in ("conversation_act", "freshness"):
        m = re.search(rf'"{key}"\s*:\s*"([^"]*)"', text)
        if m:
            out[key] = m.group(1)
    for key in ("action_requested", "needs_memory", "runtime_context_sufficient"):
        m = re.search(rf'"{key}"\s*:\s*(true|false)', text, re.IGNORECASE)
        if m:
            out[key] = m.group(1).lower() == "true"
    for key in ("emotional_valence", "emotional_intensity", "importance",
                "confidence", "novelty", "utility"):
        m = re.search(rf'"{key}"\s*:\s*(-?\d+(?:\.\d+)?)', text)
        if m:
            out[key] = float(m.group(1))
    for key in ("keywords", "entities", "topics", "requested_tools", "runtime_context_keys"):
        m = re.search(rf'"{key}"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if m:
            out[key] = re.findall(r'"([^"]+)"', m.group(1))
    return out or None




from .heuristic_extract import _NEGATIVE, _POSITIVE, _STOPWORDS, _is_interrogative, heuristic_extract  # noqa: E402,F401  (80.2 split; Rule 11)


class Sensitizer:
    """Nano-model front-end for extraction, relation judgement and summaries."""

    def __init__(self, client: Optional[OllamaClient] = None, enabled: bool = True):
        self._last_route_trace = None        # 95.10: {nano, router, fused} of the last fold, read once by the trace
        self.client = client
        self.enabled = enabled and client is not None   # master: client availability
        self._role_chat = None
        self._action_catalog_provider = None
        self._pre_router = None                     # 79.3: callable(text) -> route dict | None (bound by the agent)
        self._directives_provider = None
        self._route_exemplars_provider = None
        # runtime gates (Settings UI): off → deterministic fallbacks, never a crash
        self.extract_enabled = True    # extraction nano
        self.dream_enabled = True      # dream worker (scoring/summaries/insights)

    def bind_pre_router(self, fn) -> None:
        """79.3: a deterministic pre-router; when it returns a route the model router is not called this turn."""
        self._pre_router = fn

    def bind_role_chat(self, role_chat) -> None:
        """Route nano/dream calls through runtime provider+model settings."""
        self._role_chat = role_chat
        self.enabled = True

    def bind_action_catalog(self, registry) -> None:
        """Read the live registry on each extraction so installed skills route immediately."""
        self._action_catalog_provider = lambda: registry.schemas

    def bind_directives(self, provider) -> None:
        """Read the ACTIVE standing directives on each routing pass so the router can reason about
        a CHANGE or STOP of one (Phase 55). `provider` returns the DirectiveStore.active() list."""
        self._directives_provider = provider

    def bind_route_exemplars(self, provider) -> None:
        """`provider(text)` → learned few-shot block of CONFIRMED past routing corrections most
        similar to this turn (RouteMemory.exemplars_for) — the router improves with experience
        (Phase 56). Empty string when nothing relevant."""
        self._route_exemplars_provider = provider

    def bind_learning_examples(self, engine) -> None:
        """93.E5: the engine, so mode `adapt` can offer perception meanings a human CONFIRMED."""
        self._learning_engine = engine

    def _learning_on(self) -> bool:
        from .learning_perception import learning_on
        return learning_on(getattr(self, "_learning_engine", None))

    def _pending_question_text(self, session_id: str) -> str:
        from .learning_perception import pending_question
        return pending_question(getattr(self, "_learning_engine", None), session_id)

    def _pending_needs_text(self, session_id: str) -> str:
        from .learning_perception import pending_needs
        return pending_needs(getattr(self, "_learning_engine", None), session_id)

    def _learning_examples_text(self, text: str) -> str:
        from .learning_perception import confirmed_examples
        return confirmed_examples(getattr(self, "_learning_engine", None))

    def _route_exemplars_text(self, text: str) -> str:
        if self._route_exemplars_provider is None:
            return ""
        try:
            return self._route_exemplars_provider(text) or ""
        except Exception:
            return ""

    def _record_route(self, nano: dict, router, fused: dict) -> None:
        """95.10: keep the two stages the trace could never show; emit_context_pack emits and clears them."""
        self._last_route_trace = {"nano": nano, "router": router, "fused": dict(fused)}

    def _directives_text(self) -> str:
        """Compact 'kind: value' list of active directives for the router prompt (empty if none)."""
        if self._directives_provider is None:
            return ""
        try:
            return "\n".join(f"- {d['kind']}: {d['value']}" for d in self._directives_provider())
        except Exception:
            return ""

    def _action_catalog(self) -> dict:
        if self._action_catalog_provider is None:
            return {}
        try:
            return dict(self._action_catalog_provider())
        except Exception:
            return {}

    def _chat(self, role: str, messages: list, **kwargs) -> str:
        if self._role_chat is not None:
            return self._role_chat(role, messages, **kwargs)["content"]
        model = {"nano": config.NANO_MODEL, "router": config.ROUTER_MODEL, "chat": config.CHAT_MODEL}.get(role, config.DREAM_MODEL)
        return self.client.chat(model, messages, timeout=config.NANO_TIMEOUT_S, **kwargs)   # 73.2: role-aware fallback

    def extract(self, text: str, runtime_context=None, route: bool = False, nano: bool = True) -> Extraction:
        """`nano=False` (80.2): no nano call — the heuristic extraction plus the model router (when `route`); the caller
        runs the nano later in the tail and stores its fields on the point."""
        route_future, catalog = None, {}
        if self.enabled and self.extract_enabled:
            try:
                catalog = self._action_catalog()
                from .turn_router import EXTRACT_PROMPT, catalog_json
                catalog_text = catalog_json(catalog)
                route_future = None
                pre = None
                if route and self._pre_router is not None:  # 79.3: the deterministic pre-router decides first
                    try:
                        pre = self._pre_router(text)
                    except Exception as exc:
                        _reraise_if_ours(exc)
                        log.warning("pre-router failed (%s); model router runs", exc)
                        pre = None
                if route and pre is not None and pre.get("skip_nano"):      # 79.6: no model call at all on a claimed turn
                    fb = heuristic_extract(text)
                    merged = dict(fb)
                    merged.update({k: v for k, v in pre.items() if k != "skip_nano"})
                    out = _sanitise(merged, catalog)
                    for key in ("keywords", "entities", "topics", "title", "summary"):
                        if not out.get(key):
                            out[key] = fb[key]
                    out["extractor"] = "fallback+bypass"
                    return out
                if route and pre is None:                   # 73.2(a″): the router runs WHILE the nano extracts
                    from .turn_router import router_schema, start_route
                    route_future = start_route(self._chat, parse_nano_json, text, _router_time(runtime_context),
                                               catalog_text, self._directives_text(), self._route_exemplars_text(text),
                                               router_schema(list(catalog),
                                                             learning=self._learning_on()),
                                               self._learning_examples_text(text),
                                               self._pending_question_text(
                                                   getattr(self, "_turn_session_id", "")),
                                               self._pending_needs_text(
                                                   getattr(self, "_turn_session_id", "")))
                if not nano:                                # 80.2: the nano is off the pre-reply path — heuristic + router
                    fb = heuristic_extract(text)
                    merged = dict(fb)
                    if pre is not None:
                        merged.update({k: v for k, v in pre.items() if k != "skip_nano"})
                    elif route_future is not None:
                        from .turn_router import merge_route
                        merged = merge_route(merged, route_future, on_fused=self._record_route)
                        merged.setdefault("route_source", "model")
                    out = _sanitise(merged, catalog)
                    for key in ("keywords", "entities", "topics", "title", "summary"):
                        if not out.get(key):
                            out[key] = fb[key]
                    out["extractor"] = "heuristic+router"
                    return out
                reply = self._chat(
                    "nano",
                    [{"role": "system", "content": _time_context(runtime_context) + "\n" +
                      EXTRACT_PROMPT + "\nRUNTIME TOOL CATALOG:\n" + catalog_text},
                     {"role": "user", "content": text[:4000]}],
                    json_mode=True, temperature=0.1,
                )
                raw = parse_nano_json(reply)
                if raw:
                    if route and pre is not None:
                        raw.update(pre)                     # 79.3: the pre-router's route, no model call
                    elif route:
                        from .turn_router import merge_route
                        # Phase 57: grammar-constrained router (schema from the LIVE catalog); 73.2(a″): it ran
                        # concurrently with the nano extraction — fold its classification in now.
                        raw = merge_route(raw, route_future, on_fused=self._record_route)
                        raw.setdefault("route_source", "model")
                    out = _sanitise(raw, catalog)
                    if route and out.get("directive") and not out["directive"].get("clear"):
                        directive = out["directive"]
                        # Preserve the user's own multilingual instruction verbatim. For opener/
                        # closer, generate a fallback example that MATCHES the content spec (joke,
                        # fact, quote…) — the enforce backstop uses it when the model forgets.
                        directive["instruction"] = text[:500].strip()
                        if directive["kind"] in ("conversation_opener", "conversation_closer"):
                            from .turn_router import resilient_content
                            directive["fallback_text"] = resilient_content(
                                self._chat, parse_nano_json, directive["value"]
                            ) or directive["fallback_text"]
                    fallback = heuristic_extract(text)
                    # nano models often skip list fields; backfill from heuristics
                    for key in ("keywords", "entities", "topics"):
                        if not out[key]:
                            out[key] = fallback[key]
                    if not out["title"]:
                        out["title"] = fallback["title"]
                    if not out["summary"]:
                        out["summary"] = fallback["summary"]
                    out["extractor"] = "nano"
                    return out
                log.warning("nano extraction unparseable; using heuristic fallback")
            except Exception as exc:
                _reraise_if_ours(exc)
                log.warning("nano extraction failed (%s); using heuristic fallback", exc)
        fallback = heuristic_extract(text)
        if route_future is not None:                  # 73.4: the router ran concurrently — its classification counts
            from .turn_router import merge_route     # even when the nano failed (and the worker is joined, not leaked)
            merged = merge_route(dict(fallback), route_future, on_fused=self._record_route)
            out = _sanitise(merged, catalog)
            for key in ("keywords", "entities", "topics", "title", "summary"):
                if not out.get(key):
                    out[key] = fallback[key]
            out["extractor"] = "fallback+router"
            return out
        return fallback

    def score_pair(self, kind: str, a: str, b: str,
                   a_ts: Optional[str] = None, b_ts: Optional[str] = None) -> Optional[float]:
        """Ask the dream nano to score contradiction/analogy/causality between two memories.
        Timestamps (optional, backward-compatible) give the judge time perception (P1): two
        observations of a changing quantity at different times are a time series, not a conflict."""
        if not (self.enabled and self.dream_enabled):
            return None
        prompts = {
            "contradiction": "Do these two memories CONTRADICT each other (one invalidates the other)? "
                             "Observations of a CHANGING quantity (weather, price, status) taken at "
                             "different times are a time series, NOT a contradiction — score those 0.",
            "analogy": "Are these two memories DEEPLY ANALOGOUS (same underlying structure, different surface)?",
            "causal": "Does the first memory plausibly CAUSE or directly lead to the second?",
        }
        from .fu_math import age_label
        tag_a = f" ({age_label(a_ts)})" if a_ts else ""
        tag_b = f" ({age_label(b_ts)})" if b_ts else ""
        try:
            reply = self._chat(
                "dream",
                [{"role": "system",
                  "content": f"{_time_context()} {prompts[kind]} Reply ONLY with JSON: {{\"score\": 0.0 to 1.0}}"},
                 {"role": "user", "content": f"Memory 1{tag_a}: {a[:800]}\n\nMemory 2{tag_b}: {b[:800]}"}],
                json_mode=True, temperature=0.0,
            )
            raw = parse_nano_json(reply)
            if raw and "score" in raw:
                return _clamped(raw["score"], 0, 1, None)
        except Exception as exc:
            log.warning("nano %s scoring failed: %s", kind, exc)
        return None

    def summarise_cluster(self, points: List[MemoryPoint]) -> str:
        """Macro summary (THEORY §18). Falls back to a joined summary line."""
        bullet_lines = _cluster_bullets(points)
        if self.enabled and self.dream_enabled:
            try:
                reply = self._chat(
                    "dream",
                    [{"role": "system",
                      "content": _time_context()
                                 + " Merge these related memories into ONE macro-memory sentence "
                                   "(max 40 words) capturing the underlying pattern."
                                 + _GROUNDING_RULES + " Reply with the sentence only."},
                     {"role": "user", "content": bullet_lines}],
                    temperature=0.2,
                )
                cleaned = reply.strip().strip('"')
                if cleaned:
                    return cleaned[:400]
            except Exception as exc:
                log.warning("cluster summary failed: %s", exc)
        top = max(points, key=lambda p: p.density, default=None)
        return f"Pattern over {len(points)} memories: {top.summary or top.title}" if top else ""

    def dream_insight(self, stats: dict, macro_summaries: List[str]) -> List[str]:
        if not (self.enabled and self.dream_enabled) or not macro_summaries:
            return []
        try:
            reply = self._chat(
                "dream",
                [{"role": "system",
                  "content": _time_context()
                             + " You are the dreaming subconscious of a memory system. Given macro-memories, "
                               "produce at most 3 short insights (emerging patterns). State ONLY patterns the "
                               "given macro-memories directly support — no speculation, no invented facts, and "
                               "NEVER present a past observation (weather, prices, status) as current. "
                               "Reply ONLY JSON: {\"insights\": [\"...\"]}"},
                 {"role": "user", "content": json.dumps({"stats": stats, "macros": macro_summaries[:10]})}],
                json_mode=True, temperature=0.6,
            )
            raw = parse_nano_json(reply)
            if raw:
                return _as_str_list(raw.get("insights"), 3)
        except Exception as exc:
            log.warning("dream insight failed: %s", exc)
        return []
