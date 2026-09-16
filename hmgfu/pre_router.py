"""Deterministic PRE-ROUTER (Phase 79.3): decide the two turn classes whose reference routes are uniform on the sealed
routing set WITHOUT a model call; everything else returns None and the model router runs as before.

  (ii) a plain question about the user's own ledger attribute ("what is my name?", "onde é que eu trabalho?") →
       the recall route: action_requested, requested_tools [memory_search], conversation_act question, needs_memory.
  (iii) a plain first-person fact statement ("my favourite colour is amber", "here is the updated link …") →
       the statement route: no action, no tools, conversation_act statement, needs_memory.

Refusals (fall through to the model): any tool named, an effect requested, a standing-rule cue, an imperative opener
("remember that…", "lembra-te que…"), a correction/negation (the reference routes those as instructions), a question that
does not name a ledger attribute, anything else. Built ONLY from detectors that already exist (speech_act, fact_detect,
slots, utterance). The route dict has the same keys the model router returns; `route_source` says which path decided."""
from __future__ import annotations

import re
from typing import Iterable, Optional

from .fact_detect import _NEG_NEAR, detect_facts
from .slots import is_slot, mentions_attribute, normalise_key
from .speech_act import has_standing_cue, is_interrogative, refers_to_self, requests_side_effect
from .utterance import declarative_text

_IMPERATIVE = re.compile(r"^\s*(?:please\s+|por favor\s+)?(?:remember|note|record|save|store|lembra(?:-te)?|nota|regista|guarda|anota)\b",
                         re.IGNORECASE)
_CURRENT = re.compile(r"\b(now|right now|currently|at the moment|today|tonight|agora|neste momento|hoje|actualmente|atualmente)\b",
                      re.IGNORECASE)
_META = re.compile(r"\b(your memory|how do you|how does your|como (?:é que )?te lembras|como funciona)\b", re.IGNORECASE)


def mentions_tool(text: str, catalog_names: Iterable[str]) -> bool:
    low = (text or "").lower()
    return any(name and name.lower() in low for name in catalog_names or [])


def _about_ledger_attribute(text: str, facts) -> bool:
    try:
        keys = {f["key"] for f in facts.active() if f.get("slot")}
    except Exception:
        return False
    return any(mentions_attribute(k, text or "") for k in keys)


def pre_route(text: str, catalog_names: Iterable[str], facts) -> Optional[dict]:
    t = (text or "").strip()
    if not t or mentions_tool(t, catalog_names) or requests_side_effect(t) or has_standing_cue(t) or _META.search(t):
        return None
    if is_interrogative(t):
        if refers_to_self(t) and _about_ledger_attribute(t, facts) and not _CURRENT.search(t):
            return {"action_requested": True, "requested_tools": ["memory_search"], "conversation_act": "question",
                    "needs_memory": True, "freshness": "historical", "feedback_polarity": None, "directive": None,
                    "route_source": "bypass"}
        return None
    if _IMPERATIVE.match(t) or _NEG_NEAR.search(t):
        return None                                 # corrections / negated statements: the reference routes them as instructions
    dets = detect_facts(declarative_text(t))
    if not dets or any(d.get("clear") or d.get("clear_value") or d.get("supersedes") for d in dets):
        return None
    if not any(is_slot(normalise_key(d["key"])) for d in dets if d.get("value")):
        return None
    return {"action_requested": False, "requested_tools": [], "conversation_act": "statement", "needs_memory": True,
            "freshness": "none", "feedback_polarity": None, "directive": None, "route_source": "bypass"}
