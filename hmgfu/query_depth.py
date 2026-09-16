"""Phase 86.1 — per-question retrieval DEPTH.

Phase 85 showed that cross-session AGGREGATION questions ("how many days did I take social media breaks in total?") are
retrieval-bound — a deeper recall recovers them — while every other question is diluted by depth. So the depth is decided
per question by a deterministic cue, never globally: when the question aggregates (counts, sums, totals, "how many
different …") and `retrieval_limit_aggregate` is set (> 0), that turn retrieves that many memories; every other turn keeps
`retrieval_limit`. One rule, two callers (the agent's retrieve and the LongMemEval harness's production arm).
"""
from __future__ import annotations

import re

_AGGREGATION = re.compile(
    r"\b(?:how many|how much|how often|how long (?:in total|altogether|overall)|in total|total(?:ly)?|altogether|combined|all together|"
    r"overall|sum of|number of times|count of|quantos|quantas|quanto|quanta|no total|ao todo|em total|somad[oa]s|"
    r"ao longo d[oa]s?|todas as vezes|quantas vezes)\b", re.IGNORECASE)
# a first-person statement is never a question about totals ("I have two cats" states, it does not aggregate)
_STATEMENT_HEAD = re.compile(r"^\s*(?:i|we|my|our|eu|n[oó]s|o meu|a minha|tenho|temos|moro|vivo|sou|chamo-me)\b", re.IGNORECASE)


def is_aggregation(text: str) -> bool:
    """True for a QUESTION that counts, sums or totals over several memories; False for statements and plain recall."""
    t = (text or "").strip()
    if not t or _STATEMENT_HEAD.match(t) and "?" not in t:
        return False
    return bool(_AGGREGATION.search(t))


def depth_for(text: str, settings, default: int | None = None) -> int:
    """The recall limit for THIS question: `retrieval_limit_aggregate` when the cue fires and the setting is on, else
    `retrieval_limit` (or `default` when given — the harness passes its k)."""
    base = int(default if default is not None else settings.get("retrieval_limit"))
    try:
        deep = int(settings.get("retrieval_limit_aggregate") or 0)
    except Exception:
        deep = 0
    if deep > 0 and is_aggregation(text):
        return deep
    return base
