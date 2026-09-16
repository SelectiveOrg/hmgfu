"""Extraction schema + sanitisation — the pure, model-free half of the sensitizer.

Split out of sensitizer.py (400-line rule): everything here is deterministic normalisation of
whatever JSON a nano/main router emitted into the one validated Extraction shape. No I/O, no
model calls — fully unit-testable.
"""

from __future__ import annotations

from typing import List

from . import config


class Extraction(dict):
    """Extraction result; plain dict with attribute access for convenience."""
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e


_DEFAULTS = {
    "title": "", "summary": "", "type": "message", "keywords": [], "entities": [],
    "topics": [], "emotional_valence": 0.0, "emotional_intensity": 0.0,
    "importance": 0.5, "confidence": 0.6, "novelty": 0.5, "utility": 0.5,
    "intent": "statement", "extractor": "fallback", "conversation_act": "statement",
    "action_requested": False, "requested_tools": [], "freshness": "none",
    "needs_memory": True, "runtime_context_keys": [], "runtime_context_sufficient": False,
    "directive": None, "feedback_polarity": "", "memory_update": None,   # 92.E4
}


def _clamped(v, lo, hi, default):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


def _as_str_list(v, cap: int) -> List[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if str(x).strip()][:cap]


def _sanitise(raw: dict, allowed_tools=None) -> Extraction:
    from .turn_router import MAX_REQUESTED_TOOLS, normalise_enum
    out = Extraction(_DEFAULTS)
    out["title"] = str(raw.get("title", ""))[:80]
    out["summary"] = str(raw.get("summary", ""))[:300]
    mtype = str(raw.get("type", "message"))
    out["type"] = mtype if mtype in config.MEMORY_TYPES else "message"
    out["keywords"] = _as_str_list(raw.get("keywords"), 6)
    out["entities"] = _as_str_list(raw.get("entities"), 8)
    out["topics"] = _as_str_list(raw.get("topics"), 4)
    out["emotional_valence"] = _clamped(raw.get("emotional_valence"), -1, 1, 0.0)
    out["emotional_intensity"] = _clamped(raw.get("emotional_intensity"), 0, 1, 0.0)
    out["importance"] = _clamped(raw.get("importance"), 0, 1, 0.5)
    out["confidence"] = _clamped(raw.get("confidence"), 0, 1, 0.6)
    out["novelty"] = _clamped(raw.get("novelty"), 0, 1, 0.5)
    out["utility"] = _clamped(raw.get("utility"), 0, 1, 0.5)
    intent = str(raw.get("intent", "statement"))
    out["intent"] = intent if intent in ("question", "task", "reflection", "emotional", "statement") else "statement"
    out["conversation_act"] = normalise_enum(raw.get("conversation_act"), {
        "greeting", "question", "instruction", "feedback", "statement"
    }, "statement")
    # Phase 56: the router judges feedback SENTIMENT semantically (any language) — this replaces
    # the lexical keyword classifier as the primary tool-grading signal.
    out["feedback_polarity"] = normalise_enum(
        raw.get("feedback_polarity"), {"positive", "negative"}, "")
    out["action_requested"] = raw.get("action_requested") is True
    allowed = set(allowed_tools or [])
    out["requested_tools"] = [
        name for name in _as_str_list(raw.get("requested_tools"), MAX_REQUESTED_TOOLS) if name in allowed   # 73.2 cap
    ]
    if out["requested_tools"]:
        out["action_requested"] = True
    out["freshness"] = normalise_enum(
        raw.get("freshness"), {"none", "historical", "current"}, "none"
    )
    out["needs_memory"] = raw.get("needs_memory", True) is not False
    runtime_allowed = {"now_local", "now_utc", "local_date", "local_time", "timezone_name", "utc_offset"}
    out["runtime_context_keys"] = [k for k in _as_str_list(
        raw.get("runtime_context_keys"), 6) if k in runtime_allowed]
    out["runtime_context_sufficient"] = raw.get("runtime_context_sufficient") is True
    # 90.G1 (H-A2): the router's contract — sufficient=true means the clock answers: list the exact keys, request no tool. A claim of
    # sufficiency that names NO key while requesting tools is inconsistent; it must not wipe the requested action (it silently
    # removed plan_task/write_file from a plain file request and left the model with no tool).
    if out["runtime_context_sufficient"] and not out["runtime_context_keys"] and out["requested_tools"]:
        out["runtime_context_sufficient"] = False
    if out["runtime_context_sufficient"]:
        out["requested_tools"], out["action_requested"] = [], False
    mu = raw.get("memory_update")                      # 92.E4: carried through, validated downstream
    out["memory_update"] = mu if isinstance(mu, dict) else None
    from .directives import sanitize_router_directive   # directive-domain normalisation
    directive = sanitize_router_directive(raw.get("directive"))
    if directive:
        out["directive"] = directive
    return out
